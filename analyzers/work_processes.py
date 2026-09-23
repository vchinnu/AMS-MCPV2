"""Work process analyzer — SM50/SM66 work process status.

Handles SapNetweaver_ABAPGetWPTable_CL — one row per ABAP work process per collection.

Key capabilities:
  - WP type distribution (DIA, BTC, UPD, SPO, ENQ)
  - Status classification (Running, Waiting, Hold, PRIV)
  - WP exhaustion detection (all DIA WPs busy → system stall)
  - PRIV mode cascade detection
  - Top programs and users consuming work processes
  - WP restart detection (Err_s > 0)
  - Per-WP-type server CPU % (BTC vs DIA vs UPD share of VM CPU)
  - Per-program server CPU % (when core count is available)

Supports Scenario 3 (System Stall / WP Exhaustion).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import domain_registry as dr
from analyzers import register


def _safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _compute_wall_clock_sec(rows: list[dict]) -> float | None:
    """Derive observation window in seconds from min/max TimeGenerated."""
    timestamps: list[datetime] = []
    for r in rows:
        ts_str = str(r.get("TimeGenerated", "")).strip()
        if not ts_str:
            continue
        try:
            timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
        except (ValueError, TypeError):
            continue
    if len(timestamps) < 2:
        return None
    delta = (max(timestamps) - min(timestamps)).total_seconds()
    return delta if delta > 0 else None


def _parse_core_count_from_context(context: str) -> tuple[int | None, str]:
    """Extract CPU core count from agent-provided context string.

    Checks SMON AVAILCPUS_d first, then falls back to Prometheus/generic patterns.
    Returns (core_count, source) where source is 'smon', 'prometheus', or 'context'.
    """
    if not context:
        return None, ""
    # Priority 1: SMON AVAILCPUS_d (e.g. "AVAILCPUS_d=32", "AVAILCPUS=16", "SMON: 32 cores")
    m = re.search(r'AVAILCPUS[_d]*\s*[=:]\s*(\d{1,3})', context, re.IGNORECASE)
    if m:
        return int(m.group(1)), "smon"
    m = re.search(r'SMON[:\s]+.*?(\d{1,3})\s*(?:v?cpus?|cores?)', context, re.IGNORECASE)
    if m:
        return int(m.group(1)), "smon"
    # Priority 2: Prometheus / generic patterns (e.g. "4 cores", "core_count=4")
    m = re.search(r'(\d{1,3})\s*(?:v?cpus?|cores?)', context, re.IGNORECASE)
    if m:
        return int(m.group(1)), "context"
    m = re.search(r'(?:cores?|cpus?|core_count|cpu_count)\s*[=:]\s*(\d{1,3})', context, re.IGNORECASE)
    if m:
        return int(m.group(1)), "context"
    return None, ""


def _parse_smon_cpu_from_context(context: str) -> dict[str, float]:
    """Extract SMON CPU metrics from context for cross-validation (informational only)."""
    result: dict[str, float] = {}
    if not context:
        return result
    for key in ("CPU_CONS_d", "USR_TOTAL_d", "SYS_TOTAL_d", "IDLE_TOTAL_d"):
        m = re.search(rf'{key}\s*[=:]\s*([\d.]+)', context, re.IGNORECASE)
        if m:
            try:
                result[key] = float(m.group(1))
            except ValueError:
                pass
    return result


@register("workprocess_status")
def analyze_work_processes(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate SM50/SM66 work process data.

    Flow:
      1. Group rows by hostname → per-host WP analysis
      2. Count WPs by type and status using domain knowledge labels
      3. Detect critical findings: WP exhaustion, PRIV cascade, WP restarts
      4. Identify top programs/users consuming WPs
      5. Return per-host summary with severity classification
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "workprocess_status",
                "summary": "No work process data returned.", "raw_row_count": 0, "context": context}

    total = len(rows)

    # ── Step 1: Group rows by hostname ───────────────────────────────────────
    hosts: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        host = str(row.get("hostname_s", "unknown")).strip()
        hosts[host].append(row)

    # ── Step 2: WP type and status distribution (all hosts) ──────────────────
    type_counts  = Counter(str(r.get("Typ_s", "")).strip() for r in rows)
    status_counts = Counter(str(r.get("Status_s", "")).strip() for r in rows)

    # Enrich with domain knowledge labels
    type_distribution = []
    for typ, count in type_counts.most_common():
        info = dr.classify_wp_type(typ)
        type_distribution.append({
            "type": typ, "label": info["label"],
            "description": info.get("description", ""), "count": count,
        })

    status_distribution = []
    for status, count in status_counts.most_common():
        info = dr.classify_wp_status(status)
        status_distribution.append({
            "status": status, "label": info["label"],
            "is_busy": info["is_busy"], "meaning": info["meaning"], "count": count,
        })

    # ── Step 3: Per-host analysis — detect critical findings ─────────────────
    findings: list[dict] = []
    warnings: list[dict] = []
    per_host_summary: dict[str, dict] = {}

    for host, host_rows in hosts.items():
        # Count DIA WPs by status on this host
        dia_rows = [r for r in host_rows if str(r.get("Typ_s", "")).strip() == "DIA"]
        dia_total = len(dia_rows)
        dia_busy  = sum(1 for r in dia_rows
                        if dr.classify_wp_status(str(r.get("Status_s", "")).strip())["is_busy"])

        # Count PRIV mode WPs on this host
        priv_rows = [r for r in host_rows if str(r.get("Reason_s", "")).strip() == "PRIV"]
        priv_count = len(priv_rows)

        # Count WP restarts (Err_s > 0) on this host
        restart_count = sum(1 for r in host_rows if _safe_int(r.get("Err_s")) > 0)

        # BTC WP status
        btc_rows = [r for r in host_rows if str(r.get("Typ_s", "")).strip() == "BTC"]
        btc_total = len(btc_rows)
        btc_busy  = sum(1 for r in btc_rows
                        if dr.classify_wp_status(str(r.get("Status_s", "")).strip())["is_busy"])

        per_host_summary[host] = {
            "total_wps": len(host_rows),
            "dia_total": dia_total,
            "dia_busy": dia_busy,
            "btc_total": btc_total,
            "btc_busy": btc_busy,
            "priv_count": priv_count,
            "wp_restarts": restart_count,
        }

        # ── CRITICAL: WP Exhaustion — all DIA WPs are busy ──────────────────
        # This is the key Scenario 3 signal. If every dialog WP is in
        # Running/Hold/Semaphore, no new dialog requests can be processed.
        if dia_total > 0 and dia_busy == dia_total:
            findings.append({
                "finding": "WP_EXHAUSTION",
                "severity": "critical",
                "host": host,
                "dia_total": dia_total,
                "dia_busy": dia_busy,
                "meaning": (
                    f"ALL {dia_total} dialog WPs on {host} are busy — "
                    f"no WP available for new user requests. System is stalled."
                ),
                "investigation_hints": [
                    "Identify which programs hold the DIA WPs — see top_programs below.",
                    "Check SMON DIAQ_d for dialog queue depth confirmation.",
                    "This is a Scenario 3 (System Stall) signal.",
                ],
            })

        # ── WARNING/CRITICAL: PRIV mode WPs ─────────────────────────────────
        # PRIV mode means a WP is holding extended memory exclusively.
        # Each PRIV WP reduces the pool available to other users.
        priv_warn_thresh = dr.WP_THRESHOLDS.get("PRIV_WARNING", 2)
        priv_crit_thresh = dr.WP_THRESHOLDS.get("PRIV_CRITICAL", 5)

        if priv_count >= priv_crit_thresh:
            priv_info = dr.classify_wp_reason("PRIV")
            priv_programs = [str(r.get("Program_s", "")) for r in priv_rows]
            priv_users    = [str(r.get("User_s", "")) for r in priv_rows]
            findings.append({
                "finding": "PRIV_MODE_CRITICAL",
                "severity": "critical",
                "host": host,
                "priv_count": priv_count,
                "priv_programs": sorted(set(priv_programs)),
                "priv_users": sorted(set(priv_users)),
                "meaning": priv_info["meaning"],
                "investigation_hints": priv_info.get("investigation_hints", []),
            })
        elif priv_count >= priv_warn_thresh:
            priv_info = dr.classify_wp_reason("PRIV")
            priv_programs = [str(r.get("Program_s", "")) for r in priv_rows]
            priv_users    = [str(r.get("User_s", "")) for r in priv_rows]
            warnings.append({
                "finding": "PRIV_MODE_WARNING",
                "severity": "warning",
                "host": host,
                "priv_count": priv_count,
                "priv_programs": sorted(set(priv_programs)),
                "priv_users": sorted(set(priv_users)),
                "meaning": priv_info["meaning"],
                "investigation_hints": priv_info.get("investigation_hints", []),
            })

        # ── WARNING: WP restarts detected ────────────────────────────────────
        if restart_count >= dr.WP_THRESHOLDS.get("ERR_RESTART_WARNING", 1):
            restart_rows = [r for r in host_rows if _safe_int(r.get("Err_s")) > 0]
            restart_types = Counter(str(r.get("Typ_s", "")) for r in restart_rows)
            warnings.append({
                "finding": "WP_RESTARTS",
                "severity": "warning",
                "host": host,
                "restart_count": restart_count,
                "restart_by_type": dict(restart_types),
                "meaning": f"{restart_count} WP(s) on {host} have been restarted (Err_s > 0).",
                "investigation_hints": [
                    "WP restarts indicate instability — check SM21 for Q02/Q0Q messages.",
                    "Check OS metrics for memory/CPU pressure on this host.",
                ],
            })

    # ── Step 4: Top programs and users consuming WPs (running WPs only) ──────
    running_rows = [r for r in rows
                    if dr.classify_wp_status(str(r.get("Status_s", "")).strip())["is_busy"]]

    top_programs = Counter(str(r.get("Program_s", "")).strip() for r in running_rows
                           if str(r.get("Program_s", "")).strip())
    top_users    = Counter(str(r.get("User_s", "")).strip() for r in running_rows
                           if str(r.get("User_s", "")).strip())

    # ── Step 5: CPU attribution per WP type ──────────────────────────────────
    # Compute Cpu_s deltas and rank programs by actual CPU consumed.
    # Uses domain knowledge for parsing, delta computation, and reliability.
    cpu_deltas = dr.compute_wp_cpu_deltas(rows)
    cpu_ranking: dict = {}
    cpu_attribution_available = False
    wp_type_server_cpu: dict = {}  # per-WP-type server CPU %

    # Derive wall-clock and core count for server CPU % calculation
    wall_clock_sec = _compute_wall_clock_sec(rows)
    core_count, core_count_source = _parse_core_count_from_context(context)
    smon_cpu_metrics = _parse_smon_cpu_from_context(context)

    if cpu_deltas:
        # Check if we have enough snapshots for meaningful deltas
        max_snapshots = max(d["snapshots"] for d in cpu_deltas)
        min_snapshots_needed = dr.CPU_ATTRIBUTION_THRESHOLDS["MIN_SNAPSHOTS_FOR_DELTA"]

        if max_snapshots >= min_snapshots_needed:
            cpu_attribution_available = True
            cpu_ranking = dr.rank_programs_by_cpu(
                cpu_deltas,
                wall_clock_sec=wall_clock_sec,
                core_count=core_count,
            )

            # Compute per-WP-type server CPU % when we have both wall_clock and core_count
            if wall_clock_sec and core_count:
                wp_type_server_cpu = dr.compute_wp_type_server_cpu(
                    cpu_deltas, wall_clock_sec, core_count,
                )

            # Detect CPU anomalies per WP type
            dominance_thresh = dr.CPU_ATTRIBUTION_THRESHOLDS["CPU_DOMINANCE_PCT"]
            wp_count_thresh = dr.CPU_ATTRIBUTION_THRESHOLDS["SAME_PROGRAM_WP_COUNT"]

            for typ, ranked_list in cpu_ranking.items():
                if not ranked_list:
                    continue
                top = ranked_list[0]

                # Build meaning string — include server CPU % when available
                server_pct_str = ""
                if top.get("server_cpu_pct") is not None:
                    server_pct_str = f" ≈ {top['server_cpu_pct']}% of server CPU capacity."

                # Compute aggregate efficiency for this program across its WPs
                prog_deltas = [d for d in cpu_deltas
                               if d["Typ_s"] == typ and d["Program_s"] == top["Program_s"]]
                prog_efficiencies = [d["cpu_efficiency"] for d in prog_deltas
                                     if d.get("cpu_efficiency") is not None]
                avg_efficiency = (
                    round(sum(prog_efficiencies) / len(prog_efficiencies), 2)
                    if prog_efficiencies else None
                )
                efficiency_label = ""
                if avg_efficiency is not None:
                    if avg_efficiency >= dr.CPU_ATTRIBUTION_THRESHOLDS["CPU_BOUND_EFFICIENCY"]:
                        efficiency_label = " [CPU-bound]"
                    elif avg_efficiency <= dr.CPU_ATTRIBUTION_THRESHOLDS["IO_BOUND_EFFICIENCY"]:
                        efficiency_label = " [I/O or wait-bound — holding WPs but not burning CPU]"
                    else:
                        efficiency_label = f" [mixed — {int(avg_efficiency*100)}% CPU efficiency]"

                # CPU hog: one program dominates this WP type's CPU
                if (top["cpu_pct"] >= dominance_thresh
                        and top["wp_count"] >= wp_count_thresh
                        and top["reliable"]):
                    findings.append({
                        "finding": f"{typ}_CPU_HOG",
                        "severity": "critical",
                        "program": top["Program_s"],
                        "wp_type": typ,
                        "total_cpu_sec": top["total_cpu_sec"],
                        "cpu_pct": top["cpu_pct"],
                        "server_cpu_pct": top.get("server_cpu_pct"),
                        "cpu_efficiency": avg_efficiency,
                        "wp_count": top["wp_count"],
                        "reliable": top["reliable"],
                        "meaning": (
                            f"Program '{top['Program_s']}' consumed {top['cpu_pct']}% of "
                            f"all {typ} CPU across {top['wp_count']} work processes."
                            + efficiency_label + server_pct_str
                        ),
                        "investigation_hints": [
                            f"Cross-reference with BatchJobs_CL: filter on PROGNAME_s contains '{top['Program_s']}' "
                            "(use 'contains' not 'has' for names with underscores).",
                            "Check who scheduled these jobs: look at AUTHCKNAM_s / User_s.",
                            "Check if this program normally runs on this many WPs simultaneously.",
                        ],
                    })
                # Same program on multiple WPs but below dominance threshold
                elif (top["wp_count"] >= wp_count_thresh and top["reliable"]):
                    warnings.append({
                        "finding": f"{typ}_MULTI_WP_PROGRAM",
                        "severity": "warning",
                        "program": top["Program_s"],
                        "wp_type": typ,
                        "total_cpu_sec": top["total_cpu_sec"],
                        "cpu_pct": top["cpu_pct"],
                        "server_cpu_pct": top.get("server_cpu_pct"),
                        "cpu_efficiency": avg_efficiency,
                        "wp_count": top["wp_count"],
                        "reliable": top["reliable"],
                        "meaning": (
                            f"Program '{top['Program_s']}' running on {top['wp_count']} "
                            f"{typ} WPs ({top['cpu_pct']}% of {typ} CPU)."
                            + efficiency_label + server_pct_str
                        ),
                        "investigation_hints": [
                            f"Monitor if CPU share increases — currently at {top['cpu_pct']}%.",
                            f"Check BatchJobs_CL for job details: PROGNAME_s contains '{top['Program_s']}'.",
                        ],
                    })

            # Add finding when per-WP-type server CPU shows a type dominating the server
            if wp_type_server_cpu:
                for typ, info in wp_type_server_cpu.items():
                    if typ.startswith("_"):
                        continue
                    if info["server_cpu_pct"] >= 70:
                        findings.append({
                            "finding": f"{typ}_WP_TYPE_SERVER_CPU_HOG",
                            "severity": "critical",
                            "wp_type": typ,
                            "total_cpu_sec": info["total_cpu_sec"],
                            "server_cpu_pct": info["server_cpu_pct"],
                            "wp_count": info["wp_count"],
                            "meaning": (
                                f"{typ} work processes consumed {info['server_cpu_pct']}% of "
                                f"server CPU capacity ({info['total_cpu_sec']}s CPU across "
                                f"{info['wp_count']} WPs)."
                            ),
                            "investigation_hints": [
                                f"Check which programs are running on {typ} WPs — see cpu_attribution above.",
                                f"If {typ} is BTC: check BatchJobs_CL for the jobs consuming these WPs.",
                                f"If {typ} is DIA: check for long-running dialog transactions or RFC calls.",
                            ],
                        })

            # ── Step 5b: Long-running request and CPU efficiency detection ───
            long_run_thresh = dr.CPU_ATTRIBUTION_THRESHOLDS["LONG_RUNNING_REQUEST_SEC"]
            for d in cpu_deltas:
                rt = d.get("max_request_runtime_sec")
                if rt is not None and rt >= long_run_thresh:
                    eff = d.get("cpu_efficiency")
                    bound_label = "unknown"
                    if eff is not None:
                        if eff >= dr.CPU_ATTRIBUTION_THRESHOLDS["CPU_BOUND_EFFICIENCY"]:
                            bound_label = "CPU-bound"
                        elif eff <= dr.CPU_ATTRIBUTION_THRESHOLDS["IO_BOUND_EFFICIENCY"]:
                            bound_label = "I/O or wait-bound"
                        else:
                            bound_label = f"mixed ({int(eff * 100)}% CPU efficiency)"
                    warnings.append({
                        "finding": "LONG_RUNNING_REQUEST",
                        "severity": "warning",
                        "wp_number": d["No_d"],
                        "hostname": d["hostname_s"],
                        "wp_type": d["Typ_s"],
                        "program": d["Program_s"],
                        "request_runtime_sec": rt,
                        "cpu_delta_sec": d["cpu_delta_sec"],
                        "cpu_efficiency": eff,
                        "cpu_bound_label": bound_label,
                        "meaning": (
                            f"WP #{d['No_d']} ({d['Typ_s']}) on {d['hostname_s']} has been "
                            f"running '{d['Program_s']}' for {rt}s — {bound_label}."
                        ),
                        "investigation_hints": [
                            f"Request elapsed {rt}s — check if this is expected for this program.",
                            f"CPU efficiency: {eff if eff is not None else 'N/A'} "
                            f"— {'actively burning CPU' if bound_label == 'CPU-bound' else 'mostly waiting (DB/RFC/lock)'}.",
                            "If I/O-bound: check Action_s for the wait type (Sequential Read, RFC call, Commit, etc.).",
                        ],
                    })
        else:
            # Insufficient snapshots — hint the agent to re-query with a time range
            warnings.append({
                "finding": "INSUFFICIENT_SNAPSHOTS_FOR_CPU_ATTRIBUTION",
                "severity": "info",
                "max_snapshots_seen": max_snapshots,
                "min_needed": min_snapshots_needed,
                "meaning": (
                    f"Only {max_snapshots} snapshot(s) per WP — need ≥{min_snapshots_needed} "
                    f"to compute CPU deltas. Re-query with a time range covering the spike."
                ),
                "suggested_query": (
                    "SapNetweaver_ABAPGetWPTable_CL "
                    "| where SID_s == '<SID>' "
                    "| where TimeGenerated between (datetime(<spike_start>) .. datetime(<spike_end>)) "
                    "| where Status_s == 'Run' "
                    "| project TimeGenerated, No_d, hostname_s, Typ_s, Status_s, "
                    "Program_s, User_s, Cpu_s, Reason_s"
                ),
                "note": (
                    "Replace <SID>, <spike_start>, <spike_end> with actual values. "
                    "Include at least 10 minutes of data for meaningful CPU deltas."
                ),
            })

    # Hint if core count was not available for server CPU % calculation
    if cpu_attribution_available and not core_count:
        warnings.append({
            "finding": "CORE_COUNT_UNAVAILABLE",
            "severity": "info",
            "meaning": (
                "Server CPU % per program/WP-type could not be computed — "
                "core count not found in context. Query SMON_CL first for AVAILCPUS_d, "
                "or fall back to Prometheus_OSExporter_CL."
            ),
            "suggested_query_smon": (
                "SapNetweaver_SMON_CL "
                "| where SID_s == '<SID>' "
                "| where serverTimestamp_t > ago(1h) "
                "| summarize AVAILCPUS=max(AVAILCPUS_d) by hostname_s "
                "| project hostname_s, AVAILCPUS"
            ),
            "suggested_query_prometheus": (
                "Prometheus_OSExporter_CL "
                "| where name_s == 'node_cpu_seconds_total' "
                "| where labels_s has 'idle' "
                "| where TimeGenerated > ago(1h) "
                "| summarize core_count = dcount(tostring(extract('\"cpu\":\"([0-9]+)\"', 1, labels_s))) "
                "  by hostname_s"
            ),
            "note": "SMON_CL.AVAILCPUS_d is preferred — it is directly associated with the SAP SID and hostname.",
        })

    # ── Step 5c: Cross-validation with SMON CPU metrics (informational only) ─
    # If agent passed SMON CPU_CONS_d in context, compare with WP-derived server CPU.
    # This does NOT change any core logic — purely adds a validation data point.
    if wp_type_server_cpu and smon_cpu_metrics:
        all_wp_info = wp_type_server_cpu.get("_all_wp", {})
        wp_derived_pct = all_wp_info.get("server_cpu_pct")
        smon_cpu_cons = smon_cpu_metrics.get("CPU_CONS_d")
        if wp_derived_pct is not None and smon_cpu_cons is not None:
            delta_pct = abs(wp_derived_pct - smon_cpu_cons)
            if delta_pct <= 15:
                validation_msg = (
                    f"Cross-check: SMON CPU_CONS_d={smon_cpu_cons}% aligns with "
                    f"WP-derived server CPU={wp_derived_pct}% (delta {delta_pct:.1f}pp)."
                )
            else:
                validation_msg = (
                    f"Cross-check: SMON CPU_CONS_d={smon_cpu_cons}% vs "
                    f"WP-derived server CPU={wp_derived_pct}% (delta {delta_pct:.1f}pp). "
                    f"Large gap may indicate non-SAP processes consuming CPU."
                )
            warnings.append({
                "finding": "CPU_CROSS_VALIDATION",
                "severity": "info",
                "smon_cpu_cons_pct": smon_cpu_cons,
                "wp_derived_server_cpu_pct": wp_derived_pct,
                "delta_pp": round(delta_pct, 1),
                "meaning": validation_msg,
            })

    # ── Step 6: Determine overall severity ───────────────────────────────────
    if findings:
        overall_severity = "critical"
    elif warnings:
        overall_severity = "warning"
    else:
        overall_severity = "healthy"

    # ── Build summary text ───────────────────────────────────────────────────
    total_busy = sum(1 for r in rows
                     if dr.classify_wp_status(str(r.get("Status_s", "")).strip())["is_busy"])
    summary_parts = [
        f"{total} work process(es) across {len(hosts)} host(s).",
        f"{total_busy} busy, {total - total_busy} idle.",
    ]
    if findings:
        summary_parts.append(f"{len(findings)} critical finding(s).")
    if warnings:
        summary_parts.append(f"{len(warnings)} warning(s).")
    if cpu_attribution_available:
        summary_parts.append("CPU attribution computed per WP type.")
    if wp_type_server_cpu:
        all_wp = wp_type_server_cpu.get("_all_wp", {})
        if all_wp:
            summary_parts.append(
                f"All WPs consumed {all_wp['server_cpu_pct']}% of server CPU."
            )

    return {
        "status": "success",
        "analysis_type": "workprocess_status",
        "severity": overall_severity,
        "summary": " ".join(summary_parts),
        "wp_type_distribution": type_distribution,
        "status_distribution": status_distribution,
        "critical_findings": findings,
        "warnings": warnings,
        "per_host_summary": per_host_summary,
        "top_programs": [{"program": p, "count": c} for p, c in top_programs.most_common(10)],
        "top_users":    [{"user": u, "count": c} for u, c in top_users.most_common(10)],
        "cpu_attribution": cpu_ranking if cpu_attribution_available else None,
        "wp_type_server_cpu": wp_type_server_cpu if wp_type_server_cpu else None,
        "core_count_source": core_count_source if core_count else None,
        "raw_row_count": total,
        "context": context,
    }

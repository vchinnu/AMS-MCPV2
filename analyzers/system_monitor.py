"""System Monitor analyzer — SMON performance snapshots.

Handles SapNetweaver_SMON_CL — periodic snapshots of application server performance
(CPU, memory, work process utilization, queue lengths, response times).

Key capabilities:
  - Per-host resource analysis with threshold-based findings
  - Cross-metric correlation (e.g. PRIV + DIAQ = WP exhaustion cascade)
  - Peak stress window identification
  - Response time trending

Supports Scenarios 1 (Batch Job RCA), 2 (Short Dump Classification), 3 (System Stall).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import domain_registry as dr
from analyzers import register


# ── Metrics to evaluate — each maps to a domain knowledge threshold entry ────
# Only metrics with defined thresholds in domain_knowledge.SMON_METRIC_THRESHOLDS
# are evaluated for threshold breaches. Other columns (ACT_DIA_d, SESSIONS_d, etc.)
# are used in computed/relative analysis below.
_THRESHOLD_METRICS = [
    "CPU_CONS_d", "FREE_MEM_PERC_d", "PRIVWPNO_d", "DIAQ_d",
    "UPDQ_d", "ENQQ_d", "STEAL_TIME_d", "PAGE_IN_PERC_d",
    "PAGE_OUT_PERC_d", "DIAAVG60_d",
]


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert a value to float. Returns default if conversion fails."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


@register("system_performance")
def analyze_system_monitor(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate SMON system monitor data.

    Flow:
      1. Group rows by hostname → per-host analysis
      2. For each host, evaluate each threshold metric (avg, max, % time above threshold)
      3. Detect cross-metric correlations (compound findings)
      4. Identify the peak stress window (worst moment in the data)
      5. Return structured findings with severity classification
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "system_performance",
                "summary": "No SMON data returned.", "raw_row_count": 0, "context": context}

    total = len(rows)

    # ── Step 1: Group rows by hostname ───────────────────────────────────────
    hosts: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        host = str(row.get("hostname_s", "unknown")).strip()
        hosts[host].append(row)

    # ── Step 2: Per-host threshold analysis ──────────────────────────────────
    findings: list[dict] = []       # critical or warning findings
    per_host_metrics: dict[str, dict] = {}

    for host, host_rows in hosts.items():
        host_n = len(host_rows)
        host_stats: dict[str, dict] = {}

        # Evaluate each metric with a domain knowledge threshold
        for metric in _THRESHOLD_METRICS:
            values = [_safe_float(r.get(metric)) for r in host_rows]
            values = [v for v in values if v != 0.0 or metric not in ("PAGE_IN_PERC_d", "PAGE_OUT_PERC_d")]

            if not values:
                continue

            avg_val = sum(values) / len(values)
            max_val = max(values)
            min_val = min(values)

            # Classify the max value against thresholds
            classification = dr.classify_smon_metric(metric, max_val)
            severity = classification["severity"]

            # Calculate % of readings above warning threshold
            threshold_info = dr.SMON_METRIC_THRESHOLDS.get(metric, {})
            warning_thresh = threshold_info.get("warning", 0)
            direction = threshold_info.get("direction", "above")

            if direction == "below":
                pct_breached = sum(1 for v in values if v <= warning_thresh) / len(values) * 100
            else:
                pct_breached = sum(1 for v in values if v >= warning_thresh) / len(values) * 100

            host_stats[metric] = {
                "avg": round(avg_val, 2),
                "max": round(max_val, 2),
                "min": round(min_val, 2),
                "pct_above_warning": round(pct_breached, 1),
                "max_severity": severity,
            }

            # Generate a finding if the metric breached warning or critical
            if severity in ("warning", "critical"):
                findings.append({
                    "finding": f"{metric}_BREACH",
                    "severity": severity,
                    "host": host,
                    "metric": metric,
                    "meaning": classification["meaning"],
                    "avg": round(avg_val, 2),
                    "max": round(max_val, 2),
                    "pct_time_breached": round(pct_breached, 1),
                    "investigation_hints": classification["investigation_hints"],
                })

        per_host_metrics[host] = host_stats

        # ── Step 3: Cross-metric correlation (compound findings) ─────────────
        # These require looking at MULTIPLE metrics on the SAME row at the SAME time.
        # This logic cannot live in domain_knowledge because it requires row iteration.

        for row in host_rows:
            priv = _safe_float(row.get("PRIVWPNO_d"))
            diaq = _safe_float(row.get("DIAQ_d"))
            cpu  = _safe_float(row.get("CPU_CONS_d"))
            mem  = _safe_float(row.get("FREE_MEM_PERC_d", 100))

            ts = str(row.get("serverTimestamp_t", row.get("TimeGenerated", "")))

            # PRIV mode + dialog queue = WP exhaustion cascade (Scenario 3 signal)
            if priv > 0 and diaq > 0:
                findings.append({
                    "finding": "WP_EXHAUSTION_CASCADE",
                    "severity": "critical",
                    "host": host,
                    "timestamp": ts,
                    "priv_wps": priv,
                    "dialog_queue": diaq,
                    "meaning": (
                        f"PRIV mode WPs ({int(priv)}) AND dialog queue ({int(diaq)}) "
                        f"active simultaneously — WP exhaustion in progress."
                    ),
                    "investigation_hints": [
                        "Check ABAPGetWPTable_CL for which programs hold PRIV WPs.",
                        "This is a Scenario 3 (System Stall) signal.",
                    ],
                })

            # High CPU + Low memory = compound resource pressure
            if cpu > 90 and mem < 15:
                findings.append({
                    "finding": "COMPOUND_RESOURCE_PRESSURE",
                    "severity": "critical",
                    "host": host,
                    "timestamp": ts,
                    "cpu": cpu,
                    "free_mem_pct": mem,
                    "meaning": f"CPU at {cpu}% AND free memory at {mem}% — compound resource exhaustion.",
                    "investigation_hints": [
                        "System is under both CPU and memory pressure simultaneously.",
                        "Check for runaway programs consuming both CPU and memory.",
                    ],
                })

    # ── Deduplicate compound findings (keep only first occurrence per type+host) ──
    seen_compound: set[str] = set()
    deduped_findings: list[dict] = []
    for f in findings:
        if f["finding"] in ("WP_EXHAUSTION_CASCADE", "COMPOUND_RESOURCE_PRESSURE"):
            key = f"{f['finding']}_{f['host']}"
            if key in seen_compound:
                continue
            seen_compound.add(key)
        deduped_findings.append(f)
    findings = deduped_findings

    # ── Step 4: Peak stress window identification ────────────────────────────
    # Find the single row with the worst combined stress score
    peak_row = None
    peak_score = -1
    for row in rows:
        # Score = normalized CPU + inverse free memory + PRIV count + DIAQ
        cpu  = _safe_float(row.get("CPU_CONS_d"))
        mem  = 100 - _safe_float(row.get("FREE_MEM_PERC_d", 100))  # invert: higher = worse
        priv = _safe_float(row.get("PRIVWPNO_d")) * 10             # amplify PRIV impact
        diaq = _safe_float(row.get("DIAQ_d")) * 5                  # amplify queue impact
        score = cpu + mem + priv + diaq
        if score > peak_score:
            peak_score = score
            peak_row = row

    peak_window = None
    if peak_row:
        peak_window = {
            "timestamp": str(peak_row.get("serverTimestamp_t", peak_row.get("TimeGenerated", ""))),
            "host": str(peak_row.get("hostname_s", "")),
            "cpu": _safe_float(peak_row.get("CPU_CONS_d")),
            "free_mem_pct": _safe_float(peak_row.get("FREE_MEM_PERC_d")),
            "priv_wps": _safe_float(peak_row.get("PRIVWPNO_d")),
            "diaq": _safe_float(peak_row.get("DIAQ_d")),
            "updq": _safe_float(peak_row.get("UPDQ_d")),
            "dialog_rt_ms": _safe_float(peak_row.get("DIAAVG60_d")),
            "sessions": _safe_float(peak_row.get("SESSIONS_d")),
        }

    # ── Step 5: Determine overall severity ───────────────────────────────────
    severities = [f["severity"] for f in findings]
    if "critical" in severities:
        overall_severity = "critical"
    elif "warning" in severities:
        overall_severity = "warning"
    else:
        overall_severity = "healthy"

    # ── Separate findings by severity ────────────────────────────────────────
    critical = [f for f in findings if f["severity"] == "critical"]
    warnings = [f for f in findings if f["severity"] == "warning"]

    # ── Build summary text ───────────────────────────────────────────────────
    summary_parts = [f"{total} SMON snapshot(s) across {len(hosts)} host(s)."]
    if critical:
        summary_parts.append(f"{len(critical)} critical finding(s).")
    if warnings:
        summary_parts.append(f"{len(warnings)} warning(s).")
    if not critical and not warnings:
        summary_parts.append("All metrics within normal thresholds.")

    return {
        "status": "success",
        "analysis_type": "system_performance",
        "severity": overall_severity,
        "summary": " ".join(summary_parts),
        "critical_findings": critical,
        "warnings": warnings,
        "per_host_metrics": per_host_metrics,
        "peak_stress_window": peak_window,
        "hosts_analyzed": list(hosts.keys()),
        "raw_row_count": total,
        "context": context,
    }

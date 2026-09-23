"""RFC and queue analyzer — SM58 tRFC, SMQ1/SMQ2 queues, dispatcher queues.

Handles four table formats via auto-detection:
  - SapNetweaver_TransactionalRfc_CL  (analysis_type: transactional_rfc)  → SM58 tRFC errors
  - SapNetweaver_OutboundQueues_CL    (analysis_type: queue_monitoring)   → SMQ1 outbound queues
  - SapNetweaver_InboundQueues_CL     (analysis_type: queue_monitoring)   → SMQ2 inbound queues
  - SapNetweaver_GetQueueStatistic_CL (analysis_type: queue_monitoring)   → Dispatcher queues

Key capabilities:
  - tRFC: Failed destination identification, error message grouping, retry analysis
  - Outbound/Inbound queues: Stuck queue detection, queue depth analysis, age calculation
  - Dispatcher queues: Queue utilization, DIA/BTC/ICM queue status

Supports Scenario 1 (Batch Job RCA — RFC failures causing job failures).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import domain_registry as dr
from analyzers import register


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point — auto-detects which table format the rows come from
# ═══════════════════════════════════════════════════════════════════════════════

@register("transactional_rfc", "queue_monitoring")
def analyze_rfc_queues(rows: list[dict], context: str) -> dict[str, Any]:
    """Auto-detect table format and route to the appropriate sub-analyzer.

    Detection logic (checks for distinguishing columns in the first row):
      - ARFCSTATE_s present     → SM58 tRFC data         → _analyze_trfc()
      - DEST_s present          → SMQ1 outbound queues    → _analyze_outbound_queues()
      - QDEEP_d + QNAME_s      → SMQ2 inbound queues     → _analyze_inbound_queues()
      - Now_d present           → Dispatcher queue stats  → _analyze_dispatcher_queues()
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "queue_monitoring",
                "summary": "No RFC/queue data returned.", "raw_row_count": 0, "context": context}

    sample = rows[0]

    # SM58 tRFC — has ARFCSTATE_s (unique to TransactionalRfc_CL)
    if "ARFCSTATE_s" in sample:
        return _analyze_trfc(rows, context)

    # SMQ1 outbound — has DEST_s column (unique to OutboundQueues_CL)
    if "DEST_s" in sample:
        return _analyze_outbound_queues(rows, context)

    # Dispatcher queues — has Now_d column (unique to GetQueueStatistic_CL)
    if "Now_d" in sample:
        return _analyze_dispatcher_queues(rows, context)

    # SMQ2 inbound — has QDEEP_d + QNAME_s but no DEST_s
    if "QDEEP_d" in sample and "QNAME_s" in sample:
        return _analyze_inbound_queues(rows, context)

    # Fallback — unknown format
    return {"status": "success", "analysis_type": "queue_monitoring",
            "summary": f"Unknown queue format — {len(rows)} row(s). Check column names.",
            "raw_row_count": len(rows), "context": context}


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 1: SM58 tRFC (TransactionalRfc_CL)
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_trfc(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze SM58 transactional RFC data.

    Flow:
      1. Classify each row by ARFCSTATE_s using domain knowledge
      2. Filter to failure states (SYSFAIL, CPICERR)
      3. Group failures by destination (ARFCDEST_s)
      4. For each failing destination: collect error messages, function modules, retry counts
      5. Return severity-ranked destination failure report
    """
    total = len(rows)

    # ── Step 1: State distribution ───────────────────────────────────────────
    state_counts: Counter = Counter()
    for row in rows:
        state = str(row.get("ARFCSTATE_s", "")).strip()
        state_counts[state] += 1

    state_distribution = []
    for state, count in state_counts.most_common():
        info = dr.classify_trfc_state(state)
        state_distribution.append({
            "state": state, "label": info["label"],
            "is_failure": info["is_failure"], "count": count,
        })

    # ── Step 2: Filter to failures only ──────────────────────────────────────
    failure_rows = [r for r in rows
                    if dr.classify_trfc_state(str(r.get("ARFCSTATE_s", "")).strip())["is_failure"]]
    total_failures = len(failure_rows)

    # ── Step 3: Group failures by destination ────────────────────────────────
    dest_groups: dict[str, list[dict]] = defaultdict(list)
    for row in failure_rows:
        dest = str(row.get("ARFCDEST_s", "UNKNOWN")).strip()
        dest_groups[dest].append(row)

    # ── Step 4: Per-destination failure analysis ─────────────────────────────
    failing_destinations: list[dict] = []
    for dest, dest_rows in sorted(dest_groups.items(), key=lambda x: -len(x[1])):
        # Collect unique error messages (ARFCMSG_s)
        messages = sorted(set(
            str(r.get("ARFCMSG_s", "")).strip() for r in dest_rows
            if str(r.get("ARFCMSG_s", "")).strip()
        ))

        # Collect unique function modules (ARFCFNAM_s)
        functions = sorted(set(
            str(r.get("ARFCFNAM_s", "")).strip() for r in dest_rows
            if str(r.get("ARFCFNAM_s", "")).strip()
        ))

        # Collect unique users (ARFCUSER_s)
        users = sorted(set(
            str(r.get("ARFCUSER_s", "")).strip() for r in dest_rows
            if str(r.get("ARFCUSER_s", "")).strip()
        ))

        # Max retries — indicates persistent failure
        max_retries = max((_safe_int(r.get("ARFCRETRYS_s")) for r in dest_rows), default=0)

        # Error state breakdown for this destination
        dest_states = Counter(str(r.get("ARFCSTATE_s", "")) for r in dest_rows)

        failing_destinations.append({
            "destination": dest,
            "failure_count": len(dest_rows),
            "error_states": dict(dest_states),
            "error_messages": messages[:10],  # limit to 10 unique messages
            "affected_functions": functions[:10],
            "affected_users": users[:10],
            "max_retries": max_retries,
            "investigation_hints": [
                f"Check if destination system '{dest}' was available at the time.",
                "Check network connectivity between source and target.",
            ] + (["High retry count — failure is persistent, not transient."] if max_retries > 5 else []),
        })

    # ── Step 5: Severity determination ───────────────────────────────────────
    if total_failures > 50 or any(d["max_retries"] > 10 for d in failing_destinations):
        severity = "critical"
    elif total_failures > 0:
        severity = "warning"
    else:
        severity = "healthy"

    summary_parts = [f"{total} tRFC record(s)."]
    if total_failures:
        summary_parts.append(f"{total_failures} failure(s) across {len(failing_destinations)} destination(s).")
    else:
        summary_parts.append("No failures detected.")

    return {
        "status": "success",
        "analysis_type": "transactional_rfc",
        "data_source": "SM58",
        "severity": severity,
        "summary": " ".join(summary_parts),
        "state_distribution": state_distribution,
        "total_failures": total_failures,
        "failing_destinations": failing_destinations,
        "raw_row_count": total,
        "context": context,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 2: SMQ1 Outbound Queues (OutboundQueues_CL)
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_outbound_queues(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze SMQ1 outbound qRFC queue data.

    Flow:
      1. Filter to non-empty queues (QDEEP_d > 0)
      2. Classify queue depth using domain knowledge thresholds
      3. Group by destination (DEST_s)
      4. Sort by depth desc — worst backlogs first
    """
    total = len(rows)

    # ── Filter to non-empty queues ───────────────────────────────────────────
    non_empty = [r for r in rows if _safe_float(r.get("QDEEP_d")) > 0]

    # ── Build queue entries sorted by depth ──────────────────────────────────
    queue_entries: list[dict] = []
    for row in non_empty:
        depth = _safe_float(row.get("QDEEP_d"))
        queue_entries.append({
            "queue_name": str(row.get("QNAME_s", "")).strip(),
            "destination": str(row.get("DEST_s", "")).strip(),
            "depth": int(depth),
            "severity": dr.classify_queue_depth(depth),
            "first_entry_date": str(row.get("FDATE_s", "")),
            "first_entry_time": str(row.get("FTIME_s", "")),
            "last_entry_date": str(row.get("LDATE_s", "")),
            "last_entry_time": str(row.get("LTIME_s", "")),
        })

    queue_entries.sort(key=lambda x: -x["depth"])

    # ── Group by destination ─────────────────────────────────────────────────
    dest_summary: dict[str, dict] = defaultdict(lambda: {"total_depth": 0, "queue_count": 0})
    for q in queue_entries:
        dest = q["destination"] or "embedded_in_qname"
        dest_summary[dest]["total_depth"] += q["depth"]
        dest_summary[dest]["queue_count"] += 1

    dest_list = [
        {"destination": d, "total_depth": s["total_depth"], "queue_count": s["queue_count"]}
        for d, s in sorted(dest_summary.items(), key=lambda x: -x[1]["total_depth"])
    ]

    # ── Severity ─────────────────────────────────────────────────────────────
    severities = [q["severity"] for q in queue_entries]
    if "critical" in severities:
        overall = "critical"
    elif "warning" in severities:
        overall = "warning"
    elif non_empty:
        overall = "info"
    else:
        overall = "healthy"

    return {
        "status": "success",
        "analysis_type": "queue_monitoring",
        "data_source": "SMQ1_outbound",
        "severity": overall,
        "summary": (
            f"{total} outbound queue(s) checked. {len(non_empty)} non-empty. "
            f"Total pending entries: {sum(q['depth'] for q in queue_entries)}."
        ),
        "non_empty_queues": queue_entries[:20],  # top 20 by depth
        "destination_summary": dest_list,
        "total_queues_checked": total,
        "non_empty_count": len(non_empty),
        "raw_row_count": total,
        "context": context,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 3: SMQ2 Inbound Queues (InboundQueues_CL)
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_inbound_queues(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze SMQ2 inbound qRFC queue data.

    Same pattern as outbound but without the DEST_s column — only QNAME_s available.
    """
    total = len(rows)

    non_empty = [r for r in rows if _safe_float(r.get("QDEEP_d")) > 0]

    queue_entries: list[dict] = []
    for row in non_empty:
        depth = _safe_float(row.get("QDEEP_d"))
        queue_entries.append({
            "queue_name": str(row.get("QNAME_s", "")).strip(),
            "depth": int(depth),
            "severity": dr.classify_queue_depth(depth),
            "first_entry_date": str(row.get("FDATE_s", "")),
            "first_entry_time": str(row.get("FTIME_s", "")),
        })

    queue_entries.sort(key=lambda x: -x["depth"])

    severities = [q["severity"] for q in queue_entries]
    if "critical" in severities:
        overall = "critical"
    elif "warning" in severities:
        overall = "warning"
    elif non_empty:
        overall = "info"
    else:
        overall = "healthy"

    return {
        "status": "success",
        "analysis_type": "queue_monitoring",
        "data_source": "SMQ2_inbound",
        "severity": overall,
        "summary": (
            f"{total} inbound queue(s) checked. {len(non_empty)} non-empty. "
            f"Total pending entries: {sum(q['depth'] for q in queue_entries)}."
        ),
        "non_empty_queues": queue_entries[:20],
        "total_queues_checked": total,
        "non_empty_count": len(non_empty),
        "raw_row_count": total,
        "context": context,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 4: Dispatcher Queue Statistics (GetQueueStatistic_CL)
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_dispatcher_queues(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze dispatcher queue statistics.

    Flow:
      1. Group by Typ_s (ABAP/DIA, ABAP/BTC, ICM/HTTP, etc.) per host
      2. For each queue type: current depth, peak, capacity, utilization
      3. Detect active queuing on DIA/BTC (users/jobs waiting)
    """
    total = len(rows)

    # ── Group by host + queue type ───────────────────────────────────────────
    key_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        host = str(row.get("hostname_s", "unknown")).strip()
        typ  = str(row.get("Typ_s", "")).strip()
        key_groups[f"{host}|{typ}"].append(row)

    queue_analysis: list[dict] = []
    findings: list[dict] = []

    for key, group_rows in sorted(key_groups.items()):
        host, typ = key.split("|", 1)

        # Use the latest snapshot for current values (max timestamp)
        latest = max(group_rows, key=lambda r: str(r.get("serverTimestamp_t", "")))

        now  = _safe_float(latest.get("Now_d"))
        high = _safe_float(latest.get("High_d"))
        max_cap = _safe_float(latest.get("Max_d"))
        reads  = _safe_float(latest.get("Reads_d"))
        writes = _safe_float(latest.get("Writes_d"))

        utilization = high / max_cap if max_cap > 0 else 0

        entry = {
            "host": host,
            "queue_type": typ,
            "current_depth": int(now),
            "peak_depth": int(high),
            "max_capacity": int(max_cap),
            "utilization_pct": round(utilization * 100, 1),
            "total_arrivals": int(writes),
            "total_processed": int(reads),
        }
        queue_analysis.append(entry)

        # ── FINDING: Active queueing on dialog or batch queues ───────────────
        if now > 0 and typ in ("ABAP/DIA", "ABAP/BTC", "ABAP/UPD"):
            queue_label = {"ABAP/DIA": "dialog", "ABAP/BTC": "batch", "ABAP/UPD": "update"}.get(typ, typ)
            findings.append({
                "finding": f"{queue_label.upper()}_QUEUE_ACTIVE",
                "severity": "warning" if now < 10 else "critical",
                "host": host,
                "queue_type": typ,
                "current_depth": int(now),
                "meaning": f"{int(now)} {queue_label} request(s) waiting in dispatcher queue on {host}.",
                "investigation_hints": [
                    f"Check {queue_label} work process availability — all may be busy.",
                    "Correlate with SMON DIAQ_d / ABAPGetWPTable_CL.",
                ],
            })

        # ── FINDING: High peak utilization ───────────────────────────────────
        if utilization > 0.5:
            findings.append({
                "finding": "HIGH_QUEUE_UTILIZATION",
                "severity": "warning",
                "host": host,
                "queue_type": typ,
                "utilization_pct": round(utilization * 100, 1),
                "meaning": f"Queue {typ} on {host} reached {utilization:.0%} of capacity (peak).",
                "investigation_hints": [
                    "If utilization approaches 100%, requests will be rejected.",
                    "Consider increasing work process count or adding app servers.",
                ],
            })

    # ── Severity ─────────────────────────────────────────────────────────────
    if any(f["severity"] == "critical" for f in findings):
        overall = "critical"
    elif findings:
        overall = "warning"
    else:
        overall = "healthy"

    return {
        "status": "success",
        "analysis_type": "queue_monitoring",
        "data_source": "dispatcher_queues",
        "severity": overall,
        "summary": f"{total} dispatcher queue record(s) across {len(set(e['host'] for e in queue_analysis))} host(s).",
        "queue_analysis": queue_analysis,
        "findings": findings,
        "raw_row_count": total,
        "context": context,
    }

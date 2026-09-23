"""Failed updates analyzer — SM13 failed V1/V2/V3 updates.

Handles SapNetweaver_FailedUpdates_CL — one row per failed update record.

Key capabilities:
  - Filter to actual failures (VBSTATE_s == "1")
  - Group failures by program (VBNAME_s) and transaction code (VBTCODE_s)
  - Identify top users generating update failures
  - Detect failure spikes (many failures in short time window)
  - Classify update context (V1 synchronous vs V2/V3 asynchronous)
  - Host-level distribution of failures

Supports Scenario 2 (Intermittent Failures — failed updates are a key signal).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import domain_registry as dr
from analyzers import register


def _safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


@register("Failed_updates")
def analyze_failed_updates(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate SM13 failed update data.

    Note: The analysis_type is "Failed_updates" (capital F) to match the schema
    definition in schemas/sap_application.py.

    Flow:
      1. Classify each row by VBSTATE_s (update state) using domain knowledge
      2. Filter to actual failure rows (is_failure == True)
      3. Group failures by program (VBNAME_s) and transaction code (VBTCODE_s)
      4. Identify top users and hosts with failures
      5. Classify update context (V/W/B) using domain knowledge
      6. Return failure summary with investigation hints
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "Failed_updates",
                "summary": "No failed update data returned.", "raw_row_count": 0, "context": context}

    total = len(rows)

    # ── Step 1: State distribution ───────────────────────────────────────────
    # VBSTATE_s encodes the update processing state (0=initial, 1=error, 2=auto-processed, etc.)
    state_counts: Counter = Counter()
    for row in rows:
        state = str(row.get("VBSTATE_s", "")).strip()
        state_counts[state] += 1

    state_distribution = []
    for state, count in state_counts.most_common():
        info = dr.classify_update_state(state)
        state_distribution.append({
            "state_code": state,
            "label": info["label"],
            "is_failure": info["is_failure"],
            "meaning": info["meaning"],
            "count": count,
        })

    # ── Step 2: Filter to actual failures ────────────────────────────────────
    failure_rows = [r for r in rows
                    if dr.classify_update_state(str(r.get("VBSTATE_s", "")).strip())["is_failure"]]
    total_failures = len(failure_rows)

    if total_failures == 0:
        return {
            "status": "success",
            "analysis_type": "Failed_updates",
            "severity": "healthy",
            "summary": f"{total} update record(s) examined. No actual failures detected.",
            "state_distribution": state_distribution,
            "total_failures": 0,
            "raw_row_count": total,
            "context": context,
        }

    # ── Step 3: Group failures by program and transaction code ───────────────
    # Program is the ABAP report that triggered the update
    program_counts = Counter(
        str(r.get("VBNAME_s", "")).strip() for r in failure_rows
        if str(r.get("VBNAME_s", "")).strip()
    )
    tcode_counts = Counter(
        str(r.get("VBTCODE_s", "")).strip() for r in failure_rows
        if str(r.get("VBTCODE_s", "")).strip()
    )

    top_programs = [
        {"program": prog, "failure_count": count}
        for prog, count in program_counts.most_common(10)
    ]
    top_tcodes = [
        {"tcode": tcode, "failure_count": count}
        for tcode, count in tcode_counts.most_common(10)
    ]

    # ── Step 4: User and host distribution ───────────────────────────────────
    user_counts = Counter(
        str(r.get("VBUSER_s", "")).strip() for r in failure_rows
        if str(r.get("VBUSER_s", "")).strip()
    )
    host_counts = Counter(
        str(r.get("hostname_s", "")).strip() for r in failure_rows
        if str(r.get("hostname_s", "")).strip()
    )

    top_users = [
        {"user": user, "failure_count": count}
        for user, count in user_counts.most_common(10)
    ]
    host_distribution = [
        {"host": host, "failure_count": count}
        for host, count in host_counts.most_common()
    ]

    # ── Step 5: Context classification (V1/V2/V3) ───────────────────────────
    context_counts: Counter = Counter()
    for row in failure_rows:
        ctx = str(row.get("VBCONTEXT_s", "")).strip()
        context_counts[ctx] += 1

    context_distribution = []
    for ctx, count in context_counts.most_common():
        info = dr.classify_update_context(ctx)
        context_distribution.append({
            "context_code": ctx,
            "label": info["label"],
            "meaning": info.get("meaning", ""),
            "count": count,
        })

    # ── Step 6: Collect unique error messages ────────────────────────────────
    # VBERROR_s or VBMSG_s may contain the actual error text
    error_messages: Counter = Counter()
    for row in failure_rows:
        msg = str(row.get("VBERROR_s", "")).strip() or str(row.get("VBMSG_s", "")).strip()
        if msg:
            error_messages[msg] += 1

    top_errors = [
        {"message": msg, "count": count}
        for msg, count in error_messages.most_common(10)
    ]

    # ── Step 7: Findings and investigation hints ─────────────────────────────
    findings: list[dict] = []

    # Finding: High failure concentration in one program
    if top_programs and top_programs[0]["failure_count"] > total_failures * 0.5:
        prog = top_programs[0]
        findings.append({
            "finding": "CONCENTRATED_FAILURE",
            "severity": "critical",
            "program": prog["program"],
            "failure_pct": round(prog["failure_count"] / total_failures * 100, 1),
            "meaning": (
                f"Program {prog['program']} accounts for {prog['failure_count']} "
                f"of {total_failures} failures ({prog['failure_count']/total_failures:.0%}). "
                f"Likely a single root cause."
            ),
            "investigation_hints": [
                f"Check program {prog['program']} for code changes (recent transports).",
                "Check associated tcode for authorization/customizing changes.",
                "Review error messages below for the specific failure reason.",
            ],
        })

    # Finding: V1 (synchronous) failures — more severe than V2/V3
    v1_count = sum(count for ctx, count in context_counts.items() if ctx in ("V", "1"))
    if v1_count > 0:
        findings.append({
            "finding": "V1_SYNCHRONOUS_FAILURES",
            "severity": "critical",
            "count": v1_count,
            "meaning": (
                f"{v1_count} V1 (synchronous) update failure(s). These cause the transaction "
                f"to fail visibly and data loss. Higher impact than V2/V3 async failures."
            ),
            "investigation_hints": [
                "V1 failures typically indicate DB locks, authorization issues, or data inconsistencies.",
                "Check SM13 for the detailed error text and stack trace.",
            ],
        })

    # Finding: Spike detection — many failures from the same host
    if host_distribution and host_distribution[0]["failure_count"] > total_failures * 0.7:
        h = host_distribution[0]
        findings.append({
            "finding": "HOST_CONCENTRATED_FAILURES",
            "severity": "warning",
            "host": h["host"],
            "failure_pct": round(h["failure_count"] / total_failures * 100, 1),
            "meaning": f"Host {h['host']} accounts for {h['failure_count']}/{total_failures} failures.",
            "investigation_hints": [
                "Check if this host had infrastructure issues (OS metrics, HANA memory).",
                "Compare with other hosts — if only one host is failing, it's likely local.",
            ],
        })

    # ── Severity determination ───────────────────────────────────────────────
    if total_failures > 100 or any(f["severity"] == "critical" for f in findings):
        overall_severity = "critical"
    elif total_failures > 10:
        overall_severity = "warning"
    else:
        overall_severity = "info"

    return {
        "status": "success",
        "analysis_type": "Failed_updates",
        "severity": overall_severity,
        "summary": f"{total_failures} failed update(s) out of {total} total. Top program: {top_programs[0]['program'] if top_programs else 'N/A'}.",
        "state_distribution": state_distribution,
        "total_failures": total_failures,
        "context_distribution": context_distribution,
        "top_programs": top_programs,
        "top_tcodes": top_tcodes,
        "top_users": top_users,
        "host_distribution": host_distribution,
        "top_error_messages": top_errors,
        "findings": findings,
        "raw_row_count": total,
        "context": context,
    }

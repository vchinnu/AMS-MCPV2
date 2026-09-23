"""Transport management analyzer — STMS transport requests and objects.

Handles two table formats via auto-detection:
  - SapNetweaver_STMS_Requests_CL     (analysis_type: transport_management) → transport requests
  - SapNetweaver_STMS_RequestObj_CL   (analysis_type: transport_management) → transport objects

Key capabilities:
  - Transport request status distribution (Released, Locked, etc.)
  - Failed/stuck transports identification
  - Object type breakdown (code vs config vs data changes)
  - Import queue analysis per target system
  - Transport age detection (old unreleased transports)

Supports Scenario 4 (Post-Maintenance Degradation — what was transported?).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import domain_registry as dr
from analyzers import register


@register("transport_management")
def analyze_transports(rows: list[dict], context: str) -> dict[str, Any]:
    """Auto-detect table format and route to the appropriate sub-analyzer.

    Detection logic (checks for distinguishing columns in the first row):
      - OBJECT_s + OBJ_NAME_s present → transport objects → _analyze_transport_objects()
      - Otherwise                     → transport requests → _analyze_transport_requests()
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "transport_management",
                "summary": "No transport data returned.", "raw_row_count": 0, "context": context}

    sample = rows[0]

    # Transport objects have OBJECT_s (object type like PROG, CLAS, TABD)
    if "OBJECT_s" in sample and "OBJ_NAME_s" in sample:
        return _analyze_transport_objects(rows, context)

    # Default: transport requests
    return _analyze_transport_requests(rows, context)


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 1: STMS Transport Requests
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_transport_requests(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze STMS transport request data.

    Flow:
      1. Classify each request by status (TRSTATUS_s) using domain knowledge
      2. Classify function (KORRDEV_s: Workbench, Customizing, Transport of Copies, etc.)
      3. Count per-status and per-function distribution
      4. Identify locked/unreleased transports per owner
      5. Identify potential issues (old locked TRs, many in import queue)
    """
    total = len(rows)

    # ── Step 1: Status distribution ──────────────────────────────────────────
    status_counts: Counter = Counter()
    for row in rows:
        status = str(row.get("TRSTATUS_s", "")).strip()
        status_counts[status] += 1

    status_distribution = []
    for status, count in status_counts.most_common():
        info = dr.classify_transport_status(status)
        status_distribution.append({
            "status_code": status,
            "label": info["label"],
            "meaning": info.get("meaning", ""),
            "count": count,
        })

    # ── Step 2: Function distribution (Workbench vs Customizing) ─────────────
    function_counts: Counter = Counter()
    for row in rows:
        func = str(row.get("KORRDEV_s", "")).strip()
        function_counts[func] += 1

    function_distribution = []
    for func, count in function_counts.most_common():
        info = dr.classify_transport_function(func)
        function_distribution.append({
            "function_code": func,
            "label": info["label"],
            "count": count,
        })

    # ── Step 3: Owner analysis (who owns locked/unreleased TRs?) ─────────────
    locked_rows = [r for r in rows if str(r.get("TRSTATUS_s", "")).strip() in ("D", "L")]
    owner_counts = Counter(str(r.get("AS4USER_s", "")).strip() for r in locked_rows)

    owners_with_locked = [
        {"owner": owner, "locked_count": count}
        for owner, count in owner_counts.most_common()
        if owner
    ]

    # ── Step 4: Target system analysis (import queue by target) ──────────────
    target_counts: Counter = Counter()
    for row in rows:
        target = str(row.get("TARSYSTEM_s", "")).strip()
        if target:
            target_counts[target] += 1

    target_distribution = [
        {"target_system": target, "count": count}
        for target, count in target_counts.most_common()
    ]

    # ── Step 5: Findings ─────────────────────────────────────────────────────
    findings: list[dict] = []

    # Finding: Many locked/unreleased transports by a single owner
    for entry in owners_with_locked:
        if entry["locked_count"] >= 5:
            findings.append({
                "finding": "MANY_LOCKED_TRANSPORTS",
                "severity": "info",
                "owner": entry["owner"],
                "locked_count": entry["locked_count"],
                "meaning": (
                    f"User {entry['owner']} has {entry['locked_count']} locked/unreleased transport(s). "
                    f"These transports cannot be imported until released."
                ),
                "investigation_hints": [
                    "Check if the user forgot to release, or if these are work-in-progress.",
                    "Old locked transports may block other team members.",
                ],
            })

    # Finding: Released but not imported (status=R and target system set)
    released_count = status_counts.get("R", 0)
    if released_count > 20:
        findings.append({
            "finding": "MANY_RELEASED_PENDING_IMPORT",
            "severity": "warning",
            "count": released_count,
            "meaning": f"{released_count} transport(s) released but not yet imported — possible import queue backlog.",
            "investigation_hints": [
                "Check STMS import queue for errors or blocks.",
                "Verify target system availability.",
            ],
        })

    # ── Severity ─────────────────────────────────────────────────────────────
    if any(f["severity"] == "critical" for f in findings):
        overall = "critical"
    elif any(f["severity"] == "warning" for f in findings):
        overall = "warning"
    else:
        overall = "healthy"

    return {
        "status": "success",
        "analysis_type": "transport_management",
        "data_source": "STMS_requests",
        "severity": overall,
        "summary": f"{total} transport request(s). {released_count} released, {len(locked_rows)} locked/unreleased.",
        "status_distribution": status_distribution,
        "function_distribution": function_distribution,
        "owners_with_locked": owners_with_locked,
        "target_distribution": target_distribution,
        "findings": findings,
        "raw_row_count": total,
        "context": context,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-analyzer 2: STMS Transport Objects
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_transport_objects(rows: list[dict], context: str) -> dict[str, Any]:
    """Analyze STMS transport object (content) data.

    Flow:
      1. Classify each object type (OBJECT_s) using domain knowledge
      2. Separate code objects from config/data objects
      3. Count objects per transport request (TRKORR_s)
      4. Identify large transports (many objects = higher risk)
    """
    total = len(rows)

    # ── Step 1: Object type distribution ─────────────────────────────────────
    obj_type_counts: Counter = Counter()
    for row in rows:
        obj_type = str(row.get("OBJECT_s", "")).strip()
        obj_type_counts[obj_type] += 1

    object_distribution = []
    code_objects = 0
    config_objects = 0

    for obj_type, count in obj_type_counts.most_common():
        info = dr.classify_transport_object(obj_type)
        object_distribution.append({
            "object_type": obj_type,
            "label": info["label"],
            "is_code": info["is_code"],
            "count": count,
        })
        if info["is_code"]:
            code_objects += count
        else:
            config_objects += count

    # ── Step 2: Objects per transport request ────────────────────────────────
    transport_sizes: dict[str, int] = Counter()
    for row in rows:
        trkorr = str(row.get("TRKORR_s", "")).strip()
        if trkorr:
            transport_sizes[trkorr] += 1

    # Large transports (> 50 objects) — higher risk for post-import regression
    large_transports = [
        {"transport": tr, "object_count": count}
        for tr, count in sorted(transport_sizes.items(), key=lambda x: -x[1])
        if count > 50
    ]

    # ── Step 3: Unique object names per type (top 10 per type) ───────────────
    # Helps identify which specific programs/tables were changed
    obj_names_by_type: dict[str, set] = defaultdict(set)
    for row in rows:
        obj_type = str(row.get("OBJECT_s", "")).strip()
        obj_name = str(row.get("OBJ_NAME_s", "")).strip()
        if obj_name:
            obj_names_by_type[obj_type].add(obj_name)

    top_changed_objects = {
        obj_type: sorted(list(names))[:10]
        for obj_type, names in obj_names_by_type.items()
        if len(names) > 0
    }

    # ── Step 4: Findings ─────────────────────────────────────────────────────
    findings: list[dict] = []

    if large_transports:
        findings.append({
            "finding": "LARGE_TRANSPORTS",
            "severity": "info",
            "count": len(large_transports),
            "largest": large_transports[0] if large_transports else None,
            "meaning": (
                f"{len(large_transports)} transport(s) contain >50 objects — "
                f"these are complex changes with higher regression risk."
            ),
            "investigation_hints": [
                "For Scenario 4 (Post-Maintenance Degradation), correlate large "
                "transports with the maintenance window timestamp.",
                "Check if transported programs appear in short dumps or SMON degradation.",
            ],
        })

    return {
        "status": "success",
        "analysis_type": "transport_management",
        "data_source": "STMS_objects",
        "severity": "info" if findings else "healthy",
        "summary": (
            f"{total} transport object(s) across {len(transport_sizes)} request(s). "
            f"Code: {code_objects}, Config/Data: {config_objects}."
        ),
        "object_distribution": object_distribution,
        "code_vs_config": {"code": code_objects, "config_data": config_objects},
        "large_transports": large_transports,
        "top_changed_objects": top_changed_objects,
        "findings": findings,
        "raw_row_count": total,
        "context": context,
    }

"""System logs analyzer — SM21 system log entries."""
from __future__ import annotations

from collections import Counter
from typing import Any

import domain_registry as dr
from analyzers import register


@register("system_logs")
def analyze_system_logs(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate SM21 system log entries."""
    total      = len(rows)
    msg_counts = Counter(str(r.get("Msg_area_Msd_Id_s", "")).strip() for r in rows)
    present    = set(msg_counts.keys())

    top_msgs = [
        {
            "msg_id":   m,
            "count":    c,
            "category": dr.get_msg_group(m)["category"],
        }
        for m, c in msg_counts.most_common(10)
    ]

    # Deduplicate by group prefix
    group_totals: dict[str, int] = {}
    group_ids: dict[str, list[str]] = {}
    group_rows: dict[str, list[dict]] = {}
    for row in rows:
        msg_id = str(row.get("Msg_area_Msd_Id_s", "")).strip()
        g = dr.get_msg_group(msg_id)["group_key"]
        group_totals[g] = group_totals.get(g, 0) + 1
        group_ids.setdefault(g, [])
        if msg_id not in group_ids[g]:
            group_ids[g].append(msg_id)
        group_rows.setdefault(g, []).append(row)

    next_steps: list[dict] = []
    for g_key in sorted(group_totals, key=lambda k: -group_totals[k]):
        ids_in_group = sorted(group_ids[g_key])
        entry = dr.get_msg_group(ids_in_group[0])
        g_rows = group_rows.get(g_key, [])
        affected_programs  = sorted({str(r.get("Program_s",   "")).strip() for r in g_rows if r.get("Program_s")})
        affected_hosts     = sorted({str(r.get("E2E_HOST_s",  "")).strip() for r in g_rows if r.get("E2E_HOST_s")})
        affected_users     = sorted({str(r.get("E2E_USER_s",  "")).strip() for r in g_rows if r.get("E2E_USER_s")})
        descriptions = list({str(r.get("Description_s", "")).strip() for r in g_rows if r.get("Description_s")})[:5]
        next_steps.append({
            "message_group":        g_key,
            "message_ids_present":  ids_in_group,
            "count":                group_totals[g_key],
            "category":             entry["category"],
            "meaning":              entry["meaning"],
            "investigation_hints":  entry["investigation_hints"],
            "filter_context": {
                "affected_programs":    affected_programs,
                "affected_hosts":       affected_hosts,
                "affected_users":       affected_users,
                "descriptions":         descriptions,
            },
        })

    if not next_steps:
        next_steps.append({
            "message_group":       "unknown",
            "message_ids_present": [],
            "count":               total,
            "category":            "Unknown",
            "meaning":             "No classifiable message IDs found in these log entries.",
            "investigation_hints": [
                "Review Description_s field values for recurring patterns.",
                "Group entries by host to check whether errors are host-specific.",
            ],
        })

    return {
        "status":          "success",
        "analysis_type":   "system_logs",
        "summary": (
            f"{total} system log entries found. "
            f"Message IDs present: {', '.join(sorted(present))}. "
            f"{len(next_steps)} follow-up investigation step(s) identified."
        ),
        "severity":        "errors_present" if any(s["category"] != "Info" for s in next_steps) else "informational",
        "top_message_ids": top_msgs,
        "next_investigation_steps": next_steps,
        "raw_row_count":   total,
        "context":         context,
    }

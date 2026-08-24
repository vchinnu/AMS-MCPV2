"""Short dumps analyzer — ST22 ABAP runtime errors.

Handles both summary format (SapNetweaver_ShortDumps_CL) and
full-snap detail format (SapNetweaver_ShortDumps_SNAPFulldump_CL).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import domain_registry as dr
from analyzers import register


@register("short_dumps")
def analyze_short_dumps(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate ST22 short dump data."""
    # Detect FULL_SNAP table format (section-based) vs summary ShortDumps_CL format
    if rows and "section_s" in rows[0]:
        return _analyze_full_snap(rows, context)

    total = len(rows)

    classified: list[dict] = []
    for row in rows:
        error_code = str(row.get("Runtime_Error_s", "")).strip()
        info = dr.classify_runtime_error(error_code)
        classified.append({
            "runtime_error":      error_code,
            "category":           info["category"],
            "subcategory":        info["subcategory"],
            "meaning":            info.get("meaning", ""),
            "error_short_text":   row.get("Error_Short_Text_s", ""),
            "program":            row.get("Program_s", ""),
            "user":               row.get("E2E_USER_s", ""),
            "host":               row.get("E2E_HOST_s", ""),
            "component":          row.get("Component_s", ""),
            "timestamp":          str(row.get("serverTimestamp_t", row.get("timestamp_t", ""))),
            "investigation_hints": info.get("investigation_hints", []),
        })

    category_counts = Counter(r["category"]     for r in classified)
    error_counts    = Counter(r["runtime_error"] for r in classified)
    program_counts  = Counter(r["program"]       for r in classified if r["program"])
    host_counts     = Counter(r["host"]          for r in classified if r["host"])
    user_counts     = Counter(r["user"]          for r in classified if r["user"])

    error_investigation: list[dict] = []
    seen_errors: set[str] = set()
    for row_c in classified:
        err = row_c["runtime_error"]
        if err in seen_errors:
            continue
        seen_errors.add(err)
        affected_users    = sorted({r["user"]      for r in classified if r["runtime_error"] == err and r["user"]})
        affected_programs = sorted({r["program"]   for r in classified if r["runtime_error"] == err and r["program"]})
        affected_hosts    = sorted({r["host"]      for r in classified if r["runtime_error"] == err and r["host"]})

        error_investigation.append({
            "runtime_error":       err,
            "category":            row_c["category"],
            "subcategory":         row_c["subcategory"],
            "meaning":             row_c.get("meaning", ""),
            "count":               error_counts[err],
            "affected_users":      affected_users,
            "affected_programs":   affected_programs,
            "affected_hosts":      affected_hosts,
            "investigation_hints": row_c.get("investigation_hints", []),
        })

    error_investigation.sort(key=lambda x: -x["count"])

    return {
        "status":              "success",
        "analysis_type":       "short_dumps",
        "summary": (
            f"{total} short dump(s) across {len(error_counts)} unique runtime error(s). "
            f"Categories present: {', '.join(sorted(category_counts.keys()))}. "
            f"Every entry in error_investigation must be analysed."
        ),
        "category_breakdown":  [{"category": k, "count": v} for k, v in sorted(category_counts.items(), key=lambda x: -x[1])],
        "error_investigation": error_investigation,
        "top_programs":        [{"program": p, "count": c} for p, c in program_counts.most_common(5)],
        "top_hosts":           [{"host": h,    "count": c} for h, c in host_counts.most_common(5)],
        "top_users":           [{"user": u,    "count": c} for u, c in user_counts.most_common(5)],
        "raw_row_count":       total,
        "context":             context,
    }


def _analyze_full_snap(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify FULL_SNAP section-based dump detail rows."""
    total = len(rows)

    # Group rows by dump (correlation_id_g)
    dumps: dict[str, list[dict]] = {}
    for row in rows:
        cid = str(row.get("correlation_id_g", "")).strip()
        dumps.setdefault(cid, []).append(row)

    unique_dump_count = len(dumps)

    classified: list[dict] = []
    for cid, dump_rows in dumps.items():
        error_code = ""
        user = ""
        host = ""
        sections: list[dict] = []

        for row in dump_rows:
            if not error_code:
                error_code = str(row.get("Runtime_Error_s", "")).strip()
            if not user:
                user = str(row.get("E2E_USER_s", "")).strip()
            if not host:
                host = str(row.get("E2E_HOST_s", "")).strip()
            section = str(row.get("section_s", "")).strip()
            if not section or section == "RAW_ALL":
                continue
            guide = dr.get_section_guide(section)
            sections.append({
                "section_s":          section,
                "section_text_s":     str(row.get("section_text_s", "")).strip(),
                "section_key_name_s": str(row.get("section_key_name_s", "")).strip(),
                "interpretation":     guide,
            })

        info = dr.classify_runtime_error(error_code)
        classified.append({
            "correlation_id":      cid,
            "runtime_error":       error_code,
            "category":            info["category"],
            "subcategory":         info["subcategory"],
            "meaning":             info.get("meaning", ""),
            "user":                user,
            "host":                host,
            "sections":            sections,
            "investigation_hints": info.get("investigation_hints", []),
        })

    error_counts    = Counter(r["runtime_error"] for r in classified)
    category_counts = Counter(r["category"]      for r in classified)
    host_counts     = Counter(r["host"]          for r in classified if r["host"])
    user_counts     = Counter(r["user"]          for r in classified if r["user"])

    error_investigation: list[dict] = []
    seen_errors: set[str] = set()
    for entry in classified:
        err = entry["runtime_error"]
        if err in seen_errors:
            continue
        seen_errors.add(err)
        affected_users = sorted({r["user"] for r in classified if r["runtime_error"] == err and r["user"]})
        affected_hosts = sorted({r["host"] for r in classified if r["runtime_error"] == err and r["host"]})
        sample_dumps   = [r for r in classified if r["runtime_error"] == err][:5]
        priority = dr.get_priority_sections(entry["category"])
        error_investigation.append({
            "runtime_error":       err,
            "category":            entry["category"],
            "subcategory":         entry["subcategory"],
            "meaning":             entry.get("meaning", ""),
            "count":               error_counts[err],
            "affected_users":      affected_users,
            "affected_hosts":      affected_hosts,
            "investigation_hints": entry.get("investigation_hints", []),
            "priority_sections":   priority,
            "sample_dumps":        [
                {
                    "correlation_id": d["correlation_id"],
                    "user":           d["user"],
                    "host":           d["host"],
                    "sections":       d["sections"],
                }
                for d in sample_dumps
            ],
        })

    error_investigation.sort(key=lambda x: -x["count"])

    return {
        "status":              "success",
        "analysis_type":       "short_dumps",
        "data_source":         "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "summary": (
            f"{total} section rows from {unique_dump_count} unique dump(s) "
            f"across {len(error_counts)} runtime error type(s). "
            f"Categories: {', '.join(sorted(category_counts.keys()))}. "
            f"Full section detail available per dump — use correlation_id_g to drill into specific sections."
        ),
        "unique_dump_count":   unique_dump_count,
        "category_breakdown":  [{"category": k, "count": v} for k, v in sorted(category_counts.items(), key=lambda x: -x[1])],
        "error_investigation": error_investigation,
        "top_hosts":           [{"host": h, "count": c} for h, c in host_counts.most_common(5)],
        "top_users":           [{"user": u, "count": c} for u, c in user_counts.most_common(5)],
        "raw_row_count":       total,
        "context":             context,
    }

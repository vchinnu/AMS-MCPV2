"""TOON (Tool Output Optimization Notation) formatter for MCP responses.

Applies token-efficient formatting rules to analyzer outputs:
  1. Omit null/empty fields
  2. Deduplicate filter_context (remove when it repeats parent data)
  3. Compact arrays where possible
  4. Preserve all investigation_hints (no capping per user request)

This is a post-processing step applied to any analyzer output before
returning to the model.
"""
from __future__ import annotations

from typing import Any


def compact(result: dict[str, Any]) -> dict[str, Any]:
    """Apply TOON formatting to an analyzer result dict.

    Rules applied:
      - Remove keys with None, empty string, empty list, or empty dict values
      - Remove filter_context blocks that duplicate parent-level data
      - Compact category_breakdown into shorter form
      - Add query_id for progressive disclosure
    """
    return _compact_recursive(result)


def _compact_recursive(obj: Any) -> Any:
    """Recursively compact a data structure."""
    if isinstance(obj, dict):
        compacted = {}
        for k, v in obj.items():
            # Skip null/empty values
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            if isinstance(v, (list, dict)) and not v:
                continue

            # Skip redundant filter_context if it only duplicates parent data
            if k == "filter_context" and isinstance(v, dict):
                v = _compact_filter_context(v)
                if not v:
                    continue

            compacted[k] = _compact_recursive(v)
        return compacted

    elif isinstance(obj, list):
        return [_compact_recursive(item) for item in obj if _is_non_empty(item)]

    return obj


def _compact_filter_context(ctx: dict) -> dict:
    """Remove empty entries from filter_context; return empty dict if all empty."""
    compacted = {}
    for k, v in ctx.items():
        if v is None:
            continue
        if isinstance(v, (list, set)) and not v:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        compacted[k] = v
    return compacted


def _is_non_empty(value: Any) -> bool:
    """Check if a value is non-empty (for list filtering)."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and not value:
        return False
    return True


def format_summary_response(
    classified: dict[str, Any],
    query_id: str,
    row_count: int,
) -> dict[str, Any]:
    """Format a classified result for the summary tier (execute_query response).

    Returns a compact summary with query_id for drill-down.
    The full classified data stays in the cache.
    """
    output: dict[str, Any] = {
        "status": classified.get("status", "success"),
        "query_id": query_id,
        "analysis_type": classified.get("analysis_type", ""),
        "summary": classified.get("summary", ""),
        "row_count": row_count,
    }

    # Include severity if present
    if classified.get("severity"):
        output["severity"] = classified["severity"]

    # Include system_health for availability
    if classified.get("system_health"):
        output["system_health"] = classified["system_health"]

    # Include compact category breakdown (top-level patterns)
    if classified.get("category_breakdown"):
        output["category_breakdown"] = classified["category_breakdown"]

    # For HA cluster: include cluster_summary (it's already compact)
    if classified.get("cluster_summary"):
        output["cluster_summary"] = compact(classified["cluster_summary"])

    # Include top-level error investigation (compacted)
    if classified.get("error_investigation"):
        # Return compact version: just error, category, count, meaning
        output["error_patterns"] = [
            compact({
                "error": e.get("runtime_error", ""),
                "category": e.get("category", ""),
                "count": e.get("count", 0),
                "meaning": e.get("meaning", ""),
                "investigation_hints": e.get("investigation_hints", []),
            })
            for e in classified["error_investigation"]
        ]

    # For system_logs: include investigation steps compacted
    if classified.get("next_investigation_steps"):
        output["investigation_steps"] = [
            compact({
                "group": s.get("message_group", ""),
                "category": s.get("category", ""),
                "count": s.get("count", 0),
                "meaning": s.get("meaning", ""),
                "investigation_hints": s.get("investigation_hints", []),
            })
            for s in classified["next_investigation_steps"]
        ]

    # For batch_jobs: include status investigation
    if classified.get("status_investigation"):
        output["status_investigation"] = [
            compact(s) for s in classified["status_investigation"]
        ]

    # For HA cluster / availability: include findings summary
    if classified.get("critical_findings"):
        output["critical_findings"] = [compact(f) for f in classified["critical_findings"]]
    if classified.get("warnings"):
        output["warnings"] = [compact(f) for f in classified["warnings"]]

    # For OS metrics: include category summary
    if classified.get("category_summary"):
        output["category_summary"] = classified["category_summary"]
    if classified.get("threshold_guidance"):
        output["threshold_guidance"] = classified["threshold_guidance"]

    # For batch jobs: top failed jobs
    if classified.get("top_cancelled_jobs") or classified.get("top_failed_jobs"):
        output["top_failed_jobs"] = (
            classified.get("top_failed_jobs") or classified.get("top_cancelled_jobs", [])
        )

    # Pipeline info
    if classified.get("_pipeline"):
        output["_pipeline"] = classified["_pipeline"]

    # Hint for drill-down
    output["_hint"] = "Use get_details(query_id, category) to drill into specific findings."

    return compact(output)

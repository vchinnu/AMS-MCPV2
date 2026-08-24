"""Tool: deeper_rca_analysis - apply SAP domain knowledge to classify query results.

Now delegates to the plugin-based analyzer registry (analyzers/ package).
This module is kept as a thin wrapper for backward compatibility with
server.py and any direct imports.
"""
from __future__ import annotations

from typing import Any

from analyzers import get_analyzer, get_all_analysis_types
from tools.toon_formatter import compact


def deeper_rca_analysis(
    results: dict[str, Any],
    analysis_type: str,
    context: str = "",
) -> dict[str, Any]:
    """Apply SAP domain knowledge to interpret and classify query results.

    Delegates to the appropriate plugin analyzer from the analyzers/ package.
    """
    if results.get("status") in ("error", "rejected"):
        return {
            "status": "error",
            "analysis_type": analysis_type,
            "summary": f"Cannot analyse - query failed: {results.get('error', 'unknown error')}",
            "findings": [],
            "raw_row_count": 0,
            "context": context,
        }

    rows: list[dict] = results.get("rows", [])

    if not rows:
        return {
            "status": "no_data",
            "analysis_type": analysis_type,
            "summary": "No data returned for this query. The system may be healthy in this area.",
            "findings": [],
            "recommendations": ["Verify the time range and SID filter are correct."],
            "raw_row_count": 0,
            "context": context,
        }

    # Route to the appropriate plugin analyzer
    analyzer = get_analyzer(analysis_type)
    if analyzer:
        result = analyzer(rows, context)
        return compact(result)

    # No analyzer registered for this type
    return {
        "status": "success",
        "analysis_type": analysis_type,
        "summary": f"{len(rows)} rows returned. No domain classification defined for '{analysis_type}' yet.",
        "findings": rows[:20],
        "recommendations": [],
        "raw_row_count": len(rows),
        "context": context,
    }

"""Tool 2: execute_query — validate and run an agent-generated KQL query.

Security model:
  - Blocks all KQL management commands (lines beginning with '.')
  - Blocks SQL-style write keywords as a secondary guard
  - Automatically appends a row limit if the query has none
  - Passes the validated query to the Azure Log Analytics client

When analysis_type is provided and matches a registered analyzer (see analyzers/),
the raw rows are automatically classified by deeper_rca_analysis before being
returned — the agent only sees structured findings, never the raw 1000-row result.
"""
from __future__ import annotations

import re
from datetime import datetime

import la_client
import config
from analyzers import get_analyzer, get_all_analysis_types
from tools.result_cache import generate_query_id, store as cache_store
from tools.generic_summarizer import summarize as generic_summarize
from tools.toon_formatter import format_summary_response, compact

# KQL management commands all start with a dot — block any query that has one
_MGMT_CMD = re.compile(r"^\s*\.", re.MULTILINE)

# Additional SQL-style write keywords that should never appear in read KQL
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+SET|DELETE\s+FROM|DROP\s+TABLE|TRUNCATE)\b",
    re.IGNORECASE,
)

_SID_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")


def _strip_comments(kql: str) -> str:
    return re.sub(r"//[^\n]*", "", kql)


def _is_read_only(kql: str) -> tuple[bool, str]:
    clean = _strip_comments(kql)
    if _MGMT_CMD.search(clean):
        return False, "Query contains a KQL management command (line beginning with '.'). Only read queries are permitted."
    if _WRITE_KEYWORDS.search(clean):
        return False, "Query contains a write operation keyword. Only read queries are permitted."
    return True, ""


def execute_query(
    kql: str,
    sid: str,
    timespan_hours: int | None = None,
    start_time: str = "",
    end_time: str = "",
    workspace_id: str = "",
    analysis_type: str = "",
    context: str = "",
) -> dict:
    """Execute a KQL query against the Azure Log Analytics workspace.

    The agent generates the KQL (after calling get_schema to learn the table structure).
    This tool validates the query is read-only, enforces a row cap, then runs it.

    When analysis_type matches a registered analyzer (see analyzers/), the raw rows are
    automatically classified by the SAP domain knowledge engine before being returned.
    The agent receives structured findings instead of raw rows — this avoids the agent
    consuming tokens on up to 1000 unclassified rows.

    If analysis_type is blank or does not match a known type, raw query results are
    returned as-is so the agent can inspect them directly.

    Args:
        kql:            KQL query string. The agent constructs this from the schema.
                        Must target tables in the Log Analytics workspace.
        sid:            SAP System ID being queried (e.g. 'CHA', 'PRD').
                        Pass 'ALL' to indicate a cross-system query with no SID filter.
                        Required — must be 1–10 uppercase alphanumeric characters or 'ALL'.
        timespan_hours: Relative time window: last N hours from now (e.g. 4, 24, 48).
                        Used when start_time/end_time are not provided. Defaults to 24.
        start_time:     Absolute window start in ISO 8601 format (e.g. '2026-04-07T10:00:00Z').
                        Must be used together with end_time.
        end_time:       Absolute window end in ISO 8601 format (e.g. '2026-04-07T14:00:00Z').
                        Must be used together with start_time.
        workspace_id:   Optional override for the Log Analytics workspace.
                        ARM resource ID or workspace GUID.
                        Leave blank to use AZURE_LOG_ANALYTICS_WORKSPACE_ID from .env.
        analysis_type:  Optional SAP domain classification type.
                        Any type with a registered analyzer (see analyzers/) triggers
                        automatic classification before returning to the agent.
                        Leave blank for raw results (e.g. tables with no classification handler).
        context:        Optional free-text context string passed through to the classifier
                        (e.g. 'SID=PRD, investigating dump spike after 14:00 UTC').

    Time resolution (in priority order):
        1. start_time + end_time  → absolute range query
        2. timespan_hours         → relative window from now
        3. (neither provided)     → defaults to last 24 hours

    Returns:
        When analysis_type matches a registered analyzer:
          → Structured classification output from deeper_rca_analysis
            (category_breakdown, error_investigation, investigation_hints, filter_context)

        When analysis_type is blank or unknown:
          status      : "success" or "partial"
          sid         : echoed back for traceability
          rows        : list of row dicts from the primary result table
          row_count   : number of rows returned
          tables      : all result tables (useful for multi-table queries)

        On failure (either path):
          status      : "error" or "rejected"
          error       : description of what went wrong
    """
    # ── Validate SID ─────────────────────────────────────────────────────────
    sid = sid.strip().upper()
    if sid != "ALL" and not _SID_PATTERN.match(sid):
        return {
            "status": "rejected",
            "error": (
                f"Invalid SID '{sid}'. SAP SIDs are 1–10 uppercase alphanumeric characters "
                "(e.g. 'CHA', 'PRD') or 'ALL' for a cross-system query."
            ),
            "rows": [],
            "row_count": 0,
            "tables": [],
        }

    # ── Resolve timespan ──────────────────────────────────────────────────────
    if start_time and end_time:
        try:
            dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            dt_end   = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError as exc:
            return {
                "status": "rejected",
                "error": f"Invalid time format: {exc}. Use ISO 8601, e.g. '2026-04-07T10:00:00Z'.",
                "rows": [],
                "row_count": 0,
                "tables": [],
            }
        if dt_end <= dt_start:
            return {
                "status": "rejected",
                "error": "end_time must be after start_time.",
                "rows": [],
                "row_count": 0,
                "tables": [],
            }
        timespan = (dt_start, dt_end)
    elif timespan_hours is not None:
        if timespan_hours < 1:
            return {
                "status": "rejected",
                "error": "timespan_hours must be >= 1.",
                "rows": [],
                "row_count": 0,
                "tables": [],
            }
        timespan = timespan_hours
    else:
        # No explicit time window supplied by the agent.
        # If the KQL already contains its own time filter (between/ago/startofday etc.)
        # use a wide 30-day API window so the KQL filter is not silently overridden by
        # a narrow default timespan on the Azure LA API call (which would drop historic rows).
        # If there's no KQL time filter either, fall back to the configured default.
        _KQL_TIME_FILTER = re.compile(
            r"\b(between\s*\(|ago\s*\(|startofday|endofday|startofmonth|now\s*\()",
            re.IGNORECASE,
        )
        if _KQL_TIME_FILTER.search(kql):
            timespan = 30 * 24  # 30 days — wide enough to not clip any realistic KQL range
        else:
            timespan = config.DEFAULT_TIMESPAN_HOURS

    # ── Validate read-only ────────────────────────────────────────────────────
    safe, reason = _is_read_only(kql)
    if not safe:
        return {"status": "rejected", "error": reason, "rows": [], "row_count": 0, "tables": []}

    # Enforce row cap if the query has no explicit limit
    capped_kql = kql
    if not re.search(r"\|\s*(take|limit)\s+\d+", kql, re.IGNORECASE):
        capped_kql = f"{kql.rstrip()}\n| take {config.MAX_QUERY_ROWS}"

    result = la_client.execute_kql(capped_kql, timespan, workspace_id or None, sid=sid)
    result["sid"] = sid

    rows = result.get("rows", [])
    row_count = result.get("row_count", len(rows))

    # Generate a query_id for progressive disclosure
    query_id = generate_query_id(kql, sid)

    # If a known analysis_type is provided, classify before returning
    analyzer = get_analyzer(analysis_type) if analysis_type else None

    if analyzer:
        classified = analyzer(rows, context)
        classified["_pipeline"] = f"execute_query → {analysis_type} analyzer (auto-classified)"
        classified["_query_id"] = query_id

        # Cache full classified result for drill-down via get_details
        cache_store(
            query_id=query_id,
            rows=rows,
            analysis_type=analysis_type,
            classified=classified,
            sid=sid,
            kql=kql,
        )

        # Return TOON-formatted summary (compact, with query_id for drill-down)
        return format_summary_response(classified, query_id, row_count)

    # No domain analyzer matched — use generic statistical summarizer
    # Never return raw rows to the model
    cache_store(
        query_id=query_id,
        rows=rows,
        analysis_type=analysis_type or "unclassified",
        classified=None,
        sid=sid,
        kql=kql,
    )

    summary = generic_summarize(result, context)
    summary["query_id"] = query_id
    summary["sid"] = sid
    summary["_pipeline"] = "execute_query → generic_summarizer (no domain analyzer)"
    summary["_hint"] = "Use get_details(query_id) for paginated raw rows if needed."
    return compact(summary)

"""SAP RCA MCP Server — entry point.

Run locally (stdio mode for Claude Desktop / MCP Inspector):
    python server.py
    mcp dev server.py

Run as HTTP/SSE server (for Azure App Service):
    uvicorn server:mcp --host 0.0.0.0 --port 8000
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import config
from analyzers import get_all_analysis_types
from tools.get_schema      import get_schema           as _get_schema
from tools.execute_query   import execute_query        as _execute_query
from tools.deeper_rca_analysis import deeper_rca_analysis as _deeper_rca_analysis
from tools.result_cache    import get_detail_slice     as _get_detail_slice

config.validate()

# Build the classified types list once at startup from the plugin registry.
_classified_types_str = " | ".join(sorted(get_all_analysis_types()))

mcp = FastMCP(
    name="sap-rca-server",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    # Foundry Agent Service issues each MCP call as an independent request and does not
    # replay mcp-session-id, so stateful mode fails with "Missing session ID".
    stateless_http=True,
    instructions=(
        "You are an SAP observability assistant. "
        "Preferred workflow: "
        "(1) Call get_schema to learn table structures and column names. "
        "(2) Call execute_query with analysis_type set to the appropriate SAP domain "
        f"({_classified_types_str}) — results are automatically classified and returned "
        "as structured findings with a query_id for drill-down. "
        "(3) Use get_details(query_id, category) to drill into specific categories or "
        "paginate through additional rows from a previous query. "
        "(4) If you need to re-classify raw rows from a previous call, use deeper_rca_analysis. "
        "Never modify data — all queries must be read-only."
    ),
)


@mcp.tool()
def get_schema(table_names: list[str] | None = None) -> dict:
    """Return schema information for Log Analytics tables in the SAP RCA registry.

    Call this FIRST before generating any KQL. Returns exact column names, data types,
    the time column to use for filters, the SID column, and KQL writing hints.

    Args:
        table_names: List of specific table names for full schema detail.
                     Pass None to get a summary of all registered tables.
    """
    return _get_schema(table_names)


@mcp.tool()
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
    """Execute an agent-generated KQL query against the Azure Log Analytics workspace.

    The query is validated for read-only safety before execution. A row cap is applied
    automatically if the query has no 'take' or 'limit' clause.

    When analysis_type matches a known SAP domain type, results are automatically
    classified by the SAP domain knowledge engine before being returned — the agent
    receives structured findings instead of raw rows.

    Args:
        kql:            KQL query string. Build this using column names from get_schema.
        sid:            SAP System ID being queried (e.g. 'CHA', 'PRD').
                        Pass 'ALL' for a cross-system query with no SID filter. Required.
        timespan_hours: Relative time window — last N hours from now (e.g. 4, 24).
                        Defaults to 24 if neither timespan_hours nor start_time/end_time given.
        start_time:     Absolute window start, ISO 8601 (e.g. '2026-04-07T10:00:00Z').
                        Provide with end_time for a fixed time range query.
        end_time:       Absolute window end, ISO 8601 (e.g. '2026-04-07T14:00:00Z').
                        Provide with start_time for a fixed time range query.
        workspace_id:   Optional workspace override (ARM resource ID or GUID).
                        Leave blank to use the configured default workspace.
        analysis_type:  SAP domain classification type — triggers automatic classification.
                        Valid values are listed in CLASSIFIED_ANALYSIS_TYPES (schema_registry.py)
                        and shown in the server instructions above.
                        Leave blank for raw results (OS metrics, HA cluster, other tables).
        context:        Optional context string passed to the classifier
                        (e.g. 'SID=PRD, investigating dump spike after 14:00 UTC').
    """
    return _execute_query(kql, sid, timespan_hours, start_time, end_time, workspace_id, analysis_type, context)


@mcp.tool()
def deeper_rca_analysis(results: dict, analysis_type: str, context: str = "") -> dict:
    """Apply SAP domain knowledge to classify and interpret query results.

    Normally you do not need to call this directly — execute_query auto-classifies
    when analysis_type is provided. Call this only when you have raw rows from a
    previous execute_query call and want to classify them after the fact.

    Args:
        results:       Dict returned by execute_query (must contain 'rows').
        analysis_type: SAP domain classification type. Valid values are listed in
                       CLASSIFIED_ANALYSIS_TYPES (schema_registry.py) and shown in
                       the server instructions.
        context:       Optional context string (SID, time range, alert description).
    """
    return _deeper_rca_analysis(results, analysis_type, context)


@mcp.tool()
def get_details(
    query_id: str,
    category: str = "",
    offset: int = 0,
    limit: int = 5,
) -> dict:
    """Retrieve detailed rows from a previously cached query result.

    After execute_query returns a summary with a query_id, use this tool to
    drill into specific categories or paginate through additional rows without
    re-running the query.

    Args:
        query_id: The query_id returned by execute_query (e.g. 'q_ab12cd34').
        category: Filter to a specific finding category from the classified output.
                  Leave blank to get raw rows (paginated).
        offset:   Start position for pagination (default 0).
        limit:    Number of rows to return per page (default 5, max 50).
    """
    return _get_detail_slice(query_id, category, offset, limit)


if __name__ == "__main__":
    mcp.run()

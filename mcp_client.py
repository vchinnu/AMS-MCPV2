"""MCP client — connects to the SAP RCA MCP server and calls its tools.

Two modes:
  1. Subprocess (stdio) — starts server.py as a child process. Good for local testing.
  2. HTTP/SSE          — connects to a running server over HTTP. Good for Azure deployment.

Usage examples at the bottom of this file.

Install extra dependency if not already present:
    pip install mcp
(Already in requirements.txt)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


# ── Subprocess (stdio) client ─────────────────────────────────────────────────

async def call_tool_stdio(tool_name: str, arguments: dict) -> dict:
    """Start server.py as a subprocess and call one tool, then shut down.

    Best for: quick one-off calls, CI tests, scripts that don't need a
    persistent server.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_py = Path(__file__).parent / "server.py"
    python    = sys.executable

    server_params = StdioServerParameters(
        command=python,
        args=[str(server_py)],
        env=None,  # inherits current env (including .env values loaded by server.py)
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            # FastMCP returns content as a list of TextContent items
            raw = result.content[0].text if result.content else "{}"
            return json.loads(raw)


# ── HTTP/SSE client ───────────────────────────────────────────────────────────

async def call_tool_http(tool_name: str, arguments: dict, base_url: str = "http://localhost:8000") -> dict:
    """Connect to a running MCP server over HTTP/SSE and call one tool.

    Best for: server already running (uvicorn), Azure deployment, AI Foundry testing.

    Start the server first:
        uvicorn MCP.server:mcp --host 0.0.0.0 --port 8000
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(f"{base_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            raw = result.content[0].text if result.content else "{}"
            return json.loads(raw)


# ── Convenience helpers ───────────────────────────────────────────────────────

async def list_tools_stdio() -> list[str]:
    """Return names of all tools exposed by the MCP server."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_py = Path(__file__).parent / "server.py"
    server_params = StdioServerParameters(command=sys.executable, args=[str(server_py)])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [t.name for t in tools.tools]


async def run_rca_stdio(sid: str, time_range_hours: int = 4, issue_description: str = "") -> dict:
    """Convenience wrapper — run full RCA via stdio client."""
    return await call_tool_stdio(
        "run_full_rca",
        {"sid": sid, "time_range_hours": time_range_hours, "issue_description": issue_description},
    )


async def run_rca_http(sid: str, time_range_hours: int = 4, base_url: str = "http://localhost:8000") -> dict:
    """Convenience wrapper — run full RCA via HTTP client."""
    return await call_tool_http(
        "run_full_rca",
        {"sid": sid, "time_range_hours": time_range_hours},
        base_url=base_url,
    )


# ── AI Foundry integration helper ─────────────────────────────────────────────

async def get_tools_as_openai_functions() -> list[dict]:
    """Return the MCP tools in OpenAI function-calling format.

    Useful when you want to pass MCP tools into an Azure AI Foundry / OpenAI
    chat completion call manually (without native MCP support).
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_py = Path(__file__).parent / "server.py"
    server_params = StdioServerParameters(command=sys.executable, args=[str(server_py)])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema,
                    },
                }
                for t in tools.tools
            ]


# ── Demo / test runner ────────────────────────────────────────────────────────

async def _demo():
    print("=" * 60)
    print("SAP RCA MCP Client Demo")
    print("=" * 60)

    # 1. List available tools
    print("\n[1] Listing tools from MCP server...")
    tools = await list_tools_stdio()
    print(f"    Tools: {tools}")

    # 2. get_schema — no Azure needed
    print("\n[2] Calling get_schema (all tables)...")
    schema = await call_tool_stdio("get_schema", {})
    for t in schema.get("registered_tables", []):
        print(f"    {t['name']}  →  {t['analysis_type']}")

    # 3. get_schema — full detail for one table
    print("\n[3] Calling get_schema for ShortDumps...")
    detail = await call_tool_stdio("get_schema", {"table_names": ["SapNetweaver_ShortDumps_CL"]})
    cols = list(detail.get("SapNetweaver_ShortDumps_CL", {}).get("columns", {}).keys())
    print(f"    Columns ({len(cols)}): {cols[:6]}...")

    # 4. execute_query — live LA query
    print("\n[4] Calling execute_query (live, last 1h)...")
    kql = (
        "SapNetweaver_ShortDumps_CL\n"
        "| where serverTimestamp_t > ago(1h)\n"
        "| where SID_s == 'CHA'\n"
        "| summarize Count=count() by Runtime_Error_s\n"
        "| order by Count desc\n"
        "| take 5"
    )
    qresult = await call_tool_stdio("execute_query", {"kql": kql, "timespan_hours": 1})
    print(f"    Status: {qresult.get('status')}  Rows: {qresult.get('row_count')}")
    for row in qresult.get("rows", []):
        print(f"      {row}")

    # 5. analyze_results on those rows
    if qresult.get("status") == "success" and qresult.get("row_count", 0) > 0:
        print("\n[5] Calling analyze_results...")
        analysis = await call_tool_stdio(
            "analyze_results",
            {"results": qresult, "analysis_type": "short_dumps", "context": "SID=CHA, demo run"},
        )
        print(f"    Severity : {analysis.get('severity')}")
        print(f"    Summary  : {analysis.get('summary')}")

    # 6. run_full_rca
    print("\n[6] Calling run_full_rca (SID=CHA, 2h)...")
    rca = await run_rca_stdio("CHA", time_range_hours=2)
    print(f"    Severity : {rca.get('severity')}")
    print(f"    Summary  : {rca.get('summary')}")
    print(f"    Correlations: {len(rca.get('correlations', []))}")

    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(_demo())

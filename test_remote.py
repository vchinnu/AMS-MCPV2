"""Interactive test client for the remote SAP RCA MCP server.

Connects to the Azure Container Apps endpoint via streamable-http transport.
Lists available tools and lets you call them interactively, printing the
full structured response so you can review reasoning and output.

Usage:
    python MCP/test_remote.py
    python MCP/test_remote.py --url https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io/mcp

Shortcuts available at the prompt:
    schema              → call get_schema (no args)
    schema <TABLE>      → call get_schema for a specific table
    query <SID> <KQL>   → call execute_query with analysis_type=short_dumps
    rca <SID>           → call run_full_rca for a SID (last 24 h)
    tools               → list all available tools
    help                → show this help
    quit / exit         → exit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap

DEFAULT_URL = "https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io/mcp"

HELP = textwrap.dedent("""
    ┌─────────────────────────────────────────────────────────────────┐
    │  SAP RCA MCP — Interactive Test Client                          │
    ├─────────────────────────────────────────────────────────────────┤
    │  Shortcuts:                                                      │
    │    tools                    List all available tools            │
    │    schema                   Get full schema summary             │
    │    schema <TABLE>           Schema for one table                │
    │    query <SID> <KQL>        Run a KQL query (auto-classify)     │
    │    rca <SID> [hours]        Run full RCA (default 24 h)         │
    │    call <tool> <json>       Call any tool with raw JSON args     │
    │    help                     Show this help                      │
    │    quit / exit              Exit                                │
    └─────────────────────────────────────────────────────────────────┘
""")


def _pretty(data) -> str:
    """Pretty-print a dict/list, truncating very long strings inside it."""
    text = json.dumps(data, indent=2, default=str)
    # Truncate individual long lines so the terminal stays readable
    lines = []
    for line in text.splitlines():
        if len(line) > 200:
            line = line[:197] + "..."
        lines.append(line)
    return "\n".join(lines)


def _section(title: str) -> None:
    width = 66
    print()
    print("─" * width)
    print(f"  {title}")
    print("─" * width)


async def _call(session, tool_name: str, arguments: dict) -> dict:
    """Call a tool and return the parsed JSON result."""
    print(f"\n  → calling tool: {tool_name}")
    print(f"    args: {json.dumps(arguments, default=str)}")
    result = await session.call_tool(tool_name, arguments=arguments)
    raw = result.content[0].text if result.content else "{}"
    return json.loads(raw)


def _parse_line(line: str) -> tuple[str, dict] | None:
    """Parse a shortcut command into (tool_name, arguments).  Returns None for meta-commands."""
    parts = line.strip().split(None, 2)
    if not parts:
        return None
    cmd = parts[0].lower()

    if cmd in ("quit", "exit"):
        raise SystemExit(0)

    if cmd == "help":
        print(HELP)
        return None

    if cmd == "tools":
        return "__list_tools__", {}

    if cmd == "schema":
        if len(parts) == 1:
            return "get_schema", {}
        return "get_schema", {"table_names": [parts[1]]}

    if cmd == "query":
        if len(parts) < 3:
            print("  Usage: query <SID> <KQL>")
            return None
        sid = parts[1]
        kql = parts[2]
        return "execute_query", {
            "kql": kql,
            "sid": sid,
            "analysis_type": "short_dumps",
            "timespan_hours": 24,
        }

    if cmd == "rca":
        if len(parts) < 2:
            print("  Usage: rca <SID> [hours]")
            return None
        sid = parts[1]
        hours = int(parts[2]) if len(parts) >= 3 else 24
        return "run_full_rca", {"sid": sid, "time_range_hours": hours}

    if cmd == "call":
        if len(parts) < 3:
            print("  Usage: call <tool_name> <json_args>")
            return None
        tool = parts[1]
        try:
            args = json.loads(parts[2])
        except json.JSONDecodeError as e:
            print(f"  Invalid JSON: {e}")
            return None
        return tool, args

    print(f"  Unknown command '{cmd}'. Type 'help' for options.")
    return None


async def main(url: str) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    print(f"\nConnecting to: {url}")

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tool_names = [t.name for t in tools_response.tools]

            _section(f"Connected  —  {len(tool_names)} tool(s) available")
            for name in tool_names:
                print(f"    • {name}")
            print(HELP)

            while True:
                try:
                    line = input("mcp> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    break

                if not line:
                    continue

                parsed = _parse_line(line)
                if parsed is None:
                    continue

                tool_name, arguments = parsed

                if tool_name == "__list_tools__":
                    _section("Available tools")
                    for t in tools_response.tools:
                        print(f"  {t.name}")
                        if t.description:
                            desc_lines = textwrap.wrap(t.description.split("\n")[0], width=60)
                            for dl in desc_lines:
                                print(f"      {dl}")
                    continue

                try:
                    result = await _call(session, tool_name, arguments)
                    _section(f"Result — {tool_name}")
                    print(_pretty(result))
                except Exception as exc:
                    print(f"\n  ERROR: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive MCP test client")
    parser.add_argument("--url", default=DEFAULT_URL, help="MCP server URL")
    args = parser.parse_args()
    asyncio.run(main(args.url))

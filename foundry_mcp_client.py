"""AI Foundry + MCP integration — new Responses API (azure-ai-projects >= 2.0.0).

Connects the AMS-MCP-RCAAgent AI Foundry agent to the SAP RCA MCP server tools.
Uses the new agent_reference + function-calling pattern (no threads/runs).

How it works:
  1. MCP client starts server.py as a subprocess and discovers the 4 tools
  2. Tools are converted to OpenAI function-calling format
  3. openai.responses.create() is called with agent_reference + tools
  4. When the agent calls a tool, this client executes it via MCP
  5. Tool output is submitted back; polling continues until response is complete

Agent details:
  Project  : padmaja-ams-rca
  Endpoint : https://padmaja-ams-rca-resource.services.ai.azure.com/api/projects/padmaja-ams-rca
  Agent    : AMS-MCP-RCAAgent  (name = ID in new API — no GUID needed)

Install dependencies (once):
    pip install "azure-ai-projects>=2.0.0" azure-identity mcp
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from time import sleep

from azure.identity import DefaultAzureCredential

# ── Configuration ─────────────────────────────────────────────────────────────
FOUNDRY_ENDPOINT = "https://padmaja-ams-rca-resource.services.ai.azure.com/api/projects/padmaja-ams-rca"
AGENT_NAME       = "AMS-MCP-RCAAgent"   # name = identifier in new API — no GUID needed
AGENT_MODEL      = "gpt-4.1"            # from agent definition (list_versions)

# System instructions injected at call time (agent definition has blank instructions)
SYSTEM_INSTRUCTIONS = (
    "You are an SAP observability assistant. "
    "Workflow: (1) Call get_schema to learn table structures and column names. "
    "(2) Write a KQL query and call execute_query to run it against Log Analytics. "
    "(3) Call deeper_rca_analysis to apply SAP domain knowledge and classify findings. "
    "For a complete automated investigation, call run_full_rca — it executes all "
    "steps and returns a structured report. Never modify data — all queries must be read-only."
)

SERVER_PY = Path(__file__).parent / "server.py"


# ── MCP helpers ───────────────────────────────────────────────────────────────

async def _get_mcp_tools_as_functions() -> list[dict]:
    """Discover MCP tools and return them in OpenAI function-calling format."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PY)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [
                {
                    "type":        "function",
                    "name":        t.name,
                    "description": t.description,
                    "parameters":  t.inputSchema,
                }
                for t in tools.tools
            ]


async def _call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Start server.py as a subprocess, call one tool, return result as JSON string."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PY)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text if result.content else "{}"


# ── AI Foundry agent runner (new Responses API) ────────────────────────────────

def run_agent_with_mcp_tools(user_message: str, max_polls: int = 60) -> str:
    """Send a message to AMS-MCP-RCAAgent with the 4 MCP tools available.

    Uses the new azure-ai-projects >= 2.0.0 Responses API:
      - openai.responses.create() with model, instructions, and function tools inline
      - Tool call outputs submitted via a new responses.create() with previous_response_id
      - NOTE: agent_reference is NOT used — tools cannot be passed when agent_reference is set

    Args:
        user_message: The question or task for the agent.
        max_polls:    Maximum number of 2-second polls before giving up (default 60 = 2 min).

    Returns:
        The agent's final text response.
    """
    from azure.ai.projects import AIProjectClient

    # Discover MCP tools
    mcp_tools = asyncio.run(_get_mcp_tools_as_functions())
    print(f"MCP tools loaded ({len(mcp_tools)}): {[t['name'] for t in mcp_tools]}")

    project = AIProjectClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())
    openai  = project.get_openai_client()

    # Call the model directly with MCP tools + system prompt
    # (agent_reference cannot be combined with custom tools in this API version)
    print(f"Sending to model [{AGENT_MODEL}] with {len(mcp_tools)} MCP tools...")
    response = openai.responses.create(
        model=AGENT_MODEL,
        instructions=SYSTEM_INSTRUCTIONS,
        input=user_message,
        tools=mcp_tools,
        background=True,
    )
    print(f"Response ID: {response.id}  Status: {response.status}")

    # Agentic loop — poll and handle tool calls
    for poll in range(max_polls):
        if response.status == "completed":
            break
        if response.status in ("failed", "cancelled", "expired"):
            return f"Response {response.status}: {getattr(response, 'error', '')}"

        # Poll for updates
        sleep(2)
        response = openai.responses.retrieve(response.id)
        print(f"  [{poll+1}] Status: {response.status}")

        # Collect any function_call output items and execute them via MCP
        tool_outputs = []
        for item in getattr(response, "output", []):
            if getattr(item, "type", "") == "function_call":
                fn_name = item.name
                fn_args = json.loads(item.arguments)
                print(f"  → Tool call: {fn_name}({list(fn_args.keys())})")
                result_text = asyncio.run(_call_mcp_tool(fn_name, fn_args))
                tool_outputs.append({
                    "type":    "function_call_output",
                    "call_id": item.call_id,
                    "output":  result_text,
                })

        if tool_outputs:
            # Submit results as input to a new response, chained via previous_response_id
            response = openai.responses.create(
                model=AGENT_MODEL,
                instructions=SYSTEM_INSTRUCTIONS,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=mcp_tools,
                background=True,
            )
            print(f"  Tool outputs submitted → new response ID: {response.id}  Status: {response.status}")

    if response.status != "completed":
        return f"Response did not complete. Final status: {response.status}"

    return response.output_text


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("AI Foundry + MCP Integration — AMS-MCP-RCAAgent")
    print("=" * 60)
    print(f"Agent   : {AGENT_NAME}")
    print(f"Endpoint: {FOUNDRY_ENDPOINT}")
    print()

    # ── Choose a prompt to test ────────────────────────────────────────────────
    # Test 1: schema only (no LA query — fastest test)
    # prompt = "What SAP tables are available in your MCP tools? List them with their analysis types."

    # Test 2: dynamic KQL generation (model writes KQL → execute_query hits live LA)
    prompt = (
        "Using the SAP RCA MCP tools, query SapNetweaver_ShortDumps_CL for SID=CHA "
        "in the last 4 hours and show me the top 5 runtime errors by count."
    )

    # Test 3: full analysis chain (Tools 1 + 2 + 3) — uncomment to use
    # prompt = (
    #     "There are ABAP short dumps on SID CHA. Use the SAP RCA tools to query the last "
    #     "4 hours of short dump data, classify the findings, and give me recommendations."
    # )

    # Test 4: automated RCA using pre-built KQL templates (run_full_rca tool)
    # prompt = "Run a full root cause analysis for SID=CHA for the last 4 hours."

    print(f"PROMPT: {prompt}")
    print("-" * 60)
    result = run_agent_with_mcp_tools(prompt)
    print("\nRESPONSE:")
    print(result)


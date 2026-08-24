"""Create a new-style (Responses API) agent in AI Foundry and attach the MCP server.

New-style agents support MCP tools natively, unlike classic (Assistants API) agents.

Target project:
  Endpoint : https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092

MCP Server:
  URL      : https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp

Usage:
    python MCP/create-new-agent-with-mcp.py
"""
import json
import requests
from azure.identity import DefaultAzureCredential

# ── Configuration ─────────────────────────────────────────────────────────────
FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
API_VERSION      = "2025-05-15-preview"

AGENT_NAME       = "Padm-SecureMCP-New"
MODEL            = "gpt-5.1"

MCP_SERVER_URL   = "https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp"

SYSTEM_INSTRUCTIONS = (
    "You are an SAP observability assistant. "
    "Workflow: (1) Call get_schema to learn table structures and column names. "
    "(2) Write a KQL query and call execute_query to run it against Log Analytics. "
    "(3) Call deeper_rca_analysis to apply SAP domain knowledge and classify findings. "
    "For a complete automated investigation, call run_full_rca — it executes all "
    "steps and returns a structured report. Never modify data — all queries must be read-only."
)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Creating new Responses API agent: '{AGENT_NAME}'")
    print(f"  Foundry endpoint : {FOUNDRY_ENDPOINT}")
    print(f"  Model            : {MODEL}")
    print(f"  MCP Server URL   : {MCP_SERVER_URL}")
    print()

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Define the MCP tool
    mcp_tool = {
        "type": "mcp",
        "server_label": "sap_rca_mcp",
        "server_url": MCP_SERVER_URL,
        "allowed_tools": [
            "get_schema",
            "execute_query",
            "deeper_rca_analysis",
            "run_full_rca",
        ],
    }

    # Create a new agent via /assistants endpoint (supports MCP tools)
    url = f"{FOUNDRY_ENDPOINT}/assistants?api-version={API_VERSION}"
    payload = {
        "name": AGENT_NAME,
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool],
    }

    print(f"POST {url}")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code in (200, 201):
        agent = resp.json()
        print("\nAgent created successfully!")
        print(f"  Name    : {agent.get('name')}")
        print(f"  ID      : {agent.get('id')}")
        print(f"  Model   : {agent.get('model')}")
        tools = agent.get("tools", [])
        print(f"  Tools   : {[t.get('type') for t in tools]}")
        print()
        print("MCP server tools available to the agent:")
        print("  - get_schema          : Discover table structures")
        print("  - execute_query       : Run KQL queries against Log Analytics")
        print("  - deeper_rca_analysis : Apply SAP domain classification")
        print("  - run_full_rca        : Complete automated investigation")
    else:
        print(f"\nFailed! Status: {resp.status_code}")
        error = resp.text[:1500]
        print(error)

        # If /agents endpoint not found, try alternate approach
        if resp.status_code == 404 or "not found" in error.lower():
            print("\nTrying /assistants endpoint with response_format...")
            create_via_assistants(headers, mcp_tool)


def create_via_assistants(headers: dict, mcp_tool: dict) -> None:
    """Fallback: create via /assistants with metadata to mark as new-style."""
    url = f"{FOUNDRY_ENDPOINT}/assistants?api-version={API_VERSION}"
    payload = {
        "name": AGENT_NAME,
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool],
        "metadata": {"agent_type": "responses"},
    }

    print(f"POST {url}")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code in (200, 201):
        agent = resp.json()
        print("\nAgent created successfully!")
        print(f"  Name    : {agent.get('name')}")
        print(f"  ID      : {agent.get('id')}")
        print(f"  Model   : {agent.get('model')}")
        tools = agent.get("tools", [])
        print(f"  Tools   : {[t.get('type') for t in tools]}")
    else:
        print(f"\nFailed! Status: {resp.status_code}")
        print(resp.text[:1500])


if __name__ == "__main__":
    main()

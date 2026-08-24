"""Connect the Azure-hosted MCP server to the Padm-SecureMCP agent in AI Foundry.

Target project:
  Endpoint : https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092
  Agent    : Padm-SecureMCP (asst_fUx8TtrVgaWW4ktrslJhiE4Q)

MCP Server:
  URL      : https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp

Usage:
    python MCP/connect-mcp-to-securemcp.py

Prerequisites:
    pip install azure-identity requests
    az login  (DefaultAzureCredential must have access to the Foundry project)
"""
import json
import requests
from azure.identity import DefaultAzureCredential

# ── Configuration ─────────────────────────────────────────────────────────────
FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
AGENT_ID         = "asst_fUx8TtrVgaWW4ktrslJhiE4Q"
AGENT_NAME       = "Padm-SecureMCP"
API_VERSION      = "2025-05-15-preview"

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
    print(f"Connecting MCP server to agent '{AGENT_NAME}'")
    print(f"  Foundry endpoint : {FOUNDRY_ENDPOINT}")
    print(f"  Agent ID         : {AGENT_ID}")
    print(f"  MCP Server URL   : {MCP_SERVER_URL}")
    print()

    # Get auth token for AI Foundry
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

    # Update the agent via REST API
    url = f"{FOUNDRY_ENDPOINT}/assistants/{AGENT_ID}?api-version={API_VERSION}"
    payload = {
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool],
    }

    print(f"Updating agent at: {url}")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        agent = resp.json()
        print("\nAgent updated successfully!")
        print(f"  Name  : {agent.get('name')}")
        print(f"  ID    : {agent.get('id')}")
        print(f"  Model : {agent.get('model')}")
        tools = agent.get("tools", [])
        print(f"  Tools : {[t.get('type') for t in tools]}")
        print()
        print("The agent can now call the MCP server tools:")
        print("  - get_schema          : Discover table structures")
        print("  - execute_query       : Run KQL queries against Log Analytics")
        print("  - deeper_rca_analysis : Apply SAP domain classification")
        print("  - run_full_rca        : Complete automated investigation")
    else:
        print(f"\nFailed! Status: {resp.status_code}")
        print(resp.text[:1500])


if __name__ == "__main__":
    main()

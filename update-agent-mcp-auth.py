"""Update the Padm-SecureMCP-New agent with an auth header for the Entra-protected MCP server.

The container app requires a Bearer token with audience: api://c113e212-b251-4101-a4f1-373bf14ff051
This script:
  1. Acquires a token for the container app's audience via DefaultAzureCredential
  2. Updates the agent's MCP tool with the Authorization header

NOTE: Tokens expire (~1h). Re-run this script to refresh.
      For a permanent solution, consider using Foundry connections or managed identity.

Usage:
    python MCP/update-agent-mcp-auth.py
"""
import json
import requests
from azure.identity import DefaultAzureCredential

# ── Configuration ─────────────────────────────────────────────────────────────
FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
AGENT_ID         = "asst_xafDfYmpv7PBX5NmlKfTwpeb"
API_VERSION      = "2025-05-15-preview"

MCP_SERVER_URL   = "https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp"

# Container app Entra audience
CONTAINER_APP_AUDIENCE = "api://c113e212-b251-4101-a4f1-373bf14ff051"

SYSTEM_INSTRUCTIONS = (
    "You are an SAP observability assistant. "
    "Workflow: (1) Call get_schema to learn table structures and column names. "
    "(2) Write a KQL query and call execute_query to run it against Log Analytics. "
    "(3) Call deeper_rca_analysis to apply SAP domain knowledge and classify findings. "
    "For a complete automated investigation, call run_full_rca — it executes all "
    "steps and returns a structured report. Never modify data — all queries must be read-only."
)


def main() -> None:
    credential = DefaultAzureCredential()

    # Step 1: Get a token for the container app's Entra audience
    print(f"Acquiring token for audience: {CONTAINER_APP_AUDIENCE}")
    mcp_token = credential.get_token(f"{CONTAINER_APP_AUDIENCE}/.default").token
    print(f"  Token acquired (length={len(mcp_token)})")

    # Step 2: Get a token for AI Foundry API
    foundry_token = credential.get_token("https://ai.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {foundry_token}",
        "Content-Type": "application/json",
    }

    # Step 3: Try updating with 'headers' field in MCP tool
    mcp_tool_with_headers = {
        "type": "mcp",
        "server_label": "sap_rca_mcp",
        "server_url": MCP_SERVER_URL,
        "headers": {
            "Authorization": f"Bearer {mcp_token}",
        },
        "allowed_tools": [
            "get_schema",
            "execute_query",
            "deeper_rca_analysis",
            "run_full_rca",
        ],
    }

    url = f"{FOUNDRY_ENDPOINT}/assistants/{AGENT_ID}?api-version={API_VERSION}"
    payload = {
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool_with_headers],
    }

    print(f"\nUpdating agent with MCP tool + auth headers...")
    print(f"  POST {url}")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        agent = resp.json()
        tools = agent.get("tools", [])
        # Check if headers were accepted
        has_headers = any(t.get("headers") for t in tools if t.get("type") == "mcp")
        print(f"\nAgent updated successfully!")
        print(f"  Name    : {agent.get('name')}")
        print(f"  ID      : {agent.get('id')}")
        print(f"  Model   : {agent.get('model')}")
        print(f"  Tools   : {[t.get('type') for t in tools]}")
        print(f"  Headers : {'Yes - auth token attached' if has_headers else 'Check in portal'}")
        print(f"\nThe agent should now authenticate to the MCP server via Entra.")
        print(f"NOTE: Token expires in ~1h. Re-run this script to refresh.")
        return

    print(f"\n'headers' field failed (status {resp.status_code}):")
    print(resp.text[:500])

    # Fallback: try 'authorization' field
    print("\nTrying 'authorization' field instead...")
    mcp_tool_with_auth = {
        "type": "mcp",
        "server_label": "sap_rca_mcp",
        "server_url": MCP_SERVER_URL,
        "authorization": f"Bearer {mcp_token}",
        "allowed_tools": [
            "get_schema",
            "execute_query",
            "deeper_rca_analysis",
            "run_full_rca",
        ],
    }

    payload["tools"] = [mcp_tool_with_auth]
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        agent = resp.json()
        print(f"\nAgent updated successfully with 'authorization' field!")
        print(f"  Name  : {agent.get('name')}")
        print(f"  ID    : {agent.get('id')}")
        print(f"  Model : {agent.get('model')}")
        print(f"  Tools : {[t.get('type') for t in agent.get('tools', [])]}")
        print(f"\nNOTE: Token expires in ~1h. Re-run this script to refresh.")
    else:
        print(f"\n'authorization' field also failed (status {resp.status_code}):")
        print(resp.text[:500])


if __name__ == "__main__":
    main()

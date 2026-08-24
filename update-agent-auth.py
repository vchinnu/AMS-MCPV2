"""Update the Padm-SecureMCP-New agent's MCP tool with auth headers for the Entra-protected container app."""
import requests
from azure.identity import DefaultAzureCredential
from pathlib import Path

FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
AGENT_ID         = "asst_xafDfYmpv7PBX5NmlKfTwpeb"
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

def main() -> None:
    # Read the token for the container app
    token_file = Path(__file__).parent / ".tmp_token.txt"
    mcp_token = token_file.read_text().strip()
    print(f"MCP auth token length: {len(mcp_token)}")

    # Get Foundry auth token
    credential = DefaultAzureCredential()
    foundry_token = credential.get_token("https://ai.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {foundry_token}",
        "Content-Type": "application/json",
    }

    # MCP tool with auth for the Entra-protected container app
    mcp_tool = {
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

    url = f"{FOUNDRY_ENDPOINT}/assistants/{AGENT_ID}?api-version={API_VERSION}"
    payload = {
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool],
    }

    print(f"Updating agent {AGENT_ID} with auth headers...")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        agent = resp.json()
        print("\nAgent updated successfully!")
        print(f"  Name  : {agent.get('name')}")
        print(f"  ID    : {agent.get('id')}")
        print(f"  Model : {agent.get('model')}")
        tools = agent.get("tools", [])
        print(f"  Tools : {[t.get('type') for t in tools]}")
        has_headers = any("headers" in t for t in tools if t.get("type") == "mcp")
        print(f"  Auth  : {'headers configured' if has_headers else 'no headers'}")
        print("\nThe agent can now authenticate to the MCP server.")
        print("NOTE: Token expires in ~1 hour. Re-run this script to refresh.")
    else:
        print(f"\nFailed! Status: {resp.status_code}")
        print(resp.text[:1500])


if __name__ == "__main__":
    main()

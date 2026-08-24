"""Update Padm-SecureMCP-New agent with auth using the azure-ai-projects SDK.

The SDK (v2.4.0) natively supports MCPTool with headers/authorization fields
and may use a newer API version that accepts them.
"""
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool

FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
AGENT_ID         = "asst_xafDfYmpv7PBX5NmlKfTwpeb"
MCP_SERVER_URL   = "https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp"
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

    # Get token for the container app
    print(f"Acquiring token for: {CONTAINER_APP_AUDIENCE}")
    mcp_token = credential.get_token(f"{CONTAINER_APP_AUDIENCE}/.default").token
    print(f"  Token acquired (length={len(mcp_token)})")

    project = AIProjectClient(
        endpoint=FOUNDRY_ENDPOINT,
        credential=credential,
    )

    # Check what API version the SDK uses
    print(f"\nSDK version: {project.__class__.__module__}")

    # Try with headers
    print("\nAttempt 1: MCPTool with headers...")
    try:
        mcp_tool = MCPTool(
            server_label="sap_rca_mcp",
            server_url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {mcp_token}"},
            allowed_tools=["get_schema", "execute_query", "deeper_rca_analysis", "run_full_rca"],
        )
        print(f"  MCPTool created. Serialized keys: {list(mcp_tool.as_dict().keys()) if hasattr(mcp_tool, 'as_dict') else 'N/A'}")

        # Use the OpenAI client to update the assistant
        client = project.get_openai_client()
        agent = client.beta.assistants.update(
            assistant_id=AGENT_ID,
            instructions=SYSTEM_INSTRUCTIONS,
            tools=[mcp_tool.as_dict() if hasattr(mcp_tool, 'as_dict') else {"type": "mcp", "server_label": "sap_rca_mcp", "server_url": MCP_SERVER_URL, "headers": {"Authorization": f"Bearer {mcp_token}"}, "allowed_tools": ["get_schema", "execute_query", "deeper_rca_analysis", "run_full_rca"]}],
        )
        print(f"\nAgent updated successfully!")
        print(f"  Name  : {agent.name}")
        print(f"  ID    : {agent.id}")
        print(f"  Tools : {[t.type for t in agent.tools]}")
        return
    except Exception as e:
        print(f"  Failed: {e}")

    # Try with authorization field
    print("\nAttempt 2: MCPTool with authorization...")
    try:
        mcp_tool = MCPTool(
            server_label="sap_rca_mcp",
            server_url=MCP_SERVER_URL,
            authorization=f"Bearer {mcp_token}",
            allowed_tools=["get_schema", "execute_query", "deeper_rca_analysis", "run_full_rca"],
        )

        client = project.get_openai_client()
        agent = client.beta.assistants.update(
            assistant_id=AGENT_ID,
            instructions=SYSTEM_INSTRUCTIONS,
            tools=[mcp_tool.as_dict() if hasattr(mcp_tool, 'as_dict') else {}],
        )
        print(f"\nAgent updated successfully!")
        print(f"  Name  : {agent.name}")
        print(f"  ID    : {agent.id}")
        print(f"  Tools : {[t.type for t in agent.tools]}")
        return
    except Exception as e:
        print(f"  Failed: {e}")

    # Attempt 3: Direct REST with newer API version
    print("\nAttempt 3: REST API with 2025-06-01-preview...")
    import requests
    foundry_token = credential.get_token("https://ai.azure.com/.default").token
    for api_ver in ["2025-06-01-preview", "2025-07-01-preview", "2025-08-01-preview"]:
        url = f"{FOUNDRY_ENDPOINT}/assistants/{AGENT_ID}?api-version={api_ver}"
        payload = {
            "instructions": SYSTEM_INSTRUCTIONS,
            "tools": [{
                "type": "mcp",
                "server_label": "sap_rca_mcp",
                "server_url": MCP_SERVER_URL,
                "headers": {"Authorization": f"Bearer {mcp_token}"},
                "allowed_tools": ["get_schema", "execute_query", "deeper_rca_analysis", "run_full_rca"],
            }],
        }
        resp = requests.post(url, headers={"Authorization": f"Bearer {foundry_token}", "Content-Type": "application/json"}, json=payload)
        if resp.status_code == 200:
            agent = resp.json()
            print(f"\nSuccess with api-version={api_ver}!")
            print(f"  Name  : {agent.get('name')}")
            print(f"  ID    : {agent.get('id')}")
            print(f"  Tools : {[t.get('type') for t in agent.get('tools', [])]}")
            return
        else:
            err = resp.json().get("error", {}).get("message", resp.text[:200])
            print(f"  {api_ver}: {resp.status_code} — {err}")

    print("\nNo API version supports headers on MCP tools yet.")
    print("Alternative: Use the Foundry 'Connections' feature to configure auth.")


if __name__ == "__main__":
    main()

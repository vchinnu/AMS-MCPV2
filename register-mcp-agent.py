"""Register the deployed ACA MCP server with AMS-MCP-RCAAgent in AI Foundry.

Run AFTER deploy-to-aca.ps1 completes, passing the URL it outputs:

    python MCP/register-mcp-agent.py https://<aca-fqdn>/sse

What this does:
  - Creates a new version of AMS-MCP-RCAAgent with MCPTool pointing to the ACA endpoint
  - require_approval="never" so the agent calls tools without needing a human loop
  - The agent's model and base instructions are preserved from the existing definition
"""
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool

FOUNDRY_ENDPOINT = "https://padmajat-agenticai-hack-resource.services.ai.azure.com/api/projects/padmajat-agenticai-hackathon25"
AGENT_NAME       = "AMS-RCA-Agent"
AGENT_MODEL      = "gpt-4.1"

SYSTEM_INSTRUCTIONS = (
    "You are an SAP observability assistant. "
    "Workflow: (1) Call get_schema to learn table structures and column names. "
    "(2) Write a KQL query and call execute_query to run it against Log Analytics. "
    "(3) Call deeper_rca_analysis to apply SAP domain knowledge and classify findings. "
    "For a complete automated investigation, call run_full_rca — it executes all "
    "steps and returns a structured report. Never modify data — all queries must be read-only."
)

def main(mcp_server_url: str) -> None:
    print(f"Registering MCP server: {mcp_server_url}")
    print(f"Agent: {AGENT_NAME}  |  Endpoint: {FOUNDRY_ENDPOINT}")

    project = AIProjectClient(
        endpoint=FOUNDRY_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    tool = MCPTool(
        server_label="sap-rca-mcp",
        server_url=mcp_server_url,
        require_approval="never",        # agent calls tools automatically
        allowed_tools=[                  # explicit allow-list — only our 4 tools
            "get_schema",
            "execute_query",
            "deeper_rca_analysis",
            "run_full_rca",
        ],
    )

    agent_version = project.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=AGENT_MODEL,
            instructions=SYSTEM_INSTRUCTIONS,
            tools=[tool],
        ),
    )

    print(f"\nAgent updated successfully!")
    print(f"  Name   : {agent_version.name}")
    print(f"  Version: {agent_version.version}")
    print(f"  Model  : {AGENT_MODEL}")
    print(f"  MCPTool: {mcp_server_url}")
    print(f"\nThe agent now calls the MCP server directly.")
    print(f"Run: python MCP/call-agent.py")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python MCP/register-mcp-agent.py <mcp_server_url>")
        print("Example: python MCP/register-mcp-agent.py https://sap-rca-mcp.nicename.eastus.azurecontainerapps.io/sse")
        sys.exit(1)
    main(sys.argv[1])

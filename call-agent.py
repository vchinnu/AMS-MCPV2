"""Call AMS-MCP-RCAAgent after the MCP server is registered on the agent.

The agent handles the full MCP tool call cycle internally.
This script just sends a prompt and prints the final answer.

Usage:
    python MCP/call-agent.py
    python MCP/call-agent.py "Run a full RCA for SID=CHA for the last 4 hours"
"""
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

FOUNDRY_ENDPOINT = "https://padmaja-ams-rca-resource.services.ai.azure.com/api/projects/padmaja-ams-rca"
AGENT_NAME       = "AMS-MCP-RCAAgent"

def ask(user_message: str) -> str:
    project = AIProjectClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())
    openai  = project.get_openai_client()

    response = openai.responses.create(
        input=user_message,
        extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
    )
    return response.output_text

if __name__ == "__main__":
    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Run a full root cause analysis for SID=CHA for the last 4 hours."
    )

    print(f"PROMPT: {prompt}\n")
    print(ask(prompt))

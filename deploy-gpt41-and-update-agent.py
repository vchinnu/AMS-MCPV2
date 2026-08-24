"""Deploy gpt-4.1 model and update Padm-SecureMCP agent to use it for MCP compatibility.

The gpt-5 model on classic agents doesn't support MCP tools.
This script deploys gpt-4.1 and switches the agent to use it.
"""
import requests
import time
from azure.identity import DefaultAzureCredential

# ── Configuration ─────────────────────────────────────────────────────────────
SUBSCRIPTION_ID  = "af80180c-8e32-4a4b-9b29-1b703343f5de"
RESOURCE_GROUP   = "rg-shukp-6092"
ACCOUNT_NAME     = "shukp-6092-resource"
FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
AGENT_ID         = "asst_fUx8TtrVgaWW4ktrslJhiE4Q"

DEPLOYMENT_NAME  = "gpt-41"
MODEL_NAME       = "gpt-4.1"
MODEL_VERSION    = "2025-04-14"
SKU_CAPACITY     = 10  # tokens-per-minute in thousands

MCP_SERVER_URL   = "https://sap-ams-mcp.politebeach-12eb8693.northeurope.azurecontainerapps.io/mcp"

SYSTEM_INSTRUCTIONS = (
    "You are an SAP observability assistant. "
    "Workflow: (1) Call get_schema to learn table structures and column names. "
    "(2) Write a KQL query and call execute_query to run it against Log Analytics. "
    "(3) Call deeper_rca_analysis to apply SAP domain knowledge and classify findings. "
    "For a complete automated investigation, call run_full_rca — it executes all "
    "steps and returns a structured report. Never modify data — all queries must be read-only."
)


def get_tokens():
    """Get tokens for both ARM and AI Foundry APIs."""
    credential = DefaultAzureCredential()
    arm_token = credential.get_token("https://management.azure.com/.default").token
    ai_token = credential.get_token("https://ai.azure.com/.default").token
    return arm_token, ai_token


def deploy_model(arm_token: str) -> None:
    """Deploy gpt-4.1 via ARM API."""
    url = (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT_NAME}"
        f"/deployments/{DEPLOYMENT_NAME}?api-version=2024-10-01"
    )

    payload = {
        "sku": {
            "name": "GlobalStandard",
            "capacity": SKU_CAPACITY,
        },
        "properties": {
            "model": {
                "format": "OpenAI",
                "name": MODEL_NAME,
                "version": MODEL_VERSION,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {arm_token}",
        "Content-Type": "application/json",
    }

    print(f"Deploying model '{MODEL_NAME}' as '{DEPLOYMENT_NAME}'...")
    resp = requests.put(url, headers=headers, json=payload)

    if resp.status_code in (200, 201):
        print(f"  Deployment created/updated successfully (status {resp.status_code})")
        # Wait for provisioning
        data = resp.json()
        state = data.get("properties", {}).get("provisioningState", "Unknown")
        print(f"  Provisioning state: {state}")
        if state not in ("Succeeded", "Running"):
            print("  Waiting for deployment to complete...")
            for _ in range(30):
                time.sleep(10)
                check = requests.get(url, headers=headers)
                if check.status_code == 200:
                    state = check.json().get("properties", {}).get("provisioningState", "Unknown")
                    print(f"  State: {state}")
                    if state == "Succeeded":
                        break
    elif resp.status_code == 409:
        print(f"  Deployment '{DEPLOYMENT_NAME}' already exists — proceeding to agent update.")
    else:
        print(f"  Failed! Status: {resp.status_code}")
        print(f"  {resp.text[:800]}")
        raise SystemExit(1)


def update_agent(ai_token: str) -> None:
    """Update agent to use gpt-4.1 deployment with MCP tool."""
    url = f"{FOUNDRY_ENDPOINT}/assistants/{AGENT_ID}?api-version=2025-05-15-preview"

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

    payload = {
        "model": DEPLOYMENT_NAME,
        "instructions": SYSTEM_INSTRUCTIONS,
        "tools": [mcp_tool],
    }

    headers = {
        "Authorization": f"Bearer {ai_token}",
        "Content-Type": "application/json",
    }

    print(f"\nUpdating agent to use '{DEPLOYMENT_NAME}' with MCP tool...")
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        agent = resp.json()
        print("\nAgent updated successfully!")
        print(f"  Name  : {agent.get('name')}")
        print(f"  ID    : {agent.get('id')}")
        print(f"  Model : {agent.get('model')}")
        tools = agent.get("tools", [])
        print(f"  Tools : {[t.get('type') for t in tools]}")
    else:
        print(f"\nAgent update failed! Status: {resp.status_code}")
        print(resp.text[:1000])


def main():
    arm_token, ai_token = get_tokens()

    # Step 1: Deploy gpt-4.1
    deploy_model(arm_token)

    # Step 2: Update agent to use gpt-4.1 + MCP
    update_agent(ai_token)

    print("\n" + "=" * 60)
    print("Done! Test in the Agents playground with a prompt like:")
    print('  "Can you list SAP systems and their health?"')
    print("=" * 60)


if __name__ == "__main__":
    main()

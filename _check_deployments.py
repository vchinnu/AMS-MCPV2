"""Check available model deployments in the Foundry project and create a Responses API agent with MCP."""
import json
import requests
from azure.identity import DefaultAzureCredential

FOUNDRY_ENDPOINT = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
API_VERSION = "2025-05-15-preview"

token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# List available deployments
print("=== Available Model Deployments ===")
url = f"{FOUNDRY_ENDPOINT}/deployments?api-version={API_VERSION}"
resp = requests.get(url, headers=headers)
if resp.status_code == 200:
    for d in resp.json().get("data", []):
        print(f"  {d.get('id')}: model={d.get('model')}, status={d.get('status')}")
else:
    print(f"  Could not list deployments: {resp.status_code}")
    print(f"  {resp.text[:300]}")

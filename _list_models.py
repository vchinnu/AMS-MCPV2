"""List existing deployments and find available versions for gpt-4.1."""
import requests
from azure.identity import DefaultAzureCredential

SUBSCRIPTION_ID = "af80180c-8e32-4a4b-9b29-1b703343f5de"
RESOURCE_GROUP  = "rg-shukp-6092"
ACCOUNT_NAME    = "shukp-6092-resource"

token = DefaultAzureCredential().get_token("https://management.azure.com/.default").token
headers = {"Authorization": f"Bearer {token}"}

# List existing deployments
print("=== Existing Deployments ===")
url = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
    f"/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT_NAME}"
    f"/deployments?api-version=2024-10-01"
)
resp = requests.get(url, headers=headers)
if resp.status_code == 200:
    for d in resp.json().get("value", []):
        name = d.get("name")
        model = d.get("properties", {}).get("model", {})
        state = d.get("properties", {}).get("provisioningState", "")
        sku = d.get("sku", {})
        print(f"  {name:25s} model={model.get('name', '?'):15s} ver={model.get('version', '?'):15s} sku={sku.get('name', '?')} state={state}")
else:
    print(f"  Failed: {resp.status_code}")

# List available model versions for gpt-4.1 in eastus2
print("\n=== Available gpt-4.1 versions (eastus2) ===")
url2 = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
    f"/providers/Microsoft.CognitiveServices/locations/eastus2"
    f"/models?api-version=2024-10-01"
)
resp2 = requests.get(url2, headers=headers)
if resp2.status_code == 200:
    for m in resp2.json().get("value", []):
        model = m.get("model", m)
        name = model.get("name", "")
        if name == "gpt-4.1":
            skus = model.get("skus", m.get("skus", []))
            version = model.get("version", "")
            lifecycle = model.get("lifecycleStatus", "")
            print(f"  {name} version={version} lifecycle={lifecycle} skus={[s.get('name') for s in skus]}")
else:
    print(f"  Location models failed: {resp2.status_code}, {resp2.text[:300]}")

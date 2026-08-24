import requests
from azure.identity import DefaultAzureCredential

token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
endpoint = "https://shukp-6092-resource.services.ai.azure.com/api/projects/shukp-6092"
url = f"{endpoint}/assistants/asst_fUx8TtrVgaWW4ktrslJhiE4Q?api-version=2025-05-15-preview"
resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
if resp.status_code == 200:
    import json
    data = resp.json()
    print(json.dumps({"name": data.get("name"), "model": data.get("model"), "tools": data.get("tools")}, indent=2))
else:
    print(f"Status: {resp.status_code}")
    print(resp.text[:500])

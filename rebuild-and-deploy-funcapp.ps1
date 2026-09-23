$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Building image in ACR ==="
# --no-logs: the CLI log streamer crashes on cp1252 consoles and aborts the script
# before the (still running) remote build finishes, causing a restart onto a stale image.
az acr build `
    --registry amsmcpserveracr `
    --image sap-rca-mcp-funcapp:latest `
    --file Dockerfile.funcapp `
    --no-logs `
    . -o json

Write-Host ""
Write-Host "=== ACR pull identity config on the Function App ==="
az functionapp show --name "sap-ams-mcp-funcapp" --resource-group "AMS-HATest" `
    --query "{acrMI:siteConfig.acrUseManagedIdentityCreds, image:siteConfig.linuxFxVersion}" -o json

Write-Host ""
Write-Host "=== Restarting Function App ==="
az functionapp restart --name "sap-ams-mcp-funcapp" --resource-group "AMS-HATest" -o none
Write-Host "restarted"

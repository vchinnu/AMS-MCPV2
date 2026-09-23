#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Redeploy the SAP RCA MCP Server code/image to the existing Function App.

.DESCRIPTION
    Use this for ongoing code changes (e.g. server.py, tools/, analyzers/) once the
    Function App infrastructure is already provisioned (see deploy-to-funcapp.ps1 for
    the one-time infra setup: storage, VNet, RBAC, Entra app registration, EasyAuth).

    This script deliberately does NOT touch VNet integration, RBAC, Entra app
    registration, or EasyAuth settings — re-running those risks reverting manual
    fixes (e.g. EasyAuth allowedApplications, AzureWebJobsFeatureFlags).

    Steps:
      1. Build & push the Docker image via ACR Tasks.
      2. Refresh ACR admin credentials on the Function App (these can go stale and
         cause "ImagePullUnauthorizedFailure").
      3. Ensure AzureWebJobsFeatureFlags=EnableWorkerIndexing is set (required for the
         Python v2 / function_app.py programming model to be indexed in a container).
      4. Restart the Function App and confirm the function registers.
      5. Smoke-test the endpoint (expect 401 — confirms EasyAuth is reachable).

.NOTES
    Prerequisites: az CLI logged in with access to the subscription below.
#>

param(
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# ── Variables ────────────────────────────────────────────────────────────────
$SUBSCRIPTION   = "2b331373-3d36-4585-bdb9-d3364786e775"
$RESOURCE_GROUP = "AMS-HATest"
$ACR_NAME       = "amsmcpserveracr"
$IMAGE_NAME     = "sap-rca-mcp-funcapp"
$FUNC_APP_NAME  = "sap-ams-mcp-funcapp"

az config set core.no_color=true --only-show-errors | Out-Null

Write-Host "`n=== Step 0: Setting subscription ===" -ForegroundColor Cyan
az account set --subscription $SUBSCRIPTION

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Build and push Docker image to ACR
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 1: Building image via ACR Tasks (${IMAGE_NAME}:${ImageTag}) ===" -ForegroundColor Cyan

# --no-logs avoids a known az CLI console-encoding crash when streaming build logs
# on Windows terminals (colorama/cp1252 UnicodeEncodeError on certain pip output).
az acr build `
    --registry $ACR_NAME `
    --image "${IMAGE_NAME}:${ImageTag}" `
    --file Dockerfile.funcapp `
    --no-logs `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: ACR build failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Image built and pushed: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${ImageTag}" -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Refresh ACR registry credentials on the Function App
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 2: Refreshing ACR credentials on Function App ===" -ForegroundColor Cyan

az acr update --name $ACR_NAME --admin-enabled true --only-show-errors -o none
$acrCreds = az acr credential show --name $ACR_NAME -o json | ConvertFrom-Json

az functionapp config appsettings set `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --settings `
        "DOCKER_REGISTRY_SERVER_URL=https://${ACR_NAME}.azurecr.io" `
        "DOCKER_REGISTRY_SERVER_USERNAME=$($acrCreds.username)" `
        "DOCKER_REGISTRY_SERVER_PASSWORD=$($acrCreds.passwords[0].value)" `
    --only-show-errors `
    --output none

Write-Host "  ACR credentials refreshed." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Ensure required runtime app settings are present
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 3: Ensuring required app settings ===" -ForegroundColor Cyan

az functionapp config appsettings set `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --settings `
        "AzureWebJobsFeatureFlags=EnableWorkerIndexing" `
        "FUNCTIONS_WORKER_RUNTIME=python" `
    --only-show-errors `
    --output none

Write-Host "  Required app settings confirmed." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Restart and verify function registration
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 4: Restarting Function App ===" -ForegroundColor Cyan
az functionapp restart --name $FUNC_APP_NAME --resource-group $RESOURCE_GROUP --only-show-errors

$funcCount = 0
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 6
    $functions = az functionapp function list --name $FUNC_APP_NAME --resource-group $RESOURCE_GROUP -o json | ConvertFrom-Json
    $funcCount = @($functions).Count
    if ($funcCount -gt 0) { break }
    Write-Host "  Waiting for function indexing... (attempt $($i + 1)/10)" -ForegroundColor Yellow
}

if ($funcCount -eq 0) {
    Write-Host "ERROR: No functions registered after restart. Check container logs:" -ForegroundColor Red
    Write-Host "  az webapp log tail --name $FUNC_APP_NAME --resource-group $RESOURCE_GROUP" -ForegroundColor Gray
    exit 1
}
Write-Host "  Function registered: $($functions[0].name)" -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Smoke test — expect 401 (confirms EasyAuth is reachable and enforcing)
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 5: Smoke-testing endpoint ===" -ForegroundColor Cyan
$FUNC_URL = az functionapp show --name $FUNC_APP_NAME --resource-group $RESOURCE_GROUP --query "defaultHostName" -o tsv
try {
    $resp = Invoke-WebRequest -Uri "https://${FUNC_URL}/mcp" -Method GET -SkipHttpErrorCheck
    Write-Host "  GET /mcp -> $($resp.StatusCode) (expected 401 = EasyAuth enforcing correctly)" -ForegroundColor $(if ($resp.StatusCode -eq 401) { "Green" } else { "Yellow" })
} catch {
    Write-Host "  Smoke test request failed: $_" -ForegroundColor Yellow
}

Write-Host "`n═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Deployment complete: https://${FUNC_URL}/mcp" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green

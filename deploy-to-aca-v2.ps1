#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the SAP RCA MCP server V2 (Enterprise/Token-Optimized) to Azure Container Apps.

.DESCRIPTION
    Deploys the NEW enterprise MCP server as a SEPARATE Container App (sap-ams-mcp-v2)
    in the same resource group and Container Apps Environment as the original (sap-ams-mcp).
    Both can run side-by-side — changes to one do NOT affect the other.

    1. Reuses existing ACR (amsmcpserveracr) — pushes a distinct image tag
    2. Reuses existing Container Apps Environment (ams-mcp-rca-env)
    3. Creates a NEW Container App: sap-ams-mcp-v2
    4. Creates a NEW User-Assigned Managed Identity for v2
    5. Assigns Log Analytics Reader role
    6. Outputs the public HTTPS URL

.NOTES
    Run once to create. Re-run to update the image (creates a new revision).
    Prerequisites: az CLI logged in.

    Old server:  sap-ams-mcp     (POC — untouched by this script)
    New server:  sap-ams-mcp-v2  (Enterprise — deployed by this script)
#>

# ── Variables ────────────────────────────────────────────────────────────────
$SUBSCRIPTION    = "2b331373-3d36-4585-bdb9-d3364786e775"
$RESOURCE_GROUP  = "PADM_AMS_RCA"
$LOCATION        = "northeurope"

# Shared resources (already exist from v1 deployment)
$ACR_NAME        = "amsmcpserveracr"
$ACA_ENV_NAME    = "ams-mcp-rca-env"
$ACA_LOGS_WS     = "ams-mcp-rca-aca-logs"

# V2-specific resources
$IMAGE_NAME      = "sap-rca-mcp-server-v2"
$IMAGE_TAG       = "latest"
$ACA_APP_NAME    = "sap-ams-mcp-v2"
$UAMI_NAME       = "sap-rca-mcp-v2-uami"

# The Log Analytics workspace the MCP server queries (SAP monitoring data)
$LA_WORKSPACE_ID      = "8af591cf-7b56-422b-a1d9-701c90b2721a"
$LA_WORKSPACE_RESOURCE_ID = "/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourcegroups/mrg_padm-ams-ha-test-monitor/providers/microsoft.operationalinsights/workspaces/sapmon-laws-d44c1e41d7949a"

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT
# ══════════════════════════════════════════════════════════════════════════════

# ── Set subscription ──────────────────────────────────────────────────────────
Write-Host "`n=== Setting subscription ===" -ForegroundColor Cyan
az account set --subscription $SUBSCRIPTION

# ── Ensure ACR exists (idempotent) ────────────────────────────────────────────
Write-Host "`n=== Ensuring ACR exists: $ACR_NAME ===" -ForegroundColor Cyan
az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME `
    --sku Basic `
    --admin-enabled true `
    --location $LOCATION `
    --output none 2>$null

# ── Build + push V2 image via ACR Tasks ───────────────────────────────────────
Write-Host "`n=== Building and pushing V2 image via ACR Tasks ===" -ForegroundColor Cyan
Write-Host "  Image: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}" -ForegroundColor Yellow
az acr build `
    --registry $ACR_NAME `
    --image "${IMAGE_NAME}:${IMAGE_TAG}" `
    --file Dockerfile.v2 `
    .

# ── Ensure Container Apps Environment exists ──────────────────────────────────
Write-Host "`n=== Checking Container Apps Environment: $ACA_ENV_NAME ===" -ForegroundColor Cyan
$envExists = az containerapp env show `
    --name $ACA_ENV_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "name" -o tsv 2>$null

if (-not $envExists) {
    Write-Host "Environment not found — creating..." -ForegroundColor Yellow

    $ACA_WS_ID  = az monitor log-analytics workspace show `
        --resource-group $RESOURCE_GROUP `
        --workspace-name $ACA_LOGS_WS `
        --query "customerId" -o tsv

    $ACA_WS_KEY = az monitor log-analytics workspace get-shared-keys `
        --resource-group $RESOURCE_GROUP `
        --workspace-name $ACA_LOGS_WS `
        --query "primarySharedKey" -o tsv

    az containerapp env create `
        --name $ACA_ENV_NAME `
        --resource-group $RESOURCE_GROUP `
        --location $LOCATION `
        --logs-workspace-id $ACA_WS_ID `
        --logs-workspace-key $ACA_WS_KEY `
        --output none
    Write-Host "Environment created."
} else {
    Write-Host "Environment already exists, reusing."
}

# ── Create User-Assigned Managed Identity for V2 ─────────────────────────────
Write-Host "`n=== Creating Managed Identity: $UAMI_NAME ===" -ForegroundColor Cyan
az identity create `
    --resource-group $RESOURCE_GROUP `
    --name $UAMI_NAME `
    --location $LOCATION `
    --output none 2>$null

$UAMI_ID = az identity show `
    --resource-group $RESOURCE_GROUP `
    --name $UAMI_NAME `
    --query "id" -o tsv

$UAMI_CLIENT_ID = az identity show `
    --resource-group $RESOURCE_GROUP `
    --name $UAMI_NAME `
    --query "clientId" -o tsv

$UAMI_PRINCIPAL_ID = az identity show `
    --resource-group $RESOURCE_GROUP `
    --name $UAMI_NAME `
    --query "principalId" -o tsv

Write-Host "  UAMI Client ID:    $UAMI_CLIENT_ID"
Write-Host "  UAMI Principal ID: $UAMI_PRINCIPAL_ID"

# ── Assign Log Analytics Reader role to V2 identity ───────────────────────────
Write-Host "`n=== Assigning Log Analytics Reader role ===" -ForegroundColor Cyan
$roleExists = az role assignment list `
    --assignee $UAMI_PRINCIPAL_ID `
    --role "Log Analytics Reader" `
    --scope $LA_WORKSPACE_RESOURCE_ID `
    --query "[0].id" -o tsv 2>$null

if (-not $roleExists) {
    az role assignment create `
        --assignee $UAMI_PRINCIPAL_ID `
        --role "Log Analytics Reader" `
        --scope $LA_WORKSPACE_RESOURCE_ID `
        --output none
    Write-Host "Role assigned."
} else {
    Write-Host "Role already assigned, skipping."
}

# ── Grant ACR Pull to V2 identity ────────────────────────────────────────────
Write-Host "`n=== Granting ACR Pull permission ===" -ForegroundColor Cyan
$ACR_ID = az acr show --name $ACR_NAME --query "id" -o tsv
az role assignment create `
    --assignee $UAMI_PRINCIPAL_ID `
    --role "AcrPull" `
    --scope $ACR_ID `
    --output none 2>$null
Write-Host "ACR Pull granted."

# ── Get ACR login server ──────────────────────────────────────────────────────
$ACR_LOGIN_SERVER = az acr show `
    --name $ACR_NAME `
    --query "loginServer" -o tsv

$FULL_IMAGE = "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
Write-Host "`n  Full image path: $FULL_IMAGE" -ForegroundColor Yellow

# ── Deploy Container App (create or update) ───────────────────────────────────
Write-Host "`n=== Deploying Container App: $ACA_APP_NAME ===" -ForegroundColor Cyan

$appExists = az containerapp show `
    --name $ACA_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "name" -o tsv 2>$null

if (-not $appExists) {
    az containerapp create `
        --name $ACA_APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --environment $ACA_ENV_NAME `
        --image $FULL_IMAGE `
        --registry-server $ACR_LOGIN_SERVER `
        --registry-identity $UAMI_ID `
        --user-assigned $UAMI_ID `
        --target-port 8000 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 3 `
        --cpu 0.5 `
        --memory 1Gi `
        --env-vars `
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID=$LA_WORKSPACE_ID" `
            "AZURE_CLIENT_ID=$UAMI_CLIENT_ID" `
            "DEFAULT_SID=CHA" `
            "MAX_QUERY_ROWS=1000" `
            "DEFAULT_TIMESPAN_HOURS=24" `
            "QUERY_TIMEOUT_SECONDS=90" `
            "CACHE_TTL_SECONDS=300" `
            "CACHE_MAX_ENTRIES=50" `
        --output none
    Write-Host "Container App created." -ForegroundColor Green
} else {
    $revisionSuffix = (Get-Date -Format 'yyyyMMddHHmm')
    az containerapp update `
        --name $ACA_APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image $FULL_IMAGE `
        --revision-suffix $revisionSuffix `
        --output none
    Write-Host "Container App updated (revision: $revisionSuffix)." -ForegroundColor Green
}

# ── Get the public URL ────────────────────────────────────────────────────────
$MCP_URL = az containerapp show `
    --name $ACA_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "`n" -NoNewline
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host " MCP Server V2 (Enterprise) deployed successfully!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host " App Name    : $ACA_APP_NAME"
Write-Host " Public URL  : https://$MCP_URL"
Write-Host " SSE endpoint: https://$MCP_URL/sse"
Write-Host " MCP endpoint: https://$MCP_URL/mcp"
Write-Host ""
Write-Host " Identity    : $UAMI_NAME ($UAMI_CLIENT_ID)"
Write-Host ""
Write-Host " Old server (untouched): sap-ams-mcp"
Write-Host " New server (this one) : $ACA_APP_NAME"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test: curl https://$MCP_URL/sse"
Write-Host "  2. Register with Foundry Agent: update server_url to https://$MCP_URL/sse"
Write-Host "  3. Or use in VS Code .vscode/mcp.json with type=sse and url above"

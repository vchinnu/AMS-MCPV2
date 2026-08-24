#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the SAP RCA MCP server to Azure Container Apps.

.DESCRIPTION
    1. Creates ACR, builds + pushes the Docker image
    2. Creates a Container Apps Environment + Container App
    3. Assigns Managed Identity the Log Analytics Reader role
    4. Outputs the public HTTPS URL (use as MCPTool server_url)

.NOTES
    Run once. Re-run to update the image (it will update the existing app).
    Prerequisites: az CLI logged in, Docker Desktop running.
#>

# ── Variables ────────────────────────────────────────────────────────────────
$SUBSCRIPTION    = "2b331373-3d36-4585-bdb9-d3364786e775"
$RESOURCE_GROUP  = "PADM_AMS_RCA"
$LOCATION        = "northeurope"

$ACR_NAME        = "amsmcpserveracr"       # must be globally unique, lowercase, no hyphens
$IMAGE_NAME      = "sap-rca-mcp-server"
$IMAGE_TAG       = "latest"

$ACA_ENV_NAME    = "ams-mcp-rca-env"
$ACA_APP_NAME    = "sap-ams-mcp"
$ACA_LOGS_WS     = "ams-mcp-rca-aca-logs"      # LA workspace for ACA container logs only

# The Log Analytics workspace the MCP server queries (in a separate RG)
$LA_WORKSPACE_ID      = "8af591cf-7b56-422b-a1d9-701c90b2721a"
$LA_WORKSPACE_RESOURCE_ID = "/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourcegroups/mrg_padm-ams-ha-test-monitor/providers/microsoft.operationalinsights/workspaces/sapmon-laws-d44c1e41d7949a"

# ── Set subscription ──────────────────────────────────────────────────────────
Write-Host "`n=== Setting subscription ===" -ForegroundColor Cyan
az account set --subscription $SUBSCRIPTION

# ── Create ACR ───────────────────────────────────────────────────────────────
Write-Host "`n=== Creating Azure Container Registry: $ACR_NAME ===" -ForegroundColor Cyan
az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME `
    --sku Basic `
    --admin-enabled true `
    --location $LOCATION `
    --output none

# ── Build + push image via ACR Tasks (no local Docker needed) ─────────────────
Write-Host "`n=== Building and pushing image via ACR Tasks ===" -ForegroundColor Cyan
az acr build `
    --registry $ACR_NAME `
    --image "${IMAGE_NAME}:${IMAGE_TAG}" `
    --file MCP\Dockerfile `
    MCP\

# ── Create LA workspace for ACA container logs ────────────────────────────────
Write-Host "`n=== Creating LA workspace for ACA logs: $ACA_LOGS_WS ===" -ForegroundColor Cyan
az monitor log-analytics workspace create `
    --resource-group $RESOURCE_GROUP `
    --workspace-name $ACA_LOGS_WS `
    --location $LOCATION `
    --retention-time 30 `
    --output none

$ACA_WS_ID  = az monitor log-analytics workspace show `
    --resource-group $RESOURCE_GROUP `
    --workspace-name $ACA_LOGS_WS `
    --query "customerId" -o tsv

$ACA_WS_KEY = az monitor log-analytics workspace get-shared-keys `
    --resource-group $RESOURCE_GROUP `
    --workspace-name $ACA_LOGS_WS `
    --query "primarySharedKey" -o tsv

# ── Create Container Apps Environment ────────────────────────────────────────
Write-Host "`n=== Creating Container Apps Environment: $ACA_ENV_NAME ===" -ForegroundColor Cyan
$envExists = az containerapp env show `
    --name $ACA_ENV_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "name" -o tsv 2>$null

if (-not $envExists) {
    az containerapp env create `
        --name $ACA_ENV_NAME `
        --resource-group $RESOURCE_GROUP `
        --location $LOCATION `
        --logs-workspace-id $ACA_WS_ID `
        --logs-workspace-key $ACA_WS_KEY `
        --output none
    Write-Host "Environment created."
} else {
    Write-Host "Environment already exists, skipping."
}

# ── Get ACR login server ──────────────────────────────────────────────────────
$ACR_LOGIN_SERVER = az acr show `
    --name $ACR_NAME `
    --query "loginServer" -o tsv

$FULL_IMAGE = "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
Write-Host "Image: $FULL_IMAGE"

# ── Create / update Container App ─────────────────────────────────────────────
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
        --registry-identity system `
        --target-port 8000 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 3 `
        --cpu 0.5 `
        --memory 1Gi `
        --system-assigned `
        --env-vars `
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID=$LA_WORKSPACE_ID" `
            "DEFAULT_SID=CHA" `
            "MAX_QUERY_ROWS=1000" `
            "QUERY_TIMEOUT_SECONDS=90" `
        --output none
    Write-Host "Container App created."
} else {
    # Use a unique --revision-suffix based on timestamp to force ACA to create a new
    # revision and pull the freshly-pushed image. Without this, ACA may keep running
    # the old container even though the 'latest' tag now points to a newer digest.
    $revisionSuffix = (Get-Date -Format 'yyyyMMddHHmm')
    az containerapp update `
        --name $ACA_APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image $FULL_IMAGE `
        --revision-suffix $revisionSuffix `
        --output none
    Write-Host "Container App updated (revision suffix: $revisionSuffix)."
}

# ── Assign Managed Identity the Log Analytics Reader role ─────────────────────
Write-Host "`n=== Assigning Log Analytics Reader role to Managed Identity ===" -ForegroundColor Cyan

$PRINCIPAL_ID = az containerapp show `
    --name $ACA_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "identity.principalId" -o tsv

$LA_RESOURCE_ID = $LA_WORKSPACE_RESOURCE_ID

# Check if role already assigned
$roleExists = az role assignment list `
    --assignee $PRINCIPAL_ID `
    --role "Log Analytics Reader" `
    --scope $LA_RESOURCE_ID `
    --query "[0].id" -o tsv 2>$null

if (-not $roleExists) {
    az role assignment create `
        --assignee $PRINCIPAL_ID `
        --role "Log Analytics Reader" `
        --scope $LA_RESOURCE_ID `
        --output none
    Write-Host "Role assigned."
} else {
    Write-Host "Role already assigned, skipping."
}

# ── Also grant ACR pull permission to the managed identity ───────────────────
Write-Host "`n=== Granting ACR pull permission ===" -ForegroundColor Cyan
$ACR_ID = az acr show --name $ACR_NAME --query "id" -o tsv
az role assignment create `
    --assignee $PRINCIPAL_ID `
    --role "AcrPull" `
    --scope $ACR_ID `
    --output none 2>$null

# ── Get the public URL ────────────────────────────────────────────────────────
$MCP_URL = az containerapp show `
    --name $ACA_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "MCP Server deployed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Public URL : https://$MCP_URL"
Write-Host "SSE path   : https://$MCP_URL/sse"
Write-Host ""
Write-Host "Next: run register-mcp-agent.py with server_url = https://$MCP_URL/sse"
Write-Host "============================================================" -ForegroundColor Green

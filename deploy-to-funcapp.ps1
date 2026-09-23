#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the SAP RCA MCP Server as an Azure Function App (Docker container).

.DESCRIPTION
    Deploys the MCP server into the AMS-hosted resource group (not the managed RG),
    reusing the existing EP1 App Service Plan and VNet/subnet. The Function App runs
    under its own system-assigned managed identity, granted Log Analytics Reader only.

    1. Builds Docker image and pushes to ACR (amsmcpserveracr)
    2. Creates the Function App on the existing EP1 plan
    3. Configures the system-assigned identity, app settings, VNet integration
    4. Grants Log Analytics Reader to that identity on the AMS workspace
    5. Creates the Entra ID App Registration for the MCP server
    6. Enables EasyAuth (Entra ID authentication)
    7. Outputs the Function App URL

.NOTES
    Prerequisites: az CLI logged in, Docker not required (uses ACR Tasks).
    Rerun to update the image and app configuration.
#>

# ── Variables ────────────────────────────────────────────────────────────────
$SUBSCRIPTION    = "2b331373-3d36-4585-bdb9-d3364786e775"
$LOCATION        = "northeurope"

# AMS-hosted RG (where the monitor resource lives)
$RESOURCE_GROUP  = "AMS-HATest"

# Managed RG resources (reuse the App Service Plan only)
$MRG_NAME        = "MRG_PADM-AMS-HA-Test-Monitor"
$APP_SERVICE_PLAN = "sapmon-app-d44c1e41d7949a"

# The MCP Function App uses its OWN system-assigned managed identity (created in step 4),
# not the shared AMS user-assigned identity — least privilege, lifecycle bound to the app.

# LAWS (AMS Log Analytics Workspace)
$LAWS_WORKSPACE_ID = "8af591cf-7b56-422b-a1d9-701c90b2721a"
$LAWS_RESOURCE_ID  = "/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourcegroups/MRG_PADM-AMS-HA-Test-Monitor/providers/microsoft.operationalinsights/workspaces/sapmon-laws-d44c1e41d7949a"

# VNet/Subnet (same as existing AMS function apps)
$VNET_SUBNET_ID = "/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourceGroups/AMS-HATest/providers/Microsoft.Network/virtualNetworks/ams-padm-ams-ha-test-monitor-vnet/subnets/padm-ha-test-subnet"

# ACR (reuse from Container App deployment)
$ACR_NAME = "amsmcpserveracr"

# Function App
$FUNC_APP_NAME = "sap-ams-mcp-funcapp"
$IMAGE_NAME    = "sap-rca-mcp-funcapp"
$IMAGE_TAG     = "latest"

# Storage account for Function App (required by Azure Functions runtime)
$FUNC_STORAGE_NAME = "sapamsmcpfuncsa"

# Entra ID App Registration
$ENTRA_APP_NAME = "AMS-SAP-MCP-Server"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: Set subscription
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 0: Setting subscription ===" -ForegroundColor Cyan
az account set --subscription $SUBSCRIPTION

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Build and push Docker image to ACR
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 1: Building Docker image via ACR Tasks ===" -ForegroundColor Cyan

# Ensure ACR exists
az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME `
    --sku Basic `
    --admin-enabled true `
    --location $LOCATION `
    --output none 2>$null

Write-Host "  Image: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}" -ForegroundColor Yellow
az acr build `
    --registry $ACR_NAME `
    --image "${IMAGE_NAME}:${IMAGE_TAG}" `
    --file Dockerfile.funcapp `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: ACR build failed." -ForegroundColor Red
    exit 1
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Create Storage Account for Function App
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 2: Creating Storage Account for Function App ===" -ForegroundColor Cyan
az storage account create `
    --name $FUNC_STORAGE_NAME `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --sku Standard_LRS `
    --kind StorageV2 `
    --output none 2>$null

$STORAGE_CONN = az storage account show-connection-string `
    --name $FUNC_STORAGE_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "connectionString" -o tsv

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Create Function App (Docker container on existing EP1 plan)
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 3: Creating Function App ===" -ForegroundColor Cyan

$ACR_URL = "${ACR_NAME}.azurecr.io"
$FULL_IMAGE = "${ACR_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
$PLAN_ID = "/subscriptions/${SUBSCRIPTION}/resourceGroups/${MRG_NAME}/providers/Microsoft.Web/serverfarms/${APP_SERVICE_PLAN}"

# Get ACR credentials for function app to pull image
$ACR_USER = az acr credential show --name $ACR_NAME --query "username" -o tsv
$ACR_PASS = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

az functionapp create `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --storage-account $FUNC_STORAGE_NAME `
    --plan $PLAN_ID `
    --functions-version 4 `
    --os-type Linux `
    --runtime python `
    --runtime-version 3.11 `
    --deployment-container-image-name $FULL_IMAGE `
    --docker-registry-server-url "https://${ACR_URL}" `
    --docker-registry-server-user $ACR_USER `
    --docker-registry-server-password $ACR_PASS `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Function app creation failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Function App created: $FUNC_APP_NAME" -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Enable System-Assigned Managed Identity on the Function App
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 4: Enabling System-Assigned Managed Identity ===" -ForegroundColor Cyan

$MCP_PRINCIPAL_ID = az functionapp identity assign `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query "principalId" -o tsv

if (-not $MCP_PRINCIPAL_ID) {
    Write-Host "ERROR: Failed to create the system-assigned managed identity." -ForegroundColor Red
    exit 1
}
Write-Host "  System-assigned identity principal ID: $MCP_PRINCIPAL_ID" -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Configure App Settings
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 5: Configuring App Settings ===" -ForegroundColor Cyan
az functionapp config appsettings set `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --settings `
        "AZURE_LOG_ANALYTICS_WORKSPACE_ID=$LAWS_RESOURCE_ID" `
        "DEFAULT_SID=CHA" `
        "MAX_QUERY_ROWS=1000" `
        "DEFAULT_TIMESPAN_HOURS=24" `
        "QUERY_TIMEOUT_SECONDS=90" `
        "FUNCTIONS_WORKER_RUNTIME=python" `
        "AzureWebJobsStorage=$STORAGE_CONN" `
        "laws_arm_id=$LAWS_RESOURCE_ID" `
    --output none

# AZURE_CLIENT_ID is intentionally not set — with a system-assigned identity there is
# exactly one managed identity on the resource, so no disambiguation is needed.
Write-Host "  App settings configured." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: VNet Integration
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 6: Configuring VNet Integration ===" -ForegroundColor Cyan
az functionapp vnet-integration add `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --vnet "ams-padm-ams-ha-test-monitor-vnet" `
    --subnet "padm-ha-test-subnet" `
    --output none 2>$null

Write-Host "  VNet integration configured." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: RBAC — Log Analytics Reader for the Function App system-assigned identity
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 7: Assigning Log Analytics Reader RBAC ===" -ForegroundColor Cyan

# Log Analytics Reader role definition ID
$LA_READER_ROLE = "73c42c96-874c-492b-b04d-ab87d138a893"

az role assignment create `
    --assignee-object-id $MCP_PRINCIPAL_ID `
    --assignee-principal-type ServicePrincipal `
    --role $LA_READER_ROLE `
    --scope $LAWS_RESOURCE_ID `
    --output none 2>$null

Write-Host "  Log Analytics Reader granted to the MCP Function App identity on the LAWS." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Entra ID App Registration
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 8: Creating Entra ID App Registration ===" -ForegroundColor Cyan

# Check if app registration already exists
$EXISTING_APP_ID = az ad app list --display-name $ENTRA_APP_NAME --query "[0].appId" -o tsv 2>$null

if ($EXISTING_APP_ID) {
    Write-Host "  App registration already exists: $EXISTING_APP_ID" -ForegroundColor Yellow
    $MCP_APP_ID = $EXISTING_APP_ID
} else {
    # Create app registration with an app role for MCP tool invocation
    $roleId = [guid]::NewGuid().ToString()
    $appManifest = @"
{
  "displayName": "$ENTRA_APP_NAME",
  "signInAudience": "AzureADMyOrg",
  "appRoles": [{
    "allowedMemberTypes": ["Application"],
    "description": "Allows the application to invoke MCP tools on the SAP RCA server",
    "displayName": "MCP Tools Invoke",
    "id": "$roleId",
    "isEnabled": true,
    "value": "MCP.Tools.Invoke"
  }]
}
"@
    $manifestFile = Join-Path $env:TEMP "mcp-app-manifest.json"
    $appManifest | Out-File -Encoding utf8 $manifestFile

    $appResultJson = az rest --method POST `
        --uri "https://graph.microsoft.com/v1.0/applications" `
        --headers "Content-Type=application/json" `
        --body "@$manifestFile" `
        -o json
    $appResult = $appResultJson | ConvertFrom-Json
    $MCP_APP_ID = $appResult.appId
    $MCP_OBJECT_ID = $appResult.id
    Remove-Item $manifestFile -ErrorAction SilentlyContinue

    # Create a service principal for the app registration
    az ad sp create --id $MCP_APP_ID --output none 2>$null

    # Set the identifier URI
    az ad app update --id $MCP_APP_ID --identifier-uris "api://$MCP_APP_ID" --output none

    Write-Host "  App registration created: $MCP_APP_ID" -ForegroundColor Green
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: Enable EasyAuth (Entra ID) on Function App
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 9: Enabling Entra ID EasyAuth ===" -ForegroundColor Cyan

$TENANT_ID = az account show --query "tenantId" -o tsv

az webapp auth update `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --enabled true `
    --action Return401 `
    --aad-allowed-token-audiences "api://$MCP_APP_ID" `
    --aad-client-id $MCP_APP_ID `
    --aad-token-issuer-url "https://login.microsoftonline.com/$TENANT_ID/v2.0" `
    --output none

Write-Host "  EasyAuth enabled with Entra ID." -ForegroundColor Green
Write-Host "  App ID: $MCP_APP_ID" -ForegroundColor Green
Write-Host "  Audience: api://$MCP_APP_ID" -ForegroundColor Green
Write-Host "  Issuer: https://login.microsoftonline.com/$TENANT_ID/v2.0" -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: Configure HTTPS-only and security settings
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n=== Step 10: Security hardening ===" -ForegroundColor Cyan
az functionapp update `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --set httpsOnly=true `
    --output none

az functionapp config set `
    --name $FUNC_APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --ftps-state Disabled `
    --min-tls-version 1.2 `
    --output none

Write-Host "  HTTPS-only, FTPS disabled, TLS 1.2 minimum." -ForegroundColor Green

# ══════════════════════════════════════════════════════════════════════════════
# DONE — Output summary
# ══════════════════════════════════════════════════════════════════════════════
Write-Host "`n" -NoNewline
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  MCP Server Function App Deployment Complete" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green

$FUNC_URL = az functionapp show --name $FUNC_APP_NAME --resource-group $RESOURCE_GROUP --query "defaultHostName" -o tsv
Write-Host ""
Write-Host "  Function App:    $FUNC_APP_NAME" -ForegroundColor White
Write-Host "  URL:             https://$FUNC_URL" -ForegroundColor White
Write-Host "  MCP Endpoint:    https://${FUNC_URL}/mcp/" -ForegroundColor White
Write-Host "  Resource Group:  $RESOURCE_GROUP" -ForegroundColor White
Write-Host "  Plan:            EP1 (Elastic Premium)" -ForegroundColor White
Write-Host "  Identity:        System-Assigned MI ($MCP_PRINCIPAL_ID)" -ForegroundColor White
Write-Host "  LAWS role:       Log Analytics Reader" -ForegroundColor White
Write-Host "  Auth:            Entra ID (EasyAuth)" -ForegroundColor White
Write-Host "  Entra App ID:    $MCP_APP_ID" -ForegroundColor White
Write-Host "  VNet:            ams-padm-ams-ha-test-monitor-vnet/padm-ha-test-subnet" -ForegroundColor White
Write-Host ""
Write-Host "  To test with a bearer token:" -ForegroundColor Yellow
Write-Host "    `$token = az account get-access-token --resource api://$MCP_APP_ID --query accessToken -o tsv" -ForegroundColor Gray
Write-Host "    curl -H 'Authorization: Bearer `$token' https://${FUNC_URL}/mcp/" -ForegroundColor Gray
Write-Host ""

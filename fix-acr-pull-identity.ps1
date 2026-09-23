<#
Fixes ImagePullUnauthorizedFailure on sap-ams-mcp-funcapp.

ACR admin user is disabled, so the stored DOCKER_REGISTRY_SERVER_USERNAME/PASSWORD
no longer work. Switch the image pull to the app's user-assigned managed identity.
#>
$ErrorActionPreference = "Stop"

$APP      = "sap-ams-mcp-funcapp"
$RG       = "AMS-HATest"
$ACR_ID   = "/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourceGroups/PADM_AMS_RCA/providers/Microsoft.ContainerRegistry/registries/amsmcpserveracr"
$UAMI_PRINCIPAL = "0dd7e2d7-3a19-452d-856b-57e544fdb46e"
$UAMI_CLIENT    = "68432e03-9fbc-4fc8-97ee-1597ad33ecd4"

$siteCfg = "https://management.azure.com/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourceGroups/$RG/providers/Microsoft.Web/sites/$APP/config/web?api-version=2022-03-01"

Write-Host "Step 1: grant AcrPull to the function app's user-assigned identity"
$existing = az role assignment list --assignee $UAMI_PRINCIPAL --scope $ACR_ID --role AcrPull -o json | ConvertFrom-Json
if ($existing.Count -gt 0) {
    Write-Host "  already assigned"
} else {
    az role assignment create --assignee-object-id $UAMI_PRINCIPAL --assignee-principal-type ServicePrincipal `
        --role AcrPull --scope $ACR_ID -o none
    Write-Host "  assigned"
}

Write-Host "Step 2: point the site at that identity for image pull"
$body = @{
    properties = @{
        acrUseManagedIdentityCreds = $true
        acrUserManagedIdentityID   = $UAMI_CLIENT
    }
} | ConvertTo-Json -Depth 5
$f = Join-Path $env:TEMP "acr-mi.json"
$body | Out-File -FilePath $f -Encoding utf8
az rest --method PATCH --uri $siteCfg --body "@$f" -o none
Write-Host "  done"

Write-Host "Step 3: remove the dead admin credentials"
az functionapp config appsettings delete --name $APP --resource-group $RG `
    --setting-names DOCKER_REGISTRY_SERVER_USERNAME DOCKER_REGISTRY_SERVER_PASSWORD -o none
Write-Host "  removed"

Write-Host "Step 4: restart"
az functionapp restart --name $APP --resource-group $RG -o none

Write-Host ""
Write-Host "=== VERIFY ==="
az rest --method GET --uri $siteCfg --query "properties.{useMI:acrUseManagedIdentityCreds, miClientId:acrUserManagedIdentityID, image:linuxFxVersion}" -o json

<#
Wires the Foundry agent identity to the EasyAuth-protected MCP Function App.

  1. Adds app role  MCP.Tools.Invoke  to app registration  sap-ams-mcp-funcapp
  2. Assigns that role to the Foundry agent identity
  3. Adds the agent identity appId to EasyAuth allowedApplications
#>
$ErrorActionPreference = "Stop"

# --- MCP server (EasyAuth) ---
$MCP_APP_ID     = "c5ae8d46-57bf-4c81-a265-980dc8421c7d"
$MCP_APP_OBJID  = "0027ba8e-8735-4968-87fd-6a66839434ca"
$MCP_SP_OBJID   = "0449cfc0-f453-493c-b44e-2f968020691a"
$FUNCAPP_AUTH_URI = "https://management.azure.com/subscriptions/2b331373-3d36-4585-bdb9-d3364786e775/resourceGroups/AMS-HATest/providers/Microsoft.Web/sites/sap-ams-mcp-funcapp/config/authsettingsV2?api-version=2022-03-01"

# --- Foundry agent identity ---
$AGENT_IDENTITY_APPID = "febcd179-8a82-4a1e-b5b6-5eec7fe50286"

$ROLE_VALUE = "MCP.Tools.Invoke"

# ── Step 1: ensure the app role exists ───────────────────────────────────────
Write-Host "Step 1: ensuring app role '$ROLE_VALUE' on $MCP_APP_ID"
$app = az rest --method GET --url "https://graph.microsoft.com/v1.0/applications/$MCP_APP_OBJID" -o json | ConvertFrom-Json
$existing = @($app.appRoles) | Where-Object { $_.value -eq $ROLE_VALUE }

if ($existing) {
    $roleId = $existing.id
    Write-Host "  already exists: $roleId"
} else {
    $roleId = [guid]::NewGuid().ToString()
    $newRole = [ordered]@{
        id                 = $roleId
        allowedMemberTypes = @("Application")
        displayName        = "MCP Tools Invoke"
        description        = "Allows an application or agent identity to invoke SAP RCA MCP server tools."
        value              = $ROLE_VALUE
        isEnabled          = $true
    }
    $allRoles = @($app.appRoles) + $newRole
    $body = @{ appRoles = $allRoles } | ConvertTo-Json -Depth 10
    $f = Join-Path $env:TEMP "mcp-approles.json"
    $body | Out-File -FilePath $f -Encoding utf8
    az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/$MCP_APP_OBJID" `
        --headers "Content-Type=application/json" --body "@$f" -o none
    Write-Host "  created: $roleId"
    Start-Sleep -Seconds 10   # directory replication before the role can be assigned
}

# ── Step 2: assign the role to the agent identity ────────────────────────────
Write-Host "Step 2: assigning '$ROLE_VALUE' to agent identity $AGENT_IDENTITY_APPID"
$assigned = az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$MCP_SP_OBJID/appRoleAssignedTo" -o json | ConvertFrom-Json
$already = @($assigned.value) | Where-Object { $_.principalId -eq $AGENT_IDENTITY_APPID -and $_.appRoleId -eq $roleId }

if ($already) {
    Write-Host "  already assigned"
} else {
    $assignment = @{
        principalId = $AGENT_IDENTITY_APPID
        resourceId  = $MCP_SP_OBJID
        appRoleId   = $roleId
    } | ConvertTo-Json
    $f2 = Join-Path $env:TEMP "mcp-assignment.json"
    $assignment | Out-File -FilePath $f2 -Encoding utf8
    az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$MCP_SP_OBJID/appRoleAssignedTo" `
        --headers "Content-Type=application/json" --body "@$f2" -o none
    Write-Host "  assigned"
}

# ── Step 3: allow the agent identity through EasyAuth ────────────────────────
Write-Host "Step 3: adding agent identity to EasyAuth allowedApplications"
$auth = az rest --method GET --uri $FUNCAPP_AUTH_URI -o json | ConvertFrom-Json
$policy = $auth.properties.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy
$allowed = @($policy.allowedApplications)

if ($allowed -contains $AGENT_IDENTITY_APPID) {
    Write-Host "  already allowed"
} else {
    $policy.allowedApplications = $allowed + $AGENT_IDENTITY_APPID
    $put = @{ properties = $auth.properties } | ConvertTo-Json -Depth 30
    $f3 = Join-Path $env:TEMP "authv2-agent.json"
    $put | Out-File -FilePath $f3 -Encoding utf8
    az rest --method PUT --uri $FUNCAPP_AUTH_URI --body "@$f3" -o none
    Write-Host "  added"
}

# ── Verify ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== VERIFY ==="
$final = az rest --method GET --uri $FUNCAPP_AUTH_URI -o json | ConvertFrom-Json
Write-Host "audience           : $($final.properties.identityProviders.azureActiveDirectory.validation.allowedAudiences -join ', ')"
Write-Host "allowedApplications: $($final.properties.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy.allowedApplications -join ', ')"
$finalAssign = az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$MCP_SP_OBJID/appRoleAssignedTo" -o json | ConvertFrom-Json
foreach ($a in $finalAssign.value) {
    Write-Host "roleAssignment     : $($a.principalDisplayName) -> $($a.appRoleId)"
}
Write-Host "appRoleId          : $roleId"

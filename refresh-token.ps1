# Refresh the Log Analytics bearer token and update MCP/.env automatically.
# Run this script whenever queries fail with authentication/token errors.
#
# Usage:
#   .\MCP\refresh-token.ps1
#
# Requires: Azure CLI (az) with an existing session (az login not needed — uses cached refresh token).

$ErrorActionPreference = "Stop"
$envFile = Join-Path $PSScriptRoot ".env"

Write-Host "Fetching fresh Log Analytics token..." -ForegroundColor Cyan

try {
    $token = az account get-access-token --resource https://api.loganalytics.io --query accessToken -o tsv 2>&1
    if ($LASTEXITCODE -ne 0 -or $token -notlike "eyJ*") {
        throw "az account get-access-token failed: $token"
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: Could not obtain token." -ForegroundColor Red
    Write-Host "If 'az login' is blocked by Conditional Access, try using:" -ForegroundColor Yellow
    Write-Host "  az account get-access-token --resource https://api.loganalytics.io --query accessToken -o tsv" -ForegroundColor Yellow
    Write-Host "Then manually paste the token into AZURE_BEARER_TOKEN in MCP/.env" -ForegroundColor Yellow
    exit 1
}

# Decode expiry from JWT payload (middle segment)
$payload = ($token.Split('.')[1].PadRight(($token.Split('.')[1].Length + 3) -band -bnot 3, '='))
$decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($payload)) | ConvertFrom-Json
$expiresAt = [System.DateTimeOffset]::FromUnixTimeSeconds($decoded.exp).ToLocalTime()

# Update AZURE_BEARER_TOKEN line in .env
$envContent = Get-Content $envFile -Raw
if ($envContent -match "AZURE_BEARER_TOKEN=") {
    $envContent = $envContent -replace "AZURE_BEARER_TOKEN=.*", "AZURE_BEARER_TOKEN=$token"
} else {
    $envContent += "`nAZURE_BEARER_TOKEN=$token"
}
Set-Content $envFile -Value $envContent -NoNewline

Write-Host "Token updated in MCP/.env" -ForegroundColor Green
Write-Host "Expires at: $expiresAt (local time)" -ForegroundColor Green
Write-Host ""
Write-Host "Re-run this script before expiry or when you see authentication errors." -ForegroundColor Gray

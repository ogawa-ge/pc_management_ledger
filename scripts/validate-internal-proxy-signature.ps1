param(
    [Parameter(Mandatory = $true)][string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)][string]$ValidationId
)

$ErrorActionPreference = 'Stop'
Write-Output "ValidationId=$ValidationId"
Write-Output "Target=$ApiBaseUrl"
Write-Output 'Run the three gated stages: ECS accepts current+next, Lambda signs with next, ECS removes old.'
Write-Output 'For each stage record only status codes, keyId, request ID, and sanitized evidence references.'
Write-Output 'Verify missing, tampered, expired, unknown-key, and user-auth failures without logging signatures or secret values.'
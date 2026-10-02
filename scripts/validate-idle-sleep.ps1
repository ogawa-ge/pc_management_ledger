param(
    [string]$Region = 'ap-northeast-1',
    [string]$Cluster = 'PCManagementCluster',
    [string]$Service = 'PCManagementService',
    [string]$SystemActivityTable = 'SystemActivity',
    [Parameter(Mandatory = $true)][string]$TimeoutCheckFunctionName,
    [Parameter(Mandatory = $true)][string]$ValidationId
)

$ErrorActionPreference = 'Stop'
$backupPath = Join-Path $env:TEMP "ecs-idle-backup-$ValidationId.json"
function Format-PythonIsoUtc([DateTimeOffset]$Value) {
    return $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.ffffff+00:00')
}
aws dynamodb get-item --region $Region --table-name $SystemActivityTable `
    --key '{"entityId":{"S":"global"}}' --consistent-read | Out-File $backupPath -Encoding utf8

$cases = @(
    @{ Name = 'before-boundary'; OffsetSeconds = 7199; InFlight = 0 },
    @{ Name = 'at-boundary'; OffsetSeconds = 7200; InFlight = 0 },
    @{ Name = 'processing'; OffsetSeconds = 10800; InFlight = 1 }
)

try {
    foreach ($case in $cases) {
        $lastActivity = Format-PythonIsoUtc ([DateTimeOffset]::UtcNow.AddSeconds(-$case.OffsetSeconds))
        $item = @{
            entityId = @{ S = 'global' }
            runtimeState = @{ S = 'RUNNING' }
            generation = @{ N = '1' }
            inFlightCount = @{ N = [string]$case.InFlight }
            lastActivityAt = @{ S = $lastActivity }
            lastStateChangedAt = @{ S = Format-PythonIsoUtc ([DateTimeOffset]::UtcNow) }
        } | ConvertTo-Json -Compress -Depth 5
        aws dynamodb put-item --region $Region --table-name $SystemActivityTable --item $item | Out-Null
        $payloadPath = Join-Path $env:TEMP "ecs-idle-$($case.Name).json"
        aws lambda invoke --region $Region --function-name $TimeoutCheckFunctionName `
            --cli-binary-format raw-in-base64-out --payload '{}' $payloadPath | Out-Null
        $invokeResult = Get-Content $payloadPath -Raw | ConvertFrom-Json
        $resultBody = $invokeResult.body | ConvertFrom-Json
        Write-Output "Case=$($case.Name) Status=$($resultBody.status) Reason=$($resultBody.reason)"
        Remove-Item $payloadPath -Force
    }
} finally {
    $backup = Get-Content $backupPath -Raw | ConvertFrom-Json
    if ($backup.Item) {
        $restoreItem = $backup.Item | ConvertTo-Json -Compress -Depth 20
        aws dynamodb put-item --region $Region --table-name $SystemActivityTable --item $restoreItem | Out-Null
    } else {
        aws dynamodb delete-item --region $Region --table-name $SystemActivityTable `
            --key '{"entityId":{"S":"global"}}' | Out-Null
    }
    Remove-Item $backupPath -Force -ErrorAction SilentlyContinue
}

aws ecs describe-services --region $Region --cluster $Cluster --services $Service `
    --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
Write-Output "ValidationId=$ValidationId"
Write-Output '欠損・不正・未来時刻ケースも非本番の検証用項目だけで実行し、fail-open監査ログを確認してください。'
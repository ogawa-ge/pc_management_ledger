param(
    [Parameter(Mandatory = $true)][string]$ApiBaseUrl,
    [string]$Region = 'ap-northeast-1',
    [string]$Cluster = 'PCManagementCluster',
    [string]$Service = 'PCManagementService',
    [Parameter(Mandatory = $true)][string]$ValidationId,
    [Parameter(Mandatory = $true)][string]$Authorization
)

$ErrorActionPreference = 'Stop'
$endpoint = "$($ApiBaseUrl.TrimEnd('/'))/api/pcs"
$jobs = 1..10 | ForEach-Object {
    Start-Job -ScriptBlock {
        param($Endpoint, $Token, $Index)
        try {
            $headers = @{ Authorization = $Token; 'Idempotency-Key' = [guid]::NewGuid().ToString() }
            $response = Invoke-WebRequest -Uri $Endpoint -Headers $headers -Method Get -SkipHttpErrorCheck
            [pscustomobject]@{ Index = $Index; Status = $response.StatusCode }
        } catch {
            [pscustomobject]@{ Index = $Index; Status = 'ERROR'; ErrorType = $_.Exception.GetType().Name }
        }
    } -ArgumentList $endpoint, $Authorization, $_
}

$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job -Force
$results | Select-Object Index, Status, ErrorType

aws ecs describe-services --region $Region --cluster $Cluster --services $Service `
    --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'

Write-Output "ValidationId=$ValidationId"
Write-Output 'CloudTrailまたは安全なモック監査でUpdateService(desiredCount=1)が1回であることを別途確認してください。'
Write-Output 'Authorization値、署名、AWSアカウントID、実データは記録しないでください。'
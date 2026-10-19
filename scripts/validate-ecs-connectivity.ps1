param(
    [string]$Region = 'ap-northeast-1',
    [string]$Cluster = 'PCManagementCluster',
    [string]$Service = 'PCManagementService',
    [Parameter(Mandatory = $true)][string]$ValidationId
)

$ErrorActionPreference = 'Stop'
Write-Output "ValidationId=$ValidationId"
aws ecs describe-services --region $Region --cluster $Cluster --services $Service `
    --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,events:events[0:5]}'
Write-Output 'ECR pull and task start must be confirmed from sanitized ECS service events.'
Write-Output 'CloudWatch Logs, DynamoDB dummy read/write/delete, and Gemini dummy parsing must be executed with non-secret validation data.'
Write-Output 'Do not print API keys, Authorization headers, secret values, account IDs, or real PC data.'
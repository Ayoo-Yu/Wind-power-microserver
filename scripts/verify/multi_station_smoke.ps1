param(
    [string]$MainBaseUrl = "http://127.0.0.1:18080",
    [string]$AutoBaseUrl = "http://127.0.0.1:18081"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$failures = 0

function Assert-True {
    param(
        [string]$Name,
        [bool]$Condition,
        [string]$FailMessage
    )
    if ($Condition) {
        Write-Host "[PASS] $Name"
    } else {
        Write-Host "[FAIL] $Name - $FailMessage" -ForegroundColor Red
        $script:failures++
    }
}

function Invoke-JsonGet {
    param([string]$Url)
    $resp = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -TimeoutSec 8
    return @{
        StatusCode = [int]$resp.StatusCode
        Json = ($resp.Content | ConvertFrom-Json)
        Raw = $resp.Content
    }
}

function Invoke-JsonPost {
    param(
        [string]$Url,
        [hashtable]$Body
    )
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $Url -Body ($Body | ConvertTo-Json -Compress) -ContentType "application/json" -TimeoutSec 8
        return @{
            StatusCode = [int]$resp.StatusCode
            Raw = $resp.Content
        }
    } catch {
        if ($_.Exception.Response) {
            $response = $_.Exception.Response
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            return @{
                StatusCode = [int]$response.StatusCode.value__
                Raw = $reader.ReadToEnd()
            }
        }
        throw
    }
}

Write-Host "Multi-station smoke verification started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Main backend: $MainBaseUrl"
Write-Host "Auto backend: $AutoBaseUrl"
Write-Host ""

# 1) Main backend health
$mainHealth = Invoke-JsonGet -Url "$MainBaseUrl/api/v1/health"
Assert-True -Name "Main /api/v1/health status" -Condition ($mainHealth.StatusCode -eq 200) -FailMessage "HTTP $($mainHealth.StatusCode)"
Assert-True -Name "Main /api/v1/health payload" -Condition ($mainHealth.Json.code -eq 0) -FailMessage "Unexpected payload: $($mainHealth.Raw)"

# 2) Auto backend health
$autoHealth = Invoke-JsonGet -Url "$AutoBaseUrl/health"
Assert-True -Name "Auto /health status" -Condition ($autoHealth.StatusCode -eq 200) -FailMessage "HTTP $($autoHealth.StatusCode)"
Assert-True -Name "Auto /health payload" -Condition ($autoHealth.Json.status -eq "ok") -FailMessage "Unexpected payload: $($autoHealth.Raw)"

# 3) Farms list from main backend
$farmsResp = Invoke-JsonGet -Url "$MainBaseUrl/report/farms"
$isArray = $farmsResp.Json -is [System.Array]
Assert-True -Name "Main /report/farms status" -Condition ($farmsResp.StatusCode -eq 200) -FailMessage "HTTP $($farmsResp.StatusCode)"
Assert-True -Name "Main /report/farms payload is array" -Condition $isArray -FailMessage "Unexpected payload: $($farmsResp.Raw)"

$farmCode = "DEFAULT_FARM"
if ($isArray -and $farmsResp.Json.Count -gt 0 -and $farmsResp.Json[0].farm_code) {
    $farmCode = [string]$farmsResp.Json[0].farm_code
}
Write-Host "Using farm_code for checks: $farmCode"

# 4) Auto status with farm_code
$statusResp = Invoke-JsonGet -Url "$AutoBaseUrl/api/status?farm_code=$farmCode"
$hasFarmCode = $statusResp.Json.PSObject.Properties.Name -contains "farm_code"
Assert-True -Name "Auto /api/status status" -Condition ($statusResp.StatusCode -eq 200) -FailMessage "HTTP $($statusResp.StatusCode)"
Assert-True -Name "Auto /api/status envelope code" -Condition ($statusResp.Json.code -eq 0) -FailMessage "Payload: $($statusResp.Raw)"
Assert-True -Name "Auto /api/status contains farm_code" -Condition $hasFarmCode -FailMessage "Payload: $($statusResp.Raw)"

# 5) Invalid farm should be rejected
$invalidResp = Invoke-JsonPost -Url "$AutoBaseUrl/api/start" -Body @{
    type = "short"
    farm_code = "INVALID_FARM_123"
}
Assert-True -Name "Auto /api/start invalid farm returns 400" -Condition ($invalidResp.StatusCode -eq 400) -FailMessage "HTTP $($invalidResp.StatusCode), body=$($invalidResp.Raw)"

Write-Host ""
if ($failures -eq 0) {
    Write-Host "Multi-station smoke verification PASSED." -ForegroundColor Green
    exit 0
}

Write-Host "Multi-station smoke verification FAILED with $failures issue(s)." -ForegroundColor Red
exit 1

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

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Url
    )
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $Url -TimeoutSec 10
        return @{
            StatusCode = [int]$resp.StatusCode
            Raw = $resp.Content
            Json = ($resp.Content | ConvertFrom-Json)
        }
    } catch {
        if ($_.Exception.Response) {
            $response = $_.Exception.Response
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            $raw = $reader.ReadToEnd()
            if ([string]::IsNullOrWhiteSpace($raw)) {
                $tmp = [System.IO.Path]::GetTempFileName()
                try {
                    $status = curl.exe -s -o $tmp -w "%{http_code}" -X $Method $Url
                    $raw = Get-Content $tmp -Raw
                    return @{
                        StatusCode = [int]$status
                        Raw = $raw
                        Json = $(try { $raw | ConvertFrom-Json } catch { $null })
                    }
                } finally {
                    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
                }
            }
            $json = $null
            try {
                $json = ($raw | ConvertFrom-Json)
            } catch {}
            return @{
                StatusCode = [int]$response.StatusCode.value__
                Raw = $raw
                Json = $json
            }
        }
        throw
    }
}

function Assert-Envelope {
    param(
        [string]$Name,
        [hashtable]$Resp
    )
    $hasCode = $Resp.Json -and ($Resp.Json.PSObject.Properties.Name -contains "code")
    $hasMessage = $Resp.Json -and ($Resp.Json.PSObject.Properties.Name -contains "message")
    $hasData = $Resp.Json -and ($Resp.Json.PSObject.Properties.Name -contains "data")
    Assert-True -Name "$Name envelope has code" -Condition $hasCode -FailMessage "body=$($Resp.Raw)"
    Assert-True -Name "$Name envelope has message" -Condition $hasMessage -FailMessage "body=$($Resp.Raw)"
    Assert-True -Name "$Name envelope has data" -Condition $hasData -FailMessage "body=$($Resp.Raw)"
}

Write-Host "API contract smoke verification started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Main backend: $MainBaseUrl"
Write-Host "Auto backend: $AutoBaseUrl"
Write-Host ""

# 1) Main v1 health envelope
$mainV1Health = Invoke-Json -Method "GET" -Url "$MainBaseUrl/api/v1/health"
Assert-True -Name "Main /api/v1/health http" -Condition ($mainV1Health.StatusCode -eq 200 -or $mainV1Health.StatusCode -eq 503) -FailMessage "HTTP $($mainV1Health.StatusCode)"
Assert-Envelope -Name "Main /api/v1/health" -Resp $mainV1Health

# 2) Farms legacy and v1 consistency
$farmsLegacy = Invoke-Json -Method "GET" -Url "$MainBaseUrl/api/farms"
$farmsV1 = Invoke-Json -Method "GET" -Url "$MainBaseUrl/api/v1/farms"
$legacyIsArray = $farmsLegacy.Json -is [System.Array]
$v1IsArray = $farmsV1.Json -is [System.Array]
Assert-True -Name "Main farms legacy/v1 status aligned" -Condition ($farmsLegacy.StatusCode -eq $farmsV1.StatusCode) -FailMessage "legacy=$($farmsLegacy.StatusCode) v1=$($farmsV1.StatusCode)"
Assert-True -Name "Main farms status expected" -Condition (($farmsLegacy.StatusCode -eq 200) -or ($farmsLegacy.StatusCode -eq 401)) -FailMessage "HTTP $($farmsLegacy.StatusCode)"
if ($farmsLegacy.StatusCode -eq 200 -and $farmsV1.StatusCode -eq 200) {
    Assert-True -Name "Main /api/farms payload array" -Condition $legacyIsArray -FailMessage "body=$($farmsLegacy.Raw)"
    Assert-True -Name "Main /api/v1/farms payload array" -Condition $v1IsArray -FailMessage "body=$($farmsV1.Raw)"
    if ($legacyIsArray -and $v1IsArray) {
        Assert-True -Name "Main farms count legacy=v1" -Condition ($farmsLegacy.Json.Count -eq $farmsV1.Json.Count) -FailMessage "legacy=$($farmsLegacy.Json.Count) v1=$($farmsV1.Json.Count)"
    }
} else {
    Write-Host "[INFO] Main farms endpoint is auth-protected in current environment (401)."
}

$farmCode = "DEFAULT_FARM"
if ($legacyIsArray -and $farmsLegacy.Json.Count -gt 0 -and $farmsLegacy.Json[0].farm_code) {
    $farmCode = [string]$farmsLegacy.Json[0].farm_code
}
Write-Host "Using farm_code for autopredict checks: $farmCode"

# 3) Auto status envelope + legacy fields
$autoStatus = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/status?farm_code=$farmCode"
Assert-True -Name "Auto /api/status status" -Condition ($autoStatus.StatusCode -eq 200) -FailMessage "HTTP $($autoStatus.StatusCode) body=$($autoStatus.Raw)"
Assert-Envelope -Name "Auto /api/status" -Resp $autoStatus
$hasLegacyFarm = $autoStatus.Json -and ($autoStatus.Json.PSObject.Properties.Name -contains "farm_code")
Assert-True -Name "Auto /api/status legacy farm_code" -Condition $hasLegacyFarm -FailMessage "body=$($autoStatus.Raw)"

# 4) Auto v1 status + compatibility with legacy
$autoStatusV1 = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/v1/autopredict/status?farm_code=$farmCode"
Assert-True -Name "Auto /api/v1/autopredict/status status" -Condition ($autoStatusV1.StatusCode -eq 200) -FailMessage "HTTP $($autoStatusV1.StatusCode) body=$($autoStatusV1.Raw)"
Assert-Envelope -Name "Auto /api/v1/autopredict/status" -Resp $autoStatusV1
if ($autoStatus.Json -and $autoStatusV1.Json) {
    Assert-True -Name "Auto status legacy=v1 code" -Condition ($autoStatus.Json.code -eq $autoStatusV1.Json.code) -FailMessage "legacy=$($autoStatus.Json.code) v1=$($autoStatusV1.Json.code)"
}

# 5) Auto history envelope
$autoHistory = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/history?limit=1"
Assert-True -Name "Auto /api/history status" -Condition ($autoHistory.StatusCode -eq 200) -FailMessage "HTTP $($autoHistory.StatusCode) body=$($autoHistory.Raw)"
Assert-Envelope -Name "Auto /api/history" -Resp $autoHistory

# 6) Auto v1 history envelope
$autoHistoryV1 = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/v1/autopredict/history?limit=1"
Assert-True -Name "Auto /api/v1/autopredict/history status" -Condition ($autoHistoryV1.StatusCode -eq 200) -FailMessage "HTTP $($autoHistoryV1.StatusCode) body=$($autoHistoryV1.Raw)"
Assert-Envelope -Name "Auto /api/v1/autopredict/history" -Resp $autoHistoryV1

# 7) Auto task_status envelope (valid and invalid)
$taskStatus = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/task_status?type=short"
Assert-True -Name "Auto /api/task_status(short) http" -Condition ($taskStatus.StatusCode -eq 200 -or $taskStatus.StatusCode -eq 500) -FailMessage "HTTP $($taskStatus.StatusCode) body=$($taskStatus.Raw)"
Assert-Envelope -Name "Auto /api/task_status(short)" -Resp $taskStatus

# 8) Auto v1 task_status envelope (valid and invalid)
$taskStatusV1 = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/v1/autopredict/task_status?type=short"
Assert-True -Name "Auto /api/v1/autopredict/task_status(short) http" -Condition ($taskStatusV1.StatusCode -eq 200 -or $taskStatusV1.StatusCode -eq 500) -FailMessage "HTTP $($taskStatusV1.StatusCode) body=$($taskStatusV1.Raw)"
Assert-Envelope -Name "Auto /api/v1/autopredict/task_status(short)" -Resp $taskStatusV1

$taskInvalid = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/task_status?type=invalid_type"
Assert-True -Name "Auto /api/task_status(invalid) status expected" -Condition (($taskInvalid.StatusCode -eq 400) -or ($taskInvalid.StatusCode -eq 401)) -FailMessage "HTTP $($taskInvalid.StatusCode) body=$($taskInvalid.Raw)"
if ($taskInvalid.StatusCode -eq 400) {
    Assert-Envelope -Name "Auto /api/task_status(invalid)" -Resp $taskInvalid
    if ($taskInvalid.Json) {
        Assert-True -Name "Auto /api/task_status(invalid) code=1001" -Condition ($taskInvalid.Json.code -eq 1001) -FailMessage "body=$($taskInvalid.Raw)"
    }
} else {
    Write-Host "[INFO] Auto /api/task_status(invalid) is auth-protected in current environment (401)."
}

$taskInvalidV1 = Invoke-Json -Method "GET" -Url "$AutoBaseUrl/api/v1/autopredict/task_status?type=invalid_type"
Assert-True -Name "Auto /api/v1/autopredict/task_status(invalid) status expected" -Condition (($taskInvalidV1.StatusCode -eq 400) -or ($taskInvalidV1.StatusCode -eq 401)) -FailMessage "HTTP $($taskInvalidV1.StatusCode) body=$($taskInvalidV1.Raw)"
if ($taskInvalidV1.StatusCode -eq 400) {
    Assert-Envelope -Name "Auto /api/v1/autopredict/task_status(invalid)" -Resp $taskInvalidV1
    if ($taskInvalidV1.Json) {
        Assert-True -Name "Auto /api/v1/autopredict/task_status(invalid) code=1001" -Condition ($taskInvalidV1.Json.code -eq 1001) -FailMessage "body=$($taskInvalidV1.Raw)"
    }
} else {
    Write-Host "[INFO] Auto /api/v1/autopredict/task_status(invalid) is auth-protected in current environment (401)."
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "API contract smoke verification PASSED." -ForegroundColor Green
    exit 0
}

Write-Host "API contract smoke verification FAILED with $failures issue(s)." -ForegroundColor Red
exit 1

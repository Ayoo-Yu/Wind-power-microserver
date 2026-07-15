[CmdletBinding()]
param(
    [string]$BackendUrl = 'http://127.0.0.1:18080',
    [string]$ScadaHost = '127.0.0.1',
    [int]$ScadaPort = 12404,
    [int]$TimeoutSeconds = 120,
    [switch]$AllowNonLocalBackend
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$CatalogPath = Join-Path $RepositoryRoot 'simulation\scada-test\config\point-catalog.json'
$BackendUrl = $BackendUrl.TrimEnd('/')
$backendUri = [Uri]$BackendUrl
$localHosts = @('127.0.0.1', 'localhost', '::1')
if (-not $AllowNonLocalBackend.IsPresent -and $localHosts -notcontains $backendUri.Host) {
    throw "Refusing to seed simulated data into a non-local backend: $BackendUrl"
}

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )
    $parameters = @{
        Uri = "$BackendUrl$Path"
        Method = $Method
        TimeoutSec = 15
    }
    if ($null -ne $Body) {
        $parameters['ContentType'] = 'application/json; charset=utf-8'
        $parameters['Body'] = $Body | ConvertTo-Json -Depth 8 -Compress
    }
    Invoke-RestMethod @parameters
}

if (-not (Test-Path -LiteralPath $CatalogPath)) {
    throw "Point catalog not found: $CatalogPath"
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$backendReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get -TimeoutSec 3 | Out-Null
        $backendReady = $true
        break
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $backendReady) {
    throw "Backend did not become ready: $BackendUrl"
}

$catalog = Get-Content -LiteralPath $CatalogPath -Encoding UTF8 -Raw | ConvertFrom-Json
$current = Invoke-Api -Method Get -Path '/scada/connections'
$connections = @($current.data)

foreach ($farm in $catalog.farms) {
    $existing = $connections | Where-Object { $_.farm_code -eq $farm.farm_code } | Select-Object -First 1
    if ($null -ne $existing -and $existing.status -ne 'stopped') {
        try {
            Invoke-Api -Method Post -Path "/scada/connections/$($existing.id)/stop" -Body @{} | Out-Null
            Start-Sleep -Milliseconds 500
        }
        catch {
            Write-Host "[WARN] Could not stop stale connection $($farm.farm_code): $($_.Exception.Message)"
        }
    }

    $activePoint = $farm.points.active_power_mw
    $ioaPoints = @{}
    $ioaPoints[[string]$activePoint.ioa] = [string]$activePoint.type
    $payload = @{
        farm_code = [string]$farm.farm_code
        name = "$($farm.name) SCADA Testbed"
        protocol = 'c104'
        server_ip = $ScadaHost
        server_port = $ScadaPort
        casdu_address = [int]$catalog.common_address
        originator_address = [int]$catalog.originator_address
        ioa_points = $ioaPoints
        upload_target_ioa = [int]$activePoint.ioa
        fetch_interval = 10
        is_enabled = $true
    }

    if ($null -eq $existing) {
        $response = Invoke-Api -Method Post -Path '/scada/connections' -Body $payload
        $connectionId = [int]$response.data.id
        Write-Host "[OK] Created SCADA test connection: $($farm.farm_code)"
    }
    else {
        $response = Invoke-Api -Method Put -Path "/scada/connections/$($existing.id)" -Body $payload
        $connectionId = [int]$existing.id
        Write-Host "[OK] Updated SCADA test connection: $($farm.farm_code)"
    }

    Invoke-Api -Method Post -Path "/scada/connections/$connectionId/start" -Body @{} | Out-Null
    Write-Host "[OK] Started SCADA test worker: $($farm.farm_code)"
}

$expectedCodes = @($catalog.farms | ForEach-Object { [string]$_.farm_code } | Sort-Object)
$workerDeadline = (Get-Date).AddSeconds(45)
$allRunning = $false
while ((Get-Date) -lt $workerDeadline) {
    $latest = Invoke-Api -Method Get -Path '/scada/connections'
    $testConnections = @($latest.data | Where-Object { $expectedCodes -contains $_.farm_code })
    $runningCodes = @(
        $testConnections |
            Where-Object { $_.status -eq 'running' } |
            ForEach-Object { [string]$_.farm_code } |
            Sort-Object
    )
    if (($runningCodes -join ',') -eq ($expectedCodes -join ',')) {
        $allRunning = $true
        break
    }
    Start-Sleep -Milliseconds 500
}
if (-not $allRunning) {
    $statusSummary = @($testConnections | ForEach-Object { "$($_.farm_code)=$($_.status)" }) -join ', '
    throw "SCADA workers did not become ready: $statusSummary"
}

Write-Host "[OK] Local backend now uses SCADA test endpoint ${ScadaHost}:$ScadaPort"

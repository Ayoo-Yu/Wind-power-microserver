[CmdletBinding()]
param(
    [ValidateSet('up', 'up-infra', 'down', 'status', 'test', 'scenario', 'fault', 'reset', 'logs')]
    [string]$Action = 'status',
    [string]$Name = 'normal',
    [switch]$Disable,
    [ValidateRange(0, 60000)]
    [int]$LatencyMs = 0,
    [ValidateRange(0, 60000)]
    [int]$JitterMs = 0,
    [ValidateRange(0, 1048576)]
    [int]$BandwidthKbps = 0,
    [ValidateRange(0, 2147483647)]
    [int]$CloseAfterBytes = 0
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ComposeFile = Join-Path $RepositoryRoot 'compose.scada-test.yaml'
$ArtifactsDir = Join-Path $RepositoryRoot 'simulation\scada-test\artifacts'
$BaseImageArchive = Join-Path $RepositoryRoot 'wind-power-forecast\04_scada_simulator.tar'
$ComposePrefix = @('compose', '-p', 'wind-power-scada-test', '-f', $ComposeFile)
$SimulatorControlPort = if ($env:SCADA_TEST_SIMULATOR_CONTROL_PORT) { $env:SCADA_TEST_SIMULATOR_CONTROL_PORT } else { '18082' }
$ProxyControlPort = if ($env:SCADA_TEST_PROXY_CONTROL_PORT) { $env:SCADA_TEST_PROXY_CONTROL_PORT } else { '18081' }
$C104Port = if ($env:SCADA_TEST_C104_PORT) { $env:SCADA_TEST_C104_PORT } else { '12404' }
$NwpControlPort = if ($env:NWP_TEST_CONTROL_PORT) { $env:NWP_TEST_CONTROL_PORT } else { '18084' }
$DatabasePort = if ($env:SCADA_TEST_DB_PORT) { $env:SCADA_TEST_DB_PORT } else { '15433' }
$RedisPort = if ($env:SCADA_TEST_REDIS_PORT) { $env:SCADA_TEST_REDIS_PORT } else { '6380' }
$SimulatorControlUrl = "http://127.0.0.1:$SimulatorControlPort"
$ProxyControlUrl = "http://127.0.0.1:$ProxyControlPort"
$NwpControlUrl = "http://127.0.0.1:$NwpControlPort"

function Invoke-DockerCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & docker @ComposePrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}

function Test-DockerReady {
    & docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker is unavailable. Start Docker Desktop first.'
    }
}

function Ensure-BaseImage {
    & docker image inspect wind-power-scada-simulator:v1 *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    if (-not (Test-Path -LiteralPath $BaseImageArchive)) {
        throw "Base image and offline archive are unavailable: $BaseImageArchive"
    }
    Write-Host '[INFO] Loading the offline C104 simulator base image...'
    & docker load -i $BaseImageArchive
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to load the offline C104 simulator base image.'
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3 | Out-Null
            Write-Host "[OK] $ServiceName is ready."
            return
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for ${ServiceName}: $Url"
}

function Invoke-TestApi {
    param(
        [string]$Url,
        [hashtable]$Body = @{}
    )
    $json = $Body | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri $Url -Method Post -ContentType 'application/json; charset=utf-8' -Body $json
}

function Start-Core {
    Test-DockerReady
    Ensure-BaseImage
    New-Item -ItemType Directory -Force -Path $ArtifactsDir | Out-Null
    Invoke-DockerCompose up --detach --build scada-simulator fault-proxy nwp-simulator
    Wait-HttpReady "$SimulatorControlUrl/ready" 'SCADA simulator'
    Wait-HttpReady "$ProxyControlUrl/live" 'fault proxy'
    Wait-HttpReady "$NwpControlUrl/ready" 'NWP simulator'
    Write-Host "[OK] C104 test endpoint: 127.0.0.1:$C104Port"
    Write-Host "[OK] Simulator control API: $SimulatorControlUrl"
    Write-Host "[OK] Fault proxy control API: $ProxyControlUrl"
    Write-Host "[OK] NWP simulator control API: $NwpControlUrl"
}

Push-Location $RepositoryRoot
try {
    switch ($Action) {
        'up' {
            Start-Core
        }
        'up-infra' {
            Start-Core
            Invoke-DockerCompose --profile infra up --detach --wait --wait-timeout 120 test-kingbase test-redis
            Write-Host "[OK] Isolated KingBase: 127.0.0.1:$DatabasePort"
            Write-Host "[OK] Isolated Redis: 127.0.0.1:$RedisPort"
        }
        'down' {
            Test-DockerReady
            Invoke-DockerCompose --profile acceptance --profile infra down --remove-orphans
        }
        'status' {
            Test-DockerReady
            Invoke-DockerCompose --profile acceptance --profile infra ps
            try {
                Invoke-RestMethod -Uri "$SimulatorControlUrl/state" -Method Get -TimeoutSec 3 |
                    ConvertTo-Json -Depth 8
                Invoke-RestMethod -Uri "$ProxyControlUrl/state" -Method Get -TimeoutSec 3 |
                    ConvertTo-Json -Depth 8
            }
            catch {
                Write-Host '[INFO] Test control APIs are unavailable.'
            }
        }
        'test' {
            Start-Core
            Invoke-DockerCompose --profile acceptance up --detach mock-ingress worker-harness
            try {
                & docker @ComposePrefix --profile acceptance run --rm acceptance-runner
                $testExitCode = $LASTEXITCODE
            }
            finally {
                $cleanupPreference = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                & docker @ComposePrefix --profile acceptance stop worker-harness mock-ingress 2>$null | Out-Null
                & docker @ComposePrefix --profile acceptance rm -f worker-harness mock-ingress 2>$null | Out-Null
                $ErrorActionPreference = $cleanupPreference
            }
            $report = Join-Path $ArtifactsDir 'acceptance-report.json'
            if (Test-Path -LiteralPath $report) {
                Write-Host "[INFO] Acceptance report: $report"
            }
            if ($testExitCode -ne 0) {
                throw "SCADA acceptance failed with exit code $testExitCode"
            }
        }
        'scenario' {
            $result = Invoke-TestApi "$SimulatorControlUrl/scenario" @{ name = $Name }
            $result | ConvertTo-Json -Depth 8
        }
        'fault' {
            $result = Invoke-TestApi "$ProxyControlUrl/fault" @{
                enabled = -not $Disable.IsPresent
                latency_ms = $LatencyMs
                jitter_ms = $JitterMs
                bandwidth_kbps = $BandwidthKbps
                close_after_bytes = $CloseAfterBytes
            }
            $result | ConvertTo-Json -Depth 8
        }
        'reset' {
            Invoke-TestApi "$ProxyControlUrl/reset" @{} | Out-Null
            Invoke-TestApi "$SimulatorControlUrl/scenario" @{ name = 'normal' } | Out-Null
            Write-Host '[OK] Normal scenario restored and network faults cleared.'
        }
        'logs' {
            Test-DockerReady
            & docker @ComposePrefix logs --follow --tail 200 scada-simulator fault-proxy nwp-simulator
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to read test environment logs. Exit code: $LASTEXITCODE"
            }
        }
    }
}
finally {
    Pop-Location
}

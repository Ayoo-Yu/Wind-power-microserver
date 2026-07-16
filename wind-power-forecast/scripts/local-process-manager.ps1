param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "stop")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidateSet("backend", "worker", "beat", "scada-manager", "nwp-shadow", "integration", "frontend", "all")]
    [string]$Service
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$ProjectDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"
$StateDir = Join-Path $ProjectDir ".local-run"

function Stop-LocalService {
    param([string]$Name)

    $StateFile = Join-Path $StateDir "$Name.json"
    if (-not (Test-Path -LiteralPath $StateFile)) {
        return
    }

    try {
        $State = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $Process = Get-Process -Id ([int]$State.pid) -ErrorAction Stop
        $StartTimeUtc = $Process.StartTime.ToUniversalTime().ToString("o")
        if ($StartTimeUtc -eq [string]$State.start_time_utc) {
            & taskkill.exe /PID $Process.Id /T /F *> $null
        }
    }
    catch {
    }
    finally {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-LocalService {
    param([string]$Name)

    if ($Name -eq "all") {
        throw "Service 'all' can only be used with the stop action."
    }

    Stop-LocalService -Name $Name
    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null

    switch ($Name) {
        "backend" {
            $Executable = $env:MAIN_PY
            $Arguments = @("app.py")
            $WorkingDirectory = $BackendDir
        }
        "worker" {
            $Executable = $env:MAIN_PY
            $Arguments = @("-m", "celery", "-A", "celery_app.celery_app", "worker", "--loglevel=info", "--pool=solo")
            $WorkingDirectory = $BackendDir
        }
        "beat" {
            $Executable = $env:MAIN_PY
            $Arguments = @("-m", "celery", "-A", "celery_app.celery_app", "beat", "--loglevel=info")
            $WorkingDirectory = $BackendDir
        }
        "integration" {
            $Executable = $env:MAIN_PY
            $Arguments = @(
                "-m", "integration.processor",
                "--spool", $env:INTEGRATION_SPOOL_DIR,
                "--nwp-input-root", $env:NWP_INPUT_ROOT,
                "--nwp-farm-codes", $env:NWP_FARM_CODES,
                "--source", "development.nwp"
            )
            $WorkingDirectory = $BackendDir
            $WindowStyle = "Hidden"
        }
        "nwp-shadow" {
            if (-not $env:NWP_ETEXT_INPUT_DIR) {
                throw "NWP_ETEXT_INPUT_DIR is required for nwp-shadow."
            }
            if (-not $env:NWP_ETEXT_OUTPUT_ROOT) {
                throw "NWP_ETEXT_OUTPUT_ROOT is required for nwp-shadow."
            }
            if (-not $env:NWP_ETEXT_CONTRACT) {
                throw "NWP_ETEXT_CONTRACT is required for nwp-shadow."
            }
            $Executable = $env:MAIN_PY
            $Arguments = @(
                "-u", (Join-Path $ProjectDir "scripts\nwp_shadow.py"),
                "watch",
                "--input-dir", $env:NWP_ETEXT_INPUT_DIR,
                "--output-root", $env:NWP_ETEXT_OUTPUT_ROOT,
                "--contract", $env:NWP_ETEXT_CONTRACT
            )
            if ($env:NWP_ETEXT_SEED_FILE) {
                $Arguments += @("--seed-file", $env:NWP_ETEXT_SEED_FILE)
            }
            if ($env:NWP_ETEXT_REPLAY_LATEST -eq "true") {
                $Arguments += "--replay-now"
            }
            if ($env:NWP_ETEXT_GENERATE_SEED_IF_MISSING -eq "true") {
                $Arguments += "--generate-seed-if-missing"
            }
            $WorkingDirectory = $ProjectDir
            $WindowStyle = "Hidden"
        }
        "scada-manager" {
            $Executable = $env:MAIN_PY
            $Arguments = @("scada_manager_main.py")
            $WorkingDirectory = $BackendDir
            $WindowStyle = "Hidden"
        }
        "frontend" {
            $PackageFile = Join-Path $FrontendDir "package.json"
            $ViteCli = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"
            if (Test-Path -LiteralPath $PackageFile) {
                $Executable = (Get-Command npm.cmd -ErrorAction Stop).Source
                $Arguments = @("run", "serve")
            }
            elseif (Test-Path -LiteralPath $ViteCli) {
                $Executable = $ViteCli
            }
            else {
                throw "Frontend command was not found."
            }
            $WorkingDirectory = $FrontendDir
        }
    }

    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable)) {
        throw "Executable was not found for service '$Name': $Executable"
    }

    if (-not $WindowStyle) {
        $WindowStyle = "Normal"
    }

    $Process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle $WindowStyle `
        -PassThru

    Start-Sleep -Milliseconds 500
    if ($Process.HasExited) {
        throw "Service '$Name' exited during startup with code $($Process.ExitCode)."
    }

    $State = [ordered]@{
        service = $Name
        pid = $Process.Id
        start_time_utc = $Process.StartTime.ToUniversalTime().ToString("o")
    }
    $StateFile = Join-Path $StateDir "$Name.json"
    $State | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8
    Write-Output "[OK] Started $Name with PID $($Process.Id)."
}

if ($Action -eq "start") {
    Start-LocalService -Name $Service
    exit 0
}

if ($Service -eq "all") {
    foreach ($Name in @("frontend", "integration", "nwp-shadow", "scada-manager", "beat", "worker", "backend")) {
        Stop-LocalService -Name $Name
    }
}
else {
    Stop-LocalService -Name $Service
}

Write-Output "[OK] Stopped $Service."

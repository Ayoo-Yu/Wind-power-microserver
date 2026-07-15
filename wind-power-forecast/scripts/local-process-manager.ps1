param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "stop")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidateSet("backend", "worker", "beat", "frontend", "all")]
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
        "frontend" {
            $PackageFile = Join-Path $FrontendDir "package.json"
            $VueCli = Join-Path $FrontendDir "node_modules\.bin\vue-cli-service.cmd"
            if (Test-Path -LiteralPath $PackageFile) {
                $Executable = (Get-Command npm.cmd -ErrorAction Stop).Source
                $Arguments = @("run", "serve")
            }
            elseif (Test-Path -LiteralPath $VueCli) {
                $Executable = $VueCli
                $Arguments = @("serve")
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

    $Process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Normal `
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
    foreach ($Name in @("frontend", "beat", "worker", "backend")) {
        Stop-LocalService -Name $Name
    }
}
else {
    Stop-LocalService -Name $Service
}

Write-Output "[OK] Stopped $Service."

param(
    [string]$DbContainer = "sim-kingbase",
    [string]$DbName = "windpower",
    [string]$DbUser = "system",
    [string]$FrontendImage = "wind-power-frontend:v250715_1.0",
    [string]$PredictionImage = "wind-power-celery-worker:latest",
    [string]$DatabaseImage = "kingbase_v009r001c002b0014_single_x86:v1",
    [switch]$SkipBuild,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"

$deployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $deployDir
$packageDir = Split-Path -Parent $projectDir

$databaseTar = Join-Path $packageDir "01_database.tar"
$predictionTar = Join-Path $packageDir "02_prediction_system.tar"
$seedDump = Join-Path $packageDir "03_seed_data.dump"

function Run($FilePath, [string[]]$Arguments) {
    Write-Host "> $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Backup-IfExists($Path) {
    if ($SkipBackup -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = Join-Path $packageDir "release_backup_$stamp"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Move-Item -LiteralPath $Path -Destination (Join-Path $backupDir (Split-Path -Leaf $Path))
}

Write-Host "Project: $projectDir"
Write-Host "Output:  $packageDir"

Run "docker" @("info")

if (-not $SkipBuild) {
    Run "docker" @(
        "build",
        "-t", $FrontendImage,
        (Join-Path $projectDir "frontend")
    )

    Run "docker" @(
        "build",
        "-f", (Join-Path $projectDir "backend\Dockerfile.celery"),
        "-t", $PredictionImage,
        (Join-Path $projectDir "backend")
    )
}

Run "docker" @(
    "exec", "--user", "kingbase", $DbContainer,
    "/home/kingbase/install/kingbase/bin/ksql",
    "-p", "54321",
    "-U", $DbUser,
    "-d", $DbName,
    "-c", "select current_database();"
)

Backup-IfExists $databaseTar
Backup-IfExists $predictionTar
Backup-IfExists $seedDump

Run "docker" @("save", "-o", $databaseTar, $DatabaseImage)

Run "docker" @(
    "save",
    "-o", $predictionTar,
    $FrontendImage,
    $PredictionImage,
    "redis:7-alpine",
    "dpage/pgadmin4"
)

$containerDump = "/tmp/03_seed_data.dump"
Run "docker" @("exec", "--user", "kingbase", $DbContainer, "rm", "-f", $containerDump)
Run "docker" @(
    "exec", "--user", "kingbase", $DbContainer,
    "/home/kingbase/install/kingbase/bin/sys_dump",
    "-p", "54321",
    "-U", $DbUser,
    "-d", $DbName,
    "-F", "c",
    "-f", $containerDump
)
Run "docker" @("cp", "${DbContainer}:$containerDump", $seedDump)
Run "docker" @("exec", "--user", "kingbase", $DbContainer, "rm", "-f", $containerDump)

Get-Item $databaseTar, $predictionTar, $seedDump |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize

Write-Host "Export finished."

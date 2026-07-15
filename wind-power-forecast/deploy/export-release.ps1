param(
    [string]$ReleaseVersion = "",
    [string]$OutputDirectory = "",
    [string]$DbContainer = "sim-kingbase",
    [string]$DbName = "windpower",
    [string]$DbUser = "system",
    [string]$FrontendImage = "",
    [string]$PredictionImage = "",
    [string]$DatabaseImage = "kingbase_v009r001c002b0014_single_x86:v1",
    [string]$SigningKeyPath = "",
    [string]$SigningPublicKeyPath = "",
    [switch]$SkipBuild,
    [switch]$SkipBackup,
    [switch]$SkipDatabaseDump,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

$deployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $deployDir
$repositoryDir = Split-Path -Parent $projectDir

if ([string]::IsNullOrWhiteSpace($ReleaseVersion)) {
    $ReleaseVersion = Get-Date -Format "yyyyMMdd_HHmmss"
}
$safeVersion = $ReleaseVersion -replace '[^A-Za-z0-9_.-]', '_'
if ([string]::IsNullOrWhiteSpace($FrontendImage)) {
    $FrontendImage = "wind-power-frontend:$safeVersion"
}
if ([string]::IsNullOrWhiteSpace($PredictionImage)) {
    $PredictionImage = "wind-power-celery-worker:$safeVersion"
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryDir "release_$safeVersion"
}
$releaseDir = [System.IO.Path]::GetFullPath($OutputDirectory)

function Run($FilePath, [string[]]$Arguments) {
    Write-Host "> $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Write-Utf8NoBom($Path, $Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-RelativeReleasePath($BasePath, $TargetPath) {
    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\') + '\'
    $targetFull = [System.IO.Path]::GetFullPath($TargetPath)
    $baseUri = New-Object System.Uri($baseFull)
    $targetUri = New-Object System.Uri($targetFull)
    return [System.Uri]::UnescapeDataString(
        $baseUri.MakeRelativeUri($targetUri).ToString()
    )
}

function Copy-RequiredItem($Source, $Destination) {
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Required release item is missing: $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

$dirtyLines = @(& git -C $projectDir status --porcelain -- .)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect Git state"
}
if ($dirtyLines.Count -gt 0 -and -not $AllowDirty) {
    throw "Tracked or untracked project changes exist. Commit them or use -AllowDirty explicitly."
}
$gitCommit = (& git -C $projectDir rev-parse HEAD).Trim()
$gitBranch = (& git -C $projectDir branch --show-current).Trim()

if (Test-Path -LiteralPath $releaseDir) {
    $existing = @(Get-ChildItem -LiteralPath $releaseDir -Force)
    if ($existing.Count -gt 0) {
        throw "Output directory already exists and is not empty: $releaseDir"
    }
} else {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

$databaseTar = Join-Path $releaseDir "01_database.tar"
$predictionTar = Join-Path $releaseDir "02_prediction_system.tar"
$seedDump = Join-Path $releaseDir "03_seed_data.dump"

Write-Host "Project: $projectDir"
Write-Host "Release: $releaseDir"
Write-Host "Commit:  $gitCommit"

Run "docker" @("info")

if (-not $SkipBuild) {
    Run "docker" @("build", "-t", $FrontendImage, (Join-Path $projectDir "frontend"))
    Run "docker" @(
        "build",
        "-f", (Join-Path $projectDir "backend\Dockerfile.celery"),
        "-t", $PredictionImage,
        (Join-Path $projectDir "backend")
    )
}

Run "docker" @("save", "-o", $databaseTar, $DatabaseImage)
Run "docker" @(
    "save",
    "-o", $predictionTar,
    $FrontendImage,
    $PredictionImage,
    "redis:7-alpine",
    "dpage/pgadmin4"
)

if (-not $SkipDatabaseDump) {
    Run "docker" @(
        "exec", "--user", "kingbase", $DbContainer,
        "/home/kingbase/install/kingbase/bin/ksql",
        "-p", "54321", "-U", $DbUser, "-d", $DbName,
        "-c", "select current_database();"
    )
    $containerDump = "/tmp/03_seed_data.dump"
    Run "docker" @("exec", "--user", "kingbase", $DbContainer, "rm", "-f", $containerDump)
    Run "docker" @(
        "exec", "--user", "kingbase", $DbContainer,
        "/home/kingbase/install/kingbase/bin/sys_dump",
        "-p", "54321", "-U", $DbUser, "-d", $DbName,
        "-F", "c", "-f", $containerDump
    )
    Run "docker" @("cp", "${DbContainer}:$containerDump", $seedDump)
    Run "docker" @("exec", "--user", "kingbase", $DbContainer, "rm", "-f", $containerDump)
}

$releaseProjectDir = Join-Path $releaseDir "wind-power-forecast"
$releaseDeployDir = Join-Path $releaseProjectDir "deploy"
$releaseDocsDir = Join-Path $releaseProjectDir "docs\productization"
$releaseAgentDir = Join-Path $releaseDir "agents\integration"
New-Item -ItemType Directory -Force -Path $releaseDeployDir, $releaseDocsDir, $releaseAgentDir | Out-Null

$deployItems = @(
    ".env.example",
    "backend-entrypoint.sh",
    "deploy.sh",
    "docker-compose.db.yaml",
    "docker-compose.prod.yaml",
    "INSTALL_GUIDE.md",
    "verify-release.sh",
    "zone-agent"
)
foreach ($item in $deployItems) {
    Copy-RequiredItem (Join-Path $deployDir $item) $releaseDeployDir
}

$productizationDocs = Join-Path $projectDir "docs\productization"
if (Test-Path -LiteralPath $productizationDocs) {
    Get-ChildItem -LiteralPath $productizationDocs -File |
        Copy-Item -Destination $releaseDocsDir -Force
}
Get-ChildItem -LiteralPath (Join-Path $projectDir "backend\integration") -Filter "*.py" -File |
    Copy-Item -Destination $releaseAgentDir -Force
$schemaSource = Join-Path $projectDir "backend\integration\schemas"
if (Test-Path -LiteralPath $schemaSource) {
    Copy-RequiredItem $schemaSource $releaseAgentDir
}

$releaseEnvPath = Join-Path $releaseDeployDir ".env.example"
$releaseEnv = Get-Content -LiteralPath $releaseEnvPath -Raw -Encoding UTF8
$imageValues = [ordered]@{
    FRONTEND_IMAGE = $FrontendImage
    PREDICTION_IMAGE = $PredictionImage
    DATABASE_IMAGE = $DatabaseImage
}
foreach ($entry in $imageValues.GetEnumerator()) {
    $pattern = "(?m)^$([Regex]::Escape($entry.Key))=.*$"
    $line = "$($entry.Key)=$($entry.Value)"
    if ($releaseEnv -match $pattern) {
        $releaseEnv = $releaseEnv -replace $pattern, $line
    } else {
        $releaseEnv = $releaseEnv.TrimEnd() + "`n$line`n"
    }
}
Write-Utf8NoBom $releaseEnvPath $releaseEnv
Write-Utf8NoBom (Join-Path $releaseDir "VERSION") ($ReleaseVersion + "`n")

if (-not [string]::IsNullOrWhiteSpace($SigningKeyPath)) {
    if ([string]::IsNullOrWhiteSpace($SigningPublicKeyPath)) {
        throw "SigningPublicKeyPath is required when SigningKeyPath is provided"
    }
    Copy-RequiredItem $SigningPublicKeyPath (Join-Path $releaseDir "release-signing-public.pem")
}

$excludedNames = @("release-manifest.json", "SHA256SUMS", "SHA256SUMS.sig")
$artifactRows = @(
    Get-ChildItem -LiteralPath $releaseDir -File -Recurse |
        Where-Object { $excludedNames -notcontains $_.Name } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = (Get-RelativeReleasePath $releaseDir $_.FullName).Replace('\', '/')
            [ordered]@{
                path = $relative
                size = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
)

$manifest = [ordered]@{
    schema_version = "1.0"
    release_id = $ReleaseVersion
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    source = [ordered]@{
        git_commit = $gitCommit
        git_branch = $gitBranch
        dirty = ($dirtyLines.Count -gt 0)
    }
    images = [ordered]@{
        frontend = $FrontendImage
        prediction = $PredictionImage
        database = $DatabaseImage
        redis = "redis:7-alpine"
        pgadmin = "dpage/pgadmin4"
    }
    database_dump_included = (-not $SkipDatabaseDump)
    signature_included = (-not [string]::IsNullOrWhiteSpace($SigningKeyPath))
    artifacts = $artifactRows
}
$manifestPath = Join-Path $releaseDir "release-manifest.json"
Write-Utf8NoBom $manifestPath ($manifest | ConvertTo-Json -Depth 8)

$checksumFiles = @(
    Get-ChildItem -LiteralPath $releaseDir -File -Recurse |
        Where-Object { $_.Name -notin @("SHA256SUMS", "SHA256SUMS.sig") } |
        Sort-Object FullName
)
$checksumLines = @(
    foreach ($file in $checksumFiles) {
        $relative = (Get-RelativeReleasePath $releaseDir $file.FullName).Replace('\', '/')
        $digest = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$digest  $relative"
    }
)
$checksumPath = Join-Path $releaseDir "SHA256SUMS"
Write-Utf8NoBom $checksumPath (($checksumLines -join "`n") + "`n")

if (-not [string]::IsNullOrWhiteSpace($SigningKeyPath)) {
    if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
        throw "OpenSSL is required to sign the release"
    }
    Run "openssl" @(
        "dgst", "-sha256", "-sign", $SigningKeyPath,
        "-out", (Join-Path $releaseDir "SHA256SUMS.sig"),
        $checksumPath
    )
}

Get-ChildItem -LiteralPath $releaseDir -File |
    Select-Object Name, Length, LastWriteTime |
    Format-Table -AutoSize

Write-Host "Release export finished: $releaseDir"

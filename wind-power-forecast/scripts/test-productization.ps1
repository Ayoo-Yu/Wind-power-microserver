param(
    [switch]$SkipFrontend,
    [switch]$SkipCompose
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectDir "backend"
$frontendDir = Join-Path $projectDir "frontend"

$testFiles = @(
    "tests/test_integration_contracts.py",
    "tests/test_integration_spool.py",
    "tests/test_integration_agent.py",
    "tests/test_integration_ingress.py",
    "tests/test_integration_router.py",
    "tests/test_report_outbox_service.py",
    "tests/test_capability_service.py",
    "tests/test_celery_static_schedules.py"
)

Push-Location $backendDir
try {
    & python -m pytest @testFiles -q
    if ($LASTEXITCODE -ne 0) {
        throw "Backend productization tests failed"
    }
} finally {
    Pop-Location
}

if (-not $SkipFrontend) {
    Push-Location $frontendDir
    try {
        $npm = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
        & $npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed"
        }
    } finally {
        Pop-Location
    }
}

if (-not $SkipCompose) {
    $composeFiles = @(
        "deploy/docker-compose.db.yaml",
        "deploy/docker-compose.prod.yaml",
        "frontend-backend-compose.yaml"
    )
    foreach ($composeFile in $composeFiles) {
        $composeArgs = @(
            "compose",
            "-f", (Join-Path $projectDir $composeFile),
            "--env-file", (Join-Path $projectDir "deploy/.env.example"),
            "config", "--quiet"
        )
        & docker @composeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Compose validation failed: $composeFile"
        }
    }
}

$schemaPath = Join-Path $backendDir "integration/schemas/manifest-v1.schema.json"
Get-Content -LiteralPath $schemaPath -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null

$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $projectDir "deploy/export-release.ps1"),
    [ref]$null,
    [ref]$parseErrors
) | Out-Null
if ($parseErrors.Count -gt 0) {
    throw "Release script syntax validation failed"
}

if (Get-Command bash -ErrorAction SilentlyContinue) {
    Push-Location $projectDir
    try {
        $shellFiles = @(
            "deploy/deploy.sh",
            "deploy/verify-release.sh",
            "deploy/zone-agent/install-zone-agent.sh",
            "deploy/zone-agent/run-agent.sh"
        )
        foreach ($shellFile in $shellFiles) {
            & bash -n $shellFile
            if ($LASTEXITCODE -ne 0) {
                throw "Shell syntax validation failed: $shellFile"
            }
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Productization test suite passed."

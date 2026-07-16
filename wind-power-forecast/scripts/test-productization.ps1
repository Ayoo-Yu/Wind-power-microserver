param(
    [switch]$SkipFrontend,
    [switch]$SkipFrontendInstall,
    [switch]$SkipCompose
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$repositoryDir = Split-Path -Parent $projectDir
$backendDir = Join-Path $projectDir "backend"
$frontendDir = Join-Path $projectDir "frontend"

Push-Location $backendDir
try {
    & python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) {
        throw "Backend productization tests failed"
    }
} finally {
    Pop-Location
}

Push-Location $repositoryDir
try {
    & python -m unittest discover -s "simulation/scada-test/tests" -p "test_*.py" -v
    if ($LASTEXITCODE -ne 0) {
        throw "SCADA testbed unit tests failed"
    }
} finally {
    Pop-Location
}

if (-not $SkipFrontend) {
    Push-Location $frontendDir
    try {
        $npm = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
        if (-not $SkipFrontendInstall) {
            & $npm ci
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency installation failed"
            }
        }
        & $npm run verify
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend quality gate failed"
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
    & docker compose -p wind-power-scada-test -f (Join-Path $repositoryDir "compose.scada-test.yaml") --profile acceptance --profile infra config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Compose validation failed: compose.scada-test.yaml"
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

$scadaPowerShellFiles = @(
    "scripts/scada-test.ps1",
    "scripts/configure-scada-test.ps1",
    "scripts/local-process-manager.ps1"
)
foreach ($scadaPowerShellFile in $scadaPowerShellFiles) {
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Join-Path $projectDir $scadaPowerShellFile),
        [ref]$null,
        [ref]$parseErrors
    ) | Out-Null
    if ($parseErrors.Count -gt 0) {
        throw "SCADA PowerShell syntax validation failed: $scadaPowerShellFile"
    }
}

$scadaBatchFiles = @(
    "start-local.bat",
    "start-scada-dev.bat",
    "start-scada-test.bat",
    "stop-scada-dev.bat",
    "stop-scada-test.bat",
    "start-nwp-shadow-dev.bat",
    "stop-nwp-shadow-dev.bat",
    "test-scada-test.bat"
)
foreach ($scadaBatchFile in $scadaBatchFiles) {
    $batchPath = Join-Path $projectDir $scadaBatchFile
    $bytes = [System.IO.File]::ReadAllBytes($batchPath)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        if (
            $bytes[$index] -eq 10 -and
            ($index -eq 0 -or $bytes[$index - 1] -ne 13)
        ) {
            throw "SCADA batch file must use CRLF: $scadaBatchFile"
        }
    }
}

if (Get-Command bash -ErrorAction SilentlyContinue) {
    Push-Location $projectDir
    try {
        $shellFiles = @(
            "deploy/deploy.sh",
            "deploy/ecmwf/apply_yunnan_service_consolidation.sh",
            "deploy/ecmwf/health_check.sh",
            "deploy/ecmwf/rollback_yunnan_service_consolidation.sh",
            "deploy/ecmwf/run_yunnan_service_consolidation.sh",
            "deploy/verify-release.sh",
            "deploy/validate-field-config.sh",
            "deploy/zone-agent/install-zone-agent.sh",
            "deploy/zone-agent/run-agent.sh",
            "scripts/scada-test.sh"
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

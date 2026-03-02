Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
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

Write-Host "M1 verification started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Repo root: $root"
Write-Host ""

# 1) Microservice/deployment directories removed
$removedDirs = @(
    "wind-power-microservices",
    "microservices",
    "helm",
    "k8s",
    "monitoring"
)
foreach ($dir in $removedDirs) {
    $path = Join-Path $root $dir
    Assert-True -Name "Directory removed: $dir" -Condition (-not (Test-Path $path)) -FailMessage "Found at $path"
}

# 2) Key docs no longer reference microservices keywords
$docFiles = @(
    "DEVELOPER_QUICK_REFERENCE.md",
    "COMPREHENSIVE_USAGE_MANUAL.md",
    "PROJECT_DOCUMENTATION.md"
)
$keywords = @("wind-power-microservices", "microservices")
foreach ($doc in $docFiles) {
    $docPath = Join-Path $root $doc
    if (-not (Test-Path $docPath)) {
        Assert-True -Name "Doc exists: $doc" -Condition $false -FailMessage "Missing file"
        continue
    }

    $content = Get-Content -Raw -Path $docPath
    $hasKeyword = $false
    foreach ($kw in $keywords) {
        if ($content -match [regex]::Escape($kw)) {
            $hasKeyword = $true
            break
        }
    }
    Assert-True -Name "No microservice keyword in $doc" -Condition (-not $hasKeyword) -FailMessage "Keyword found"
}

# 3) app.py contains /api/v1/health route
$appPath = Join-Path $root "wind-power-forecast\backend\app.py"
if (Test-Path $appPath) {
    $appText = Get-Content -Raw -Path $appPath
    $hasV1Health = $appText -match "/api/v1/health"
    Assert-True -Name "app.py has /api/v1/health" -Condition $hasV1Health -FailMessage "Route missing"
} else {
    Assert-True -Name "app.py exists" -Condition $false -FailMessage "Missing file at $appPath"
}

# 4) common files exist
$requiredFiles = @(
    "wind-power-forecast\backend\common\api_response.py",
    "wind-power-forecast\backend\common\error_codes.py"
)
foreach ($file in $requiredFiles) {
    $path = Join-Path $root $file
    Assert-True -Name "File exists: $file" -Condition (Test-Path $path) -FailMessage "Missing file"
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "M1 verification PASSED." -ForegroundColor Green
    exit 0
}

Write-Host "M1 verification FAILED with $failures issue(s)." -ForegroundColor Red
exit 1


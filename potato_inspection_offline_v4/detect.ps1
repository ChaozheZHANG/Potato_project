<#
    Potato Inspection Offline Detection Script (Windows)
    Example:
        ./detect.ps1 test_images
        ./detect.ps1 C:\data\images -Conf 0.35
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Source,

    [Parameter(Position = 1)]
    [double]$Conf = 0.25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Set-Location $scriptDir

$activateScript = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
$modelPath = Join-Path $scriptDir "models\yolov8s-obb-potato-v22_best.pt"
$rulesPath = Join-Path $scriptDir "config\grading_rules.json"
$gradeScript = Join-Path $scriptDir "scripts\grade_with_potato_label.py"

if (-not (Test-Path $activateScript)) {
    Write-Host "Virtual environment not found. Please run ./deploy.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $modelPath)) {
    Write-Host "Model file missing: $modelPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $rulesPath)) {
    Write-Host "Grading rules missing: $rulesPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $gradeScript)) {
    Write-Host "Detection script missing: $gradeScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $Source)) {
    Write-Host "Input path not found: $Source" -ForegroundColor Red
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputDir = Join-Path $scriptDir "results\$timestamp"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Starting detection" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Source : $Source"
Write-Host "Output : $outputDir"
Write-Host "Confidence threshold : $Conf"
Write-Host ""

$previousPolicy = $null
try {
    $previousPolicy = Get-ExecutionPolicy -Scope Process -ErrorAction SilentlyContinue
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null

    . $activateScript

    $arguments = @(
        $gradeScript
        '--model', $modelPath
        '--source', $Source
        '--rules', $rulesPath
        '--out', $outputDir
        '--conf', $Conf
    )

    & python @arguments

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Detection finished successfully." -ForegroundColor Green
        Write-Host "Results saved to: $outputDir" -ForegroundColor Yellow

        $csvPath = Join-Path $outputDir "potatoes.csv"
        if (Test-Path $csvPath) {
            $lineCount = (Get-Content $csvPath | Measure-Object -Line).Lines - 1
            if ($lineCount -lt 0) { $lineCount = 0 }
            Write-Host "Detected potato count: $lineCount" -ForegroundColor Green
        }
    } else {
        Write-Host ""
        Write-Host "Detection failed. Check the log output above for details." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    if ($previousPolicy) {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy $previousPolicy -Force | Out-Null
    } else {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Undefined -Force | Out-Null
    }
}


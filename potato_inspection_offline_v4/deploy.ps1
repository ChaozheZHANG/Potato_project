<#
    Potato Inspection Offline Deployment Script (Windows)
    Usage:
        - Right click the file and choose "Run with PowerShell", or
        - From PowerShell:   Set-ExecutionPolicy -Scope Process Bypass; ./deploy.ps1
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan
    )

    Write-Host "=========================================" -ForegroundColor $Color
    Write-Host $Text -ForegroundColor $Color
    Write-Host "=========================================" -ForegroundColor $Color
}

function Write-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Text
    )

    Write-Host $Text -ForegroundColor Yellow
}

$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Set-Location $scriptDir
$venvDir = Join-Path $scriptDir "venv"
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
$requirementsPath = Join-Path $scriptDir "requirements.txt"
$modelPath = Join-Path $scriptDir "models\yolov8s-obb-potato-v22_best.pt"
$resultsDir = Join-Path $scriptDir "results"

# Debug: 显示文件路径（用于排查）
if ($PSBoundParameters.ContainsKey('Debug')) {
    Write-Host "[Debug] Script directory: $scriptDir" -ForegroundColor Gray
    Write-Host "[Debug] Requirements path: $requirementsPath" -ForegroundColor Gray
    Write-Host "[Debug] Requirements exists: $(Test-Path $requirementsPath)" -ForegroundColor Gray
}

Write-Section "Potato Grading System - Windows Deployment"

try {
    Write-Step "[1/5] Checking Python installation..."
    $pythonVersion = python --version 2>&1
    Write-Host "  Detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  Python 3.8+ is required. Please install it and run the script again." -ForegroundColor Red
    exit 1
}

Write-Step "[2/5] Creating virtual environment..."
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
    Write-Host "  Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "  Virtual environment already exists." -ForegroundColor Green
}

if (-not (Test-Path $activateScript)) {
    Write-Host "  Activation script missing: $activateScript" -ForegroundColor Red
    exit 1
}

Write-Step "[3/5] Installing Python packages..."
$previousPolicy = $null
try {
    $previousPolicy = Get-ExecutionPolicy -Scope Process -ErrorAction SilentlyContinue
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null

    . $activateScript

    Write-Host "  Upgrading pip..." -ForegroundColor Gray
    python -m pip install --upgrade pip --quiet | Out-Null
    
    if (Test-Path $requirementsPath) {
        Write-Host "  Installing from requirements.txt..." -ForegroundColor Gray
        python -m pip install -r $requirementsPath
    } else {
        Write-Host "  requirements.txt not found, installing core packages..." -ForegroundColor Yellow
        Write-Host "  Installing ultralytics..." -ForegroundColor Gray
        python -m pip install ultralytics==8.3.222 --quiet
        Write-Host "  Installing opencv-python..." -ForegroundColor Gray
        python -m pip install opencv-python==4.10.0.84 --quiet
        Write-Host "  Installing numpy..." -ForegroundColor Gray
        python -m pip install "numpy>=1.24.0" --quiet
        Write-Host "  Installing Pillow..." -ForegroundColor Gray
        python -m pip install "Pillow>=10.0.0" --quiet
    }
    Write-Host "  Dependencies installed successfully." -ForegroundColor Green
} finally {
    if ($previousPolicy) {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy $previousPolicy -Force | Out-Null
    } else {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Undefined -Force | Out-Null
    }
}

Write-Step "[4/5] Verifying model file..."
if (Test-Path $modelPath) {
    $modelSizeMb = [math]::Round(((Get-Item $modelPath).Length / 1MB), 1)
    Write-Host "  Model file present ($modelSizeMb MB)." -ForegroundColor Green
} else {
    Write-Host "  Model file missing. Expected at $modelPath" -ForegroundColor Red
    exit 1
}

Write-Step "[5/5] Preparing output folder..."
if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
}
Write-Host "  Output folder ready: $resultsDir" -ForegroundColor Green

Write-Host ""
Write-Section "Deployment Complete" -Color ([ConsoleColor]::Green)
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "To start the detection service (production mode):" -ForegroundColor Cyan
Write-Host "  .\run_detection_service.ps1 -CameraDir `"F:\data\camera`" -PLCIp `"192.168.1.1`" -PLCPort 502 -Channels `"1,2,3,4`"" -ForegroundColor White
Write-Host ""
Write-Host "Or with custom parameters:" -ForegroundColor Cyan
Write-Host "  .\run_detection_service.ps1 -CameraDir `"F:\data\camera`" -PLCIp `"<PLC_IP>`" -PLCPort <PORT> -Channels `"<CHANNELS>`"" -ForegroundColor Gray
Write-Host ""
Write-Host "For batch detection (test mode):" -ForegroundColor Cyan
Write-Host "  .\detect.ps1 test_images" -ForegroundColor Gray
Write-Host ""


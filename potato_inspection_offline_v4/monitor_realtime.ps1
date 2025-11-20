<#
    Real-time Camera Monitoring Script (Windows)
    Monitors camera directory and processes new images automatically
    Usage:
        .\monitor_realtime.ps1
        .\monitor_realtime.ps1 -CameraDir "F:\data\camera" -PLCEnable
#>

[CmdletBinding()]
param(
    [string]$CameraDir = "F:\data\camera",
    [string]$Model = "models\yolov8s-obb-potato-v22_best.pt",
    [string]$Rules = "config\grading_rules.json",
    [switch]$PLCEnable,
    [string]$PLCHost = "192.168.1.100",
    [int]$PLCPort = 502,
    [int]$PLCAddress = 0,
    [double]$Conf = 0.25,
    [string]$Output = "results\realtime_monitor",
    [double]$ScanInterval = 0.5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Set-Location $scriptDir

$activateScript = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
$monitorScript = Join-Path $scriptDir "scripts\monitor_camera_realtime.py"

if (-not (Test-Path $activateScript)) {
    Write-Host "Virtual environment not found. Please run .\deploy.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $monitorScript)) {
    Write-Host "Monitor script not found: $monitorScript" -ForegroundColor Red
    exit 1
}

$modelPath = Join-Path $scriptDir $Model
if (-not (Test-Path $modelPath)) {
    Write-Host "Model file not found: $modelPath" -ForegroundColor Red
    exit 1
}

$rulesPath = Join-Path $scriptDir $Rules
if (-not (Test-Path $rulesPath)) {
    Write-Host "Rules file not found: $rulesPath" -ForegroundColor Red
    exit 1
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Real-time Camera Monitor" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Camera directory: $CameraDir"
Write-Host "Model: $Model"
Write-Host "PLC enabled: $PLCEnable"
if ($PLCEnable) {
    Write-Host "PLC host: $PLCHost"
    Write-Host "PLC port: $PLCPort"
    Write-Host "PLC address: $PLCAddress"
}
Write-Host "Scan interval: $ScanInterval seconds"
Write-Host ""

$previousPolicy = $null
try {
    $previousPolicy = Get-ExecutionPolicy -Scope Process -ErrorAction SilentlyContinue
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null

    . $activateScript

    $arguments = @(
        $monitorScript
        '--camera_dir', $CameraDir
        '--model', $modelPath
        '--rules', $rulesPath
        '--conf', $Conf
        '--output', $Output
        '--scan_interval', $ScanInterval
    )

    if ($PLCEnable) {
        $arguments += '--plc_enable'
        $arguments += '--plc_host', $PLCHost
        $arguments += '--plc_port', $PLCPort
        $arguments += '--plc_address', $PLCAddress
    }

    & python @arguments

} finally {
    if ($previousPolicy) {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy $previousPolicy -Force | Out-Null
    } else {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Undefined -Force | Out-Null
    }
}


<#
    Detection Service Launcher (Windows)
    启动检测服务，与 cam_plc_capture.py 和 plc_dummy_loop.py 配合工作
#>

[CmdletBinding()]
param(
    [string]$CameraDir = "F:\data\camera",
    [string]$Model = "models\yolov8s-obb-potato-v22_best.pt",
    [string]$Rules = "config\grading_rules.json",
    [string]$PLCIp = "192.168.1.1",
    [int]$PLCPort = 502,
    [string]$Channels = "1,2,3,4",
    [int]$AddrBase = 0,
    [double]$Conf = 0.25,
    [double]$ScanInterval = 0.5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Set-Location $scriptDir

# 检测虚拟环境位置（可能在项目根目录或venv目录）
$venvPath = Join-Path $scriptDir "venv"
if (-not (Test-Path $venvPath)) {
    # 尝试在上级目录查找
    $parentVenv = Join-Path (Split-Path $scriptDir) "venv"
    if (Test-Path $parentVenv) {
        $venvPath = $parentVenv
    }
}

$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
$detectScript = Join-Path $scriptDir "scripts\detect_and_write_plc.py"

if (-not (Test-Path $activateScript)) {
    Write-Host "Virtual environment not found. Please run .\deploy.ps1 first." -ForegroundColor Red
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
Write-Host "Detection Service" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Camera directory: $CameraDir"
Write-Host "Model: $Model"
Write-Host "PLC: ${PLCIp}:${PLCPort}"
Write-Host "Channels: $Channels"
Write-Host "Address base: $AddrBase"
Write-Host ""

$previousPolicy = $null
try {
    $previousPolicy = Get-ExecutionPolicy -Scope Process -ErrorAction SilentlyContinue
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null

    . $activateScript

    $arguments = @(
        $detectScript
        '--camera_dir', $CameraDir
        '--model', $modelPath
        '--rules', $rulesPath
        '--plc_ip', $PLCIp
        '--plc_port', $PLCPort
        '--channels', $Channels
        '--addr_base', $AddrBase
        '--conf', $Conf
        '--scan_interval', $ScanInterval
    )

    & python @arguments

} finally {
    if ($previousPolicy) {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy $previousPolicy -Force | Out-Null
    } else {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Undefined -Force | Out-Null
    }
}


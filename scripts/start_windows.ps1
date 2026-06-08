# FinAlly — Start script for Windows (PowerShell)
# Usage: .\scripts\start_windows.ps1 [-Build]
#   -Build   Force a fresh Docker image build (bypasses layer cache)
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"
$ImageName = "finally"
$Port = 8000
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

# ── Prerequisite: .env ───────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Write-Host "Copying .env.example to .env..."
        Copy-Item ".env.example" ".env"
        Write-Host ""
        Write-Host "ACTION REQUIRED: Open .env and set your OPENROUTER_API_KEY, then re-run this script." -ForegroundColor Cyan
        exit 1
    } else {
        Write-Host "Error: .env.example not found either. Cannot continue." -ForegroundColor Red
        exit 1
    }
}

# ── Stop any existing container ──────────────────────────────────────────────
$RunningId = docker ps -q --filter "name=^${ContainerName}$" 2>$null
if ($RunningId) {
    Write-Host "Stopping existing FinAlly container..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
}

# Also remove stopped container with same name (if it exists but isn't running)
$StoppedId = docker ps -aq --filter "name=^${ContainerName}$" 2>$null
if ($StoppedId) {
    docker rm $ContainerName | Out-Null
}

# ── Build image if needed ────────────────────────────────────────────────────
$ImageExists = docker image inspect $ImageName 2>$null
if (-not $ImageExists -or $Build) {
    Write-Host "Building Docker image — this takes a few minutes the first time..."
    Write-Host "(Subsequent starts are much faster)"
    Write-Host ""
    if ($Build) {
        docker build --no-cache -t $ImageName .
    } else {
        docker build -t $ImageName .
    }
    Write-Host ""
}

# ── Start container ──────────────────────────────────────────────────────────
Write-Host "Starting FinAlly..."
docker run -d `
    --name $ContainerName `
    -p "${Port}:8000" `
    -v finally-data:/app/db `
    --env-file .env `
    $ImageName | Out-Null

Write-Host ""
Write-Host "FinAlly is running at http://localhost:$Port" -ForegroundColor Green
Write-Host "To stop: .\scripts\stop_windows.ps1"
Write-Host ""

# ── Open browser ─────────────────────────────────────────────────────────────
Write-Host "Opening browser in 2 seconds..."
Start-Sleep -Seconds 2
Start-Process "http://localhost:$Port"

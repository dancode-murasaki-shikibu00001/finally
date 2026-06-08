# FinAlly — Stop script for Windows (PowerShell)
# Usage: .\scripts\stop_windows.ps1
# Note: Data is preserved in the Docker volume (finally-data).

$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"

# Check if container is running
$RunningId = docker ps -q --filter "name=^${ContainerName}$" 2>$null
if ($RunningId) {
    Write-Host "Stopping FinAlly..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
    Write-Host "FinAlly stopped. Your portfolio data is preserved in the Docker volume." -ForegroundColor Green
} else {
    # Check if it exists but is stopped
    $StoppedId = docker ps -aq --filter "name=^${ContainerName}$" 2>$null
    if ($StoppedId) {
        Write-Host "FinAlly container exists but is already stopped. Removing..."
        docker rm $ContainerName | Out-Null
        Write-Host "Done." -ForegroundColor Green
    } else {
        Write-Host "FinAlly is not running." -ForegroundColor Yellow
    }
}

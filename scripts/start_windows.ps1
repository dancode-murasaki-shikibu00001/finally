param([switch]$Build)

$ContainerName = "finally-app"
$ImageName     = "finally"
$Port          = 8000

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Stop any existing container
$existing = docker ps -aq --filter "name=$ContainerName" 2>$null
if ($existing) {
    Write-Host "Stopping existing container..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
}

# Build if forced or image missing
$imageExists = docker image inspect $ImageName 2>$null
if ($Build -or -not $imageExists) {
    Write-Host "Building Docker image..."
    docker build -t $ImageName $ProjectRoot
}

docker volume create finally-data 2>$null | Out-Null

Write-Host "Starting FinAlly on http://localhost:$Port ..."
docker run -d `
    --name $ContainerName `
    -p "${Port}:${Port}" `
    -v finally-data:/app/db `
    --env-file "$ProjectRoot\.env" `
    $ImageName

Write-Host ""
Write-Host "  FinAlly is running at http://localhost:$Port"
Write-Host "  Stop with: .\scripts\stop_windows.ps1"

Start-Sleep 1
Start-Process "http://localhost:$Port"

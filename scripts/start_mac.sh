#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="finally-app"
IMAGE_NAME="finally"
PORT=8000
BUILD=false

for arg in "$@"; do
  case $arg in
    --build) BUILD=true ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Stop any existing container
if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
  echo "Stopping existing container..."
  docker stop "$CONTAINER_NAME" >/dev/null
fi
if docker ps -aq --filter "name=$CONTAINER_NAME" | grep -q .; then
  docker rm "$CONTAINER_NAME" >/dev/null
fi

# Build image if missing or forced
if $BUILD || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building Docker image..."
  docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
fi

# Ensure volume exists
docker volume create finally-data >/dev/null 2>&1 || true

echo "Starting FinAlly on http://localhost:$PORT ..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PORT:$PORT" \
  -v finally-data:/app/db \
  --env-file "$PROJECT_ROOT/.env" \
  "$IMAGE_NAME"

echo ""
echo "  FinAlly is running at http://localhost:$PORT"
echo "  Stop with: ./scripts/stop_mac.sh"

# Open browser on macOS
if command -v open >/dev/null 2>&1; then
  sleep 1 && open "http://localhost:$PORT" &
fi

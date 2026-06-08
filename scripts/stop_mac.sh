#!/usr/bin/env bash
# FinAlly — Stop script for macOS/Linux
# Usage: ./scripts/stop_mac.sh
# Note: Data is preserved in the Docker volume (finally-data).
set -euo pipefail

CONTAINER_NAME="finally-app"

# Check if container is running
if docker ps -q --filter "name=^${CONTAINER_NAME}$" | grep -q .; then
  echo "Stopping FinAlly..."
  docker stop "$CONTAINER_NAME" > /dev/null
  docker rm "$CONTAINER_NAME" > /dev/null
  echo "FinAlly stopped. Your portfolio data is preserved in the Docker volume."
else
  # Check if it exists but is stopped
  if docker ps -aq --filter "name=^${CONTAINER_NAME}$" | grep -q .; then
    echo "FinAlly container exists but is already stopped. Removing..."
    docker rm "$CONTAINER_NAME" > /dev/null
    echo "Done."
  else
    echo "FinAlly is not running."
  fi
fi

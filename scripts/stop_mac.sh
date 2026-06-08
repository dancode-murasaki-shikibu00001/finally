#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="finally-app"

if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
  echo "Stopping FinAlly..."
  docker stop "$CONTAINER_NAME"
  docker rm "$CONTAINER_NAME"
  echo "Stopped."
else
  echo "FinAlly is not running."
fi

#!/usr/bin/env bash
# FinAlly — Start script for macOS/Linux
# Usage: ./scripts/start_mac.sh [--build]
#   --build   Force a fresh Docker image build (bypasses layer cache)
set -euo pipefail

CONTAINER_NAME="finally-app"
IMAGE_NAME="finally"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT=8000

# ── Parse flags ──────────────────────────────────────────────────────────────
BUILD_FLAG=""
for arg in "$@"; do
  case $arg in
    --build) BUILD_FLAG="--no-cache" ;;
  esac
done

cd "$PROJECT_DIR"

# ── Prerequisite: .env ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "Warning: .env file not found."
  if [ -f ".env.example" ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "ACTION REQUIRED: Open .env and set your OPENROUTER_API_KEY, then re-run this script."
    exit 1
  else
    echo "Error: .env.example not found either. Cannot continue."
    exit 1
  fi
fi

# ── Stop any existing container ──────────────────────────────────────────────
if docker ps -q --filter "name=^${CONTAINER_NAME}$" | grep -q .; then
  echo "Stopping existing FinAlly container..."
  docker stop "$CONTAINER_NAME" > /dev/null
  docker rm "$CONTAINER_NAME" > /dev/null
fi

# Also remove stopped container with same name (if it exists but isn't running)
if docker ps -aq --filter "name=^${CONTAINER_NAME}$" | grep -q .; then
  docker rm "$CONTAINER_NAME" > /dev/null
fi

# ── Build image if needed ────────────────────────────────────────────────────
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1 || [ -n "$BUILD_FLAG" ]; then
  echo "Building Docker image — this takes a few minutes the first time..."
  echo "(Subsequent starts are much faster)"
  echo ""
  # shellcheck disable=SC2086
  docker build $BUILD_FLAG -t "$IMAGE_NAME" .
  echo ""
fi

# ── Start container ──────────────────────────────────────────────────────────
echo "Starting FinAlly..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:8000" \
  -v finally-data:/app/db \
  --env-file .env \
  "$IMAGE_NAME" > /dev/null

echo ""
echo "FinAlly is running at http://localhost:${PORT}"
echo "To stop: ./scripts/stop_mac.sh"
echo ""

# ── Open browser (macOS) ─────────────────────────────────────────────────────
if command -v open > /dev/null 2>&1; then
  echo "Opening browser in 2 seconds..."
  (sleep 2 && open "http://localhost:${PORT}") &
fi

#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# BridgeAI Deploy Script
# Usage: ./scripts/deploy.sh [--registry REGISTRY] [--tag TAG]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$(cd "$PROJECT_ROOT/../frontend" && pwd)"

# Defaults
REGISTRY="${REGISTRY:-}"
TAG="${TAG:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry) REGISTRY="$2"; shift 2 ;;
    --tag)      TAG="$2"; shift 2 ;;
    --compose)  COMPOSE_FILE="$2"; shift 2 ;;
    *)          echo "Unknown option: $1"; exit 1 ;;
  esac
done

BACKEND_IMAGE="bridgeai-backend:${TAG}"
FRONTEND_IMAGE="bridgeai-frontend:${TAG}"

echo "=== BridgeAI Deploy ==="
echo "  Tag:      ${TAG}"
echo "  Registry: ${REGISTRY:-<local>}"
echo ""

# ---- Step 1: Build frontend ----
echo "[1/4] Building frontend production bundle..."
cd "$FRONTEND_DIR"
if command -v npm &>/dev/null; then
  npm ci --silent 2>/dev/null || npm install --silent
  npm run build
else
  echo "ERROR: npm not found. Please install Node.js." >&2
  exit 1
fi
echo "  Frontend build complete: ${FRONTEND_DIR}/dist"

# ---- Step 2: Build Docker images ----
echo "[2/4] Building Docker images..."
cd "$PROJECT_ROOT"
docker build -t "$BACKEND_IMAGE" -f Dockerfile .
echo "  Built: ${BACKEND_IMAGE}"

if [ -f "$FRONTEND_DIR/Dockerfile.prod" ]; then
  docker build -t "$FRONTEND_IMAGE" -f "$FRONTEND_DIR/Dockerfile.prod" "$FRONTEND_DIR"
elif [ -f "$FRONTEND_DIR/Dockerfile" ]; then
  docker build -t "$FRONTEND_IMAGE" -f "$FRONTEND_DIR/Dockerfile" "$FRONTEND_DIR"
else
  echo "  WARN: No frontend Dockerfile found, skipping frontend image build."
  FRONTEND_IMAGE=""
fi

if [ -n "$FRONTEND_IMAGE" ]; then
  echo "  Built: ${FRONTEND_IMAGE}"
fi

# ---- Step 3: Push to registry (if configured) ----
if [ -n "$REGISTRY" ]; then
  echo "[3/4] Pushing images to registry: ${REGISTRY}..."
  REMOTE_BACKEND="${REGISTRY}/${BACKEND_IMAGE}"
  docker tag "$BACKEND_IMAGE" "$REMOTE_BACKEND"
  docker push "$REMOTE_BACKEND"
  echo "  Pushed: ${REMOTE_BACKEND}"

  if [ -n "$FRONTEND_IMAGE" ]; then
    REMOTE_FRONTEND="${REGISTRY}/${FRONTEND_IMAGE}"
    docker tag "$FRONTEND_IMAGE" "$REMOTE_FRONTEND"
    docker push "$REMOTE_FRONTEND"
    echo "  Pushed: ${REMOTE_FRONTEND}"
  fi
else
  echo "[3/4] No registry configured, skipping push."
fi

# ---- Step 4: Deploy with docker compose ----
echo "[4/4] Deploying with docker compose..."
cd "$PROJECT_ROOT"
if [ -f "$COMPOSE_FILE" ]; then
  docker compose -f "$COMPOSE_FILE" up -d --build
  echo "  Deployed successfully."
else
  echo "  WARN: ${COMPOSE_FILE} not found. Skipping compose deploy."
  echo "  You can run manually: docker compose up -d"
fi

echo ""
echo "=== Deploy complete ==="

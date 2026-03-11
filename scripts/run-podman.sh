#!/bin/bash
# Run Easy Convert API with Podman (development mode)
# Includes Redis container

set -e

# Configuration
IMAGE_NAME="easy-convert-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_NAME="easy-convert-api"
REDIS_CONTAINER="easy-convert-redis"
NETWORK_NAME="easy-convert-network"
API_PORT="${API_PORT:-8000}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "🚀 Starting Easy Convert API with Podman"
echo ""

# Create network if it doesn't exist
if ! podman network exists "${NETWORK_NAME}" 2>/dev/null; then
    echo "📡 Creating network: ${NETWORK_NAME}"
    podman network create "${NETWORK_NAME}"
fi

# Stop and remove existing containers if they exist
if podman container exists "${REDIS_CONTAINER}" 2>/dev/null; then
    echo "🛑 Stopping existing Redis container..."
    podman stop "${REDIS_CONTAINER}" || true
    podman rm "${REDIS_CONTAINER}" || true
fi

if podman container exists "${CONTAINER_NAME}" 2>/dev/null; then
    echo "🛑 Stopping existing API container..."
    podman stop "${CONTAINER_NAME}" || true
    podman rm "${CONTAINER_NAME}" || true
fi


# Start Redis
echo "🔴 Starting Redis..."
podman run -d \
    --name "${REDIS_CONTAINER}" \
    --network "${NETWORK_NAME}" \
    -p "${REDIS_PORT}:6379" \
    --health-cmd "redis-cli ping" \
    --health-interval 10s \
    --health-timeout 5s \
    --health-retries 5 \
    docker.io/library/redis:7-alpine \
    redis-server --appendonly yes

# Wait for Redis to be healthy
echo "⏳ Waiting for Redis to be healthy..."
timeout=30
elapsed=0
until [ "$(podman inspect --format='{{.State.Health.Status}}' ${REDIS_CONTAINER})" == "healthy" ]; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Redis failed to start within ${timeout} seconds"
        exit 1
    fi
done
echo "✅ Redis is healthy"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
# Start API
echo "🚀 Starting API..."
podman run -d \
    --name "${CONTAINER_NAME}" \
    --network "${NETWORK_NAME}" \
    -p "${API_PORT}:8000" \
    -e REDIS_HOST="${REDIS_CONTAINER}" \
    -e REDIS_PORT=6379 \
    -e DEBUG=true \
    -e LOG_LEVEL=DEBUG \
    -v /tmp/easy-convert:/tmp/easy-convert:Z \
    --env-file .env.container \
    "${IMAGE_NAME}:${IMAGE_TAG}"

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
timeout=30
elapsed=0
until curl -sf http://localhost:${API_PORT}/health > /dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ $elapsed -ge $timeout ]; then
        echo "❌ API failed to start within ${timeout} seconds"
        echo "📋 Container logs:"
        podman logs "${CONTAINER_NAME}"
        exit 1
    fi
done

echo ""
echo "✅ Easy Convert API is running!"
echo ""
echo "📋 Container Info:"
echo "   API:   http://localhost:${API_PORT}"
echo "   Docs:  http://localhost:${API_PORT}/docs"
echo "   Redis: localhost:${REDIS_PORT}"
echo ""
echo "📊 View logs:"
echo "   podman logs -f ${CONTAINER_NAME}"
echo ""
echo "🛑 Stop containers:"
echo "   ./scripts/stop-podman.sh"

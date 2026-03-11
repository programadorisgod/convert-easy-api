#!/bin/bash
# Stop Easy Convert API containers

set -e

CONTAINER_NAME="easy-convert-api"
REDIS_CONTAINER="easy-convert-redis"

echo "🛑 Stopping Easy Convert API containers"
echo ""

# Stop API
if podman container exists "${CONTAINER_NAME}" 2>/dev/null; then
    echo "Stopping ${CONTAINER_NAME}..."
    podman stop "${CONTAINER_NAME}"
    podman rm "${CONTAINER_NAME}"
    echo "✅ API stopped"
else
    echo "⚠️  API container not running"
fi

# Stop Redis
if podman container exists "${REDIS_CONTAINER}" 2>/dev/null; then
    echo "Stopping ${REDIS_CONTAINER}..."
    podman stop "${REDIS_CONTAINER}"
    podman rm "${REDIS_CONTAINER}"
    echo "✅ Redis stopped"
else
    echo "⚠️  Redis container not running"
fi

echo ""
echo "✅ All containers stopped"

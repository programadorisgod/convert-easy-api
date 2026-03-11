#!/bin/bash
# Build script for Easy Convert API using Podman
# Podman is Docker-compatible and can run rootless

set -e

# Configuration
IMAGE_NAME="easy-convert-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🏗️  Building Easy Convert API with Podman"
echo "Image: ${FULL_IMAGE}"
echo ""


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
# Build using Containerfile  (using buildash)
echo "📦 Building image..."
podman build \
    --format docker \
    --tag "${FULL_IMAGE}" \
    --file Containerfile \
    --layers \
    .
echo ""
echo "✅ Build complete: ${FULL_IMAGE}"
echo ""

# Show image info
podman images | grep "${IMAGE_NAME}" || true

echo ""
echo "🚀 To run the container:"
echo "   ./scripts/run-podman.sh"
echo ""
echo "💾 To save image:"
echo "   podman save -o ${IMAGE_NAME}.tar ${FULL_IMAGE}"

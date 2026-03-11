#!/bin/bash
# Run tests with coverage

set -e

echo "🧪 Running Easy Convert API tests"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Starting Redis..."
    if command -v podman &> /dev/null; then
        podman run -d --name test-redis -p 6379:6379 redis:7-alpine
    elif command -v docker &> /dev/null; then
        docker run -d --name test-redis -p 6379:6379 redis:7-alpine
    else
        echo "❌ Neither podman nor docker found. Please start Redis manually."
        exit 1
    fi
    sleep 2
fi



SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  uv venv
fi

# Activate venv
source .venv/bin/activate

echo "📦 Installing test dependencies..."
uv pip install pytest pytest-asyncio pytest-cov httpx

echo ""
echo "🧪 Running tests..."


# Run tests with coverage
pytest \
    tests/ \
    -v \
    --cov=src \
    --cov=shared \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    "$@"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
    echo ""
    echo "📊 Coverage report: htmlcov/index.html"
else
    echo "❌ Some tests failed"
fi

exit $EXIT_CODE

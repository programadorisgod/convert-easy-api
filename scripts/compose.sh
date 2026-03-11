#!/bin/bash
# Docker Compose convenience script

set -e

ACTION="${1:-up}"

case "$ACTION" in
    up)
        echo "🚀 Starting services with docker-compose..."
        docker-compose up -d
        echo ""
        echo "✅ Services started!"
        echo "   API:  http://localhost:8000"
        echo "   Docs: http://localhost:8000/docs"
        ;;
    down)
        echo "🛑 Stopping services..."
        docker-compose down
        echo "✅ Services stopped"
        ;;
    logs)
        docker-compose logs -f
        ;;
    restart)
        echo "🔄 Restarting services..."
        docker-compose restart
        echo "✅ Services restarted"
        ;;
    build)
        echo "🏗️  Building images..."
        docker-compose build
        echo "✅ Build complete"
        ;;
    *)
        echo "Usage: $0 {up|down|logs|restart|build}"
        exit 1
        ;;
esac

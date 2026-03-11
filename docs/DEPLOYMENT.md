# 🚀 Deployment Guide

Easy Convert API deployment guide for Podman, Buildah, and Docker Compose.

## Prerequisites

### Option 1: Podman & Buildah (Recommended - Rootless)
```bash
# Fedora/RHEL
sudo dnf install podman buildah

# Ubuntu/Debian
sudo apt install podman buildah

# macOS
brew install podman
```

### Option 2: Docker & Docker Compose
```bash
# Install Docker Desktop or Docker Engine
# https://docs.docker.com/get-docker/
```

## Quick Start

### Using Podman (Rootless, Daemonless)

```bash
# 1. Build image
./scripts/build-podman.sh

# 2. Run containers (API + Redis)
./scripts/run-podman.sh

# 3. Access API
curl http://localhost:8000/health
open http://localhost:8000/docs

# 4. View logs
podman logs -f easy-convert-api

# 5. Stop containers
./scripts/stop-podman.sh
```

### Using Buildah (Build-only tool)

```bash
# Build optimized container image
./scripts/build-buildah.sh

# Run with podman
./scripts/run-podman.sh
```

### Using Docker Compose

```bash
# Start all services
./scripts/compose.sh up

# View logs
./scripts/compose.sh logs

# Stop services
./scripts/compose.sh down

# Rebuild
./scripts/compose.sh build
```

## Configuration

### Environment Variables

Copy `.env.container` to `.env` and customize:

```bash
cp .env.container .env
```

Key settings:
- `REDIS_HOST`: Redis hostname (default: `redis` in compose, `localhost` standalone)
- `MAX_FILE_SIZE`: Maximum file size in bytes (default: 100MB)
- `WORKER_CONCURRENCY`: Number of concurrent conversion workers (default: 4)
- `STORAGE_BASE_PATH`: Temporary storage path (default: `/tmp/easy-convert`)

### Storage

Containers use `/tmp/easy-convert` for temporary file storage. To persist or customize:

```bash
# Create custom storage directory
mkdir -p /my/custom/storage

# Run with custom volume
podman run -d \
  ... \
  -v /my/custom/storage:/tmp/easy-convert:Z \
  easy-convert-api:latest
```

## Architecture

```
┌────────────────┐
│   Client       │
└───────┬────────┘
        │ HTTP/WebSocket
        ▼
┌────────────────┐
│  FastAPI App   │ :8000
│  - Upload API  │
│  - Job API     │
│  - WebSocket   │
└───────┬────────┘
        │
        ▼
┌────────────────┐     ┌──────────────┐
│     Redis      │────▶│  BullMQ      │
│  Event Store   │     │  Worker      │
└────────────────┘     └──────┬───────┘
     :6379                    │
                              ▼
                      ┌──────────────┐
                      │ ImageMagick  │
                      │  Converter   │
                      └──────────────┘
```

## Multi-Architecture Support

Build for different platforms:

```bash
# ARM64 (Apple Silicon, Raspberry Pi)
podman build --platform linux/arm64 -t easy-convert-api:arm64 .

# AMD64 (x86_64)
podman build --platform linux/amd64 -t easy-convert-api:amd64 .

# Multi-arch manifest
podman manifest create easy-convert-api:latest
podman manifest add easy-convert-api:latest easy-convert-api:arm64
podman manifest add easy-convert-api:latest easy-convert-api:amd64
```

## Production Deployment

### Kubernetes

```yaml
apiVersion: v1
kind: Service
metadata:
  name: easy-convert-api
spec:
  selector:
    app: easy-convert-api
  ports:
    - port: 8000
      targetPort: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: easy-convert-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: easy-convert-api
  template:
    metadata:
      labels:
        app: easy-convert-api
    spec:
      containers:
      - name: api
        image: easy-convert-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_HOST
          value: "redis-service"
        - name: WORKER_CONCURRENCY
          value: "4"
        volumeMounts:
        - name: tmp-storage
          mountPath: /tmp/easy-convert
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
      volumes:
      - name: tmp-storage
        emptyDir: {}
```

### Systemd Service (Podman)

```ini
# /etc/systemd/system/easy-convert-api.service
[Unit]
Description=Easy Convert API
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/easy-convert-api
ExecStartPre=/usr/bin/podman pull easy-convert-api:latest
ExecStart=/opt/easy-convert-api/scripts/run-podman.sh
ExecStop=/opt/easy-convert-api/scripts/stop-podman.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable easy-convert-api
sudo systemctl start easy-convert-api
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "service": "Easy Convert API",
  "version": "1.0.0"
}
```

### Container Stats

```bash
# Podman
podman stats easy-convert-api

# Docker
docker stats easy-convert-api
```

### Logs

```bash
# Follow logs
podman logs -f easy-convert-api

# Last 100 lines
podman logs --tail 100 easy-convert-api

# With timestamps
podman logs --timestamps easy-convert-api
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
API_PORT=8080 ./scripts/run-podman.sh
```

### ImageMagick Policy Errors

If you get "not authorized" errors, check ImageMagick policy:

```bash
# Inside container
podman exec -it easy-convert-api cat /etc/ImageMagick-6/policy.xml
```

### Redis Connection Issues

```bash
# Check Redis is running
podman ps | grep redis

# Test Redis connection
podman exec easy-convert-redis redis-cli ping
```

### Container Won't Start

```bash
# Check logs
podman logs easy-convert-api

# Inspect container
podman inspect easy-convert-api

# Run interactive shell
podman run -it --rm easy-convert-api:latest /bin/bash
```

## Security

### Non-root User

Container runs as non-root user `appuser` (UID 1000) for security.

### SELinux

When using volumes on SELinux systems, use `:Z` flag:

```bash
-v /path/on/host:/tmp/easy-convert:Z
```

### Networks

Containers use dedicated network `easy-convert-network` for isolation.

## Backup & Restore

### Export Container

```bash
# Save image
podman save -o easy-convert-api.tar easy-convert-api:latest

# Load image
podman load -i easy-convert-api.tar
```

### Redis Data

```bash
# Backup Redis data
podman exec easy-convert-redis redis-cli BGSAVE
podman cp easy-convert-redis:/data/dump.rdb ./backup/

# Restore
podman cp ./backup/dump.rdb easy-convert-redis:/data/
podman restart easy-convert-redis
```

## Performance Tuning

### Worker Concurrency

Adjust based on CPU cores:
```bash
# .env
WORKER_CONCURRENCY=8  # For 8-core CPU
```

### Redis Memory

```bash
# Limit Redis memory
podman run -d \
  --name easy-convert-redis \
  redis:7-alpine \
  redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### File Upload Limits

```bash
# .env
MAX_FILE_SIZE=209715200  # 200MB
MAX_CHUNK_SIZE=20971520  # 20MB chunks
```

# Easy Convert API

**Privacy-focused file conversion API built with FastAPI**

> Conversión de archivos privada, sin rastro, sin compromisos.

## Overview

Easy Convert is a file conversion service designed with privacy as the core principle. Files are processed in memory, converted, and immediately deleted. No persistent storage, no content logging, no file analysis. The server doesn't know what's inside your documents.

### Phase 1: Image Conversion ✅ (In Progress)

Convert images between 200+ formats using ImageMagick with automatic EXIF stripping for privacy.

**Supported Formats:**
- **Input**: JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, SVG  
- **Output**: JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF

## Architecture

This project follows **Clean Architecture** with **Event Sourcing**:

```
src/
├── domain/          # Core business logic (framework-agnostic)
│   └── job/        # Job aggregate, events, status
├── application/     # Use cases (commands, handlers, services)
├── infrastructure/  # External concerns (Redis, file storage, workers)
├── interfaces/      # API layer (HTTP controllers, WebSocket)
└── shared/         # Cross-cutting concerns
```

## Tech Stack

- **FastAPI** - Async Python web framework
- **Pydantic v2** - Data validation and settings
- **Redis** - Job queue and state storage
- **WebSockets** - Real-time job status notifications
- **ImageMagick** - Image conversion CLI
- **Podman** - Rootless containerization

## Getting Started

### Prerequisites

- Python 3.11+
- Redis server
- ImageMagick (for image conversion)
- Podman (for containerization)

### Installation

1. **Clone the repository**

```bash
cd easy_convert_api
```

2. **Install dependencies with uv**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

3. **Set up environment**

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start Redis** (if not already running)

```bash
redis-server
```

### Running the API

#### Development Mode

```bash
# Using FastAPI CLI (recommended)
uv run fastapi dev

# Or using uvicorn directly
uv run uvicorn src.main:app --reload --port 8000
```

#### Production Mode

```bash
uv run fastapi run
```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Project Status

### ✅ Completed

- [x] Project structure with Clean Architecture
- [x] Domain layer (Job aggregate, events, status)
- [x] Shared layer (exceptions, config, event bus, queue port)
- [x] FastAPI app initialization
- [x] Redis integration setup
- [x] Lifespan management

### 🚧 In Progress

- [ ] Infrastructure layer (file storage, queue adapter, worker)
- [ ] Application layer (commands, handlers, services)
- [ ] Interface layer (HTTP controllers, WebSocket gateway)
- [ ] ImageMagick integration
- [ ] Testing suite

### 📋 Planned

- [ ] Podman containerization
- [ ] Buildah build scripts
- [ ] Comprehensive documentation
- [ ] Performance benchmarks

## Development

### Project Structure

```
easy_convert_api/
├── src/
│   ├── domain/job/          # Domain entities, events, logic
│   ├── application/job/     # Commands, handlers, services
│   ├── infrastructure/      # Queue, storage, persistence, workers
│   ├── interfaces/          # HTTP & WebSocket endpoints
│   ├── main.py             # FastAPI app
│   └── lifespan.py         # App lifecycle management
├── shared/
│   ├── config/             # Settings and configuration
│   ├── events/             # Event bus
│   ├── queue/              # Queue abstractions
│   └── exceptions.py       # Custom exceptions
├── tests/                  # Test suite
├── pyproject.toml         # Project dependencies
└── .env.example          # Environment template
```

### Running Tests

```bash
uv run pytest
```

### Code Quality

The project follows Clean Code principles:
- Meaningful names
- Small, focused functions
- Single Responsibility Principle
- Dependency injection
- Type hints throughout

## API Flow

### Small Files (<10MB)

```
1. POST /api/v1/convert (file + target_format)
2. → Returns job_id
3. Connect to ws://host/api/v1/ws/jobs/{job_id}
4. Receive: job:started, job:completed
5. GET /api/v1/jobs/{job_id}/download
```

### Large Files (>10MB) - Chunked Upload

```
1. POST /api/v1/upload/chunk (chunk + metadata) × N
2. POST /api/v1/upload/assemble (file_id + target_format)
3. → Returns job_id
4. Connect to WebSocket for status updates
5. Download converted file
```

## Privacy Guarantees

- ✅ Files stored only in `/tmp` with random UUID names
- ✅ EXIF metadata stripped from images
- ✅ Immediate deletion post-download
- ✅ No logging of file content or names
- ✅ Job metadata expires after 24 hours
- ✅ Event sourcing provides audit without storing files

## Configuration

Key environment variables (see `.env.example`):

- `MAX_FILE_SIZE_MB` - Maximum file size (default: 100MB)
- `JOB_TTL_HOURS` - Job metadata retention (default: 24h)
- `REDIS_URL` - Redis connection URL
- `TEMP_DIR` - Temporary file storage location

## License

[To be determined]

## Contributing

[To be determined]

---

**Built with privacy in mind. Your files, your business.**

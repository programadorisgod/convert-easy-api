# Easy Convert API

**Privacy-focused file conversion API built with FastAPI**

> Conversión de archivos privada, sin rastro, sin compromisos.

## Overview

Easy Convert is a file conversion service designed with privacy as the core principle. Files are processed in memory, converted, and immediately deleted. No persistent storage, no content logging, no file analysis. The server doesn't know what's inside your documents.

### Phase 1: Advanced Image Processing ✅ **COMPLETE**

Full-featured image processing with privacy-first approach: format conversion, background removal, intelligent compression, and watermarking through **individual endpoints**.

**Core Features:**
- ✅ **200+ Format Conversions** - ImageMagick powered (JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, SVG)
- ✅ **Background Removal** - AI-powered with rembg (U2Net/BRIA models, 100% local) - `POST /process/remove-background`
- ✅ **Smart Compression** - 3 levels (low/balanced/strong), 30-90% reduction with mozjpeg/oxipng/pngquant - `POST /process/compress`
- ✅ **Watermarking** - Text & logo support, 6 positions + diagonal, opacity control - `POST /process/watermark`
- ✅ **Privacy Guaranteed** - Auto EXIF stripping, local processing, no external APIs
- ✅ **File Upload Flow** - Direct upload <10MB, chunked >10MB (frontend-handled)

**Architecture:** Individual endpoints for maximum flexibility - apply only the operations you need.

**📖 Full Documentation**: [docs/FASE_1_IMAGE_PROCESSING.md](docs/FASE_1_IMAGE_PROCESSING.md)

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

### Core Framework
- **FastAPI** - Async Python web framework with OpenAPI
- **Pydantic v2** - Data validation and settings
- **Redis** - Event store and job queue backend
- **BullMQ** - Distributed job queue system
- **WebSockets** - Real-time job status notifications

### Image Processing Tools
- **ImageMagick 7+** - Format conversion, cropping, watermarking
- **Quick Start with Docker/Podman (Recommended)

All image processing tools pre-installed:

```bash
# 1. Start services with docker-compose
docker-compose up -d

# 2. API available at http://localhost:8000
curl http://localhost:8000/health

# 3. View API docs
open http://localhost:8000/docs
```

### Manual Installation (Development)

#### Prerequisites

- Python 3.11+
- Redis server
- ImageMagick 7+
- Image processing tools (see [Containerfile](Containerfile) for installation)

#### Installation

1. **Install system dependencies**

```bash
# Ubuntu/Debian
sudo apt-get install -y \
  imagemagick \
  jpegoptim \
  pngquant \
  git \
  cmake \
  nasm \
  wget

# Build mozjpeg from source
git clone https://github.com/mozilla/mozjpeg.git
cd mozjpeg && mkdir build && cd build
cmake -G"Unix Makefiles" -DCMAKE_INSTALL_PREFIX=/opt/mozjpeg ..
make && sudo make install

# Download oxipng
wget https://github.com/shssoichiro/oxipng/releases/download/v9.1.2/oxipng-9.1.2-x86_64-unknown-linux-musl.tar.gz
tar xzf oxipng* && sudo mv oxipng /usr/local/bin/
```

2. **Install Python dependencies**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml

# Or install with extras
uv pip install ".[dev]"
```

3. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your Redis URL and settings
```

4. **Start Redis**

```bash
redis-server --appendonly yes
```

### Running the API

#### Development Mode

```bash
# 1. Start API
uv run fastapi dev

# 2. Start worker (separate terminal)
uv run python src/infrastructure/worker/conversion_worker.py
```

#### Production Mode

```bash
# Using Podman (recommended)
./scripts/compose.sh up -d

# Or using Docker Compose
docker-compose up -dode

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

### ✅ Phase 1 Complete: Advanced Image Processing

- [x] Clean Architecture foundation
- [x] Domain layer with Event Sourcing (Job aggregate, 10+ event types)
- [x] Shared layer (exceptions, config, event bus, queue abstractions)
- [x] Infrastructure layer (Redis persistence, BullMQ queue, file storage, conversion worker)
- [x] Application layer (6 commands, 6 handlers, process image pipeline)
- [x] Interface layer (HTTP REST API, image processing endpoint)
- [x] **Background Removal** - rembg with U2Net model, alpha matting support
- [x] **Smart Compression** - 3 levels, multi-tool strategy (mozjpeg, oxipng, pngquant, jpegoptim)
- [x] **Watermarking** - Text & logo, 6 positions, opacity control
- [x] **Advanced Cropping** - 4 modes (coordinates, aspect ratio, square, auto)
- [x] **Image Processing Pipeline** - Orchestrates: bg_removal → crop → convert → compress → watermark
- [x] FastAPI app with OpenAPI documentation
- [x] Redis integration (queue + event store)
- [x] Lifespan management
- [x] **Comprehensive Test Suite** - 62 tests (27 unit + 15 integration + 20 E2E)
- [xBasic Image Conversion

```bash
# 1. Create conversion job
curl -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{
    "input_format": "jpg",
    "output_formats": ["webp"],
    "original_size": 1000000
  }'
# → Returns: {"job_id": "abc123-..."}

# 2. Upload file
curl -X POST http://localhost:8000/api/v1/upload/abc123/file \
  -F "file=@image.jpg"

# 3. Download converted file
curl http://localhost:8000/api/v1/jobs/abc123/download -o output.webp
```

### Advanced Image Processing (Phase 1)

```bash
# Full pipeline: remove background + crop + compress + watermark
curl -X POST http://localhost:8000/api/v1/process/image \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "abc123",
    "output_format": "png",
    "remove_background": true,
    "background_model": "u2net",
    "crop": {
      "mode": "square",
      "square_size": 1080
    },
    "compress": true,
    "compression_level": "balanced",
    "watermark": {
      "type": "text",
      "text": "© 2026 Brand",
      "position": "bottom-right",
      "opacity": 0.7
    }
  }'
# → Returns: 202 Accepted with pipeline config
```

**📖 Complete API Documentation**:
- [Phase 1 Examples](docs/FASE_1_IMAGE_PROCESSING.md) - All image processing features
- [Swagger UI](http://localhost:8000/docs) - Interactive API explorer
- [ReDoc](http://localhost:8000/redoc) - Detailed API reference
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

**Complete test suite with 62 tests** covering all Phase 1 features.

```bash
# Run all tests (requires container environment)
./scripts/run-tests.sh

# Or with docker-compose
docker-compose run --rm api pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v                    # 27 unit tests
pytest tests/integration/test_pipeline.py -v  # 15 pipeline tests
pytest tests/integration/test_api_image_processing.py -v  # 20 E2E tests

# With coverage report
pytest tests/ --cov=src --cov=shared --cov-report=html
open htmlcov/index.html
```

**📖 Full Testing Guide**: [docs/TESTING.md](docs/TESTING.md)

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

### Core Privacy Principles

- ✅ **Zero Persistent Storage** - Files stored only in `/tmp` with random UUID names
- ✅ **Metadata Stripping** - EXIF, IPTC, XMP automatically removed from all images
- ✅ **Immediate Deletion** - Files deleted immediately after download or conversion
- ✅ **No Content Logging** - Zero logging of file content, original names, or user data
- ✅ **Local Processing** - 100% local AI/compression (rembg, mozjpeg) - no external APIs
- ✅ **Event Sourcing Audit** - Complete processing history without storing files
- ✅ **Time-Limited Metadata** - Job metadata auto-expires after 24 hours
- ✅ **Memory-Safe Operations** - Async processing with proper cleanup
- ✅ **No Analytics** - Zero tracking, cookies, or user profiling

### What We DON'T Store

- ❌ Original file content
- ❌ File names (only job IDs)
- ❌ EXIF/GPS metadata
- ❌ User IP addresses
- ❌ Processing parameters after job completion
- ❌ Download history

### What We DO Store (Temporarily)

- ✅ Job ID (UUID v4)
- ✅ Job status (queued/processing/completed/failed)
- ✅ File size and format
- ✅ Processing events (for debugging)
- ✅ Expires after: **24 hours**

**Your files, your business. Zero compromise on privacy.**

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

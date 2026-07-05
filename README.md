# Easy Convert API

**Privacy-focused file conversion API built with FastAPI**

> Conversión de archivos privada, sin rastro, sin compromisos.

## Overview

Easy Convert is a file conversion service designed with privacy as the core principle. Files are processed in memory, converted, and immediately deleted. No persistent storage, no content logging, no file analysis. The server doesn't know what's inside your documents.

### What It Does

| Category | What | Formats |
|----------|------|---------|
| **Images** | Convert, compress, remove BG, watermark, crop | JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, SVG, +200 via ImageMagick |
| **Audio** | Convert, normalize volume, trim, bitrate/channels | MP3, WAV, FLAC, OGG, M4A, AAC, WMA, OPUS, AC3, AIFF |
| **Video** | Convert, compress (CRF/resolution/FPS), trim, extract/remove audio | MP4, WebM, AVI, MKV, MOV, GIF, OGG, FLV, TS |
| **PDF** | Merge, split, extract, delete/rotate pages, encrypt/decrypt, add text/image, draw, annotate | PDF |
| **Documents** | Convert between formats via Pandoc/LibreOffice | DOCX, PDF, ODT, EPUB, Markdown, HTML, LaTeX, and 30+ more |
| **XML** | Convert to JSON, YAML, HTML; transform via XSLT | XML |

### Docs Per Feature

- **📷 Images**: [docs/FASE_1_IMAGE_PROCESSING.md](docs/FASE_1_IMAGE_PROCESSING.md)
- **📄 Documents/PDF/XML**: [docs/FASE_2_DOCUMENT_PROCESSING.md](docs/FASE_2_DOCUMENT_PROCESSING.md)

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

### Quick Start with Docker/Podman (Recommended)

All processing tools pre-installed in the container:

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
docker-compose up -d

# Or using FastAPI CLI directly
uv run fastapi run
```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Project Status

### ✅ Phase 1: Advanced Image Processing
*Full docs: [docs/FASE_1_IMAGE_PROCESSING.md](docs/FASE_1_IMAGE_PROCESSING.md)*

- [x] **200+ Format Conversions** - ImageMagick: JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, SVG
- [x] **Background Removal** - AI-powered with rembg (U2Net, 100% local)
- [x] **Smart Compression** - 3 levels (low/balanced/strong), mozjpeg/oxipng/pngquant/jpegoptim
- [x] **Watermarking** - Text & logo, 6 positions + diagonal, opacity control
- [x] **Advanced Cropping** - 4 modes (coordinates, aspect ratio, square, auto)
- [x] **Privacy Guaranteed** - Auto EXIF stripping, local processing, no external APIs

### ✅ Phase 2: Document Processing
*Full docs: [docs/FASE_2_DOCUMENT_PROCESSING.md](docs/FASE_2_DOCUMENT_PROCESSING.md)*

- [x] **PDF Manipulation** — Merge, split, extract pages, rotate, metadata, encrypt/decrypt, add text/image, annotations, draw rectangles, adjustable layout
- [x] **Document Conversion** — Pandoc + LibreOffice engines, auto-selection via MIME validation
- [x] **XML Conversion** — XML → JSON / YAML / HTML / XSLT transform
- [x] **Audio Conversion (FFmpeg)** — 10 input → 7 output, bitrate/sample rate/channels/trim/volume
- [x] **Video Conversion (FFmpeg)** — 10 input → 8 output, CRF/resolution/FPS/trim/extract/remove audio
- [ ] Video Phase 2 (codec selection, watermark, ffprobe) — spec complete, pending

### Common Infrastructure
- [x] **File Upload Workflow** — Create job → Upload (<10MB direct, >10MB chunked) → Start conversion
- [x] **Job Management** — Status check, cancel, download (file deleted after download)
- [x] **Redis + BullMQ** — Event store, job queue, persistence
- [x] **69+ Tests** — Unit + Integration across all phases
- [x] **OpenAPI Docs** — Swagger UI + ReDoc auto-generated

## API Examples

### 1. Upload & Convert Flow (all file types)

```bash
# 1. Create job
curl -X POST http://localhost:8000/api/v1/upload/create \
  -H "Content-Type: application/json" \
  -d '{
    "input_format": "jpg",
    "output_formats": ["webp"],
    "original_size": 1000000
  }'
# → {"job_id": "abc123-...", "file_id": "..."}

# 2. Upload file
curl -X POST http://localhost:8000/api/v1/upload/abc123/file \
  -F "file=@image.jpg"

# 3. Start conversion
curl -X POST http://localhost:8000/api/v1/upload/abc123/start

# 4. Check status
curl http://localhost:8000/api/v1/jobs/abc123

# 5. Download result (auto-deleted after download)
curl http://localhost:8000/api/v1/jobs/abc123/download -o output.webp
```

### 2. Image Processing (Phase 1)

```bash
# Full pipeline: remove BG + crop + compress + watermark
curl -X POST http://localhost:8000/api/v1/process/image \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "abc123",
    "output_format": "png",
    "remove_background": true,
    "crop": {"mode": "square", "square_size": 1080},
    "compress": true, "compression_level": "balanced",
    "watermark": {"type": "text", "text": "© 2026 Brand", "position": "bottom-right", "opacity": 0.7}
  }'
# → 202 Accepted with pipeline config
```

### 3. Audio Conversion (FFmpeg)

```bash
curl -X POST http://localhost:8000/api/v1/process/audio \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "output_format": "mp3", "bitrate": "192k", "channels": 2}'
# → 202 Accepted
```

### 4. Video Conversion (FFmpeg)

```bash
# Convert format
curl -X POST http://localhost:8000/api/v1/process/video \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "output_format": "mkv", "crf": 23, "resolution": "1920:1080"}'

# Extract audio
curl -X POST http://localhost:8000/api/v1/process/video \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "output_format": "mp3", "extract_audio": true, "audio_output_format": "mp3", "audio_bitrate": "192k"}'

# Remove audio track
curl -X POST http://localhost:8000/api/v1/process/video \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "output_format": "mp4", "remove_audio": true}'
```

### 5. PDF Processing (13 operations)

```bash
# Merge PDFs
curl -X POST http://localhost:8000/api/v1/process/pdf/merge \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "source_job_ids": ["pdf2", "pdf3"]}'

# Split pages (range)
curl -X POST http://localhost:8000/api/v1/process/pdf/split-range \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "start_page": 1, "end_page": 5}'

# Encrypt
curl -X POST http://localhost:8000/api/v1/process/pdf/encrypt \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "user_password": "secret123", "owner_password": "admin456"}'

# Full list: merge, split-range, extract-pages, delete-pages, rotate, metadata,
#            encrypt, decrypt, add-text, add-image, draw-rectangle, add-annotation, set-mediabox
```

### 6. XML Conversion

```bash
# XML to JSON
curl -X POST http://localhost:8000/api/v1/convert/xml/json \
  -F "file=@data.xml" \
  -F "preserve_attributes=true"

# XML to YAML
curl -X POST http://localhost:8000/api/v1/convert/xml/yaml \
  -F "file=@data.xml" \
  -F "indent=2"

# XML to HTML (with template)
curl -X POST http://localhost:8000/api/v1/convert/xml/html \
  -F "file=@data.xml" \
  -F "template=table" \
  -F "title=My Data"
```

### 7. Document Processing (Pandoc/LibreOffice)

```bash
curl -X POST http://localhost:8000/api/v1/process/document \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "output_format": "pdf", "preferred_engine": "auto"}'
```

### 8. Job Management

```bash
# Status
curl http://localhost:8000/api/v1/jobs/abc123

# Cancel
curl -X POST http://localhost:8000/api/v1/jobs/abc123/cancel \
  -H "Content-Type: application/json" \
  -d '{"reason": "user-requested"}'

# Download (file deleted after download)
curl http://localhost:8000/api/v1/jobs/abc123/download -o result.pdf
```

**📖 API Reference**: [Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc)
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

**Complete test suite with 69 tests** covering all phases.

```bash
# Run all tests (unit + integration, requires FFmpeg)
uv run pytest tests/ -v

# Run without integration tests (no FFmpeg needed)
uv run pytest tests/ --ignore=tests/test_audio_integration.py --ignore=tests/test_video_integration.py -v

# Run specific converter tests
uv run pytest tests/test_video_converter.py -v  # 34 video unit tests
uv run pytest tests/test_audio_converter.py -v  # audio unit tests
uv run pytest tests/test_image_converter.py -v  # image unit tests

# With coverage report
uv run pytest tests/ --cov=src --cov=shared --cov-report=html
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

### Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload/create` | POST | Create job (returns `job_id` + `file_id`) |
| `/upload/{job_id}/file` | POST | Upload complete file (<10MB) |
| `/upload/{job_id}/chunk` | POST | Upload chunk (>10MB, N times) |
| `/upload/{job_id}/merge` | POST | Merge chunks after upload |
| `/upload/{job_id}/start` | POST | Start conversion process |
| `/jobs/{job_id}` | GET | Get job status |
| `/jobs/{job_id}/cancel` | POST | Cancel pending/processing job |
| `/jobs/{job_id}/download` | GET | Download result (auto-deletes) |
| `/process/image` | POST | Full image pipeline |
| `/process/audio` | POST | Audio conversion |
| `/process/video` | POST | Video conversion |
| `/process/pdf/*` | POST | 13 PDF operations (merge, split, encrypt...) |
| `/process/document` | POST | Document conversion (auto engine) |
| `/convert/xml/*` | POST | XML → JSON/YAML/HTML/XSLT |

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

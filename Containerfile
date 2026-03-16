# Containerfile for Easy Convert API
# Compatible with Podman and Buildah
# Multi-stage build for smaller image size

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    nasm \
    pkg-config \
    git \
    wget \
    tar \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Install Python dependencies
RUN uv pip install --system --no-cache .

# Build and install mozjpeg
RUN git clone https://github.com/mozilla/mozjpeg.git /tmp/mozjpeg && \
    cd /tmp/mozjpeg && \
    mkdir build && cd build && \
    cmake -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DENABLE_SHARED=FALSE -DCMAKE_INSTALL_PREFIX=/opt/mozjpeg .. && \
    make -j$(nproc) && \
    make install && \
    rm -rf /tmp/mozjpeg

# Download and install oxipng
RUN wget -q https://github.com/shssoichiro/oxipng/releases/download/v9.1.2/oxipng-9.1.2-x86_64-unknown-linux-musl.tar.gz && \
    tar -xzf oxipng-9.1.2-x86_64-unknown-linux-musl.tar.gz && \
    mv oxipng-9.1.2-x86_64-unknown-linux-musl/oxipng /usr/local/bin/ && \
    rm -rf oxipng-*


# Stage 2: Runtime
FROM python:3.11-slim

# Install image and document processing tools (Phase 1 + Phase 2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    libmagickwand-dev \
    jpegoptim \
    pngquant \
    libreoffice \
    pandoc \
    texlive \
    texlive-xetex \
    libmagic1 \
    zlib1g \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy to allow all operations
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' /etc/ImageMagick-6/policy.xml || true

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /tmp/easy-convert && \
    chown -R appuser:appuser /app /tmp/easy-convert

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy mozjpeg binaries
COPY --from=builder /opt/mozjpeg /opt/mozjpeg

# Add mozjpeg to PATH
ENV PATH="/opt/mozjpeg/bin:${PATH}"

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose API port (Render injects PORT at runtime)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import os, urllib.request; port=os.getenv('PORT','8000'); urllib.request.urlopen(f'http://localhost:{port}/health').read()" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Run FastAPI with uvicorn (bind to Render PORT in a shell-independent way)
CMD ["python3", "-c", "import os, uvicorn; uvicorn.run('src.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '10000')), workers=1)"]

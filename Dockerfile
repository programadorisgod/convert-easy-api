# Dockerfile for Easy Convert API
# Symlink to Containerfile for Render compatibility
# Render looks for Dockerfile by default but supports Containerfile

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Install Python dependencies
RUN uv pip install --system --no-cache .


# Stage 2: Runtime
FROM python:3.11-slim

# Install ImageMagick and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    libmagickwand-dev \
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

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Run FastAPI with uvicorn
CMD ["python3", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

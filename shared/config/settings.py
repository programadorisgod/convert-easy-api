"""Application settings using Pydantic Settings.

Configuration is loaded from environment variables with sensible defaults.
Following the 12-factor app principle: configuration in the environment.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = "Easy Convert API"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://convert-easy.localhost:1355",
        ],
        description="Allowed CORS origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from JSON string if needed."""

        def normalize(origins: list[str]) -> list[str]:
            # CORS origins must not include trailing slash.
            return [origin.strip().rstrip("/") for origin in origins]

        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return normalize(parsed)
            except json.JSONDecodeError:
                # If it's a comma-separated string, split it
                result = [origin.strip() for origin in v.split(",")]
                return normalize(result)

        if isinstance(v, list):
            return normalize(v)

        return v

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    redis_max_connections: int = 10

    # File Upload
    max_file_size_mb: int = Field(default=100, description="Maximum file size in MB")
    chunk_size_mb: int = Field(
        default=5, description="Chunk size for file uploads in MB"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/easy_convert"),
        description="Temporary directory for file processing",
    )

    # Job Processing
    job_ttl_hours: int = Field(default=24, description="Job time-to-live in hours")
    job_cleanup_hours: int = Field(
        default=1, description="Delete completed jobs after this many hours"
    )
    max_conversion_time_seconds: int = Field(
        default=300, description="Maximum time for a single conversion (5 minutes)"
    )
    max_document_conversion_time_seconds: int = Field(
        default=900,
        description="Maximum time for a single document conversion (15 minutes)",
    )

    # Rate Limiting
    rate_limit_uploads_per_hour: int = 100
    rate_limit_concurrent_jobs_per_ip: int = 10

    # Image Conversion (Phase 1)
    supported_image_input_formats: list[str] = Field(
        default=[
            "jpeg",
            "jpg",
            "png",
            "webp",
            "avif",
            "heic",
            "tiff",
            "tif",
            "bmp",
            "gif",
            "svg",
        ],
        description="Supported input image formats",
    )
    supported_image_output_formats: list[str] = Field(
        default=[
            "jpeg",
            "jpg",
            "png",
            "webp",
            "avif",
            "heic",
            "tiff",
            "tif",
            "bmp",
            "gif",
        ],
        description="Supported output image formats (SVG excluded for security)",
    )
    image_quality: int = Field(
        default=85, ge=1, le=100, description="Default image quality for lossy formats"
    )

    # Document Conversion (Phase 2)
    supported_document_input_formats: list[str] = Field(
        default=[
            "pdf",
            "doc",
            "docx",
            "odt",
            "rtf",
            "txt",
            "md",
            "markdown",
            "html",
            "htm",
            "latex",
            "tex",
            "rst",
            "epub",
            "xls",
            "xlsx",
            "ods",
            "csv",
            "tsv",
            "ppt",
            "pptx",
            "odp",
        ],
        description="Supported input document formats",
    )
    supported_document_output_formats: list[str] = Field(
        default=[
            "pdf",
            "docx",
            "odt",
            "rtf",
            "txt",
            "md",
            "markdown",
            "html",
            "latex",
            "tex",
            "epub",
            "xlsx",
            "ods",
            "csv",
            "tsv",
            "pptx",
            "odp",
        ],
        description="Supported output document formats",
    )

    # Worker
    worker_concurrency: int = Field(
        default=4, description="Number of concurrent jobs the worker can process"
    )
    worker_poll_interval_seconds: int = Field(
        default=1, description="How often worker checks for new jobs"
    )

    # Observability
    log_level: str = "INFO"
    structured_logs: bool = True

    def get_temp_dir(self) -> Path:
        """Get temp directory, ensuring it exists."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir

    def is_image_format_supported(
        self, format_name: str, is_output: bool = False
    ) -> bool:
        """Check if image format is supported."""
        format_lower = format_name.lower().lstrip(".")
        formats = (
            self.supported_image_output_formats
            if is_output
            else self.supported_image_input_formats
        )
        return format_lower in formats

    def is_document_format_supported(
        self, format_name: str, is_output: bool = False
    ) -> bool:
        """Check if document format is supported."""
        format_lower = format_name.lower().lstrip(".")
        formats = (
            self.supported_document_output_formats
            if is_output
            else self.supported_document_input_formats
        )
        return format_lower in formats

    def is_format_supported(self, format_name: str, is_output: bool = False) -> bool:
        """Check if format is supported in any conversion family."""
        return self.is_image_format_supported(
            format_name, is_output=is_output
        ) or self.is_document_format_supported(format_name, is_output=is_output)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

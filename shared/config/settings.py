"""Application settings using Pydantic Settings.

Configuration is loaded from environment variables with sensible defaults.
Following the 12-factor app principle: configuration in the environment.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = "Easy Convert API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = 10
    
    # File Upload
    max_file_size_mb: int = Field(
        default=100,
        description="Maximum file size in MB"
    )
    chunk_size_mb: int = Field(
        default=5,
        description="Chunk size for file uploads in MB"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/easy_convert"),
        description="Temporary directory for file processing"
    )
    
    # Job Processing
    job_ttl_hours: int = Field(
        default=24,
        description="Job time-to-live in hours"
    )
    job_cleanup_hours: int = Field(
        default=1,
        description="Delete completed jobs after this many hours"
    )
    max_conversion_time_seconds: int = Field(
        default=300,
        description="Maximum time for a single conversion (5 minutes)"
    )
    
    # Rate Limiting
    rate_limit_uploads_per_hour: int = 100
    rate_limit_concurrent_jobs_per_ip: int = 10
    
    # Image Conversion (Phase 1)
    supported_image_input_formats: list[str] = Field(
        default=[
            "jpeg", "jpg", "png", "webp", "avif", 
            "heic", "tiff", "tif", "bmp", "gif", "svg"
        ],
        description="Supported input image formats"
    )
    supported_image_output_formats: list[str] = Field(
        default=[
            "jpeg", "jpg", "png", "webp", "avif",
            "heic", "tiff", "tif", "bmp", "gif"
        ],
        description="Supported output image formats (SVG excluded for security)"
    )
    image_quality: int = Field(
        default=85,
        ge=1,
        le=100,
        description="Default image quality for lossy formats"
    )
    
    # Worker
    worker_concurrency: int = Field(
        default=4,
        description="Number of concurrent jobs the worker can process"
    )
    worker_poll_interval_seconds: int = Field(
        default=1,
        description="How often worker checks for new jobs"
    )
    
    # Observability
    log_level: str = "INFO"
    structured_logs: bool = True
    
    def get_temp_dir(self) -> Path:
        """Get temp directory, ensuring it exists."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir
    
    def is_image_format_supported(self, format_name: str, is_output: bool = False) -> bool:
        """Check if image format is supported."""
        format_lower = format_name.lower().lstrip('.')
        formats = (
            self.supported_image_output_formats 
            if is_output 
            else self.supported_image_input_formats
        )
        return format_lower in formats


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

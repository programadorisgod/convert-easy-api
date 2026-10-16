"""Centralized logging setup with correlation IDs and rotating file handlers."""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from shared.config.settings import Settings
from src.infrastructure.logging.context import get_job_id, get_request_id


class CorrelationLogFormatter(logging.Formatter):
    """Custom log formatter that injects request_id and job_id into log records."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = get_request_id()
        job_id = get_job_id()

        prefix_parts = []
        if req_id:
            prefix_parts.append(f"[{req_id}]")
        if job_id:
            prefix_parts.append(f"[{job_id}]")

        correlation_prefix = f"{' '.join(prefix_parts)} " if prefix_parts else ""

        original_msg = record.getMessage()
        record.msg = f"{correlation_prefix}{original_msg}"
        formatted = super().format(record)
        record.msg = original_msg
        return formatted


def configure_logging(settings: Settings) -> None:
    """Configure system-wide logging with console and 3-day rotating file handlers."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Formatter
    formatter = CorrelationLogFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handlers (with 3-day retention policy)
    try:
        log_dir = settings.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        retention = max(1, settings.log_retention_days)

        # Main API log: all records >= log_level
        api_log_path = log_dir / "api.log"
        api_file_handler = TimedRotatingFileHandler(
            filename=str(api_log_path),
            when="midnight",
            interval=1,
            backupCount=retention,
            encoding="utf-8",
        )
        api_file_handler.setLevel(log_level)
        api_file_handler.setFormatter(formatter)
        root_logger.addHandler(api_file_handler)

        # Dedicated Errors log: only ERROR and CRITICAL
        error_log_path = log_dir / "errors.log"
        error_file_handler = TimedRotatingFileHandler(
            filename=str(error_log_path),
            when="midnight",
            interval=1,
            backupCount=retention,
            encoding="utf-8",
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        root_logger.addHandler(error_file_handler)

        logging.getLogger(__name__).info(
            f"Logging configured: console + rotating files in '{log_dir}' "
            f"(retention: {retention} days)"
        )
    except Exception as e:
        # If filesystem writes are restricted (e.g. read-only container), fallback to console gracefully
        logging.getLogger(__name__).warning(
            f"Could not initialize rotating file handlers: {e}. Defaulting to console only."
        )

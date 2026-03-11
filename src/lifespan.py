"""Application lifespan management.

Handles startup and shutdown tasks like establishing database connections,
creating temp directories, and cleaning up resources.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from redis.asyncio import Redis

from shared.config import get_settings
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.persistence import JobRepository, initialize_repository
from src.infrastructure.storage.file_storage import FileStorage, get_file_storage
from src.infrastructure.worker import ConversionWorker, start_worker


logger = logging.getLogger(__name__)


class AppState:
    """Application state container."""

    def __init__(self):
        self.redis: Redis | None = None
        self.queue: BullMQAdapter | None = None
        self.repository: JobRepository | None = None
        self.storage: FileStorage | None = None
        self.worker: ConversionWorker | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.

    Startup:
    - Initialize Redis connection
    - Create temp directories
    - Setup event bus subscribers

    Shutdown:
    - Close Redis connection
    - Cleanup temp files (optional)
    """
    settings = get_settings()

    logger.info("🚀 Starting Easy Convert API...")

    # Startup tasks
    try:
        # Create temp directory
        temp_dir = settings.get_temp_dir()
        logger.info(f"📁 Temp directory: {temp_dir}")

        # Initialize Redis connection
        app_state.redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_max_connections,
        )
        await app_state.redis.ping()
        logger.info(f"✅ Redis connected: {settings.redis_url}")

        # Initialize JobRepository
        app_state.repository = initialize_repository(app_state.redis)
        logger.info("✅ JobRepository initialized")

        # Initialize BullMQ queue adapter
        app_state.queue = BullMQAdapter(settings.redis_url)
        logger.info("✅ BullMQ queue adapter initialized")

        # Initialize FileStorage
        app_state.storage = get_file_storage()
        logger.info("✅ FileStorage initialized")

        # Start ConversionWorker
        app_state.worker = await start_worker(
            settings.redis_url, app_state.repository, app_state.storage
        )
        logger.info("✅ ConversionWorker started")

        # Log queue status
        queue_size = await app_state.queue.get_queue_size()
        counts = await app_state.queue.get_job_counts()
        logger.info(
            f"📊 Queue status: {queue_size} pending | "
            f"{counts.get('processing', 0)} processing | "
            f"{counts.get('completed', 0)} completed | "
            f"{counts.get('failed', 0)} failed"
        )

        logger.info("✨ Application started successfully")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        raise

    # Application is running
    yield

    # Shutdown tasks
    logger.info("🛑 Shutting down Easy Convert API...")

    try:
        # Stop worker first
        if app_state.worker:
            await app_state.worker.stop()
            logger.info("✅ ConversionWorker stopped")

        # Close BullMQ queue connection
        if app_state.queue:
            await app_state.queue.close()
            logger.info("✅ BullMQ queue closed")

        # Close Redis connection
        if app_state.redis:
            await app_state.redis.aclose()
            logger.info("✅ Redis connection closed")

        logger.info("👋 Application shut down gracefully")

    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}", exc_info=True)


def get_redis() -> Redis:
    """Get Redis client dependency.

    Returns:
        Redis client instance

    Raises:
        RuntimeError: If Redis is not initialized
    """
    if app_state.redis is None:
        raise RuntimeError("Redis not initialized")
    return app_state.redis


def get_queue() -> BullMQAdapter:
    """Get queue adapter dependency.

    Returns:
        Queue adapter instance

    Raises:
        RuntimeError: If queue is not initialized
    """
    if app_state.queue is None:
        raise RuntimeError("Queue adapter not initialized")
    return app_state.queue


def get_repository() -> JobRepository:
    """Get job repository dependency.

    Returns:
        JobRepository instance

    Raises:
        RuntimeError: If repository is not initialized
    """
    if app_state.repository is None:
        raise RuntimeError("JobRepository not initialized")
    return app_state.repository


def get_storage() -> FileStorage:
    """Get file storage dependency.

    Returns:
        FileStorage instance

    Raises:
        RuntimeError: If storage is not initialized
    """
    if app_state.storage is None:
        raise RuntimeError("FileStorage not initialized")
    return app_state.storage


def get_worker() -> ConversionWorker:
    """Get conversion worker dependency.

    Returns:
        ConversionWorker instance

    Raises:
        RuntimeError: If worker is not initialized
    """
    if app_state.worker is None:
        raise RuntimeError("ConversionWorker not initialized")
    return app_state.worker

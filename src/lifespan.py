"""Application lifespan management.

Handles startup and shutdown tasks like establishing database connections,
creating temp directories, and cleaning up resources.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import FastAPI

from shared.config import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.infrastructure.persistence import JobRepository
    from src.infrastructure.queue import BullMQAdapter
    from src.infrastructure.storage.file_storage import FileStorage
    from src.infrastructure.worker import ConversionWorker


logger = logging.getLogger(__name__)


class AppState:
    """Application state container."""

    def __init__(self):
        self.redis: "Redis | None" = None
        self.queue: "BullMQAdapter | None" = None
        self.repository: "JobRepository | None" = None
        self.storage: "FileStorage | None" = None
        self.worker: "ConversionWorker | None" = None
        self.ready: bool = False


app_state = AppState()


async def _initialize_background() -> None:
    """Initialize heavy dependencies in background after server starts."""
    from redis.asyncio import Redis

    from src.infrastructure.persistence import initialize_repository
    from src.infrastructure.queue import BullMQAdapter
    from src.infrastructure.storage.file_storage import get_file_storage
    from src.infrastructure.worker import start_worker

    settings = get_settings()
    enable_worker = os.getenv("ENABLE_WORKER", "true").lower() == "true"

    try:
        # Initialize FileStorage
        app_state.storage = get_file_storage()
        logger.info("✅ FileStorage initialized")

        # Initialize Redis connection
        try:
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

            # Start ConversionWorker (optional)
            if enable_worker:
                app_state.worker = await start_worker(
                    settings.redis_url, app_state.repository, app_state.storage
                )
                logger.info("✅ ConversionWorker started")
            else:
                logger.info("⚠️ Worker disabled (ENABLE_WORKER=false)")

            # Log queue status if available
            if app_state.queue:
                queue_size = await app_state.queue.get_queue_size()
                counts = await app_state.queue.get_job_counts()
                logger.info(
                    f"📊 Queue status: {queue_size} pending | "
                    f"{counts.get('processing', 0)} processing | "
                    f"{counts.get('completed', 0)} completed | "
                    f"{counts.get('failed', 0)} failed"
                )

        except Exception as redis_error:
            logger.warning(f"⚠️ Redis unavailable: {redis_error}")
            logger.warning("⚠️ App will start without queue/worker functionality")
            app_state.redis = None
            app_state.queue = None
            app_state.repository = None
            app_state.worker = None

        app_state.ready = True
        logger.info("✨ Application fully initialized")

    except Exception as e:
        logger.error(f"❌ Background initialization failed: {e}", exc_info=True)
        app_state.ready = True  # Still mark as ready to serve requests


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.

    Startup:
    - Minimal initialization to bind port quickly
    - Heavy initialization (Redis, worker) runs in background

    Shutdown:
    - Close Redis connection
    - Cleanup temp files
    """
    settings = get_settings()

    logger.info("🚀 Starting Easy Convert API...")

    # Minimal startup - bind port immediately
    temp_dir = settings.get_temp_dir()
    logger.info(f"📁 Temp directory: {temp_dir}")

    # Start heavy initialization in background (non-blocking)
    asyncio.create_task(_initialize_background())

    logger.info("✨ Application started (background initialization in progress)")

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


def get_redis() -> "Redis":
    """Get Redis client dependency."""
    if app_state.redis is None:
        raise RuntimeError("Redis not initialized")
    return app_state.redis


def get_queue() -> "BullMQAdapter":
    """Get queue adapter dependency."""
    if app_state.queue is None:
        raise RuntimeError("Queue adapter not initialized")
    return app_state.queue


def get_repository() -> "JobRepository":
    """Get job repository dependency."""
    if app_state.repository is None:
        raise RuntimeError("JobRepository not initialized")
    return app_state.repository


def get_storage() -> "FileStorage":
    """Get file storage dependency."""
    if app_state.storage is None:
        raise RuntimeError("FileStorage not initialized")
    return app_state.storage


def get_worker() -> "ConversionWorker":
    """Get conversion worker dependency."""
    if app_state.worker is None:
        raise RuntimeError("ConversionWorker not initialized")
    return app_state.worker

"""Conversion worker using BullMQ.

Processes image and document conversion jobs from the queue.
Handles job lifecycle, error recovery, and progress tracking.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bullmq import Worker, Job as BullMQJob

from shared.config import get_settings
from shared.events import get_event_bus
from shared.exceptions import ProcessingError
from src.domain.job import (
    JobStarted,
    JobCompleted,
    JobFailed,
    BackgroundRemoved,
    ImageCompressed,
    WatermarkApplied,
)
from src.infrastructure.persistence import JobRepository
from src.infrastructure.storage.file_storage import FileStorage
from src.infrastructure.converters.image_converter import get_image_converter
from src.infrastructure.converters.document_converter import get_document_converter
from src.infrastructure.converters.pdf_processor import get_pdf_processor
from src.infrastructure.converters import XmlConverter
from src.infrastructure.converters.xml.exceptions import XmlConversionError
from src.infrastructure.converters.image_pipeline import (
    get_image_pipeline,
    PipelineConfig,
    CompressionLevel,
    WatermarkPosition,
)


logger = logging.getLogger(__name__)


class ConversionWorker:
    """Worker for processing conversion jobs.

    Uses BullMQ Worker to consume jobs from the queue and process them
    using ImageMagick for image format conversion.

    Features:
    - Automatic retry with exponential backoff (handled by BullMQ)
    - Progress tracking and event publishing
    - Graceful shutdown
    - Error handling and logging
    """

    def __init__(
        self,
        redis_url: str,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize conversion worker.

        Args:
            redis_url: Redis connection URL
            repository: Job repository for persistence
            storage: File storage for accessing input/output files
        """
        self.redis_url = redis_url
        self.repository = repository
        self.storage = storage
        self.converter = get_image_converter()
        self.pipeline = get_image_pipeline()
        self.document_converter = get_document_converter()
        self.pdf_processor = get_pdf_processor()
        self.settings = get_settings()
        self.event_bus = get_event_bus()

        self.worker: Worker | None = None
        self._shutdown = False

        logger.info("ConversionWorker initialized")

    async def start(self) -> None:
        """Start the worker to process jobs from the queue."""
        try:
            logger.info("🚀 Starting ConversionWorker...")

            # Create BullMQ Worker
            self.worker = Worker(
                "easy-convert-jobs",
                self._process_job,
                {
                    "connection": self.redis_url,
                    "concurrency": self.settings.worker_concurrency,
                },
            )

            logger.info(
                f"✅ Worker started with concurrency={self.settings.worker_concurrency}"
            )

            # Keep worker running until shutdown
            while not self._shutdown:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Worker failed to start: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info("🛑 Stopping ConversionWorker...")
        self._shutdown = True

        if self.worker:
            await self.worker.close()
            logger.info("✅ Worker stopped")

    async def _process_job(
        self, bullmq_job: BullMQJob, token: str | None = None
    ) -> dict[str, Any]:
        """Process a single conversion job.

        Called by BullMQ Worker for each job in the queue.

        Args:
            bullmq_job: BullMQ job instance
            token: Worker token for progress updates

        Returns:
            Result dictionary with output information

        Raises:
            ProcessingError: If conversion fails
        """
        job_id = bullmq_job.id
        start_time = datetime.now(timezone.utc)

        logger.info(f"📋 Processing job {job_id}")

        try:
            # Get job data from BullMQ
            job_data = bullmq_job.data
            input_format = job_data.get("input_format")
            output_format = job_data.get("output_format")
            file_id = job_data.get("file_id")

            if not all([input_format, output_format, file_id]):
                raise ProcessingError("Invalid job data: missing required fields")

            # Reconstruct Job aggregate from events
            job = await self.repository.get_job(job_id)

            # Check if job is already in a terminal state (avoid retries on failed/completed jobs)
            if job.status.is_terminal():
                logger.warning(
                    f"⚠️ Job {job_id} is already in terminal state {job.status}. "
                    f"Skipping processing to avoid infinite retries."
                )
                return {
                    "success": True,
                    "job_id": job_id,
                    "skipped": True,
                    "reason": f"Job already in terminal state: {job.status}",
                }

            # Check if job can be processed
            if not job.can_start_processing():
                raise ProcessingError(
                    f"Job {job_id} cannot be processed in state: {job.status}"
                )

            # Mark job as started
            worker_id = f"worker-{os.getpid()}"
            event = JobStarted.create(job_id=job_id, worker_id=worker_id)
            job.apply_event(event)
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

            logger.info(f"🔧 Converting {input_format} → {output_format}")

            # Get input file path
            input_path = await self.storage.get_file(file_id)

            pdf_config = job_data.get("pdf_config") or {}
            xml_config = job_data.get("xml_config") or {}

            is_image_job = self.settings.is_image_format_supported(
                input_format
            ) and self.settings.is_image_format_supported(output_format, is_output=True)

            if pdf_config:
                logger.info("Using PDF processing flow")
                output_path = await self._process_pdf(
                    input_path=input_path,
                    file_id=file_id,
                    pdf_config=pdf_config,
                )
            elif xml_config:
                logger.info("Using XML conversion flow")
                output_path = await self._process_xml(
                    input_path=input_path,
                    file_id=file_id,
                    xml_config=xml_config,
                    job_id=job_id,
                )
            elif is_image_job:
                # Check if this is an advanced pipeline job or simple conversion
                pipeline_config_data = job_data.get("pipeline_config")

                if pipeline_config_data:
                    # Advanced pipeline processing
                    logger.info("Using advanced image processing pipeline")
                    output_path = await self._process_with_pipeline(
                        input_path, file_id, output_format, pipeline_config_data, job_id
                    )
                else:
                    # Simple image format conversion
                    logger.info("Using simple image format conversion")
                    output_path = await self._convert_image(
                        input_path, file_id, input_format, output_format, bullmq_job
                    )
            else:
                logger.info("Using document conversion flow")
                document_config = job_data.get("document_config") or {}
                output_path = await self._convert_document(
                    input_path=input_path,
                    file_id=file_id,
                    input_format=input_format,
                    output_format=output_format,
                    job_id=job_id,
                    preferred_engine=document_config.get("preferred_engine", "auto"),
                )

            result = {
                "format": output_format,
                "size": output_path.stat().st_size,
                "path": str(output_path),
            }

            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            processing_time_seconds = (end_time - start_time).total_seconds()

            # Get output info
            output_size_bytes = result["size"]
            output_file_path = result["path"]

            # Mark job as completed
            event = JobCompleted.create(
                job_id=job_id,
                output_file_path=output_file_path,
                output_size_bytes=output_size_bytes,
                processing_time_seconds=processing_time_seconds,
            )
            job.apply_event(event)
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

            logger.info(
                f"✅ Job {job_id} completed in {processing_time_seconds:.2f}s "
                f"(output: {output_size_bytes} bytes)"
            )

            return {
                "success": True,
                "job_id": job_id,
                "result": result,
                "processing_time_seconds": processing_time_seconds,
            }

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Mark job as failed (only if not already in terminal state)
            try:
                job = await self.repository.get_job(job_id)

                # Don't create failure event if already in terminal state
                if job.status.is_terminal():
                    logger.warning(
                        f"Job {job_id} already in terminal state {job.status}, "
                        f"not creating duplicate failure event"
                    )
                else:
                    event = JobFailed.create(
                        job_id=job_id,
                        error_message=str(e),
                        error_code=type(e).__name__,
                    )
                    job.apply_event(event)
                    await self.repository.save_events(job_id, [event])
                    await self.event_bus.publish(event)
            except Exception as save_error:
                logger.error(f"Failed to save failure event: {save_error}")

            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(f"Job processing failed: {e}")

    async def _convert_image(
        self,
        input_path: Path,
        file_id: str,
        input_format: str,
        output_format: str,
        bullmq_job: BullMQJob,
    ) -> Path:
        """Convert image using ImageMagick.

        Args:
            input_path: Path to input file
            file_id: File identifier
            input_format: Input format (e.g., 'png')
            output_format: Output format (e.g., 'jpg')
            bullmq_job: BullMQ job for progress updates

        Returns:
            Path to converted output file

        Raises:
            UnsupportedFormatError: If format is not supported
            ProcessingError: If conversion fails
        """
        try:
            # Build output path
            output_path = self.storage._get_output_path(file_id)

            # Use ImageMagick converter utility
            await self.converter.convert(
                input_path=input_path,
                output_path=output_path,
                output_format=output_format,
                strip_metadata=True,  # Privacy: always strip EXIF
                preserve_transparency=True,
            )

            return output_path

        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            raise ProcessingError(f"Image conversion failed: {e}")

    async def _process_with_pipeline(
        self,
        input_path: Path,
        file_id: str,
        output_format: str,
        pipeline_config_data: dict,
        job_id: str,
    ) -> Path:
        """Process image using full pipeline with advanced operations.

        Args:
            input_path: Path to input file
            file_id: File identifier
            output_format: Output format
            pipeline_config_data: Pipeline configuration dict
            job_id: Job identifier for event publishing

        Returns:
            Path to processed output file

        Raises:
            ProcessingError: If pipeline processing fails
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Build output path
            output_path = self.storage._get_output_path(file_id)

            # Convert pipeline config data to PipelineConfig
            config = self._build_pipeline_config(pipeline_config_data, output_format)

            # Execute pipeline
            logger.info(f"Executing pipeline with config: {config}")
            result_path = await self.pipeline.process(
                input_path=input_path,
                output_path=output_path,
                config=config,
            )

            # Publish events for operations that were performed
            await self._publish_pipeline_events(job_id, config, start_time)

            return result_path

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}", exc_info=True)
            raise ProcessingError(f"Image pipeline processing failed: {e}")

    async def _convert_document(
        self,
        input_path: Path,
        file_id: str,
        input_format: str,
        output_format: str,
        job_id: str,
        preferred_engine: str = "auto",
    ) -> Path:
        """Convert document using Pandoc/LibreOffice selection."""
        try:
            output_path = self.storage._get_output_path(file_id)
            return await self.document_converter.convert(
                input_path=input_path,
                output_path=output_path,
                input_format=input_format,
                output_format=output_format,
                job_id=job_id,
                preferred_engine=preferred_engine,
            )
        except Exception as e:
            logger.error(f"Document conversion failed: {e}", exc_info=True)
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(f"Document conversion failed: {e}")

    async def _process_pdf(
        self,
        input_path: Path,
        file_id: str,
        pdf_config: dict[str, Any],
    ) -> Path:
        """Process a PDF manipulation or editing job."""
        try:
            output_path = self.storage._get_output_path(file_id)
            source_paths = [
                await self.storage.get_file(source_file_id)
                for source_file_id in pdf_config.get("source_file_ids", [])
            ]
            asset_paths = {
                asset_name: await self.storage.get_file(asset_file_id)
                for asset_name, asset_file_id in pdf_config.get(
                    "asset_file_ids", {}
                ).items()
            }

            return await self.pdf_processor.process(
                input_path=input_path,
                output_path=output_path,
                operation=pdf_config["operation"],
                operation_params=pdf_config.get("operation_params", {}),
                source_paths=source_paths,
                asset_paths=asset_paths,
            )
        except Exception as e:
            logger.error(f"PDF processing failed: {e}", exc_info=True)
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(f"PDF processing failed: {e}")

    async def _process_xml(
        self,
        input_path: Path,
        file_id: str,
        xml_config: dict[str, Any],
        job_id: str,
    ) -> Path:
        """Process XML conversion job.

        Args:
            input_path: Path to input XML file
            file_id: File identifier
            xml_config: XML conversion configuration dict
                - output_format: Target format (json, yaml, html, xslt)
                - options: Format-specific options
            job_id: Job identifier for logging

        Returns:
            Path to converted output file

        Raises:
            ProcessingError: If XML conversion fails
        """
        try:
            output_path = self.storage._get_output_path(file_id)

            # Read XML content from input file
            xml_content = input_path.read_bytes()

            # Get conversion parameters
            output_format = xml_config.get("output_format", "json")
            options = xml_config.get("options", {})

            # Validate XML content
            XmlConverter.validate_xml(xml_content, input_path.name)

            # Convert XML to target format
            logger.info(f"Converting XML to {output_format}")
            result = await XmlConverter.convert(xml_content, output_format, options)

            # Write result to output file
            output_path.write_bytes(result.content)

            logger.info(
                f"XML conversion completed: {input_path.name} -> {output_path.name}"
            )
            return output_path

        except XmlConversionError as e:
            logger.error(f"XML conversion failed: {e}", exc_info=True)
            raise ProcessingError(f"XML conversion failed: {e}")
        except Exception as e:
            logger.error(f"XML processing failed: {e}", exc_info=True)
            raise ProcessingError(f"XML processing failed: {e}")

    def _build_pipeline_config(
        self,
        config_data: dict,
        output_format: str,
    ) -> PipelineConfig:
        """Build PipelineConfig from dict.

        Args:
            config_data: Configuration dictionary
            output_format: Output format

        Returns:
            PipelineConfig instance
        """
        # Map compression level string to enum
        compression_level_map = {
            "low": CompressionLevel.LOW,
            "balanced": CompressionLevel.BALANCED,
            "strong": CompressionLevel.STRONG,
        }
        compression_level = compression_level_map.get(
            config_data.get("compression_level", "balanced"),
            CompressionLevel.BALANCED,
        )

        # Map watermark position string to enum
        watermark_position_map = {
            "top-left": WatermarkPosition.TOP_LEFT,
            "top-right": WatermarkPosition.TOP_RIGHT,
            "center": WatermarkPosition.CENTER,
            "bottom-left": WatermarkPosition.BOTTOM_LEFT,
            "bottom-right": WatermarkPosition.BOTTOM_RIGHT,
            "diagonal": WatermarkPosition.DIAGONAL,
        }
        watermark_params = config_data.get("watermark_params", {})
        watermark_position = watermark_position_map.get(
            watermark_params.get("position", "bottom-right"),
            WatermarkPosition.BOTTOM_RIGHT,
        )

        return PipelineConfig(
            # Background removal
            remove_background=config_data.get("remove_background", False),
            background_model=config_data.get("background_model", "u2net"),
            alpha_matting=config_data.get("alpha_matting", False),
            # Compression
            compress_enabled=config_data.get("compress_enabled", False),
            compression_level=compression_level,
            compression_quality=config_data.get("compression_quality"),
            # Watermark
            watermark_enabled=config_data.get("watermark_enabled", False),
            watermark_type=config_data.get("watermark_type"),
            watermark_text=watermark_params.get("text"),
            watermark_logo_path=Path(watermark_params["logo_path"])
            if watermark_params.get("logo_path")
            else None,
            watermark_position=watermark_position,
            watermark_opacity=watermark_params.get("opacity", 0.7),
            watermark_font_size=watermark_params.get("font_size", 40),
            watermark_color=watermark_params.get("color", "white"),
            watermark_margin=watermark_params.get("margin", 20),
            watermark_size_percent=watermark_params.get("size_percent", 15),
            # Output
            output_format=output_format,
            output_quality=config_data.get("output_quality"),
            strip_metadata=config_data.get("strip_metadata", True),
            preserve_transparency=True,
        )

    async def _publish_pipeline_events(
        self,
        job_id: str,
        config: PipelineConfig,
        start_time: datetime,
    ) -> None:
        """Publish events for pipeline operations that were performed.

        Args:
            job_id: Job identifier
            config: Pipeline configuration
            start_time: Processing start time
        """
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Publish background removal event
        if config.remove_background:
            event = BackgroundRemoved.create(
                job_id=job_id,
                model_used=config.background_model,
                processing_time_seconds=processing_time,
                output_size_bytes=0,  # Would need to track intermediate sizes
            )
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

        # Publish compression event
        if config.compress_enabled:
            event = ImageCompressed.create(
                job_id=job_id,
                compression_level=config.compression_level.value,
                original_size_bytes=0,  # Would need to track
                compressed_size_bytes=0,  # Would need to track
                reduction_percent=0.0,  # Would need to calculate
                tool_used="auto",
            )
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

        # Publish watermark event
        if config.watermark_enabled:
            event = WatermarkApplied.create(
                job_id=job_id,
                watermark_type=config.watermark_type or "unknown",
                watermark_position=config.watermark_position.value,
                watermark_params={
                    "text": config.watermark_text,
                    "opacity": config.watermark_opacity,
                },
            )
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)


async def start_worker(
    redis_url: str, repository: JobRepository, storage: FileStorage
) -> ConversionWorker:
    """Start a conversion worker instance.

    Args:
        redis_url: Redis connection URL
        repository: Job repository
        storage: File storage

    Returns:
        Running ConversionWorker instance
    """
    worker = ConversionWorker(redis_url, repository, storage)

    # Start worker in background task
    asyncio.create_task(worker.start())

    return worker

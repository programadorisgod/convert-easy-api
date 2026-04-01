"""Image processing pipeline orchestrator.

Coordinates the execution of multiple image operations in the correct order:
1. Remove background (optional)
2. Compress (optional)
3. Watermark (optional)
4. Convert format (always)

Following the recommended pipeline from architecture documentation.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from shared.exceptions import ProcessingError
from .image_compressor import CompressionLevel, get_image_compressor
from .image_converter import get_image_converter
from .watermark_service import WatermarkPosition, get_watermark_service

if TYPE_CHECKING:
    from .background_remover import BackgroundRemover


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for image processing pipeline."""

    # Background removal
    remove_background: bool = False
    background_model: str = "u2net"
    alpha_matting: bool = False

    # Compression
    compress_enabled: bool = False
    compression_level: CompressionLevel = CompressionLevel.BALANCED
    compression_quality: int | None = None

    # Watermark
    watermark_enabled: bool = False
    watermark_type: str | None = None  # "text" or "logo"
    watermark_text: str | None = None
    watermark_logo_path: Path | None = None
    watermark_position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT
    watermark_opacity: float = 0.7
    watermark_font_size: int = 40
    watermark_color: str = "white"
    watermark_margin: int = 20
    watermark_size_percent: int = 15

    # Format conversion (always executed)
    output_format: str = "jpg"
    output_quality: int | None = None
    strip_metadata: bool = True
    preserve_transparency: bool = True


class ImageProcessingPipeline:
    """Orchestrates multiple image processing operations.

    Executes operations in the optimal order to ensure quality:
    1. Remove background → 2. Convert → 3. Compress → 4. Watermark

    Note: Watermark comes AFTER compression to prevent degradation.
    """

    def __init__(self):
        """Initialize pipeline with all services."""
        self.background_remover: BackgroundRemover | None = None
        self.converter = get_image_converter()
        self.compressor = get_image_compressor()
        self.watermark_service = get_watermark_service()
        logger.info("ImageProcessingPipeline initialized")

    async def process(
        self,
        input_path: Path,
        output_path: Path,
        config: PipelineConfig,
    ) -> Path:
        """Execute full image processing pipeline.

        Args:
            input_path: Path to input image
            output_path: Path for final output image
            config: Pipeline configuration

        Returns:
            Path to final processed image

        Raises:
            ProcessingError: If any step fails
        """
        logger.info(f"🔄 Starting pipeline for {input_path.name}")

        current_file = input_path
        temp_files: list[Path] = []

        try:
            # Step 1: Remove background (if enabled)
            if config.remove_background:
                # Temporary safeguard: background removal is disabled while
                # GPU-backed runtime is unavailable.
                raise ProcessingError(
                    "Background removal is temporarily disabled while GPU support is unavailable"
                )
            else:
                logger.info("⏭️  Step 1/4: Background removal skipped")

            # Step 2: Convert format (always executed)
            logger.info(f"📍 Step 2/4: Converting to {config.output_format}")
            temp_convert = (
                output_path.parent
                / f"temp_convert_{output_path.stem}.{config.output_format}"
            )
            temp_files.append(temp_convert)

            current_file = await self.converter.convert(
                current_file,
                temp_convert,
                config.output_format,
                quality=config.output_quality,
                strip_metadata=config.strip_metadata,
                preserve_transparency=config.preserve_transparency,
            )

            # Step 3: Compress (if enabled)
            if config.compress_enabled:
                logger.info(
                    f"📍 Step 3/4: Compressing (level: {config.compression_level.value})"
                )
                temp_compress = (
                    output_path.parent
                    / f"temp_compress_{output_path.stem}.{config.output_format}"
                )
                temp_files.append(temp_compress)

                current_file, _ = await self.compressor.compress(
                    current_file,
                    temp_compress,
                    level=config.compression_level,
                    quality=config.compression_quality,
                )
            else:
                logger.info("⏭️  Step 3/4: Compression skipped")

            # Step 4: Watermark (if enabled) - MUST come after compression
            if config.watermark_enabled and config.watermark_type:
                logger.info(f"📍 Step 4/4: Adding {config.watermark_type} watermark")

                if config.watermark_type == "text" and config.watermark_text:
                    current_file = await self.watermark_service.add_text_watermark(
                        current_file,
                        output_path,
                        text=config.watermark_text,
                        position=config.watermark_position,
                        font_size=config.watermark_font_size,
                        opacity=config.watermark_opacity,
                        color=config.watermark_color,
                        margin=config.watermark_margin,
                    )
                elif config.watermark_type == "logo" and config.watermark_logo_path:
                    current_file = await self.watermark_service.add_logo_watermark(
                        current_file,
                        output_path,
                        logo_path=config.watermark_logo_path,
                        position=config.watermark_position,
                        opacity=config.watermark_opacity,
                        size_percent=config.watermark_size_percent,
                        margin=config.watermark_margin,
                    )
                else:
                    logger.warning("Watermark enabled but invalid configuration")
                    # Copy current file to output
                    if current_file != output_path:
                        output_path.write_bytes(current_file.read_bytes())
            else:
                logger.info("⏭️  Step 4/4: Watermark skipped")
                # Copy current file to output if not already there
                if current_file != output_path:
                    output_path.write_bytes(current_file.read_bytes())

            # Verify final output
            if not output_path.exists():
                raise ProcessingError("Pipeline completed but output file not found")

            output_size = output_path.stat().st_size
            logger.info(
                f"✅ Pipeline complete: {output_path.name} "
                f"({output_size / (1024 * 1024):.2f} MB)"
            )

            return output_path

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if temp_file.exists() and temp_file != output_path:
                        temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")


# Singleton instance
_pipeline: ImageProcessingPipeline | None = None


def get_image_pipeline() -> ImageProcessingPipeline:
    """Get singleton image processing pipeline instance.

    Returns:
        ImageProcessingPipeline instance
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = ImageProcessingPipeline()
    return _pipeline

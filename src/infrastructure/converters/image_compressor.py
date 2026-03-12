"""Image compression service with multiple strategies.

Supports different compression levels and optimizers:
- JPEG: jpegoptim (light), mozjpeg (balanced/strong)
- PNG: oxipng (lossless), pngquant (lossy)
"""

import asyncio
import logging
import subprocess
from enum import Enum
from pathlib import Path

from shared.exceptions import ProcessingError


logger = logging.getLogger(__name__)


class CompressionLevel(str, Enum):
    """Compression level options."""

    LOW = "low"  # 10-20% reduction, high quality
    BALANCED = "balanced"  # 30-60% reduction, good quality (recommended)
    STRONG = "strong"  # 60-90% reduction, acceptable quality


class ImageCompressor:
    """Service for compressing images with various strategies.

    Automatically detects format and applies optimal compression tool.
    """

    def __init__(self):
        """Initialize image compressor."""
        logger.info("ImageCompressor initialized")

    async def compress(
        self,
        input_path: Path,
        output_path: Path,
        level: CompressionLevel = CompressionLevel.BALANCED,
        quality: int | None = None,
    ) -> tuple[Path, float]:
        """Compress image using optimal strategy for format.

        Args:
            input_path: Path to input image
            output_path: Path to save compressed image
            level: Compression level (low, balanced, strong)
            quality: Optional quality override (0-100, overrides level)

        Returns:
            Tuple of (compressed image path, reduction percentage)

        Raises:
            ProcessingError: If compression fails
        """
        try:
            # Detect format from extension
            ext = input_path.suffix.lower()

            original_size = input_path.stat().st_size
            logger.info(
                f"Compressing {input_path.name} ({ext}) at level={level.value} "
                f"({original_size / (1024 * 1024):.2f} MB)"
            )

            # Route to appropriate compressor
            if ext in [".jpg", ".jpeg"]:
                await self._compress_jpeg(input_path, output_path, level, quality)
            elif ext == ".png":
                await self._compress_png(input_path, output_path, level, quality)
            else:
                # For other formats, just copy
                logger.warning(f"No compression strategy for {ext}, copying file")
                await asyncio.to_thread(
                    lambda: output_path.write_bytes(input_path.read_bytes())
                )
                return output_path, 0.0

            # Verify output and log stats
            if not output_path.exists():
                raise ProcessingError("Compression failed: output not created")

            output_size = output_path.stat().st_size
            reduction = ((original_size - output_size) / original_size) * 100

            logger.info(
                f"✅ Compressed to {output_path.name}: "
                f"{output_size / (1024 * 1024):.2f} MB ({reduction:.1f}% reduction)"
            )

            return output_path, reduction

        except Exception as e:
            logger.error(f"❌ Compression failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to compress image: {e}")

    async def _compress_jpeg(
        self,
        input_path: Path,
        output_path: Path,
        level: CompressionLevel,
        quality: int | None,
    ) -> None:
        """Compress JPEG using jpegoptim.

        Args:
            input_path: Input JPEG path
            output_path: Output JPEG path
            level: Compression level
            quality: Optional quality override
        """
        # Copy file first, then optimize in place
        # This handles cases where the file is already optimal
        import shutil

        await asyncio.to_thread(shutil.copy2, input_path, output_path)

        # Set quality based on compression level
        if level == CompressionLevel.LOW:
            quality_val = quality if quality else 90
        elif level == CompressionLevel.BALANCED:
            quality_val = quality if quality else 80
        else:  # STRONG
            quality_val = quality if quality else 70

        cmd = [
            "jpegoptim",
            "--strip-all",
            f"--max={quality_val}",
            str(output_path),
        ]
        await self._run_command(cmd)

    async def _compress_png(
        self,
        input_path: Path,
        output_path: Path,
        level: CompressionLevel,
        quality: int | None,
    ) -> None:
        """Compress PNG using oxipng or pngquant.

        Args:
            input_path: Input PNG path
            output_path: Output PNG path
            level: Compression level
            quality: Optional quality override
        """
        if level == CompressionLevel.LOW:
            # Use oxipng for lossless compression
            cmd = [
                "oxipng",
                "-o",
                "4",
                "--strip",
                "all",
                "--out",
                str(output_path),
                str(input_path),
            ]
        else:
            # Use pngquant for lossy compression
            if level == CompressionLevel.BALANCED:
                quality_range = "65-85" if not quality else f"{quality - 10}-{quality}"
            else:  # STRONG
                quality_range = "40-65" if not quality else f"{quality - 20}-{quality}"

            cmd = [
                "pngquant",
                f"--quality={quality_range}",
                "--speed",
                "1" if level == CompressionLevel.STRONG else "3",
                "--output",
                str(output_path),
                str(input_path),
            ]

        await self._run_command(cmd)

    async def _run_command(
        self,
        cmd: list[str],
    ) -> None:
        """Run compression command asynchronously.

        Args:
            cmd: Command and arguments to run

        Raises:
            ProcessingError: If command fails
        """
        try:
            logger.debug(f"Running: {' '.join(cmd)}")

            # Run command in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    check=False,  # Don't raise on non-zero exit
                    timeout=300,  # 5 minutes max
                ),
            )

            # jpegoptim returns exit code 2 when file is already optimal (skipped)
            # This is not an error, just means no optimization was needed
            if result.returncode not in (0, 2):
                stderr = result.stderr.decode() if result.stderr else "No error message"
                raise ProcessingError(f"Compression command failed: {stderr}")

            if result.stderr:
                logger.debug(f"Command stderr: {result.stderr.decode()}")

        except subprocess.TimeoutExpired:
            raise ProcessingError("Compression timeout exceeded")
        except ProcessingError:
            raise
        except Exception as e:
            raise ProcessingError(f"Compression error: {e}")


# Singleton instance
_compressor: ImageCompressor | None = None


def get_image_compressor() -> ImageCompressor:
    """Get singleton image compressor instance.

    Returns:
        ImageCompressor instance
    """
    global _compressor
    if _compressor is None:
        _compressor = ImageCompressor()
    return _compressor

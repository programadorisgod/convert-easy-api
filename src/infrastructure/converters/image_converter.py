"""ImageMagick converter utility.

Wrapper for ImageMagick's magick command-line tool to handle
image format conversions with proper quality settings and privacy protection.

Based on ImageMagick documentation:
https://imagemagick.org/script/command-line-processing.php
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from shared.config import get_settings
from shared.exceptions import ProcessingError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class ImageMagickConverter:
    """ImageMagick-based image converter.

    Provides high-level interface for converting images between formats
    using ImageMagick's 'magick' command.

    Features:
    - Automatic quality settings per format
    - EXIF stripping for privacy
    - Timeout protection
    - Error handling with detailed messages
    - Format validation
    """

    # Quality settings by format (0-100)
    QUALITY_SETTINGS = {
        "jpg": 90,
        "jpeg": 90,
        "webp": 85,
        "avif": 80,
        "heic": 85,
        "png": 95,  # PNG compression level
    }

    # Formats that benefit from -quality flag
    QUALITY_FORMATS = {"jpg", "jpeg", "webp", "avif", "heic", "png"}

    # Formats that support transparency
    TRANSPARENCY_FORMATS = {"png", "webp", "gif", "tiff"}

    def __init__(self):
        """Initialize ImageMagick converter."""
        self.settings = get_settings()
        self._magick_path: str | None = None
        self._validate_installation()

    def _validate_installation(self) -> None:
        """Check if ImageMagick is installed and available.

        Raises:
            ProcessingError: If ImageMagick is not found
        """
        # Try 'magick' command first (modern ImageMagick 7+)
        self._magick_path = shutil.which("magick")

        if not self._magick_path:
            # Fall back to 'convert' (ImageMagick 6)
            convert_path = shutil.which("convert")
            if convert_path:
                logger.warning(
                    "Using legacy 'convert' command. "
                    "Consider upgrading to ImageMagick 7+ for 'magick' command."
                )
                self._magick_path = convert_path
            else:
                raise ProcessingError(
                    "ImageMagick not found. Please install ImageMagick 7+ "
                    "(https://imagemagick.org/script/download.php)"
                )

        logger.info(f"ImageMagick found at: {self._magick_path}")

    async def convert(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
        quality: int | None = None,
        strip_metadata: bool = True,
        preserve_transparency: bool = True,
    ) -> Path:
        """Convert image to specified format.

        Args:
            input_path: Path to input image
            output_path: Path for output image
            output_format: Desired output format (e.g., 'jpg', 'png')
            quality: Optional quality setting (0-100). Uses defaults if not provided.
            strip_metadata: Whether to strip EXIF/metadata for privacy
            preserve_transparency: Preserve alpha channel if format supports it

        Returns:
            Path to converted image

        Raises:
            UnsupportedFormatError: If format is not supported
            ProcessingError: If conversion fails
        """
        # Validate input exists
        if not input_path.exists():
            raise ProcessingError(f"Input file not found: {input_path}")

        # Validate format
        output_format = output_format.lower()
        if not self.settings.is_image_format_supported(output_format):
            raise UnsupportedFormatError(output_format)

        # Build ImageMagick command
        cmd = [self._magick_path, str(input_path)]

        # Add quality setting if applicable
        if output_format in self.QUALITY_FORMATS:
            quality_value = quality or self.QUALITY_SETTINGS.get(output_format, 90)
            cmd.extend(["-quality", str(quality_value)])

        # Strip metadata for privacy (removes EXIF, GPS, etc.)
        if strip_metadata:
            cmd.append("-strip")

        # Preserve transparency if format supports it
        if preserve_transparency and output_format in self.TRANSPARENCY_FORMATS:
            cmd.extend(["-alpha", "on"])
        else:
            # Flatten transparency to white background for formats without alpha
            cmd.extend(["-background", "white", "-flatten"])

        # Add output path
        cmd.append(str(output_path))

        logger.info(f"Converting {input_path.name} → {output_format}")
        logger.debug(f"ImageMagick command: {' '.join(cmd)}")

        # Execute conversion
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.settings.max_conversion_time_seconds
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"ImageMagick error: {error_msg}")
                raise ProcessingError(f"Conversion failed: {error_msg}")

            # Verify output was created
            if not output_path.exists():
                raise ProcessingError("Output file was not created")

            output_size = output_path.stat().st_size
            output_size_mb = output_size / (1024 * 1024)

            logger.info(
                f"✅ Conversion complete: {output_path.name} ({output_size_mb:.2f} MB)"
            )

            return output_path

        except asyncio.TimeoutError:
            if process:
                process.kill()
            raise ProcessingError(
                f"Conversion timed out after {self.settings.max_conversion_time_seconds}s"
            )
        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            raise ProcessingError(f"Image conversion failed: {e}")

    async def get_image_info(self, image_path: Path) -> dict[str, Any]:
        """Get information about an image using ImageMagick identify.

        Args:
            image_path: Path to image

        Returns:
            Dict with image information (format, width, height, size)

        Raises:
            ProcessingError: If identify fails
        """
        if not image_path.exists():
            raise ProcessingError(f"Image not found: {image_path}")

        # Use identify to get image info
        # Format: format width height filesize
        cmd = ["identify", "-format", "%m %w %h %b", str(image_path)]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10,  # Short timeout for identify
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise ProcessingError(f"Failed to get image info: {error_msg}")

            # Parse output
            output = stdout.decode().strip()
            parts = output.split()

            if len(parts) >= 4:
                return {
                    "format": parts[0].lower(),
                    "width": int(parts[1]),
                    "height": int(parts[2]),
                    "size": parts[3],
                }
            else:
                raise ProcessingError(f"Unexpected identify output: {output}")

        except asyncio.TimeoutError:
            process.kill()
            raise ProcessingError("Image info retrieval timed out")
        except Exception as e:
            logger.error(f"Failed to get image info: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get image info: {e}")

    async def validate_image(self, image_path: Path) -> bool:
        """Validate that a file is a valid image.

        Args:
            image_path: Path to image

        Returns:
            True if valid image, False otherwise
        """
        try:
            await self.get_image_info(image_path)
            return True
        except ProcessingError:
            return False

    def get_supported_formats(self) -> list[str]:
        """Get list of supported image formats.

        Returns:
            List of supported format extensions
        """
        return list(self.settings.supported_image_input_formats)

    def is_format_supported(self, format: str) -> bool:
        """Check if a format is supported.

        Args:
            format: Format extension (e.g., 'jpg', 'png')

        Returns:
            True if supported
        """
        return self.settings.is_image_format_supported(format.lower())


# Singleton instance
_converter: ImageMagickConverter | None = None


def get_image_converter() -> ImageMagickConverter:
    """Get ImageMagick converter singleton.

    Returns:
        ImageMagickConverter instance
    """
    global _converter
    if _converter is None:
        _converter = ImageMagickConverter()
    return _converter

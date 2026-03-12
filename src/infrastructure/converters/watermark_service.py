"""Watermark service using ImageMagick.

Supports text and logo watermarks with configurable position, opacity, and size.
"""

import asyncio
import logging
import subprocess
from enum import Enum
from pathlib import Path

from shared.exceptions import ProcessingError


logger = logging.getLogger(__name__)


class WatermarkPosition(str, Enum):
    """Watermark position options."""

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    CENTER = "center"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    DIAGONAL = "diagonal"  # Centered, rotated 45°

    def to_imagemagick_gravity(self) -> str:
        """Convert to ImageMagick gravity parameter."""
        mapping = {
            "top-left": "northwest",
            "top-right": "northeast",
            "center": "center",
            "bottom-left": "southwest",
            "bottom-right": "southeast",
            "diagonal": "center",
        }
        return mapping[self.value]


class WatermarkService:
    """Service for adding watermarks to images using ImageMagick."""

    def __init__(self):
        """Initialize watermark service."""
        logger.info("WatermarkService initialized")

    async def add_text_watermark(
        self,
        input_path: Path,
        output_path: Path,
        text: str,
        position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT,
        font_size: int = 40,
        opacity: float = 0.7,
        color: str = "white",
        margin: int = 20,
    ) -> Path:
        """Add text watermark to image.

        Args:
            input_path: Path to input image
            output_path: Path to save watermarked image
            text: Watermark text
            position: Position of watermark
            font_size: Font size in points
            opacity: Opacity (0.0-1.0, where 1.0 is fully opaque)
            color: Text color (name or hex)
            margin: Margin from edge in pixels

        Returns:
            Path to watermarked image

        Raises:
            ProcessingError: If watermarking fails
        """
        try:
            logger.info(f"Adding text watermark '{text}' to {input_path.name}")

            # Build ImageMagick command
            if position == WatermarkPosition.DIAGONAL:
                # Diagonal watermark (rotated 45°, centered)
                cmd = [
                    "convert",
                    str(input_path),
                    "-fill",
                    f"rgba({self._color_to_rgba(color, opacity)})",
                    "-pointsize",
                    str(font_size),
                    "-gravity",
                    position.to_imagemagick_gravity(),
                    "-annotate",
                    "45",
                    text,  # 45° rotation
                    str(output_path),
                ]
            else:
                # Standard positioned watermark
                cmd = [
                    "convert",
                    str(input_path),
                    "-gravity",
                    position.to_imagemagick_gravity(),
                    "-pointsize",
                    str(font_size),
                    "-fill",
                    f"rgba({self._color_to_rgba(color, opacity)})",
                    "-annotate",
                    f"+{margin}+{margin}",
                    text,
                    str(output_path),
                ]

            await self._run_command(cmd)

            logger.info(f"✅ Text watermark added: {output_path.name}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Text watermark failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to add text watermark: {e}")

    async def add_logo_watermark(
        self,
        input_path: Path,
        output_path: Path,
        logo_path: Path,
        position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT,
        opacity: float = 0.5,
        size_percent: int = 15,  # % of image width
        margin: int = 20,
    ) -> Path:
        """Add logo watermark to image.

        Args:
            input_path: Path to input image
            output_path: Path to save watermarked image
            logo_path: Path to logo PNG (with transparency)
            position: Position of watermark
            opacity: Opacity (0.0-1.0)
            size_percent: Logo size as percentage of image width
            margin: Margin from edge in pixels

        Returns:
            Path to watermarked image

        Raises:
            ProcessingError: If watermarking fails
        """
        try:
            logger.info(
                f"Adding logo watermark from {logo_path.name} to {input_path.name}"
            )

            # Create temporary logo with adjusted opacity
            temp_logo = output_path.parent / f"temp_logo_{output_path.stem}.png"

            try:
                # Adjust logo opacity
                opacity_percent = int(opacity * 100)
                opacity_cmd = [
                    "convert",
                    str(logo_path),
                    "-alpha",
                    "set",
                    "-channel",
                    "A",
                    "-evaluate",
                    "set",
                    f"{opacity_percent}%",
                    str(temp_logo),
                ]
                await self._run_command(opacity_cmd)

                # Apply logo watermark with auto-resize
                if position == WatermarkPosition.DIAGONAL:
                    # Diagonal positioning is less common for logos, use center
                    gravity = "center"
                    geometry = "+0+0"
                else:
                    gravity = position.to_imagemagick_gravity()
                    geometry = f"+{margin}+{margin}"

                cmd = [
                    "convert",
                    str(input_path),
                    "(",
                    str(temp_logo),
                    "-resize",
                    f"{size_percent}%",
                    ")",
                    "-gravity",
                    gravity,
                    "-geometry",
                    geometry,
                    "-composite",
                    str(output_path),
                ]

                await self._run_command(cmd)

                logger.info(f"✅ Logo watermark added: {output_path.name}")
                return output_path

            finally:
                # Clean up temp logo
                if temp_logo.exists():
                    await asyncio.to_thread(temp_logo.unlink)

        except Exception as e:
            logger.error(f"❌ Logo watermark failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to add logo watermark: {e}")

    def _color_to_rgba(self, color: str, opacity: float) -> str:
        """Convert color name/hex to RGBA string for ImageMagick.

        Args:
            color: Color name (e.g., "white") or hex (e.g., "#FFFFFF")
            opacity: Opacity (0.0-1.0)

        Returns:
            RGBA string like "255,255,255,0.7"
        """
        # Simple color mapping (extend as needed)
        color_map = {
            "white": "255,255,255",
            "black": "0,0,0",
            "red": "255,0,0",
            "green": "0,255,0",
            "blue": "0,0,255",
        }

        if color.lower() in color_map:
            rgb = color_map[color.lower()]
        elif color.startswith("#"):
            # Convert hex to RGB
            hex_color = color.lstrip("#")
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                rgb = f"{r},{g},{b}"
            else:
                rgb = "255,255,255"  # Default to white
        else:
            rgb = "255,255,255"  # Default to white

        return f"{rgb},{opacity}"

    async def _run_command(self, cmd: list[str]) -> None:
        """Run ImageMagick command asynchronously.

        Args:
            cmd: Command and arguments

        Raises:
            ProcessingError: If command fails
        """
        try:
            logger.debug(f"Running: {' '.join(cmd)}")

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    check=True,
                    timeout=300,
                ),
            )

            if result.stderr:
                logger.debug(f"Command stderr: {result.stderr.decode()}")

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else "No error message"
            raise ProcessingError(f"ImageMagick command failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProcessingError("Watermark timeout exceeded")
        except Exception as e:
            raise ProcessingError(f"Watermark error: {e}")


# Singleton instance
_watermark_service: WatermarkService | None = None


def get_watermark_service() -> WatermarkService:
    """Get singleton watermark service instance.

    Returns:
        WatermarkService instance
    """
    global _watermark_service
    if _watermark_service is None:
        _watermark_service = WatermarkService()
    return _watermark_service

"""Convert one or more images into a single multi-page PDF.

Uses Pillow to render each image as a full-size page. The order of the
input paths determines the page order, so callers must pass them already
sorted (page 1 first).
"""

import asyncio
import logging
from pathlib import Path

from shared.config import get_settings
from shared.exceptions import ProcessingError

from PIL import Image


logger = logging.getLogger(__name__)


class ImageToPdfConverter:
    """Concatenate images into a single PDF using Pillow."""

    def __init__(self):
        self.settings = get_settings()

    async def convert(self, paths: list[Path], output_path: Path) -> Path:
        """Write a PDF made of one page per input image.

        Args:
            paths: Image paths in page order (at least one).
            output_path: Destination for the generated PDF.

        Returns:
            The output_path.

        Raises:
            ProcessingError: If conversion fails or no input is provided.
        """
        if not paths:
            raise ProcessingError("No images provided for PDF conversion")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._convert_sync, paths, output_path),
                timeout=self.settings.max_conversion_time_seconds,
            )
        except asyncio.TimeoutError:
            raise ProcessingError(
                f"Image to PDF conversion timed out after "
                f"{self.settings.max_conversion_time_seconds}s"
            )
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Image to PDF conversion failed: {e}", exc_info=True)
            raise ProcessingError(f"Image to PDF conversion failed: {e}")

        if not output_path.exists():
            raise ProcessingError("Output PDF was not created")

        logger.info(
            f"Created PDF from {len(paths)} image(s): {output_path.name} "
            f"({output_path.stat().st_size} bytes)"
        )
        return output_path

    def _convert_sync(self, paths: list[Path], output_path: Path) -> None:
        """CPU-bound Pillow work, run inside a thread."""
        images: list[Image.Image] = []
        try:
            for path in paths:
                image = Image.open(path)
                # PDF does not support alpha; flatten transparency to white.
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                images.append(image)

            first, *rest = images
            first.save(
                output_path,
                "PDF",
                save_all=True,
                append_images=rest,
                resolution=100.0,
            )
        finally:
            for image in images:
                image.close()


# Singleton instance
_converter: ImageToPdfConverter | None = None


def get_image_to_pdf_converter() -> ImageToPdfConverter:
    """Get ImageToPdfConverter singleton."""
    global _converter
    if _converter is None:
        _converter = ImageToPdfConverter()
    return _converter

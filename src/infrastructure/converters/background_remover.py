"""Background removal service using rembg.

Removes background from images using AI-powered segmentation models.
All processing happens locally without external API calls for maximum privacy.
"""

import asyncio
import logging
from pathlib import Path
from typing import Literal

from rembg import remove, new_session

from shared.exceptions import ProcessingError


logger = logging.getLogger(__name__)


class BackgroundRemover:
    """Service for removing backgrounds from images using rembg.

    Uses U2Net or BRIA models for AI-powered background segmentation.
    Processing is done entirely locally for privacy.
    """

    # Supported models
    ModelType = Literal[
        "u2net",
        "u2netp",
        "u2net_human_seg",
        "u2net_cloth_seg",
        "silueta",
        "isnet-general-use",
        "isnet-anime",
        "sam",
    ]

    def __init__(self, model: ModelType = "u2net"):
        """Initialize background remover with specified model.

        Args:
            model: Name of the rembg model to use (default: u2net)
        """
        self.model = model
        self._session = None
        logger.info(f"BackgroundRemover initialized with model: {model}")

    def _get_session(self):
        """Get or create rembg session (lazy loading)."""
        if self._session is None:
            logger.info(f"Loading rembg model: {self.model}")
            self._session = new_session(self.model)
            logger.info(f"Model {self.model} loaded successfully")
        return self._session

    async def remove_background(
        self,
        input_path: Path,
        output_path: Path,
        alpha_matting: bool = False,
        alpha_matting_foreground_threshold: int = 240,
        alpha_matting_background_threshold: int = 10,
        alpha_matting_erode_size: int = 10,
    ) -> Path:
        """Remove background from image.

        Args:
            input_path: Path to input image
            output_path: Path to save output PNG with transparency
            alpha_matting: Enable alpha matting for better edges (slower)
            alpha_matting_foreground_threshold: Foreground detection threshold (0-255)
            alpha_matting_background_threshold: Background detection threshold (0-255)
            alpha_matting_erode_size: Erosion size for matting

        Returns:
            Path to output image (PNG with alpha channel)

        Raises:
            ProcessingError: If background removal fails
        """
        try:
            logger.info(f"Removing background from {input_path.name}")

            # Run in executor to avoid blocking the event loop
            # rembg is CPU-intensive and blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._remove_background_sync,
                input_path,
                output_path,
                alpha_matting,
                alpha_matting_foreground_threshold,
                alpha_matting_background_threshold,
                alpha_matting_erode_size,
            )

            # Verify output
            if not output_path.exists():
                raise ProcessingError("Background removal failed: output not created")

            output_size = output_path.stat().st_size
            logger.info(
                f"✅ Background removed successfully: {output_path.name} "
                f"({output_size / (1024 * 1024):.2f} MB)"
            )

            return output_path

        except Exception as e:
            logger.error(f"❌ Background removal failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to remove background: {e}")

    def _remove_background_sync(
        self,
        input_path: Path,
        output_path: Path,
        alpha_matting: bool,
        alpha_matting_foreground_threshold: int,
        alpha_matting_background_threshold: int,
        alpha_matting_erode_size: int,
    ) -> None:
        """Synchronous background removal (runs in executor).

        Args:
            input_path: Input image path
            output_path: Output image path
            alpha_matting: Enable alpha matting
            alpha_matting_foreground_threshold: Foreground threshold
            alpha_matting_background_threshold: Background threshold
            alpha_matting_erode_size: Erosion size
        """
        # Read input image
        with open(input_path, "rb") as f:
            input_data = f.read()

        # Remove background
        session = self._get_session()
        output_data = remove(
            input_data,
            session=session,
            alpha_matting=alpha_matting,
            alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
            alpha_matting_background_threshold=alpha_matting_background_threshold,
            alpha_matting_erode_size=alpha_matting_erode_size,
        )

        # Save output as PNG (with alpha channel)
        with open(output_path, "wb") as f:
            f.write(output_data)


# Singleton instance
_background_remover: BackgroundRemover | None = None


def get_background_remover(
    model: BackgroundRemover.ModelType = "u2net",
) -> BackgroundRemover:
    """Get singleton background remover instance.

    Args:
        model: Model to use for background removal

    Returns:
        BackgroundRemover instance
    """
    global _background_remover
    if _background_remover is None or _background_remover.model != model:
        _background_remover = BackgroundRemover(model=model)
    return _background_remover

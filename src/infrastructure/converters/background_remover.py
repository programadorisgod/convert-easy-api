"""
Optimized background removal service for low-memory environments (Render 512MB).
"""

import asyncio
import gc
import logging
from pathlib import Path
from typing import Literal

from rembg import new_session, remove

from shared.exceptions import ProcessingError

logger = logging.getLogger(__name__)

# 🔒 Control global de concurrencia (CRÍTICO)
_semaphore = asyncio.Semaphore(1)

# 🔒 Límite de tamaño de imagen (ajustable)
MAX_IMAGE_SIZE_MB = 5


class BackgroundRemover:
    """Memory-optimized background remover using rembg."""

    ModelType = Literal[
        "u2netp",  # 🔥 default optimizado
        "u2net",
        "u2net_human_seg",
        "isnet-general-use",
    ]

    def __init__(self, model: ModelType = "u2netp"):
        self.model = model
        self._session = None
        logger.info(f"BackgroundRemover initialized with model: {model}")

    def _get_session(self):
        """Lazy-load ONNX session (critical for memory)."""
        if self._session is None:
            logger.info(f"🔄 Loading rembg model: {self.model}")
            self._session = new_session(self.model)
            logger.info(f"✅ Model {self.model} loaded")
        return self._session

    async def remove_background(
        self,
        input_path: Path,
        output_path: Path,
        alpha_matting: bool = False,  # 🔥 desactivado por defecto
        alpha_matting_foreground_threshold: int = 240,
        alpha_matting_background_threshold: int = 10,
        alpha_matting_erode_size: int = 10,
    ) -> Path:
        """Remove background with strict memory control."""

        try:
            # 🔒 Validar tamaño antes de cargar en RAM
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_IMAGE_SIZE_MB:
                raise ProcessingError(
                    f"Image too large: {file_size_mb:.2f}MB (max {MAX_IMAGE_SIZE_MB}MB)"
                )

            logger.info(f"Processing {input_path.name} ({file_size_mb:.2f}MB)")

            # 🔒 Limitar concurrencia (CRÍTICO para evitar OOM)
            async with _semaphore:
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

            if not output_path.exists():
                raise ProcessingError("Output not created")

            output_size = output_path.stat().st_size / (1024 * 1024)

            logger.info(f"✅ Done: {output_path.name} ({output_size:.2f}MB)")

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
        """Blocking inference with memory discipline."""

        input_data = None
        output_data = None

        try:
            # 📥 Leer imagen (controlado)
            with open(input_path, "rb") as f:
                input_data = f.read()

            # 🧠 Obtener sesión ONNX
            session = self._get_session()

            # 🚀 Inferencia
            output_data = remove(
                input_data,
                session=session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
                alpha_matting_background_threshold=alpha_matting_background_threshold,
                alpha_matting_erode_size=alpha_matting_erode_size,
            )

            # 💾 Guardar resultado
            with open(output_path, "wb") as f:
                f.write(output_data)

        finally:
            # 🧹 Liberación agresiva de memoria
            del input_data
            del output_data
            gc.collect()


# Singleton optimizado
_background_remover: BackgroundRemover | None = None


def get_background_remover(
    model: BackgroundRemover.ModelType = "u2netp",  # 🔥 clave
) -> BackgroundRemover:
    global _background_remover

    if _background_remover is None or _background_remover.model != model:
        _background_remover = BackgroundRemover(model=model)

    return _background_remover

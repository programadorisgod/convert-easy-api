"""Image conversion and processing utilities.

This module provides services for:
- Format conversion (ImageMagick)
- Background removal (rembg)
- Compression (jpegoptim, mozjpeg, oxipng, pngquant)
- Watermarking (ImageMagick)
- Pipeline orchestration
"""

from .background_remover import BackgroundRemover, get_background_remover
from .document_converter import DocumentConverter, get_document_converter
from .image_compressor import CompressionLevel, ImageCompressor, get_image_compressor
from .image_converter import ImageMagickConverter, get_image_converter
from .image_pipeline import ImageProcessingPipeline, PipelineConfig, get_image_pipeline
from .pdf_processor import PdfProcessor, get_pdf_processor
from .watermark_service import (
    WatermarkPosition,
    WatermarkService,
    get_watermark_service,
)


__all__ = [
    # Background removal
    "BackgroundRemover",
    "get_background_remover",
    # Documents
    "DocumentConverter",
    "get_document_converter",
    "PdfProcessor",
    "get_pdf_processor",
    # Compression
    "CompressionLevel",
    "ImageCompressor",
    "get_image_compressor",
    # Conversion
    "ImageMagickConverter",
    "get_image_converter",
    # Watermark
    "WatermarkPosition",
    "WatermarkService",
    "get_watermark_service",
    # Pipeline
    "ImageProcessingPipeline",
    "PipelineConfig",
    "get_image_pipeline",
]

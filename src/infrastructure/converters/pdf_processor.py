"""PDF processing utilities for structural and visual editing operations."""

import asyncio
import logging
import zipfile
from pathlib import Path
from typing import Any

from shared.exceptions import ProcessingError, ValidationError

try:
    import fitz
except Exception:  # pragma: no cover - handled at runtime with clear error
    fitz = None

try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover - handled at runtime with clear error
    PdfReader = None
    PdfWriter = None


logger = logging.getLogger(__name__)


class PdfProcessor:
    """Processes PDF jobs using pypdf and PyMuPDF."""

    STRUCTURAL_OPERATIONS = {
        "merge",
        "split_range",
        "extract_pages",
        "delete_pages",
        "rotate_pages",
        "update_metadata",
        "encrypt",
        "decrypt",
    }
    VISUAL_OPERATIONS = {
        "add_text",
        "add_image",
        "draw_rectangle",
        "add_annotation",
        "set_mediabox",
    }

    async def process(
        self,
        input_path: Path,
        output_path: Path,
        operation: str,
        operation_params: dict[str, Any] | None = None,
        source_paths: list[Path] | None = None,
        asset_paths: dict[str, Path] | None = None,
    ) -> Path:
        """Process a PDF operation and write the result to output_path."""
        normalized_operation = operation.lower()
        params = operation_params or {}
        sources = source_paths or []
        assets = asset_paths or {}

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if normalized_operation in self.STRUCTURAL_OPERATIONS:
            await asyncio.to_thread(
                self._process_structural,
                input_path,
                output_path,
                normalized_operation,
                params,
                sources,
            )
            return output_path

        if normalized_operation in self.VISUAL_OPERATIONS:
            await asyncio.to_thread(
                self._process_visual,
                input_path,
                output_path,
                normalized_operation,
                params,
                assets,
            )
            return output_path

        raise ValidationError(f"Unsupported PDF operation: {operation}")

    def _process_structural(
        self,
        input_path: Path,
        output_path: Path,
        operation: str,
        params: dict[str, Any],
        source_paths: list[Path],
    ) -> None:
        if PdfReader is None or PdfWriter is None:
            raise ProcessingError("PDF structural operations require 'pypdf'")

        if operation == "merge":
            self._merge_pdfs(input_path, output_path, source_paths)
            return

        reader = PdfReader(str(input_path))

        if operation == "split_range":
            self._split_range_to_zip(reader, output_path, params)
            return

        if operation == "extract_pages":
            self._extract_pages(reader, output_path, params)
            return
        if operation == "delete_pages":
            self._delete_pages(reader, output_path, params)
            return
        if operation == "rotate_pages":
            self._rotate_pages(reader, output_path, params)
            return
        if operation == "update_metadata":
            self._update_metadata(reader, output_path, params)
            return
        if operation == "encrypt":
            self._encrypt_pdf(reader, output_path, params)
            return
        if operation == "decrypt":
            self._decrypt_pdf(reader, input_path, output_path, params)
            return

        raise ValidationError(f"Unsupported PDF operation: {operation}")

    def _split_range_to_zip(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        start = int(params.get("start_page", 0))
        end = int(params.get("end_page", 0))

        if start < 1 or end < 1:
            raise ValidationError("start_page and end_page must be >= 1")
        if start > end:
            raise ValidationError("start_page must be <= end_page")

        total_pages = len(reader.pages)
        if end > total_pages:
            raise ValidationError(
                f"end_page ({end}) cannot exceed total pages ({total_pages})"
            )

        selected = PdfWriter()
        remaining = PdfWriter()

        for page_number, page in enumerate(reader.pages, start=1):
            if start <= page_number <= end:
                selected.add_page(page)
            else:
                remaining.add_page(page)

        parte_path = output_path.parent / "parte.pdf"
        resto_path = output_path.parent / "resto.pdf"

        with parte_path.open("wb") as f_selected:
            selected.write(f_selected)

        with resto_path.open("wb") as f_remaining:
            remaining.write(f_remaining)

        with zipfile.ZipFile(
            output_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.write(parte_path, arcname="parte.pdf")
            zip_file.write(resto_path, arcname="resto.pdf")

        parte_path.unlink(missing_ok=True)
        resto_path.unlink(missing_ok=True)

    def _merge_pdfs(
        self,
        input_path: Path,
        output_path: Path,
        source_paths: list[Path],
    ) -> None:
        all_sources = [input_path, *source_paths]
        if len(all_sources) < 2:
            raise ValidationError("merge requires at least two PDF sources")

        writer = PdfWriter()
        for path in all_sources:
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _extract_pages(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        page_numbers = self._parse_page_numbers(params.get("page_numbers"))
        writer = PdfWriter()

        for page_number in page_numbers:
            writer.add_page(reader.pages[page_number])

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _delete_pages(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        pages_to_delete = set(self._parse_page_numbers(params.get("page_numbers")))
        writer = PdfWriter()

        for index, page in enumerate(reader.pages):
            if index in pages_to_delete:
                continue
            writer.add_page(page)

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _rotate_pages(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        rotation = int(params.get("rotation", 0))
        if rotation % 90 != 0:
            raise ValidationError("rotation must be a multiple of 90")

        page_numbers = params.get("page_numbers")
        target_pages = (
            set(self._parse_page_numbers(page_numbers))
            if page_numbers
            else set(range(len(reader.pages)))
        )

        writer = PdfWriter()
        for index, page in enumerate(reader.pages):
            if index in target_pages:
                page.rotate(rotation)
            writer.add_page(page)

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _update_metadata(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        metadata = params.get("metadata") or {}
        if not metadata:
            raise ValidationError("metadata payload cannot be empty")

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata(
            {
                self._normalize_metadata_key(key): str(value)
                for key, value in metadata.items()
            }
        )

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _encrypt_pdf(
        self,
        reader: PdfReader,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        user_password = params.get("user_password")
        owner_password = params.get("owner_password")
        if not user_password:
            raise ValidationError("user_password is required for encrypt")

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata(dict(reader.metadata or {}))
        writer.encrypt(user_password, owner_password=owner_password)

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _decrypt_pdf(
        self,
        reader: PdfReader,
        input_path: Path,
        output_path: Path,
        params: dict[str, Any],
    ) -> None:
        password = params.get("password")
        if not password:
            raise ValidationError("password is required for decrypt")

        encrypted_reader = PdfReader(str(input_path))
        if not encrypted_reader.is_encrypted:
            raise ValidationError("PDF is not encrypted")

        decrypt_result = encrypted_reader.decrypt(password)
        if decrypt_result == 0:
            raise ValidationError("Invalid password for encrypted PDF")

        writer = PdfWriter()
        for page in encrypted_reader.pages:
            writer.add_page(page)
        if encrypted_reader.metadata:
            writer.add_metadata(dict(encrypted_reader.metadata))

        with output_path.open("wb") as output_file:
            writer.write(output_file)

    def _process_visual(
        self,
        input_path: Path,
        output_path: Path,
        operation: str,
        params: dict[str, Any],
        asset_paths: dict[str, Path],
    ) -> None:
        if fitz is None:
            raise ProcessingError("PDF visual editing requires 'PyMuPDF'")

        document = fitz.open(str(input_path))
        try:
            if operation == "add_text":
                self._add_text(document, params)
            elif operation == "add_image":
                self._add_image(document, params, asset_paths)
            elif operation == "draw_rectangle":
                self._draw_rectangle(document, params)
            elif operation == "add_annotation":
                self._add_annotation(document, params)
            elif operation == "set_mediabox":
                self._set_mediabox(document, params)
            else:
                raise ValidationError(f"Unsupported PDF operation: {operation}")

            document.save(str(output_path))
        finally:
            document.close()

    def _add_text(self, document: Any, params: dict[str, Any]) -> None:
        page = self._get_page(document, params)
        position = (float(params.get("x", 72)), float(params.get("y", 72)))
        text = params.get("text")
        if not text:
            raise ValidationError("text is required for add_text")

        page.insert_text(
            position,
            text,
            fontsize=float(params.get("font_size", 12)),
            color=self._to_color_tuple(params.get("color"), default=(0, 0, 0)),
        )

    def _add_image(
        self,
        document: Any,
        params: dict[str, Any],
        asset_paths: dict[str, Path],
    ) -> None:
        page = self._get_page(document, params)
        image_path = asset_paths.get("image")
        if image_path is None:
            raise ValidationError("image_job_id is required for add_image")

        rect = self._build_rect(params)
        page.insert_image(rect, filename=str(image_path))

    def _draw_rectangle(self, document: Any, params: dict[str, Any]) -> None:
        page = self._get_page(document, params)
        rect = self._build_rect(params)
        page.draw_rect(
            rect,
            color=self._to_color_tuple(params.get("color"), default=(1, 0, 0)),
            fill=self._to_optional_color_tuple(params.get("fill_color")),
            width=float(params.get("width", 1.0)),
        )

    def _add_annotation(self, document: Any, params: dict[str, Any]) -> None:
        page = self._get_page(document, params)
        text = params.get("text")
        if not text:
            raise ValidationError("text is required for add_annotation")

        page.add_text_annot(
            (float(params.get("x", 72)), float(params.get("y", 72))),
            text,
        )

    def _set_mediabox(self, document: Any, params: dict[str, Any]) -> None:
        page = self._get_page(document, params)
        page.set_mediabox(self._build_rect(params))

    def _get_page(self, document: Any, params: dict[str, Any]) -> Any:
        page_number = int(params.get("page_number", 1))
        if page_number < 1 or page_number > document.page_count:
            raise ValidationError(
                f"page_number must be between 1 and {document.page_count}"
            )
        return document[page_number - 1]

    def _build_rect(self, params: dict[str, Any]) -> Any:
        return fitz.Rect(
            float(params.get("x0")),
            float(params.get("y0")),
            float(params.get("x1")),
            float(params.get("y1")),
        )

    def _parse_page_numbers(self, page_numbers: Any) -> list[int]:
        if not page_numbers:
            raise ValidationError("page_numbers cannot be empty")

        normalized: list[int] = []
        for page_number in page_numbers:
            numeric_page = int(page_number)
            if numeric_page < 1:
                raise ValidationError("page numbers must start at 1")
            normalized.append(numeric_page - 1)
        return normalized

    def _normalize_metadata_key(self, key: str) -> str:
        normalized = str(key).strip()
        if not normalized:
            raise ValidationError("metadata keys cannot be empty")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    def _to_color_tuple(
        self,
        color: Any,
        default: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        if color is None:
            return default
        if not isinstance(color, list) or len(color) != 3:
            raise ValidationError("color must be a list of three numeric values")
        return tuple(float(value) for value in color)

    def _to_optional_color_tuple(
        self,
        color: Any,
    ) -> tuple[float, float, float] | None:
        if color is None:
            return None
        return self._to_color_tuple(color, default=(0, 0, 0))


_pdf_processor: PdfProcessor | None = None


def get_pdf_processor() -> PdfProcessor:
    """Get singleton PDF processor instance."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PdfProcessor()
    return _pdf_processor

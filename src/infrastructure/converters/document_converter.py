"""Document conversion utility for Phase 2.

Uses Pandoc and LibreOffice headless depending on source/target formats.
Selection strategy:
- Markup/text conversions prefer Pandoc
- Office fidelity conversions use LibreOffice
- If both can handle it, Pandoc has priority
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from shared.config import get_settings
from shared.exceptions import ProcessingError, UnsupportedFormatError

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - handled at runtime with clear error
    PdfReader = None

try:
    from pdf2docx import Converter as Pdf2DocxConverter
except Exception:  # pragma: no cover - handled at runtime with clear error
    Pdf2DocxConverter = None


logger = logging.getLogger(__name__)


class DocumentConverter:
    """Converts document files using Pandoc or LibreOffice."""

    # High-confidence sets based on Phase 2 architecture document.
    PANDOC_INPUT_FORMATS = {
        "md",
        "markdown",
        "html",
        "htm",
        "latex",
        "tex",
        "rst",
        "epub",
        "docx",
        "odt",
        "txt",
    }
    PANDOC_OUTPUT_FORMATS = {
        "html",
        "pdf",
        "docx",
        "epub",
        "latex",
        "tex",
        "md",
        "markdown",
        "txt",
        "odt",
        "rst",
    }

    LIBREOFFICE_INPUT_FORMATS = {
        "pdf",
        "doc",
        "docx",
        "odt",
        "rtf",
        "xls",
        "xlsx",
        "ods",
        "csv",
        "tsv",
        "ppt",
        "pptx",
        "odp",
    }
    LIBREOFFICE_OUTPUT_FORMATS = {
        "pdf",
        "docx",
        "odt",
        "html",
        "txt",
        "xlsx",
        "ods",
        "csv",
        "pptx",
        "odp",
    }

    MARKUP_INPUTS = {"md", "markdown", "html", "htm", "latex", "tex", "rst"}
    TEXTUAL_OUTPUTS = {
        "md",
        "markdown",
        "html",
        "htm",
        "txt",
        "rst",
        "latex",
        "tex",
        "epub",
    }
    OFFICE_LIKE_INPUTS = {
        "doc",
        "docx",
        "odt",
        "rtf",
        "xls",
        "xlsx",
        "ods",
        "ppt",
        "pptx",
        "odp",
    }

    def __init__(self):
        self.settings = get_settings()
        self._pandoc_path = shutil.which("pandoc")
        self._libreoffice_path = shutil.which("libreoffice")
        self._pandoc_pdf_engine = self._resolve_pandoc_pdf_engine()

    async def convert(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        job_id: str,
        preferred_engine: str = "auto",
    ) -> Path:
        """Convert document and normalize output to output_path."""
        in_fmt = self._normalize_format(input_format)
        out_fmt = self._normalize_format(output_format)

        if not self.settings.is_document_format_supported(in_fmt):
            raise UnsupportedFormatError(in_fmt)
        if not self.settings.is_document_format_supported(out_fmt, is_output=True):
            raise UnsupportedFormatError(out_fmt)

        # PDF input uses dedicated conversion paths.
        if in_fmt == "pdf":
            desired_output = output_path.with_suffix(f".{out_fmt}")
            if out_fmt == "txt":
                produced = await self._convert_pdf_to_text(input_path, desired_output)
            elif out_fmt == "docx":
                produced = await self._convert_pdf_to_docx(input_path, desired_output)
            elif out_fmt == "odt":
                temp_docx_output = desired_output.with_suffix(".docx")
                docx_path = await self._convert_pdf_to_docx(
                    input_path, temp_docx_output
                )
                produced = await self._convert_with_libreoffice(
                    input_path=docx_path,
                    output_path=desired_output,
                    input_format="docx",
                    output_format="odt",
                    job_id=job_id,
                )
                if docx_path.exists():
                    docx_path.unlink()
            elif out_fmt in {"html", "htm"}:
                produced = await self._convert_with_libreoffice(
                    input_path=input_path,
                    output_path=desired_output,
                    input_format="pdf",
                    output_format="html",
                    job_id=job_id,
                )
            else:
                raise UnsupportedFormatError(
                    f"pdf->{out_fmt} is not supported. Supported from pdf: txt, docx, odt, html"
                )

            if output_path.exists():
                output_path.unlink()
            produced.replace(output_path)
            return output_path

        engine = self.select_engine(in_fmt, out_fmt, preferred_engine=preferred_engine)
        desired_output = output_path.with_suffix(f".{out_fmt}")

        if engine == "pandoc":
            produced = await self._convert_with_pandoc(
                input_path=input_path,
                output_path=desired_output,
                input_format=in_fmt,
                output_format=out_fmt,
            )
        else:
            produced = await self._convert_with_libreoffice(
                input_path=input_path,
                output_path=desired_output,
                input_format=in_fmt,
                output_format=out_fmt,
                job_id=job_id,
            )

        if not produced.exists():
            raise ProcessingError("Document conversion did not produce an output file")

        # Normalize to storage canonical path without extension.
        if output_path.exists():
            output_path.unlink()
        produced.replace(output_path)

        return output_path

    def select_engine(
        self,
        input_format: str,
        output_format: str,
        preferred_engine: str = "auto",
    ) -> str:
        """Select conversion engine according to architecture rules."""
        in_fmt = self._normalize_format(input_format)
        out_fmt = self._normalize_format(output_format)
        engine_pref = self._normalize_format(preferred_engine)

        if in_fmt == "pdf":
            raise UnsupportedFormatError(
                "pdf input uses dedicated converter path (supported output: txt)"
            )

        pandoc_supported = self._supports_pandoc(in_fmt, out_fmt)
        libreoffice_supported = self._supports_libreoffice(in_fmt, out_fmt)

        if engine_pref == "pandoc":
            if not pandoc_supported:
                raise UnsupportedFormatError(
                    f"{in_fmt}->{out_fmt} for preferred_engine=pandoc"
                )
            return "pandoc"

        if engine_pref == "libreoffice":
            if not libreoffice_supported:
                raise UnsupportedFormatError(
                    f"{in_fmt}->{out_fmt} for preferred_engine=libreoffice"
                )
            return "libreoffice"

        # Text-oriented outputs are faster and semantically better with Pandoc.
        if pandoc_supported and out_fmt in self.TEXTUAL_OUTPUTS:
            return "pandoc"

        # Performance-first rule: office-like inputs run faster/more consistently on LibreOffice.
        if libreoffice_supported and in_fmt in self.OFFICE_LIKE_INPUTS:
            return "libreoffice"

        # Markup and text conversions should prefer Pandoc.
        if pandoc_supported and (
            in_fmt in self.MARKUP_INPUTS
            or out_fmt in {"md", "markdown", "latex", "tex", "rst", "epub"}
        ):
            return "pandoc"

        # If both support, prefer Pandoc (lighter and matches ADR guidance).
        if pandoc_supported:
            return "pandoc"

        if libreoffice_supported:
            return "libreoffice"

        raise UnsupportedFormatError(f"{in_fmt}->{out_fmt}")

    def _supports_pandoc(self, input_format: str, output_format: str) -> bool:
        return (
            input_format in self.PANDOC_INPUT_FORMATS
            and output_format in self.PANDOC_OUTPUT_FORMATS
        )

    def _supports_libreoffice(self, input_format: str, output_format: str) -> bool:
        return (
            input_format in self.LIBREOFFICE_INPUT_FORMATS
            and output_format in self.LIBREOFFICE_OUTPUT_FORMATS
        )

    async def _convert_with_pandoc(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
    ) -> Path:
        if not self._pandoc_path:
            raise ProcessingError("Pandoc is not installed in runtime image")

        pandoc_input = self._to_pandoc_format(input_format)
        cmd = [
            self._pandoc_path,
            "-f",
            pandoc_input,
            str(input_path),
            "-o",
            str(output_path),
        ]
        if output_format == "pdf":
            if not self._pandoc_pdf_engine:
                raise ProcessingError(
                    "No LaTeX PDF engine found for Pandoc. Install one of: "
                    "xelatex, lualatex, pdflatex"
                )
            cmd.extend(["--pdf-engine", self._pandoc_pdf_engine])

        await self._run_command(cmd)
        return output_path

    async def _convert_with_libreoffice(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str,
        output_format: str,
        job_id: str,
    ) -> Path:
        if not self._libreoffice_path:
            raise ProcessingError("LibreOffice is not installed in runtime image")

        out_dir = output_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # LibreOffice requires writable HOME; isolate per job to avoid lock conflicts.
        lo_home = out_dir / f"lo_home_{job_id}"
        lo_home.mkdir(parents=True, exist_ok=True)

        # LibreOffice relies heavily on filename extension to infer input type.
        # Our storage uses extensionless UUID paths, so create a typed copy.
        normalized_input = self._normalize_format(input_format)
        lo_input_path = out_dir / f"{input_path.stem}.{normalized_input}"
        created_temp_input = False
        if input_path.resolve() != lo_input_path.resolve():
            shutil.copy2(input_path, lo_input_path)
            created_temp_input = True

        started_at = datetime.now(timezone.utc)

        cmd = [
            self._libreoffice_path,
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--norestore",
            "--convert-to",
            output_format,
            "--outdir",
            str(out_dir),
            str(lo_input_path),
        ]

        env = {**os.environ, "HOME": str(lo_home)}
        stdout_text, stderr_text = await self._run_command(cmd, env=env)

        produced = out_dir / f"{lo_input_path.stem}.{output_format}"
        if not produced.exists():
            # Fallback: locate any recently generated output with expected suffix.
            candidates = sorted(
                [
                    p
                    for p in out_dir.glob(f"*.{output_format}")
                    if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                    >= started_at
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if candidates:
                produced = candidates[0]
            else:
                # Include command output to make failures debuggable.
                details = stderr_text or stdout_text or "no converter output"
                raise ProcessingError(
                    f"LibreOffice output not found: expected {produced.name}. "
                    f"Details: {details}"
                )

        if produced != output_path:
            if output_path.exists():
                output_path.unlink()
            produced.replace(output_path)

        # Cleanup typed temporary input copy when we created one.
        if created_temp_input and lo_input_path.exists():
            lo_input_path.unlink()

        return output_path

    async def _run_command(
        self, cmd: list[str], env: dict | None = None
    ) -> tuple[str, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.max_document_conversion_time_seconds,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProcessingError("Document conversion timed out") from exc

        if process.returncode != 0:
            stderr_text = stderr.decode().strip() if stderr else ""
            stdout_text = stdout.decode().strip() if stdout else ""
            details = stderr_text or stdout_text or "unknown error"
            raise ProcessingError(f"Document conversion failed: {details}")

        return (
            stdout.decode().strip() if stdout else "",
            stderr.decode().strip() if stderr else "",
        )

    async def _convert_pdf_to_text(self, input_path: Path, output_path: Path) -> Path:
        """Extract plain text from PDF using pypdf."""
        if PdfReader is None:
            raise ProcessingError("PDF to TXT conversion requires 'pypdf' dependency")

        try:
            reader = PdfReader(str(input_path))
            pages_text: list[str] = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")

            output_path.write_text("\n\n".join(pages_text), encoding="utf-8")
            return output_path
        except Exception as exc:
            raise ProcessingError(f"PDF to TXT conversion failed: {exc}") from exc

    async def _convert_pdf_to_docx(self, input_path: Path, output_path: Path) -> Path:
        """Convert PDF to DOCX using pdf2docx."""
        if Pdf2DocxConverter is None:
            raise ProcessingError(
                "PDF to DOCX conversion requires 'pdf2docx' dependency"
            )

        try:
            await asyncio.to_thread(
                self._run_pdf2docx_conversion,
                input_path,
                output_path,
            )
            if not output_path.exists():
                raise ProcessingError("PDF to DOCX conversion produced no output")
            return output_path
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(f"PDF to DOCX conversion failed: {exc}") from exc

    def _run_pdf2docx_conversion(self, input_path: Path, output_path: Path) -> None:
        converter = Pdf2DocxConverter(str(input_path))
        try:
            converter.convert(str(output_path))
        finally:
            converter.close()

    def _normalize_format(self, format_name: str) -> str:
        return format_name.lower().lstrip(".")

    def _resolve_pandoc_pdf_engine(self) -> str | None:
        """Pick first available PDF engine for Pandoc in priority order."""
        for engine in ("xelatex", "lualatex", "pdflatex"):
            if shutil.which(engine):
                return engine
        return None

    def _to_pandoc_format(self, format_name: str) -> str:
        """Map our normalized format names to Pandoc format tokens."""
        normalized = self._normalize_format(format_name)
        mapping = {
            "markdown": "markdown",
            "md": "markdown",
            "htm": "html",
            "latex": "latex",
            "tex": "latex",
        }
        return mapping.get(normalized, normalized)


_document_converter: DocumentConverter | None = None


def get_document_converter() -> DocumentConverter:
    """Get singleton document converter instance."""
    global _document_converter
    if _document_converter is None:
        _document_converter = DocumentConverter()
    return _document_converter

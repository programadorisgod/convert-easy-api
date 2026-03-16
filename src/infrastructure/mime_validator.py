"""MIME type validation service using python-magic (libmagic).

Validates that the actual file content matches the format declared by the client.
This prevents format spoofing attacks where a malicious file is uploaded with
a declared format that differs from its real content type.

Security note: Validation is intentionally lenient for ambiguous text-based formats
(md, rst, csv, tex, txt) since libmagic cannot distinguish them — all resolve to
text/plain. Strict enforcement is applied only to binary formats where MIME
detection is reliable.
"""

import logging
from pathlib import Path

import magic

from shared.exceptions import ValidationError


logger = logging.getLogger(__name__)

# Formats where MIME is reliably text/plain — libmagic cannot distinguish them.
# Validation is skipped for these to avoid false positives.
_TEXT_PLAIN_FORMATS = frozenset(
    {"txt", "md", "markdown", "rst", "csv", "tsv", "tex", "latex"}
)

# Maps detected MIME type to a canonical format name.
# Binary formats have reliable detection; text-based formats are approximated.
_MIME_TO_FORMAT: dict[str, str] = {
    # Images
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/avif": "avif",
    "image/heic": "heic",
    "image/heif": "heic",
    "image/tiff": "tiff",
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    # Documents — binary formats with reliable MIME detection
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/epub+zip": "epub",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.oasis.opendocument.presentation": "odp",
    "application/rtf": "rtf",
    "text/rtf": "rtf",
    # HTML is distinct from plain text
    "text/html": "html",
    "application/xhtml+xml": "html",
    # Text-based — ambiguous, best-effort only
    "text/plain": "txt",
    "text/csv": "csv",
    "text/tab-separated-values": "tsv",
    "text/markdown": "md",
    "text/x-rst": "rst",
    "text/x-latex": "tex",
}

# Aliases that normalize to a canonical format name used in the map above.
_FORMAT_ALIASES: dict[str, str] = {
    "jpeg": "jpg",
    "markdown": "md",
    "htm": "html",
    "latex": "tex",
    "tif": "tiff",
}


class MimeValidator:
    """Validates file content against the declared format using libmagic.

    Only raises on clear mismatches (e.g. binary image file declared as docx).
    Text-based formats that share text/plain are allowed through without error.
    Unknown MIME types are logged and allowed to avoid blocking unsupported-but-valid files.
    """

    def validate(self, file_path: Path, declared_format: str) -> str:
        """Validate that file content matches the declared format.

        Args:
            file_path: Path to the uploaded file.
            declared_format: Format name declared by the client (e.g. "jpg", "docx").

        Returns:
            The detected MIME type string.

        Raises:
            ValidationError: If file content clearly does not match declared format.
        """
        try:
            detected_mime: str = magic.from_file(str(file_path), mime=True)
        except Exception as exc:
            logger.warning("MIME detection failed for %s: %s", file_path, exc)
            return "application/octet-stream"

        declared_norm = _FORMAT_ALIASES.get(
            declared_format.lower(), declared_format.lower()
        )

        detected_format = _MIME_TO_FORMAT.get(detected_mime)

        if detected_format is None:
            # Unknown MIME — allow to avoid false positives on less-common formats
            logger.warning(
                "Unknown MIME type '%s' for declared format '%s'; skipping strict check",
                detected_mime,
                declared_format,
            )
            return detected_mime

        # text/plain covers many text-based formats that libmagic cannot distinguish
        if detected_mime == "text/plain":
            if declared_norm not in _TEXT_PLAIN_FORMATS:
                raise ValidationError(
                    f"File content appears to be plain text but declared format "
                    f"'{declared_format}' expects binary data."
                )
            return detected_mime

        if detected_format != declared_norm:
            raise ValidationError(
                f"File content does not match declared format. "
                f"Declared: '{declared_format}', detected: '{detected_mime}'."
            )

        logger.debug(
            "MIME validation passed: declared=%s detected=%s",
            declared_format,
            detected_mime,
        )
        return detected_mime


_validator: MimeValidator | None = None


def get_mime_validator() -> MimeValidator:
    """Return the singleton MimeValidator instance."""
    global _validator
    if _validator is None:
        _validator = MimeValidator()
    return _validator

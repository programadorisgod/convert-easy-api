"""Base64 conversion endpoints (synchronous, in-memory).

Handles both directions:
- Image -> Base64   (POST /convert/image/to-base64)
- Base64 -> Image    (POST /convert/base64/to-image)

These are pure text <-> bytes transforms; they do NOT need the async job/queue
system. Processing happens in-memory in a single request, mirroring the
synchronous XML conversion pattern.

The endpoint also supports Data URIs (``data:image/png;base64,...``) on input
for the Base64 -> Image direction.
"""

import base64
import binascii
import logging
import mimetypes

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from typing import Annotated

from shared.http import safe_download_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/convert", tags=["Base64 Conversion"])

# Guards against pathological inputs (a base64 string decodes to at most its
# length; reject anything that would balloon into a huge binary).
MAX_B64_CHARS = 10 * 1024 * 1024  # 10MB of base64 text
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15MB decoded binary

# MIME types the API is willing to hand back as an image. Anything outside
# this set is rejected to avoid serving arbitrary binary as an image.
ALLOWED_IMAGE_MIME = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/avif",
    "image/bmp",
    "image/svg+xml",
    "image/tiff",
}


def _extension_to_mime(filename: str) -> str:
    """Best-effort MIME from the filename extension (defaults to png)."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in filename else ""
    detected, _ = mimetypes.guess_type(f"x.{ext}") if ext else (None, None)
    return detected or "image/png"


def _strip_data_uri(data: str) -> tuple[str, str | None]:
    """Split a Data URI into ``(base64_payload, mime)``.

    A plain base64 string (no header) returns ``(data, None)``.
    """
    data = data.strip()
    if data.startswith("data:") and "," in data:
        header, payload = data.split(",", 1)
        mime = header.split(";", 1)[0].removeprefix("data:") or None
        return payload.strip(), mime
    return data, None


@router.post(
    "/image/to-base64",
    summary="Encode an image to Base64",
    description=(
        "Uploads an image and returns its Base64 representation plus an "
        "optional Data URI, inferring the MIME type from the file extension."
    ),
    responses={400: {"description": "Invalid or oversized input"}},
)
async def image_to_base64(
    file: Annotated[UploadFile, File(description="Image file to encode")],
) -> dict:
    """Encode an uploaded image file into a Base64 string."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file upload")

    filename = file.filename or "image"
    mime = _extension_to_mime(filename)
    encoded = base64.b64encode(content).decode("ascii")

    return {
        "filename": filename,
        "mime": mime,
        "mime_type": mime,
        "size": len(content),
        "base64": encoded,
        "data_uri": f"data:{mime};base64,{encoded}",
        "data_uri_prefix": f"data:{mime};base64,",
    }


@router.post(
    "/base64/to-image",
    summary="Decode Base64 back into an image",
    description=(
        "Accepts either a raw Base64 string or a Data URI "
        "(``data:image/png;base64,...``) and returns the decoded image file. "
        "The MIME type is taken from the Data URI header when present, "
        "otherwise from the ``mime`` form field."
    ),
    responses={
        400: {"description": "Invalid Base64 payload or unsupported MIME type"}
    },
)
async def base64_to_image(
    data: Annotated[
        str,
        Form(description="Base64 string or Data URI to decode into an image"),
    ],
    mime: Annotated[
        str | None,
        Form(description="MIME type used when no Data URI header is present"),
    ] = None,
    filename: Annotated[
        str | None,
        Form(description="Output filename (extension appended from MIME)"),
    ] = None,
) -> Response:
    """Decode a Base64 string or Data URI back into an image file."""
    if not data or not data.strip():
        raise HTTPException(status_code=400, detail="Empty Base64 input")

    if len(data) > MAX_B64_CHARS:
        raise HTTPException(status_code=413, detail="Base64 input too large")

    payload, uri_mime = _strip_data_uri(data)
    if not payload:
        raise HTTPException(status_code=400, detail="Empty Base64 payload")

    # Validate strictly BEFORE decoding to avoid decoding garbage into bytes.
    try:
        if len(payload) % 4 != 0:
            # Accept unpadded base64 by re-padding, common from some tools.
            payload += "=" * (-len(payload) % 4)
        blob = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Base64: {exc}") from exc

    if not blob:
        raise HTTPException(status_code=400, detail="Decoded image is empty")
    if len(blob) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Decoded image too large")

    resolved_mime = uri_mime or mime or "image/png"
    if resolved_mime not in ALLOWED_IMAGE_MIME:
        # Reject arbitrary MIME values on the way out.
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image MIME type: {resolved_mime}",
        )

    ext = mimetypes.guess_extension(resolved_mime) or ".png"
    base_name = safe_download_filename(
        filename or "output", "output"
    ).rsplit(".", 1)[0]
    download_name = safe_download_filename(f"{base_name}{ext}", f"output{ext}")

    return Response(
        content=blob,
        media_type=resolved_mime,
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"'
        },
    )

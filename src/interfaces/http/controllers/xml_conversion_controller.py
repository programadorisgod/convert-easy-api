"""XML conversion endpoints."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from typing import Annotated

from src.infrastructure.converters import XmlConverter
from src.infrastructure.converters.xml.exceptions import (
    XmlConversionError,
    XmlSyntaxError,
    XmlMappingError,
    XmlXsltError,
    XmlSizeError,
    XmlMimeError,
    XmlValidationError,
)

router = APIRouter(prefix="/convert/xml", tags=["XML Conversion"])

# Size thresholds
MAX_SYNC_SIZE_JSON_YAML = 5 * 1024 * 1024  # 5MB
MAX_SYNC_SIZE_HTML = 2 * 1024 * 1024  # 2MB


def get_error_response(error: XmlConversionError) -> dict:
    """Map exception to HTTP response."""
    if isinstance(error, XmlSyntaxError):
        return {"error": "xml_syntax", "message": str(error)}
    elif isinstance(error, XmlMappingError):
        return {"error": "xml_mapping", "message": str(error)}
    elif isinstance(error, XmlXsltError):
        return {"error": "xslt_error", "message": str(error)}
    elif isinstance(error, XmlSizeError):
        return {"error": "file_too_large", "message": str(error)}
    elif isinstance(error, XmlMimeError):
        return {"error": "invalid_mime", "message": str(error)}
    elif isinstance(error, XmlValidationError):
        return {"error": "validation_error", "message": str(error)}
    else:
        return {"error": "conversion_error", "message": str(error)}


@router.post("/json")
async def convert_xml_to_json(
    file: Annotated[UploadFile, File(description="XML file to convert")],
    preserve_attributes: Annotated[bool, Form()] = False,
    always_as_list: Annotated[bool, Form()] = False,
) -> Response:
    """
    Convert XML to JSON.

    **Sync** for files < 5MB, returns JSON directly.
    **Async** for files >= 5MB, returns job_id for polling.
    """
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "input.xml"

    # Validate
    XmlConverter.validate_xml(content, filename)

    # Check size for sync/async decision
    if file_size >= MAX_SYNC_SIZE_JSON_YAML:
        # TODO: Queue as async job
        raise HTTPException(
            status_code=501,
            detail="Async conversion not yet implemented. Please use files < 5MB.",
        )

    # Options
    options = {
        "preserve_attributes": preserve_attributes,
        "always_as_list": always_as_list,
    }

    try:
        result = await XmlConverter.convert(content, "json", options)
        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename.replace(".xml", ".json")}"'
            },
        )
    except XmlConversionError as e:
        raise HTTPException(status_code=400, detail=get_error_response(e))


@router.post("/yaml")
async def convert_xml_to_yaml(
    file: Annotated[UploadFile, File(description="XML file to convert")],
    indent: Annotated[int, Form(ge=2, le=4)] = 2,
    flow_style: Annotated[bool, Form()] = False,
    preserve_xml_declaration: Annotated[bool, Form()] = True,
) -> Response:
    """
    Convert XML to YAML.

    **Sync** for files < 5MB, returns YAML directly.
    **Async** for files >= 5MB, returns job_id for polling.
    """
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "input.xml"

    # Validate
    XmlConverter.validate_xml(content, filename)

    # Check size
    if file_size >= MAX_SYNC_SIZE_JSON_YAML:
        raise HTTPException(
            status_code=501,
            detail="Async conversion not yet implemented. Please use files < 5MB.",
        )

    options = {
        "indent": indent,
        "flow_style": flow_style,
        "preserve_xml_declaration": preserve_xml_declaration,
    }

    try:
        result = await XmlConverter.convert(content, "yaml", options)
        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename.replace(".xml", ".yaml")}"'
            },
        )
    except XmlConversionError as e:
        raise HTTPException(status_code=400, detail=get_error_response(e))


@router.post("/html")
async def convert_xml_to_html(
    file: Annotated[UploadFile, File(description="XML file to convert")],
    template: Annotated[
        str, Form(description="Template: table, list, cards")
    ] = "table",
    title: Annotated[str | None, Form()] = None,
    custom_xslt: Annotated[str | None, Form()] = None,
) -> Response:
    """
    Convert XML to HTML.

    **Sync** for files < 2MB using built-in templates.
    **Async** for files >= 2MB or custom XSLT.

    Built-in templates:
    - table: Tabular display
    - list: Nested list display
    - cards: Card-based display
    """
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "input.xml"

    # Validate
    XmlConverter.validate_xml(content, filename)

    # Custom XSLT is async only
    if custom_xslt and file_size >= MAX_SYNC_SIZE_HTML:
        raise HTTPException(
            status_code=501, detail="Custom XSLT conversion is async-only."
        )

    # Check size
    if file_size >= MAX_SYNC_SIZE_HTML:
        raise HTTPException(
            status_code=501,
            detail="Large HTML conversion not yet implemented. Please use files < 2MB.",
        )

    options = {
        "template": template,
        "title": title,
        "custom_xslt": custom_xslt,
    }

    try:
        result = await XmlConverter.convert(content, "html", options)
        return Response(
            content=result.content,
            media_type=result.content_type,
        )
    except XmlConversionError as e:
        raise HTTPException(status_code=400, detail=get_error_response(e))


@router.post("/transform")
async def transform_xml_with_xslt(
    file: Annotated[UploadFile, File(description="XML file to transform")],
    xslt_file: Annotated[UploadFile, File(description="XSLT transformation file")],
    preserve_declaration: Annotated[bool, Form()] = True,
) -> Response:
    """
    Transform XML using XSLT.

    **Async-only** - requires XSLT file upload.

    Security: External document access (document(), import, include) is blocked.
    """
    content = await file.read()
    xslt_content = await xslt_file.read()
    filename = file.filename or "input.xml"

    # Validate
    XmlConverter.validate_xml(content, filename)

    options = {
        "xslt_content": xslt_content.decode("utf-8"),
        "preserve_declaration": preserve_declaration,
    }

    # Transform is always async
    raise HTTPException(
        status_code=501,
        detail="XSLT transformation is async-only. Queue implementation pending.",
    )

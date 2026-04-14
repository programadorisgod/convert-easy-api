"""Pydantic schemas for XML conversion requests and responses."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field


# ===== JSON Options =====


class XmlJsonOptions(BaseModel):
    """Options for XML to JSON conversion."""

    preserve_attributes: bool = Field(
        default=False,
        description="Preserve XML attributes as @attr in JSON objects",
    )
    always_as_list: bool = Field(
        default=False,
        description="Always convert repeated elements to lists",
    )
    dict_constructor: str | None = Field(
        default=None,
        description="Custom dict constructor function name",
    )


# ===== YAML Options =====


class XmlYamlOptions(BaseModel):
    """Options for XML to YAML conversion."""

    indent: Literal[2, 4] = Field(
        default=2,
        description="Indentation level",
    )
    flow_style: bool = Field(
        default=False,
        description="Use flow style (inline) instead of block style",
    )
    preserve_xml_declaration: bool = Field(
        default=True,
        description="Include <?xml?> declaration in output",
    )


# ===== HTML Options =====


class XmlHtmlOptions(BaseModel):
    """Options for XML to HTML conversion."""

    template: Literal["table", "list", "cards"] = Field(
        default="table",
        description="Built-in template to use",
    )
    custom_xslt: str | None = Field(
        default=None,
        description="Custom XSLT content (for async path)",
    )
    title: str | None = Field(
        default=None,
        description="HTML page title",
    )


# ===== XSLT Transform Options =====


class XmlTransformOptions(BaseModel):
    """Options for XML to XML transformation via XSLT."""

    xslt_content: str = Field(description="XSLT transformation content")
    preserve_declaration: bool = Field(
        default=True,
        description="Preserve XML declaration in output",
    )


# ===== Request/Response Models =====


class XmlConversionRequest(BaseModel):
    """Base request model for XML conversion."""

    options: dict = Field(default_factory=dict)


class XmlConversionResponse(BaseModel):
    """Base response model for XML conversion."""

    content: str = Field(description="Converted content as string")
    content_type: str = Field(description="MIME type of converted content")
    original_filename: str = Field(description="Original XML filename")


class XmlConversionErrorResponse(BaseModel):
    """Error response for XML conversion failures."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional error details")

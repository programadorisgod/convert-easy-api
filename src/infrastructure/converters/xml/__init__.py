"""XML conversion module."""

from .exceptions import (
    XmlConversionError,
    XmlSyntaxError,
    XmlMappingError,
    XmlXsltError,
    XmlSizeError,
    XmlMimeError,
    XmlValidationError,
)
from .schemas import (
    XmlHtmlOptions,
    XmlJsonOptions,
    XmlTransformOptions,
    XmlYamlOptions,
)
from .strategies import (
    ConversionResult,
    XmlConversionStrategy,
    HtmlStrategy,
    JsonStrategy,
    XsltStrategy,
    YamlStrategy,
)

__all__ = [
    # Exceptions
    "XmlConversionError",
    "XmlSyntaxError",
    "XmlMappingError",
    "XmlXsltError",
    "XmlSizeError",
    "XmlMimeError",
    "XmlValidationError",
    # Schemas
    "XmlJsonOptions",
    "XmlYamlOptions",
    "XmlHtmlOptions",
    "XmlTransformOptions",
    # Strategies
    "ConversionResult",
    "XmlConversionStrategy",
    "JsonStrategy",
    "YamlStrategy",
    "HtmlStrategy",
    "XsltStrategy",
]

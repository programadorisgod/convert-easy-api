"""XML converter orchestrator with strategy pattern."""

from .xml.strategies import (
    ConversionResult,
    XmlConversionStrategy,
    JsonStrategy,
    YamlStrategy,
    HtmlStrategy,
    XsltStrategy,
)
from .xml.exceptions import (
    XmlConversionError,
    XmlSizeError,
    XmlMimeError,
)

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


# Size thresholds in bytes
SYNC_THRESHOLD_JSON_YAML = 5 * 1024 * 1024  # 5MB
SYNC_THRESHOLD_HTML = 2 * 1024 * 1024  # 2MB
STREAMING_THRESHOLD = 1024 * 1024  # 1MB - use streaming above this

# Valid XML MIME types
VALID_XML_MIMES = {
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "application/atom+xml",
}


class XmlConverter:
    """
    Main orchestrator for XML conversions.

    Handles strategy selection, sync/async routing, and error handling.
    """

    # Strategy instances (singletons)
    _strategies: dict[str, XmlConversionStrategy] = {
        "json": JsonStrategy(),
        "yaml": YamlStrategy(),
        "html": HtmlStrategy(),
        "xslt": XsltStrategy(),
    }

    @classmethod
    def get_strategy(cls, output_format: str) -> XmlConversionStrategy:
        """Get strategy for output format."""
        strategy = cls._strategies.get(output_format.lower())
        if not strategy:
            raise XmlConversionError(
                f"Unsupported output format: {output_format}. "
                f"Supported: {list(cls._strategies.keys())}",
            )
        return strategy

    @classmethod
    def get_threshold(cls, output_format: str) -> int:
        """Get size threshold for sync conversion."""
        match output_format.lower():
            case "json" | "yaml":
                return SYNC_THRESHOLD_JSON_YAML
            case "html":
                return SYNC_THRESHOLD_HTML
            case "xslt":
                return 0  # Always async
            case _:
                return SYNC_THRESHOLD_JSON_YAML

    @classmethod
    def should_use_streaming(cls, file_size: int) -> bool:
        """Determine if streaming response should be used."""
        return file_size > STREAMING_THRESHOLD

    @classmethod
    def is_async(cls, output_format: str, file_size: int) -> bool:
        """Determine if conversion should be async based on format and size."""
        threshold = cls.get_threshold(output_format)
        return file_size >= threshold

    @classmethod
    def validate_xml(cls, content: bytes, filename: str = "") -> None:
        """
        Validate XML content.

        Args:
            content: XML file bytes
            filename: Original filename for error messages

        Raises:
            XmlMimeError: If content doesn't appear to be XML
            XmlSizeError: If content is empty
        """
        if not content:
            raise XmlSizeError("Empty file provided")

        # Check for XML-like content
        text = content[:100].decode("utf-8", errors="ignore").strip()
        if not (text.startswith("<?xml") or text.startswith("<")):
            raise XmlMimeError(
                f"File does not appear to be valid XML: {filename or 'content'}",
            )

    @classmethod
    async def convert(
        cls,
        xml_content: bytes,
        output_format: str,
        options: dict | None = None,
    ) -> ConversionResult:
        """
        Convert XML to target format.

        Args:
            xml_content: Raw XML bytes
            output_format: Target format (json, yaml, html, xslt)
            options: Format-specific options

        Returns:
            ConversionResult with converted content

        Raises:
            XmlConversionError: On any conversion failure
        """
        options = options or {}

        # Get and validate strategy
        strategy = cls.get_strategy(output_format)
        strategy.validate_options(options)

        # Perform conversion
        return await strategy.convert(xml_content, options)

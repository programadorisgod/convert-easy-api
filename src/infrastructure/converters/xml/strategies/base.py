"""Base classes for XML conversion strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from lxml import etree

from ..exceptions import XmlXsltError


@dataclass
class ConversionResult:
    """Result of an XML conversion operation."""

    content: bytes
    content_type: str
    original_filename: str
    preserve_declaration: bool = False


class XmlConversionStrategy(ABC):
    """Abstract base class for XML conversion strategies."""

    # Security: Elements/functions to strip from XSLT
    FORBIDDEN_ELEMENTS = {
        "document",  # Prevents reading external files
        "include",  # Prevents including external XSLT
        "import",  # Prevents importing external XSLT
        "write",  # Prevents writing files
    }

    @abstractmethod
    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """
        Convert XML content to target format.

        Args:
            xml_content: Raw XML bytes
            options: Format-specific options dict

        Returns:
            ConversionResult with converted content

        Raises:
            XmlSyntaxError: If XML is malformed
            XmlMappingError: If mapping configuration is invalid
            XmlXsltError: If XSLT transformation fails
        """
        pass

    @abstractmethod
    def validate_options(self, options: dict) -> None:
        """
        Validate format-specific options.

        Args:
            options: Options dict to validate

        Raises:
            XmlValidationError: If options are invalid
        """
        pass

    def get_content_type(self) -> str:
        """Return the MIME content type for this format."""
        return "application/octet-stream"

    def validate_xslt_content(self, xslt_content: str) -> None:
        """Validate XSLT syntax and block forbidden elements (security).

        Raises:
            XmlXsltError: If the XSLT is malformed or uses forbidden elements.
        """
        try:
            xslt_tree = etree.fromstring(xslt_content.encode("utf-8"))
            for element in self.FORBIDDEN_ELEMENTS:
                # Element usage, e.g. <xsl:include href="..."/>
                found = xslt_tree.xpath(f"//*[local-name()='{element}']")
                if found:
                    raise XmlXsltError(
                        f"Forbidden XSLT element '{element}' detected. "
                        "External document access is not allowed for security.",
                    )
                # Function-call usage, e.g. select="document('file:///etc/passwd')"
                function_calls = xslt_tree.xpath(
                    f"//@*[contains(., '{element}(')]"
                )
                if function_calls:
                    raise XmlXsltError(
                        f"Forbidden XSLT function '{element}(' detected. "
                        "External document access is not allowed for security.",
                    )
        except etree.XMLSyntaxError as e:
            raise XmlXsltError(f"Invalid XSLT syntax: {e}")

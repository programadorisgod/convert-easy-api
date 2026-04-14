"""Base classes for XML conversion strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ConversionResult:
    """Result of an XML conversion operation."""

    content: bytes
    content_type: str
    original_filename: str
    preserve_declaration: bool = False


class XmlConversionStrategy(ABC):
    """Abstract base class for XML conversion strategies."""

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

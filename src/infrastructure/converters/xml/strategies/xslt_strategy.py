"""XML to XML transformation strategy using XSLT."""

import asyncio

from lxml import etree

from .base import ConversionResult, XmlConversionStrategy
from ..exceptions import XmlSyntaxError, XmlXsltError, XmlValidationError
from ..schemas import XmlTransformOptions


class XsltStrategy(XmlConversionStrategy):
    """Transforms XML using XSLT with sandboxed execution."""

    def get_content_type(self) -> str:
        return "application/xml"

    def validate_options(self, options: dict) -> None:
        """Validate XSLT transformation options."""
        if not options:
            raise XmlValidationError(
                "XSLT transformation requires 'xslt_content' option",
            )

        try:
            opts = XmlTransformOptions(**options)
        except Exception as e:
            raise XmlValidationError(f"Invalid XSLT options: {e}")

        if not opts.xslt_content:
            raise XmlValidationError("xslt_content is required")

        # Validate XSLT syntax
        self.validate_xslt_content(opts.xslt_content)

    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """
        Transform XML using XSLT.

        Args:
            xml_content: Raw XML bytes
            options: XmlTransformOptions with xslt_content

        Returns:
            ConversionResult with transformed XML
        """
        try:
            opts = XmlTransformOptions(**options)

            # lxml parsing/XSLT is blocking C work: run off the event loop
            # so one request cannot freeze all others.
            xml_tree = await asyncio.to_thread(etree.fromstring, xml_content)
            xslt_tree = await asyncio.to_thread(
                etree.fromstring, opts.xslt_content.encode("utf-8")
            )

            # Create transformer
            transform = await asyncio.to_thread(etree.XSLT, xslt_tree)

            # Apply transformation
            result_tree = await asyncio.to_thread(transform, xml_tree)

            # Get XML string
            xml_output = await asyncio.to_thread(str, result_tree)

            # Add XML declaration if requested
            if opts.preserve_declaration:
                # XSLT already includes declaration, but ensure if not present
                if not xml_output.startswith("<?xml"):
                    xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_output

            return ConversionResult(
                content=xml_output.encode("utf-8"),
                content_type="application/xml",
                original_filename="",
                preserve_declaration=opts.preserve_declaration,
            )

        except etree.XMLSyntaxError as e:
            raise XmlSyntaxError(f"Invalid XML or XSLT: {e}")
        except etree.XSLTApplyError as e:
            raise XmlXsltError(f"XSLT transformation failed: {e}")
        except UnicodeDecodeError as e:
            raise XmlSyntaxError(f"Invalid encoding: {e}")

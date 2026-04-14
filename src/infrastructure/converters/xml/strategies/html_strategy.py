"""XML to HTML conversion strategy using XSLT templates."""

from lxml import etree

from .base import ConversionResult, XmlConversionStrategy
from ..exceptions import XmlSyntaxError, XmlValidationError
from ..schemas import XmlHtmlOptions


# Built-in XSLT templates
XSLT_TEMPLATES = {
    "table": """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes" encoding="UTF-8"/>
    
    <xsl:template match="/">
        <html>
            <head>
                <title>XML Data</title>
                <style>
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #4CAF50; color: white; }
                    tr:nth-child(even) { background-color: #f2f2f2; }
                </style>
            </head>
            <body>
                <table>
                    <tr>
                        <xsl:for-each select="*[1]/*">
                            <th><xsl:value-of select="name()"/></th>
                        </xsl:for-each>
                    </tr>
                    <xsl:for-each select="*/*">
                        <tr>
                            <xsl:for-each select="*">
                                <td><xsl:value-of select="."/></td>
                            </xsl:for-each>
                        </tr>
                    </xsl:for-each>
                </table>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>""",
    "list": """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes" encoding="UTF-8"/>
    
    <xsl:template match="/">
        <html>
            <head>
                <title>XML Data</title>
                <style>
                    ul { list-style-type: none; padding: 0; }
                    li { background: #f4f4f4; margin: 5px 0; padding: 10px; border-left: 4px solid #4CAF50; }
                    .key { font-weight: bold; color: #333; }
                </style>
            </head>
            <body>
                <h1>XML Content</h1>
                <ul>
                    <xsl:apply-templates select="*/*"/>
                </ul>
            </body>
        </html>
    </xsl:template>
    
    <xsl:template match="*">
        <li>
            <span class="key"><xsl:value-of select="name()"/>:</span>
            <xsl:choose>
                <xsl:when test="*">
                    <ul><xsl:apply-templates select="*"/></ul>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:value-of select="."/>
                </xsl:otherwise>
            </xsl:choose>
        </li>
    </xsl:template>
</xsl:stylesheet>""",
    "cards": """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes" encoding="UTF-8"/>
    
    <xsl:template match="/">
        <html>
            <head>
                <title>XML Data</title>
                <style>
                    .card-container { display: flex; flex-wrap: wrap; gap: 20px; }
                    .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; min-width: 200px; }
                    .card-title { font-size: 1.2em; font-weight: bold; margin-bottom: 10px; color: #4CAF50; }
                    .card-item { margin: 5px 0; }
                    .card-key { font-weight: bold; color: #666; }
                </style>
            </head>
            <body>
                <h1>XML Records</h1>
                <div class="card-container">
                    <xsl:for-each select="*/*">
                        <div class="card">
                            <div class="card-title"><xsl:value-of select="name()"/></div>
                            <xsl:for-each select="*">
                                <div class="card-item">
                                    <span class="card-key"><xsl:value-of select="name()"/>:</span>
                                    <xsl:value-of select="."/>
                                </div>
                            </xsl:for-each>
                        </div>
                    </xsl:for-each>
                </div>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>""",
}


class HtmlStrategy(XmlConversionStrategy):
    """Converts XML to HTML using XSLT templates."""

    def get_content_type(self) -> str:
        return "text/html"

    def validate_options(self, options: dict) -> None:
        """Validate HTML conversion options."""
        if options:
            try:
                opts = XmlHtmlOptions(**options)
                if opts.template not in XSLT_TEMPLATES and not opts.custom_xslt:
                    raise XmlValidationError(
                        f"Invalid template '{opts.template}'. "
                        f"Valid options: {list(XSLT_TEMPLATES.keys())}",
                    )
            except Exception as e:
                raise XmlValidationError(f"Invalid HTML options: {e}")

    async def convert(self, xml_content: bytes, options: dict) -> ConversionResult:
        """
        Convert XML to HTML using XSLT.

        Args:
            xml_content: Raw XML bytes
            options: XmlHtmlOptions with template or custom_xslt

        Returns:
            ConversionResult with HTML content
        """
        try:
            opts = XmlHtmlOptions(**options) if options else XmlHtmlOptions()

            # Get XSLT content
            if opts.custom_xslt:
                xslt_content = opts.custom_xslt
            else:
                xslt_content = XSLT_TEMPLATES.get(
                    opts.template, XSLT_TEMPLATES["table"]
                )

            # Parse XML and XSLT
            xml_tree = etree.fromstring(xml_content)
            xslt_tree = etree.fromstring(xslt_content.encode("utf-8"))

            # Create transformer
            transform = etree.XSLT(xslt_tree)

            # Apply transformation
            result_tree = transform(xml_tree)

            # Get HTML string
            html_content = str(result_tree)

            # Update title if provided
            if opts.title and opts.title in html_content:
                html_content = html_content.replace("XML Data", opts.title)

            return ConversionResult(
                content=html_content.encode("utf-8"),
                content_type="text/html",
                original_filename="",
                preserve_declaration=False,
            )

        except etree.XMLSyntaxError as e:
            raise XmlSyntaxError(f"Invalid XML or XSLT: {e}")
        except etree.XSLTApplyError as e:
            raise XmlSyntaxError(f"XSLT transformation failed: {e}")
        except UnicodeDecodeError as e:
            raise XmlSyntaxError(f"Invalid encoding: {e}")

    @classmethod
    def get_available_templates(cls) -> list[str]:
        """Return list of available template names."""
        return list(XSLT_TEMPLATES.keys())

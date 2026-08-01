"""Behavior tests for XML conversion security.

Tests observable API behavior: user-supplied XSLT must never be able to
read server files, and built-in templates must keep working.
"""

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.converters.xml.exceptions import XmlXsltError
from src.infrastructure.converters.xml.strategies.html_strategy import HtmlStrategy
from src.main import app


# XSLT that tries to read a local file via document()
MALICIOUS_XSLT = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html"/>
    <xsl:template match="/">
        <html><body><pre>
        <xsl:value-of select="document('file:///etc/passwd')"/>
        </pre></body></html>
    </xsl:template>
</xsl:stylesheet>"""

XML_CONTENT = b"""<?xml version="1.0" encoding="UTF-8"?>
<catalog><book><title>Clean Code</title></book></catalog>"""


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Behavior: custom XSLT must never run synchronously
# ---------------------------------------------------------------------------

def test_custom_xslt_is_rejected_as_async_only(client):
    """Custom XSLT is async-only; the sync endpoint must not process it."""
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", XML_CONTENT, "application/xml")},
        data={"custom_xslt": MALICIOUS_XSLT},
    )

    assert response.status_code == 501


def test_malicious_xslt_cannot_leak_server_files(client):
    """A malicious custom XSLT must never read /etc/passwd in a sync request."""
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", XML_CONTENT, "application/xml")},
        data={"custom_xslt": MALICIOUS_XSLT},
    )

    # Whatever the status, the server file contents must not be returned.
    assert response.status_code != 200
    assert "root:" not in response.text


# ---------------------------------------------------------------------------
# Behavior: built-in templates keep working
# ---------------------------------------------------------------------------

def test_builtin_template_still_converts(client):
    """Built-in templates (no custom XSLT) must keep producing HTML."""
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", XML_CONTENT, "application/xml")},
        data={"template": "table"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<table" in response.text


# ---------------------------------------------------------------------------
# Behavior: user-supplied title must not inject HTML/JS (XSS)
# ---------------------------------------------------------------------------

def test_title_script_injection_is_escaped(client):
    """A </title><script> payload must never become live markup."""
    payload = "</title><script>alert(1)</script>"
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", XML_CONTENT, "application/xml")},
        data={"template": "table", "title": payload},
    )

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;/title&gt;" in response.text


def test_title_ampersand_is_escaped(client):
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", XML_CONTENT, "application/xml")},
        data={"template": "table", "title": "A & B"},
    )

    assert response.status_code == 200
    assert "A &amp; B" in response.text
    assert "A & B" not in response.text


def test_title_only_replaces_title_tag_not_body(client):
    """'XML Data' text inside the document body must not be overwritten."""
    xml_with_data_text = b"""<?xml version="1.0" encoding="UTF-8"?>
<catalog><book><title>XML Data</title></book></catalog>"""
    response = client.post(
        "/api/v1/convert/xml/html",
        files={"file": ("catalog.xml", xml_with_data_text, "application/xml")},
        data={"template": "table", "title": "My Title"},
    )

    assert response.status_code == 200
    # The page <title> was replaced…
    assert "<title>My Title</title>" in response.text
    # …but the body still shows the original XML value untouched.
    assert "<td>XML Data</td>" in response.text


@pytest.mark.asyncio
async def test_html_strategy_escapes_title():
    strategy = HtmlStrategy()
    result = await strategy.convert(
        XML_CONTENT,
        {"template": "table", "title": '<img src=x onerror=alert(1)>'},
    )

    assert b"<img src=x onerror=alert(1)>" not in result.content
    assert b"&lt;img src=x onerror=alert(1)&gt;" in result.content


# ---------------------------------------------------------------------------
# Defense in depth: the strategy itself must reject forbidden XSLT elements
# (this is what protects the future async path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_html_strategy_rejects_document_element():
    strategy = HtmlStrategy()

    with pytest.raises(XmlXsltError):
        await strategy.convert(
            XML_CONTENT,
            {"template": "table", "custom_xslt": MALICIOUS_XSLT},
        )


@pytest.mark.asyncio
async def test_html_strategy_allows_safe_custom_xslt():
    """A custom XSLT without forbidden elements must still work."""
    strategy = HtmlStrategy()
    safe_xslt = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html"/>
    <xsl:template match="/">
        <html><body><h1><xsl:value-of select="catalog/book/title"/></h1></body></html>
    </xsl:template>
</xsl:stylesheet>"""

    result = await strategy.convert(
        XML_CONTENT,
        {"template": "table", "custom_xslt": safe_xslt},
    )

    assert b"Clean Code" in result.content

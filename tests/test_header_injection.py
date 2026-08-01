"""Behavior tests for header injection via user-controlled file names.

A user-supplied filename must never reach a response header raw: CR/LF
would inject arbitrary HTTP headers, quotes would break the
Content-Disposition quoting.
"""

from fastapi.testclient import TestClient

from shared.http import safe_download_filename
from src.main import app

XML_CONTENT = b"""<?xml version="1.0" encoding="UTF-8"?>
<catalog><book><title>Clean Code</title></book></catalog>"""


class TestSafeDownloadFilename:
    def test_crlf_stripped(self):
        assert (
            safe_download_filename("evil.xml\r\nX-Injected: yes")
            == "evil.xmlX-Injected: yes"
        )

    def test_quotes_stripped(self):
        assert safe_download_filename('foo"bar.xml') == "foobar.xml"

    def test_basename_only(self):
        assert safe_download_filename("../../etc/passwd.xml") == "passwd.xml"

    def test_control_chars_stripped(self):
        assert safe_download_filename("evil\x00.xml") == "evil.xml"

    def test_none_returns_fallback(self):
        assert safe_download_filename(None, "converted.json") == "converted.json"

    def test_empty_returns_fallback(self):
        assert safe_download_filename("", "converted.json") == "converted.json"

    def test_only_dots_returns_fallback(self):
        assert safe_download_filename("....", "converted.json") == "converted.json"

    def test_normal_name_preserved(self):
        assert safe_download_filename("report.xml") == "report.xml"


class TestXmlConversionHeaderInjection:
    def _post(self, client: TestClient, filename: str):
        return client.post(
            "/api/v1/convert/xml/json",
            files={"file": (filename, XML_CONTENT, "application/xml")},
        )

    def test_filename_with_crlf_does_not_inject_header(self):
        client = TestClient(app)
        response = self._post(client, "evil.xml\r\nX-Injected: yes")
        assert response.status_code == 200
        # No literal CR/LF may reach the header value: that is what would
        # allow header injection. The framework percent-encodes the name.
        disposition = response.headers["content-disposition"]
        assert "\r" not in disposition
        assert "\n" not in disposition
        assert "x-injected" not in response.headers

    def test_filename_with_quotes_does_not_break_disposition(self):
        client = TestClient(app)
        response = self._post(client, 'foo"bar.xml')
        assert response.status_code == 200
        disposition = response.headers["content-disposition"]
        # A single well-formed Content-Disposition with two quotes: open/close.
        assert disposition.startswith("attachment; filename=")
        assert disposition.count('"') == 2

    def test_normal_filename_still_used(self):
        client = TestClient(app)
        response = self._post(client, "catalog.xml")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == (
            'attachment; filename="catalog.json"'
        )

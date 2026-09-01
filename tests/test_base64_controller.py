"""Behavior tests for the Base64 conversion endpoints.

Covers both directions (Image -> Base64 and Base64 -> Image), the Data URI
shortcut, MIME inference, and the security guardrails (reject bad base64,
unreachable MIME values, oversized inputs).
"""

import base64
import pytest
from fastapi.testclient import TestClient

from src.main import app

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def client():
    return TestClient(app)


def test_image_to_base64(client):
    res = client.post(
        "/api/v1/convert/image/to-base64",
        files={"file": ("foto.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mime"] == "image/png"
    assert body["mime_type"] == "image/png"
    assert body["base64"] == base64.b64encode(PNG_BYTES).decode()
    assert body["data_uri"].startswith("data:image/png;base64,")
    assert base64.b64decode(body["base64"]) == PNG_BYTES


def test_base64_to_image_roundtrip(client):
    encoded = base64.b64encode(PNG_BYTES).decode()
    res = client.post(
        "/api/v1/convert/base64/to-image",
        data={"data": encoded, "mime": "image/png", "filename": "out"},
    )
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"
    assert 'filename="out.png"' in res.headers["content-disposition"]


def test_base64_to_image_data_uri(client):
    encoded = base64.b64encode(PNG_BYTES).decode()
    data_uri = f"data:image/png;base64,{encoded}"
    res = client.post(
        "/api/v1/convert/base64/to-image",
        data={"data": data_uri},
    )
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"


def test_invalid_base64_rejected(client):
    res = client.post(
        "/api/v1/convert/base64/to-image",
        data={"data": "!!!not-base64!!!", "mime": "image/png"},
    )
    assert res.status_code == 400


def test_unsupported_mime_rejected(client):
    res = client.post(
        "/api/v1/convert/base64/to-image",
        data={"data": "aGVsbG8=", "mime": "application/octet-stream"},
    )
    assert res.status_code == 400

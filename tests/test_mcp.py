"""Automated tests for Easy Convert MCP Server using real conversion calls."""

from pathlib import Path
import pytest
from src.interfaces.mcp.server import server


@pytest.mark.asyncio
async def test_mcp_list_tools():
    """Verify all 12 tools are registered on MCPServer."""
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "convert_image",
        "remove_image_background",
        "images_to_pdf",
        "convert_document",
        "pdf_merge",
        "pdf_split",
        "pdf_rotate",
        "pdf_encrypt",
        "pdf_decrypt",
        "convert_audio",
        "convert_video",
        "video_extract_audio",
        "convert_xml",
        "base64_encode_image",
        "base64_decode_image",
    }
    assert expected.issubset(tool_names)


@pytest.mark.asyncio
async def test_mcp_convert_document_real(tmp_path: Path):
    """Test convert_document tool with real 100 ideas.docx from ~/Descargas."""
    real_docx = Path("/home/camidev/Descargas/100 ideas.docx")
    if not real_docx.exists():
        pytest.skip("100 ideas.docx not in Descargas")

    out_pdf = tmp_path / "mcp_100_ideas.pdf"
    res = await server.call_tool(
        "convert_document",
        {
            "input_path": str(real_docx),
            "format": "pdf",
            "output_path": str(out_pdf),
        },
    )
    assert not res.is_error
    assert out_pdf.is_file()
    assert out_pdf.stat().st_size > 0


@pytest.mark.asyncio
async def test_mcp_convert_image_real(tmp_path: Path):
    """Test convert_image tool with real logo.png from ~/Descargas."""
    real_logo = Path("/home/camidev/Descargas/logo.png")
    if not real_logo.exists():
        pytest.skip("logo.png not in Descargas")

    out_webp = tmp_path / "mcp_logo.webp"
    res = await server.call_tool(
        "convert_image",
        {
            "input_path": str(real_logo),
            "format": "webp",
            "output_path": str(out_webp),
            "quality": 80,
        },
    )
    assert not res.is_error
    assert out_webp.is_file()
    assert out_webp.stat().st_size > 0


@pytest.mark.asyncio
async def test_mcp_convert_audio_real(tmp_path: Path):
    """Test convert_audio tool with real MP3 from ~/Descargas."""
    real_audio = Path("/home/camidev/Descargas/YTDown.com_YouTube_Media_qmdF1X2IDLU_The-Undertaker-Bell-Sound-Effect_009_128k.mp3")
    if not real_audio.exists():
        pytest.skip("MP3 not in Descargas")

    out_wav = tmp_path / "mcp_bell.wav"
    res = await server.call_tool(
        "convert_audio",
        {
            "input_path": str(real_audio),
            "format": "wav",
            "output_path": str(out_wav),
            "normalize": True,
        },
    )
    assert not res.is_error
    assert out_wav.is_file()
    assert out_wav.stat().st_size > 0


@pytest.mark.asyncio
async def test_mcp_convert_video_real(tmp_path: Path):
    """Test convert_video tool with real eter.mp4 from ~/Descargas."""
    real_video = Path("/home/camidev/Descargas/eter.mp4")
    if not real_video.exists():
        pytest.skip("eter.mp4 not in Descargas")

    out_webm = tmp_path / "mcp_eter.webm"
    res = await server.call_tool(
        "convert_video",
        {
            "input_path": str(real_video),
            "format": "webm",
            "output_path": str(out_webm),
            "crf": 28,
        },
    )
    assert not res.is_error
    assert out_webm.is_file()
    assert out_webm.stat().st_size > 0


@pytest.mark.asyncio
async def test_mcp_xml_to_json(tmp_path: Path):
    """Test convert_xml tool."""
    xml_file = tmp_path / "data.xml"
    xml_file.write_text("<user><name>Antigravity</name><role>Assistant</role></user>", encoding="utf-8")
    out_json = tmp_path / "data.json"

    res = await server.call_tool(
        "convert_xml",
        {
            "input_path": str(xml_file),
            "format": "json",
            "output_path": str(out_json),
        },
    )
    assert not res.is_error
    assert out_json.is_file()
    assert "Antigravity" in out_json.read_text(encoding="utf-8")

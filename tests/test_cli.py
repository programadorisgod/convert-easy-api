"""Automated tests for the Easy Convert CLI."""

import base64
from pathlib import Path
import pytest
from typer.testing import CliRunner

from src.interfaces.cli.main import app

runner = CliRunner()


def test_cli_version():
    """Verify version command output."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Easy Convert API & CLI" in result.stdout


def test_cli_help():
    """Verify top-level help lists main command groups."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "image" in result.stdout
    assert "audio" in result.stdout
    assert "video" in result.stdout
    assert "doc" in result.stdout
    assert "pdf" in result.stdout
    assert "xml" in result.stdout
    assert "base64" in result.stdout
    assert "serve" in result.stdout


@pytest.mark.parametrize(
    "subcommand",
    ["image", "audio", "video", "doc", "pdf", "xml", "base64"],
)
def test_subcommand_helps(subcommand: str):
    """Verify each subcommand provides helpful guidance."""
    result = runner.invoke(app, [subcommand, "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout


def test_base64_encode_and_decode(tmp_path: Path):
    """Test full base64 roundtrip via CLI."""
    sample_img = tmp_path / "test.png"
    sample_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    # 1. Encode to Data URI
    res_enc = runner.invoke(app, ["base64", "encode", str(sample_img)])
    assert res_enc.exit_code == 0
    data_uri = res_enc.stdout.strip()
    assert data_uri.startswith("data:image/png;base64,")

    # 2. Decode back to image
    out_img = tmp_path / "decoded.png"
    res_dec = runner.invoke(app, ["base64", "decode", data_uri, "-o", str(out_img)])
    assert res_dec.exit_code == 0
    assert out_img.is_file()
    assert out_img.read_bytes() == sample_img.read_bytes()


def test_xml_to_json_and_yaml(tmp_path: Path):
    """Test XML conversions via CLI."""
    xml_file = tmp_path / "note.xml"
    xml_file.write_text("<note><to>Alice</to><from>Bob</from><msg>Hello</msg></note>", encoding="utf-8")

    # to-json
    json_out = tmp_path / "note.json"
    res_json = runner.invoke(app, ["xml", "to-json", str(xml_file), "-o", str(json_out)])
    assert res_json.exit_code == 0
    assert json_out.is_file()
    assert '"Alice"' in json_out.read_text(encoding="utf-8")

    # to-yaml
    yaml_out = tmp_path / "note.yaml"
    res_yaml = runner.invoke(app, ["xml", "to-yaml", str(xml_file), "-o", str(yaml_out)])
    assert res_yaml.exit_code == 0
    assert yaml_out.is_file()
    assert "Alice" in yaml_out.read_text(encoding="utf-8")


def test_image_convert_cli(tmp_path: Path):
    """Test image format conversion with ImageMagick via CLI."""
    import shutil
    if not shutil.which("magick"):
        pytest.skip("ImageMagick is not installed")

    # Create a small valid PNG using Pillow
    from PIL import Image
    input_png = tmp_path / "sample.png"
    img = Image.new("RGB", (30, 30), color="blue")
    img.save(input_png)

    output_webp = tmp_path / "sample.webp"
    result = runner.invoke(app, ["image", "convert", str(input_png), "-f", "webp", "-o", str(output_webp)])
    assert result.exit_code == 0
    assert output_webp.is_file()
    assert output_webp.stat().st_size > 0


def test_pdf_merge_and_split_cli(tmp_path: Path):
    """Test PDF merge and split operations via CLI."""
    import fitz  # PyMuPDF

    # Create two 1-page PDFs
    pdf1 = tmp_path / "doc1.pdf"
    doc1 = fitz.open()
    doc1.new_page()
    doc1.save(pdf1)
    doc1.close()

    pdf2 = tmp_path / "doc2.pdf"
    doc2 = fitz.open()
    doc2.new_page()
    doc2.save(pdf2)
    doc2.close()

    # Merge
    merged_pdf = tmp_path / "merged.pdf"
    res_merge = runner.invoke(app, ["pdf", "merge", str(pdf1), str(pdf2), "-o", str(merged_pdf)])
    assert res_merge.exit_code == 0
    assert merged_pdf.is_file()

    chk_merge = fitz.open(merged_pdf)
    assert len(chk_merge) == 2
    chk_merge.close()

    # Split (extract page 1)
    split_pdf = tmp_path / "split.pdf"
    res_split = runner.invoke(app, ["pdf", "split", str(merged_pdf), "-p", "1", "-o", str(split_pdf)])
    assert res_split.exit_code == 0
    assert split_pdf.is_file()

    chk_split = fitz.open(split_pdf)
    assert len(chk_split) == 1
    chk_split.close()


def test_audio_convert_cli(tmp_path: Path):
    """Test audio conversion using ffmpeg via CLI."""
    import subprocess
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is not installed")

    audio_wav = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", str(audio_wav)],
        check=True,
        capture_output=True,
    )

    audio_mp3 = tmp_path / "tone.mp3"
    result = runner.invoke(app, ["audio", "convert", str(audio_wav), "-f", "mp3", "-o", str(audio_mp3), "--bitrate", "128k"])
    assert result.exit_code == 0
    assert audio_mp3.is_file()
    assert audio_mp3.stat().st_size > 0


def test_video_convert_cli(tmp_path: Path):
    """Test video conversion using ffmpeg via CLI."""
    import subprocess
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is not installed")

    vid_mp4 = tmp_path / "test.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10", str(vid_mp4)],
        check=True,
        capture_output=True,
    )

    vid_webm = tmp_path / "test.webm"
    result = runner.invoke(app, ["video", "convert", str(vid_mp4), "-f", "webm", "-o", str(vid_webm)])
    assert result.exit_code == 0
    assert vid_webm.is_file()
    assert vid_webm.stat().st_size > 0


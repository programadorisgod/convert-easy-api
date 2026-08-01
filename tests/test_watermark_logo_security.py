"""Security tests for logo watermark path handling.

The logo_path is user-controlled and previously reached ImageMagick as a
raw path argument, enabling @file LFI, URL fetches (SSRF) and ImageMagick
pseudo-protocols. It must only ever resolve to a plain file name inside
the configured logos directory.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shared.exceptions import ValidationError
from src.infrastructure.converters.watermark_service import (
    resolve_watermark_logo,
)
from src.infrastructure.worker.conversion_worker import ConversionWorker


@pytest.fixture
def logo_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logos"
    d.mkdir()
    (d / "brand.png").write_bytes(b"fake png")
    return d


class TestResolveWatermarkLogo:
    def test_plain_existing_name_resolves(self, logo_dir: Path):
        resolved = resolve_watermark_logo("brand.png", logo_dir)
        assert resolved == logo_dir / "brand.png"

    @pytest.mark.parametrize(
        "malicious",
        [
            "@/etc/passwd",  # ImageMagick @file LFI
            "/etc/passwd",  # absolute path
            "../../etc/passwd",  # traversal
            "https://evil.com/logo.png",  # SSRF via URL
            "msl:/tmp/evil.msl",  # ImageMagick pseudo-protocol
            "|sh -c id",  # pipe execution
            "@brand.png",  # @ prefix on a valid name
            "brand png.png",  # spaces
            "brand;png",  # shell metachar
        ],
    )
    def test_malicious_paths_rejected(self, logo_dir: Path, malicious: str):
        with pytest.raises(ValidationError):
            resolve_watermark_logo(malicious, logo_dir)

    def test_missing_logo_rejected(self, logo_dir: Path):
        with pytest.raises(ValidationError):
            resolve_watermark_logo("missing.png", logo_dir)

    def test_none_rejected(self, logo_dir: Path):
        with pytest.raises(ValidationError):
            resolve_watermark_logo(None, logo_dir)

    def test_scheme_with_existing_name_does_not_escape(
        self, logo_dir: Path, tmp_path: Path
    ):
        # Even a "name" that exists elsewhere must not resolve outside logo_dir.
        (tmp_path / "brand.png").write_bytes(b"outside")
        resolved = resolve_watermark_logo("https://x/brand.png", logo_dir)
        assert resolved == logo_dir / "brand.png"


class TestWorkerBuildPipelineConfig:
    def _make_worker(self, logo_dir: Path) -> ConversionWorker:
        worker = ConversionWorker("redis://x", MagicMock(), MagicMock())
        worker.settings = MagicMock(watermark_logo_dir=logo_dir)
        return worker

    def test_malicious_logo_path_fails_job_config(self, logo_dir: Path):
        worker = self._make_worker(logo_dir)
        config_data = {
            "watermark_enabled": True,
            "watermark_type": "logo",
            "watermark_params": {"logo_path": "@/etc/passwd"},
        }
        with pytest.raises(ValidationError):
            worker._build_pipeline_config(config_data, "png")

    def test_valid_logo_path_resolves_in_config(self, logo_dir: Path):
        worker = self._make_worker(logo_dir)
        config_data = {
            "watermark_enabled": True,
            "watermark_type": "logo",
            "watermark_params": {"logo_path": "brand.png"},
        }
        config = worker._build_pipeline_config(config_data, "png")
        assert config.watermark_logo_path == logo_dir / "brand.png"

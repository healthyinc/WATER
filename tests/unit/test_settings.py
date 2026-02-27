"""
Unit tests for WATER configuration settings.
"""

from __future__ import annotations

from pathlib import Path

from water.config.settings import OrthancSettings, TCIASettings, WATERSettings


class TestOrthancSettings:
    """Verify Orthanc config defaults and derived properties."""

    def test_defaults(self) -> None:
        s = OrthancSettings()
        assert s.host == "localhost"
        assert s.http_port == 8042
        assert s.dicom_port == 4242

    def test_base_url(self) -> None:
        s = OrthancSettings(host="myhost", http_port=9999)
        assert s.base_url == "http://myhost:9999"


class TestTCIASettings:
    """Verify TCIA config defaults."""

    def test_defaults(self) -> None:
        s = TCIASettings()
        assert s.collection == "LIDC-IDRI"
        assert s.max_series == 5
        assert isinstance(s.download_dir, Path)


class TestWATERSettings:
    """Verify top-level settings composition."""

    def test_nested_defaults(self) -> None:
        s = WATERSettings()
        assert s.log_level == "INFO"
        assert s.orthanc.http_port == 8042
        assert s.tcia.collection == "LIDC-IDRI"

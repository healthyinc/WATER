"""
Integration tests for Orthanc connectivity.

These tests require a running Orthanc instance and are skipped
by default in CI. Run with: ``make test-integration``
"""

from __future__ import annotations

import pytest

from water.config.settings import get_settings
from water.dicom.orthanc_client import OrthancClient


@pytest.fixture
def orthanc_client() -> OrthancClient:
    """Create an OrthancClient pointing at the dev Orthanc instance."""
    settings = get_settings()
    return OrthancClient(
        base_url=settings.orthanc.base_url,
        username=settings.orthanc.username,
        password=settings.orthanc.password,
    )


@pytest.mark.integration
class TestOrthancIntegration:
    """Smoke tests against a live Orthanc server."""

    def test_server_is_alive(self, orthanc_client: OrthancClient) -> None:
        assert orthanc_client.is_alive(), "Orthanc server is not reachable"

    def test_system_info_has_version(self, orthanc_client: OrthancClient) -> None:
        info = orthanc_client.get_system_info()
        assert "Version" in info

    def test_statistics_returns_counts(self, orthanc_client: OrthancClient) -> None:
        stats = orthanc_client.get_statistics()
        assert "CountInstances" in stats

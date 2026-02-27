"""
WATER Framework — Configuration Settings.

Centralized, type-safe configuration using pydantic-settings.
All values can be overridden via environment variables prefixed with ``WATER_``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrthancSettings(BaseSettings):
    """Connection settings for the Orthanc DICOM server."""

    model_config = SettingsConfigDict(env_prefix="ORTHANC_")

    host: str = Field(default="localhost", description="Orthanc hostname")
    http_port: int = Field(default=8042, description="Orthanc REST API port")
    dicom_port: int = Field(default=4242, description="Orthanc DICOM protocol port")
    username: str = Field(default="", description="Orthanc basic-auth username (empty = auth disabled)")
    password: str = Field(default="", description="Orthanc basic-auth password")

    @property
    def base_url(self) -> str:
        """Return the fully-qualified Orthanc REST API base URL."""
        return f"http://{self.host}:{self.http_port}"


class TCIASettings(BaseSettings):
    """Settings for The Cancer Imaging Archive (TCIA) REST API."""

    model_config = SettingsConfigDict(env_prefix="TCIA_")

    base_url: str = Field(
        default="https://services.cancerimagingarchive.net/nbia-api/services/v1",
        description="TCIA NBIA REST API base URL",
    )
    collection: str = Field(
        default="LIDC-IDRI",
        description="Default TCIA collection to query",
    )
    max_series: int = Field(
        default=5,
        description="Maximum number of series to download in a bootstrap run",
    )
    batch_size: int = Field(
        default=1,
        description="Number of series to download concurrently",
    )
    download_dir: Path = Field(
        default=Path("data/tcia_downloads"),
        description="Local directory for downloaded DICOM files",
    )


class WATERSettings(BaseSettings):
    """Top-level WATER framework settings."""

    model_config = SettingsConfigDict(
        env_prefix="WATER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO", description="Logging verbosity (DEBUG, INFO, WARNING, ERROR)")
    log_format: str = Field(default="console", description="Log output format: 'console' or 'json'")
    data_dir: Path = Field(default=Path("data"), description="Root data directory")

    orthanc: OrthancSettings = Field(default_factory=OrthancSettings)
    tcia: TCIASettings = Field(default_factory=TCIASettings)


def get_settings() -> WATERSettings:
    """Factory function to create a validated settings instance."""
    return WATERSettings()

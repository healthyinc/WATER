"""
WATER Framework — Orthanc REST Client.

Provides a typed, async-capable client for interacting with the Orthanc
DICOM server's REST API. This is the primary programmatic interface
for uploading DICOM instances and querying server state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class OrthancClient:
    """Synchronous HTTP client for the Orthanc REST API.

    Handles authentication, retries on transient errors, and
    structured logging for every operation.

    Args:
        base_url: Orthanc REST API root (e.g. ``http://localhost:8042``).
        username: Basic-auth username (omit if auth is disabled).
        password: Basic-auth password.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8042",
        username: str = "",
        password: str = "",
        timeout: float = 30.0,
    ) -> None:
        auth = (username, password) if username else None
        self._client = httpx.Client(
            base_url=base_url,
            auth=auth,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._base_url = base_url

    # Lifecycle

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> OrthancClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # Server introspection

    def get_system_info(self) -> dict[str, Any]:
        """Return Orthanc server system information.

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx status.
        """
        resp = self._client.get("/system")
        resp.raise_for_status()
        return resp.json()

    def is_alive(self) -> bool:
        """Check whether the Orthanc server is reachable."""
        try:
            self.get_system_info()
            return True
        except (httpx.HTTPError, httpx.ConnectError):
            return False

    # Statistics

    def get_statistics(self) -> dict[str, Any]:
        """Return storage statistics (patient/study/series/instance counts)."""
        resp = self._client.get("/statistics")
        resp.raise_for_status()
        return resp.json()

    # Upload

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def upload_dicom(self, dicom_bytes: bytes) -> dict[str, Any]:
        """Upload a single DICOM instance to Orthanc.

        Args:
            dicom_bytes: Raw bytes of a ``.dcm`` file.

        Returns:
            Orthanc response dict containing the instance ID and status.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
        """
        resp = self._client.post(
            "/instances",
            content=dicom_bytes,
            headers={"Content-Type": "application/dicom"},
        )
        resp.raise_for_status()
        return resp.json()

    def upload_dicom_file(self, path: Path) -> dict[str, Any]:
        """Convenience wrapper: read a ``.dcm`` file from disk and upload it.

        Args:
            path: Filesystem path to a DICOM file.

        Returns:
            Orthanc response dict.
        """
        data = path.read_bytes()
        result = self.upload_dicom(data)
        logger.debug("Uploaded %s → %s", path.name, result.get("ID", "unknown"))
        return result

    # Query

    def list_patients(self) -> list[str]:
        """Return the list of Orthanc patient IDs."""
        resp = self._client.get("/patients")
        resp.raise_for_status()
        return resp.json()

    def list_studies(self) -> list[str]:
        """Return the list of Orthanc study IDs."""
        resp = self._client.get("/studies")
        resp.raise_for_status()
        return resp.json()

    def list_series(self) -> list[str]:
        """Return the list of Orthanc series IDs."""
        resp = self._client.get("/series")
        resp.raise_for_status()
        return resp.json()

    def list_instances(self) -> list[str]:
        """Return the list of Orthanc instance IDs."""
        resp = self._client.get("/instances")
        resp.raise_for_status()
        return resp.json()

    def get_instance_tags(self, instance_id: str) -> dict[str, Any]:
        """Return DICOM tags for a specific instance.

        Args:
            instance_id: Orthanc instance identifier.
        """
        resp = self._client.get(f"/instances/{instance_id}/simplified-tags")
        resp.raise_for_status()
        return resp.json()

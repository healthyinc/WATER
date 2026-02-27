"""
WATER Framework — TCIA (The Cancer Imaging Archive) Client.

Provides functions to discover imaging collections on TCIA and
download DICOM series as ZIP archives via the NBIA REST API.

API Reference: https://wiki.cancerimagingarchive.net/display/Public/TCIA+Programmatic+Interface+REST+API+Guides
"""

from __future__ import annotations

import io
import logging
import zipfile
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

# NBIA API changed to require authentication for most endpoints.
# The public v2 search API still provides unauthenticated access for
# public collections.
_DEFAULT_BASE_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
_NBIA_SEARCH_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v2"


class TCIAClient:
    """Client for the TCIA NBIA REST API.

    Supports querying collection metadata and downloading DICOM series.

    Args:
        base_url: NBIA v1 REST endpoint.
        timeout: HTTP timeout in seconds for metadata queries.
        download_timeout: HTTP timeout in seconds for large downloads.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 30.0,
        download_timeout: float = 300.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        self._download_timeout = download_timeout
        self._base_url = base_url

    # -- Lifecycle --------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TCIAClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # -- Collection metadata ----------------------------------------------

    def get_collections(self) -> list[dict[str, Any]]:
        """Return all available TCIA collections."""
        resp = self._client.get("/getCollectionValues")
        resp.raise_for_status()
        return resp.json()

    def get_patient_ids(self, collection: str) -> list[dict[str, Any]]:
        """Return patient IDs within a given collection.

        Args:
            collection: TCIA collection name (e.g. ``"LIDC-IDRI"``).
        """
        resp = self._client.get("/getPatient", params={"Collection": collection})
        resp.raise_for_status()
        return resp.json()

    def get_series(self, collection: str) -> list[dict[str, Any]]:
        """Return series metadata for a collection.

        Args:
            collection: TCIA collection name.
        """
        resp = self._client.get("/getSeries", params={"Collection": collection})
        resp.raise_for_status()
        return resp.json()

    def get_series_for_patient(self, collection: str, patient_id: str) -> list[dict[str, Any]]:
        """Return series metadata for a specific patient in a collection."""
        resp = self._client.get(
            "/getSeries",
            params={"Collection": collection, "PatientID": patient_id},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Download ---------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    def download_series(
        self,
        series_instance_uid: str,
        output_dir: Path,
    ) -> list[Path]:
        """Download a DICOM series as a ZIP and extract to *output_dir*.

        Args:
            series_instance_uid: The DICOM ``SeriesInstanceUID``.
            output_dir: Directory to extract DICOM files into.

        Returns:
            List of paths to the extracted ``.dcm`` files.
        """
        logger.info("Downloading series %s …", series_instance_uid)

        # Use streaming download to handle large series
        with httpx.Client(timeout=self._download_timeout, follow_redirects=True) as dl_client:
            resp = dl_client.get(
                f"{self._base_url}/getImage",
                params={"SeriesInstanceUID": series_instance_uid},
            )
            resp.raise_for_status()

        series_dir = output_dir / series_instance_uid
        series_dir.mkdir(parents=True, exist_ok=True)

        extracted_files: list[Path] = []

        # TCIA returns a ZIP archive containing DICOM files
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for member in zf.namelist():
                    if member.endswith("/"):
                        continue  # skip directories
                    target = series_dir / Path(member).name
                    target.write_bytes(zf.read(member))
                    extracted_files.append(target)
        except zipfile.BadZipFile:
            # Some endpoints return raw DICOM instead of ZIP
            logger.warning("Response was not a ZIP; saving as single DICOM file.")
            single = series_dir / f"{series_instance_uid}.dcm"
            single.write_bytes(resp.content)
            extracted_files.append(single)

        logger.info(
            "Extracted %d file(s) for series %s → %s",
            len(extracted_files),
            series_instance_uid,
            series_dir,
        )
        return extracted_files

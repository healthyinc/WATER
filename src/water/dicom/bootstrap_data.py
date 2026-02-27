"""
WATER Framework — Bootstrap Data Pipeline.

End-to-end script that:
1. Queries TCIA for a specified imaging collection.
2. Downloads DICOM series in batches to a local staging directory.
3. Pushes each DICOM file to an Orthanc server via its REST API.

This is the primary entrypoint for Phase 1.1 — standing up a
populated local DICOM server for downstream WATER development.

Usage:
    python -m water.dicom.bootstrap_data          # uses defaults from .env
    python -m water.dicom.bootstrap_data --collection LIDC-IDRI --max-series 3
    water-bootstrap --help                         # if installed via pip
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from water.config.settings import get_settings
from water.core.logging import setup_logging
from water.dicom.orthanc_client import OrthancClient
from water.dicom.tcia_client import TCIAClient

logger = logging.getLogger(__name__)
console = Console()

# Helpers


def _wait_for_orthanc(client: OrthancClient, max_retries: int = 12, delay: float = 5.0) -> None:
    """Block until Orthanc is reachable, with exponential back-off."""
    for attempt in range(1, max_retries + 1):
        if client.is_alive():
            info = client.get_system_info()
            logger.info(
                "Orthanc is ready — version %s, DICOM AET: %s",
                info.get("Version", "?"),
                info.get("DicomAet", "?"),
            )
            return
        logger.warning("Orthanc not reachable (attempt %d/%d), retrying in %.0fs …", attempt, max_retries, delay)
        time.sleep(delay)
    logger.error("Orthanc did not become available after %d attempts.", max_retries)
    sys.exit(1)


def _push_files_to_orthanc(client: OrthancClient, dicom_files: list[Path]) -> dict[str, int]:
    """Upload a list of DICOM files to Orthanc and return upload statistics."""
    stats = {"uploaded": 0, "already_stored": 0, "failed": 0}

    for path in tqdm(dicom_files, desc="Uploading to Orthanc", unit="file"):
        try:
            result = client.upload_dicom_file(path)
            status = result.get("Status", "")
            if status == "AlreadyStored":
                stats["already_stored"] += 1
            else:
                stats["uploaded"] += 1
        except Exception:
            logger.exception("Failed to upload %s", path.name)
            stats["failed"] += 1

    return stats


def _print_summary(orthanc: OrthancClient, upload_stats: dict[str, int]) -> None:
    """Print a rich summary table after the bootstrap run."""
    server_stats = orthanc.get_statistics()

    table = Table(title="WATER Bootstrap — Summary", show_header=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green", justify="right")

    table.add_row("Files uploaded (new)", str(upload_stats["uploaded"]))
    table.add_row("Files already stored", str(upload_stats["already_stored"]))
    table.add_row("Files failed", str(upload_stats["failed"]))
    table.add_row("─" * 25, "─" * 10)
    table.add_row("Total patients in Orthanc", str(server_stats.get("CountPatients", "?")))
    table.add_row("Total studies in Orthanc", str(server_stats.get("CountStudies", "?")))
    table.add_row("Total series in Orthanc", str(server_stats.get("CountSeries", "?")))
    table.add_row("Total instances in Orthanc", str(server_stats.get("CountInstances", "?")))
    disk_bytes = int(server_stats.get("TotalDiskSize", 0))
    table.add_row("Total disk size", f"{disk_bytes / (1024**2):.1f} MB")

    console.print()
    console.print(table)


def run(
    collection: str,
    max_series: int,
    download_dir: Path,
    orthanc_url: str,
    orthanc_user: str,
    orthanc_pass: str,
) -> None:
    """Execute the full TCIA → Orthanc bootstrap pipeline.

    Args:
        collection: TCIA collection name to query.
        max_series: Maximum number of DICOM series to download.
        download_dir: Local directory for staging downloaded files.
        orthanc_url: Orthanc REST API base URL.
        orthanc_user: Orthanc basic-auth username (empty = no auth).
        orthanc_pass: Orthanc basic-auth password.
    """
    download_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Verify Orthanc connectivity
    console.print("\n[bold blue]▸ Step 1/3:[/] Connecting to Orthanc …")
    orthanc = OrthancClient(
        base_url=orthanc_url,
        username=orthanc_user,
        password=orthanc_pass,
    )
    _wait_for_orthanc(orthanc)

    # Step 2: Query TCIA and download series
    console.print(f"\n[bold blue]▸ Step 2/3:[/] Querying TCIA collection [cyan]{collection}[/] …")
    tcia = TCIAClient()

    try:
        series_list = tcia.get_series(collection)
    except Exception:
        logger.exception("Failed to query TCIA for collection '%s'", collection)
        sys.exit(1)

    if not series_list:
        logger.error("No series found for collection '%s'. Check the collection name.", collection)
        sys.exit(1)

    logger.info("Found %d series in collection '%s'. Downloading up to %d.", len(series_list), collection, max_series)

    all_dicom_files: list[Path] = []
    selected = series_list[:max_series]

    for idx, series_meta in enumerate(selected, 1):
        uid = series_meta.get("SeriesInstanceUID", "")
        if not uid:
            logger.warning("Series entry %d has no SeriesInstanceUID — skipping.", idx)
            continue

        desc = series_meta.get("SeriesDescription", "N/A")
        modality = series_meta.get("Modality", "?")
        image_count = series_meta.get("ImageCount", "?")
        console.print(
            f"  [{idx}/{len(selected)}] Series [cyan]{uid[:40]}…[/]  "
            f"Modality={modality}  Images={image_count}  Desc={desc}"
        )

        try:
            files = tcia.download_series(uid, download_dir)
            all_dicom_files.extend(files)
        except Exception:
            logger.exception("Failed to download series %s", uid)

    tcia.close()

    if not all_dicom_files:
        logger.error("No DICOM files were downloaded. Aborting upload.")
        sys.exit(1)

    logger.info("Downloaded %d DICOM file(s) total.", len(all_dicom_files))

    # Step 3: Push to Orthanc
    console.print(f"\n[bold blue]▸ Step 3/3:[/] Uploading {len(all_dicom_files)} DICOM files to Orthanc …")
    upload_stats = _push_files_to_orthanc(orthanc, all_dicom_files)

    # Summary
    _print_summary(orthanc, upload_stats)
    orthanc.close()
    console.print("\n[bold green]✓ Bootstrap complete.[/]\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments, falling back to pydantic-settings defaults."""
    settings = get_settings()

    parser = argparse.ArgumentParser(
        prog="water-bootstrap",
        description="Bootstrap a local Orthanc DICOM server with TCIA imaging data.",
    )
    parser.add_argument(
        "-c",
        "--collection",
        default=settings.tcia.collection,
        help=f"TCIA collection name (default: {settings.tcia.collection})",
    )
    parser.add_argument(
        "-n",
        "--max-series",
        type=int,
        default=settings.tcia.max_series,
        help=f"Max series to download (default: {settings.tcia.max_series})",
    )
    parser.add_argument(
        "-d",
        "--download-dir",
        type=Path,
        default=settings.tcia.download_dir,
        help=f"Download staging directory (default: {settings.tcia.download_dir})",
    )
    parser.add_argument(
        "--orthanc-url",
        default=settings.orthanc.base_url,
        help=f"Orthanc REST API URL (default: {settings.orthanc.base_url})",
    )
    parser.add_argument(
        "--orthanc-user",
        default=settings.orthanc.username,
        help="Orthanc basic-auth username",
    )
    parser.add_argument(
        "--orthanc-pass",
        default=settings.orthanc.password,
        help="Orthanc basic-auth password",
    )
    parser.add_argument(
        "--log-level",
        default=settings.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Log verbosity (default: {settings.log_level})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    args = parse_args(argv)
    setup_logging(level=args.log_level)

    console.print("[bold]WATER Framework — Bootstrap Data Loader[/]")
    console.print(f"  Collection : {args.collection}")
    console.print(f"  Max series : {args.max_series}")
    console.print(f"  Download to: {args.download_dir}")
    console.print(f"  Orthanc URL: {args.orthanc_url}")

    run(
        collection=args.collection,
        max_series=args.max_series,
        download_dir=args.download_dir,
        orthanc_url=args.orthanc_url,
        orthanc_user=args.orthanc_user,
        orthanc_pass=args.orthanc_pass,
    )


if __name__ == "__main__":
    main()

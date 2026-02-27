"""
WATER — Verify Orthanc connectivity.

Quick standalone script to check if Orthanc is running and responsive.
Usage: python scripts/verify_orthanc.py
"""

from __future__ import annotations

import sys

from rich.console import Console

from water.config.settings import get_settings
from water.dicom.orthanc_client import OrthancClient

console = Console()


def main() -> None:
    settings = get_settings()
    url = settings.orthanc.base_url
    console.print(f"Checking Orthanc at [cyan]{url}[/] …")

    client = OrthancClient(
        base_url=url,
        username=settings.orthanc.username,
        password=settings.orthanc.password,
    )

    if not client.is_alive():
        console.print("[bold red]✗ Orthanc is not reachable.[/]")
        console.print("  Start it with: [cyan]make orthanc-up[/]")
        sys.exit(1)

    info = client.get_system_info()
    stats = client.get_statistics()

    console.print(f"[bold green]✓ Orthanc is running[/]")
    console.print(f"  Version      : {info.get('Version', '?')}")
    console.print(f"  DICOM AET    : {info.get('DicomAet', '?')}")
    console.print(f"  Patients     : {stats.get('CountPatients', 0)}")
    console.print(f"  Studies      : {stats.get('CountStudies', 0)}")
    console.print(f"  Series       : {stats.get('CountSeries', 0)}")
    console.print(f"  Instances    : {stats.get('CountInstances', 0)}")

    client.close()


if __name__ == "__main__":
    main()

"""Handle Github artifacts."""
import logging
import zipfile
from pathlib import Path
from typing import Generator

import github
import requests

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)


def get_result_artifacts(
    run: github.WorkflowRun.WorkflowRun,
) -> Generator[github.Artifact.Artifact, None, None]:
    """Return results artifacts for a run."""
    result_artifacts = (
        a for a in run.get_artifacts() if a.name.startswith(consts.ARTIFACT_NAME)  # type: ignore
    )
    return result_artifacts


def download_artifact(url: str, dest_file: Path) -> Path:
    """Download artifact from Github."""
    if not url.startswith("https://"):
        raise ValueError(f"Invalid URL: {url}")

    with requests.get(
        url, headers=consts.AUTH_HEADERS, stream=True, allow_redirects=True, timeout=300
    ) as r:
        r.raise_for_status()
        with open(dest_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return dest_file


def process_artifact(dest_dir: Path, download_url: str) -> None:
    """Process artifact."""
    dest_file = dest_dir / consts.REPORTS_ARCHIVE
    zip_file = dest_dir / f"{consts.ARTIFACT_NAME}.zip"

    if not (dest_dir / consts.DOWNLOADED_SFILE).exists():
        dest_file.unlink(missing_ok=True)
        zip_file.unlink(missing_ok=True)
        LOGGER.info(f"Downloading artifact: {dest_file}")

        download_artifact(
            url=download_url,
            dest_file=zip_file,
        )

        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(dest_dir)
        zip_file.unlink()

        # if the resulting artifact name doesn't match the expected one, rename it
        if not dest_file.exists():
            for ar in dest_dir.glob(f"{consts.ARTIFACT_NAME}*.tar.xz"):
                ar.rename(dest_file)
                break

    (dest_dir / consts.DOWNLOADED_SFILE).touch()

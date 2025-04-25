"""Handle Github artifacts."""

import logging
import zipfile
from pathlib import Path
from typing import Generator
from typing import List

import github
import requests

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)


def get_run_artifacts(
    run: github.WorkflowRun.WorkflowRun,
) -> Generator[github.Artifact.Artifact, None, None]:
    """Return artifacts for a run."""
    return run.get_artifacts()  # type: ignore


def get_result_artifacts(
    run_artifacts: List[github.Artifact.Artifact],
) -> Generator[github.Artifact.Artifact, None, None]:
    """Return results artifacts for a run."""
    result_artifacts = (a for a in run_artifacts if a.name.startswith(consts.RESULTS_ARTIFACT_NAME))
    return result_artifacts


def get_coverage_artifacts(
    run_artifacts: List[github.Artifact.Artifact],
) -> Generator[github.Artifact.Artifact, None, None]:
    """Return coverage artifacts for a run."""
    result_artifacts = (a for a in run_artifacts if a.name.startswith(consts.COV_ARTIFACT_NAME))
    return result_artifacts


def download_artifact(url: str, dest_file: Path) -> Path:
    """Download artifact from Github."""
    if not url.startswith("https://"):
        err = f"Invalid URL: {url}"
        raise ValueError(err)

    with requests.get(
        url, headers=consts.AUTH_HEADERS, stream=True, allow_redirects=True, timeout=300
    ) as r:
        r.raise_for_status()
        with open(dest_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return dest_file


def _process_artifact(dest_dir: Path, zip_file: Path, download_url: str) -> None:
    zip_file.unlink(missing_ok=True)
    LOGGER.info(f"Downloading artifact: {zip_file}")

    download_artifact(
        url=download_url,
        dest_file=zip_file,
    )

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(dest_dir)
    zip_file.unlink()


def process_result_artifact(dest_dir: Path, download_url: str) -> None:
    """Process artifact."""
    dest_file = dest_dir / consts.REPORTS_ARCHIVE
    zip_file = dest_dir / f"{consts.RESULTS_ARTIFACT_NAME}.zip"

    if not (dest_dir / consts.REPORT_DOWNLOADED_SFILE).exists():
        dest_file.unlink(missing_ok=True)
        _process_artifact(dest_dir=dest_dir, zip_file=zip_file, download_url=download_url)

        # if the resulting artifact name doesn't match the expected one, rename it
        if not dest_file.exists():
            for ar in dest_dir.glob(f"{consts.RESULTS_ARTIFACT_NAME}*.tar.xz"):
                ar.rename(dest_file)
                break

    (dest_dir / consts.REPORT_DOWNLOADED_SFILE).touch()


def process_coverage_artifact(dest_dir: Path, download_url: str) -> None:
    """Process artifact."""
    dest_file = dest_dir / f"{consts.COV_ARTIFACT_NAME}.json"
    zip_file = dest_dir / f"{consts.COV_ARTIFACT_NAME}.zip"

    if not (dest_dir / consts.COV_DOWNLOADED_SFILE).exists():
        dest_file.unlink(missing_ok=True)
        _process_artifact(dest_dir=dest_dir, zip_file=zip_file, download_url=download_url)

        # if the resulting artifact name doesn't match the expected one, rename it
        if not dest_file.exists():
            for ar in dest_dir.glob("cli*coverage*.json"):
                ar.rename(dest_file)
                break

    (dest_dir / consts.COV_DOWNLOADED_SFILE).touch()

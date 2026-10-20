"""Import artifacts from local test runs."""

import filecmp
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List
from typing import Tuple

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)
SOURCE_COV_FILE_NAME = "cli_coverage.json"


def _check_artifact(source_file: Path, dest_file: Path) -> None:
    """Check an artifact before making any changes to the results tree."""
    if not source_file.is_file():
        err = f"Artifact is not a file: {source_file}"
        raise FileNotFoundError(err)

    for parent_dir in dest_file.parents:
        if parent_dir.exists() and not parent_dir.is_dir():
            err = f"Destination path is not a directory: {parent_dir}"
            raise NotADirectoryError(err)

    if dest_file.exists() and (
        not dest_file.is_file() or not filecmp.cmp(source_file, dest_file, shallow=False)
    ):
        err = (
            f"Artifact conflict: {dest_file} differs from {source_file}. "
            "Use a new run subdirectory or testrun name."
        )
        raise FileExistsError(err)


def _copy_artifact(source_file: Path, dest_file: Path) -> None:
    """Copy an artifact atomically so interrupted imports can be retried."""
    with tempfile.NamedTemporaryFile(dir=dest_file.parent, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        shutil.copy2(source_file, tmp_path)
        tmp_path.replace(dest_file)
    finally:
        tmp_path.unlink(missing_ok=True)


def import_testrun_results(base_dir: Path, source_dir: Path) -> None:
    """Copy local artifacts into the layout used by the report publisher."""
    source_dir = source_dir.resolve()
    dest_dir = base_dir.resolve() / consts.LOCAL_JOB_NAME / source_dir.name
    if source_dir.is_relative_to(dest_dir) or dest_dir.is_relative_to(source_dir):
        err = "Source and destination testrun directories must not overlap."
        raise ValueError(err)

    run_dirs = sorted(p for p in source_dir.iterdir() if p.is_dir())
    if not run_dirs:
        err = f"No run subdirectories found in {source_dir}"
        raise ValueError(err)

    # Validate every run and check for conflicts before copying any artifacts.
    artifacts: List[Tuple[Path, Path, str]] = []
    filecmp.clear_cache()
    for run_dir in run_dirs:
        run_dest_dir = dest_dir / run_dir.name
        artifacts.append(
            (
                run_dir / consts.RESULTS_ARCHIVE,
                run_dest_dir / consts.RESULTS_ARCHIVE,
                consts.REPORT_DOWNLOADED_SFILE,
            )
        )
        coverage_file = run_dir / SOURCE_COV_FILE_NAME
        if coverage_file.exists():
            artifacts.append(
                (
                    coverage_file,
                    run_dest_dir / consts.COV_FILE_NAME,
                    consts.COV_DOWNLOADED_SFILE,
                )
            )

    for source_file, dest_file, _ in artifacts:
        _check_artifact(source_file=source_file, dest_file=dest_file)

    LOGGER.info(f"Importing local testrun: {source_dir.name}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    name_file = dest_dir / "testrun_name.txt"
    if not name_file.exists():
        name_file.write_text(source_dir.name)

    for source_file, dest_file, marker_name in artifacts:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if not dest_file.exists():
            LOGGER.info(f"Copying artifact: {source_file} -> {dest_file}")
            _copy_artifact(source_file=source_file, dest_file=dest_file)
        else:
            LOGGER.info(f"Skipping identical artifact: {dest_file}")

        marker_file = dest_file.parent / marker_name
        if not marker_file.exists():
            marker_file.touch()

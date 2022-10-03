"""Publish the reports to the web."""
import json
import logging
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Generator
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Tuple

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)


class Job(NamedTuple):
    job_name: str
    revision: str
    build_id: str
    step: str


def cli(cli_args: Iterable[str]) -> Tuple[str, str]:
    """Run command."""
    assert not isinstance(cli_args, str), "`cli_args` must be sequence of strings"
    with subprocess.Popen(list(cli_args), stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
        stdout, stderr = p.communicate()
    return stdout.decode("utf-8"), stderr.decode("utf-8")


def get_job_from_results(results_path: Path, base_dir: Path) -> Job:
    """Return a `Job` record derived from results dir or archive file path.

    E.g.
    * 'nightly/506/allure-results.tar.xz' ->
        Job(job_name='nightly', revision='', build_id='506', step='')
    * 'babbage_dbsync/40458eefa87c7c3abd8c6ba542d9e931d8b2ecb8/1664632102/allure-results' ->
        Job(job_name='babbage_dbsync', revision='40458eefa87c7c3abd8c6ba542d9e931d8b2ecb8',
            build_id='1664632102', step='')
    * 'nightly-upgrade/506/step1/allure-results.tar.xz' ->
        Job(job_name='nightly', revision='', build_id='506', step="step1")
    """
    steps_path = results_path.parent
    step = steps_path.name
    if not steps_path.name.startswith(consts.STEPS_BASE):
        steps_path = results_path
        step = ""
    build_id_path = steps_path.parent
    revision_path = build_id_path.parent
    job_path = revision_path.parent

    revision = revision_path.name
    # check if there is a "revision" component in the file path
    if job_path == base_dir:
        job_path = revision_path
        revision = ""

    return Job(job_name=job_path.name, revision=revision, build_id=build_id_path.name, step=step)


def get_job_from_tree(inner_dir: Path, base_dir: Path) -> Job:
    """Return a `Job` record derived from dir tree.

    E.g.
    * 'nightly -> Job(job_name='nightly', revision='', build_id='')
    * 'babbage_dbsync/40458eefa87c7c3abd8c6ba542d9e931d8b2ecb8' ->
        Job(job_name='babbage_dbsync', revision='40458eefa87c7c3abd8c6ba542d9e931d8b2ecb8',
            build_id='', step='')
    * 'nightly-upgrade/step1' -> Job(job_name='nightly', revision='', build_id='', step="step1")
    """
    revision_path = inner_dir
    step = ""
    if inner_dir.name.startswith(consts.STEPS_BASE):
        step = inner_dir.name
        revision_path = inner_dir.parent
    job_path = revision_path.parent

    revision = revision_path.name
    # check if there is a "revision" component in the file path
    if job_path == base_dir:
        job_path = revision_path
        revision = ""

    return Job(job_name=job_path.name, revision=revision, build_id="", step=step)


def get_new_results(base_dir: Path) -> Generator[Path, None, None]:
    """Walk results directories and yield each new set of results."""
    result_artifact_file = Path(consts.REPORTS_ARCHIVE)

    for p in base_dir.rglob(consts.DONE_FILE):
        result_file = p.parent / consts.REPORTS_ARCHIVE
        if result_file.is_file():
            yield result_file

        result_dir = p.parent / result_artifact_file.stem.split(".")[0]
        if result_dir.is_dir():
            yield result_dir


def unpack_results_archive(archive_file: Path) -> Path:
    """Unpack the result archive."""
    results_dir = archive_file.parent

    with tarfile.open(archive_file, "r:xz") as tar:
        tar.extractall(path=results_dir)

    unpacked_dir = results_dir / archive_file.stem.split(".")[0]
    return unpacked_dir


def aggregate_results(results_base_dir: Path, dest_base_dir: Path) -> List[Path]:
    """Aggregate new results with existing results."""
    aggregated_dirs: List[Path] = []
    for cur_results in get_new_results(base_dir=results_base_dir):
        results_dir = cur_results
        if cur_results.name == consts.REPORTS_ARCHIVE:
            results_dir = unpack_results_archive(archive_file=cur_results)
            cur_results.unlink()

        job_rec = get_job_from_results(results_path=cur_results, base_dir=results_base_dir)
        dest_dir = dest_base_dir / job_rec.job_name
        if job_rec.revision:
            dest_dir = dest_dir / job_rec.revision
        if job_rec.step:
            dest_dir = dest_dir / job_rec.step

        shutil.copytree(results_dir, dest_dir, symlinks=True, dirs_exist_ok=True)

        aggregated_dirs.append(dest_dir)

        # delete extracted files
        shutil.rmtree(results_dir, ignore_errors=False, onerror=None)

    return aggregated_dirs


def get_aggregated_dirs(base_dir: Path) -> Generator[Path, None, None]:
    """Yield aggregated results directories."""
    for p in base_dir.rglob("environment.properties"):
        yield p.parent


def gen_badge_endpoint(report_dir: Path) -> Path:
    """Generate endpoint for shields.io badge."""
    summary_json = report_dir / "widgets" / "summary.json"
    badge_json = report_dir / "badge.json"

    with open(summary_json, "r", encoding="utf-8") as in_fp:
        summary = json.load(in_fp)

    statistic = summary["statistic"]
    passed = statistic["passed"]
    failed = statistic["failed"] + statistic["broken"]

    response = {
        "schemaVersion": 1,
        "label": "tests",
        "message": f"{passed} passed, {failed} failed",
        "color": "red" if failed else "green",
    }

    with open(badge_json, "w", encoding="utf-8") as out_fp:
        json.dump(response, out_fp, indent=4)

    return badge_json


def generate_reports(
    aggregation_base_dir: Path, aggregated_dirs: List[Path], reports_base_dir: Path
) -> List[Path]:
    """Generate reports from aggregated results."""
    report_dirs: List[Path] = []
    for a_dir in aggregated_dirs:
        job_rec = get_job_from_tree(inner_dir=a_dir, base_dir=aggregation_base_dir)
        dest_dir = reports_base_dir / job_rec.job_name
        if job_rec.revision:
            dest_dir = dest_dir / job_rec.revision
        if job_rec.step:
            dest_dir = dest_dir / job_rec.step

        shutil.rmtree(dest_dir, ignore_errors=True, onerror=None)
        dest_dir.mkdir(parents=True)

        cli_args = ["allure", "generate", str(a_dir), "-o", str(dest_dir), "--clean"]
        cli(cli_args=cli_args)

        gen_badge_endpoint(report_dir=dest_dir)

        report_dirs.append(dest_dir)

    return report_dirs


def copy_reports(reports_base_dir: Path, report_dirs: List[Path], web_base_dir: Path) -> List[Path]:
    """Copy reports to dirs served by web server."""
    web_dirs: List[Path] = []
    for report_dir in report_dirs:
        job_rec = get_job_from_tree(inner_dir=report_dir, base_dir=reports_base_dir)
        dest_dir = web_base_dir / job_rec.job_name
        if job_rec.revision:
            dest_dir = dest_dir / job_rec.revision
        if job_rec.step:
            dest_dir = dest_dir / job_rec.step

        shutil.rmtree(dest_dir, ignore_errors=True, onerror=None)
        dest_dir.mkdir(parents=True)
        shutil.copytree(report_dir, dest_dir, symlinks=True, dirs_exist_ok=True)
        web_dirs.append(dest_dir)

    return web_dirs


def publish(
    results_base_dir: Path,
    aggregation_base_dir: Path,
    web_base_dir: Path,
    reports_tmp_dir: Path,
    force_regenerate: bool = False,
) -> None:
    """Publish reports to the web."""
    # directory where results from different test runs are aggregated
    aggregation_base_dir.mkdir(parents=True, exist_ok=True)
    # temp dir where reports are generated before moving to the web dir
    reports_tmp_dir.mkdir(parents=True, exist_ok=True)

    # aggregate results
    aggregated_dirs = aggregate_results(
        results_base_dir=results_base_dir, dest_base_dir=aggregation_base_dir
    )
    if force_regenerate:
        aggregated_dirs = list(get_aggregated_dirs(base_dir=aggregation_base_dir))
    else:
        aggregated_dirs_strs = [str(p) for p in aggregated_dirs]
        LOGGER.info(f"Aggregated dirs with new results: {aggregated_dirs_strs}")

    # generate reports from aggregated results
    report_dirs = generate_reports(
        aggregation_base_dir=aggregation_base_dir,
        aggregated_dirs=aggregated_dirs,
        reports_base_dir=reports_tmp_dir,
    )

    # copy reports to dirs served by web server
    web_dirs = copy_reports(
        reports_base_dir=reports_tmp_dir,
        report_dirs=report_dirs,
        web_base_dir=web_base_dir,
    )
    web_dirs_strs = [str(p) for p in web_dirs]
    LOGGER.info(f"Generated reports: {web_dirs_strs}")

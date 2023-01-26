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
    """Run CLI command."""
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
    """Walk new results directories and yield each set of results."""
    for p in base_dir.rglob(consts.REPORT_DOWNLOADED_SFILE):
        if (p.parent / consts.REPORT_PUBLISHED_SFILE).exists():
            continue

        result_file = p.parent / consts.REPORTS_ARCHIVE
        if result_file.is_file():
            yield result_file

        result_dir = p.parent / consts.REPORTS_DIRNAME
        if result_dir.is_dir():
            yield result_dir


def unpack_results_archive(archive_file: Path) -> Path:
    """Unpack the result archive."""
    results_dir = archive_file.parent

    with tarfile.open(archive_file, "r:xz") as tar:
        tar.extractall(path=results_dir)

    unpacked_dir = results_dir / consts.REPORTS_DIRNAME
    return unpacked_dir


def get_results(new_results_base_dir: Path, out_dir: Path) -> Generator[Path, None, None]:
    """Copy/unpack/clean new results."""
    for cur_results in sorted(get_new_results(base_dir=new_results_base_dir)):
        results_dir = cur_results
        extracted_dir = None
        if cur_results.name == consts.REPORTS_ARCHIVE:
            results_dir = unpack_results_archive(archive_file=cur_results)
            extracted_dir = results_dir

        job_rec = get_job_from_results(results_path=cur_results, base_dir=new_results_base_dir)

        LOGGER.info(f"Processing {job_rec}")

        dest_dir = out_dir / job_rec.job_name
        if job_rec.revision:
            dest_dir = dest_dir / job_rec.revision
        if job_rec.step:
            dest_dir = dest_dir / job_rec.step

        shutil.rmtree(dest_dir, ignore_errors=True, onerror=None)
        dest_dir.mkdir(parents=True)
        shutil.copytree(results_dir, dest_dir, symlinks=True, dirs_exist_ok=True)

        # delete extracted files
        if extracted_dir:
            shutil.rmtree(extracted_dir, ignore_errors=True, onerror=None)

        (cur_results.parent / consts.REPORT_PUBLISHED_SFILE).touch()

        yield dest_dir


def aggregate_testrun(results_dirs: Iterable[Path], out_dir: Path) -> List[Path]:
    """Aggregate new results from the same testrun (job)."""
    mixed_results = out_dir / "mixed_results"
    shutil.rmtree(mixed_results, ignore_errors=True, onerror=None)
    mixed_results.mkdir(parents=True, exist_ok=True)

    dest_dirs = set()
    for results_dir in results_dirs:
        job_rec = get_job_from_tree(inner_dir=results_dir, base_dir=out_dir)

        LOGGER.info(f"Aggregating {job_rec}")

        dest_dir = mixed_results / job_rec.job_name
        if job_rec.revision:
            dest_dir = dest_dir / job_rec.revision
        if job_rec.step:
            dest_dir = dest_dir / job_rec.step

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(results_dir, dest_dir, symlinks=True, dirs_exist_ok=True)
        dest_dirs.add(dest_dir)

    return list(dest_dirs)


def gen_badge_endpoint(report_dir: Path) -> Path:
    """Generate endpoint for shields.io badge."""
    summary_json = report_dir / "widgets" / "summary.json"
    badge_json = report_dir / "badge.json"

    with open(summary_json, encoding="utf-8") as in_fp:
        summary = json.load(in_fp)

    statistic = summary.get("statistic") or {}
    passed = statistic.get("passed") or 0
    failed = statistic.get("failed") or 0
    broken = statistic.get("broken") or 0

    response = {
        "schemaVersion": 1,
        "label": "",
        "message": f"{passed} passed, {failed} failed, {broken} broken",
        "color": "red" if failed else "green",
    }

    with open(badge_json, "w", encoding="utf-8") as out_fp:
        json.dump(response, out_fp, indent=4)

    return badge_json


def copy_history(prev_report_dir: Path, results_dir: Path) -> None:
    """Copy history files from previous report to results dir."""
    history_dir = prev_report_dir / "history"
    if not history_dir.is_dir():
        return

    shutil.rmtree(results_dir / "history", ignore_errors=True, onerror=None)
    shutil.copytree(history_dir, results_dir / "history", symlinks=True)


def overwrite_statuses(results_dir: Path) -> None:
    """Overwrite selected test statuses.

    broken -> failed
    XFAIL skipped -> broken
    """
    for result_json in results_dir.glob("*-result.json"):
        overwrite = False

        with open(result_json, encoding="utf-8") as in_fp:
            result = json.load(in_fp)

        if result["status"] == "skipped" and "XFAIL reason" in result["statusDetails"]["message"]:
            result["status"] = "broken"
            overwrite = True
        elif result["status"] == "broken":
            result["status"] = "failed"
            overwrite = True

        if overwrite:
            with open(result_json, "w", encoding="utf-8") as out_fp:
                json.dump(result, out_fp)


def generate_report(
    results_base_dir: Path, results_dir: Path, reports_work_dir: Path, web_base_dir: Path
) -> Path:
    """Generate report from stored results."""
    job_rec = get_job_from_tree(inner_dir=results_dir, base_dir=results_base_dir)
    dest_path_parts = [job_rec.job_name]
    if job_rec.revision:
        dest_path_parts.append(job_rec.revision)
    if job_rec.step:
        dest_path_parts.append(job_rec.step)

    report_dir = Path(*reports_work_dir.parts, *dest_path_parts)
    web_dir = Path(*web_base_dir.parts, *dest_path_parts)

    # make clean temporary directory for generated report
    shutil.rmtree(report_dir, ignore_errors=True, onerror=None)
    report_dir.mkdir(parents=True)

    # copy history files from last published report
    copy_history(prev_report_dir=web_dir, results_dir=results_dir)

    # overwrite selected statuses
    overwrite_statuses(results_dir=results_dir)

    # generate Allure report
    cli_args = ["allure", "generate", str(results_dir), "-o", str(report_dir), "--clean"]
    cli(cli_args=cli_args)

    # generate badge endpoint
    gen_badge_endpoint(report_dir=report_dir)

    shutil.rmtree(web_dir, ignore_errors=True, onerror=None)
    web_dir.mkdir(parents=True)
    shutil.copytree(report_dir, web_dir, symlinks=True, dirs_exist_ok=True)

    return web_dir


def publish(
    new_results_base_dir: Path,
    web_base_dir: Path,
    results_tmp_dir: Path,
    reports_tmp_dir: Path,
    aggregate_results: bool = False,
) -> None:
    """Publish reports to the web."""
    # tmp dir where unpacked / aggregated results are stored
    results_tmp_dir.mkdir(parents=True, exist_ok=True)
    # temp dir where reports are generated before moving to the web dir
    reports_tmp_dir.mkdir(parents=True, exist_ok=True)

    results_dirs: Iterable[Path] = get_results(
        new_results_base_dir=new_results_base_dir, out_dir=results_tmp_dir
    )
    if aggregate_results:
        results_dirs = aggregate_testrun(results_dirs=results_dirs, out_dir=results_tmp_dir)

    for results_dir in results_dirs:
        web_dir = generate_report(
            results_base_dir=results_tmp_dir,
            results_dir=results_dir,
            reports_work_dir=reports_tmp_dir,
            web_base_dir=web_base_dir,
        )
        LOGGER.info(f"Generated report: {web_dir}")

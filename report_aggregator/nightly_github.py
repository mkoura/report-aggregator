"""Download nightly testing results from Github."""
import datetime
import logging
import zipfile
from pathlib import Path
from typing import Generator

import github
import requests

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)

NAME_BASE = "Nightly tests"
RUN_OFFSET = 2000  # we need higher number than Buildkite build


def get_slug(name: str) -> str:
    """Return slug that corresponds to Buildkite pipelines."""
    slug = name.replace(" ", "-").lower().replace("nightly-tests", "cardano-node-tests-nightly")
    return slug


def get_workflows(
    repo_obj: github.Repository.Repository,
) -> Generator[github.Workflow.Workflow, None, None]:
    """Return active nightly workflows."""
    workflows = (w for w in repo_obj.get_workflows() if NAME_BASE in w.name and w.state == "active")
    return workflows


def get_runs(
    workflow: github.Workflow.Workflow, started_from: datetime.datetime
) -> Generator[github.WorkflowRun.WorkflowRun, None, None]:
    """Return recent runs for a workflow."""
    for r in workflow.get_runs(branch="master", event="schedule", status="completed"):
        if r.created_at < started_from:
            return
        yield r


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


def download_nightly_results(
    base_dir: Path, repo_slug: str = consts.REPO_SLUG, timedelta_mins: int = consts.TIMEDELTA_MINS
) -> None:
    """Download results from all recent nightly jobs."""
    github_obj = github.Github(consts.GITHUB_TOKEN)
    repo_obj = github_obj.get_repo(repo_slug)
    started_from = datetime.datetime.now() - datetime.timedelta(minutes=timedelta_mins)

    for workflow in get_workflows(repo_obj=repo_obj):
        workflow_slug = get_slug(name=workflow.name)
        LOGGER.info(f"Processing workflow: {workflow.name} ({workflow_slug})")

        for cur_run in get_runs(workflow=workflow, started_from=started_from):
            run_num = cur_run.run_number + RUN_OFFSET
            LOGGER.info(f"Processing run: {cur_run.run_number} ({run_num})")

            result_artifacts = list(get_result_artifacts(run=cur_run))
            has_steps = len(result_artifacts) > 1

            if has_steps and "step" not in result_artifacts[0].name:
                LOGGER.warning("Skipping run with unexpected artifacts")
                continue

            for step, artifact in enumerate(result_artifacts, start=1):
                dest_dir = base_dir / workflow_slug / str(run_num)
                if has_steps:
                    dest_dir = dest_dir / f"{consts.STEPS_BASE}{step}"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / consts.REPORTS_ARCHIVE
                zip_file = dest_dir / f"{consts.ARTIFACT_NAME}.zip"

                if not (dest_dir / consts.DONE_FILE).exists():
                    dest_file.unlink(missing_ok=True)
                    zip_file.unlink(missing_ok=True)
                    LOGGER.info(f"Downloading artifact: {dest_file}")

                    download_artifact(
                        url=artifact.archive_download_url,
                        dest_file=zip_file,
                    )

                    with zipfile.ZipFile(zip_file, "r") as zip_ref:
                        zip_ref.extractall(dest_dir)
                    zip_file.unlink()

                with open(dest_dir / consts.DONE_FILE, "wb"):
                    pass

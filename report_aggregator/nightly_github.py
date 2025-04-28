"""Download nightly testing results from Github."""

import datetime
import logging
from pathlib import Path
from typing import Generator

import github

from report_aggregator import artifacts_github
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


def download_nightly_results(
    base_dir: Path, repo_slug: str = consts.REPO_SLUG, timedelta_mins: int = consts.TIMEDELTA_MINS
) -> None:
    """Download results from all recent nightly jobs."""
    github_obj = github.Github(consts.GITHUB_TOKEN)
    repo_obj = github_obj.get_repo(repo_slug)
    started_from = datetime.datetime.now() - datetime.timedelta(minutes=timedelta_mins)  # noqa: DTZ005

    for workflow in get_workflows(repo_obj=repo_obj):
        workflow_slug = get_slug(name=workflow.name)
        LOGGER.info(f"Processing workflow: {workflow.name} ({workflow_slug})")

        for cur_run in get_runs(workflow=workflow, started_from=started_from):
            run_num = cur_run.run_number + RUN_OFFSET
            dest_dir = base_dir / workflow_slug / str(run_num)
            LOGGER.info(f"Processing run: {cur_run.run_number} ({run_num})")

            run_artifacts = list(artifacts_github.get_run_artifacts(run=cur_run))

            result_artifacts = list(
                artifacts_github.get_result_artifacts(run_artifacts=run_artifacts)
            )
            has_steps = result_artifacts and ("step" in result_artifacts[0].name)

            if len(result_artifacts) > 1 and not has_steps:
                LOGGER.warning("Skipping run with unexpected artifacts")
                continue

            for step, result_artifact in enumerate(result_artifacts, start=1):
                a_dest_dir = dest_dir
                if has_steps:
                    a_dest_dir = dest_dir / f"{consts.STEPS_BASE}{step}"
                a_dest_dir.mkdir(parents=True, exist_ok=True)

                artifacts_github.process_result_artifact(
                    dest_dir=a_dest_dir, download_url=result_artifact.archive_download_url
                )

            coverage_artifacts = list(
                artifacts_github.get_coverage_artifacts(run_artifacts=run_artifacts)
            )
            if coverage_artifacts:
                dest_dir.mkdir(parents=True, exist_ok=True)

            for cov_artifact in coverage_artifacts:
                artifacts_github.process_coverage_artifact(
                    dest_dir=dest_dir, download_url=cov_artifact.archive_download_url
                )

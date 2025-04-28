"""Download regression testing results from Github."""

import datetime
import logging
from pathlib import Path
from typing import Generator

import github

from report_aggregator import artifacts_github
from report_aggregator import consts

LOGGER = logging.getLogger(__name__)

NAME_BASE = "Regression tests"
SEARCH_PAST_MINS = 60 * 24 * 10


def get_slug(name: str) -> str:
    slug = name.replace(" ", "-").lower()
    return slug


def get_workflows(
    repo_obj: github.Repository.Repository,
) -> Generator[github.Workflow.Workflow, None, None]:
    """Return active regression workflows."""
    workflows = (w for w in repo_obj.get_workflows() if NAME_BASE in w.name and w.state == "active")
    return workflows


def get_runs(
    workflow: github.Workflow.Workflow, testrun_name: str, started_from: datetime.datetime
) -> Generator[github.WorkflowRun.WorkflowRun, None, None]:
    """Return recent runs for a workflow."""
    for r in workflow.get_runs(event="workflow_dispatch", status="completed"):
        if r.created_at < started_from:
            return

        if f"Run: {testrun_name}" not in r.raw_data["name"]:
            continue

        if ":repeat:" not in r.raw_data["name"]:
            # this is the first full testrun, no need to look further
            yield r
            return

        yield r


def download_testrun_results(
    base_dir: Path,
    testrun_name: str,
    repo_slug: str = consts.REPO_SLUG,
    timedelta_mins: int = SEARCH_PAST_MINS,
) -> None:
    """Download results from all recent nightly jobs."""
    github_obj = github.Github(login_or_token=consts.GITHUB_TOKEN)
    repo_obj = github_obj.get_repo(repo_slug)
    started_from = datetime.datetime.now() - datetime.timedelta(minutes=timedelta_mins)  # noqa: DTZ005

    LOGGER.info(f"Searching for run '{testrun_name}' since {started_from}")
    workflow_found = False

    for workflow in get_workflows(repo_obj=repo_obj):
        workflow_slug = get_slug(name=workflow.name)
        testrun_slug = get_slug(name=testrun_name)
        base_dest_dir = base_dir / workflow_slug / testrun_slug
        if not (base_dest_dir / "testrun_name.txt").exists():
            base_dest_dir.mkdir(parents=True, exist_ok=True)
            (base_dest_dir / "testrun_name.txt").write_text(testrun_name)

        LOGGER.info(f"Processing workflow: {workflow.name} ({workflow_slug})")

        for cur_run in get_runs(
            workflow=workflow, testrun_name=testrun_name, started_from=started_from
        ):
            LOGGER.info(f"Processing run: {cur_run.run_number}")
            workflow_found = True

            run_artifacts = list(artifacts_github.get_run_artifacts(run=cur_run))
            result_artifacts = list(
                artifacts_github.get_result_artifacts(run_artifacts=run_artifacts)
            )
            has_steps = len(result_artifacts) > 1

            if has_steps and "step" not in result_artifacts[0].name:
                LOGGER.warning("Skipping run with unexpected artifacts")
                continue

            for step, artifact in enumerate(result_artifacts, start=1):
                dest_dir = base_dest_dir / str(cur_run.run_number)
                if has_steps:
                    dest_dir = dest_dir / f"{consts.STEPS_BASE}{step}"
                dest_dir.mkdir(parents=True, exist_ok=True)

                artifacts_github.process_result_artifact(
                    dest_dir=dest_dir, download_url=artifact.archive_download_url
                )

        # the workflow with matching runs was found, no need to search in other workflows
        if workflow_found:
            break

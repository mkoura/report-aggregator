"""Download testing results from Buildkite."""

import datetime
import logging
import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from pybuildkite import buildkite

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)

ORG_NAME = "input-output-hk"
BUILDKITE_TOKEN = os.environ.get("BUILDKITE_TOKEN") or ""
SLUG_BASE = "cardano-node-tests-nightly"
DISABLED_BRANCH = "disabled"


def get_pipelines(buildkite_obj: buildkite.Buildkite) -> List[Dict[str, Any]]:
    """Return active nightly pipelines."""
    pipelines_org = buildkite_obj.pipelines().list_pipelines(organization=ORG_NAME)
    pipelines = [
        p
        for p in pipelines_org
        if p["slug"].startswith(SLUG_BASE)
        and p["default_branch"] != DISABLED_BRANCH
        and not p["archived_at"]
    ]
    return pipelines


def get_builds(
    buildkite_obj: buildkite.Buildkite, pipeline_slug: str, finished_from: datetime.datetime
) -> List[Dict[str, Any]]:
    """Return recent builds for a pipeline."""
    builds: List[Dict[str, Any]] = buildkite_obj.builds().list_all_for_pipeline(
        organization=ORG_NAME,
        pipeline=pipeline_slug,
        finished_from=finished_from,
        states=[buildkite.BuildState.FINISHED],
    )
    return builds


def get_build_artifacts(
    buildkite_obj: buildkite.Buildkite, pipeline_slug: str, build_num: int
) -> List[Dict[str, Any]]:
    """Get list of results artifacts for a build."""
    artifacts = buildkite_obj.artifacts()

    build_artifacts = artifacts.list_artifacts_for_build(
        organization=ORG_NAME,
        pipeline=pipeline_slug,
        build=build_num,
    )

    result_artifacts = [
        a for a in build_artifacts if a["filename"].startswith(consts.REPORTS_ARCHIVE)
    ]

    return result_artifacts


def download_build_results(
    buildkite_obj: buildkite.Buildkite,
    pipeline_slug: str,
    build_num: int,
    artifact: Dict[str, Any],
    dest_file: Path,
) -> Path:
    """Download results for a build."""
    artifacts = buildkite_obj.artifacts()

    stream = artifacts.download_artifact(
        organization=ORG_NAME,
        pipeline=pipeline_slug,
        build=build_num,
        job=artifact["job_id"],
        artifact=artifact["id"],
        as_stream=True,
    )

    with open(dest_file, "wb") as out_fp:
        for chunk in stream:
            out_fp.write(chunk)

    return dest_file


def download_nightly_results(base_dir: Path, timedelta_mins: int = consts.TIMEDELTA_MINS) -> None:
    """Download results from all recent nightly jobs."""
    buildkite_obj = buildkite.Buildkite()
    buildkite_obj.set_access_token(access_token=BUILDKITE_TOKEN)

    check_from_time = datetime.datetime.now() - datetime.timedelta(minutes=timedelta_mins)  # noqa: DTZ005

    pipelines = get_pipelines(buildkite_obj=buildkite_obj)
    for pipeline in pipelines:
        pipeline_slug = pipeline["slug"]
        LOGGER.info(f"Processing pipeline: {pipeline_slug}")
        builds = get_builds(
            buildkite_obj=buildkite_obj, pipeline_slug=pipeline_slug, finished_from=check_from_time
        )

        for cur_build in builds:
            build_num = cur_build["number"]
            LOGGER.info(f"Processing build: {build_num}")

            result_artifacts = get_build_artifacts(
                buildkite_obj=buildkite_obj, pipeline_slug=pipeline_slug, build_num=build_num
            )
            has_steps = len(result_artifacts) > 1

            for step, artifact in enumerate(result_artifacts):
                dest_dir = base_dir / pipeline_slug / str(build_num)
                if has_steps:
                    dest_dir = dest_dir / f"{consts.STEPS_BASE}{step}"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / consts.REPORTS_ARCHIVE

                if not (dest_dir / consts.REPORT_DOWNLOADED_SFILE).exists():
                    dest_file.unlink(missing_ok=True)
                    LOGGER.info(f"Downloading artifact: {dest_file}")

                    download_build_results(
                        buildkite_obj=buildkite_obj,
                        pipeline_slug=pipeline["slug"],
                        build_num=cur_build["number"],
                        artifact=artifact,
                        dest_file=dest_file,
                    )

                with open(dest_dir / consts.REPORT_DOWNLOADED_SFILE, "wb"):
                    pass

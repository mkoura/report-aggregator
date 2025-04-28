import logging
import tempfile
from pathlib import Path

import click

from report_aggregator import consts
from report_aggregator import coverage_publisher
from report_aggregator import nightly_github
from report_aggregator import publisher
from report_aggregator import regression_github

DEFAULT_LOG_LEVEL = "WARNING"


def init_log(log_level: str = DEFAULT_LOG_LEVEL) -> None:
    """Initialize logging."""
    logging.basicConfig(
        format="%(name)s: %(levelname)s: %(message)s",
        level=getattr(logging, log_level.upper(), logging.WARNING),
    )


@click.group()
@click.option("--log-level", default=DEFAULT_LOG_LEVEL, help="Logging level.")
def cli(log_level: str = DEFAULT_LOG_LEVEL) -> None:
    init_log(log_level=log_level)


@cli.command("nightly")
@click.option(
    "-d",
    "--results-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for results.",
)
@click.option(
    "-m",
    "--timedelta-mins",
    type=int,
    default=consts.TIMEDELTA_MINS,
    show_default=True,
    help="Look for runs started from TIMEDELTA_MINS in the past until now (in minutes).",
)
def nightly_github_cli(results_dir: str, timedelta_mins: int) -> None:
    """Download nightly results from Github."""
    nightly_github.download_nightly_results(
        base_dir=Path(results_dir), timedelta_mins=timedelta_mins
    )


@cli.command("testrun")
@click.option(
    "-d",
    "--results-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for results.",
)
@click.option(
    "-n",
    "--testrun-name",
    required=True,
    help="Name of the testrun to download results for.",
)
@click.option(
    "-r",
    "--repo-slug",
    default=consts.REPO_SLUG,
    show_default=True,
    help="Repository slug to download results from.",
)
@click.option(
    "-m",
    "--timedelta-mins",
    type=int,
    default=regression_github.SEARCH_PAST_MINS,
    show_default=True,
    help="Look for runs started from TIMEDELTA_MINS in the past until now (in minutes).",
)
def regression_github_cli(
    results_dir: str, testrun_name: str, repo_slug: str, timedelta_mins: int
) -> None:
    """Download regression results for testrun from Github."""
    regression_github.download_testrun_results(
        base_dir=Path(results_dir),
        testrun_name=testrun_name,
        repo_slug=repo_slug,
        timedelta_mins=timedelta_mins,
    )


@cli.command()
@click.option(
    "-d",
    "--results-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory with results.",
)
@click.option(
    "-w",
    "--web-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for published reports.",
)
@click.option(
    "--aggregate",
    is_flag=True,
    show_default=True,
    default=False,
    help="Aggregate new results from the same testrun (job).",
)
def publish(results_dir: str, web_dir: str, aggregate: bool) -> None:
    """Publish reports."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        results_tmp_dir = Path(tmp_dir) / "results"
        reports_tmp_dir = Path(tmp_dir) / "reports"

        publisher.publish(
            new_results_base_dir=Path(results_dir),
            web_base_dir=Path(web_dir),
            results_tmp_dir=results_tmp_dir,
            reports_tmp_dir=reports_tmp_dir,
            aggregate_results=aggregate,
        )


@cli.command("publish-coverage")
@click.option(
    "-d",
    "--results-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory with results.",
)
@click.option(
    "-w",
    "--web-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for published coverage.",
)
def publish_coverage(results_dir: str, web_dir: str) -> None:
    """Publish reports."""
    coverage_publisher.publish(
        results_base_dir=Path(results_dir),
        web_dir=Path(web_dir),
    )

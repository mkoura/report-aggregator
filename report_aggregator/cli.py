import logging
import tempfile
from pathlib import Path

import click

from report_aggregator import consts
from report_aggregator import nightly_buildkite
from report_aggregator import nightly_github
from report_aggregator import publisher


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


@cli.command("nightly-buildkite")
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
    help="Look for jobs finished from TIMEDELTA_MINS in the past until now (in minutes).",
)
def nightly_buildkite_cli(results_dir: str, timedelta_mins: int) -> None:
    """Download nightly results from Buildkite."""
    nightly_buildkite.download_nightly_results(
        base_dir=Path(results_dir), timedelta_mins=timedelta_mins
    )


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
def publish(results_dir: str, web_dir: str) -> None:
    """Publish reports."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        results_tmp_dir = Path(tmp_dir) / "results"
        reports_tmp_dir = Path(tmp_dir) / "reports"

        publisher.publish(
            new_results_base_dir=Path(results_dir),
            results_base_dir=Path(results_tmp_dir),
            web_base_dir=Path(web_dir),
            reports_tmp_dir=Path(reports_tmp_dir),
        )

import logging
import tempfile
from pathlib import Path

import click

from report_aggregator import consts
from report_aggregator import nightly_results
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


@cli.command()
@click.option(
    "--base-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for results.",
)
@click.option(
    "--timedelta-mins",
    type=int,
    default=consts.TIMEDELTA_MINS,
    show_default=True,
    help="Look for jobs finished number of minutes in the past from now.",
)
def nightly(base_dir: str, timedelta_mins: int) -> None:
    """Download nightly results."""
    nightly_results.download_nightly_results(base_dir=Path(base_dir), timedelta_mins=timedelta_mins)


@cli.command()
@click.option(
    "--results-base-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory with results.",
)
@click.option(
    "--aggregation-base-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory with aggregated results.",
)
@click.option(
    "--web-base-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Base directory for published reports.",
)
def publish(results_base_dir: str, aggregation_base_dir: str, web_base_dir: str) -> None:
    """Publish reports."""
    with tempfile.TemporaryDirectory() as reports_tmp_dir:
        publisher.publish(
            results_base_dir=Path(results_base_dir),
            aggregation_base_dir=Path(aggregation_base_dir),
            web_base_dir=Path(web_base_dir),
            reports_tmp_dir=Path(reports_tmp_dir),
        )

import json
import logging
import time
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import Tuple

from report_aggregator import consts

LOGGER = logging.getLogger(__name__)

SKIPPED = (
    "--out-file",
    "--testnet-magic",
    "--mainnet",
    "--cardano-mode",
    "create-cardano",
    "help",
)


def get_latest_coverage(base_dir: Path) -> Generator[Path, None, None]:
    """Walk new results directories and yield latest coverage."""
    for nd in base_dir.rglob("*tests-nightly*"):
        for p in sorted(nd.rglob(consts.COV_DOWNLOADED_SFILE), reverse=True):
            cov_file = p.parent / consts.COV_FILE_NAME
            if cov_file.is_file():
                LOGGER.debug(f"Using coverage file {cov_file}")
                yield cov_file
                # only last coverage file per nightly workflow`
                break


def merge_coverage(dict_a: dict, dict_b: dict) -> dict:
    """Merge dict_b into dict_a."""
    if not (isinstance(dict_a, dict) and isinstance(dict_b, dict)):
        return dict_a

    mergeable = (list, set, tuple)
    addable = (int, float)
    for key, value in dict_b.items():
        if key in dict_a and isinstance(value, mergeable) and isinstance(dict_a[key], mergeable):
            new_list = set(dict_a[key]).union(value)
            dict_a[key] = sorted(new_list)
        elif key in dict_a and isinstance(value, addable) and isinstance(dict_a[key], addable):
            dict_a[key] += value
        elif (key not in dict_a) or not isinstance(value, dict):
            dict_a[key] = value
        else:
            merge_coverage(dict_a[key], value)

    return dict_a


def get_merged_coverage(coverage_files: Iterable[Path]) -> Dict[str, Any]:
    """Get coverage info by merging available data."""
    coverage_dict: Dict[str, Any] = {}
    for in_coverage in coverage_files:
        with open(in_coverage, encoding="utf-8") as infile:
            coverage = json.load(infile)

        if coverage.get("cardano-cli", {}).get("latest") is None:
            err = f"Data in '{in_coverage}' doesn't seem to be in proper coverage format."
            raise AttributeError(err)

        coverage_dict = merge_coverage(coverage_dict, coverage)

    return coverage_dict


def get_report(
    arg_name: str, coverage: dict, uncovered_only: bool = False
) -> Tuple[dict, int, int]:
    """Generate coverage report."""
    uncovered_db: dict = {}
    covered_count = 0
    uncovered_count = 0
    for key, value in coverage.items():
        if key.startswith("_coverage") or key in SKIPPED:
            continue

        if arg_name == "create-mir-certificate" and key.startswith("--"):
            # ignore legacy options that were superceded by `stake-addresses` command
            continue

        if key.startswith("_count"):
            uncovered_db[key] = value
            continue

        if isinstance(value, dict):
            ret_db, ret_covered_count, ret_uncovered_count = get_report(
                arg_name=key, coverage=value, uncovered_only=uncovered_only
            )
            covered_count += ret_covered_count
            uncovered_count += ret_uncovered_count
            if ret_db:
                uncovered_db[key] = ret_db
            continue

        count = value
        if count == 0:
            uncovered_db[key] = 0
            uncovered_count += 1
        else:
            covered_count += 1
        if count and not uncovered_only:
            uncovered_db[key] = count

    # in case all options were skipped, the command is covered if it was executed at least once
    if covered_count == 0 and coverage[f"_count_{arg_name}"] > 0:
        covered_count = 1

    uncovered_db[f"_coverage_{arg_name}"] = (
        (100 / ((covered_count + uncovered_count) / covered_count)) if covered_count else 0
    )

    return uncovered_db, covered_count, uncovered_count


def publish(
    results_base_dir: Path,
    web_dir: Path,
) -> None:
    """Publish coverage report."""
    coverage = get_merged_coverage(coverage_files=get_latest_coverage(base_dir=results_base_dir))
    report, *__ = get_report(arg_name="cardano-cli", coverage=coverage)

    # round the top-level coverage
    top_coverage = report.get("_coverage_cardano-cli")
    rounded_coverage = 0
    if top_coverage is not None:
        rounded_coverage = round(top_coverage)
        report["_coverage_cardano-cli"] = rounded_coverage

    web_dir.mkdir(parents=True, exist_ok=True)
    todays_coverage = web_dir / f"coverage_{time.strftime('%Y%m%d')}.json"

    with open(todays_coverage, "w", encoding="utf-8") as outfile:
        json.dump(report, outfile, indent=4)

    LOGGER.info("Coverage report published to '%s'", todays_coverage)

    # symlink latest coverage
    latest_coverage = web_dir / "coverage.json"
    if latest_coverage.is_symlink():
        latest_coverage.unlink()
    latest_coverage.symlink_to(todays_coverage.name)

    # publish total coverage percentage
    if rounded_coverage:
        (web_dir / "coverage.txt").write_text(str(rounded_coverage))

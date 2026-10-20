# ruff: noqa: PT009, PT027
"""Tests using the standard-library unittest runner."""

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Iterable
from typing import Tuple
from unittest.mock import patch

from click.testing import CliRunner

from report_aggregator import consts
from report_aggregator import local_results
from report_aggregator import publisher
from report_aggregator.cli import cli


class LocalResultsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.root = Path(tmp_dir.name)
        self.base_dir = self.root / "results"
        self.base_dir.mkdir()
        self.source_dir = self.root / "my-testrun"
        self.source_dir.mkdir()
        self.dest_dir = self.base_dir / "local" / self.source_dir.name

    def _make_run(self, run_id: str, coverage: bool = False) -> Path:
        run_dir = self.source_dir / run_id
        run_dir.mkdir(exist_ok=True)
        result = json.dumps({"uuid": run_id, "status": "passed"}).encode()
        entry = tarfile.TarInfo(f"allure-results/{run_id}-result.json")
        entry.size = len(result)
        with tarfile.open(run_dir / consts.RESULTS_ARCHIVE, "w:xz") as archive:
            archive.addfile(entry, io.BytesIO(result))
        if coverage:
            (run_dir / "cli_coverage.json").write_text('{"cardano-cli": {"latest": {}}}')
        return run_dir

    def _import(self) -> None:
        local_results.import_testrun_results(base_dir=self.base_dir, source_dir=self.source_dir)

    def test_import_copies_artifacts_and_normalizes_optional_coverage(self) -> None:
        self._make_run("01", coverage=True)
        self._make_run("02")
        (self.source_dir / "notes.txt").write_text("Ignored top-level file")
        source_files = {p: p.read_bytes() for p in self.source_dir.rglob("*") if p.is_file()}

        self._import()

        self.assertEqual((self.dest_dir / "testrun_name.txt").read_text(), "my-testrun")
        for run_id in ("01", "02"):
            source_archive = self.source_dir / run_id / consts.RESULTS_ARCHIVE
            dest_archive = self.dest_dir / run_id / consts.RESULTS_ARCHIVE
            self.assertEqual(source_archive.read_bytes(), dest_archive.read_bytes())
            self.assertTrue((dest_archive.parent / consts.REPORT_DOWNLOADED_SFILE).is_file())
            self.assertFalse((dest_archive.parent / consts.REPORT_PUBLISHED_SFILE).exists())
        self.assertEqual(
            (self.dest_dir / "01" / consts.COV_FILE_NAME).read_bytes(),
            (self.source_dir / "01" / "cli_coverage.json").read_bytes(),
        )
        self.assertTrue((self.dest_dir / "01" / consts.COV_DOWNLOADED_SFILE).is_file())
        self.assertFalse((self.dest_dir / "01" / "cli_coverage.json").exists())
        self.assertFalse((self.dest_dir / "02" / consts.COV_FILE_NAME).exists())
        self.assertFalse((self.dest_dir / "02" / consts.COV_DOWNLOADED_SFILE).exists())
        self.assertEqual(
            source_files,
            {p: p.read_bytes() for p in self.source_dir.rglob("*") if p.is_file()},
        )

    def test_repeat_import_preserves_artifacts_and_publication_markers(self) -> None:
        self._make_run("01", coverage=True)
        self._import()
        published_file = self.dest_dir / "01" / consts.REPORT_PUBLISHED_SFILE
        published_file.touch()
        original_files = {
            p: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.dest_dir.rglob("*")
            if p.is_file()
        }

        self._import()

        self.assertEqual(
            original_files,
            {
                p: (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.dest_dir.rglob("*")
                if p.is_file()
            },
        )
        self.assertEqual(list(publisher.get_new_results(self.base_dir)), [])

    def test_new_run_is_imported_without_republishing_old_runs(self) -> None:
        self._make_run("01")
        self._import()
        (self.dest_dir / "01" / consts.REPORT_PUBLISHED_SFILE).touch()
        self._make_run("02")

        self._import()

        self.assertEqual(
            list(publisher.get_new_results(self.base_dir)),
            [self.dest_dir / "02" / consts.RESULTS_ARCHIVE],
        )

    def test_coverage_can_be_added_after_publication(self) -> None:
        run_dir = self._make_run("01")
        self._import()
        (self.dest_dir / "01" / consts.REPORT_PUBLISHED_SFILE).touch()
        (run_dir / "cli_coverage.json").write_text("{}")

        self._import()

        self.assertEqual((self.dest_dir / "01" / consts.COV_FILE_NAME).read_text(), "{}")
        self.assertTrue((self.dest_dir / "01" / consts.COV_DOWNLOADED_SFILE).is_file())
        self.assertEqual(list(publisher.get_new_results(self.base_dir)), [])

    def test_absent_coverage_does_not_remove_previously_imported_coverage(self) -> None:
        run_dir = self._make_run("01", coverage=True)
        self._import()
        (run_dir / "cli_coverage.json").unlink()

        self._import()

        self.assertTrue((self.dest_dir / "01" / consts.COV_FILE_NAME).is_file())
        self.assertTrue((self.dest_dir / "01" / consts.COV_DOWNLOADED_SFILE).is_file())

    def test_archive_conflict_is_detected_before_copying_new_runs(self) -> None:
        run_dir = self._make_run("02")
        self._import()
        (self.dest_dir / "02" / consts.REPORT_PUBLISHED_SFILE).touch()
        original_archive = (self.dest_dir / "02" / consts.RESULTS_ARCHIVE).read_bytes()
        self._make_run("01")
        (run_dir / consts.RESULTS_ARCHIVE).write_bytes(b"Changed archive")

        with self.assertRaisesRegex(FileExistsError, "Use a new run subdirectory"):
            self._import()

        self.assertFalse((self.dest_dir / "01").exists())
        self.assertEqual(
            (self.dest_dir / "02" / consts.RESULTS_ARCHIVE).read_bytes(), original_archive
        )
        self.assertTrue((self.dest_dir / "02" / consts.REPORT_PUBLISHED_SFILE).is_file())

    def test_coverage_conflict_is_detected_before_copying_new_runs(self) -> None:
        run_dir = self._make_run("02", coverage=True)
        self._import()
        original_coverage = (self.dest_dir / "02" / consts.COV_FILE_NAME).read_bytes()
        self._make_run("01")
        (run_dir / "cli_coverage.json").write_text("{}")

        with self.assertRaisesRegex(FileExistsError, "Artifact conflict"):
            self._import()

        self.assertFalse((self.dest_dir / "01").exists())
        self.assertEqual(
            (self.dest_dir / "02" / consts.COV_FILE_NAME).read_bytes(), original_coverage
        )

    def test_invalid_destination_directory_is_detected_before_copying(self) -> None:
        self._make_run("01")
        self._make_run("02")
        self.dest_dir.mkdir(parents=True)
        (self.dest_dir / "02").write_text("Existing file")

        with self.assertRaisesRegex(NotADirectoryError, "Destination path is not a directory"):
            self._import()

        self.assertFalse((self.dest_dir / "01").exists())
        self.assertEqual((self.dest_dir / "02").read_text(), "Existing file")

    def test_missing_archive_is_detected_before_copying_any_runs(self) -> None:
        self._make_run("01")
        (self.source_dir / "02").mkdir()

        with self.assertRaisesRegex(FileNotFoundError, consts.RESULTS_ARCHIVE):
            self._import()

        self.assertFalse(self.dest_dir.exists())

    def test_coverage_must_be_a_file_when_present(self) -> None:
        run_dir = self._make_run("01")
        (run_dir / "cli_coverage.json").mkdir()

        with self.assertRaisesRegex(FileNotFoundError, "cli_coverage.json"):
            self._import()

        self.assertFalse(self.dest_dir.exists())

    def test_empty_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "No run subdirectories"):
            self._import()

        self.assertFalse(self.dest_dir.exists())

    def test_overlapping_source_and_destination_are_rejected(self) -> None:
        self._make_run("01")
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            local_results.import_testrun_results(
                base_dir=self.source_dir, source_dir=self.source_dir
            )

        self.dest_dir.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            local_results.import_testrun_results(base_dir=self.base_dir, source_dir=self.dest_dir)

    def test_interrupted_copy_leaves_no_artifact_or_completion_marker(self) -> None:
        self._make_run("01")
        with (
            patch("report_aggregator.local_results.shutil.copy2", side_effect=OSError("Full")),
            self.assertRaisesRegex(OSError, "Full"),
        ):
            self._import()

        self.assertEqual(list((self.dest_dir / "01").iterdir()), [])
        self._import()
        self.assertTrue((self.dest_dir / "01" / consts.REPORT_DOWNLOADED_SFILE).is_file())

    def test_cli_import_uses_source_directory_name(self) -> None:
        self._make_run("01")
        result = CliRunner().invoke(
            cli,
            [
                "--log-level",
                "info",
                "local",
                "-d",
                str(self.base_dir),
                "-s",
                f"{self.source_dir}/.",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue((self.dest_dir / "01" / consts.RESULTS_ARCHIVE).is_file())

    def test_cli_reports_validation_errors_without_a_traceback(self) -> None:
        (self.source_dir / "01").mkdir()
        result = CliRunner().invoke(
            cli, ["local", "-d", str(self.base_dir), "-s", str(self.source_dir)]
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: Artifact is not a file:", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_cli_requires_existing_directories(self) -> None:
        for option in ("--results-dir", "--source-dir"):
            with self.subTest(option=option):
                args = {
                    "--results-dir": str(self.base_dir),
                    "--source-dir": str(self.source_dir),
                }
                args[option] = str(self.root / "missing")
                result = CliRunner().invoke(
                    cli,
                    [
                        "local",
                        "--results-dir",
                        args["--results-dir"],
                        "--source-dir",
                        args["--source-dir"],
                    ],
                )
                self.assertEqual(result.exit_code, 2)
                self.assertIn(option, result.output)

    def test_publish_aggregates_only_new_runs_and_preserves_history(self) -> None:
        self._check_publish_new_runs()

    def test_publishing_testrun_names_starting_with_step(self) -> None:
        self.source_dir = self.source_dir.rename(self.root / "step-testrun")
        self._check_publish_new_runs()

    def _check_publish_new_runs(self) -> None:
        self._make_run("01")
        self._make_run("02")
        self._import()
        web_dir = self.root / "web"
        web_dir.mkdir()
        published_results = []
        history_present = []

        def fake_allure(cli_args: Iterable[str]) -> Tuple[str, str]:
            args = list(cli_args)
            self.assertEqual(args[:2], ["allure", "generate"])
            self.assertEqual(args[args.index("--name") + 1], self.source_dir.name)
            results_dir = Path(args[2])
            published_results.append({p.name for p in results_dir.glob("*-result.json")})
            history_present.append((results_dir / "history" / "history.json").is_file())
            report_dir = Path(args[args.index("-o") + 1])
            (report_dir / "widgets").mkdir()
            (report_dir / "widgets" / "summary.json").write_text('{"statistic": {"passed": 1}}')
            (report_dir / "history").mkdir()
            (report_dir / "history" / "history.json").write_text("{}")
            return "", ""

        def publish() -> None:
            with tempfile.TemporaryDirectory(dir=self.root) as tmp_dir:
                publisher.publish(
                    new_results_base_dir=self.base_dir,
                    web_base_dir=web_dir,
                    results_tmp_dir=Path(tmp_dir) / "results",
                    reports_tmp_dir=Path(tmp_dir) / "reports",
                    aggregate_results=True,
                )

        with patch("report_aggregator.publisher.cli", side_effect=fake_allure):
            publish()
            report_dir = web_dir / "local" / self.source_dir.name
            self.assertTrue((report_dir / "badge.json").is_file())
            untouched_file = report_dir / "untouched.txt"
            untouched_file.write_text("Existing report")

            self._import()
            publish()
            self.assertTrue(untouched_file.is_file())
            self.assertEqual(len(published_results), 1)

            self._make_run("03")
            self._import()
            publish()
            self.assertFalse(untouched_file.exists())

        self.assertEqual(
            published_results, [{"01-result.json", "02-result.json"}, {"03-result.json"}]
        )
        self.assertEqual(history_present, [False, True])
        self.assertEqual(list(publisher.get_new_results(self.base_dir)), [])

    def test_local_names_starting_with_step_are_not_treated_as_steps(self) -> None:
        self.source_dir = self.source_dir.rename(self.root / "step-testrun")
        self._make_run("step01")
        self._import()
        archive_path = self.base_dir / "local" / "step-testrun" / "step01" / consts.RESULTS_ARCHIVE

        self.assertEqual(
            publisher.get_job_from_results(archive_path, self.base_dir),
            publisher.Job(job_name="local", revision="step-testrun", build_id="step01", step=""),
        )
        out_dir = self.root / "unpacked"
        aggregated = publisher.aggregate_testrun(
            results_dirs=publisher.get_results(self.base_dir, out_dir), out_dir=out_dir
        )
        self.assertEqual(aggregated, [out_dir / "mixed_results" / "local" / "step-testrun"])

    def test_github_job_path_interpretation_is_unchanged(self) -> None:
        for relative_path, expected in (
            ("nightly/506/allure-results.tar.xz", publisher.Job("nightly", "", "506", "")),
            (
                "nightly/506/step1/allure-results.tar.xz",
                publisher.Job("nightly", "", "506", "step1"),
            ),
            (
                "regression-tests/my-testrun/506/allure-results.tar.xz",
                publisher.Job("regression-tests", "my-testrun", "506", ""),
            ),
        ):
            with self.subTest(path=relative_path):
                self.assertEqual(
                    publisher.get_job_from_results(self.base_dir / relative_path, self.base_dir),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()

"""Unit tests for shared experiment artifact and process helpers."""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.utils.experiment_artifacts import (
    FileLockError,
    exclusive_file_lock,
    project_relative,
    read_json,
    resolve_path,
    run_logged_command,
    write_csv_atomic,
    write_json_atomic,
    write_text_atomic,
)


class ExperimentArtifactTests(unittest.TestCase):
    """Exercise artifact helpers without TensorFlow, data, or network access."""

    def test_path_normalization_with_injected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "project"
            root.mkdir()
            relative_path = Path("outputs") / "metrics.json"
            expected_path = (root / relative_path).resolve()

            self.assertEqual(
                resolve_path(relative_path, root=root),
                expected_path,
            )
            self.assertEqual(
                resolve_path(expected_path, root=root),
                expected_path,
            )
            self.assertEqual(
                project_relative(expected_path, root=root),
                "outputs/metrics.json",
            )

            outside_path = (
                Path(temporary_directory) / "outside.json"
            ).resolve()
            self.assertEqual(
                project_relative(outside_path, root=root),
                outside_path.as_posix(),
            )

    def test_atomic_json_text_and_csv_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            json_path = output_directory / "nested" / "record.json"
            text_path = output_directory / "report.txt"
            csv_path = output_directory / "records.csv"
            json_payload = {
                "schema_version": 1,
                "status": "completed",
                "labels": ["D00", "D40"],
            }
            csv_rows = [
                {"condition": "all_countries", "passed": True},
                {"condition": "us_only", "passed": False},
            ]

            write_json_atomic(json_path, json_payload)
            write_text_atomic(text_path, "refactor verification\n")
            write_csv_atomic(
                csv_path,
                ["condition", "passed"],
                csv_rows,
            )

            self.assertEqual(read_json(json_path), json_payload)
            self.assertEqual(
                text_path.read_text(encoding="utf-8"),
                "refactor verification\n",
            )
            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                self.assertEqual(reader.fieldnames, ["condition", "passed"])
                self.assertEqual(
                    list(reader),
                    [
                        {"condition": "all_countries", "passed": "True"},
                        {"condition": "us_only", "passed": "False"},
                    ],
                )

            temporary_files = list(output_directory.rglob("*.tmp"))
            self.assertEqual(temporary_files, [])

    def test_logged_command_captures_success_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_directory = Path(temporary_directory)
            log_path = working_directory / "logs" / "success.log"
            command = [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('stdout marker'); "
                    "print('stderr marker', file=sys.stderr)"
                ),
            ]

            result = run_logged_command(
                command,
                log_path,
                cwd=working_directory,
                echo=False,
            )

            self.assertEqual(result.command, tuple(command))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.log_path, log_path)
            self.assertGreaterEqual(result.elapsed_seconds, 0.0)
            log_contents = log_path.read_text(encoding="utf-8")
            self.assertIn("stdout marker", log_contents)
            self.assertIn("stderr marker", log_contents)
            self.assertIn("Exit code: 0", log_contents)

    def test_logged_command_supports_checked_and_unchecked_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_directory = Path(temporary_directory)
            command = [
                sys.executable,
                "-c",
                "import sys; print('failure marker'); sys.exit(7)",
            ]
            unchecked_log = working_directory / "unchecked.log"

            result = run_logged_command(
                command,
                unchecked_log,
                cwd=working_directory,
                check=False,
                echo=False,
            )

            self.assertEqual(result.returncode, 7)
            self.assertIn(
                "Exit code: 7",
                unchecked_log.read_text(encoding="utf-8"),
            )

            checked_log = working_directory / "checked.log"
            with self.assertRaises(subprocess.CalledProcessError) as context:
                run_logged_command(
                    command,
                    checked_log,
                    cwd=working_directory,
                    check=True,
                    echo=False,
                )

            self.assertEqual(context.exception.returncode, 7)
            checked_contents = checked_log.read_text(encoding="utf-8")
            self.assertIn("failure marker", checked_contents)
            self.assertIn("Exit code: 7", checked_contents)

    def test_exclusive_lock_rejects_collision_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_path = Path(temporary_directory) / "locks" / "runner.lock"

            with exclusive_file_lock(lock_path, purpose="unit test") as acquired:
                self.assertEqual(acquired, lock_path)
                self.assertTrue(lock_path.is_file())
                lock_contents = lock_path.read_text(encoding="utf-8")
                self.assertIn("purpose=unit test", lock_contents)

                with self.assertRaises(FileLockError):
                    with exclusive_file_lock(lock_path):
                        self.fail("A colliding lock must never be acquired.")

            self.assertFalse(lock_path.exists())

            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                with exclusive_file_lock(lock_path):
                    raise RuntimeError("simulated failure")

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()

"""Integrity tests for the matched U.S. country-comparison supervisor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from scripts.two_arm_experiment import (
    build_matched_training_arms,
    class_counts,
    record_identity,
    valid_completion,
    validate_frozen_manifests,
)
from src.datasets.classification_dataset import CropRecord
from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX
from src.utils.experiment_artifacts import (
    sha256_file,
    write_json_atomic,
)


class UsDomainAblationIntegrityTests(unittest.TestCase):
    """Ensure resumability never trusts mutable or misdirected artifacts."""

    @staticmethod
    def _record(country: str, label: str, number: int) -> CropRecord:
        relative_path = Path(country) / label / f"crop_{number:03d}.jpg"
        values = {
            "split": "train",
            "country": country,
            "source_image_path": f"raw/{country}/image_{number:03d}.jpg",
            "source_object_id": f"{country}_{label}_{number:03d}",
            "crop_relative_path": relative_path.as_posix(),
            "label": label,
            "class_index": str(CLASS_TO_INDEX[label]),
            "sequence_group": f"{country}_{number // 2:04d}",
        }
        return CropRecord(
            split="train",
            country=country,
            source_image_path=Path(values["source_image_path"]),
            source_object_id=values["source_object_id"],
            crop_relative_path=relative_path,
            crop_path=Path("/tmp") / relative_path,
            label=label,
            class_index=CLASS_TO_INDEX[label],
            sequence_group=values["sequence_group"],
            manifest_values=MappingProxyType(values),
        )

    def test_matched_arms_use_exact_us_core_and_one_for_one_swaps(self) -> None:
        records: list[CropRecord] = []
        for label in CLASS_NAMES:
            records.extend(
                self._record("United_States", label, number)
                for number in range(2)
            )
            for country in ("Japan", "Czech", "Norway", "India"):
                records.extend(
                    self._record(country, label, number)
                    for number in range(4)
                )

        arm_a, arm_b, audit = build_matched_training_arms(records, seed=42)
        arm_a_again, arm_b_again, _ = build_matched_training_arms(
            list(reversed(records)),
            seed=42,
        )

        self.assertEqual(len(arm_a), len(arm_b))
        self.assertEqual(class_counts(arm_a), class_counts(arm_b))
        self.assertEqual(
            {record_identity(record) for record in arm_a},
            {record_identity(record) for record in arm_a_again},
        )
        self.assertEqual(
            {record_identity(record) for record in arm_b},
            {record_identity(record) for record in arm_b_again},
        )
        self.assertFalse(
            any(record.country in {"Norway", "India"} for record in arm_a)
        )
        self.assertEqual(
            {record.country for record in arm_b} & {"Norway", "India"},
            {"Norway", "India"},
        )
        self.assertEqual(audit["shared_us_records"], 8)
        for label in CLASS_NAMES:
            self.assertEqual(
                audit["swaps_by_class"][label],
                {
                    "other_country_crops_removed": 4,
                    "norway_india_crops_added": 4,
                },
            )

    def test_frozen_manifest_hash_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "train.csv"
            manifest_path.write_text("label\nD00\n", encoding="utf-8")
            plan = {
                "manifests": {"no_norway_india_train": manifest_path.as_posix()},
                "frozen_manifest_sha256": {
                    "no_norway_india_train": sha256_file(manifest_path),
                },
            }

            validate_frozen_manifests(plan)
            manifest_path.write_text("label\nD40\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "changed since planning"):
                validate_frozen_manifests(plan)

    def test_completion_requires_matching_condition_and_training_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            attempt_directory = Path(temporary_directory) / "attempt_01"
            attempt_directory.mkdir()
            artifact_paths = {
                name: attempt_directory / filename
                for name, filename in {
                    "training_metrics_path": "training_metrics.json",
                    "restored_checkpoint": "restored.keras",
                    "internal_tune_metrics_path": "internal_tune.json",
                    "us_holdout_metrics_path": "holdout.json",
                    "us_holdout_predictions_path": "predictions.csv",
                    "structured_analysis_path": "analysis.json",
                }.items()
            }
            for name, path in artifact_paths.items():
                if name != "training_metrics_path":
                    path.touch()

            passed_check = {"passed": True}
            write_json_atomic(
                artifact_paths["training_metrics_path"],
                {
                    "status": "completed",
                    "condition": {"name": "no_norway_india"},
                    "round_trip_check": passed_check,
                    "fresh_reloaded_internal_tune_check": passed_check,
                },
            )
            completion = {
                "status": "completed",
                "condition": "no_norway_india",
                "round_trip_check": passed_check,
                "fresh_reloaded_internal_tune_check": passed_check,
                **{
                    name: path.as_posix()
                    for name, path in artifact_paths.items()
                },
            }
            write_json_atomic(
                attempt_directory / "completion.json",
                completion,
            )

            self.assertIsNotNone(
                valid_completion(
                    attempt_directory,
                    expected_condition="no_norway_india",
                )
            )
            self.assertIsNone(
                valid_completion(
                    attempt_directory,
                    expected_condition="with_norway_india",
                )
            )

            write_json_atomic(
                artifact_paths["training_metrics_path"],
                {
                    "status": "round_trip_verified",
                    "condition": {"name": "no_norway_india"},
                    "round_trip_check": passed_check,
                    "fresh_reloaded_internal_tune_check": passed_check,
                },
            )
            self.assertIsNone(
                valid_completion(
                    attempt_directory,
                    expected_condition="no_norway_india",
                )
            )


if __name__ == "__main__":
    unittest.main()

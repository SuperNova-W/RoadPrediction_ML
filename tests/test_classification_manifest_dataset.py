"""Focused tests for the manifest-driven square-crop dataset helpers."""

from __future__ import annotations

import csv
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from src.datasets.classification_dataset import (
    filter_crop_records,
    load_crop_manifest,
    load_manifest_records,
)


class ClassificationManifestDatasetTests(unittest.TestCase):
    """Validate path resolution and metadata filtering without loading images."""

    def test_load_and_filter_records_preserves_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_directory = Path(temporary_directory)
            manifest_path = dataset_directory / "manifest.csv"
            rows = [
                {
                    "split": "train",
                    "country": "United_States",
                    "source_image_path": "raw/us.jpg",
                    "source_object_id": "us#object_00",
                    "crop_relative_path": "train/D00/us.jpg",
                    "label": "D00",
                    "class_index": "0",
                    "sequence_group": "United_States_0007",
                },
                {
                    "split": "val",
                    "country": "India",
                    "source_image_path": "raw/india.jpg",
                    "source_object_id": "india#object_00",
                    "crop_relative_path": "val/D40/india.jpg",
                    "label": "D40",
                    "class_index": "3",
                    "sequence_group": "India_0001",
                },
            ]
            with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            records = load_manifest_records(manifest_path)
            self.assertEqual([record.label for record in records], ["D00", "D40"])
            self.assertIsInstance(records[0], Mapping)
            self.assertEqual(
                records[0].crop_path,
                (dataset_directory / "train/D00/us.jpg").resolve(),
            )

            filtered = filter_crop_records(
                records,
                split="train",
                include_countries="United_States",
                exclude_sequence_groups="United_States_9999",
            )
            self.assertEqual(filtered, [records[0]])

    def test_frozen_manifest_uses_explicit_crop_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            crop_root = root / "published_crops"
            frozen_directory = root / "experiment" / "manifests"
            crop_path = crop_root / "train" / "D00" / "example.jpg"
            crop_path.parent.mkdir(parents=True)
            crop_path.touch()
            frozen_directory.mkdir(parents=True)
            manifest_path = frozen_directory / "train_subset.csv"
            row = {
                "split": "train",
                "country": "United_States",
                "source_image_path": "raw/us.jpg",
                "source_object_id": "us#object_00",
                "crop_relative_path": "train/D00/example.jpg",
                "crop_path": "data/processed/example.jpg",
                "label": "D00",
                "class_index": "0",
                "sequence_group": "United_States_0007",
            }
            with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)

            manifest = load_crop_manifest(
                manifest_path,
                crop_root=crop_root,
                require_existing_files=True,
            )
            record = manifest.records[0]

            self.assertEqual(record.crop_path, crop_path.resolve())
            self.assertEqual(record["crop_path"], row["crop_path"])
            self.assertEqual(record.to_manifest_row(), row)

    def test_manifest_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.csv"
            row = {
                "split": "train",
                "country": "United_States",
                "source_image_path": "raw/us.jpg",
                "source_object_id": "us#object_00",
                "crop_relative_path": "../outside.jpg",
                "label": "D00",
                "class_index": "0",
                "sequence_group": "United_States_0007",
            }
            with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)

            with self.assertRaisesRegex(ValueError, "must stay inside"):
                load_manifest_records(manifest_path)


if __name__ == "__main__":
    unittest.main()

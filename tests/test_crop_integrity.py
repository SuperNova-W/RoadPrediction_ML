"""Tests for shared crop-file integrity validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.datasets.crop_integrity import (
    validate_crop_file_integrity,
    validate_declared_crop_paths,
)


class CropIntegrityTests(unittest.TestCase):
    def test_valid_rgb_square_inventory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_directory = Path(temporary_directory)
            crop_path = dataset_directory / "train" / "D00" / "crop.jpg"
            crop_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), color="white").save(crop_path)
            records = [
                {
                    "crop_relative_path": "train/D00/crop.jpg",
                    "source_object_id": "image.xml#object_00",
                    "crop_side": 8,
                }
            ]

            result = validate_crop_file_integrity(
                dataset_directory,
                records,
                expected_side_field="crop_side",
            )

            self.assertEqual(result.record_count, 1)
            self.assertEqual(result.image_count, 1)

    def test_unexpected_image_fails_inventory_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_directory = Path(temporary_directory)
            crop_path = dataset_directory / "train" / "D00" / "crop.jpg"
            extra_path = dataset_directory / "train" / "D00" / "extra.jpg"
            crop_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8)).save(crop_path)
            Image.new("RGB", (8, 8)).save(extra_path)
            records = [
                {
                    "crop_relative_path": "train/D00/crop.jpg",
                    "source_object_id": "image.xml#object_00",
                }
            ]

            with self.assertRaisesRegex(RuntimeError, "extra=1"):
                validate_crop_file_integrity(dataset_directory, records)

    def test_declared_crop_path_must_match_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_directory = Path(temporary_directory)
            expected_path = dataset_directory / "val" / "D40" / "crop.jpg"
            record = {
                "crop_relative_path": "val/D40/crop.jpg",
                "crop_path": expected_path.as_posix(),
            }

            validate_declared_crop_paths(dataset_directory, [record])
            record["crop_path"] = (dataset_directory / "wrong.jpg").as_posix()

            with self.assertRaisesRegex(RuntimeError, "inconsistent crop paths"):
                validate_declared_crop_paths(dataset_directory, [record])


if __name__ == "__main__":
    unittest.main()

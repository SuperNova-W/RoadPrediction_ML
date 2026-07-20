"""Regression tests for the shared manifest-driven evaluator."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import tensorflow as tf

from scripts.analyze_validation_metrics import (
    load_crop_metadata,
    load_predictions,
)
from src.datasets.classification_dataset import load_crop_manifest
from src.evaluation.evaluate_classifier import evaluate_classifier_records


class _DivergentCompiledModel:
    """Return perfect eager predictions but deliberately different Keras metrics."""

    def evaluate(self, dataset, verbose: int, return_dict: bool):
        del dataset, verbose, return_dict
        return {"loss": 2.0, "accuracy": 0.0}

    def __call__(self, images, training: bool = False):
        del images, training
        return tf.constant(
            [
                [8.0, 0.0, 0.0, 0.0],
                [0.0, 8.0, 0.0, 0.0],
            ],
            dtype=tf.float32,
        )


class ClassifierEvaluationTests(unittest.TestCase):
    def test_compiled_and_eager_metrics_remain_separate(self) -> None:
        labels = tf.constant([0, 1], dtype=tf.int32)
        images = tf.zeros((2, 4, 4, 3), dtype=tf.float32)
        dataset = tf.data.Dataset.from_tensors((images, labels))
        records = [
            {"crop_path": "dataset/train/D00/a.jpg", "class_index": 0},
            {"crop_path": "dataset/train/D10/b.jpg", "class_index": 1},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "evaluation"
            metrics = evaluate_classifier_records(
                model=_DivergentCompiledModel(),
                dataset=dataset,
                records=records,
                output_directory=output_directory,
                split="val",
                batch_size=2,
                role="contract_test",
                checkpoint_path="outputs/checkpoints/fake.keras",
                compiled_dataset=dataset,
                metric_aliases={"test_loss": "loss"},
            )

            self.assertEqual(metrics["accuracy"], 1.0)
            self.assertEqual(metrics["keras_evaluation"]["accuracy"], 0.0)
            self.assertEqual(
                metrics["keras_vs_prediction_accuracy_absolute_difference"],
                1.0,
            )
            self.assertEqual(metrics["test_loss"], metrics["loss"])
            self.assertTrue((output_directory / "metrics.json").is_file())
            self.assertTrue((output_directory / "confusion_matrix.png").is_file())

            with (output_directory / "predictions.csv").open(
                newline="",
                encoding="utf-8",
            ) as prediction_file:
                prediction_rows = list(csv.DictReader(prediction_file))

            self.assertEqual(
                [row["crop_path"] for row in prediction_rows],
                [record["crop_path"] for record in records],
            )

    def test_crop_records_round_trip_into_structured_analysis(self) -> None:
        labels = tf.constant([0, 1], dtype=tf.int32)
        images = tf.zeros((2, 4, 4, 3), dtype=tf.float32)
        dataset = tf.data.Dataset.from_tensors((images, labels))

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "manifest.csv"
            common = {
                "split": "val",
                "country": "United_States",
                "source_image_path": "data/raw/source.jpg",
                "annotation_path": "data/raw/source.xml",
                "sequence_group": "United_States_0001",
                "xmin": "10",
                "ymin": "20",
                "xmax": "30",
                "ymax": "40",
                "crop_left": "0",
                "crop_top": "0",
                "crop_right": "64",
                "crop_bottom": "64",
            }
            rows = [
                {
                    **common,
                    "source_object_id": "source#object_00",
                    "crop_relative_path": "val/D00/a.jpg",
                    "crop_path": "published/val/D00/a.jpg",
                    "label": "D00",
                    "class_index": "0",
                },
                {
                    **common,
                    "source_object_id": "source#object_01",
                    "crop_relative_path": "val/D10/b.jpg",
                    "crop_path": "published/val/D10/b.jpg",
                    "label": "D10",
                    "class_index": "1",
                },
            ]
            with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            records = list(load_crop_manifest(manifest_path).records)
            output_directory = root / "evaluation"
            metrics = evaluate_classifier_records(
                model=_DivergentCompiledModel(),
                dataset=dataset,
                records=records,
                output_directory=output_directory,
                split="val",
            )

            metadata = load_crop_metadata(manifest_path)
            enriched = load_predictions(
                Path(str(metrics["predictions_path"])),
                metadata,
            )

            self.assertEqual(len(enriched), 2)
            self.assertEqual(
                [row["crop_path"] for row in enriched],
                [row["crop_path"] for row in rows],
            )


if __name__ == "__main__":
    unittest.main()

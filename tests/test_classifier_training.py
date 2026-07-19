"""Unit tests for shared classifier-training mechanics."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import tensorflow as tf
from tensorflow import keras

from src.evaluation.classifier_runtime import evaluate_eager_dataset
from src.training.classifier_training import (
    balanced_class_weights,
    certify_saved_classifier,
    compare_metric_sets,
    compile_classifier,
    fit_and_certify_classifier,
    history_best_validation_metrics,
)


class ClassifierTrainingTests(unittest.TestCase):
    def test_balanced_class_weights_use_fixed_counts(self) -> None:
        weights = balanced_class_weights({"D00": 6, "D10": 3, "D20": 2})

        self.assertEqual(weights["D00"], 11 / 18)
        self.assertEqual(weights["D10"], 11 / 9)
        self.assertEqual(weights["D20"], 11 / 6)

    def test_balanced_class_weights_reject_empty_classes(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            balanced_class_weights({"D00": 1, "D40": 0})

    def test_metric_comparison_includes_tolerance_boundary(self) -> None:
        comparison = compare_metric_sets(
            {"loss": 0.5, "accuracy": 0.75},
            {"loss": 0.625, "accuracy": 0.875},
            tolerance=0.125,
        )

        self.assertTrue(comparison["passed"])

    def test_metric_comparison_fails_if_either_metric_exceeds_tolerance(self) -> None:
        comparison = compare_metric_sets(
            {"loss": 0.5, "accuracy": 0.75},
            {"loss": 0.5, "accuracy": 0.751},
            tolerance=0.0001,
        )

        self.assertFalse(comparison["passed"])

    def test_history_best_metrics_come_from_lowest_loss_epoch(self) -> None:
        metrics = history_best_validation_metrics(
            {
                "val_loss": [0.9, 0.7, 0.8],
                "val_accuracy": [0.5, 0.65, 0.7],
            }
        )

        self.assertEqual(
            metrics,
            {
                "epoch": 2,
                "monitor": "val_loss",
                "value": 0.7,
                "loss": 0.7,
                "accuracy": 0.65,
            },
        )

    def test_history_best_metrics_support_a_maximized_monitor(self) -> None:
        metrics = history_best_validation_metrics(
            {
                "val_loss": [0.9, 0.7, 0.8],
                "val_accuracy": [0.5, 0.65, 0.7],
                "val_macro_f1": [0.40, 0.55, 0.60],
            },
            monitor="val_macro_f1",
            mode="max",
        )

        self.assertEqual(metrics["epoch"], 3)
        self.assertEqual(metrics["monitor"], "val_macro_f1")
        self.assertEqual(metrics["value"], 0.60)
        # loss/accuracy still report val_loss/val_accuracy at the chosen epoch.
        self.assertEqual(metrics["accuracy"], 0.70)

    def test_focal_loss_reduces_to_cross_entropy_at_gamma_zero(self) -> None:
        from src.training.focal_loss import SparseCategoricalFocalLoss

        logits = tf.constant(
            [[2.0, 0.5, -1.0, 0.0], [0.1, 0.2, 3.0, -2.0]], dtype=tf.float32
        )
        labels = tf.constant([0, 2], dtype=tf.int32)

        cross_entropy = float(
            keras.losses.SparseCategoricalCrossentropy(from_logits=True)(
                labels, logits
            )
        )
        focal = float(SparseCategoricalFocalLoss(gamma=0.0)(labels, logits))

        self.assertAlmostEqual(cross_entropy, focal, places=5)

    def test_focal_loss_downweights_confident_correct_examples(self) -> None:
        from src.training.focal_loss import SparseCategoricalFocalLoss

        logits = tf.constant([[10.0, 0.0, 0.0, 0.0]], dtype=tf.float32)
        labels = tf.constant([0], dtype=tf.int32)

        cross_entropy = float(
            keras.losses.SparseCategoricalCrossentropy(from_logits=True)(
                labels, logits
            )
        )
        focal = float(SparseCategoricalFocalLoss(gamma=2.0)(labels, logits))

        self.assertLess(focal, cross_entropy)

    def test_certification_compares_in_memory_against_fresh_evaluator(
        self,
    ) -> None:
        model = keras.Sequential(
            [
                keras.layers.Input(shape=(2,)),
                keras.layers.Dense(4),
            ]
        )
        compile_classifier(model, learning_rate=0.001)
        dataset_builds = 0

        def dataset_factory() -> tf.data.Dataset:
            nonlocal dataset_builds
            dataset_builds += 1
            return tf.data.Dataset.from_tensor_slices(
                (
                    tf.constant([[0.0, 1.0], [1.0, 0.0]]),
                    tf.constant([0, 1], dtype=tf.int32),
                )
            ).batch(2)

        fresh_checkpoints: list[Path] = []

        def fresh_evaluator(checkpoint_path: Path) -> dict[str, float]:
            # Stand in for a subprocess: reload from disk and evaluate eagerly
            # on an independently built dataset, exactly as the real certifier.
            fresh_checkpoints.append(checkpoint_path)
            reloaded = keras.models.load_model(checkpoint_path, compile=False)
            return evaluate_eager_dataset(reloaded, dataset_factory())

        with tempfile.TemporaryDirectory() as temporary_directory:
            restored_checkpoint_path = (
                Path(temporary_directory) / "restored.keras"
            )
            reloaded_model, evidence = certify_saved_classifier(
                model,
                restored_checkpoint_path=restored_checkpoint_path,
                validation_dataset_factory=dataset_factory,
                tolerance=1e-6,
                fresh_evaluator=fresh_evaluator,
            )

        # One in-memory build plus one build inside the fresh evaluator.
        self.assertEqual(dataset_builds, 2)
        self.assertEqual(fresh_checkpoints, [restored_checkpoint_path])
        self.assertTrue(evidence["comparison"]["passed"])
        self.assertIsInstance(reloaded_model, keras.Model)

    def test_fit_certifies_weights_restored_from_nonfinal_best_epoch(self) -> None:
        """Exercise the exact EarlyStopping restoration state transition."""

        train_dataset = tf.data.Dataset.from_tensor_slices(
            (
                tf.ones((32, 1), dtype=tf.float32),
                tf.ones((32,), dtype=tf.int32),
            )
        ).batch(8)
        validation_builds = 0

        def validation_dataset_factory() -> tf.data.Dataset:
            nonlocal validation_builds
            validation_builds += 1
            # Training rewards class 1 while validation rewards class 0, so
            # validation loss worsens and the first epoch must be restored.
            return tf.data.Dataset.from_tensor_slices(
                (
                    tf.ones((8, 1), dtype=tf.float32),
                    tf.zeros((8,), dtype=tf.int32),
                )
            ).batch(8)

        def model_factory() -> keras.Model:
            return keras.Sequential(
                [
                    keras.layers.Input(shape=(1,)),
                    keras.layers.Dense(
                        2,
                        kernel_initializer="zeros",
                        bias_initializer="zeros",
                    ),
                ]
            )

        def fresh_evaluator(checkpoint_path: Path) -> dict[str, float]:
            # Certify against an independently built copy of the validation set,
            # so its build is not counted against the eager-validation callback.
            reloaded = keras.models.load_model(checkpoint_path, compile=False)
            fresh_dataset = tf.data.Dataset.from_tensor_slices(
                (
                    tf.ones((8, 1), dtype=tf.float32),
                    tf.zeros((8,), dtype=tf.int32),
                )
            ).batch(8)
            return evaluate_eager_dataset(reloaded, fresh_dataset)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            result = fit_and_certify_classifier(
                model_factory=model_factory,
                train_dataset=train_dataset,
                validation_dataset_factory=validation_dataset_factory,
                epochs=6,
                class_weights={0: 1.0, 1: 1.0},
                learning_rate=0.1,
                seed=42,
                best_checkpoint_path=output_directory / "best.keras",
                restored_checkpoint_path=output_directory / "restored.keras",
                csv_log_path=output_directory / "history.csv",
                tensorboard_path=output_directory / "tensorboard",
                tolerance=1e-6,
                fresh_evaluator=fresh_evaluator,
                early_stopping_patience=1,
                reduce_lr_patience=5,
                verbose=0,
            )

        completed_epochs = len(result.history_values["loss"])
        best_epoch = int(result.history_best_validation["epoch"])
        self.assertGreater(completed_epochs, 1)
        self.assertLess(best_epoch, completed_epochs)
        # The eager-validation callback builds the set once per epoch, and
        # certification builds it once more for the in-memory measurement.
        self.assertEqual(validation_builds, completed_epochs + 1)
        self.assertTrue(result.round_trip_check["passed"])
        self.assertAlmostEqual(
            result.in_memory_metrics["loss"],
            float(result.history_best_validation["loss"]),
            places=5,
        )


if __name__ == "__main__":
    unittest.main()

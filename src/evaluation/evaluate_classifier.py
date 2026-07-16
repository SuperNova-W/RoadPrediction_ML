"""Evaluate a trained damage classifier on the untouched test split."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import matplotlib
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from tensorflow import keras

from src.datasets.classification_dataset import load_split
from src.utils.classes import CLASS_DESCRIPTIONS, CLASS_TO_INDEX


matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


FIGURE_DIRECTORY = Path("outputs/figures")
METRICS_DIRECTORY = Path("outputs/metrics")
TEST_CROP_DIRECTORY = Path("data/processed/classification/test")

CLASS_NAMES = list(CLASS_TO_INDEX.keys())
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_arguments() -> argparse.Namespace:
    """Read evaluation options from the command line."""

    parser = argparse.ArgumentParser(
        description="Evaluate a classification checkpoint."
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to a saved .keras checkpoint.",
    )
    parser.add_argument("--batch-size", type=int, default=32)

    args = parser.parse_args()

    if not args.checkpoint.is_file():
        parser.error(f"Checkpoint does not exist: {args.checkpoint}")
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")

    return args


def ordered_test_crop_paths() -> list[Path]:
    """Match the deterministic ordering used by the test dataset."""

    crop_paths: list[Path] = []

    for label in CLASS_NAMES:
        class_directory = TEST_CROP_DIRECTORY / label

        if not class_directory.is_dir():
            raise FileNotFoundError(
                f"Test class directory not found: {class_directory}"
            )

        class_paths = sorted(
            path
            for path in class_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        crop_paths.extend(class_paths)

    return crop_paths


def collect_predictions(
    model: keras.Model,
    test_dataset: tf.data.Dataset,
    crop_paths: list[Path],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Run inference once and retain labels, probabilities, and loss."""

    true_batches: list[np.ndarray] = []
    probability_batches: list[np.ndarray] = []

    loss_function = keras.losses.SparseCategoricalCrossentropy(
        from_logits=True,
        reduction="none",
    )

    total_loss = 0.0
    total_examples = 0

    for batch_number, (images, labels) in enumerate(
        test_dataset,
        start=1,
    ):
        # training=False disables augmentation and dropout.
        logits = model(images, training=False)
        probabilities = tf.nn.softmax(logits, axis=1)
        batch_losses = loss_function(labels, logits)

        true_batches.append(labels.numpy())
        probability_batches.append(probabilities.numpy())

        total_loss += float(tf.reduce_sum(batch_losses).numpy())
        total_examples += int(labels.shape[0])

        if batch_number % 50 == 0:
            print(f"Evaluated {total_examples:,} test crops...")

    true_labels = np.concatenate(true_batches)
    probabilities = np.concatenate(probability_batches)
    predicted_labels = np.argmax(probabilities, axis=1)

    if len(crop_paths) != len(true_labels):
        raise RuntimeError(
            f"Found {len(crop_paths):,} paths but evaluated "
            f"{len(true_labels):,} labels."
        )

    expected_labels = np.array(
        [CLASS_TO_INDEX[path.parent.name] for path in crop_paths]
    )

    if not np.array_equal(expected_labels, true_labels):
        raise RuntimeError(
            "Test file ordering does not match TensorFlow label ordering."
        )

    average_loss = total_loss / total_examples

    return true_labels, predicted_labels, probabilities, average_loss


def save_confusion_matrices(
    matrix: np.ndarray,
    output_path: Path,
) -> None:
    """Save count and row-normalized confusion matrices."""

    row_totals = matrix.sum(axis=1, keepdims=True)
    normalized_matrix = np.divide(
        matrix,
        row_totals,
        out=np.zeros_like(matrix, dtype=float),
        where=row_totals != 0,
    )

    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=CLASS_NAMES,
    ).plot(
        ax=axes[0],
        cmap="Blues",
        colorbar=False,
        values_format="d",
    )
    axes[0].set_title("Test confusion matrix — counts")

    ConfusionMatrixDisplay(
        confusion_matrix=normalized_matrix,
        display_labels=CLASS_NAMES,
    ).plot(
        ax=axes[1],
        cmap="Blues",
        colorbar=False,
        values_format=".2f",
    )
    axes[1].set_title("Test confusion matrix — row normalized")

    figure.suptitle("Custom CNN road-damage classification")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def save_prediction_csv(
    crop_paths: list[Path],
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
    probabilities: np.ndarray,
    output_path: Path,
) -> None:
    """Save individual predictions for later error analysis."""

    fieldnames = [
        "crop_path",
        "true_label",
        "predicted_label",
        "correct",
        "confidence",
        *[f"probability_{label}" for label in CLASS_NAMES],
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for index, crop_path in enumerate(crop_paths):
            true_index = int(true_labels[index])
            predicted_index = int(predicted_labels[index])

            row: dict[str, object] = {
                "crop_path": crop_path.as_posix(),
                "true_label": CLASS_NAMES[true_index],
                "predicted_label": CLASS_NAMES[predicted_index],
                "correct": int(true_index == predicted_index),
                "confidence": float(probabilities[index, predicted_index]),
            }

            for class_index, label in enumerate(CLASS_NAMES):
                row[f"probability_{label}"] = float(
                    probabilities[index, class_index]
                )

            writer.writerow(row)


def main() -> None:
    """Evaluate one checkpoint and save all test artifacts."""

    args = parse_arguments()
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    METRICS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    run_name = args.checkpoint.stem.removesuffix("_best")
    figure_path = FIGURE_DIRECTORY / f"{run_name}_test_confusion_matrix.png"
    metrics_path = METRICS_DIRECTORY / f"{run_name}_test_metrics.json"
    predictions_path = METRICS_DIRECTORY / f"{run_name}_test_predictions.csv"

    print(f"Checkpoint: {args.checkpoint}")
    print(f"TensorFlow: {tf.__version__}")
    print(f"Physical GPUs: {tf.config.list_physical_devices('GPU')}")

    model = keras.models.load_model(args.checkpoint, compile=False)
    test_dataset = load_split(
        split="test",
        batch_size=args.batch_size,
        shuffle=False,
    )
    crop_paths = ordered_test_crop_paths()

    start_time = time.perf_counter()

    true_labels, predicted_labels, probabilities, test_loss = (
        collect_predictions(model, test_dataset, crop_paths)
    )

    evaluation_seconds = time.perf_counter() - start_time

    accuracy = float(accuracy_score(true_labels, predicted_labels))
    macro_f1 = float(
        f1_score(true_labels, predicted_labels, average="macro")
    )
    weighted_f1 = float(
        f1_score(true_labels, predicted_labels, average="weighted")
    )

    report = classification_report(
        true_labels,
        predicted_labels,
        labels=list(range(len(CLASS_NAMES))),
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    report_text = classification_report(
        true_labels,
        predicted_labels,
        labels=list(range(len(CLASS_NAMES))),
        target_names=CLASS_NAMES,
        zero_division=0,
        digits=4,
    )

    matrix = confusion_matrix(
        true_labels,
        predicted_labels,
        labels=list(range(len(CLASS_NAMES))),
    )

    results = {
        "checkpoint": args.checkpoint.as_posix(),
        "split": "test",
        "number_of_examples": int(len(true_labels)),
        "batch_size": args.batch_size,
        "test_loss": test_loss,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "evaluation_seconds": evaluation_seconds,
        "images_per_second": len(true_labels) / evaluation_seconds,
        "class_mapping": CLASS_TO_INDEX,
        "class_descriptions": CLASS_DESCRIPTIONS,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "tensorflow_version": tf.__version__,
        "gpu_devices": [
            device.name
            for device in tf.config.list_physical_devices("GPU")
        ],
    }

    with metrics_path.open("w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2)

    save_confusion_matrices(matrix, figure_path)
    save_prediction_csv(
        crop_paths=crop_paths,
        true_labels=true_labels,
        predicted_labels=predicted_labels,
        probabilities=probabilities,
        output_path=predictions_path,
    )

    print("\nTest results")
    print("------------")
    print(f"Examples: {len(true_labels):,}")
    print(f"Loss: {test_loss:.4f}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"Weighted F1: {weighted_f1:.4f}")
    print(f"Evaluation time: {evaluation_seconds:.2f} seconds")
    print(f"Throughput: {len(true_labels) / evaluation_seconds:.2f} images/s")
    print(f"\n{report_text}")
    print(f"Metrics: {metrics_path}")
    print(f"Predictions: {predictions_path}")
    print(f"Confusion matrix: {figure_path}")


if __name__ == "__main__":
    main()

"""Evaluate saved road-damage classifiers and write reusable artifacts.

The command-line entry point evaluates the legacy directory-based dataset.  The
programmatic APIs below also support an explicitly ordered manifest record list,
which is required when an experiment intentionally filters countries or creates
a new holdout without changing the underlying crop directories.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    ConfusionMatrixDisplay,
)
from tensorflow import keras

from src.datasets.classification_dataset import load_split
from src.evaluation.classifier_metrics import (
    compute_classification_metrics,
    normalized_metric_mapping,
    save_confusion_matrix_csv,
)
from src.evaluation.classifier_runtime import evaluate_compiled_dataset
from src.utils.classes import (
    CLASS_DESCRIPTIONS,
    CLASS_NAMES,
    CLASS_TO_INDEX,
)
from src.utils.experiment_artifacts import (
    project_relative,
    write_csv_atomic,
    write_json_atomic,
)


matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


FIGURE_DIRECTORY = Path("outputs/figures")
METRICS_DIRECTORY = Path("outputs/metrics")
CLASSIFICATION_DIRECTORY = Path("data/processed/classification")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
Record = Mapping[str, object]


@dataclass(frozen=True)
class EvaluationArtifactPaths:
    """Explicit destinations for one complete classifier evaluation."""

    predictions: Path
    confusion_csv: Path
    confusion_figure: Path
    metrics: Path


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
    parser.add_argument(
        "--split",
        choices=("val", "test"),
        default="val",
        help="Dataset split to evaluate. Defaults to validation.",
    )
    parser.add_argument("--batch-size", type=int, default=32)

    args = parser.parse_args()

    if not args.checkpoint.is_file():
        parser.error(f"Checkpoint does not exist: {args.checkpoint}")
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")

    return args


def ordered_crop_paths(split: str) -> list[Path]:
    """Match the deterministic ordering used by a legacy directory split."""

    crop_paths: list[Path] = []

    for label in CLASS_NAMES:
        class_directory = CLASSIFICATION_DIRECTORY / split / label

        if not class_directory.is_dir():
            raise FileNotFoundError(
                f"Class directory not found: {class_directory}"
            )

        class_paths = sorted(
            path
            for path in class_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        crop_paths.extend(class_paths)

    return crop_paths


def _collect_prediction_arrays(
    model: keras.Model,
    dataset: tf.data.Dataset,
    *,
    progress_interval: int = 50,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Run one eager inference pass and return labels, probabilities, and loss.

    This deliberately uses the same eager forward pass for every external
    metric.  On Metal, that avoids mixing a compiled ``model.evaluate`` metric
    with predictions that can differ at a rare decision boundary.
    """

    true_batches: list[np.ndarray] = []
    probability_batches: list[np.ndarray] = []
    loss_function = keras.losses.SparseCategoricalCrossentropy(
        from_logits=True,
        reduction="none",
    )
    total_loss = 0.0
    total_examples = 0

    for batch_number, (images, labels) in enumerate(dataset, start=1):
        # training=False disables the model's augmentation and dropout layers.
        logits = model(images, training=False)
        probabilities = tf.nn.softmax(logits, axis=1)
        batch_losses = loss_function(labels, logits)

        true_batches.append(np.asarray(labels.numpy()).reshape(-1))
        probability_batches.append(np.asarray(probabilities.numpy()))
        total_loss += float(tf.reduce_sum(batch_losses).numpy())
        total_examples += int(tf.shape(labels)[0].numpy())

        if progress_interval and batch_number % progress_interval == 0:
            print(f"Evaluated {total_examples:,} crops...")

    if total_examples == 0:
        raise ValueError("Cannot evaluate an empty dataset.")

    true_labels = np.concatenate(true_batches)
    probabilities = np.concatenate(probability_batches)

    if probabilities.ndim != 2 or probabilities.shape[1] != len(CLASS_NAMES):
        raise RuntimeError(
            "Classifier output shape does not match the configured classes: "
            f"expected (*, {len(CLASS_NAMES)}), received {probabilities.shape}."
        )

    predicted_labels = np.argmax(probabilities, axis=1)
    return true_labels, predicted_labels, probabilities, total_loss / total_examples


def _validate_expected_labels(
    expected_labels: np.ndarray,
    true_labels: np.ndarray,
    *,
    context: str,
) -> None:
    """Fail early when input-file order and TensorFlow labels disagree."""

    if len(expected_labels) != len(true_labels):
        raise RuntimeError(
            f"Found {len(expected_labels):,} expected labels but evaluated "
            f"{len(true_labels):,} labels for {context}."
        )

    if not np.array_equal(expected_labels, true_labels):
        raise RuntimeError(
            f"{context} ordering does not match TensorFlow label ordering."
        )


def _record_class_index(record: Record) -> int:
    """Read a manifest record's class index with a clear validation error."""

    class_index = record.get("class_index")
    if class_index not in (None, ""):
        try:
            index = int(class_index)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid class_index in record: {class_index!r}"
            ) from error
    else:
        label = record.get("label", record.get("true_label"))
        if label not in CLASS_TO_INDEX:
            raise ValueError(
                "Every evaluation record needs a valid class_index or label. "
                f"Received label={label!r}."
            )
        index = CLASS_TO_INDEX[str(label)]

    if index not in range(len(CLASS_NAMES)):
        raise ValueError(
            f"Class index must be in [0, {len(CLASS_NAMES) - 1}], got {index}."
        )
    return index


def _record_crop_path(record: Record) -> str:
    """Read the traceable crop path from a manifest record."""

    crop_path = record.get("crop_path")
    if crop_path in (None, ""):
        raise ValueError("Every evaluation record needs a non-empty crop_path.")
    return Path(str(crop_path)).as_posix()


def collect_predictions_from_records(
    model: keras.Model,
    dataset: tf.data.Dataset,
    records: Sequence[Record],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Run inference for explicitly ordered manifest records.

    ``records`` must be in the same order supplied to ``dataset`` and contain
    ``crop_path`` plus either ``class_index`` or ``label``.  The crop path is
    not used to infer the class, so this supports arbitrary manifest filters
    and does not depend on a class-directory layout.
    """

    true_labels, predicted_labels, probabilities, average_loss = (
        _collect_prediction_arrays(model, dataset)
    )
    expected_labels = np.array(
        [_record_class_index(record) for record in records],
        dtype=true_labels.dtype,
    )
    _validate_expected_labels(
        expected_labels,
        true_labels,
        context="Manifest record",
    )
    return true_labels, predicted_labels, probabilities, average_loss


def save_confusion_matrices(
    matrix: np.ndarray,
    output_path: Path,
    split: str = "evaluation",
    *,
    title: str | None = None,
) -> None:
    """Save count and row-normalized confusion matrices as one figure."""

    row_totals = matrix.sum(axis=1, keepdims=True)
    normalized_matrix = np.divide(
        matrix,
        row_totals,
        out=np.zeros_like(matrix, dtype=float),
        where=row_totals != 0,
    )
    split_title = {"val": "Validation", "test": "Test"}.get(
        split,
        split.replace("_", " ").title(),
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
    axes[0].set_title(f"{split_title} confusion matrix — counts")

    ConfusionMatrixDisplay(
        confusion_matrix=normalized_matrix,
        display_labels=CLASS_NAMES,
    ).plot(
        ax=axes[1],
        cmap="Blues",
        colorbar=False,
        values_format=".2f",
    )
    axes[1].set_title(
        f"{split_title} confusion matrix — row normalized"
    )

    figure.suptitle(title or "Custom CNN road-damage classification")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def save_prediction_records_csv(
    records: Sequence[Record],
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
    probabilities: np.ndarray,
    output_path: Path,
) -> None:
    """Save traceable manifest-record predictions for error analysis."""

    if len(records) != len(true_labels):
        raise ValueError(
            "records and true_labels must have identical lengths when writing "
            "predictions."
        )

    fieldnames = [
        "crop_path",
        "true_label",
        "predicted_label",
        "correct",
        "confidence",
        *[f"probability_{label}" for label in CLASS_NAMES],
    ]
    rows: list[dict[str, object]] = []
    for index, record in enumerate(records):
        true_index = int(true_labels[index])
        predicted_index = int(predicted_labels[index])
        row: dict[str, object] = {
            "crop_path": _record_crop_path(record),
            "true_label": CLASS_NAMES[true_index],
            "predicted_label": CLASS_NAMES[predicted_index],
            "correct": int(true_index == predicted_index),
            "confidence": float(probabilities[index, predicted_index]),
        }
        for class_index, label in enumerate(CLASS_NAMES):
            row[f"probability_{label}"] = float(
                probabilities[index, class_index]
            )
        rows.append(row)
    write_csv_atomic(output_path, fieldnames, rows)


def evaluate_classifier_records(
    model: keras.Model,
    dataset: tf.data.Dataset,
    records: Sequence[Record],
    output_directory: Path,
    *,
    split: str = "evaluation",
    batch_size: int | None = None,
    checkpoint_path: Path | str | None = None,
    role: str | None = None,
    title: str | None = None,
    compiled_dataset: tf.data.Dataset | None = None,
    compiled_metrics: Mapping[str, float] | None = None,
    artifact_paths: EvaluationArtifactPaths | None = None,
    metric_aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Evaluate manifest records and save metrics, confusion, and predictions.

    The supplied dataset must be deterministic and built from ``records`` in
    exactly the same order.  The result uses one eager prediction pass for all
    deployable metrics.  If a caller separately obtains a compiled Keras
    evaluation for save/reload certification, pass it through ``compiled_metrics``
    so its numerical difference is documented rather than silently mixed into
    the external report.  Pass a freshly constructed ``compiled_dataset`` to
    evaluate that path here, or pass already measured ``compiled_metrics``.
    Supplying both would hide which dataset produced the certification metric
    and is therefore rejected.
    """

    if compiled_dataset is not None and compiled_metrics is not None:
        raise ValueError(
            "Pass either compiled_dataset or compiled_metrics, not both."
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    paths = artifact_paths or EvaluationArtifactPaths(
        predictions=output_directory / "predictions.csv",
        confusion_csv=output_directory / "confusion_matrix.csv",
        confusion_figure=output_directory / "confusion_matrix.png",
        metrics=output_directory / "metrics.json",
    )
    for artifact_path in (
        paths.predictions,
        paths.confusion_csv,
        paths.confusion_figure,
        paths.metrics,
    ):
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

    if compiled_dataset is not None:
        compiled_metrics = evaluate_compiled_dataset(
            model,
            compiled_dataset,
        )

    start_time = time.perf_counter()
    true_labels, predicted_labels, probabilities, loss = (
        collect_predictions_from_records(model, dataset, records)
    )
    evaluation_seconds = time.perf_counter() - start_time
    metrics = compute_classification_metrics(
        true_labels,
        predicted_labels,
        loss=loss,
    )
    matrix = np.asarray(metrics["confusion_matrix"], dtype=int)

    save_prediction_records_csv(
        records,
        true_labels,
        predicted_labels,
        probabilities,
        paths.predictions,
    )
    save_confusion_matrix_csv(matrix, paths.confusion_csv)
    save_confusion_matrices(
        matrix,
        paths.confusion_figure,
        split,
        title=title,
    )

    results: dict[str, Any] = {
        **metrics,
        "role": role,
        "checkpoint": (
            project_relative(checkpoint_path)
            if checkpoint_path is not None
            else None
        ),
        "split": split,
        "batch_size": batch_size,
        "evaluation_seconds": evaluation_seconds,
        "images_per_second": len(true_labels) / evaluation_seconds,
        "class_mapping": CLASS_TO_INDEX,
        "class_descriptions": CLASS_DESCRIPTIONS,
        "tensorflow_version": tf.__version__,
        "gpu_devices": [
            device.name for device in tf.config.list_physical_devices("GPU")
        ],
        "predictions_path": project_relative(paths.predictions),
        "confusion_matrix_csv": project_relative(paths.confusion_csv),
        "confusion_matrix_figure": project_relative(paths.confusion_figure),
        "metrics_path": project_relative(paths.metrics),
    }
    if compiled_metrics is not None:
        normalized_compiled_metrics = normalized_metric_mapping(compiled_metrics)
        results["keras_evaluation"] = normalized_compiled_metrics
        if "accuracy" in normalized_compiled_metrics:
            results["keras_vs_prediction_accuracy_absolute_difference"] = abs(
                results["accuracy"] - normalized_compiled_metrics["accuracy"]
            )
        if "loss" in normalized_compiled_metrics:
            results["keras_vs_prediction_loss_absolute_difference"] = abs(
                results["loss"] - normalized_compiled_metrics["loss"]
            )

    for alias, source_name in (metric_aliases or {}).items():
        if source_name not in results:
            raise ValueError(
                f"Cannot create metric alias {alias!r}; "
                f"source metric {source_name!r} is absent."
            )
        results[alias] = results[source_name]

    write_json_atomic(paths.metrics, results)
    return results


def main() -> None:
    """Evaluate one checkpoint and save all legacy validation/test artifacts."""

    args = parse_arguments()
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    METRICS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    run_name = args.checkpoint.stem.removesuffix("_best")
    artifact_paths = EvaluationArtifactPaths(
        predictions=(
            METRICS_DIRECTORY / f"{run_name}_{args.split}_predictions.csv"
        ),
        confusion_csv=(
            METRICS_DIRECTORY
            / f"{run_name}_{args.split}_confusion_matrix.csv"
        ),
        confusion_figure=(
            FIGURE_DIRECTORY / f"{run_name}_{args.split}_confusion_matrix.png"
        ),
        metrics=(
            METRICS_DIRECTORY / f"{run_name}_{args.split}_metrics.json"
        ),
    )

    print(f"Checkpoint: {args.checkpoint}")
    print(f"TensorFlow: {tf.__version__}")
    print(f"Physical GPUs: {tf.config.list_physical_devices('GPU')}")

    model = keras.models.load_model(args.checkpoint, compile=False)
    dataset = load_split(
        split=args.split,
        batch_size=args.batch_size,
        shuffle=False,
    )
    crop_paths = ordered_crop_paths(args.split)
    records = [
        {
            "crop_path": crop_path.as_posix(),
            "class_index": CLASS_TO_INDEX[crop_path.parent.name],
        }
        for crop_path in crop_paths
    ]
    results = evaluate_classifier_records(
        model=model,
        dataset=dataset,
        records=records,
        output_directory=METRICS_DIRECTORY,
        split=args.split,
        batch_size=args.batch_size,
        checkpoint_path=args.checkpoint,
        title="Custom CNN road-damage classification",
        artifact_paths=artifact_paths,
        metric_aliases={"test_loss": "loss"},
    )

    split_title = "Validation" if args.split == "val" else "Test"
    print(f"\n{split_title} results")
    print("-" * (len(split_title) + 8))
    print(f"Examples: {results['number_of_examples']:,}")
    print(f"Loss: {results['loss']:.4f}")
    print(f"Accuracy: {results['accuracy']:.4f}")
    print(f"Balanced accuracy: {results['balanced_accuracy']:.4f}")
    print(f"Macro F1: {results['macro_f1']:.4f}")
    print(f"Weighted F1: {results['weighted_f1']:.4f}")
    print(f"Evaluation time: {results['evaluation_seconds']:.2f} seconds")
    print(
        f"Throughput: {results['images_per_second']:.2f} images/s"
    )
    print("\nPer-class metrics")
    for label in CLASS_NAMES:
        class_metrics = results["classification_report"][label]
        print(
            f"{label}: precision={class_metrics['precision']:.4f}, "
            f"recall={class_metrics['recall']:.4f}, "
            f"F1={class_metrics['f1-score']:.4f}, "
            f"support={int(class_metrics['support']):,}"
        )
    print(f"Metrics: {artifact_paths.metrics}")
    print(f"Predictions: {artifact_paths.predictions}")
    print(f"Confusion matrix: {artifact_paths.confusion_figure}")


if __name__ == "__main__":
    main()

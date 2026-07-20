"""Framework-light classifier metrics shared by training and analysis."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from src.utils.classes import CLASS_NAMES
from src.utils.experiment_artifacts import write_csv_atomic


def compute_classification_metrics(
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
    *,
    loss: float | None = None,
) -> dict[str, Any]:
    """Compute one canonical multiclass classification report."""

    if len(true_labels) == 0:
        raise ValueError("Cannot compute metrics for zero predictions.")
    if len(true_labels) != len(predicted_labels):
        raise ValueError(
            "true_labels and predicted_labels must have identical lengths."
        )

    class_indices = list(range(len(CLASS_NAMES)))
    matrix = confusion_matrix(
        true_labels,
        predicted_labels,
        labels=class_indices,
    )
    report = classification_report(
        true_labels,
        predicted_labels,
        labels=class_indices,
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    metrics: dict[str, Any] = {
        "number_of_examples": int(len(true_labels)),
        "accuracy": float(accuracy_score(true_labels, predicted_labels)),
        "balanced_accuracy": float(
            balanced_accuracy_score(true_labels, predicted_labels)
        ),
        "macro_f1": float(
            f1_score(
                true_labels,
                predicted_labels,
                labels=class_indices,
                average="macro",
                zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                true_labels,
                predicted_labels,
                labels=class_indices,
                average="weighted",
                zero_division=0,
            )
        ),
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
    }
    if loss is not None:
        metrics["loss"] = float(loss)
    return metrics


def save_confusion_matrix_csv(
    matrix: np.ndarray,
    output_path: Path,
) -> None:
    """Write a portable count confusion matrix for downstream analysis."""

    fieldnames = ["true_label", *[f"predicted_{label}" for label in CLASS_NAMES]]
    rows = [
        {
            "true_label": true_label,
            **{
                f"predicted_{predicted_label}": int(
                    matrix[true_index, predicted_index]
                )
                for predicted_index, predicted_label in enumerate(CLASS_NAMES)
            },
        }
        for true_index, true_label in enumerate(CLASS_NAMES)
    ]
    write_csv_atomic(output_path, fieldnames, rows)


def normalized_metric_mapping(
    metrics: Mapping[str, float],
) -> dict[str, float]:
    """Convert framework scalar metrics into JSON-safe Python floats."""

    return {name: float(value) for name, value in metrics.items()}

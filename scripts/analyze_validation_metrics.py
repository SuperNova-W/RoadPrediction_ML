"""Perform structured error analysis for classifier validation predictions."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image
from src.evaluation.classifier_metrics import (
    compute_classification_metrics,
    save_confusion_matrix_csv,
)
from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX
from src.utils.experiment_artifacts import (
    read_json_object,
    write_csv_atomic,
    write_json_atomic,
)


matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402


DEFAULT_CROP_MANIFEST_PATH = Path(
    "data/processed/classification_crops.csv"
)
DEFAULT_METRICS_DIRECTORY = Path("outputs/metrics")
DEFAULT_FIGURE_DIRECTORY = Path("outputs/figures")
MODEL_INPUT_SIZE = 224

REVIEW_METADATA_FIELDS = (
    "country",
    "source_image_path",
    "annotation_path",
    "sequence_group",
    "xmin",
    "ymin",
    "xmax",
    "ymax",
    "crop_left",
    "crop_top",
    "crop_right",
    "crop_bottom",
)
REVIEW_FIELDNAMES = (
    "rank",
    "review_category",
    "crop_path",
    "true_label",
    "predicted_label",
    "correct",
    "confidence",
    *[f"probability_{label}" for label in CLASS_NAMES],
    *REVIEW_METADATA_FIELDS,
)


def parse_arguments() -> argparse.Namespace:
    """Read the validation artifact paths and review-set size."""

    parser = argparse.ArgumentParser(
        description="Analyze a classifier validation prediction CSV."
    )
    parser.add_argument(
        "--predictions-path",
        type=Path,
        required=True,
        help="Prediction CSV written by evaluate_classifier.py.",
    )
    parser.add_argument(
        "--crop-manifest-path",
        type=Path,
        default=DEFAULT_CROP_MANIFEST_PATH,
        help="Crop manifest corresponding to the evaluated prediction CSV.",
    )
    parser.add_argument(
        "--evaluation-metrics-path",
        type=Path,
        default=None,
        help="Optional evaluator JSON used to record checkpoint provenance.",
    )
    parser.add_argument(
        "--metrics-directory",
        type=Path,
        default=DEFAULT_METRICS_DIRECTORY,
    )
    parser.add_argument(
        "--figure-directory",
        type=Path,
        default=DEFAULT_FIGURE_DIRECTORY,
    )
    parser.add_argument(
        "--review-size",
        type=int,
        default=12,
        help="Maximum examples to retain in each visual-review category.",
    )

    args = parser.parse_args()

    for path, description in (
        (args.predictions_path, "Prediction CSV"),
        (args.crop_manifest_path, "Crop manifest"),
    ):
        if not path.is_file():
            parser.error(f"{description} does not exist: {path}")

    if (
        args.evaluation_metrics_path is not None
        and not args.evaluation_metrics_path.is_file()
    ):
        parser.error(
            "Evaluation metrics JSON does not exist: "
            f"{args.evaluation_metrics_path}"
        )
    if args.review_size <= 0:
        parser.error("--review-size must be greater than zero")

    return args


def analysis_name(predictions_path: Path) -> str:
    """Derive a stable output prefix from an evaluator prediction CSV."""

    return predictions_path.stem.removesuffix("_predictions")


def load_crop_metadata(
    crop_manifest_path: Path,
) -> dict[str, dict[str, str]]:
    """Index validation crop metadata by its exact generated crop path."""

    metadata_by_path: dict[str, dict[str, str]] = {}

    with crop_manifest_path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            if row["split"] != "val":
                continue

            crop_path = row["crop_path"]

            if crop_path in metadata_by_path:
                raise ValueError(
                    "Crop manifest contains duplicate validation paths: "
                    f"{crop_path}"
                )

            metadata_by_path[crop_path] = row

    if not metadata_by_path:
        raise ValueError(
            "Crop manifest does not contain any validation examples: "
            f"{crop_manifest_path}"
        )

    return metadata_by_path


def load_predictions(
    predictions_path: Path,
    crop_metadata: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    """Load evaluator predictions and attach their source/crop metadata."""

    enriched_predictions: list[dict[str, object]] = []

    with predictions_path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            crop_path = row["crop_path"]
            metadata = crop_metadata.get(crop_path)

            if metadata is None:
                raise ValueError(
                    "Prediction crop is absent from the validation manifest: "
                    f"{crop_path}"
                )
            if row["true_label"] != metadata["label"]:
                raise ValueError(
                    "Prediction label and crop manifest label disagree: "
                    f"{crop_path}"
                )

            prediction: dict[str, object] = {
                "crop_path": crop_path,
                "true_label": row["true_label"],
                "predicted_label": row["predicted_label"],
                "correct": int(row["correct"]),
                "confidence": float(row["confidence"]),
            }

            for label in CLASS_NAMES:
                prediction[f"probability_{label}"] = float(
                    row[f"probability_{label}"]
                )

            for field_name in REVIEW_METADATA_FIELDS:
                prediction[field_name] = metadata[field_name]

            enriched_predictions.append(prediction)

    if not enriched_predictions:
        raise ValueError(f"Prediction CSV is empty: {predictions_path}")

    return enriched_predictions


def label_indices_from_predictions(
    predictions: list[dict[str, object]],
) -> tuple[np.ndarray, np.ndarray]:
    """Extract parallel integer targets in canonical classifier order."""

    return (
        np.asarray(
            [
                CLASS_TO_INDEX[str(prediction["true_label"])]
                for prediction in predictions
            ],
            dtype=int,
        ),
        np.asarray(
            [
                CLASS_TO_INDEX[str(prediction["predicted_label"])]
                for prediction in predictions
            ],
            dtype=int,
        ),
    )


def global_metrics(
    predictions: list[dict[str, object]],
) -> dict[str, object]:
    """Calculate the required validation metrics and confusion matrix."""

    true_labels, predicted_labels = label_indices_from_predictions(predictions)
    metrics = compute_classification_metrics(true_labels, predicted_labels)
    metrics["examples"] = metrics.pop("number_of_examples")
    return metrics


def country_metrics(
    predictions: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Calculate summary and class-level validation metrics by country."""

    predictions_by_country: dict[str, list[dict[str, object]]] = defaultdict(
        list
    )

    for prediction in predictions:
        predictions_by_country[str(prediction["country"])].append(prediction)

    summary_rows: list[dict[str, object]] = []
    class_rows: list[dict[str, object]] = []

    for country in sorted(predictions_by_country):
        country_predictions = predictions_by_country[country]
        true_labels, predicted_labels = label_indices_from_predictions(
            country_predictions
        )
        metrics = compute_classification_metrics(
            true_labels,
            predicted_labels,
        )
        report = dict(metrics["classification_report"])

        summary_rows.append(
            {
                "country": country,
                "examples": metrics["number_of_examples"],
                "accuracy": metrics["accuracy"],
                "balanced_accuracy": metrics["balanced_accuracy"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
            }
        )

        for label in CLASS_NAMES:
            class_report = report[label]
            class_rows.append(
                {
                    "country": country,
                    "label": label,
                    "precision": class_report["precision"],
                    "recall": class_report["recall"],
                    "f1_score": class_report["f1-score"],
                    "support": int(class_report["support"]),
                }
            )

    return summary_rows, class_rows


def dominant_confusions(
    matrix: list[list[int]],
) -> list[dict[str, object]]:
    """Rank all incorrect true/predicted class pairs by their frequency."""

    confusion_rows = [
        {
            "true_label": true_label,
            "predicted_label": predicted_label,
            "examples": int(matrix[true_index][predicted_index]),
        }
        for true_index, true_label in enumerate(CLASS_NAMES)
        for predicted_index, predicted_label in enumerate(CLASS_NAMES)
        if true_label != predicted_label
        and matrix[true_index][predicted_index] > 0
    ]

    return sorted(
        confusion_rows,
        key=lambda row: int(row["examples"]),
        reverse=True,
    )


def select_review_rows(
    predictions: list[dict[str, object]],
    review_size: int,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, int]]:
    """Select reproducible examples for each requested visual review category."""

    is_correct = lambda row: bool(int(row["correct"]))

    populations = {
        "high_confidence_errors": [
            row for row in predictions if not is_correct(row)
        ],
        "low_confidence_correct": [
            row for row in predictions if is_correct(row)
        ],
        "d00_d10_orientation_confusions": [
            row
            for row in predictions
            if {
                str(row["true_label"]),
                str(row["predicted_label"]),
            }
            == {"D00", "D10"}
        ],
        "missed_d20": [
            row
            for row in predictions
            if row["true_label"] == "D20"
            and row["predicted_label"] != "D20"
        ],
        "missed_d40": [
            row
            for row in predictions
            if row["true_label"] == "D40"
            and row["predicted_label"] != "D40"
        ],
    }

    selections = {
        "high_confidence_errors": select_diverse_rows(
            populations["high_confidence_errors"],
            review_size=review_size,
            descending_confidence=True,
        ),
        "low_confidence_correct": select_class_balanced_rows(
            populations["low_confidence_correct"],
            review_size=review_size,
            descending_confidence=False,
        ),
        "d00_d10_orientation_confusions": select_orientation_confusions(
            populations["d00_d10_orientation_confusions"],
            review_size=review_size,
        ),
        "missed_d20": select_diverse_rows(
            populations["missed_d20"],
            review_size=review_size,
            descending_confidence=True,
        ),
        "missed_d40": select_diverse_rows(
            populations["missed_d40"],
            review_size=review_size,
            descending_confidence=True,
        ),
    }

    return selections, {
        category: len(rows)
        for category, rows in populations.items()
    }


def select_class_balanced_rows(
    rows: list[dict[str, object]],
    review_size: int,
    descending_confidence: bool,
) -> list[dict[str, object]]:
    """Include each correct class before filling the ranked review set.

    A purely confidence-ranked set can hide classes whose calibrated confidence
    is systematically higher.  This keeps the lowest-confidence correct review
    useful for every class while preserving deterministic ordering.
    """

    selected: list[dict[str, object]] = []
    selected_paths: set[str] = set()

    for label in CLASS_NAMES:
        class_rows = [
            row for row in rows if str(row["true_label"]) == label
        ]
        class_selection = select_diverse_rows(
            class_rows,
            review_size=1,
            descending_confidence=descending_confidence,
        )
        for row in class_selection:
            selected.append(row)
            selected_paths.add(str(row["crop_path"]))

    if len(selected) >= review_size:
        return selected[:review_size]

    remaining_rows = [
        row for row in rows if str(row["crop_path"]) not in selected_paths
    ]
    selected.extend(
        select_diverse_rows(
            remaining_rows,
            review_size=review_size - len(selected),
            descending_confidence=descending_confidence,
        )
    )
    return selected


def select_orientation_confusions(
    rows: list[dict[str, object]],
    review_size: int,
) -> list[dict[str, object]]:
    """Retain both directions of the D00/D10 orientation confusion.

    D00-to-D10 is much more frequent.  Reserving a small slot for D10-to-D00
    prevents that rare but informative reverse error from disappearing from a
    confidence-ranked sheet.
    """

    d00_to_d10 = [
        row
        for row in rows
        if row["true_label"] == "D00"
        and row["predicted_label"] == "D10"
    ]
    d10_to_d00 = [
        row
        for row in rows
        if row["true_label"] == "D10"
        and row["predicted_label"] == "D00"
    ]

    # Up to one third of the compact review may show the rare reverse direction;
    # this preserves all available examples for the current validation split.
    reverse_limit = min(len(d10_to_d00), max(1, review_size // 3))
    reverse_selection = select_diverse_rows(
        d10_to_d00,
        review_size=reverse_limit,
        descending_confidence=True,
    )
    forward_selection = select_diverse_rows(
        d00_to_d10,
        review_size=review_size - len(reverse_selection),
        descending_confidence=True,
    )
    return [*forward_selection, *reverse_selection]


def select_diverse_rows(
    rows: list[dict[str, object]],
    review_size: int,
    descending_confidence: bool,
) -> list[dict[str, object]]:
    """Prefer distinct source images and sequence groups in a ranked review."""

    ordered_rows = sorted(
        rows,
        key=lambda row: (
            -float(row["confidence"])
            if descending_confidence
            else float(row["confidence"]),
            str(row["crop_path"]),
        ),
    )
    selected: list[dict[str, object]] = []
    selected_paths: set[str] = set()
    seen_sources: set[str] = set()
    seen_groups: set[str] = set()

    # First select the most diverse examples, then relax the constraints only
    # when a rare slice cannot fill the requested review size.
    for require_new_source, require_new_group in (
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ):
        for row in ordered_rows:
            if len(selected) == review_size:
                return selected

            crop_path = str(row["crop_path"])
            source_image_path = str(row["source_image_path"])
            sequence_group = str(row["sequence_group"])

            if crop_path in selected_paths:
                continue
            if require_new_source and source_image_path in seen_sources:
                continue
            if require_new_group and sequence_group in seen_groups:
                continue

            selected.append(row)
            selected_paths.add(crop_path)
            seen_sources.add(source_image_path)
            seen_groups.add(sequence_group)

    return selected


def review_rows_with_ranks(
    selections: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Attach category/rank fields used by review CSVs and figure titles."""

    ranked_rows: list[dict[str, object]] = []

    for category, rows in selections.items():
        for rank, row in enumerate(rows, start=1):
            ranked_row = dict(row)
            ranked_row["rank"] = rank
            ranked_row["review_category"] = category
            ranked_rows.append(ranked_row)

    return ranked_rows


def model_input_preview(
    image: Image.Image,
) -> tuple[Image.Image, float, int, int]:
    """Recreate the legacy black-padded 224×224 classifier input for review."""

    scale = min(
        MODEL_INPUT_SIZE / image.width,
        MODEL_INPUT_SIZE / image.height,
    )
    resized_width = max(1, round(image.width * scale))
    resized_height = max(1, round(image.height * scale))
    resized_image = image.resize(
        (resized_width, resized_height),
        resample=Image.Resampling.BILINEAR,
    )
    padded_image = Image.new(
        "RGB",
        (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE),
        color=(0, 0, 0),
    )
    offset_x = (MODEL_INPUT_SIZE - resized_width) // 2
    offset_y = (MODEL_INPUT_SIZE - resized_height) // 2
    padded_image.paste(resized_image, (offset_x, offset_y))

    return padded_image, scale, offset_x, offset_y


def save_review_contact_sheet(
    rows: list[dict[str, object]],
    category: str,
    output_path: Path,
) -> None:
    """Render actual legacy model inputs with their ground-truth boxes."""

    if not rows:
        return

    columns = min(4, len(rows))
    row_count = math.ceil(len(rows) / columns)
    figure, axes = plt.subplots(
        row_count,
        columns,
        figsize=(4.5 * columns, 4.7 * row_count),
        squeeze=False,
    )

    for axis in axes.flat:
        axis.axis("off")

    for rank, (axis, row) in enumerate(zip(axes.flat, rows), start=1):
        crop_path = Path(str(row["crop_path"]))

        if not crop_path.is_file():
            raise FileNotFoundError(
                f"Review crop no longer exists: {crop_path}"
            )

        with Image.open(crop_path) as crop:
            image = crop.convert("RGB")

        model_input, scale, offset_x, offset_y = model_input_preview(image)
        crop_left = float(row["crop_left"])
        crop_top = float(row["crop_top"])
        xmin = offset_x + (float(row["xmin"]) - crop_left) * scale
        ymin = offset_y + (float(row["ymin"]) - crop_top) * scale
        width = (float(row["xmax"]) - float(row["xmin"])) * scale
        height = (float(row["ymax"]) - float(row["ymin"])) * scale
        native_aspect_ratio = image.width / image.height

        axis.imshow(model_input)
        axis.add_patch(
            Rectangle(
                (xmin, ymin),
                width,
                height,
                fill=False,
                edgecolor="#00d4ff",
                linewidth=2.0,
            )
        )
        axis.set_title(
            f"#{rank}  {row['true_label']} → "
            f"{row['predicted_label']}\n"
            f"confidence={float(row['confidence']):.1%} · "
            f"aspect={native_aspect_ratio:.2f} · {row['country']}",
            fontsize=9,
        )
        axis.axis("off")

    figure.suptitle(
        category.replace("_", " ").title(),
        fontsize=14,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def print_global_summary(metrics: dict[str, object]) -> None:
    """Print a short terminal summary for the completed analysis."""

    print("\nGlobal validation metrics")
    print("-------------------------")
    print(f"Examples: {metrics['examples']:,}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Balanced accuracy: {metrics['balanced_accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"Weighted F1: {metrics['weighted_f1']:.4f}")

    print("\nPer-class metrics")
    print("-----------------")
    report = dict(metrics["classification_report"])

    for label in CLASS_NAMES:
        class_metrics = dict(report[label])
        print(
            f"{label}: precision={class_metrics['precision']:.4f}, "
            f"recall={class_metrics['recall']:.4f}, "
            f"F1={class_metrics['f1-score']:.4f}, "
            f"support={int(class_metrics['support']):,}"
        )


def main() -> None:
    """Write metrics, country reports, and a visual review set from validation."""

    args = parse_arguments()
    args.metrics_directory.mkdir(parents=True, exist_ok=True)
    args.figure_directory.mkdir(parents=True, exist_ok=True)

    run_name = analysis_name(args.predictions_path)
    crop_metadata = load_crop_metadata(args.crop_manifest_path)
    predictions = load_predictions(args.predictions_path, crop_metadata)
    metrics = global_metrics(predictions)
    country_summary, country_classes = country_metrics(predictions)
    selections, review_population_counts = select_review_rows(
        predictions,
        args.review_size,
    )
    ranked_review_rows = review_rows_with_ranks(selections)

    output_prefix = f"{run_name}_structured"
    confusion_path = (
        args.metrics_directory / f"{output_prefix}_confusion_matrix.csv"
    )
    country_summary_path = (
        args.metrics_directory / f"{output_prefix}_country_summary.csv"
    )
    country_classes_path = (
        args.metrics_directory / f"{output_prefix}_country_classes.csv"
    )
    review_set_path = (
        args.metrics_directory / f"{output_prefix}_review_set.csv"
    )
    analysis_path = (
        args.metrics_directory / f"{output_prefix}_analysis.json"
    )

    save_confusion_matrix_csv(
        matrix=np.asarray(metrics["confusion_matrix"], dtype=int),
        output_path=confusion_path,
    )
    write_csv_atomic(
        country_summary_path,
        (
            "country",
            "examples",
            "accuracy",
            "balanced_accuracy",
            "macro_f1",
            "weighted_f1",
        ),
        country_summary,
    )
    write_csv_atomic(
        country_classes_path,
        (
            "country",
            "label",
            "precision",
            "recall",
            "f1_score",
            "support",
        ),
        country_classes,
    )
    write_csv_atomic(
        review_set_path,
        REVIEW_FIELDNAMES,
        ranked_review_rows,
    )

    review_figure_paths: dict[str, str] = {}

    for category, rows in selections.items():
        figure_path = (
            args.figure_directory / f"{output_prefix}_{category}.png"
        )
        save_review_contact_sheet(
            rows=rows,
            category=category,
            output_path=figure_path,
        )

        if rows:
            review_figure_paths[category] = figure_path.as_posix()

    evaluator_provenance: dict[str, object] | None = None

    if args.evaluation_metrics_path is not None:
        evaluator_provenance = read_json_object(args.evaluation_metrics_path)

    analysis = {
        "analysis_scope": (
            "validation-only structured error analysis; do not use for test "
            "selection or hyperparameter tuning"
        ),
        "prediction_csv": args.predictions_path.as_posix(),
        "crop_manifest": args.crop_manifest_path.as_posix(),
        "evaluator_provenance": evaluator_provenance,
        "metrics": metrics,
        "dominant_confusions": dominant_confusions(
            list(metrics["confusion_matrix"])
        ),
        "country_summary_path": country_summary_path.as_posix(),
        "country_classes_path": country_classes_path.as_posix(),
        "confusion_matrix_path": confusion_path.as_posix(),
        "review_set_path": review_set_path.as_posix(),
        "review_population_counts": review_population_counts,
        "review_size_per_category": args.review_size,
        "review_figures": review_figure_paths,
    }

    write_json_atomic(analysis_path, analysis)

    print_global_summary(metrics)
    print("\nReview populations")
    print("------------------")

    for category, count in review_population_counts.items():
        print(f"{category}: {count:,}")

    print("\nSaved artifacts")
    print("---------------")
    print(f"Analysis: {analysis_path}")
    print(f"Country summary: {country_summary_path}")
    print(f"Country classes: {country_classes_path}")
    print(f"Review set: {review_set_path}")


if __name__ == "__main__":
    main()

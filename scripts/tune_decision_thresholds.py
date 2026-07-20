"""Tune per-class decision biases post-hoc to lift minority-class recall.

The classifier is trained and certified as usual; this script does not touch the
weights. It replaces plain ``argmax`` with ``argmax(logits + bias)`` and fits the
per-class ``bias`` vector to maximize macro-F1 on the internal U.S. tuning set,
then applies that frozen bias to the untouched U.S. holdout. Because the decision
rule is applied to the already-softmaxed probabilities, the search runs in
``log`` space: ``argmax(log p_c + bias_c)`` is exactly ``argmax(logit_c + bias_c)``.

This directly counteracts a class (here D20, alligator cracking) whose true crops
leak into other classes under argmax. It is a decision rule, not a weight change,
so the certified checkpoint stays valid and no re-certification is needed.

The bias is fit on the tuning set, so the **holdout** numbers are the honest test.
With very few minority tuning crops (D40 has only 13) the fit can overfit the
tuning set; the script reports tune and holdout side by side so that is visible.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from sklearn.metrics import f1_score

from src.evaluation.classifier_metrics import (
    compute_classification_metrics,
    save_confusion_matrix_csv,
)
from src.utils.classes import CLASS_NAMES, NUM_CLASSES
from src.utils.experiment_artifacts import (
    project_relative,
    read_json_object,
    resolve_path,
    utc_now,
    write_json_atomic,
)

if TYPE_CHECKING:
    import tensorflow as tf


def parse_arguments() -> argparse.Namespace:
    """Read the experiment directory and search settings."""

    parser = argparse.ArgumentParser(
        description=(
            "Fit per-class decision biases on the tuning set and apply them to "
            "the U.S. holdout."
        )
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="A completed train_efficientnet_v2 experiment directory.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Override the checkpoint (defaults to <experiment>/checkpoints/restored.keras).",
    )
    parser.add_argument(
        "--output-subdir",
        type=str,
        default="threshold_tuning",
        help="Subdirectory of the experiment to write results into.",
    )
    parser.add_argument(
        "--bias-limit",
        type=float,
        default=4.0,
        help="Maximum absolute per-class log-odds bias explored.",
    )
    parser.add_argument(
        "--bias-step",
        type=float,
        default=0.25,
        help="Grid resolution for the coordinate-ascent search.",
    )
    parser.add_argument(
        "--max-sweeps",
        type=int,
        default=12,
        help="Maximum coordinate-ascent sweeps over the classes.",
    )
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)

    args = parser.parse_args()
    if args.bias_limit <= 0:
        parser.error("--bias-limit must be greater than zero")
    if args.bias_step <= 0:
        parser.error("--bias-step must be greater than zero")
    if args.max_sweeps <= 0:
        parser.error("--max-sweeps must be greater than zero")
    return args


def log_probabilities(probabilities: np.ndarray) -> np.ndarray:
    """Return numerically safe log-probabilities for additive-bias search."""

    return np.log(np.clip(probabilities, 1e-12, 1.0))


def predict_with_bias(log_probs: np.ndarray, bias: np.ndarray) -> np.ndarray:
    """Predict classes from biased log-probabilities."""

    return np.argmax(log_probs + bias, axis=1)


def macro_f1(true_labels: np.ndarray, predicted_labels: np.ndarray) -> float:
    """Macro-averaged F1 over all classes (absent classes score zero)."""

    return float(
        f1_score(
            true_labels,
            predicted_labels,
            labels=list(range(NUM_CLASSES)),
            average="macro",
            zero_division=0,
        )
    )


def optimize_class_biases(
    log_probs: np.ndarray,
    true_labels: np.ndarray,
    *,
    bias_limit: float,
    bias_step: float,
    max_sweeps: int,
) -> tuple[np.ndarray, float]:
    """Coordinate-ascent the per-class bias to maximize macro-F1.

    The first class's bias is fixed at zero: adding a constant to every class
    leaves ``argmax`` unchanged, so only the relative offsets are identifiable.
    macro-F1 is piecewise-constant in the bias, so a grid coordinate search is
    used rather than a gradient method.
    """

    grid = np.arange(-bias_limit, bias_limit + bias_step / 2, bias_step)
    bias = np.zeros(NUM_CLASSES, dtype=float)
    best_score = macro_f1(true_labels, predict_with_bias(log_probs, bias))

    for _ in range(max_sweeps):
        improved = False
        for class_index in range(1, NUM_CLASSES):
            candidate = bias.copy()
            best_value = bias[class_index]
            for value in grid:
                candidate[class_index] = value
                score = macro_f1(
                    true_labels, predict_with_bias(log_probs, candidate)
                )
                if score > best_score + 1e-9:
                    best_score = score
                    best_value = value
            if not np.isclose(best_value, bias[class_index]):
                bias[class_index] = best_value
                improved = True
        if not improved:
            break

    return bias, best_score


def per_class_recall(
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
) -> dict[str, float]:
    """Recall per class label from a prediction vector."""

    report = compute_classification_metrics(true_labels, predicted_labels)[
        "classification_report"
    ]
    return {label: float(report[label]["recall"]) for label in CLASS_NAMES}


def summarize(
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
) -> dict[str, Any]:
    """Compact accuracy/balanced/macro-F1/per-class-recall summary."""

    metrics = compute_classification_metrics(true_labels, predicted_labels)
    report = metrics["classification_report"]
    return {
        "accuracy": metrics["accuracy"],
        "balanced_accuracy": metrics["balanced_accuracy"],
        "macro_f1": metrics["macro_f1"],
        "per_class_recall": {
            label: float(report[label]["recall"]) for label in CLASS_NAMES
        },
    }


def collect(
    model: Any,
    manifest_path: Path,
    crop_root: Path,
    batch_size: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Eager-infer one manifest, returning (true_labels, probabilities)."""

    from src.datasets.classification_dataset import (
        build_dataset_from_records,
        load_manifest_records,
    )
    from src.evaluation.evaluate_classifier import collect_predictions_from_records

    records = load_manifest_records(
        manifest_path,
        crop_root=crop_root,
        require_existing_files=True,
    )
    dataset = build_dataset_from_records(
        records,
        batch_size=batch_size,
        shuffle=False,
        seed=seed,
    )
    true_labels, _, probabilities, _ = collect_predictions_from_records(
        model, dataset, records
    )
    return true_labels, probabilities


def write_holdout_artifacts(
    output_directory: Path,
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
    title: str,
) -> str:
    """Write a metrics.json + confusion matrix for a biased holdout evaluation."""

    from src.evaluation.evaluate_classifier import save_confusion_matrices

    output_directory.mkdir(parents=True, exist_ok=True)
    metrics = compute_classification_metrics(true_labels, predicted_labels)
    matrix = np.asarray(metrics["confusion_matrix"], dtype=int)

    save_confusion_matrix_csv(matrix, output_directory / "confusion_matrix.csv")
    save_confusion_matrices(
        matrix,
        output_directory / "confusion_matrix.png",
        "val",
        title=title,
    )
    metrics_path = output_directory / "metrics.json"
    write_json_atomic(metrics_path, metrics)
    return project_relative(metrics_path)


def main() -> None:
    """Fit decision biases on tune, apply to holdout, and write artifacts."""

    args = parse_arguments()

    experiment_directory = resolve_path(args.experiment_dir)
    config = read_json_object(experiment_directory / "config.json")
    crop_root = resolve_path(str(config["square_dataset"]["directory"]))
    tune_manifest = resolve_path(str(config["manifests"]["us_internal_tune"]["path"]))
    holdout_manifest = resolve_path(
        str(config["manifests"]["us_comparison_holdout"]["path"])
    )
    batch_size = args.batch_size or int(config["arguments"]["eval_batch_size"])
    seed = args.seed if args.seed is not None else int(config["arguments"]["seed"])
    checkpoint_path = (
        resolve_path(args.checkpoint)
        if args.checkpoint is not None
        else experiment_directory / "checkpoints" / "restored.keras"
    )
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint does not exist: {checkpoint_path}")

    from tensorflow import keras

    print(f"Loading {project_relative(checkpoint_path)} ...", flush=True)
    model = keras.models.load_model(checkpoint_path, compile=False)

    print("Running eager inference on the tuning and holdout sets ...", flush=True)
    tune_true, tune_probs = collect(
        model, tune_manifest, crop_root, batch_size, seed
    )
    holdout_true, holdout_probs = collect(
        model, holdout_manifest, crop_root, batch_size, seed
    )

    tune_log_probs = log_probabilities(tune_probs)
    holdout_log_probs = log_probabilities(holdout_probs)
    zero_bias = np.zeros(NUM_CLASSES, dtype=float)

    tune_argmax = predict_with_bias(tune_log_probs, zero_bias)
    holdout_argmax = predict_with_bias(holdout_log_probs, zero_bias)

    bias, tune_macro_f1_after = optimize_class_biases(
        tune_log_probs,
        tune_true,
        bias_limit=args.bias_limit,
        bias_step=args.bias_step,
        max_sweeps=args.max_sweeps,
    )

    tune_tuned = predict_with_bias(tune_log_probs, bias)
    holdout_tuned = predict_with_bias(holdout_log_probs, bias)

    output_directory = experiment_directory / args.output_subdir
    holdout_metrics_path = write_holdout_artifacts(
        output_directory / "us_holdout_thresholded",
        holdout_true,
        holdout_tuned,
        title="U.S. Holdout — EfficientNetV2-B1 (per-class decision bias)",
    )

    result = {
        "created_at_utc": utc_now(),
        "experiment_id": experiment_directory.name,
        "checkpoint": project_relative(checkpoint_path),
        "method": "per_class_additive_logit_bias",
        "objective": "macro_f1_on_internal_tune",
        "search": {
            "bias_limit": args.bias_limit,
            "bias_step": args.bias_step,
            "max_sweeps": args.max_sweeps,
        },
        "class_bias": {
            label: float(bias[index]) for index, label in enumerate(CLASS_NAMES)
        },
        "internal_tune": {
            "argmax": summarize(tune_true, tune_argmax),
            "thresholded": summarize(tune_true, tune_tuned),
        },
        "us_holdout": {
            "argmax": summarize(holdout_true, holdout_argmax),
            "thresholded": summarize(holdout_true, holdout_tuned),
        },
        "us_holdout_thresholded_metrics_path": holdout_metrics_path,
        "caveat": (
            "Bias fit on the internal tuning set (D40 has only 13 crops); the "
            "U.S. holdout comparison below is the honest test."
        ),
    }
    write_json_atomic(output_directory / "decision_thresholds.json", result)

    _print_report(result)


def _print_report(result: dict[str, Any]) -> None:
    """Print an argmax-vs-thresholded comparison on tune and holdout."""

    rule = "=" * 74
    print(f"\n{rule}\n  Per-class decision bias (fit on internal tune)\n{rule}")
    for label in CLASS_NAMES:
        print(f"    {label} bias: {result['class_bias'][label]:+.3f}")

    for scope in ("internal_tune", "us_holdout"):
        before = result[scope]["argmax"]
        after = result[scope]["thresholded"]
        heading = "Internal tuning set" if scope == "internal_tune" else "U.S. holdout"
        honest = "  (honest test)" if scope == "us_holdout" else "  (fit here)"
        print(f"\n{rule}\n  {heading}{honest}\n{rule}")
        print(f"    {'metric':<20}{'argmax':>12}{'thresholded':>14}{'delta':>10}")
        for name, key in (
            ("accuracy", "accuracy"),
            ("balanced accuracy", "balanced_accuracy"),
            ("macro F1", "macro_f1"),
        ):
            b, a = before[key], after[key]
            print(f"    {name:<20}{b:>12.4f}{a:>14.4f}{a - b:>+10.4f}")
        print(f"    {'per-class recall':<20}")
        for label in CLASS_NAMES:
            b = before["per_class_recall"][label]
            a = after["per_class_recall"][label]
            print(f"      {label:<18}{b:>12.4f}{a:>14.4f}{a - b:>+10.4f}")


if __name__ == "__main__":
    main()

"""Train an EfficientNetV2-B1 damage classifier with two-stage transfer learning.

This trainer targets accuracy, not the controlled A/B contrast of
``two_arm_experiment``. The two-arm study showed that including the Norway and
India crops helps, so training here uses the full ``train`` split from every
country (Norway and India included), holding out only the fixed internal U.S.
tuning groups for early stopping and the untouched U.S. ``val`` split for the
final report — the same evaluation surface as the two-arm runs, so the numbers
are directly comparable.

Stage 1 trains just the classification head on a frozen ImageNet backbone
(batch size 32, at most a small number of epochs). Stage 2 unfreezes the
backbone and fine-tunes end to end at a low learning rate (batch size 16). The
saved checkpoint is then certified in a genuinely fresh Python process and
evaluated on the internal tuning set and the U.S. holdout, reusing the exact
eager-inference and subprocess-certification machinery the custom-CNN pipeline
uses.
"""

from __future__ import annotations

import argparse
import math
import time
import traceback
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from src.datasets.classification_dataset import (
    CropRecord,
    build_dataset_from_records,
    filter_crop_records,
    load_crop_manifest,
)
from src.training.classifier_training import (
    SubprocessCertification,
    balanced_class_weights,
    build_classifier_callbacks,
    certify_saved_classifier,
    compare_metric_sets,
    compile_classifier,
    history_best_validation_metrics,
    subprocess_certifier,
)
from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX, NUM_CLASSES
from src.utils.experiment_artifacts import (
    PROJECT_ROOT,
    project_relative,
    resolve_path,
    sha256_file,
    utc_now,
    write_csv_atomic,
    write_json_atomic,
)

# Reuse the two-arm study's fixed data definitions so training, tuning, and the
# holdout mean exactly the same thing across both projects.
from scripts.two_arm_experiment import (
    DEFAULT_SQUARE_DATASET_DIRECTORY,
    DEFAULT_TUNING_GROUPS,
    class_counts,
    country_class_counts,
)


DEFAULT_EXPERIMENTS_DIRECTORY = Path("outputs/experiments")
INPUT_SHAPE = (224, 224, 3)


def _banner(title: str) -> str:
    """Return a prominent section header for verbose console output."""

    rule = "=" * 74
    return f"\n{rule}\n  {title}\n{rule}"


def _format_metric(value: float | None) -> str:
    """Format an optional metric for console output."""

    return "n/a" if value is None else f"{value:.4f}"


def print_environment(tf: Any, keras: Any, gpus: Sequence[Any]) -> None:
    """Print the runtime, accelerator, and precision configuration."""

    import os

    print(_banner("Environment"))
    print(f"  TensorFlow             : {tf.__version__}")
    print(f"  Keras                  : {keras.__version__}")
    print(
        "  Visible GPUs           : "
        f"{[device.name for device in gpus] or 'none (CPU only)'}"
    )
    try:
        precision_policy = keras.mixed_precision.global_policy().name
    except Exception:  # noqa: BLE001 - purely informational
        precision_policy = "unknown"
    print(f"  Mixed-precision policy : {precision_policy}")
    print(f"  Eager execution        : {tf.executing_eagerly()}")
    print(f"  CPU cores              : {os.cpu_count()}")


def print_data_selection(
    selection: Mapping[str, Sequence[CropRecord]],
    class_weights: Mapping[int, float],
) -> None:
    """Print per-role counts, a country/class training table, and weights."""

    print(_banner("Data selection"))
    for role, records in selection.items():
        counts = class_counts(records)
        detail = "  ".join(f"{label} {counts[label]:>6,}" for label in CLASS_NAMES)
        print(f"  {role:<24}{sum(counts.values()):>8,} crops    {detail}")

    print("\n  Training crops by country and class:")
    country_counts = country_class_counts(selection["eligible_train"])
    name_width = max((len(country) for country in country_counts), default=12)
    header = f"    {'country':<{name_width}}" + "".join(
        f"{column:>9}" for column in (*CLASS_NAMES, "total")
    )
    print(header)
    for country in sorted(country_counts):
        counts = country_counts[country]
        cells = "".join(f"{counts[label]:>9,}" for label in CLASS_NAMES)
        print(f"    {country:<{name_width}}{cells}{sum(counts.values()):>9,}")

    print("\n  Balanced class weights (by class index):")
    for label in CLASS_NAMES:
        index = CLASS_TO_INDEX[label]
        print(f"    {label} (index {index}): {class_weights[index]:.4f}")


def print_evaluation_report(title: str, evaluation: Mapping[str, Any]) -> None:
    """Print full aggregate metrics, per-class metrics, and the confusion matrix."""

    print(_banner(title))
    print(f"  examples          : {evaluation['number_of_examples']:,}")
    print(f"  accuracy          : {evaluation['accuracy']:.4f}")
    print(f"  balanced accuracy : {evaluation['balanced_accuracy']:.4f}")
    print(f"  macro F1          : {evaluation['macro_f1']:.4f}")
    print(f"  weighted F1       : {evaluation['weighted_f1']:.4f}")
    print(f"  loss              : {evaluation['loss']:.4f}")

    report = evaluation["classification_report"]
    print("\n  Per-class metrics:")
    print(
        f"    {'class':<8}{'precision':>11}{'recall':>9}"
        f"{'f1':>9}{'support':>9}"
    )
    for label in CLASS_NAMES:
        row = report[label]
        print(
            f"    {label:<8}{row['precision']:>11.4f}{row['recall']:>9.4f}"
            f"{row['f1-score']:>9.4f}{int(row['support']):>9,}"
        )

    print("\n  Confusion matrix (rows = true, columns = predicted):")
    print("    " + " " * 6 + "".join(f"{label:>8}" for label in CLASS_NAMES))
    for true_index, label in enumerate(CLASS_NAMES):
        cells = "".join(
            f"{int(count):>8,}"
            for count in evaluation["confusion_matrix"][true_index]
        )
        print(f"    {label:>6}{cells}")


def build_verbose_epoch_logger(
    stage_name: str,
    monitor: str,
    monitor_mode: str,
) -> Any:
    """Create a callback that prints rich per-epoch diagnostics.

    It reads the validation metrics the shared eager-validation callback injects
    into ``logs`` (val loss/accuracy, macro-F1, balanced accuracy, and per-class
    ``val_recall_*``), so no extra inference pass is needed. It tracks the
    ``monitor`` metric that early stopping uses and flags each new best, alongside
    the learning rate, epoch time, and the train/val losses.
    """

    from tensorflow import keras

    better = (lambda new, best: new < best - 1e-12) if monitor_mode == "min" else (
        lambda new, best: new > best + 1e-12
    )

    class _VerboseEpochLogger(keras.callbacks.Callback):
        def __init__(self) -> None:
            super().__init__()
            self._best_monitor: float | None = None
            self._epoch_start: float | None = None

        def on_epoch_begin(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
            self._epoch_start = time.perf_counter()

        def on_epoch_end(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
            logs = dict(logs or {})
            elapsed = time.perf_counter() - (self._epoch_start or time.perf_counter())

            monitored = logs.get(monitor)
            improved = monitored is not None and (
                self._best_monitor is None or better(monitored, self._best_monitor)
            )
            delta_text = ""
            if monitored is not None and self._best_monitor is not None:
                delta_text = f" (Δ {monitored - self._best_monitor:+.4f} vs best)"
            if improved:
                self._best_monitor = monitored
            marker = f"✓ new best {monitor}" if improved else "· no improvement"

            # logs["learning_rate"] is the rate used *this* epoch. The optimizer's
            # current rate is what the *next* epoch will use: ReduceLROnPlateau
            # runs before this callback and may have just lowered it at this
            # epoch's end. Show both when they differ so the "reducing learning
            # rate to ..." message is not misread as already in effect.
            try:
                next_learning_rate = float(self.model.optimizer.learning_rate)
            except Exception:  # noqa: BLE001 - purely informational
                next_learning_rate = None
            epoch_learning_rate = logs.get("learning_rate", next_learning_rate)
            if epoch_learning_rate is None:
                learning_rate_text = "n/a"
            elif next_learning_rate is not None and not math.isclose(
                epoch_learning_rate, next_learning_rate, rel_tol=1e-6
            ):
                learning_rate_text = (
                    f"{epoch_learning_rate:.2e} -> {next_learning_rate:.2e} "
                    "(reduced for next epoch)"
                )
            else:
                learning_rate_text = f"{epoch_learning_rate:.2e}"

            recall_line = "   ".join(
                f"{label} {_format_metric(logs.get(f'val_recall_{label}'))}"
                for label in CLASS_NAMES
            )
            print(f"\n  -- [{stage_name}] epoch {epoch + 1} - {elapsed:.1f}s --")
            print(
                f"     train  loss {_format_metric(logs.get('loss'))}"
                f"   acc {_format_metric(logs.get('accuracy'))}"
            )
            print(
                f"     val    loss {_format_metric(logs.get('val_loss'))}"
                f"   acc {_format_metric(logs.get('val_accuracy'))}"
                f"   {marker}{delta_text}"
            )
            print(f"     val recall    {recall_line}")
            print(
                f"     val macro-F1 {_format_metric(logs.get('val_macro_f1'))}"
                f"   balanced-acc {_format_metric(logs.get('val_balanced_accuracy'))}"
                f"   lr {learning_rate_text}"
            )

    return _VerboseEpochLogger()


def parse_arguments() -> argparse.Namespace:
    """Read two-stage transfer-learning settings."""

    parser = argparse.ArgumentParser(
        description=(
            "Train an EfficientNetV2-B1 road-damage classifier with a frozen "
            "head stage and a fine-tuning stage, using all countries."
        )
    )
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument(
        "--square-dataset-directory",
        type=Path,
        default=DEFAULT_SQUARE_DATASET_DIRECTORY,
        help="Published square-crop directory with manifest.csv and metadata.json.",
    )
    parser.add_argument(
        "--experiments-directory",
        type=Path,
        default=DEFAULT_EXPERIMENTS_DIRECTORY,
    )
    parser.add_argument(
        "--frozen-epochs",
        type=int,
        default=10,
        help="Maximum epochs for the frozen-backbone head stage.",
    )
    parser.add_argument(
        "--fine-tune-epochs",
        type=int,
        default=15,
        help="Maximum epochs for the end-to-end fine-tuning stage.",
    )
    parser.add_argument("--frozen-batch-size", type=int, default=32)
    parser.add_argument("--fine-tune-batch-size", type=int, default=16)
    parser.add_argument(
        "--eval-batch-size",
        type=int,
        default=32,
        help="Batch size for validation, certification, and evaluation.",
    )
    parser.add_argument("--frozen-learning-rate", type=float, default=1e-3)
    parser.add_argument("--fine-tune-learning-rate", type=float, default=1e-5)
    parser.add_argument("--dropout", type=float, default=0.30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument("--round-trip-tolerance", type=float, default=1e-5)
    parser.add_argument(
        "--loss",
        choices=("focal", "weighted_ce"),
        default="focal",
        help=(
            "Training loss. 'focal' (default) concentrates on hard minority "
            "examples with per-class alpha from the balanced weights; "
            "'weighted_ce' uses cross-entropy with class_weight."
        ),
    )
    parser.add_argument(
        "--focal-gamma",
        type=float,
        default=2.0,
        help="Focusing parameter for focal loss (0 reduces it to cross-entropy).",
    )
    parser.add_argument(
        "--checkpoint-metric",
        choices=("val_macro_f1", "val_balanced_accuracy", "val_loss"),
        default="val_macro_f1",
        help=(
            "Validation metric that drives checkpointing and early stopping. "
            "Macro-F1 (default) weights every class equally, unlike val_loss."
        ),
    )
    parser.add_argument(
        "--skip-fine-tune",
        action="store_true",
        help="Stop after the frozen head stage (no end-to-end fine-tuning).",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Permit training if TensorFlow cannot see a GPU.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run one epoch on two training batches per stage to check wiring.",
    )
    parser.add_argument(
        "--verbose",
        choices=(0, 1, 2),
        type=int,
        default=1,
    )

    args = parser.parse_args()

    for name, value in (
        ("--frozen-epochs", args.frozen_epochs),
        ("--fine-tune-epochs", args.fine_tune_epochs),
        ("--frozen-batch-size", args.frozen_batch_size),
        ("--fine-tune-batch-size", args.fine_tune_batch_size),
        ("--eval-batch-size", args.eval_batch_size),
        ("--early-stopping-patience", args.early_stopping_patience),
    ):
        if value <= 0:
            parser.error(f"{name} must be greater than zero")
    for name, value in (
        ("--frozen-learning-rate", args.frozen_learning_rate),
        ("--fine-tune-learning-rate", args.fine_tune_learning_rate),
        ("--round-trip-tolerance", args.round_trip_tolerance),
    ):
        if value <= 0:
            parser.error(f"{name} must be greater than zero")
    if not 0.0 <= args.dropout < 1.0:
        parser.error("--dropout must be in [0, 1)")
    if args.focal_gamma < 0:
        parser.error("--focal-gamma must be non-negative")

    return args


def select_training_records(
    records: Sequence[CropRecord],
) -> dict[str, list[CropRecord]]:
    """Split crops into the all-country train pool, U.S. tuning, and holdout.

    Training keeps every country (Norway and India included) and excludes only
    the fixed internal U.S. tuning groups, which are reserved for early
    stopping. The holdout is the untouched U.S. ``val`` split.
    """

    train_records = filter_crop_records(records, split="train")
    tune_records = filter_crop_records(
        train_records,
        include_countries="United_States",
        include_sequence_groups=DEFAULT_TUNING_GROUPS,
    )
    actual_groups = {record["sequence_group"] for record in tune_records}
    if actual_groups != set(DEFAULT_TUNING_GROUPS):
        raise RuntimeError(
            "The fixed internal U.S. tuning groups are absent or changed. "
            f"Expected={sorted(DEFAULT_TUNING_GROUPS)}, actual={sorted(actual_groups)}"
        )

    eligible_train = filter_crop_records(
        train_records,
        exclude_sequence_groups=DEFAULT_TUNING_GROUPS,
    )
    holdout_records = filter_crop_records(
        records,
        split="val",
        include_countries="United_States",
    )

    for name, subset in (
        ("all-country training", eligible_train),
        ("internal U.S. tuning", tune_records),
        ("U.S. holdout", holdout_records),
    ):
        if not subset:
            raise RuntimeError(f"The {name} selection is empty.")

    represented = {str(record["country"]) for record in eligible_train}
    missing = {"Norway", "India"} - represented
    if missing:
        raise RuntimeError(
            f"Training pool is missing required countries: {sorted(missing)}."
        )

    return {
        "eligible_train": eligible_train,
        "us_internal_tune": tune_records,
        "us_comparison_holdout": holdout_records,
    }


def class_weight_indices(records: Sequence[CropRecord]) -> dict[int, float]:
    """Balanced class weights keyed by integer class index."""

    weights_by_label = balanced_class_weights(class_counts(records))
    return {
        CLASS_TO_INDEX[label]: float(weights_by_label[label])
        for label in CLASS_NAMES
    }


def write_frozen_manifests(
    fieldnames: Sequence[str],
    selection: Mapping[str, Sequence[CropRecord]],
    manifests_directory: Path,
) -> dict[str, dict[str, str]]:
    """Freeze each record subset to its own CSV with a content hash."""

    manifests: dict[str, dict[str, str]] = {}
    for name, subset in selection.items():
        output_path = manifests_directory / f"{name}.csv"
        write_csv_atomic(output_path, list(fieldnames), subset)
        manifests[name] = {
            "path": project_relative(output_path),
            "sha256": sha256_file(output_path),
            "records": str(len(subset)),
        }
    return manifests


def make_dataset(
    records: Sequence[CropRecord],
    *,
    batch_size: int,
    shuffle: bool,
    seed: int,
    take_batches: int | None = None,
) -> Any:
    """Build a manifest-driven dataset, optionally limited to the first batches."""

    dataset = build_dataset_from_records(
        records,
        batch_size=batch_size,
        shuffle=shuffle,
        seed=seed,
    )
    if take_batches is not None:
        dataset = dataset.take(take_batches)
    return dataset


def fit_stage(
    model: Any,
    *,
    stage_name: str,
    train_records: Sequence[CropRecord],
    validation_dataset_factory,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    loss_name: str,
    focal_gamma: float,
    focal_alpha: Sequence[float] | None,
    class_weight_for_fit: Mapping[int, float] | None,
    monitor: str,
    monitor_mode: str,
    seed: int,
    checkpoint_path: Path,
    csv_log_path: Path,
    tensorboard_path: Path,
    early_stopping_patience: int,
    verbose: int,
    smoke_test: bool,
    extra_callbacks: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Compile and fit one transfer-learning stage, returning its history.

    Validation is owned by the eager-validation callback inside
    ``build_classifier_callbacks``, so no ``validation_data`` is passed: the
    monitored metric comes from the reliable eager path, and early stopping
    restores the best epoch's weights into ``model`` in place.
    ``class_weight_for_fit`` is passed to ``fit`` only for weighted-CE; focal
    loss handles imbalance through its alpha instead. ``extra_callbacks`` (e.g.
    the verbose logger) run after the built-in ones, so they see the fully
    populated ``logs``.
    """

    train_dataset = make_dataset(
        train_records,
        batch_size=batch_size,
        shuffle=True,
        seed=seed,
        take_batches=2 if smoke_test else None,
    )
    compile_classifier(
        model,
        learning_rate,
        loss_name=loss_name,
        focal_gamma=focal_gamma,
        focal_alpha=focal_alpha,
    )
    callbacks = build_classifier_callbacks(
        checkpoint_path=checkpoint_path,
        csv_log_path=csv_log_path,
        tensorboard_path=tensorboard_path,
        validation_dataset_factory=validation_dataset_factory,
        monitor=monitor,
        monitor_mode=monitor_mode,
        early_stopping_patience=early_stopping_patience,
        verbose=verbose,
    )
    if extra_callbacks:
        callbacks = [*callbacks, *extra_callbacks]

    max_epochs = 1 if smoke_test else epochs
    print(_banner(f"Stage: {stage_name}"))
    print(f"  training crops         : {len(train_records):,}")
    print(f"  batch size             : {batch_size}")
    print(f"  learning rate          : {learning_rate:g}")
    print(f"  loss                   : {loss_name}"
          + (f" (gamma={focal_gamma:g})" if loss_name == "focal" else ""))
    print(f"  monitor                : {monitor} ({monitor_mode})")
    print(f"  max epochs             : {max_epochs}")
    print(f"  early-stopping patience: {early_stopping_patience}")
    print(f"  checkpoint             : {project_relative(checkpoint_path)}")
    print(f"  epoch log (csv)        : {project_relative(csv_log_path)}", flush=True)

    fit_kwargs: dict[str, Any] = {}
    if class_weight_for_fit is not None:
        fit_kwargs["class_weight"] = dict(class_weight_for_fit)

    start_time = time.perf_counter()
    history = model.fit(
        train_dataset,
        epochs=max_epochs,
        callbacks=callbacks,
        shuffle=False,
        verbose=verbose,
        **fit_kwargs,
    )
    stage_seconds = time.perf_counter() - start_time

    history_values = {
        metric: [float(value) for value in values]
        for metric, values in history.history.items()
    }
    best_validation = history_best_validation_metrics(
        history_values, monitor=monitor, mode=monitor_mode
    )
    completed_epochs = len(history_values.get("loss", []))
    print(
        f"\n  [{stage_name}] finished: {completed_epochs} epoch(s) in "
        f"{stage_seconds:.1f}s; best epoch {best_validation['epoch']} "
        f"({monitor} {_format_metric(best_validation['value'])}, "
        f"val_accuracy {_format_metric(best_validation['accuracy'])}).",
        flush=True,
    )
    return {
        "history": history_values,
        "completed_epochs": completed_epochs,
        "history_best_validation": best_validation,
        "stage_seconds": stage_seconds,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
    }


def train_efficientnet(args: argparse.Namespace, experiment_directory: Path) -> None:
    """Run both training stages, certify the checkpoint, and evaluate it."""

    import tensorflow as tf
    from tensorflow import keras

    from src.evaluation.evaluate_classifier import evaluate_classifier_records
    from src.models.efficientnet_v2 import (
        build_efficientnet_v2_b1,
        count_trainable_parameters,
        unfreeze_backbone,
    )

    gpus = tf.config.list_physical_devices("GPU")
    if not gpus and not args.allow_cpu:
        raise RuntimeError(
            "TensorFlow cannot see a GPU. Fine-tuning EfficientNetV2 on CPU is "
            "very slow; rerun with --allow-cpu only if that is intentional."
        )

    print(_banner(f"EfficientNetV2-B1 transfer learning: {experiment_directory.name}"))
    print(f"  experiment directory   : {project_relative(experiment_directory)}")
    print_environment(tf, keras, gpus)

    square_directory = resolve_path(args.square_dataset_directory)
    manifest = load_crop_manifest(
        square_directory / "manifest.csv",
        crop_root=square_directory,
        require_existing_files=False,
    )
    selection = select_training_records(manifest.records)
    eligible_train = selection["eligible_train"]
    tune_records = selection["us_internal_tune"]
    holdout_records = selection["us_comparison_holdout"]

    manifests_directory = experiment_directory / "manifests"
    frozen_manifests = write_frozen_manifests(
        manifest.fieldnames,
        selection,
        manifests_directory,
    )
    class_weights = class_weight_indices(eligible_train)

    checkpoints_directory = experiment_directory / "checkpoints"
    logs_directory = experiment_directory / "logs"
    certification_directory = experiment_directory / "certification"
    for directory in (checkpoints_directory, logs_directory, certification_directory):
        directory.mkdir(parents=True, exist_ok=True)

    eval_batch_size = args.eval_batch_size
    smoke_test = args.smoke_test

    monitor = args.checkpoint_metric
    monitor_mode = "min" if monitor == "val_loss" else "max"
    # Focal loss carries the imbalance in its per-class alpha, so it must not
    # also be class-weighted in fit(); weighted-CE keeps the class_weight path.
    if args.loss == "focal":
        focal_alpha: list[float] | None = [
            class_weights[index] for index in range(NUM_CLASSES)
        ]
        class_weight_for_fit: dict[int, float] | None = None
    else:
        focal_alpha = None
        class_weight_for_fit = class_weights

    def tuning_dataset_factory():
        return make_dataset(
            tune_records,
            batch_size=eval_batch_size,
            shuffle=False,
            seed=args.seed,
            take_batches=1 if smoke_test else None,
        )

    config = {
        "created_at_utc": utc_now(),
        "project_root": PROJECT_ROOT.as_posix(),
        "experiment_id": experiment_directory.name,
        "model": "efficientnet_v2_b1",
        "backbone_weights": "imagenet",
        "input_shape": list(INPUT_SHAPE),
        "training_countries": "all_countries_including_norway_and_india",
        "arguments": {
            "frozen_epochs": args.frozen_epochs,
            "fine_tune_epochs": args.fine_tune_epochs,
            "frozen_batch_size": args.frozen_batch_size,
            "fine_tune_batch_size": args.fine_tune_batch_size,
            "eval_batch_size": args.eval_batch_size,
            "frozen_learning_rate": args.frozen_learning_rate,
            "fine_tune_learning_rate": args.fine_tune_learning_rate,
            "dropout": args.dropout,
            "seed": args.seed,
            "early_stopping_patience": args.early_stopping_patience,
            "round_trip_tolerance": args.round_trip_tolerance,
            "loss": args.loss,
            "focal_gamma": args.focal_gamma,
            "checkpoint_metric": args.checkpoint_metric,
            "skip_fine_tune": args.skip_fine_tune,
            "smoke_test": smoke_test,
        },
        "square_dataset": {
            "directory": project_relative(square_directory),
            "manifest_sha256": sha256_file(square_directory / "manifest.csv"),
        },
        "class_weights_by_index": class_weights,
        "counts": {
            "eligible_train": class_counts(eligible_train),
            "us_internal_tune": class_counts(tune_records),
            "us_comparison_holdout": class_counts(holdout_records),
        },
        "training_country_class_counts": country_class_counts(eligible_train),
        "manifests": frozen_manifests,
    }
    write_json_atomic(experiment_directory / "config.json", config)
    print_data_selection(selection, class_weights)

    keras.utils.set_random_seed(args.seed)
    model, backbone = build_efficientnet_v2_b1(
        input_shape=INPUT_SHAPE,
        dropout_rate=args.dropout,
    )
    print(_banner("Model architecture"))
    model.summary(show_trainable=True, expand_nested=False)
    print(
        f"\n  backbone params        : {backbone.count_params():,}"
        f"\n  trainable params (head): {count_trainable_parameters(model):,}"
        f"\n  total params           : {model.count_params():,}",
        flush=True,
    )

    stages: dict[str, Any] = {}
    stages["frozen_head"] = fit_stage(
        model,
        stage_name="frozen_head",
        train_records=eligible_train,
        validation_dataset_factory=tuning_dataset_factory,
        batch_size=args.frozen_batch_size,
        epochs=args.frozen_epochs,
        learning_rate=args.frozen_learning_rate,
        loss_name=args.loss,
        focal_gamma=args.focal_gamma,
        focal_alpha=focal_alpha,
        class_weight_for_fit=class_weight_for_fit,
        monitor=monitor,
        monitor_mode=monitor_mode,
        seed=args.seed,
        checkpoint_path=checkpoints_directory / "stage1_frozen_best.keras",
        csv_log_path=logs_directory / "stage1_frozen.csv",
        tensorboard_path=logs_directory / "tensorboard_stage1",
        early_stopping_patience=args.early_stopping_patience,
        verbose=args.verbose,
        smoke_test=smoke_test,
        extra_callbacks=[
            build_verbose_epoch_logger("frozen_head", monitor, monitor_mode)
        ],
    )
    stages["frozen_head"]["trainable_parameters"] = count_trainable_parameters(
        model
    )

    if not args.skip_fine_tune:
        unfrozen_layers = unfreeze_backbone(backbone)
        print(
            f"\n  Unfroze backbone for fine-tuning: {unfrozen_layers} layers now "
            f"trainable ({count_trainable_parameters(model):,} params; "
            "BatchNorm kept frozen).",
            flush=True,
        )
        stages["fine_tune"] = fit_stage(
            model,
            stage_name="fine_tune",
            train_records=eligible_train,
            validation_dataset_factory=tuning_dataset_factory,
            batch_size=args.fine_tune_batch_size,
            epochs=args.fine_tune_epochs,
            learning_rate=args.fine_tune_learning_rate,
            loss_name=args.loss,
            focal_gamma=args.focal_gamma,
            focal_alpha=focal_alpha,
            class_weight_for_fit=class_weight_for_fit,
            monitor=monitor,
            monitor_mode=monitor_mode,
            seed=args.seed,
            checkpoint_path=checkpoints_directory / "stage2_finetune_best.keras",
            csv_log_path=logs_directory / "stage2_finetune.csv",
            tensorboard_path=logs_directory / "tensorboard_stage2",
            early_stopping_patience=args.early_stopping_patience,
            verbose=args.verbose,
            smoke_test=smoke_test,
            extra_callbacks=[
                build_verbose_epoch_logger("fine_tune", monitor, monitor_mode)
            ],
        )
        stages["fine_tune"]["unfrozen_backbone_layers"] = unfrozen_layers
        stages["fine_tune"]["trainable_parameters"] = (
            count_trainable_parameters(model)
        )

    # Certify the final in-memory model in a genuinely fresh Python process,
    # re-measuring the internal tuning set from its frozen manifest.
    restored_checkpoint_path = checkpoints_directory / "restored.keras"
    certification = SubprocessCertification(
        log_path=certification_directory / "certification.log",
        output_path=certification_directory / "fresh_process_metrics.json",
        manifest_path=resolve_path(
            frozen_manifests["us_internal_tune"]["path"]
        ),
        crop_root=square_directory,
        batch_size=eval_batch_size,
        seed=args.seed,
        limit_batches=1 if smoke_test else None,
    )
    reloaded_model, evidence = certify_saved_classifier(
        model,
        restored_checkpoint_path=restored_checkpoint_path,
        validation_dataset_factory=tuning_dataset_factory,
        tolerance=args.round_trip_tolerance,
        fresh_evaluator=subprocess_certifier(certification),
    )
    round_trip = dict(evidence["comparison"])

    training_metrics: dict[str, Any] = {
        "status": "round_trip_failed" if not round_trip["passed"] else "running",
        "model": "efficientnet_v2_b1",
        "stages": stages,
        "in_memory_internal_tune": dict(evidence["in_memory"]),
        "fresh_process_internal_tune": dict(evidence["reloaded"]),
        "round_trip_check": round_trip,
        "certification": {
            "mechanism": "fresh_python_subprocess_eager_inference",
            "fresh_process_metrics": project_relative(certification.output_path),
            "log": project_relative(certification.log_path),
        },
        "restored_checkpoint": project_relative(restored_checkpoint_path),
        "class_weights_by_index": class_weights,
        "tensorflow_version": tf.__version__,
        "gpu_devices": [device.name for device in gpus],
        "smoke_test": smoke_test,
    }
    training_metrics_path = experiment_directory / "training_metrics.json"
    write_json_atomic(training_metrics_path, training_metrics)

    if not round_trip["passed"]:
        raise RuntimeError(
            "Fresh-process certification disagreed with the in-memory model. "
            f"See {training_metrics_path}."
        )

    # Smoke mode fits and certifies on the first deterministic tuning batch, so
    # its independent evaluation must use that same subset.
    tune_evaluation_records = (
        tune_records[: eval_batch_size] if smoke_test else tune_records
    )
    tune_evaluation = evaluate_classifier_records(
        model=reloaded_model,
        dataset=make_dataset(
            tune_evaluation_records,
            batch_size=eval_batch_size,
            shuffle=False,
            seed=args.seed,
        ),
        records=tune_evaluation_records,
        output_directory=experiment_directory / "internal_tune_evaluation",
        split="train_internal_tune",
        batch_size=eval_batch_size,
        role="internal_tune",
        checkpoint_path=restored_checkpoint_path,
        title="Internal Tune — EfficientNetV2-B1",
    )
    fresh_tune_check = compare_metric_sets(
        dict(evidence["reloaded"]),
        {
            "loss": float(tune_evaluation["loss"]),
            "accuracy": float(tune_evaluation["accuracy"]),
        },
        tolerance=args.round_trip_tolerance,
    )
    training_metrics["fresh_reloaded_internal_tune_check"] = fresh_tune_check
    training_metrics["status"] = (
        "fresh_tune_check_failed"
        if not fresh_tune_check["passed"]
        else "round_trip_verified"
    )
    write_json_atomic(training_metrics_path, training_metrics)
    if not fresh_tune_check["passed"]:
        raise RuntimeError(
            "In-process tuning evaluation disagreed with the fresh-process "
            f"certification. See {training_metrics_path}."
        )
    print_evaluation_report(
        "Internal U.S. tuning evaluation (saved model)", tune_evaluation
    )

    holdout_evaluation_records = (
        holdout_records[: eval_batch_size] if smoke_test else holdout_records
    )
    holdout_evaluation = evaluate_classifier_records(
        model=reloaded_model,
        dataset=make_dataset(
            holdout_evaluation_records,
            batch_size=eval_batch_size,
            shuffle=False,
            seed=args.seed,
        ),
        records=holdout_evaluation_records,
        output_directory=experiment_directory / "us_holdout_evaluation",
        split="val",
        batch_size=eval_batch_size,
        role="us_holdout",
        checkpoint_path=restored_checkpoint_path,
        title="U.S. Holdout — EfficientNetV2-B1",
    )

    training_metrics["status"] = "completed"
    write_json_atomic(training_metrics_path, training_metrics)

    completion = {
        "status": "completed",
        "completed_at_utc": utc_now(),
        "model": "efficientnet_v2_b1",
        "round_trip_check": round_trip,
        "fresh_reloaded_internal_tune_check": fresh_tune_check,
        "restored_checkpoint": project_relative(restored_checkpoint_path),
        "training_metrics_path": project_relative(training_metrics_path),
        "internal_tune_metrics_path": tune_evaluation["metrics_path"],
        "us_holdout_metrics_path": holdout_evaluation["metrics_path"],
        "us_holdout_predictions_path": holdout_evaluation["predictions_path"],
    }
    write_json_atomic(experiment_directory / "completion.json", completion)

    print_evaluation_report(
        "U.S. holdout evaluation (saved model)", holdout_evaluation
    )
    keras.backend.clear_session()

    print(_banner("EfficientNetV2-B1 training completed"))
    print(f"  experiment directory : {project_relative(experiment_directory)}")
    print(f"  restored checkpoint  : {project_relative(restored_checkpoint_path)}")
    print(f"  holdout metrics      : {holdout_evaluation['metrics_path']}")
    print(
        f"  headline: accuracy {holdout_evaluation['accuracy']:.4f} | "
        f"balanced {holdout_evaluation['balanced_accuracy']:.4f} | "
        f"macro-F1 {holdout_evaluation['macro_f1']:.4f}",
        flush=True,
    )


def main() -> None:
    """Create the experiment directory and run the transfer-learning trainer."""

    import os

    args = parse_arguments()
    os.chdir(PROJECT_ROOT)

    experiment_id = args.experiment_id or (
        "efficientnet_v2_b1_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    experiment_directory = resolve_path(args.experiments_directory) / experiment_id
    if experiment_directory.exists():
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_directory}. "
            "Choose a new --experiment-id."
        )
    experiment_directory.mkdir(parents=True)

    try:
        train_efficientnet(args, experiment_directory)
    except Exception as error:
        write_json_atomic(
            experiment_directory / "failure.json",
            {
                "status": "failed",
                "failed_at_utc": utc_now(),
                "error": str(error),
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    main()

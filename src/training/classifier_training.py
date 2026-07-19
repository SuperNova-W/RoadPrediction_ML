"""Reusable TensorFlow classifier training and certification primitives.

CLI entry points decide which records, experiment folders, and policies to use.
This module owns the mechanics that must remain identical across those runs:
compilation, callbacks, balanced weights, history inspection, and certification
of the saved checkpoint.

Two properties matter for trustworthy results and are enforced here:

* The monitored validation loss is computed through the eager inference path
  (:func:`~src.evaluation.classifier_runtime.evaluate_eager_dataset`) rather
  than ``model.evaluate``'s compiled metrics, so early stopping, checkpointing,
  and the LR scheduler select epochs from numbers a redeployed model
  reproduces.
* Certification re-evaluates the saved checkpoint through a caller-supplied
  ``fresh_evaluator``. Production callers launch a genuinely fresh Python
  process (see :func:`subprocess_certifier`) so no compiled-metric or session
  state can leak from training into the measurement.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from tensorflow import keras

from src.evaluation.classifier_runtime import evaluate_eager_dataset
from src.utils.experiment_artifacts import read_json_object, run_logged_command


ClassKey = TypeVar("ClassKey", str, int)
DatasetFactory = Callable[[], Any]
ModelFactory = Callable[[], Any]
# A certifier maps a saved checkpoint path to its {"loss", "accuracy"} metrics.
FreshEvaluator = Callable[[Path], dict[str, float]]


@dataclass(frozen=True)
class CertifiedTrainingResult:
    """Outputs from one shared fit and model round-trip certification."""

    reloaded_model: Any
    history_values: dict[str, list[float]]
    history_best_validation: dict[str, int | float | None]
    training_seconds: float
    in_memory_metrics: dict[str, float]
    reloaded_metrics: dict[str, float]
    round_trip_check: dict[str, float | bool]


def compile_classifier(
    model: keras.Model,
    learning_rate: float,
    *,
    loss_name: str = "weighted_ce",
    focal_gamma: float = 2.0,
    focal_alpha: Sequence[float] | None = None,
) -> None:
    """Compile a logits classifier with the project's standard objective.

    ``loss_name="weighted_ce"`` (default) uses sparse categorical cross-entropy,
    paired with ``fit(class_weight=...)`` for imbalance. ``loss_name="focal"``
    uses sparse categorical focal loss with optional per-class ``focal_alpha``;
    when focal is used the caller should not also pass ``class_weight`` to ``fit``.
    """

    from tensorflow import keras

    if learning_rate <= 0:
        raise ValueError("learning_rate must be greater than zero")

    if loss_name == "weighted_ce":
        loss = keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    elif loss_name == "focal":
        from src.training.focal_loss import SparseCategoricalFocalLoss

        loss = SparseCategoricalFocalLoss(
            gamma=focal_gamma,
            alpha=focal_alpha,
            from_logits=True,
        )
    else:
        raise ValueError(
            f"Unknown loss_name {loss_name!r}; expected 'weighted_ce' or 'focal'."
        )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss=loss,
        metrics=[keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )


def compare_metric_sets(
    first: Mapping[str, float],
    second: Mapping[str, float],
    tolerance: float,
) -> dict[str, float | bool]:
    """Compare deterministic loss/accuracy measurements within a tolerance."""

    if tolerance <= 0:
        raise ValueError("tolerance must be greater than zero")

    for metric_name in ("loss", "accuracy"):
        if metric_name not in first or metric_name not in second:
            raise ValueError(
                "Both metric sets must contain loss and accuracy. "
                f"Missing {metric_name!r}."
            )

    loss_difference = abs(float(first["loss"]) - float(second["loss"]))
    accuracy_difference = abs(
        float(first["accuracy"]) - float(second["accuracy"])
    )
    return {
        "tolerance": tolerance,
        "loss_absolute_difference": loss_difference,
        "accuracy_absolute_difference": accuracy_difference,
        "passed": (
            loss_difference <= tolerance
            and accuracy_difference <= tolerance
        ),
    }


def history_best_validation_metrics(
    history_values: Mapping[str, list[float]],
    *,
    monitor: str = "val_loss",
    mode: str = "min",
) -> dict[str, int | float | str | None]:
    """Return validation metrics from the best epoch for the monitored metric.

    The best epoch is chosen by ``monitor`` (``mode="min"`` or ``"max"``), which
    must match what the checkpoint/early-stopping callbacks monitor. ``loss`` and
    ``accuracy`` report ``val_loss``/``val_accuracy`` at that epoch regardless of
    which metric was monitored, and ``value`` is the monitored metric itself.
    """

    if mode not in ("min", "max"):
        raise ValueError("mode must be 'min' or 'max'")

    monitored = history_values.get(monitor, [])
    if not monitored:
        return {
            "epoch": None,
            "monitor": monitor,
            "value": None,
            "loss": None,
            "accuracy": None,
        }

    choose = min if mode == "min" else max
    best_epoch_index = monitored.index(choose(monitored))

    def value_at(metric_name: str) -> float | None:
        series = history_values.get(metric_name, [])
        return (
            float(series[best_epoch_index])
            if best_epoch_index < len(series)
            else None
        )

    return {
        "epoch": best_epoch_index + 1,
        "monitor": monitor,
        "value": float(monitored[best_epoch_index]),
        "loss": value_at("val_loss"),
        "accuracy": value_at("val_accuracy"),
    }


def balanced_class_weights(
    counts: Mapping[ClassKey, int],
) -> dict[ClassKey, float]:
    """Calculate scikit-learn-style balanced weights from fixed class counts."""

    if not counts:
        raise ValueError("Class counts must not be empty")
    normalized_counts = {label: int(count) for label, count in counts.items()}
    if any(count <= 0 for count in normalized_counts.values()):
        raise ValueError(
            f"Every class needs at least one training example: {normalized_counts}"
        )

    total_examples = sum(normalized_counts.values())
    number_of_classes = len(normalized_counts)
    return {
        label: total_examples / (number_of_classes * count)
        for label, count in normalized_counts.items()
    }


def eager_validation_callback(
    validation_dataset_factory: DatasetFactory,
) -> keras.callbacks.Callback:
    """Recompute ``val_loss``/``val_accuracy`` through the eager inference path.

    ``model.fit``'s built-in validation reports compiled metrics that can drift
    from a plain ``model(x, training=False)`` forward pass on some accelerators.
    Because early stopping, checkpointing, and the LR scheduler all monitor
    ``val_loss``, they must see the same eager numbers a freshly reloaded model
    produces. This callback evaluates the validation set eagerly at each epoch
    end and writes the results into ``logs`` before those monitoring callbacks
    run, which is why it must be listed first.
    """

    from tensorflow import keras

    from src.evaluation.classifier_metrics import compute_classification_metrics
    from src.evaluation.classifier_runtime import evaluate_eager_predictions
    from src.utils.classes import CLASS_NAMES

    class _EagerValidationMetrics(keras.callbacks.Callback):
        def __init__(self, factory: DatasetFactory) -> None:
            super().__init__()
            self._factory = factory

        def on_epoch_end(
            self,
            epoch: int,
            logs: dict[str, float] | None = None,
        ) -> None:
            if logs is None:
                return
            outcome = evaluate_eager_predictions(self.model, self._factory())
            metrics = compute_classification_metrics(
                outcome["true_labels"],
                outcome["predicted_labels"],
                loss=outcome["loss"],
            )
            report = metrics["classification_report"]
            logs["val_loss"] = metrics["loss"]
            logs["val_accuracy"] = metrics["accuracy"]
            logs["val_macro_f1"] = metrics["macro_f1"]
            logs["val_balanced_accuracy"] = metrics["balanced_accuracy"]
            for label in CLASS_NAMES:
                logs[f"val_recall_{label}"] = float(report[label]["recall"])

    return _EagerValidationMetrics(validation_dataset_factory)


def build_classifier_callbacks(
    *,
    checkpoint_path: Path,
    csv_log_path: Path,
    tensorboard_path: Path,
    validation_dataset_factory: DatasetFactory,
    monitor: str = "val_loss",
    monitor_mode: str = "min",
    early_stopping_patience: int = 5,
    reduce_lr_patience: int = 2,
    verbose: int = 1,
) -> list[keras.callbacks.Callback]:
    """Create the shared eager-validation, checkpoint, scheduling, and logging
    callbacks.

    The eager-validation callback is intentionally first so the ``monitor`` below
    reads the reliable eager metrics it injects (``val_loss``, ``val_accuracy``,
    ``val_macro_f1``, ``val_balanced_accuracy``, per-class ``val_recall_*``) rather
    than the compiled metrics ``model.fit`` would otherwise leave in ``logs``.
    ``monitor``/``monitor_mode`` select which of those drives checkpointing, early
    stopping, and the LR scheduler.
    """

    from tensorflow import keras

    if monitor_mode not in ("min", "max"):
        raise ValueError("monitor_mode must be 'min' or 'max'")
    if early_stopping_patience <= 0:
        raise ValueError("early_stopping_patience must be greater than zero")
    if reduce_lr_patience <= 0:
        raise ValueError("reduce_lr_patience must be greater than zero")

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    csv_log_path.parent.mkdir(parents=True, exist_ok=True)
    tensorboard_path.parent.mkdir(parents=True, exist_ok=True)

    return [
        eager_validation_callback(validation_dataset_factory),
        keras.callbacks.ModelCheckpoint(
            filepath=checkpoint_path,
            monitor=monitor,
            mode=monitor_mode,
            save_best_only=True,
            verbose=verbose,
        ),
        keras.callbacks.EarlyStopping(
            monitor=monitor,
            mode=monitor_mode,
            patience=early_stopping_patience,
            restore_best_weights=True,
            verbose=verbose,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor=monitor,
            mode=monitor_mode,
            factor=0.5,
            patience=reduce_lr_patience,
            min_lr=1e-6,
            verbose=verbose,
        ),
        keras.callbacks.TensorBoard(
            log_dir=tensorboard_path,
            histogram_freq=0,
        ),
        keras.callbacks.CSVLogger(csv_log_path),
        keras.callbacks.TerminateOnNaN(),
    ]


@dataclass(frozen=True)
class SubprocessCertification:
    """Everything a fresh Python process needs to re-evaluate a checkpoint.

    Provide either a ``manifest_path`` (plus its ``crop_root``) or a legacy
    directory ``split``. ``limit_batches`` mirrors a smoke-test
    ``dataset.take(n)`` so the in-process and fresh-process measurements cover
    the exact same crops. Metrics are always computed through the eager path.
    """

    log_path: Path
    output_path: Path
    manifest_path: Path | None = None
    crop_root: Path | None = None
    split: str | None = None
    batch_size: int = 32
    seed: int = 42
    limit_batches: int | None = None
    python_executable: str = field(default_factory=lambda: sys.executable)

    def __post_init__(self) -> None:
        if (self.manifest_path is None) == (self.split is None):
            raise ValueError(
                "Provide exactly one of manifest_path or split for certification."
            )
        if self.split is not None and self.crop_root is not None:
            raise ValueError("crop_root only applies to manifest certification.")

    def command(self, checkpoint_path: Path) -> list[str]:
        """Build the ``scripts.certify_checkpoint`` command for a checkpoint."""

        command = [
            self.python_executable,
            "-m",
            "scripts.certify_checkpoint",
            "--checkpoint",
            str(checkpoint_path),
            "--output",
            str(self.output_path),
            "--batch-size",
            str(self.batch_size),
            "--seed",
            str(self.seed),
        ]
        if self.manifest_path is not None:
            command += ["--manifest", str(self.manifest_path)]
            if self.crop_root is not None:
                command += ["--crop-root", str(self.crop_root)]
        else:
            command += ["--split", str(self.split)]
        if self.limit_batches is not None:
            command += ["--limit-batches", str(self.limit_batches)]
        return command


def run_subprocess_certification(
    checkpoint_path: Path,
    certification: SubprocessCertification,
) -> dict[str, float]:
    """Re-evaluate a saved checkpoint in a genuinely fresh Python process.

    A separate interpreter guarantees no compiled-metric or session state leaks
    from training into the measurement, so the reported loss and accuracy are
    what a redeployed model produces.
    """

    run_subprocess = run_logged_command(
        certification.command(checkpoint_path),
        certification.log_path,
    )
    del run_subprocess  # run_logged_command raises on a non-zero exit code.
    metrics = read_json_object(certification.output_path)
    for name in ("loss", "accuracy"):
        if name not in metrics:
            raise RuntimeError(
                "Fresh-process certification did not report "
                f"{name!r}: {certification.output_path}"
            )
    return {"loss": float(metrics["loss"]), "accuracy": float(metrics["accuracy"])}


def subprocess_certifier(
    certification: SubprocessCertification,
) -> FreshEvaluator:
    """Return a fresh-process certifier bound to a certification description."""

    def certify(checkpoint_path: Path) -> dict[str, float]:
        return run_subprocess_certification(checkpoint_path, certification)

    return certify


def _in_process_reload_certifier(
    validation_dataset_factory: DatasetFactory,
) -> FreshEvaluator:
    """Fallback certifier that reloads and evaluates eagerly in this process.

    Callers without a manifest to hand a subprocess (the legacy directory
    trainer) use this. It still exercises serialization and the reliable eager
    path, but a caller that can spawn a subprocess should prefer
    :func:`subprocess_certifier` for a genuinely fresh runtime.
    """

    def certify(checkpoint_path: Path) -> dict[str, float]:
        from tensorflow import keras

        keras.backend.clear_session()
        reloaded_model = keras.models.load_model(
            checkpoint_path,
            compile=False,
        )
        return evaluate_eager_dataset(
            reloaded_model,
            validation_dataset_factory(),
        )

    return certify


def certify_saved_classifier(
    model: keras.Model,
    *,
    restored_checkpoint_path: Path,
    validation_dataset_factory: DatasetFactory,
    tolerance: float,
    fresh_evaluator: FreshEvaluator,
) -> tuple[keras.Model, dict[str, Any]]:
    """Save the best weights, then certify them against a fresh evaluation.

    The in-memory metrics use the eager path on the just-trained model; the
    ``fresh_evaluator`` re-measures the saved checkpoint from disk (in a fresh
    process for production callers). Both paths are eager, so a healthy model
    reproduces its numbers and the comparison is no longer a tautology of the
    compiled metric state. The returned model is reloaded from disk for the
    downstream artifact evaluations.
    """

    from tensorflow import keras

    in_memory_metrics = evaluate_eager_dataset(
        model,
        validation_dataset_factory(),
    )
    restored_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(restored_checkpoint_path)

    fresh_metrics = fresh_evaluator(restored_checkpoint_path)
    comparison = compare_metric_sets(
        in_memory_metrics,
        fresh_metrics,
        tolerance,
    )

    keras.backend.clear_session()
    reloaded_model = keras.models.load_model(
        restored_checkpoint_path,
        compile=False,
    )
    return reloaded_model, {
        "in_memory": in_memory_metrics,
        "reloaded": fresh_metrics,
        "comparison": comparison,
    }


def fit_and_certify_classifier(
    *,
    model_factory: ModelFactory,
    train_dataset: Any,
    validation_dataset_factory: DatasetFactory,
    epochs: int,
    class_weights: Mapping[int, float],
    learning_rate: float,
    seed: int,
    best_checkpoint_path: Path,
    restored_checkpoint_path: Path,
    csv_log_path: Path,
    tensorboard_path: Path,
    tolerance: float,
    fresh_evaluator: FreshEvaluator | None = None,
    monitor: str = "val_loss",
    monitor_mode: str = "min",
    early_stopping_patience: int = 5,
    reduce_lr_patience: int = 2,
    verbose: int = 1,
) -> CertifiedTrainingResult:
    """Fit once, restore the best epoch, then certify the saved model.

    Validation is monitored through the eager inference path so the restored
    epoch is selected from reliable numbers. Certification re-measures the saved
    checkpoint with ``fresh_evaluator``; production callers pass
    :func:`subprocess_certifier` for a genuinely fresh runtime, and the default
    reloads and evaluates eagerly in this process.

    Both command-line trainers use this exact orchestration so callback,
    serialization, and certification semantics cannot drift between them.
    """

    from tensorflow import keras

    if epochs <= 0:
        raise ValueError("epochs must be greater than zero")

    if fresh_evaluator is None:
        fresh_evaluator = _in_process_reload_certifier(
            validation_dataset_factory
        )

    keras.utils.set_random_seed(seed)
    model = model_factory()
    compile_classifier(model, learning_rate)
    callbacks = build_classifier_callbacks(
        checkpoint_path=best_checkpoint_path,
        csv_log_path=csv_log_path,
        tensorboard_path=tensorboard_path,
        validation_dataset_factory=validation_dataset_factory,
        monitor=monitor,
        monitor_mode=monitor_mode,
        early_stopping_patience=early_stopping_patience,
        reduce_lr_patience=reduce_lr_patience,
        verbose=verbose,
    )

    start_time = time.perf_counter()
    # Validation is owned by the eager-validation callback (first in the list),
    # so model.fit intentionally receives no validation_data: its compiled
    # validation path is exactly what we are avoiding.
    history = model.fit(
        train_dataset,
        epochs=epochs,
        class_weight=dict(class_weights),
        callbacks=callbacks,
        shuffle=False,
        verbose=verbose,
    )
    training_seconds = time.perf_counter() - start_time

    reloaded_model, evidence = certify_saved_classifier(
        model,
        restored_checkpoint_path=restored_checkpoint_path,
        validation_dataset_factory=validation_dataset_factory,
        tolerance=tolerance,
        fresh_evaluator=fresh_evaluator,
    )
    history_values = {
        metric: [float(value) for value in values]
        for metric, values in history.history.items()
    }
    return CertifiedTrainingResult(
        reloaded_model=reloaded_model,
        history_values=history_values,
        history_best_validation=history_best_validation_metrics(
            history_values,
            monitor=monitor,
            mode=monitor_mode,
        ),
        training_seconds=training_seconds,
        in_memory_metrics=dict(evidence["in_memory"]),
        reloaded_metrics=dict(evidence["reloaded"]),
        round_trip_check=dict(evidence["comparison"]),
    )

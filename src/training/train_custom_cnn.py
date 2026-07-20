"""Train the custom TensorFlow CNN damage classifier."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import tensorflow as tf

from src.datasets.classification_dataset import load_split
from src.models.custom_cnn import build_custom_cnn
from src.utils.classes import CLASS_TO_INDEX
from src.utils.experiment_artifacts import write_json_atomic
from src.training.classifier_training import (
    CertifiedTrainingResult,
    balanced_class_weights,
    fit_and_certify_classifier,
)


TRAIN_SPLIT_PATH = Path("data/splits/train.csv")
CHECKPOINT_DIRECTORY = Path("outputs/checkpoints")
LOG_DIRECTORY = Path("outputs/logs")
METRICS_DIRECTORY = Path("outputs/metrics")
DEFAULT_ROUND_TRIP_TOLERANCE = 1e-5


def parse_arguments() -> argparse.Namespace:
    """Read training options from the command line."""

    parser = argparse.ArgumentParser(
        description="Train the custom road-damage CNN."
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--verbose",
        type=int,
        choices=(0, 1, 2),
        default=1,
        help=(
            "Keras output mode: 0=silent, "
            "1=live progress bar, 2=one line per epoch."
        ),
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Train on two batches for one epoch.",
    )
    parser.add_argument(
        "--round-trip-tolerance",
        type=float,
        default=DEFAULT_ROUND_TRIP_TOLERANCE,
        help=(
            "Maximum allowed absolute difference between in-memory and "
            "reloaded validation loss and accuracy."
        ),
    )

    args = parser.parse_args()

    if args.epochs <= 0:
        parser.error("--epochs must be greater than zero")
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.learning_rate <= 0:
        parser.error("--learning-rate must be greater than zero")
    if args.round_trip_tolerance <= 0:
        parser.error(
            "--round-trip-tolerance must be greater than zero"
        )

    return args


def build_validation_dataset(
    batch_size: int,
    smoke_test: bool,
) -> tf.data.Dataset:
    """Build the deterministic validation dataset used by every check."""

    validation_dataset = load_split(
        split="val",
        batch_size=batch_size,
        shuffle=False,
    )

    if smoke_test:
        # Match the one validation batch used during the smoke-test fit call.
        return validation_dataset.take(1)

    return validation_dataset


def calculate_class_weights() -> dict[int, float]:
    """Balance classes using counts from the training split only."""

    if not TRAIN_SPLIT_PATH.is_file():
        raise FileNotFoundError(
            f"Training split not found: {TRAIN_SPLIT_PATH}"
        )

    label_counts = {label: 0 for label in CLASS_TO_INDEX}

    with TRAIN_SPLIT_PATH.open(
        newline="",
        encoding="utf-8",
    ) as csv_file:
        for row in csv.DictReader(csv_file):
            for label in CLASS_TO_INDEX:
                label_counts[label] += int(row[f"{label}_count"])

    weights_by_label = balanced_class_weights(label_counts)
    return {
        CLASS_TO_INDEX[label]: weight
        for label, weight in weights_by_label.items()
    }


def save_experiment_results(
    run_name: str,
    args: argparse.Namespace,
    class_weights: dict[int, float],
    training_result: CertifiedTrainingResult,
    restored_model_path: Path,
) -> None:
    """Save configuration, history, and model round-trip evidence as JSON."""

    METRICS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    history_values = training_result.history_values
    history_best = training_result.history_best_validation

    gpu_names = [
        device.name
        for device in tf.config.list_physical_devices("GPU")
    ]

    results = {
        "run_name": run_name,
        "model_name": "custom_damage_cnn",
        "dataset_split_version": "sequence_blocks_100_seed_42",
        "input_size": [224, 224, 3],
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "optimizer": "Adam",
        "weight_decay": 0.0,
        "scheduler": "ReduceLROnPlateau",
        "requested_epochs": 1 if args.smoke_test else args.epochs,
        "completed_epochs": len(history_values.get("loss", [])),
        "augmentations": [
            "horizontal_flip",
            "translation_5_percent",
            "zoom_10_percent",
            "contrast_15_percent",
        ],
        "random_seed": args.seed,
        "class_weights": class_weights,
        "best_epoch": history_best["epoch"],
        "best_validation_loss": history_best["loss"],
        "history_best_validation": history_best,
        "in_memory_validation": training_result.in_memory_metrics,
        "reloaded_validation": training_result.reloaded_metrics,
        "validation_scope": (
            "first_validation_batch"
            if args.smoke_test
            else "full_validation_split"
        ),
        "round_trip_check": training_result.round_trip_check,
        "restored_model_path": restored_model_path.as_posix(),
        "training_seconds": training_result.training_seconds,
        "tensorflow_version": tf.__version__,
        "gpu_devices": gpu_names,
        "smoke_test": args.smoke_test,
        "history": history_values,
    }

    output_path = METRICS_DIRECTORY / f"{run_name}.json"

    write_json_atomic(output_path, results)

    print(f"Experiment record: {output_path}")


def main() -> None:
    args = parse_arguments()

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_prefix = "custom_cnn_smoke" if args.smoke_test else "custom_cnn"
    run_name = f"{run_prefix}_{run_timestamp}"

    print(f"Run: {run_name}")
    print(f"TensorFlow: {tf.__version__}")
    print(f"Physical GPUs: {tf.config.list_physical_devices('GPU')}")

    train_dataset = load_split(
        split="train",
        batch_size=args.batch_size,
        shuffle=True,
    )
    epochs = args.epochs

    if args.smoke_test:
        train_dataset = train_dataset.take(2)
        epochs = 1
        print("Smoke test mode: 2 training batches and 1 validation batch")

    class_weights = calculate_class_weights()
    print(f"Class weights: {class_weights}")

    restored_model_path = (
        CHECKPOINT_DIRECTORY / f"{run_name}_restored.keras"
    )
    training_result = fit_and_certify_classifier(
        model_factory=build_custom_cnn,
        train_dataset=train_dataset,
        validation_dataset_factory=lambda: build_validation_dataset(
            batch_size=args.batch_size,
            smoke_test=args.smoke_test,
        ),
        epochs=epochs,
        class_weights=class_weights,
        learning_rate=args.learning_rate,
        seed=args.seed,
        best_checkpoint_path=(
            CHECKPOINT_DIRECTORY / f"{run_name}_best.keras"
        ),
        restored_checkpoint_path=restored_model_path,
        csv_log_path=LOG_DIRECTORY / f"{run_name}.csv",
        tensorboard_path=LOG_DIRECTORY / run_name,
        tolerance=args.round_trip_tolerance,
        verbose=args.verbose,
    )

    save_experiment_results(
        run_name=run_name,
        args=args,
        class_weights=class_weights,
        training_result=training_result,
        restored_model_path=restored_model_path,
    )

    in_memory_validation = training_result.in_memory_metrics
    reloaded_validation = training_result.reloaded_metrics
    round_trip_check = training_result.round_trip_check

    print("\nModel save/reload round-trip")
    print("-----------------------------")
    print(
        "In-memory validation: "
        f"loss={in_memory_validation['loss']:.6f}, "
        f"accuracy={in_memory_validation['accuracy']:.6f}"
    )
    print(
        "Reloaded validation: "
        f"loss={reloaded_validation['loss']:.6f}, "
        f"accuracy={reloaded_validation['accuracy']:.6f}"
    )
    print(
        "Absolute differences: "
        f"loss={round_trip_check['loss_absolute_difference']:.8f}, "
        "accuracy="
        f"{round_trip_check['accuracy_absolute_difference']:.8f}"
    )

    if not round_trip_check["passed"]:
        raise RuntimeError(
            "Model save/reload round-trip verification failed. "
            f"Tolerance: {args.round_trip_tolerance}. "
            f"In-memory metrics: {in_memory_validation}. "
            f"Reloaded metrics: {reloaded_validation}. "
            f"Restored checkpoint: {restored_model_path}. "
            "The experiment JSON was written with the diagnostic evidence."
        )

    print(f"Training time: {training_result.training_seconds:.2f} seconds")
    print("Training run completed successfully.")


if __name__ == "__main__":
    main()

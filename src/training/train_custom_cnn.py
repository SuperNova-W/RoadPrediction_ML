"""Train the custom TensorFlow CNN damage classifier."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import tensorflow as tf
from tensorflow import keras

from src.datasets.classification_dataset import load_split
from src.models.custom_cnn import build_custom_cnn
from src.utils.classes import CLASS_TO_INDEX


TRAIN_SPLIT_PATH = Path("data/splits/train.csv")
CHECKPOINT_DIRECTORY = Path("outputs/checkpoints")
LOG_DIRECTORY = Path("outputs/logs")
METRICS_DIRECTORY = Path("outputs/metrics")


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

    args = parser.parse_args()

    if args.epochs <= 0:
        parser.error("--epochs must be greater than zero")
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.learning_rate <= 0:
        parser.error("--learning-rate must be greater than zero")

    return args


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

    total_objects = sum(label_counts.values())
    number_of_classes = len(label_counts)

    if total_objects == 0 or any(count == 0 for count in label_counts.values()):
        raise ValueError(
            f"Every class needs training examples: {label_counts}"
        )

    return {
        CLASS_TO_INDEX[label]: total_objects / (number_of_classes * count)
        for label, count in label_counts.items()
    }


def build_callbacks(run_name: str) -> list[keras.callbacks.Callback]:
    """Create callbacks for recovery, logging, and overfitting control."""

    CHECKPOINT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    checkpoint_path = CHECKPOINT_DIRECTORY / f"{run_name}_best.keras"
    tensorboard_path = LOG_DIRECTORY / run_name
    csv_log_path = LOG_DIRECTORY / f"{run_name}.csv"

    return [
        keras.callbacks.ModelCheckpoint(
            filepath=checkpoint_path,
            monitor="val_loss",
            mode="min",
            save_best_only=True,
            verbose=1,
        ),
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            mode="min",
            patience=5,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            mode="min",
            factor=0.5,
            patience=2,
            min_lr=1e-6,
            verbose=1,
        ),
        keras.callbacks.TensorBoard(
            log_dir=tensorboard_path,
            histogram_freq=0,
        ),
        keras.callbacks.CSVLogger(csv_log_path),
        keras.callbacks.TerminateOnNaN(),
    ]


def save_experiment_results(
    run_name: str,
    args: argparse.Namespace,
    class_weights: dict[int, float],
    history: keras.callbacks.History,
    training_seconds: float,
) -> None:
    """Save configuration and observed training history as JSON."""

    METRICS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    history_values = {
        metric: [float(value) for value in values]
        for metric, values in history.history.items()
    }

    validation_losses = history_values.get("val_loss", [])
    best_epoch = (
        validation_losses.index(min(validation_losses)) + 1
        if validation_losses
        else None
    )

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
        "best_epoch": best_epoch,
        "best_validation_loss": (
            min(validation_losses) if validation_losses else None
        ),
        "training_seconds": training_seconds,
        "tensorflow_version": tf.__version__,
        "gpu_devices": gpu_names,
        "smoke_test": args.smoke_test,
        "history": history_values,
    }

    output_path = METRICS_DIRECTORY / f"{run_name}.json"

    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2)

    print(f"Experiment record: {output_path}")


def main() -> None:
    args = parse_arguments()
    keras.utils.set_random_seed(args.seed)

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
    validation_dataset = load_split(
        split="val",
        batch_size=args.batch_size,
        shuffle=False,
    )

    epochs = args.epochs

    if args.smoke_test:
        train_dataset = train_dataset.take(2)
        validation_dataset = validation_dataset.take(1)
        epochs = 1
        print("Smoke test mode: 2 training batches and 1 validation batch")

    class_weights = calculate_class_weights()
    print(f"Class weights: {class_weights}")

    model = build_custom_cnn()
    model.compile(
        optimizer=keras.optimizers.Adam(
            learning_rate=args.learning_rate
        ),
        loss=keras.losses.SparseCategoricalCrossentropy(
            from_logits=True
        ),
        metrics=[
            keras.metrics.SparseCategoricalAccuracy(
                name="accuracy"
            )
        ],
    )

    start_time = time.perf_counter()

    history = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=epochs,
        class_weight=class_weights,
        callbacks=build_callbacks(run_name),
        # The training tf.data pipeline already performs shuffling.
        shuffle=False,
        verbose=args.verbose,
    )

    training_seconds = time.perf_counter() - start_time

    save_experiment_results(
        run_name=run_name,
        args=args,
        class_weights=class_weights,
        history=history,
        training_seconds=training_seconds,
    )

    print(f"Training time: {training_seconds:.2f} seconds")
    print("Training run completed successfully.")


if __name__ == "__main__":
    main()

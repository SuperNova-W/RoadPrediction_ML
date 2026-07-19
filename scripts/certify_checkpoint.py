"""Re-evaluate a saved classifier in a genuinely fresh Python process.

The two-arm experiment (and, by default, the custom-CNN trainer) certify a
checkpoint by launching this module as a subprocess. A fresh interpreter
guarantees no compiled-metric or session state leaks from training into the
measurement, so the reported loss and accuracy match what a redeployed model
produces. Metrics are computed through the eager inference path in
:func:`src.evaluation.classifier_runtime.evaluate_eager_dataset`.

Provide either a manifest (plus an optional crop root) or a legacy directory
``--split``. ``--limit-batches`` mirrors a smoke-test ``dataset.take(n)`` so an
in-process measurement can be compared against this one on the exact same crops.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from src.datasets.classification_dataset import (
    build_dataset_from_records,
    load_manifest_records,
    load_split,
)
from src.evaluation.classifier_runtime import evaluate_eager_dataset
from src.utils.experiment_artifacts import (
    project_relative,
    resolve_path,
    utc_now,
    write_json_atomic,
)

if TYPE_CHECKING:
    import tensorflow as tf


def parse_arguments() -> argparse.Namespace:
    """Read the checkpoint, data source, and output destination."""

    parser = argparse.ArgumentParser(
        description="Certify a saved classifier in a fresh Python process."
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to the saved .keras checkpoint to re-evaluate.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON path for the fresh-process metrics.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--manifest",
        type=Path,
        help="Frozen crop manifest CSV describing the evaluation records.",
    )
    source_group.add_argument(
        "--split",
        choices=("val", "test"),
        help="Legacy directory split to evaluate instead of a manifest.",
    )
    parser.add_argument(
        "--crop-root",
        type=Path,
        default=None,
        help="Crop root for manifest paths copied away from the dataset.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--limit-batches",
        type=int,
        default=None,
        help="Evaluate only the first N batches (mirrors a smoke-test take).",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.limit_batches is not None and args.limit_batches <= 0:
        parser.error("--limit-batches must be greater than zero")
    if args.split is not None and args.crop_root is not None:
        parser.error("--crop-root only applies to --manifest evaluation")

    return args


def build_certification_dataset(args: argparse.Namespace) -> tf.data.Dataset:
    """Rebuild the exact evaluation dataset from serializable arguments."""

    if args.manifest is not None:
        records = load_manifest_records(
            resolve_path(args.manifest),
            crop_root=(
                None if args.crop_root is None else resolve_path(args.crop_root)
            ),
            require_existing_files=True,
        )
        dataset = build_dataset_from_records(
            records,
            batch_size=args.batch_size,
            shuffle=False,
            seed=args.seed,
        )
    else:
        dataset = load_split(
            split=args.split,
            batch_size=args.batch_size,
            shuffle=False,
        )

    if args.limit_batches is not None:
        dataset = dataset.take(args.limit_batches)
    return dataset


def main() -> None:
    """Load the checkpoint, evaluate eagerly, and write the metrics JSON."""

    args = parse_arguments()

    import tensorflow as tf
    from tensorflow import keras

    checkpoint_path = resolve_path(args.checkpoint)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint does not exist: {checkpoint_path}")

    model = keras.models.load_model(checkpoint_path, compile=False)
    dataset = build_certification_dataset(args)
    metrics = evaluate_eager_dataset(model, dataset)

    if args.manifest is not None:
        source: dict[str, object] = {
            "manifest": project_relative(resolve_path(args.manifest)),
            "crop_root": (
                None
                if args.crop_root is None
                else project_relative(resolve_path(args.crop_root))
            ),
        }
    else:
        source = {"split": args.split}

    payload = {
        "certified_at_utc": utc_now(),
        "checkpoint": project_relative(checkpoint_path),
        "evaluation_path": "eager_inference_fresh_process",
        "loss": metrics["loss"],
        "accuracy": metrics["accuracy"],
        "number_of_examples": int(metrics["number_of_examples"]),
        "batch_size": args.batch_size,
        "seed": args.seed,
        "limit_batches": args.limit_batches,
        "source": source,
        "tensorflow_version": tf.__version__,
        "gpu_devices": [
            device.name for device in tf.config.list_physical_devices("GPU")
        ],
    }
    write_json_atomic(resolve_path(args.output), payload)

    print(
        f"Certified {checkpoint_path.name}: "
        f"loss={metrics['loss']:.6f} accuracy={metrics['accuracy']:.6f} "
        f"on {int(metrics['number_of_examples']):,} crops "
        "(eager, fresh process)."
    )


if __name__ == "__main__":
    main()

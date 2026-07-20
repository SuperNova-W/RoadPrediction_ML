"""Launch the EfficientNetV2 damage-classifier training job on AWS SageMaker.

Run this from your machine (or a SageMaker notebook). It packages ``src`` and
``scripts`` with the ``train_entry.py`` entry point, points a training channel at
the crop dataset in S3, and starts a single-GPU training job. The defaults match
the recommended EfficientNetV2-S @ 256 accuracy recipe.

Prerequisites:
  * ``pip install sagemaker`` and configured AWS credentials;
  * an execution role ARN SageMaker can assume (``--role``);
  * the square-crop dataset in S3 (pass ``--data-s3``), or a local copy to
    upload once (pass ``--upload-from data/processed/classification_square_v2``).

Example:
  python sagemaker_job/launch_training.py \
    --role arn:aws:iam::<acct>:role/<SageMakerRole> \
    --upload-from data/processed/classification_square_v2 \
    --wait

See sagemaker_job/README.md for the framework-version / container notes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    # AWS / data
    parser.add_argument(
        "--role",
        required=True,
        help="IAM execution role ARN SageMaker assumes for the job.",
    )
    parser.add_argument(
        "--data-s3",
        default=None,
        help="S3 URI of the dataset directory (must contain manifest.csv).",
    )
    parser.add_argument(
        "--upload-from",
        default=None,
        help="Local dataset dir to upload if --data-s3 is not given.",
    )
    parser.add_argument("--instance-type", default="ml.g5.xlarge")
    parser.add_argument(
        "--framework-version",
        default="2.16",
        help="SageMaker TensorFlow DLC version (must ship Keras 3, i.e. >=2.16).",
    )
    parser.add_argument("--py-version", default="py310")
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--max-run-hours", type=float, default=6.0)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Stream logs and block until the job finishes.",
    )

    # Training recipe (defaults = EfficientNetV2-S @ 256, accuracy-first).
    parser.add_argument("--backbone", default="s", choices=("b1", "b3", "s"))
    parser.add_argument("--input-size", type=int, default=256)
    parser.add_argument(
        "--loss", default="weighted_ce", choices=("weighted_ce", "focal")
    )
    parser.add_argument(
        "--checkpoint-metric",
        default="val_accuracy",
        choices=(
            "val_accuracy",
            "val_macro_f1",
            "val_balanced_accuracy",
            "val_loss",
        ),
    )
    parser.add_argument("--frozen-epochs", type=int, default=10)
    parser.add_argument("--fine-tune-epochs", type=int, default=20)
    parser.add_argument("--frozen-batch-size", type=int, default=64)
    parser.add_argument("--fine-tune-batch-size", type=int, default=32)
    parser.add_argument(
        "--eval-batch-size",
        type=int,
        default=16,
        help="Batch for eval + the certify subprocess; kept small so the "
        "subprocess fits in the GPU memory the trainer leaves free.",
    )
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument("--dropout", type=float, default=0.40)
    parser.add_argument(
        "--mixed-precision",
        default="true",
        choices=("true", "false"),
        help="Tensor-Core fp16 training (much faster on A10G).",
    )
    parser.add_argument(
        "--verbose",
        type=int,
        choices=(0, 1, 2),
        default=2,
        help="Keras output. 2 (one line/epoch) is best for CloudWatch logs.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import sagemaker
    from sagemaker.tensorflow import TensorFlow

    session = sagemaker.Session()

    data_s3 = args.data_s3
    if data_s3 is None:
        if not args.upload_from:
            raise SystemExit("Provide either --data-s3 or --upload-from.")
        print(f"Uploading {args.upload_from} to S3 (one-time)...", flush=True)
        data_s3 = session.upload_data(
            path=args.upload_from,
            key_prefix="road-damage/classification_square_v2",
        )
        print(f"Uploaded dataset to {data_s3}", flush=True)

    hyperparameters: dict[str, object] = {
        "backbone": args.backbone,
        "input-size": args.input_size,
        "loss": args.loss,
        "checkpoint-metric": args.checkpoint_metric,
        "frozen-epochs": args.frozen_epochs,
        "fine-tune-epochs": args.fine_tune_epochs,
        "frozen-batch-size": args.frozen_batch_size,
        "fine-tune-batch-size": args.fine_tune_batch_size,
        "eval-batch-size": args.eval_batch_size,
        "early-stopping-patience": args.early_stopping_patience,
        "dropout": args.dropout,
        "mixed-precision": args.mixed_precision,
        "verbose": args.verbose,
    }
    # fp16 inference does not reproduce to 1e-5 across processes; loosen the
    # certification tolerance so it still catches gross bugs without flaking.
    if args.mixed_precision == "true":
        hyperparameters["round-trip-tolerance"] = 1e-3

    estimator = TensorFlow(
        entry_point="train_entry.py",
        source_dir=str(REPO_ROOT / "sagemaker_job"),
        dependencies=[str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts")],
        role=args.role,
        instance_type=args.instance_type,
        instance_count=1,
        framework_version=args.framework_version,
        py_version=args.py_version,
        hyperparameters=hyperparameters,
        max_run=int(args.max_run_hours * 3600),
        disable_profiler=True,
        base_job_name="road-damage-effv2",
        # Unbuffered Python so CloudWatch streams logs live (a crash won't
        # swallow buffered lines); show TF warnings/errors but not info spam.
        environment={
            "PYTHONUNBUFFERED": "1",
            "TF_CPP_MIN_LOG_LEVEL": "1",
        },
    )

    print(
        f"Launching {args.backbone.upper()} @ {args.input_size}px on "
        f"{args.instance_type} (mixed_precision={args.mixed_precision})...",
        flush=True,
    )
    estimator.fit(
        {"training": data_s3},
        job_name=args.job_name,
        wait=args.wait,
    )

    job = estimator.latest_training_job.name
    print(f"\nTraining job: {job}")
    if args.wait:
        print(f"Model artifact: {estimator.model_data}")
        print(
            "Holdout metrics + config.json are inside model.tar.gz and the "
            "full experiment (predictions, confusion matrices) is in "
            "output.tar.gz."
        )
    else:
        print("Track it with: aws sagemaker describe-training-job "
              f"--training-job-name {job}")


if __name__ == "__main__":
    main()

# SageMaker training for the EfficientNetV2 damage classifier

Runs the same `scripts/train_efficientnet_v2.py` pipeline as a managed AWS
SageMaker training job (billed per-second, instance torn down at the end). This
is the practical way to train the larger backbones / higher resolutions that are
impractical on the local Apple Metal GPU.

The directory is named `sagemaker_job/` (not `sagemaker/`) on purpose: a folder
named `sagemaker` collides with and shadows the installed `sagemaker` SDK, which
breaks `from sagemaker.tensorflow import TensorFlow`.

```
sagemaker_job/
  launch_training.py   # run on your machine: builds the estimator, calls .fit()
  train_entry.py       # runs in the container: maps SageMaker paths -> the trainer
  requirements.txt     # extra libs installed in the container (Pillow/sklearn/mpl)
```

## Prerequisites

1. `pip install "sagemaker<3"` (in an env separate from the TF-metal one) and
   configured AWS credentials (`aws configure`). **Pin `<3`** — `sagemaker` v3
   is a rewrite that removed the classic `sagemaker.tensorflow.TensorFlow`
   estimator this launcher uses; plain `pip install sagemaker` grabs v3 and
   fails with `No module named 'sagemaker.tensorflow'`.
2. An IAM **execution role** SageMaker can assume, with S3 access to your data
   and output bucket. You pass its ARN via `--role`.
3. The square-crop dataset available to SageMaker — either already in S3
   (`--data-s3 s3://...`) or a local copy to upload once (`--upload-from ...`).

## 1. Stage the data in S3

The training channel must contain `manifest.csv`, `metadata.json`, and the crop
files. Either let the launcher upload it (simplest, one-time), or upload
yourself:

```bash
aws s3 sync data/processed/classification_square_v2 \
  s3://<your-bucket>/road-damage/classification_square_v2
```

## 2. Launch the recommended run (EfficientNetV2-S @ 256, accuracy-first)

```bash
python sagemaker_job/launch_training.py \
  --role arn:aws:iam::<account-id>:role/<SageMakerExecutionRole> \
  --data-s3 s3://<your-bucket>/road-damage/classification_square_v2 \
  --wait
```

Defaults baked in: `--backbone s --input-size 256 --loss weighted_ce
--checkpoint-metric val_accuracy --frozen-epochs 10 --fine-tune-epochs 20
--dropout 0.4 --mixed-precision true` on `ml.g5.xlarge` (1× A10G). Override any
of them on the command line. Drop `--wait` to return immediately and poll later.

**Expected: ~1.5–3 hrs, ~$2–5** (mixed precision on the A10G). Without
`--mixed-precision true` it's roughly ~2× slower/cost.

## 3. Get the results

- `model.tar.gz` (at `estimator.model_data`) contains **`restored.keras`** (the
  certified, deployable checkpoint) plus `completion.json` and `config.json`.
- `output.tar.gz` contains the full experiment tree: `us_holdout_evaluation/`
  (metrics.json, predictions.csv, confusion matrix), `internal_tune_evaluation/`,
  training logs, and the fresh-process certification record.

The holdout accuracy / macro-F1 in `us_holdout_evaluation/metrics.json` is the
number to trust — same eager, subprocess-certified metric as the local runs, so
it's directly comparable to `effv2_b1_v3`.

## Container / framework version — read this

The estimator uses a **prebuilt SageMaker TensorFlow DLC**. Two requirements:

1. It must ship **Keras 3** — i.e. **TensorFlow ≥ 2.16**. Earlier images ship
   Keras 2 and this code will not run on them.
2. The exact `(framework_version, py_version, instance_type)` combination must
   exist as a published image. The default here is `--framework-version 2.16
   --py-version py310`; check the current list and adjust if needed:
   https://github.com/aws/deep-learning-containers/blob/master/available_images.md

The container is trained fresh from ImageNet weights (not from a local
checkpoint), so a minor TF version difference from your laptop's 2.18 is fine.
`requirements.txt` installs Pillow / scikit-learn / matplotlib on top of the
container's TensorFlow.

## Notes

- **Mixed precision**: fp16 Tensor-Core training. Because fp16 inference doesn't
  reproduce to 1e-5 across processes, the launcher automatically loosens the
  certification tolerance to `1e-3` when it's on (still catches gross bugs).
- **Spot training**: not enabled — this pipeline has no checkpoint-resume, so a
  spot interruption loses the run. Add resume before using managed spot.
- **Multi-GPU**: unnecessary for this ~20M-param model (trains in ~2 hrs on one
  A10G). If you specifically want a distributed-training setup, that's a separate
  change (`tf.distribute.MirroredStrategy` on a multi-GPU instance).
- **ConvNeXt**: intentionally not offered. Its grouped convolutions force XLA
  JIT; that runs on CUDA (so it *would* work here) but not on Apple Metal, and
  EfficientNetV2-S is the recommended choice regardless.

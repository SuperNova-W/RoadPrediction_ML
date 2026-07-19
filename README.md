# Road Damage Prediction / RoadLens

An experimental computer-vision pipeline for classifying road damage in
ground-level imagery, plus a frontend prototype for a future municipal review
product.

The machine-learning work uses the
[RDD2022 dataset](https://github.com/sekilab/RoadDamageDetector) and currently
classifies annotated damage crops with TensorFlow on Apple Silicon. The
long-term product direction is full-image detection, map-based review, and
municipal maintenance workflows.

> This is a research project, not a production inspection system. It does not
> yet detect damage in full road images, and no severity or repair-priority
> output should be treated as a professional engineering assessment.

The [`frontend/`](frontend/README.md) directory contains the separate RoadLens
Next.js prototype. It uses fictional mock data and is not connected to the ML
pipeline.

## Current status

The trustworthy classification workflow now includes:

- leakage-resistant train, validation, and test splits based on country and
  sequential image groups;
- immutable square contextual crops with no aspect-ratio black bars;
- deterministic manifest-driven `tf.data` inputs;
- a custom CNN baseline and an ImageNet-pretrained EfficientNetV2-B1 model;
- eager validation metrics used for checkpointing and early stopping;
- model save/reload certification in a genuinely fresh Python process;
- accuracy, balanced accuracy, macro/weighted F1, per-class metrics, confusion
  matrices, country reports, and visual error-review sets;
- a matched Norway/India ablation with identical U.S. images, total size, and
  class counts in both arms; and
- focal-loss and weighted-cross-entropy transfer-learning comparisons.

The official RDD2022 test split remains untouched for model selection. Results
below are from a fixed U.S. validation holdout and should be considered
provisional until repeated across seeds and confirmed once on the test set.

## Damage classes

| Code | Class | Index |
| --- | --- | ---: |
| D00 | Longitudinal crack | 0 |
| D10 | Transverse crack | 1 |
| D20 | Alligator crack | 2 |
| D40 | Pothole | 3 |

The canonical mapping is defined in `src/utils/classes.py` and shared by data,
training, evaluation, and experiment scripts.

## Validated results

All rows below use seed 42 and the same fixed U.S. validation holdout
(`n = 1,579`). Each reported checkpoint was reloaded and evaluated in a fresh
Python process. Generated checkpoints and experiment artifacts live under
`outputs/` and are intentionally excluded from Git.

| Experiment | Training loss | Accuracy | Balanced accuracy | Macro F1 | D20 recall | D40 recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Custom CNN, Arm A: no Norway/India | weighted CE | 0.5187 | 0.3892 | 0.4071 | 0.1966 | 0.2500 |
| Custom CNN, Arm B: Norway/India replace other-country samples | weighted CE | 0.5041 | 0.4649 | 0.4485 | 0.1966 | 0.5625 |
| EfficientNetV2-B1 v2 | weighted CE | **0.8803** | 0.8179 | **0.8314** | 0.5470 | 0.9062 |
| EfficientNetV2-B1 v3 | focal loss | 0.8778 | **0.8351** | 0.8298 | **0.5897** | **0.9375** |

The two-arm result shows a tradeoff: replacing other-country crops with
Norway/India crops reduced raw accuracy but improved class balance, macro F1,
and pothole recall. It is not evidence of a general causal benefit because it
is one seed and the U.S. holdout contains only 32 D40 crops.

EfficientNet v2 has the highest accuracy and macro F1; v3 has the strongest
balanced accuracy and minority-class recall. The project has not selected a
final model. Post-hoc class-bias tuning on v2 was rejected because it reduced
holdout macro F1 from 0.8314 to 0.8169 and balanced accuracy from 0.8179 to
0.7779 without improving accuracy.

## Data and leakage controls

RDD2022 is not distributed with this repository. Follow the upstream dataset
instructions and place the extracted files under `data/raw/RDD2022/`.

The parser found 55,006 valid crops in the four target classes:

| Class | Crops |
| --- | ---: |
| D00 | 26,016 |
| D10 | 11,830 |
| D20 | 10,616 |
| D40 | 6,544 |

One zero-width object in `Japan_001265.xml` is skipped while other valid
objects from that image are retained.

Source images are grouped by country and blocks of 100 sequential image IDs
before splitting. This reduces the chance that neighboring road frames leak
across partitions.

| Split | Source images | Crops |
| --- | ---: | ---: |
| Train | 26,953 | 38,776 |
| Validation | 5,721 | 8,074 |
| Test | 5,711 | 8,156 |

Known image and group overlap is zero. Square crop version
`square_context_v1` uses 30% context around the longer bounding-box dimension,
shifts the crop inside source-image boundaries where possible, and resizes
directly to 224×224. The builder writes its manifest and metadata atomically
and refuses to overwrite an existing dataset directory.

## Why validation uses eager inference

Earlier runs showed a serious discrepancy: the epoch log reported roughly 75%
validation accuracy, while the saved model reproduced roughly 54%. The cause
was stale compiled validation metrics in this TensorFlow/Metal workflow.

The shared training code now computes validation loss and predictions with an
explicit eager pass. Those eager metrics drive checkpointing, learning-rate
scheduling, and early stopping. After training, the selected model is saved,
loaded by a new Python process, evaluated on a newly constructed deterministic
dataset, and compared with the in-process result within a numerical tolerance.
An experiment is not marked complete when that certification fails.

## Environment

The verified local environment is:

- macOS on an Apple M5 with 24 GB unified memory;
- Python 3.11.15;
- TensorFlow 2.18.1;
- `tensorflow-metal` 1.2.0;
- NumPy 2.0.2 and scikit-learn 1.9.0;
- Pillow 12.3.0, Matplotlib 3.11.0, SciPy 1.17.1, and TensorBoard 2.18.0.

TensorFlow 2.21.0 did not load with `tensorflow-metal` 1.2.0 in this project,
so do not upgrade TensorFlow independently without retesting Metal support.

Create and activate the environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  tensorflow==2.18.1 tensorflow-metal==1.2.0 \
  numpy==2.0.2 scikit-learn==1.9.0 \
  pillow==12.3.0 matplotlib==3.11.0 scipy==1.17.1 \
  tensorboard==2.18.0 pytest
```

Verify that TensorFlow can see the Metal GPU:

```bash
python -c "import tensorflow as tf; print(tf.__version__); print(tf.config.list_physical_devices('GPU'))"
```

Metal messages about an unknown NUMA node or `0 MB` device memory are known
plugin-reporting quirks on this machine; confirm the listed device rather than
inferring failure from those messages alone.

## Repository layout

```text
RoadDamagePrediction_ML/
├── scripts/
│   ├── build_image_manifest.py
│   ├── create_dataset_splits.py
│   ├── create_classification_crops.py
│   ├── two_arm_experiment.py
│   ├── train_efficientnet_v2.py
│   ├── certify_checkpoint.py
│   ├── tune_decision_thresholds.py
│   └── analyze_validation_metrics.py
├── src/
│   ├── datasets/      # parsing, manifests, tf.data, leakage/integrity checks
│   ├── models/        # custom CNN and EfficientNetV2-B1
│   ├── training/      # shared callbacks, focal loss, training utilities
│   ├── evaluation/    # eager metrics, reports, checkpoint evaluation
│   ├── inference/     # reserved for the future inference service
│   └── utils/         # class definitions and atomic experiment artifacts
├── tests/
├── data/              # ignored: raw data, manifests, splits, generated crops
├── outputs/           # ignored: checkpoints, logs, metrics, figures
├── frontend/          # RoadLens mock-data product prototype
├── MODEL_IMPROVEMENT_PLAN.md
└── AGENTS.md          # authoritative engineering handoff for coding agents
```

## Build the dataset

Run commands from the repository root:

```bash
# Extract the source dataset.
python -m scripts.extract_rdd2022

# Inventory annotated source images and create grouped splits.
python -m scripts.build_image_manifest
python -m scripts.create_dataset_splits

# Inspect annotations before generating crops.
python -m scripts.analyze_annotations

# Validate the square-crop plan without writing images.
python -m scripts.create_classification_crops \
  --output-directory data/processed/classification_square_v2 \
  --context-ratio 0.30 \
  --dry-run

# Build the immutable square crop dataset.
python -m scripts.create_classification_crops \
  --output-directory data/processed/classification_square_v2 \
  --context-ratio 0.30
```

Do not regenerate the grouped split while comparing models; otherwise both the
data and the model change at once.

## Run experiments

Use `caffeinate -i` for long macOS runs so idle sleep does not interrupt
training. The user should launch full runs locally to keep live progress
visible.

### Smoke test the custom CNN

```bash
caffeinate -i ./.venv/bin/python -m src.training.train_custom_cnn \
  --smoke-test \
  --verbose 1
```

### Build or run the matched Norway/India experiment

First freeze and validate the two arm manifests without training:

```bash
./.venv/bin/python -m scripts.two_arm_experiment \
  --experiment-id matched_norway_india_plan \
  --plan-only
```

Then use a new experiment ID for a full run:

```bash
caffeinate -i ./.venv/bin/python -m scripts.two_arm_experiment \
  --experiment-id matched_norway_india_seed42 \
  --epochs 30 \
  --batch-size 32 \
  --seed 42 \
  --verbose 1
```

Arm B replaces class-matched samples from other countries; it does not add
Norway/India images on top. Both arms contain 24,793 crops, the same 6,680 U.S.
training crops, and the same per-class totals.

### Train EfficientNetV2-B1

The current balanced configuration uses focal loss and selects checkpoints by
validation macro F1:

```bash
caffeinate -i ./.venv/bin/python -m scripts.train_efficientnet_v2 \
  --experiment-id effv2_b1_focal_seed42 \
  --loss focal \
  --focal-gamma 2.0 \
  --checkpoint-metric val_macro_f1 \
  --frozen-epochs 10 \
  --fine-tune-epochs 15 \
  --seed 42 \
  --verbose 1
```

Use `--smoke-test` before a full run. To reproduce the weighted-cross-entropy
comparison, use `--loss weighted_ce --checkpoint-metric val_loss`.

### Evaluate an explicit checkpoint

```bash
./.venv/bin/python -m src.evaluation.evaluate_classifier \
  --checkpoint outputs/checkpoints/NAME.keras \
  --split val \
  --batch-size 32
```

Never choose a checkpoint by assuming that a filename is the latest. Do not use
`--split test` until a final configuration has been selected without reference
to test performance.

### Analyze a validation prediction file

```bash
./.venv/bin/python -m scripts.analyze_validation_metrics \
  --predictions-path outputs/metrics/NAME_val_predictions.csv \
  --evaluation-metrics-path outputs/metrics/NAME_val_metrics.json \
  --crop-manifest-path data/processed/classification_square_v2/manifest.csv
```

### Optional threshold experiment

```bash
./.venv/bin/python -m scripts.tune_decision_thresholds \
  --experiment-dir outputs/experiments/EXPERIMENT_ID
```

Thresholds are fitted only on the internal tuning set and assessed on the
fixed U.S. holdout. Keep them only when the holdout result improves; the v2
threshold experiment did not.

## Tests

```bash
./.venv/bin/python -m pytest tests -q
```

The tests cover crop geometry and integrity, manifest datasets, record
disjointness, eager evaluation, shared training behavior, atomic experiment
artifacts, and the matched two-arm construction.

## Frontend prototype

```bash
cd frontend
npm install
npm run dev
```

For frontend checks and route documentation, see
[`frontend/README.md`](frontend/README.md). The frontend currently has no live
backend, model endpoint, authentication, or municipal data.

## Roadmap

1. Repeat the weighted-CE and focal EfficientNetV2-B1 runs across multiple
   seeds and report mean, spread, and per-class recall.
2. Select the classification configuration using validation metrics and
   deployment constraints, then perform one final untouched test evaluation.
3. Compare a smaller MobileNetV3Small transfer model for latency and model-size
   tradeoffs.
4. Add realistic road-imaging augmentations one controlled change at a time.
5. Move from annotated-crop classification to full-image object detection.
6. Connect a versioned inference API to RoadLens, then add GIS review and
   auditable municipal workflows.

See [`MODEL_IMPROVEMENT_PLAN.md`](MODEL_IMPROVEMENT_PLAN.md) for the detailed
status and experiment rules.

## Limitations

- Current metrics are validation-only and come from one seed.
- The fixed U.S. holdout has only 32 pothole crops, so D40 recall has high
  uncertainty.
- Country/camera/domain correlations may still act as shortcuts.
- Crop classification assumes a ground-truth bounding box and does not localize
  damage in a full image.
- The frontend is a mock-data prototype, not a deployed SaaS application.
- The repository does not currently include a software license; RDD2022 has
  separate upstream terms and citation requirements.
- Severity and repair priority have not been professionally validated and must
  remain clearly labeled as heuristic if introduced.

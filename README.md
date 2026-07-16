# Road Damage Prediction

A computer-vision project that analyzes ground-level road imagery to detect and
classify road damage, built on the [RDD2022 dataset](https://github.com/sekilab/RoadDamageDetector)
(Road Damage Detection 2022). The long-term goal is a system that draws bounding
boxes around damaged pavement, classifies the damage type, estimates severity,
and produces a repair-priority score that municipal maintenance teams can act on.

> The repository also contains a standalone frontend prototype for the eventual
> product ("RoadLens") in [`frontend/`](frontend/README.md). It runs entirely on
> mock data and is documented separately — everything below is about the ML side.

## Damage types

The project uses the four primary RDD2022 damage classes:

| Code | Damage type        |
| ---- | ------------------ |
| D00  | Longitudinal crack |
| D10  | Transverse crack   |
| D20  | Alligator crack    |
| D40  | Pothole            |

Class definitions and index mappings live in `src/utils/classes.py` and are
shared by every dataset, training, and evaluation module.

## Project status

The work follows a staged plan (see `AGENTS.md` for the full brief):

- ✅ **Environment & dataset tooling** — archive extraction, annotation parsing,
  statistics, and visualization
- ✅ **Leakage-safe dataset splits** — image manifest + grouped train/val/test splits
- ✅ **Classification baseline (in progress)** — bounding-box crops feed a custom
  CNN classifier (TensorFlow/Keras) with training and test-set evaluation
- 🔜 Transfer-learning baselines (e.g. ResNet/MobileNet-family)
- 🔜 Full-image object detection
- 🔜 Severity estimation and a repair-priority heuristic
- 🔜 Inference service consumed by the frontend

No benchmark numbers are quoted here on purpose: results depend on the local
run, and reported metrics belong in `outputs/metrics/` alongside the exact
configuration that produced them.

## Repository layout

```
├── scripts/                     # Runnable data-preparation & analysis tools
│   ├── extract_rdd2022.py           # Unpack the nested country ZIP archives
│   ├── build_image_manifest.py      # Image-level inventory (per country/split)
│   ├── create_dataset_splits.py     # Leakage-resistant train/val/test splits
│   ├── analyze_annotations.py       # Class balance & bounding-box statistics
│   ├── create_classification_crops.py  # Cut annotated boxes into crop images
│   ├── visualize_annotation.py      # Draw boxes on a source image
│   └── visualize_damage_crops.py    # Contact-sheet of sampled crops
├── src/
│   ├── datasets/                # VOC-XML annotation parser, tf.data pipeline
│   ├── models/                  # Custom CNN architecture
│   ├── training/                # Training loop, checkpoints, history logging
│   ├── evaluation/              # Test-split metrics, confusion matrix, figures
│   ├── inference/               # (reserved for the future inference service)
│   └── utils/                   # Shared class definitions
├── tests/                       # Pytest unit tests
├── configs/                     # (reserved) experiment configuration
├── data/                        # Not committed — see .gitignore
│   ├── raw/RDD2022/                 # Extracted dataset
│   ├── processed/                   # Manifest, crops, crop manifest
│   └── splits/                      # train/val/test CSVs
├── outputs/                     # Not committed: checkpoints, logs, metrics, figures
└── frontend/                    # Product UI prototype (mock data; own README)
```

`data/` (~39 GB) and `outputs/` are intentionally excluded from git.

## Setup

Requires **Python 3.11+**. The code is written against **TensorFlow 2.18**.

```bash
python -m venv .venv
source .venv/bin/activate
pip install tensorflow matplotlib pytest
```

Download the RDD2022 release archive (via the
[RoadDamageDetector project](https://github.com/sekilab/RoadDamageDetector))
and place it where the extractor expects it, or pass `--archive` explicitly.

## Data pipeline

Run everything from the repository root so `src` imports resolve:

```bash
# 1. Extract the nested per-country archives into data/raw/RDD2022/
python -m scripts.extract_rdd2022

# 2. Build an image-level manifest (one row per annotated image)
python -m scripts.build_image_manifest

# 3. Create train/val/test splits
python -m scripts.create_dataset_splits

# 4. Inspect the dataset
python -m scripts.analyze_annotations

# 5. Cut annotated bounding boxes into classification crops
python -m scripts.create_classification_crops
```

**Leakage safety:** RDD2022 images are numbered sequences captured along
continuous drives, so random per-image splitting would place near-duplicate
frames in both train and test. `create_dataset_splits.py` therefore groups
images into per-country blocks of nearby frame numbers and assigns whole
groups to a single split.

## Training & evaluation

The classification baseline trains on 224×224 crops of the annotated regions:

```bash
# Train the custom CNN (checkpoints -> outputs/checkpoints, history -> outputs/metrics)
python -m src.training.train_custom_cnn --epochs 20 --batch-size 32 --learning-rate 1e-3

# Evaluate the best checkpoint on the untouched test split
# (per-class metrics -> outputs/metrics, confusion matrix -> outputs/figures)
python -m src.evaluation.evaluate_classifier
```

Ground rules baked into the tooling: the test split is never used for tuning,
augmentation applies to training data only, and metrics are written to disk
with the run's configuration rather than kept in a notebook.

## Tests

```bash
pytest tests/
```

## Limitations

- The current model is a **classification** baseline over pre-cropped regions —
  it does not yet localize damage in full frames.
- Any future severity score or repair-priority value is a planning heuristic
  derived from image evidence. It is **not** an engineering assessment and does
  not replace licensed inspection or PCI surveys.

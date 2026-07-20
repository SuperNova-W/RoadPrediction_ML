# Road Damage Model: Improvement Plan

This is the active roadmap for the four-class TensorFlow road-damage
classifier. The target classes are D00 (longitudinal crack), D10 (transverse
crack), D20 (alligator crack), and D40 (pothole).

Last updated: 2026-07-19.

## Experiment rules

1. Change one major variable at a time.
2. Freeze data manifests before training and record their hashes.
3. Use the deterministic validation data for development; do not tune on test.
4. Report accuracy, balanced accuracy, macro F1, and every class recall.
5. Treat eager inference as canonical in the local TensorFlow/Metal workflow.
6. Certify a selected checkpoint by loading and evaluating it in a fresh Python
   process before reporting its metrics.
7. Keep configurations, logs, predictions, metrics, and completion state with
   each experiment rather than comparing runs from memory.
8. Evaluate the untouched test split once, after selecting a configuration.

## Status summary

| Work item | Status | Main outcome |
| --- | --- | --- |
| 1. Checkpoint certification | Complete | Eager metrics and fresh-process reload checks replaced stale compiled validation metrics. |
| 2. Square contextual crops | Complete | `classification_square_v2` removes the black-bar orientation shortcut. |
| 3. Structured validation analysis | Complete | Shared metrics, confusion matrices, country reports, predictions, and visual review artifacts are implemented. |
| 4. Transfer-learning baseline | Complete | EfficientNetV2-B1 substantially outperformed the custom CNN on the fixed U.S. validation holdout. |
| 5. Lightweight model comparison | Next | MobileNetV3Small is not implemented yet. |
| 6. Class-imbalance comparison | In progress | Weighted CE and focal loss are complete; balanced sampling remains untested. |
| 7. Realistic augmentation | Planned | Existing augmentation is conservative; controlled road-domain changes remain to be tested. |
| 8. Country/domain bias | In progress | A matched Norway/India replacement experiment is complete; broader domain analysis remains. |
| 9. Model selection | In progress | Multi-seed repeats, latency/size comparison, and final selection remain. |
| 10. Full-image detection | Planned | Begin only after classification selection is trustworthy. |

## 1. Checkpoint certification — complete

Earlier epoch logs reported roughly 75% validation accuracy while the saved
model reproduced roughly 54%. Those old runs are invalid as benchmarks.

The shared training workflow now:

- runs an explicit eager validation pass every epoch;
- injects eager loss, accuracy, macro F1, balanced accuracy, and per-class
  recall into the logs;
- uses the configured eager metric for checkpointing and early stopping;
- saves the restored selected model explicitly;
- loads and evaluates that exact artifact in a fresh Python subprocess; and
- fails completion when the in-process and fresh-process results differ beyond
  tolerance.

Training loss is recorded for diagnosing overfitting. It is not a second early
stopping condition: validation deterioration while training loss continues to
fall is precisely the normal signal that generalization has stopped improving.

Relevant files:

- `src/evaluation/classifier_runtime.py`
- `src/training/classifier_training.py`
- `scripts/certify_checkpoint.py`
- `src/utils/experiment_artifacts.py`

## 2. Square contextual crops — complete

The legacy loader added black bars when converting rectangular crops to
224×224. Padding direction correlated with D00/D10 box orientation and could
therefore act as a label shortcut.

The replacement `square_context_v1` dataset:

- uses a square centered on each annotation;
- adds 30% context relative to the longer box dimension;
- shifts inside the source image where possible;
- resizes directly to 224×224 without aspect padding;
- retains the original grouped train/validation/test assignments; and
- validates crop files and record disjointness before use.

The output directory is immutable. Rebuilding requires a new versioned path,
not overwriting the existing dataset.

## 3. Structured validation analysis — complete

Implemented outputs include:

- accuracy, balanced accuracy, macro F1, and weighted F1;
- per-class precision, recall, F1, and support;
- confusion matrix CSV and figure;
- per-country metrics;
- deterministic prediction CSVs; and
- high-confidence error and low-confidence correct review sets.

Use `scripts/analyze_validation_metrics.py` for standalone prediction files.
The controlled experiment runners generate equivalent artifacts directly.

## 4. EfficientNetV2-B1 transfer baseline — complete

The implemented transfer model is EfficientNetV2-B1 rather than the originally
proposed EfficientNetB0. It uses ImageNet weights, a frozen-backbone head stage,
then low-learning-rate fine-tuning. Its Keras preprocessing expects input in
the 0–255 range, so do not add a second external normalization step.

Certified seed-42 results on the same fixed U.S. validation holdout
(`n = 1,579`):

| Run | Loss / checkpoint metric | Accuracy | Balanced accuracy | Macro F1 | D20 recall | D40 recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `effv2_b1_v2` | weighted CE / val loss | 0.8803 | 0.8179 | 0.8314 | 0.5470 | 0.9062 |
| `effv2_b1_v3` | focal / val macro F1 | 0.8778 | 0.8351 | 0.8298 | 0.5897 | 0.9375 |

V2 leads narrowly on accuracy and macro F1. V3 leads on balanced accuracy and
minority-class recall. Both are validation-only, single-seed results and
neither is a final selected model.

## 5. MobileNetV3Small deployment comparison — next

Train MobileNetV3Small with the same frozen/fine-tune procedure, square crop
manifest, fixed internal tuning set, fixed U.S. holdout, eager metrics, and
fresh-process certification.

Record:

- parameter count and saved-model size;
- validation accuracy, balanced accuracy, macro F1, and class recalls;
- inference latency and crops per second on Apple Metal; and
- peak memory if it can be measured reliably.

Completion requires a direct quality/size/speed table against EfficientNetV2-B1.

## 6. Class imbalance — in progress

Completed:

- class-weighted cross-entropy;
- focal loss with balanced per-class alpha and gamma 2.0.

Remaining:

- balanced sampling or balanced batches as a separate experiment;
- multi-seed comparison of weighted CE and focal loss;
- inspection of prediction distributions to catch indiscriminate minority
  overprediction.

Post-hoc additive class-bias tuning on V2 was tested and rejected. It left
accuracy unchanged while reducing holdout macro F1 from 0.8314 to 0.8169 and
balanced accuracy from 0.8179 to 0.7779.

## 7. Realistic road-image augmentation — planned

Test one change at a time after the multi-seed loss comparison:

- small brightness, contrast, and color changes;
- mild translation, zoom, and limited rotation;
- light blur or compression artifacts; and
- restrained exposure or shadow variation.

Do not use 90-degree rotations as label-preserving augmentation because D00
and D10 are orientation-defined. Validation and test inputs must remain
deterministic and unaugmented.

## 8. Country and source-domain bias — in progress

The matched Norway/India experiment is complete and corrected:

- Arm A excludes Norway/India.
- Arm B replaces class-matched other-country samples with Norway/India samples.
- Both arms have 24,793 crops, identical class totals, and the exact same 6,680
  U.S. training crops.
- Both use the same internal U.S. tune set and U.S. comparison holdout.

Seed-42 results:

| Arm | Accuracy | Balanced accuracy | Macro F1 | D40 recall |
| --- | ---: | ---: | ---: | ---: |
| No Norway/India | 0.5187 | 0.3892 | 0.4071 | 0.2500 |
| Norway/India replacements | 0.5041 | 0.4649 | 0.4485 | 0.5625 |

The replacement arm improved balance and pothole recall but reduced accuracy.
Repeat across seeds before making a strong domain-generalization claim; the
holdout contains only 32 pothole crops.

Remaining domain work:

- report per-country class distribution and performance for the selected
  transfer model;
- identify camera, pavement, marking, weather, and image-format shortcuts;
- consider country-aware sampling; and
- consider leave-one-country-out evaluation only after the base comparison is
  stable.

## 9. Model selection — current priority

Run the weighted-CE and focal EfficientNetV2-B1 configurations across multiple
seeds without changing the frozen data manifests. Summarize mean, spread,
confusion matrices, and class recalls.

Then compare MobileNetV3Small and select a classifier using explicit product
tradeoffs:

- macro F1 and balanced accuracy;
- D20 and D40 recall without unacceptable precision collapse;
- model size, inference speed, and operational complexity; and
- stability across seeds and source domains.

Only after selection should the untouched RDD2022 test split be evaluated once.
Do not use the test result to cycle back into hyperparameter tuning.

## 10. Full-image object detection — planned

The current classifier requires an annotated crop. A deployable road-imagery
workflow must instead accept a full frame and return multiple boxes, labels,
and confidence values, including the possibility of no target damage.

The first detector must report:

- IoU, precision, recall, AP, mAP, and per-class AP;
- confidence-threshold and non-maximum-suppression behavior;
- false-positive and false-negative examples; and
- performance by class and source domain.

Classification work remains useful for validating labels, preprocessing,
backbones, imbalance handling, and evaluation before adding localization.
Severity and repair-priority heuristics come only after detection is measured
and must be labeled non-authoritative until professionally validated.

## Execution order

```text
multi-seed EfficientNetV2 comparison
        -> MobileNetV3Small quality/latency comparison
        -> validation-based classifier selection
        -> one untouched test evaluation
        -> controlled augmentation/domain experiments as justified
        -> full-image object detection
        -> versioned inference API and RoadLens integration
```

The immediate next task is the multi-seed EfficientNetV2 weighted-CE versus
focal-loss comparison. Do not start a long run automatically; the user launches
long training locally with live progress.

"""Run a sequential, resumable matched U.S.-targeted country experiment.

Arm A excludes Norway and India. Arm B uses the exact same U.S. crops and
replaces same-class crops from the other countries with Norway/India crops.
The arms therefore have identical total and per-class training counts. The
model, optimizer, augmentation, seed, loss treatment, internal U.S. tuning set,
and untouched U.S. validation set are also shared.

This script never edits the original split manifests or reuses an incomplete
crop staging directory.  Every completed arm writes its own model, history,
round-trip evidence, predictions, metrics, figures, and structured review.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import traceback
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from src.datasets.classification_dataset import (
    CropRecord,
    build_dataset_from_records,
    filter_crop_records,
    load_crop_manifest,
    load_manifest_records,
)
from src.datasets.crop_integrity import (
    validate_crop_file_integrity,
    validate_declared_crop_paths,
)
from src.datasets.record_integrity import assert_record_sets_disjoint
from src.training.classifier_training import (
    SubprocessCertification,
    balanced_class_weights,
    compare_metric_sets,
    fit_and_certify_classifier,
    subprocess_certifier,
)
from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX
from src.utils.experiment_artifacts import (
    PROJECT_ROOT,
    FileLockError,
    exclusive_file_lock,
    project_relative,
    read_json_object,
    resolve_path,
    run_logged_command,
    sha256_file,
    utc_now,
    write_csv_atomic,
    write_json_atomic,
    write_text_atomic,
)


DEFAULT_SQUARE_DATASET_DIRECTORY = Path(
    "data/processed/classification_square_v2"
)
DEFAULT_EXPERIMENTS_DIRECTORY = Path("outputs/experiments")
DEFAULT_TUNING_GROUPS = (
    "United_States_0007",
    "United_States_0009",
    "United_States_0027",
    "United_States_0035",
    "United_States_0042",
)

# These values are intentionally strict: a changed split or crop artifact must
# create a new, consciously reviewed experiment instead of silently changing
# what the two arms mean.
EXPECTED_SQUARE_CROP_COUNTS = {
    "train": 38_776,
    "val": 8_074,
    "test": 8_156,
}
EXPECTED_SQUARE_CROP_MODES = {
    "in_image": 52_317,
    "context_limited": 2_653,
    "edge_padded": 36,
}
EXPECTED_US_HOLDOUT_COUNTS = {
    "D00": 956,
    "D10": 474,
    "D20": 117,
    "D40": 32,
}
EXPECTED_US_TUNE_COUNTS = {
    "D00": 726,
    "D10": 351,
    "D20": 89,
    "D40": 13,
}
EXPECTED_MATCHED_TRAINING_COUNTS = {
    "D00": 10_523,
    "D10": 6_717,
    "D20": 5_605,
    "D40": 1_948,
}
EXPECTED_NORWAY_INDIA_REPLACEMENTS = {
    "D00": 3_204,
    "D10": 1_291,
    "D20": 1_766,
    "D40": 938,
}
# Norway/India may occupy at most half of each class's non-U.S. slots. This
# preserves meaningful representation from the other countries in Arm B. If
# fewer Norway/India crops exist, all available crops for that class are used.
NORWAY_INDIA_MAX_NON_US_SHARE = 0.50
TARGET_COUNTRIES = frozenset({"Norway", "India"})
US_COUNTRY = "United_States"
CONDITIONS = (
    {
        "name": "no_norway_india",
        "arm": "A",
        "description": "Same U.S. core plus other-country crops; no Norway/India",
    },
    {
        "name": "with_norway_india",
        "arm": "B",
        "description": (
            "Exact same U.S. core; Norway/India replace same-class crops "
            "from the other countries"
        ),
    },
)


def class_counts(records: Sequence[Mapping[str, object]]) -> dict[str, int]:
    """Count classifier labels in a record collection."""

    counts = Counter(str(record["label"]) for record in records)
    unknown = set(counts) - set(CLASS_NAMES)

    if unknown:
        raise ValueError(f"Unexpected labels in records: {sorted(unknown)}")

    return {label: int(counts[label]) for label in CLASS_NAMES}


def country_class_counts(
    records: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, int]]:
    """Return auditable class counts for every represented country."""

    countries = sorted({str(record["country"]) for record in records})
    return {
        country: class_counts(
            [record for record in records if record["country"] == country]
        )
        for country in countries
    }


def record_identity(record: Mapping[str, object]) -> tuple[str, str, str]:
    """Identify one crop independently of manifest ordering."""

    return (
        str(record["source_image_path"]),
        str(record["source_object_id"]),
        str(record["crop_relative_path"]),
    )


def _seeded_sample(
    records: Sequence[CropRecord],
    sample_size: int,
    *,
    seed: int,
    namespace: str,
) -> list[CropRecord]:
    """Select an order-independent, deterministic sample."""

    if sample_size < 0 or sample_size > len(records):
        raise ValueError(
            f"Invalid sample size {sample_size} for {len(records)} records."
        )

    def seeded_rank(record: CropRecord) -> tuple[str, tuple[str, str, str]]:
        identity = record_identity(record)
        key = "|".join((str(seed), namespace, *identity)).encode("utf-8")
        return hashlib.sha256(key).hexdigest(), identity

    return sorted(records, key=seeded_rank)[:sample_size]


def _proportional_country_sample(
    records: Sequence[CropRecord],
    sample_size: int,
    *,
    seed: int,
    namespace: str,
) -> list[CropRecord]:
    """Sample while preserving country shares as closely as possible."""

    if sample_size < 0 or sample_size > len(records):
        raise ValueError(
            f"Invalid proportional sample size {sample_size} for "
            f"{len(records)} records."
        )
    if sample_size == 0:
        return []

    records_by_country: dict[str, list[CropRecord]] = {}
    for record in records:
        records_by_country.setdefault(str(record["country"]), []).append(record)

    exact_quotas = {
        country: sample_size * len(country_records) / len(records)
        for country, country_records in records_by_country.items()
    }
    quotas = {
        country: math.floor(exact_quota)
        for country, exact_quota in exact_quotas.items()
    }
    remaining = sample_size - sum(quotas.values())
    remainder_order = sorted(
        records_by_country,
        key=lambda country: (
            -(exact_quotas[country] - quotas[country]),
            country,
        ),
    )
    for country in remainder_order[:remaining]:
        quotas[country] += 1

    selected: list[CropRecord] = []
    for country in sorted(records_by_country):
        selected.extend(
            _seeded_sample(
                records_by_country[country],
                quotas[country],
                seed=seed,
                namespace=f"{namespace}:{country}",
            )
        )
    return selected


def validate_matched_training_arms(
    arm_a: Sequence[CropRecord],
    arm_b: Sequence[CropRecord],
) -> dict[str, object]:
    """Prove the two arms differ only through class-matched country swaps."""

    identities_a = [record_identity(record) for record in arm_a]
    identities_b = [record_identity(record) for record in arm_b]
    if len(identities_a) != len(set(identities_a)):
        raise RuntimeError("Arm A contains duplicate crop identities.")
    if len(identities_b) != len(set(identities_b)):
        raise RuntimeError("Arm B contains duplicate crop identities.")

    counts_a = class_counts(arm_a)
    counts_b = class_counts(arm_b)
    if len(arm_a) != len(arm_b) or counts_a != counts_b:
        raise RuntimeError(
            "Matched arms must have identical total and per-class counts. "
            f"Arm A total/counts={len(arm_a)}/{counts_a}; "
            f"Arm B total/counts={len(arm_b)}/{counts_b}."
        )

    us_a = {
        record_identity(record)
        for record in arm_a
        if record["country"] == US_COUNTRY
    }
    us_b = {
        record_identity(record)
        for record in arm_b
        if record["country"] == US_COUNTRY
    }
    if us_a != us_b:
        raise RuntimeError("The two arms do not contain the exact same U.S. crops.")

    target_a = [
        record for record in arm_a if record["country"] in TARGET_COUNTRIES
    ]
    target_b = [
        record for record in arm_b if record["country"] in TARGET_COUNTRIES
    ]
    if target_a:
        raise RuntimeError("Arm A must not contain Norway or India crops.")
    represented_targets = {str(record["country"]) for record in target_b}
    if represented_targets != TARGET_COUNTRIES:
        raise RuntimeError(
            "Arm B must contain both Norway and India crops; "
            f"found {sorted(represented_targets)}."
        )

    swaps_by_class: dict[str, dict[str, int]] = {}
    for label in CLASS_NAMES:
        other_a = {
            record_identity(record)
            for record in arm_a
            if record["label"] == label and record["country"] != US_COUNTRY
        }
        other_b = {
            record_identity(record)
            for record in arm_b
            if record["label"] == label
            and record["country"] not in TARGET_COUNTRIES
            and record["country"] != US_COUNTRY
        }
        target_b_label = {
            record_identity(record)
            for record in target_b
            if record["label"] == label
        }
        if not other_b.issubset(other_a):
            raise RuntimeError(
                f"Arm B introduced non-target country crops for {label} "
                "that were not in Arm A."
            )
        removed_count = len(other_a - other_b)
        added_count = len(target_b_label)
        if removed_count != added_count:
            raise RuntimeError(
                f"Norway/India did not replace other-country {label} crops "
                f"one-for-one: removed={removed_count}, added={added_count}."
            )
        swaps_by_class[label] = {
            "other_country_crops_removed": removed_count,
            "norway_india_crops_added": added_count,
        }

    return {
        "passed": True,
        "training_records_per_arm": len(arm_a),
        "class_counts_per_arm": counts_a,
        "shared_us_records": len(us_a),
        "exact_same_us_identities": True,
        "swaps_by_class": swaps_by_class,
        "arm_a_country_class_counts": country_class_counts(arm_a),
        "arm_b_country_class_counts": country_class_counts(arm_b),
    }


def build_matched_training_arms(
    eligible_train_records: Sequence[CropRecord],
    *,
    seed: int,
) -> tuple[list[CropRecord], list[CropRecord], dict[str, object]]:
    """Build Arm B by swapping Norway/India into Arm A one class at a time."""

    us_records = [
        record
        for record in eligible_train_records
        if record["country"] == US_COUNTRY
    ]
    target_records = [
        record
        for record in eligible_train_records
        if record["country"] in TARGET_COUNTRIES
    ]
    other_records = [
        record
        for record in eligible_train_records
        if record["country"] != US_COUNTRY
        and record["country"] not in TARGET_COUNTRIES
    ]

    # Arm A contains the complete eligible U.S. core and all eligible records
    # from countries other than Norway and India.
    arm_a_identities = {
        record_identity(record) for record in (*us_records, *other_records)
    }
    arm_b_identities = {record_identity(record) for record in us_records}

    for label in CLASS_NAMES:
        target_for_label = [
            record for record in target_records if record["label"] == label
        ]
        other_for_label = [
            record for record in other_records if record["label"] == label
        ]
        replacement_count = min(
            len(target_for_label),
            math.floor(
                len(other_for_label) * NORWAY_INDIA_MAX_NON_US_SHARE
            ),
        )
        if replacement_count <= 0:
            raise RuntimeError(
                f"Cannot construct a Norway/India replacement for class {label}."
            )

        added_targets = _proportional_country_sample(
            target_for_label,
            replacement_count,
            seed=seed,
            namespace=f"{label}:norway_india_added",
        )
        removed_others = _proportional_country_sample(
            other_for_label,
            replacement_count,
            seed=seed,
            namespace=f"{label}:other_countries_removed",
        )
        removed_identities = {
            record_identity(record) for record in removed_others
        }
        arm_b_identities.update(
            record_identity(record)
            for record in other_for_label
            if record_identity(record) not in removed_identities
        )
        arm_b_identities.update(
            record_identity(record) for record in added_targets
        )

    # Preserve source-manifest order so the frozen CSVs are easy to audit.
    arm_a = [
        record
        for record in eligible_train_records
        if record_identity(record) in arm_a_identities
    ]
    arm_b = [
        record
        for record in eligible_train_records
        if record_identity(record) in arm_b_identities
    ]
    audit = validate_matched_training_arms(arm_a, arm_b)
    return arm_a, arm_b, audit


def assert_expected_counts(
    actual: dict[str, int],
    expected: dict[str, int],
    description: str,
) -> None:
    """Fail loudly if a supposedly fixed experimental subset changed."""

    if actual != expected:
        raise RuntimeError(
            f"Unexpected {description} class counts. "
            f"Expected={expected}, actual={actual}"
        )


def update_state(
    state_path: Path,
    status: str,
    phase: str,
    details: dict[str, object] | None = None,
) -> None:
    """Append a durable supervisor event and update its current state."""

    state = read_json_object(state_path) if state_path.is_file() else {
        "schema_version": 1,
        "events": [],
    }
    event = {
        "at_utc": utc_now(),
        "status": status,
        "phase": phase,
    }

    if details:
        event["details"] = details

    state["status"] = status
    state["phase"] = phase
    state["updated_at_utc"] = event["at_utc"]
    state.setdefault("events", []).append(event)
    write_json_atomic(state_path, state)


def parse_arguments() -> argparse.Namespace:
    """Read sequential experiment settings."""

    parser = argparse.ArgumentParser(
        description=(
            "Train matched no-Norway/India and with-Norway/India square-crop "
            "arms against the same untouched U.S. validation set."
        )
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help=(
            "Stable output folder name. Supply this explicitly when using "
            "--resume."
        ),
    )
    parser.add_argument(
        "--square-dataset-directory",
        type=Path,
        default=DEFAULT_SQUARE_DATASET_DIRECTORY,
        help="Published square crop directory containing manifest.csv and metadata.json.",
    )
    parser.add_argument(
        "--experiments-directory",
        type=Path,
        default=DEFAULT_EXPERIMENTS_DIRECTORY,
        help="Directory that will contain this experiment's immutable artifacts.",
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument(
        "--round-trip-tolerance",
        type=float,
        default=1e-5,
        help="Maximum absolute loss/accuracy difference after save and reload.",
    )
    parser.add_argument(
        "--review-size",
        type=int,
        default=8,
        help="Examples per error-review category for each U.S. holdout evaluation.",
    )
    parser.add_argument(
        "--verbose",
        choices=(0, 1, 2),
        type=int,
        default=1,
        help="Keras output mode: 0=silent, 1=progress bar, 2=one line per epoch.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a prior experiment ID; completed, verified arms are skipped.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run one epoch on two training batches per arm to verify the workflow.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write and validate all frozen manifests but do not train models.",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Permit training if TensorFlow cannot see the Metal GPU.",
    )

    args = parser.parse_args()

    if args.resume and not args.experiment_id:
        parser.error("--resume requires an explicit --experiment-id")
    if args.epochs <= 0:
        parser.error("--epochs must be greater than zero")
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.learning_rate <= 0:
        parser.error("--learning-rate must be greater than zero")
    if args.early_stopping_patience <= 0:
        parser.error("--early-stopping-patience must be greater than zero")
    if args.round_trip_tolerance <= 0:
        parser.error("--round-trip-tolerance must be greater than zero")
    if args.review_size <= 0:
        parser.error("--review-size must be greater than zero")

    return args


def immutable_arguments(args: argparse.Namespace) -> dict[str, object]:
    """Return exactly the configuration that must not change on resume."""

    return {
        "square_dataset_directory": project_relative(
            args.square_dataset_directory
        ),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "seed": args.seed,
        "early_stopping_patience": args.early_stopping_patience,
        "round_trip_tolerance": args.round_trip_tolerance,
        "review_size": args.review_size,
        "smoke_test": args.smoke_test,
        "resize_policy": "ordinary_bilinear_resize_224_no_aspect_padding",
        "class_weight_policy": "shared_from_identical_matched_class_counts",
        "country_swap_policy": (
            "class_stratified_one_for_one_replacement_with_"
            f"max_{NORWAY_INDIA_MAX_NON_US_SHARE:.2f}_non_us_share"
        ),
    }


def validate_square_dataset(
    dataset_directory: Path,
    qa_directory: Path,
) -> tuple[list[str], list[CropRecord], dict[str, Any]]:
    """Independently verify the published square-crop artifact is trainable."""

    dataset_directory = resolve_path(dataset_directory)
    manifest_path = dataset_directory / "manifest.csv"
    metadata_path = dataset_directory / "metadata.json"
    report_path = qa_directory / "square_crop_integrity.json"
    report: dict[str, Any] = {
        "checked_at_utc": utc_now(),
        "dataset_directory": project_relative(dataset_directory),
        "manifest_path": project_relative(manifest_path),
        "metadata_path": project_relative(metadata_path),
        "status": "failed",
    }

    try:
        if not dataset_directory.is_dir():
            raise FileNotFoundError(
                f"Published square dataset directory does not exist: {dataset_directory}"
            )
        if not manifest_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(
                "Square dataset must contain both manifest.csv and metadata.json: "
                f"{dataset_directory}"
            )

        metadata = read_json_object(metadata_path)
        manifest = load_crop_manifest(
            manifest_path,
            crop_root=dataset_directory,
        )
        fieldnames = list(manifest.fieldnames)
        records = list(manifest.records)
        if not records:
            raise ValueError(f"Record file contains no rows: {manifest_path}")

        if metadata.get("dataset_version") != "square_context_v1":
            raise RuntimeError(
                "Unexpected square crop dataset version: "
                f"{metadata.get('dataset_version')}"
            )
        if abs(float(metadata.get("context_ratio", -1.0)) - 0.30) > 1e-12:
            raise RuntimeError(
                "Square crop context ratio must be exactly 0.30 for this experiment."
            )
        if int(metadata.get("total_crops", -1)) != sum(
            EXPECTED_SQUARE_CROP_COUNTS.values()
        ):
            raise RuntimeError(
                "Square crop metadata does not report the expected total of 55,006."
            )

        actual_by_split = Counter(record["split"] for record in records)
        actual_split_counts = {
            split: int(actual_by_split[split])
            for split in EXPECTED_SQUARE_CROP_COUNTS
        }

        if actual_split_counts != EXPECTED_SQUARE_CROP_COUNTS:
            raise RuntimeError(
                "Square crop manifest split counts differ from the frozen splits. "
                f"Expected={EXPECTED_SQUARE_CROP_COUNTS}, actual={actual_split_counts}"
            )
        if len(records) != sum(EXPECTED_SQUARE_CROP_COUNTS.values()):
            raise RuntimeError(
                f"Expected 55,006 crop records, found {len(records):,}."
            )

        metadata_modes = {
            name: int(value)
            for name, value in dict(metadata.get("crop_mode_counts", {})).items()
        }
        if metadata_modes != EXPECTED_SQUARE_CROP_MODES:
            raise RuntimeError(
                "Square crop construction modes differ from the validated plan. "
                f"Expected={EXPECTED_SQUARE_CROP_MODES}, actual={metadata_modes}"
            )

        validate_declared_crop_paths(dataset_directory, records)

        file_integrity = validate_crop_file_integrity(
            dataset_directory,
            records,
        )

        report.update(
            {
                "status": "passed",
                "manifest_sha256": sha256_file(manifest_path),
                "metadata_sha256": sha256_file(metadata_path),
                "total_records": len(records),
                "jpeg_count": file_integrity.image_count,
                "split_counts": actual_split_counts,
                "crop_mode_counts": metadata_modes,
                "all_crops_are_rgb_and_square": True,
                "full_image_header_check": True,
            }
        )
        write_json_atomic(report_path, report)
        return fieldnames, records, metadata

    except Exception as error:
        report["error"] = str(error)
        write_json_atomic(report_path, report)
        raise


def save_square_crop_contact_sheet(
    records: Sequence[CropRecord],
    output_path: Path,
) -> None:
    """Save one representative square crop for every country/class pairing."""

    train_records = [record for record in records if record["split"] == "train"]
    countries = sorted({record["country"] for record in train_records})
    representatives: dict[tuple[str, str], CropRecord] = {}

    for record in sorted(train_records, key=lambda row: row["crop_path"]):
        representatives.setdefault((record["country"], record["label"]), record)

    missing_pairs = [
        (country, label)
        for country in countries
        for label in CLASS_NAMES
        if (country, label) not in representatives
    ]
    if missing_pairs:
        raise RuntimeError(
            f"Cannot create representative contact sheet; missing {missing_pairs}"
        )

    tile_size = 140
    left_margin = 150
    top_margin = 40
    canvas = Image.new(
        "RGB",
        (
            left_margin + tile_size * len(CLASS_NAMES),
            top_margin + tile_size * len(countries),
        ),
        color="white",
    )
    draw = ImageDraw.Draw(canvas)

    for column, label in enumerate(CLASS_NAMES):
        draw.text(
            (left_margin + column * tile_size + 8, 12),
            label,
            fill="black",
        )

    resampling = getattr(Image, "Resampling", Image).BILINEAR

    for row_index, country in enumerate(countries):
        y_offset = top_margin + row_index * tile_size
        draw.text((4, y_offset + 8), country, fill="black")

        for column, label in enumerate(CLASS_NAMES):
            record = representatives[(country, label)]
            crop_path = record.crop_path

            with Image.open(crop_path) as source_image:
                tile = source_image.convert("RGB").resize(
                    (tile_size, tile_size),
                    resample=resampling,
                )

            canvas.paste(tile, (left_margin + column * tile_size, y_offset))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def validate_original_split_separation(records: Sequence[CropRecord]) -> None:
    """Confirm original train/val/test groups remain disjoint in square data."""

    records_by_split = {
        split: [record for record in records if record["split"] == split]
        for split in ("train", "val", "test")
    }
    assert_record_sets_disjoint(
        records_by_split,
        identity_fields=("sequence_group", "source_image_path"),
        description="Square crop records violate split separation",
    )


def assert_no_role_overlap(
    left_name: str,
    left_records: Sequence[CropRecord],
    right_name: str,
    right_records: Sequence[CropRecord],
) -> None:
    """Verify two experimental roles share no groups, source images, or objects."""

    assert_record_sets_disjoint(
        {left_name: left_records, right_name: right_records},
        identity_fields=(
            "sequence_group",
            "source_image_path",
            "source_object_id",
        ),
        description="Experiment role leakage",
    )


def select_experiment_records(
    records: Sequence[CropRecord],
    *,
    seed: int = 42,
) -> dict[str, list[CropRecord]]:
    """Freeze matched training arms, tuning data, and untouched U.S. holdout."""

    validate_original_split_separation(records)
    train_records = filter_crop_records(records, split="train")
    us_train_records = filter_crop_records(
        train_records,
        include_countries="United_States",
    )
    tune_records = filter_crop_records(
        us_train_records,
        include_sequence_groups=DEFAULT_TUNING_GROUPS,
    )
    actual_tuning_groups = {record["sequence_group"] for record in tune_records}

    if actual_tuning_groups != set(DEFAULT_TUNING_GROUPS):
        raise RuntimeError(
            "The fixed internal U.S. tuning groups are absent or changed. "
            f"Expected={sorted(DEFAULT_TUNING_GROUPS)}, actual={sorted(actual_tuning_groups)}"
        )
    assert_expected_counts(
        class_counts(tune_records),
        EXPECTED_US_TUNE_COUNTS,
        "internal U.S. tuning",
    )

    us_holdout_records = filter_crop_records(
        records,
        split="val",
        include_countries="United_States",
    )
    assert_expected_counts(
        class_counts(us_holdout_records),
        EXPECTED_US_HOLDOUT_COUNTS,
        "untouched U.S. holdout",
    )
    assert_no_role_overlap(
        "internal U.S. tuning",
        tune_records,
        "untouched U.S. holdout",
        us_holdout_records,
    )

    result: dict[str, list[CropRecord]] = {
        "us_internal_tune": tune_records,
        "us_comparison_holdout": us_holdout_records,
    }

    eligible_train_records = filter_crop_records(
        train_records,
        exclude_sequence_groups=DEFAULT_TUNING_GROUPS,
    )
    arm_a, arm_b, matching_audit = build_matched_training_arms(
        eligible_train_records,
        seed=seed,
    )
    selected_by_condition = {
        "no_norway_india": arm_a,
        "with_norway_india": arm_b,
    }
    assert_expected_counts(
        class_counts(arm_a),
        EXPECTED_MATCHED_TRAINING_COUNTS,
        "Arm A training",
    )
    assert_expected_counts(
        class_counts(arm_b),
        EXPECTED_MATCHED_TRAINING_COUNTS,
        "Arm B training",
    )
    actual_replacements = {
        label: int(
            dict(matching_audit["swaps_by_class"])[label][
                "norway_india_crops_added"
            ]
        )
        for label in CLASS_NAMES
    }
    assert_expected_counts(
        actual_replacements,
        EXPECTED_NORWAY_INDIA_REPLACEMENTS,
        "Norway/India replacement",
    )

    for condition_name, selected_records in selected_by_condition.items():
        assert_no_role_overlap(
            condition_name,
            selected_records,
            "internal U.S. tuning",
            tune_records,
        )
        assert_no_role_overlap(
            condition_name,
            selected_records,
            "untouched U.S. holdout",
            us_holdout_records,
        )
        result[f"{condition_name}_train"] = selected_records

    return result


def manifest_path_from_plan(plan: Mapping[str, Any], name: str) -> Path:
    """Resolve one frozen manifest path stored in the experiment plan."""

    manifests = dict(plan["manifests"])
    if name not in manifests:
        raise KeyError(f"Plan has no manifest named {name}")
    return resolve_path(str(manifests[name]))


def records_from_plan(
    plan: Mapping[str, Any],
    name: str,
) -> list[CropRecord]:
    """Load a frozen subset against its original square-dataset crop root."""

    manifest_path = manifest_path_from_plan(plan, name)
    frozen_hashes = dict(plan.get("frozen_manifest_sha256", {}))
    if name in frozen_hashes:
        actual_hash = sha256_file(manifest_path)
        if actual_hash != frozen_hashes[name]:
            raise RuntimeError(
                f"Frozen manifest changed after planning: {manifest_path}"
            )

    square_dataset = dict(plan["square_dataset"])
    records = load_manifest_records(
        manifest_path,
        crop_root=resolve_path(str(square_dataset["directory"])),
        require_existing_files=True,
    )
    if not records:
        raise ValueError(f"Frozen manifest contains no records: {name}")
    return records


def validate_planned_matched_arms(plan: Mapping[str, Any]) -> None:
    """Recheck the frozen Arm A/Arm B manifests before any training starts."""

    arm_a = records_from_plan(plan, "no_norway_india_train")
    arm_b = records_from_plan(plan, "with_norway_india_train")
    actual_audit = validate_matched_training_arms(arm_a, arm_b)
    planned_audit = dict(plan.get("matched_arm_audit", {}))

    for field_name, actual_value in actual_audit.items():
        if planned_audit.get(field_name) != actual_value:
            raise RuntimeError(
                "Frozen matched-arm evidence differs from the experiment plan: "
                f"field={field_name}, planned={planned_audit.get(field_name)}, "
                f"actual={actual_value}."
            )


def create_experiment_plan(
    args: argparse.Namespace,
    experiment_directory: Path,
    fieldnames: list[str],
    records: Sequence[CropRecord],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Write frozen subset manifests and a provenance-rich immutable plan."""

    selection = select_experiment_records(records, seed=args.seed)
    manifests_directory = experiment_directory / "manifests"
    manifests: dict[str, str] = {}

    for name, subset_records in selection.items():
        output_path = manifests_directory / f"{name}.csv"
        write_csv_atomic(output_path, fieldnames, subset_records)
        manifests[name] = project_relative(output_path)

    arm_a_records = selection["no_norway_india_train"]
    arm_b_records = selection["with_norway_india_train"]
    matching_audit = validate_matched_training_arms(
        arm_a_records,
        arm_b_records,
    )
    frozen_weights = balanced_class_weights(class_counts(arm_a_records))
    expected_weights = {
        "D00": 0.589019,
        "D10": 0.922771,
        "D20": 1.105843,
        "D40": 3.181853,
    }

    for label, expected_weight in expected_weights.items():
        actual_weight = frozen_weights[label]
        if abs(actual_weight - expected_weight) > 1e-6:
            raise RuntimeError(
                "Frozen matched-arm class weights changed unexpectedly: "
                f"{label} expected≈{expected_weight}, actual={actual_weight}"
            )

    crop_directory = resolve_path(args.square_dataset_directory)
    source_split_paths = {
        split: PROJECT_ROOT / "data" / "splits" / f"{split}.csv"
        for split in ("train", "val", "test")
    }
    plan = {
        "schema_version": 3,
        "created_at_utc": utc_now(),
        "project_root": PROJECT_ROOT.as_posix(),
        "experiment_id": experiment_directory.name,
        "arguments": immutable_arguments(args),
        "square_dataset": {
            "directory": project_relative(crop_directory),
            "manifest": project_relative(crop_directory / "manifest.csv"),
            "metadata": project_relative(crop_directory / "metadata.json"),
            "manifest_sha256": sha256_file(crop_directory / "manifest.csv"),
            "metadata_sha256": sha256_file(crop_directory / "metadata.json"),
            "dataset_version": metadata["dataset_version"],
            "context_ratio": metadata["context_ratio"],
            "resize_policy": "ordinary_bilinear_resize_224_no_aspect_padding",
        },
        "source_split_manifests": {
            split: {
                "path": project_relative(path),
                "sha256": sha256_file(path),
            }
            for split, path in source_split_paths.items()
        },
        "us_internal_tune": {
            "groups": list(DEFAULT_TUNING_GROUPS),
            "purpose": "early_stopping_and_scheduler_only",
            "class_counts": class_counts(selection["us_internal_tune"]),
            "records": len(selection["us_internal_tune"]),
        },
        "us_comparison_holdout": {
            "purpose": "comparison_only_never_used_for_early_stopping",
            "class_counts": class_counts(selection["us_comparison_holdout"]),
            "records": len(selection["us_comparison_holdout"]),
        },
        "class_weight_policy": {
            "description": (
                "Weights are calculated once from Arm A and reused for both "
                "arms. Because class counts are identical, independently "
                "calculating Arm B weights would produce the same values."
            ),
            "weights_by_label": frozen_weights,
        },
        "matched_arm_audit": {
            **matching_audit,
            "replacement_policy": (
                "For each class, deterministically replace up to 50% of "
                "non-U.S. slots with available Norway/India crops. Sampling "
                "is proportional by country and seeded by the experiment seed."
            ),
            "norway_india_max_non_us_share": (
                NORWAY_INDIA_MAX_NON_US_SHARE
            ),
        },
        "conditions": [
            {
                **condition,
                "train_manifest_name": f"{condition['name']}_train",
                "train_records": len(selection[f"{condition['name']}_train"]),
                "class_counts": class_counts(
                    selection[f"{condition['name']}_train"]
                ),
            }
            for condition in CONDITIONS
        ],
        "manifests": manifests,
        "frozen_manifest_sha256": {
            name: sha256_file(resolve_path(path))
            for name, path in manifests.items()
        },
        "test_split_policy": "not_read_or_used_by_this_experiment",
    }
    write_json_atomic(experiment_directory / "plan.json", plan)
    return plan


def validate_frozen_manifests(plan: Mapping[str, Any]) -> None:
    """Reject changed frozen subsets before a planned experiment resumes."""

    manifests = dict(plan["manifests"])
    frozen_hashes = dict(plan.get("frozen_manifest_sha256", {}))
    if frozen_hashes:
        if set(frozen_hashes) != set(manifests):
            raise RuntimeError(
                "Frozen manifest hash inventory does not match plan manifests."
            )
        for name, path_value in manifests.items():
            manifest_path = resolve_path(str(path_value))
            if sha256_file(manifest_path) != frozen_hashes[name]:
                raise RuntimeError(
                    f"Frozen manifest changed since planning: {manifest_path}"
                )
        return

    # Schema-v1 plans predate stored subset hashes. Reconstruct their exact
    # deterministic selections from the already-hashed published manifest so
    # older interrupted runs remain resumable without trusting mutable copies.
    square_dataset = dict(plan["square_dataset"])
    crop_root = resolve_path(str(square_dataset["directory"]))
    published_manifest = load_crop_manifest(
        resolve_path(str(square_dataset["manifest"])),
        crop_root=crop_root,
    )
    expected_selections = select_experiment_records(published_manifest.records)

    if set(manifests) != set(expected_selections):
        raise RuntimeError(
            "Legacy plan manifest inventory differs from deterministic subsets."
        )

    for name, expected_records in expected_selections.items():
        actual_records = load_manifest_records(
            resolve_path(str(manifests[name])),
            crop_root=crop_root,
        )
        expected_rows = [record.to_manifest_row() for record in expected_records]
        actual_rows = [record.to_manifest_row() for record in actual_records]
        if actual_rows != expected_rows:
            raise RuntimeError(
                f"Frozen manifest changed since legacy planning: {manifests[name]}"
            )


def load_and_validate_resume_plan(
    args: argparse.Namespace,
    experiment_directory: Path,
) -> dict[str, Any]:
    """Ensure a resumed run uses exactly the frozen original configuration."""

    plan_path = experiment_directory / "plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(f"Cannot resume; plan is missing: {plan_path}")

    plan = read_json_object(plan_path)
    if plan.get("arguments") != immutable_arguments(args):
        raise RuntimeError(
            "Resume arguments differ from the immutable experiment plan. "
            "Create a new experiment ID for a new configuration."
        )

    crop_dataset = dict(plan["square_dataset"])
    manifest_path = resolve_path(str(crop_dataset["manifest"]))
    metadata_path = resolve_path(str(crop_dataset["metadata"]))

    if (
        sha256_file(manifest_path) != crop_dataset["manifest_sha256"]
        or sha256_file(metadata_path) != crop_dataset["metadata_sha256"]
    ):
        raise RuntimeError(
            "Square crop artifact changed since this plan was created. "
            "Refusing to resume with different data."
        )

    for split, source in dict(plan["source_split_manifests"]).items():
        source_path = resolve_path(str(source["path"]))
        if sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(
                f"Source {split} split manifest changed since plan creation."
            )

    validate_frozen_manifests(plan)

    return plan


def run_structured_analysis(
    plan: dict[str, Any],
    holdout_metrics: dict[str, Any],
    attempt_directory: Path,
) -> str:
    """Generate an independently rerunnable review set for the U.S. holdout."""

    analysis_directory = attempt_directory / "us_holdout_evaluation" / "structured_analysis"
    metrics_directory = analysis_directory / "metrics"
    figures_directory = analysis_directory / "figures"
    log_path = analysis_directory / "analysis.log"
    crop_manifest = resolve_path(str(plan["square_dataset"]["manifest"]))
    command = [
        sys.executable,
        "-m",
        "scripts.analyze_validation_metrics",
        "--predictions-path",
        str(resolve_path(str(holdout_metrics["predictions_path"]))),
        "--crop-manifest-path",
        str(crop_manifest),
        "--evaluation-metrics-path",
        str(resolve_path(str(holdout_metrics["metrics_path"]))),
        "--metrics-directory",
        str(metrics_directory),
        "--figure-directory",
        str(figures_directory),
        "--review-size",
        str(plan["arguments"]["review_size"]),
    ]
    run_logged_command(command, log_path)
    analysis_path = metrics_directory / "predictions_structured_analysis.json"

    # The analyzer names outputs from the prediction filename, which is exactly
    # "predictions.csv" for this runner. Keep an explicit guard here so a future
    # refactor cannot silently claim structured analysis completed.
    if not analysis_path.is_file():
        raise RuntimeError(
            "Structured analysis did not create its expected JSON artifact: "
            f"{analysis_path}"
        )

    return project_relative(analysis_path)


def write_attempt_status(
    attempt_directory: Path,
    status: str,
    details: dict[str, object] | None = None,
) -> None:
    """Persist condition status before and after every material phase."""

    payload: dict[str, object] = {
        "status": status,
        "updated_at_utc": utc_now(),
    }
    if details:
        payload.update(details)
    write_json_atomic(attempt_directory / "status.json", payload)


def find_condition(plan: dict[str, Any], condition_name: str) -> dict[str, Any]:
    """Return one named condition from an immutable experiment plan."""

    for condition in plan["conditions"]:
        if condition["name"] == condition_name:
            return dict(condition)
    raise KeyError(f"Plan has no condition named {condition_name}")


def run_condition(
    plan: dict[str, Any],
    condition_name: str,
    attempt_directory: Path,
    allow_cpu: bool,
    verbose: int,
) -> None:
    """Train, round-trip verify, evaluate, and analyze one condition."""

    import tensorflow as tf
    from tensorflow import keras

    from src.evaluation.evaluate_classifier import evaluate_classifier_records
    from src.models.custom_cnn import build_custom_cnn

    condition = find_condition(plan, condition_name)
    train_manifest_name = str(condition["train_manifest_name"])
    train_records = records_from_plan(plan, train_manifest_name)
    tune_records = records_from_plan(plan, "us_internal_tune")
    holdout_records = records_from_plan(plan, "us_comparison_holdout")
    arguments = dict(plan["arguments"])
    seed = int(arguments["seed"])
    batch_size = int(arguments["batch_size"])
    learning_rate = float(arguments["learning_rate"])
    requested_epochs = int(arguments["epochs"])
    smoke_test = bool(arguments["smoke_test"])
    tolerance = float(arguments["round_trip_tolerance"])

    gpus = tf.config.list_physical_devices("GPU")
    if not gpus and not allow_cpu:
        raise RuntimeError(
            "TensorFlow cannot see a GPU. Refusing CPU fallback; rerun with "
            "--allow-cpu only if that is intentional."
        )

    attempt_directory.mkdir(parents=True, exist_ok=False)
    checkpoints_directory = attempt_directory / "checkpoints"
    logs_directory = attempt_directory / "logs"
    checkpoints_directory.mkdir(parents=True)
    logs_directory.mkdir(parents=True)
    write_attempt_status(
        attempt_directory,
        "running",
        {
            "condition": condition,
            "train_records": len(train_records),
            "tune_records": len(tune_records),
            "holdout_records": len(holdout_records),
        },
    )

    try:
        train_dataset = build_dataset_from_records(
            train_records,
            batch_size=batch_size,
            shuffle=True,
            seed=seed,
        )

        def tuning_dataset_factory():
            dataset = build_dataset_from_records(
                tune_records,
                batch_size=batch_size,
                shuffle=False,
                seed=seed,
            )
            return dataset.take(1) if smoke_test else dataset

        epochs = requested_epochs

        if smoke_test:
            train_dataset = train_dataset.take(2)
            epochs = 1

        frozen_weights = dict(plan["class_weight_policy"]["weights_by_label"])
        class_weights = {
            CLASS_TO_INDEX[label]: float(frozen_weights[label])
            for label in CLASS_NAMES
        }
        best_checkpoint_path = checkpoints_directory / "best.keras"
        restored_checkpoint_path = checkpoints_directory / "restored.keras"
        history_path = logs_directory / "history.csv"
        tensorboard_path = logs_directory / "tensorboard"

        # Certify the saved checkpoint in a genuinely fresh Python process,
        # re-measuring the internal U.S. tuning set through the eager path. This
        # rebuilds the exact tuning dataset from its frozen manifest, so no
        # compiled-metric or session state from training can inflate the number.
        certification_directory = attempt_directory / "certification"
        certification = SubprocessCertification(
            log_path=certification_directory / "certification.log",
            output_path=certification_directory / "fresh_process_metrics.json",
            manifest_path=manifest_path_from_plan(plan, "us_internal_tune"),
            crop_root=resolve_path(str(plan["square_dataset"]["directory"])),
            batch_size=batch_size,
            seed=seed,
            limit_batches=1 if smoke_test else None,
        )

        print(
            f"\nStarting {condition_name}: {len(train_records):,} training crops; "
            f"{len(tune_records):,} U.S. tuning crops; {epochs} epochs maximum.",
            flush=True,
        )
        training_result = fit_and_certify_classifier(
            model_factory=build_custom_cnn,
            train_dataset=train_dataset,
            validation_dataset_factory=tuning_dataset_factory,
            epochs=epochs,
            class_weights=class_weights,
            learning_rate=learning_rate,
            seed=seed,
            best_checkpoint_path=best_checkpoint_path,
            restored_checkpoint_path=restored_checkpoint_path,
            csv_log_path=history_path,
            tensorboard_path=tensorboard_path,
            tolerance=tolerance,
            fresh_evaluator=subprocess_certifier(certification),
            early_stopping_patience=int(
                arguments["early_stopping_patience"]
            ),
            verbose=verbose,
        )
        reloaded_model = training_result.reloaded_model
        in_memory_tune = training_result.in_memory_metrics
        reloaded_tune = training_result.reloaded_metrics
        round_trip = training_result.round_trip_check

        # The callback checkpoint is kept for debugging. Only this explicitly
        # restored and freshly reloaded model is used for downstream evaluation.
        if not restored_checkpoint_path.is_file():
            raise RuntimeError(
                "Round-trip verification did not create the restored model: "
                f"{restored_checkpoint_path}"
            )
        history_values = training_result.history_values
        training_record_path = attempt_directory / "training_metrics.json"
        training_record: dict[str, Any] = {
            "status": "round_trip_failed" if not round_trip["passed"] else "running",
            "condition": condition,
            "dataset": {
                "square_dataset": plan["square_dataset"],
                "train_records": len(train_records),
                "tune_records": len(tune_records),
                "holdout_records": len(holdout_records),
                "resize_policy": arguments["resize_policy"],
                "class_weights": class_weights,
            },
            "requested_epochs": epochs,
            "completed_epochs": len(history_values.get("loss", [])),
            "history": history_values,
            "history_best_validation": (
                training_result.history_best_validation
            ),
            "in_memory_internal_tune": in_memory_tune,
            "fresh_process_internal_tune": reloaded_tune,
            "round_trip_check": round_trip,
            "certification": {
                "mechanism": "fresh_python_subprocess_eager_inference",
                "monitored_validation_path": "eager_inference",
                "fresh_process_metrics": project_relative(
                    certification.output_path
                ),
                "log": project_relative(certification.log_path),
            },
            "best_checkpoint": project_relative(best_checkpoint_path),
            "restored_checkpoint": project_relative(restored_checkpoint_path),
            "training_seconds": training_result.training_seconds,
            "tensorflow_version": tf.__version__,
            "gpu_devices": [device.name for device in gpus],
            "smoke_test": smoke_test,
        }
        write_json_atomic(training_record_path, training_record)

        if not round_trip["passed"]:
            raise RuntimeError(
                "Model save/reload round-trip failed. The training record was "
                f"saved at {training_record_path}."
            )

        # Smoke mode deliberately uses the first deterministic tuning batch for
        # model.fit and the round-trip check, so its independent inference check
        # must use that same subset rather than the full internal tuning set.
        tune_evaluation_records = (
            tune_records[:batch_size] if smoke_test else tune_records
        )
        # Every deployable metric now comes from the eager inference path, so
        # no compiled dataset is passed here: the misleading compiled metric is
        # exactly what certification exists to catch.
        tune_evaluation = evaluate_classifier_records(
            model=reloaded_model,
            dataset=build_dataset_from_records(
                tune_evaluation_records,
                batch_size=batch_size,
                shuffle=False,
                seed=seed,
            ),
            records=tune_evaluation_records,
            output_directory=attempt_directory / "internal_tune_evaluation",
            split="train_internal_tune",
            batch_size=batch_size,
            role="internal_tune",
            checkpoint_path=restored_checkpoint_path,
            title="Internal Tune — saved square-crop model",
        )
        # The fresh-process certification and this in-process artifact evaluation
        # both measure the same tuning crops through the eager path, so they must
        # agree — a cross-runtime reproducibility guarantee for the tuning set.
        fresh_tune_check = compare_metric_sets(
            reloaded_tune,
            {
                "loss": float(tune_evaluation["loss"]),
                "accuracy": float(tune_evaluation["accuracy"]),
            },
            tolerance=tolerance,
        )
        training_record["fresh_reloaded_internal_tune_check"] = fresh_tune_check
        training_record["status"] = (
            "fresh_tune_check_failed"
            if not fresh_tune_check["passed"]
            else "round_trip_verified"
        )
        write_json_atomic(training_record_path, training_record)

        if not fresh_tune_check["passed"]:
            raise RuntimeError(
                "Fresh reloaded internal-tune evaluation disagreed with the "
                "round-trip evaluation. See training_metrics.json."
            )

        holdout_evaluation = evaluate_classifier_records(
            model=reloaded_model,
            dataset=build_dataset_from_records(
                holdout_records,
                batch_size=batch_size,
                shuffle=False,
                seed=seed,
            ),
            records=holdout_records,
            output_directory=attempt_directory / "us_holdout_evaluation",
            split="val",
            batch_size=batch_size,
            role="us_holdout",
            checkpoint_path=restored_checkpoint_path,
            title="Us Holdout — saved square-crop model",
        )
        structured_analysis_path = run_structured_analysis(
            plan=plan,
            holdout_metrics=holdout_evaluation,
            attempt_directory=attempt_directory,
        )
        training_record["status"] = "completed"
        write_json_atomic(training_record_path, training_record)

        completion = {
            "status": "completed",
            "completed_at_utc": utc_now(),
            "condition": condition_name,
            "round_trip_check": round_trip,
            "fresh_reloaded_internal_tune_check": fresh_tune_check,
            "training_metrics_path": project_relative(training_record_path),
            "restored_checkpoint": project_relative(restored_checkpoint_path),
            "internal_tune_metrics_path": tune_evaluation["metrics_path"],
            "us_holdout_metrics_path": holdout_evaluation["metrics_path"],
            "us_holdout_predictions_path": holdout_evaluation["predictions_path"],
            "structured_analysis_path": structured_analysis_path,
        }
        write_json_atomic(attempt_directory / "completion.json", completion)
        write_attempt_status(attempt_directory, "completed", completion)
        keras.backend.clear_session()

    except Exception as error:
        write_attempt_status(
            attempt_directory,
            "failed",
            {
                "error": str(error),
                "traceback": traceback.format_exc(),
            },
        )
        raise


def valid_completion(
    attempt_directory: Path,
    *,
    expected_condition: str | None = None,
) -> dict[str, Any] | None:
    """Return a completion only if its identity and evidence still agree."""

    completion_path = attempt_directory / "completion.json"
    if not completion_path.is_file():
        return None

    completion = read_json_object(completion_path)
    if completion.get("status") != "completed":
        return None
    condition_name = completion.get("condition")
    if not isinstance(condition_name, str) or not condition_name:
        return None
    if expected_condition is not None and condition_name != expected_condition:
        return None
    if not completion.get("round_trip_check", {}).get("passed"):
        return None
    if not completion.get("fresh_reloaded_internal_tune_check", {}).get("passed"):
        return None

    required_paths = (
        "training_metrics_path",
        "restored_checkpoint",
        "internal_tune_metrics_path",
        "us_holdout_metrics_path",
        "us_holdout_predictions_path",
        "structured_analysis_path",
    )
    if not all(
        resolve_path(str(completion.get(name, ""))).is_file()
        for name in required_paths
    ):
        return None

    training_metrics = read_json_object(
        resolve_path(str(completion["training_metrics_path"]))
    )
    training_condition = training_metrics.get("condition", {})
    if (
        training_metrics.get("status") != "completed"
        or not isinstance(training_condition, Mapping)
        or training_condition.get("name") != condition_name
        or not training_metrics.get("round_trip_check", {}).get("passed")
        or not training_metrics.get(
            "fresh_reloaded_internal_tune_check", {}
        ).get("passed")
    ):
        return None

    return completion


def completed_attempt_for_condition(
    experiment_directory: Path,
    condition_name: str,
) -> tuple[Path, dict[str, Any]] | None:
    """Find the newest fully verified attempt for a condition."""

    condition_directory = experiment_directory / "runs" / condition_name
    if not condition_directory.is_dir():
        return None

    attempts = sorted(
        (
            path
            for path in condition_directory.iterdir()
            if path.is_dir() and path.name.startswith("attempt_")
        ),
        reverse=True,
    )

    for attempt_directory in attempts:
        completion = valid_completion(
            attempt_directory,
            expected_condition=condition_name,
        )
        if completion is not None:
            return attempt_directory, completion

    return None


def next_attempt_directory(
    experiment_directory: Path,
    condition_name: str,
) -> Path:
    """Create a new attempt number without overwriting an interrupted run."""

    condition_directory = experiment_directory / "runs" / condition_name
    condition_directory.mkdir(parents=True, exist_ok=True)
    existing_numbers = [
        int(path.name.removeprefix("attempt_"))
        for path in condition_directory.iterdir()
        if path.is_dir()
        and path.name.startswith("attempt_")
        and path.name.removeprefix("attempt_").isdigit()
    ]
    next_number = max(existing_numbers, default=0) + 1
    return condition_directory / f"attempt_{next_number:02d}"


def write_comparison(
    plan: dict[str, Any],
    experiment_directory: Path,
) -> None:
    """Aggregate both verified U.S.-holdout results into comparison files."""

    rows: list[dict[str, object]] = []

    for condition in plan["conditions"]:
        condition_name = str(condition["name"])
        found = completed_attempt_for_condition(experiment_directory, condition_name)
        if found is None:
            raise RuntimeError(
                f"Cannot compare; {condition_name} has no verified completion."
            )

        attempt_directory, completion = found
        holdout_metrics = read_json_object(
            resolve_path(str(completion["us_holdout_metrics_path"]))
        )
        training_metrics = read_json_object(
            resolve_path(str(completion["training_metrics_path"]))
        )
        report = dict(holdout_metrics["classification_report"])
        row: dict[str, object] = {
            "condition": condition_name,
            "description": condition["description"],
            "attempt": attempt_directory.name,
            "holdout_examples": holdout_metrics["number_of_examples"],
            "accuracy": holdout_metrics["accuracy"],
            "balanced_accuracy": holdout_metrics["balanced_accuracy"],
            "macro_f1": holdout_metrics["macro_f1"],
            "weighted_f1": holdout_metrics["weighted_f1"],
            "D00_recall": report["D00"]["recall"],
            "D10_recall": report["D10"]["recall"],
            "D20_recall": report["D20"]["recall"],
            "D40_recall": report["D40"]["recall"],
            "training_seconds": training_metrics["training_seconds"],
            "completed_epochs": training_metrics["completed_epochs"],
            "round_trip_passed": training_metrics["round_trip_check"]["passed"],
            "holdout_metrics_path": completion["us_holdout_metrics_path"],
            "structured_analysis_path": completion["structured_analysis_path"],
        }
        rows.append(row)

    baseline = next(
        row for row in rows if row["condition"] == "no_norway_india"
    )
    for row in rows:
        row["delta_macro_f1_vs_no_norway_india"] = (
            float(row["macro_f1"]) - float(baseline["macro_f1"])
        )
        row["delta_balanced_accuracy_vs_no_norway_india"] = (
            float(row["balanced_accuracy"])
            - float(baseline["balanced_accuracy"])
        )

    comparison = {
        "created_at_utc": utc_now(),
        "experiment_id": plan["experiment_id"],
        "evaluation_scope": (
            "Both saved-and-reloaded models are evaluated on the same "
            "untouched United_States validation subset. The test split was not used."
        ),
        "matched_arm_audit": plan["matched_arm_audit"],
        "rows": rows,
    }
    write_json_atomic(experiment_directory / "comparison.json", comparison)
    write_csv_atomic(
        experiment_directory / "comparison.csv",
        list(rows[0]),
        rows,
    )

    header = (
        "# Matched U.S. square-crop country comparison\n\n"
        "All values below come from the same untouched U.S.-only validation "
        "subset. Each checkpoint was explicitly saved, reloaded, and verified "
        "before evaluation. Both arms have the same training size, per-class "
        "counts, exact U.S. crops, and internal U.S. early-stopping set. The "
        "test split was not used.\n\n"
    )
    table_header = (
        "| Condition | Accuracy | Balanced accuracy | Macro F1 | Weighted F1 | "
        "D00 recall | D10 recall | D20 recall | D40 recall | Epochs |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    )
    table_rows = "".join(
        "| {condition} | {accuracy:.4f} | {balanced_accuracy:.4f} | "
        "{macro_f1:.4f} | {weighted_f1:.4f} | {D00_recall:.4f} | "
        "{D10_recall:.4f} | {D20_recall:.4f} | {D40_recall:.4f} | "
        "{completed_epochs} |\n".format(**row)
        for row in rows
    )
    interpretation = (
        "\nInterpret results only after considering the macro-F1 and per-class "
        "recall changes, not accuracy alone. Because Norway/India crops replace "
        "same-class crops one-for-one, training-set size and class balance are "
        "controlled in this comparison.\n"
    )
    write_text_atomic(
        experiment_directory / "comparison.md",
        header + table_header + table_rows + interpretation,
    )


def supervisor_main(args: argparse.Namespace) -> None:
    """Create/resume the plan, then execute two isolated sequential arms."""

    os.chdir(PROJECT_ROOT)
    experiment_id = args.experiment_id or (
        "us_domain_ablation_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    experiment_directory = resolve_path(args.experiments_directory) / experiment_id
    state_path = experiment_directory / "state.json"

    if args.resume:
        if not experiment_directory.is_dir():
            raise FileNotFoundError(
                f"Cannot resume; experiment directory does not exist: {experiment_directory}"
            )
        plan = load_and_validate_resume_plan(args, experiment_directory)
    else:
        if experiment_directory.exists():
            raise FileExistsError(
                f"Experiment directory already exists: {experiment_directory}. "
                "Use --resume with the same immutable settings or choose a new ID."
            )
        experiment_directory.mkdir(parents=True)
        update_state(state_path, "running", "square_crop_validation")
        fieldnames, records, metadata = validate_square_dataset(
            args.square_dataset_directory,
            experiment_directory / "qa",
        )
        save_square_crop_contact_sheet(
            records,
            experiment_directory / "qa" / "square_crop_contact_sheet.png",
        )
        plan = create_experiment_plan(
            args=args,
            experiment_directory=experiment_directory,
            fieldnames=fieldnames,
            records=records,
            metadata=metadata,
        )
        update_state(state_path, "planned", "plan_created")

    validate_planned_matched_arms(plan)

    if args.plan_only:
        print(f"Validated plan only: {experiment_directory / 'plan.json'}")
        return

    try:
        with exclusive_file_lock(
            experiment_directory / ".runner.lock",
            purpose="matched U.S. country-comparison supervisor",
        ):
            for condition in plan["conditions"]:
                condition_name = str(condition["name"])
                existing_completion = completed_attempt_for_condition(
                    experiment_directory,
                    condition_name,
                )

                if existing_completion is not None:
                    attempt_directory, _ = existing_completion
                    print(
                        f"Skipping verified {condition_name}: {attempt_directory}",
                        flush=True,
                    )
                    continue

                attempt_directory = next_attempt_directory(
                    experiment_directory,
                    condition_name,
                )
                update_state(
                    state_path,
                    "running",
                    condition_name,
                    {"attempt_directory": project_relative(attempt_directory)},
                )
                run_condition(
                    plan=plan,
                    condition_name=condition_name,
                    attempt_directory=attempt_directory,
                    allow_cpu=args.allow_cpu,
                    verbose=args.verbose,
                )

                if valid_completion(
                    attempt_directory,
                    expected_condition=condition_name,
                ) is None:
                    raise RuntimeError(
                        f"{condition_name} did not create a complete "
                        "verified artifact set."
                    )
                update_state(state_path, "completed", condition_name)

            write_comparison(plan, experiment_directory)
            update_state(state_path, "completed", "comparison_written")
            print(
                "\nExperiment completed successfully. "
                f"Comparison: {experiment_directory / 'comparison.md'}"
            )

    except FileLockError as error:
        raise RuntimeError(
            "Experiment appears to be active or was interrupted: "
            f"{experiment_directory / '.runner.lock'}. Inspect it before "
            "removing the lock manually."
        ) from error

    except Exception as error:
        update_state(
            state_path,
            "failed",
            "supervisor",
            {"error": str(error), "traceback": traceback.format_exc()},
        )
        raise


def main() -> None:
    """Run the sequential matched square-crop country experiment."""

    args = parse_arguments()
    supervisor_main(args)


if __name__ == "__main__":
    main()

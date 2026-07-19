"""Create leakage-resistant train, validation, and test splits."""

from __future__ import annotations

import csv
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.datasets.record_integrity import assert_record_sets_disjoint
from src.utils.experiment_artifacts import write_csv_atomic


MANIFEST_PATH = Path("data/processed/image_manifest.csv")
OUTPUT_DIRECTORY = Path("data/splits")

RANDOM_SEED = 42
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15

# Nearby numbered images may come from the same road sequence.
SEQUENCE_BLOCK_SIZE = 100

TARGET_LABELS = ("D00", "D10", "D20", "D40")


def get_sequence_group(row: dict[str, str]) -> str:
    """Group nearby image numbers to reduce sequence leakage."""

    image_stem = Path(row["image_path"]).stem
    match = re.search(r"_(\d+)$", image_stem)

    if match is None:
        raise ValueError(
            f"Could not extract an image number from: {image_stem}"
        )

    image_number = int(match.group(1))
    block_number = image_number // SEQUENCE_BLOCK_SIZE

    return f"{row['country']}_{block_number:04d}"


def assign_splits(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Assign complete sequence groups to dataset splits."""

    grouped_rows: dict[
        tuple[str, str],
        list[dict[str, str]],
    ] = defaultdict(list)

    for row in rows:
        sequence_group = get_sequence_group(row)
        row["sequence_group"] = sequence_group

        group_key = (row["country"], sequence_group)
        grouped_rows[group_key].append(row)

    random_generator = random.Random(RANDOM_SEED)

    countries = sorted({row["country"] for row in rows})

    for country in countries:
        country_groups = [
            group_key
            for group_key in grouped_rows
            if group_key[0] == country
        ]

        # Sorting before shuffling makes the result reproducible.
        country_groups.sort()
        random_generator.shuffle(country_groups)

        number_of_groups = len(country_groups)
        validation_groups = round(
            number_of_groups * VALIDATION_RATIO
        )
        test_groups = round(number_of_groups * TEST_RATIO)

        for index, group_key in enumerate(country_groups):
            if index < validation_groups:
                split = "val"
            elif index < validation_groups + test_groups:
                split = "test"
            else:
                split = "train"

            for row in grouped_rows[group_key]:
                row["split"] = split

    return rows


def verify_no_group_leakage(
    rows: list[dict[str, str]],
) -> None:
    """Ensure a sequence group appears in only one split."""

    rows_by_split = {
        split: [row for row in rows if row["split"] == split]
        for split in ("train", "val", "test")
    }
    assert_record_sets_disjoint(
        rows_by_split,
        identity_fields=("sequence_group",),
        description="Sequence groups found in multiple splits",
    )


def print_split_summary(rows: list[dict[str, str]]) -> None:
    """Print image and object counts for each split."""

    for split in ("train", "val", "test"):
        split_rows = [
            row for row in rows if row["split"] == split
        ]

        class_counts = Counter()

        for row in split_rows:
            for label in TARGET_LABELS:
                class_counts[label] += int(row[f"{label}_count"])

        print(f"\n{split.upper()}")
        print("-" * len(split))
        print(f"Images: {len(split_rows):,}")

        for label in TARGET_LABELS:
            print(f"{label}: {class_counts[label]:,} objects")


def write_split_files(rows: list[dict[str, str]]) -> None:
    """Write one CSV manifest for each dataset split."""

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    for split in ("train", "val", "test"):
        output_path = OUTPUT_DIRECTORY / f"{split}.csv"
        split_rows = [
            row for row in rows if row["split"] == split
        ]

        write_csv_atomic(output_path, fieldnames, split_rows)

        print(f"Wrote {output_path}")


def main() -> None:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}\n"
            "Run python -m scripts.build_image_manifest first."
        )

    with MANIFEST_PATH.open(
        newline="",
        encoding="utf-8",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        raise ValueError(f"Manifest is empty: {MANIFEST_PATH}")

    rows = assign_splits(rows)
    verify_no_group_leakage(rows)
    print_split_summary(rows)
    write_split_files(rows)

    print("\nSplit creation complete.")
    print("No sequence group appears in multiple splits.")


if __name__ == "__main__":
    main()

"""Build an image-level inventory for leakage-safe dataset splitting."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from src.datasets.annotation_parser import parse_annotation
from src.utils.classes import CLASS_TO_INDEX


DATASET_ROOT = Path("data/raw/RDD2022")
OUTPUT_PATH = Path("data/processed/image_manifest.csv")

TARGET_LABELS = set(CLASS_TO_INDEX)


def find_image(xml_path: Path, filename: str) -> Path | None:
    """Find the image associated with an annotation."""

    # The XML normally lives in:
    # country/train/annotations/xmls/example.xml
    train_directory = xml_path.parents[2]
    image_directory = train_directory / "images"

    image_path = image_directory / filename

    if image_path.is_file():
        return image_path

    return None


def main() -> None:
    xml_paths = sorted(DATASET_ROOT.glob("*/train/annotations/xmls/*.xml"))

    if not xml_paths:
        raise FileNotFoundError(
            f"No XML annotations found under {DATASET_ROOT}"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    invalid_annotations = 0
    missing_images = 0

    for xml_path in xml_paths:
        try:
            annotation = parse_annotation(xml_path)
        except (ValueError, FileNotFoundError) as error:
            invalid_annotations += 1
            print(f"Skipping invalid annotation: {error}")
            continue

        image_path = find_image(xml_path, annotation.filename)

        if image_path is None:
            missing_images += 1
            print(f"Missing image for: {xml_path}")
            continue

        label_counts = Counter(
            damage_object.label
            for damage_object in annotation.objects
        )

        target_count = sum(
            count
            for label, count in label_counts.items()
            if label in TARGET_LABELS
        )

        unknown_labels = sorted(
            label
            for label in label_counts
            if label not in TARGET_LABELS
        )

        country = xml_path.relative_to(DATASET_ROOT).parts[0]

        rows.append(
            {
                "country": country,
                "image_path": image_path.as_posix(),
                "annotation_path": xml_path.as_posix(),
                "D00_count": label_counts.get("D00", 0),
                "D10_count": label_counts.get("D10", 0),
                "D20_count": label_counts.get("D20", 0),
                "D40_count": label_counts.get("D40", 0),
                "target_count": target_count,
                "has_target_damage": int(target_count > 0),
                "unknown_labels": ";".join(unknown_labels),
                "has_unknown_labels": int(bool(unknown_labels)),
            }
        )

    fieldnames = [
        "country",
        "image_path",
        "annotation_path",
        "D00_count",
        "D10_count",
        "D20_count",
        "D40_count",
        "target_count",
        "has_target_damage",
        "unknown_labels",
        "has_unknown_labels",
    ]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\nManifest complete")
    print("-----------------")
    print(f"Rows written: {len(rows):,}")
    print(f"Invalid annotations skipped: {invalid_annotations:,}")
    print(f"Missing images skipped: {missing_images:,}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

"""Calculate basic statistics from all RDD2022 training annotations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from src.datasets.annotation_parser import parse_annotation
from src.utils.classes import CLASS_DESCRIPTIONS, CLASS_TO_INDEX


def analyze_annotations(dataset_root: Path) -> None:
    xml_paths = sorted(
        dataset_root.glob("*/train/annotations/xmls/*.xml")
    )

    if not xml_paths:
        raise FileNotFoundError(
            f"No annotation XML files found under {dataset_root}"
        )

    class_counts: Counter[str] = Counter()
    country_class_counts: dict[str, Counter[str]] = defaultdict(Counter)

    empty_annotation_count = 0
    missing_image_count = 0
    invalid_annotations: list[tuple[Path, str]] = []

    print(f"Found {len(xml_paths):,} XML annotation files.")

    for index, xml_path in enumerate(xml_paths, start=1):
        country = xml_path.relative_to(dataset_root).parts[0]

        try:
            annotation = parse_annotation(xml_path)
        except (OSError, ValueError) as error:
            invalid_annotations.append((xml_path, str(error)))
            continue

        image_path = (
            xml_path.parents[2]
            / "images"
            / annotation.filename
        )

        if not image_path.is_file():
            missing_image_count += 1

        if not annotation.objects:
            empty_annotation_count += 1

        for damage_object in annotation.objects:
            class_counts[damage_object.label] += 1
            country_class_counts[country][damage_object.label] += 1

        if index % 5_000 == 0:
            print(f"Processed {index:,} / {len(xml_paths):,} annotations...")

    total_objects = sum(class_counts.values())

    print("\nDataset summary")
    print("----------------")
    print(f"Annotation files: {len(xml_paths):,}")
    print(f"Damage objects: {total_objects:,}")
    print(f"Empty annotations: {empty_annotation_count:,}")
    print(f"Missing matching images: {missing_image_count:,}")
    print(f"Invalid annotations: {len(invalid_annotations):,}")

    print("\nClass distribution")
    print("------------------")

    for class_name in CLASS_TO_INDEX:
        count = class_counts[class_name]
        percentage = (
            100 * count / total_objects
            if total_objects > 0
            else 0
        )
        description = CLASS_DESCRIPTIONS[class_name]

        print(
            f"{class_name} ({description}): "
            f"{count:,} objects ({percentage:.2f}%)"
        )

    unknown_labels = {
        label: count
        for label, count in class_counts.items()
        if label not in CLASS_TO_INDEX
    }

    if unknown_labels:
        print("\nUnknown labels")
        print("--------------")
        for label, count in sorted(unknown_labels.items()):
            print(f"{label}: {count:,}")

    print("\nObjects by country and class")
    print("----------------------------")

    header = f"{'Country':<20} {'D00':>8} {'D10':>8} {'D20':>8} {'D40':>8}"
    print(header)
    print("-" * len(header))

    for country in sorted(country_class_counts):
        counts = country_class_counts[country]

        print(
            f"{country:<20} "
            f"{counts['D00']:>8,} "
            f"{counts['D10']:>8,} "
            f"{counts['D20']:>8,} "
            f"{counts['D40']:>8,}"
        )

    if invalid_annotations:
        print("\nFirst invalid annotations")
        print("-------------------------")

        for xml_path, error_message in invalid_annotations[:10]:
            print(f"{xml_path}: {error_message}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze RDD2022 training annotations."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/raw/RDD2022"),
    )
    args = parser.parse_args()

    analyze_annotations(args.dataset_root)


if __name__ == "__main__":
    main()
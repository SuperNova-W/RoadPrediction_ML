"""Create cropped road-damage images for classification."""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.datasets.annotation_parser import parse_annotation
from src.utils.classes import CLASS_TO_INDEX


SPLIT_DIRECTORY = Path("data/splits")
CROP_DIRECTORY = Path("data/processed/classification")
CROP_MANIFEST_PATH = Path("data/processed/classification_crops.csv")

TARGET_LABELS = set(CLASS_TO_INDEX)

# Include a small amount of surrounding road context.
PADDING_RATIO = 0.10

SPLIT_NAMES = ("train", "val", "test")


def calculate_crop_coordinates(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Add context around a box and constrain it to the image."""

    box_width = xmax - xmin
    box_height = ymax - ymin

    horizontal_padding = box_width * PADDING_RATIO
    vertical_padding = box_height * PADDING_RATIO

    left = max(0, math.floor(xmin - horizontal_padding))
    top = max(0, math.floor(ymin - vertical_padding))
    right = min(
        image_width,
        math.ceil(xmax + horizontal_padding),
    )
    bottom = min(
        image_height,
        math.ceil(ymax + vertical_padding),
    )

    return left, top, right, bottom


def load_split_rows(split: str) -> list[dict[str, str]]:
    """Load the image-level manifest for one split."""

    split_path = SPLIT_DIRECTORY / f"{split}.csv"

    if not split_path.is_file():
        raise FileNotFoundError(
            f"Split manifest not found: {split_path}"
        )

    with split_path.open(
        newline="",
        encoding="utf-8",
    ) as csv_file:
        return list(csv.DictReader(csv_file))


def main() -> None:
    CROP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CROP_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    class_counts: Counter[str] = Counter()

    skipped_images = 0
    skipped_crops = 0
    processed_images = 0

    for split in SPLIT_NAMES:
        split_rows = load_split_rows(split)

        for label in TARGET_LABELS:
            (CROP_DIRECTORY / split / label).mkdir(
                parents=True,
                exist_ok=True,
            )

        for row in split_rows:
            image_path = Path(row["image_path"])
            annotation_path = Path(row["annotation_path"])

            try:
                annotation = parse_annotation(annotation_path)

                with Image.open(image_path) as opened_image:
                    image = opened_image.convert("RGB")

            except (
                FileNotFoundError,
                OSError,
                UnidentifiedImageError,
                ValueError,
            ) as error:
                skipped_images += 1
                print(f"Skipping image: {error}")
                continue

            for object_index, damage_object in enumerate(
                annotation.objects
            ):
                if damage_object.label not in TARGET_LABELS:
                    continue

                box = damage_object.bounding_box

                left, top, right, bottom = (
                    calculate_crop_coordinates(
                        xmin=box.xmin,
                        ymin=box.ymin,
                        xmax=box.xmax,
                        ymax=box.ymax,
                        image_width=image.width,
                        image_height=image.height,
                    )
                )

                if right <= left or bottom <= top:
                    skipped_crops += 1
                    print(
                        "Skipping invalid crop after clipping: "
                        f"{image_path}, object {object_index}"
                    )
                    continue

                crop = image.crop((left, top, right, bottom))

                crop_filename = (
                    f"{image_path.stem}_"
                    f"object_{object_index:02d}.jpg"
                )

                crop_path = (
                    CROP_DIRECTORY
                    / split
                    / damage_object.label
                    / crop_filename
                )

                crop.save(crop_path, format="JPEG", quality=95)

                manifest_rows.append(
                    {
                        "split": split,
                        "country": row["country"],
                        "source_image_path": image_path.as_posix(),
                        "annotation_path": annotation_path.as_posix(),
                        "crop_path": crop_path.as_posix(),
                        "label": damage_object.label,
                        "class_index": damage_object.class_index,
                        "xmin": box.xmin,
                        "ymin": box.ymin,
                        "xmax": box.xmax,
                        "ymax": box.ymax,
                        "crop_left": left,
                        "crop_top": top,
                        "crop_right": right,
                        "crop_bottom": bottom,
                        "sequence_group": row["sequence_group"],
                    }
                )

                class_counts[
                    f"{split}_{damage_object.label}"
                ] += 1

            processed_images += 1

            if processed_images % 2_500 == 0:
                print(
                    f"Processed {processed_images:,} images..."
                )

    fieldnames = [
        "split",
        "country",
        "source_image_path",
        "annotation_path",
        "crop_path",
        "label",
        "class_index",
        "xmin",
        "ymin",
        "xmax",
        "ymax",
        "crop_left",
        "crop_top",
        "crop_right",
        "crop_bottom",
        "sequence_group",
    ]

    with CROP_MANIFEST_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("\nClassification crop summary")
    print("---------------------------")
    print(f"Source images processed: {processed_images:,}")
    print(f"Images skipped: {skipped_images:,}")
    print(f"Crops skipped: {skipped_crops:,}")
    print(f"Total crops created: {len(manifest_rows):,}")

    for split in SPLIT_NAMES:
        print(f"\n{split.upper()}")

        for label in sorted(TARGET_LABELS):
            count = class_counts[f"{split}_{label}"]
            print(f"{label}: {count:,}")

    print(f"\nCrop manifest: {CROP_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

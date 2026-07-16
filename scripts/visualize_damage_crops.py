"""Display damage crops extracted from one RDD2022 annotation."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

from src.datasets.annotation_parser import BoundingBox, parse_annotation


def box_to_integer_coordinates(
    box: BoundingBox,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Convert decimal coordinates into safe PIL crop coordinates."""

    left = max(0, math.floor(box.xmin))
    top = max(0, math.floor(box.ymin))
    right = min(image_width, math.ceil(box.xmax))
    bottom = min(image_height, math.ceil(box.ymax))

    if right <= left or bottom <= top:
        raise ValueError(f"Bounding box produces an empty crop: {box}")

    return left, top, right, bottom


def visualize_damage_crops(xml_path: Path) -> None:
    annotation = parse_annotation(xml_path)

    train_directory = xml_path.parents[2]
    image_path = train_directory / "images" / annotation.filename

    if not image_path.is_file():
        raise FileNotFoundError(f"Matching image not found: {image_path}")

    if not annotation.objects:
        print(f"No damage objects found in {xml_path}")
        return

    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")

    object_count = len(annotation.objects)
    columns = min(3, object_count)
    rows = math.ceil(object_count / columns)

    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(5 * columns, 4 * rows),
        squeeze=False,
    )

    # Hide every subplot before filling the required ones.
    for axis in axes.flat:
        axis.axis("off")

    for index, damage_object in enumerate(annotation.objects):
        coordinates = box_to_integer_coordinates(
            box=damage_object.bounding_box,
            image_width=image.width,
            image_height=image.height,
        )

        crop = image.crop(coordinates)
        axis = axes.flat[index]

        axis.imshow(crop)
        axis.set_title(
            f"Object {index + 1}: {damage_object.label}\n"
            f"Crop size: {crop.width} × {crop.height}"
        )
        axis.axis("off")

    figure.suptitle(annotation.filename, fontsize=14)
    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display annotated road-damage crops."
    )
    parser.add_argument(
        "xml_path",
        type=Path,
        help="Path to one annotation XML file.",
    )
    args = parser.parse_args()

    visualize_damage_crops(args.xml_path)


if __name__ == "__main__":
    main()
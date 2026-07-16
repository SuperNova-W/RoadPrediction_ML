"""Display one RDD2022 image with its ground-truth bounding boxes."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

from src.datasets.annotation_parser import parse_annotation


CLASS_COLORS = {
    "D00": "red",
    "D10": "blue",
    "D20": "orange",
    "D40": "lime",
}


def visualize_annotation(xml_path: Path) -> None:
    annotation = parse_annotation(xml_path)

    # The XML is inside train/annotations/xmls/.
    train_directory = xml_path.parents[2]
    image_path = train_directory / "images" / annotation.filename

    if not image_path.is_file():
        raise FileNotFoundError(f"Matching image not found: {image_path}")

    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")

    if image.size != (annotation.width, annotation.height):
        raise ValueError(
            f"XML size is {(annotation.width, annotation.height)}, "
            f"but image size is {image.size}."
        )

    figure, axis = plt.subplots(figsize=(14, 8))
    axis.imshow(image)

    for damage_object in annotation.objects:
        box = damage_object.bounding_box
        color = CLASS_COLORS.get(damage_object.label, "white")

        rectangle = Rectangle(
            xy=(box.xmin, box.ymin),
            width=box.width,
            height=box.height,
            linewidth=2,
            edgecolor=color,
            facecolor="none",
        )
        axis.add_patch(rectangle)

        axis.text(
            box.xmin,
            max(0, box.ymin - 10),
            damage_object.label,
            color="white",
            fontsize=10,
            backgroundcolor=color,
        )

    axis.set_title(
        f"{annotation.filename} — "
        f"{len(annotation.objects)} annotated objects"
    )
    axis.axis("off")

    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "xml_path",
        type=Path,
        help="Path to one RDD2022 annotation XML.",
    )
    args = parser.parse_args()

    visualize_annotation(args.xml_path)


if __name__ == "__main__":
    main()
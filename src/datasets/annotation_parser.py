"""Parse Pascal VOC-style XML annotations from RDD2022."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
import warnings
from dataclasses import dataclass
from pathlib import Path

from src.utils.classes import CLASS_TO_INDEX


@dataclass(frozen=True)
class BoundingBox:
    """Coordinates of one damaged region."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


@dataclass(frozen=True)
class DamageObject:
    """One labeled damage object inside an image."""

    label: str
    class_index: int | None
    bounding_box: BoundingBox


@dataclass(frozen=True)
class ImageAnnotation:
    """All annotation information associated with one image."""

    filename: str
    width: int
    height: int
    objects: tuple[DamageObject, ...]


def required_text(element: ET.Element, tag: str) -> str:
    """Read a required XML value and raise a clear error if it is missing."""

    value = element.findtext(tag)

    if value is None or not value.strip():
        raise ValueError(f"Missing required XML field: {tag}")

    return value.strip()


def parse_annotation(xml_path: Path) -> ImageAnnotation:
    """Parse one RDD2022 annotation XML file."""

    if not xml_path.is_file():
        raise FileNotFoundError(f"Annotation does not exist: {xml_path}")

    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"Invalid XML file: {xml_path}") from error

    filename = required_text(root, "filename")

    size_element = root.find("size")
    if size_element is None:
        raise ValueError(f"Missing image size in {xml_path}")

    width = int(float(required_text(size_element, "width")))
    height = int(float(required_text(size_element, "height")))

    damage_objects: list[DamageObject] = []

    for object_element in root.findall("object"):
        label = required_text(object_element, "name")

        box_element = object_element.find("bndbox")
        if box_element is None:
            raise ValueError(f"Missing bounding box in {xml_path}")

        bounding_box = BoundingBox(
            xmin=float(required_text(box_element, "xmin")),
            ymin=float(required_text(box_element, "ymin")),
            xmax=float(required_text(box_element, "xmax")),
            ymax=float(required_text(box_element, "ymax")),
        )

        if bounding_box.width <= 0 or bounding_box.height <= 0:
            warnings.warn(
                f"Skipping invalid bounding box in {xml_path}: "
                f"{bounding_box}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue

        damage_objects.append(
            DamageObject(
                label=label,
                # Unknown labels are preserved with index None.
                class_index=CLASS_TO_INDEX.get(label),
                bounding_box=bounding_box,
            )
        )

    return ImageAnnotation(
        filename=filename,
        width=width,
        height=height,
        objects=tuple(damage_objects),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect one RDD2022 XML annotation."
    )
    parser.add_argument(
        "xml_path",
        type=Path,
        help="Path to one annotation XML file.",
    )
    args = parser.parse_args()

    annotation = parse_annotation(args.xml_path)

    print(f"Image: {annotation.filename}")
    print(f"Image size: {annotation.width} × {annotation.height}")
    print(f"Number of damage objects: {len(annotation.objects)}")

    for object_number, damage_object in enumerate(
        annotation.objects,
        start=1,
    ):
        box = damage_object.bounding_box

        print(
            f"Object {object_number}: "
            f"label={damage_object.label}, "
            f"class_index={damage_object.class_index}, "
            f"box=({box.xmin:.2f}, {box.ymin:.2f}, "
            f"{box.xmax:.2f}, {box.ymax:.2f}), "
            f"size=({box.width:.2f} × {box.height:.2f})"
        )


if __name__ == "__main__":
    main()

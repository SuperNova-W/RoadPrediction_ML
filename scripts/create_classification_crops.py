"""Build a versioned square-crop dataset for road-damage classification."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from src.datasets.annotation_parser import parse_annotation
from src.datasets.crop_integrity import validate_crop_file_integrity
from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX
from src.utils.experiment_artifacts import (
    sha256_file,
    utc_now,
    write_csv_atomic,
    write_json_atomic,
)


SPLIT_DIRECTORY = Path("data/splits")
DEFAULT_OUTPUT_DIRECTORY = Path(
    "data/processed/classification_square_v1"
)
DATASET_VERSION = "square_context_v1"
MANIFEST_FILENAME = "manifest.csv"
METADATA_FILENAME = "metadata.json"

# The square side is the longest annotation dimension plus 30% total context.
CONTEXT_RATIO = 0.30
JPEG_QUALITY = 95
SPLIT_NAMES = ("train", "val", "test")
TARGET_LABELS = set(CLASS_NAMES)
MANIFEST_FIELDNAMES = (
    "split",
    "country",
    "source_image_path",
    "annotation_path",
    "object_index",
    "source_object_id",
    "crop_relative_path",
    "crop_path",
    "label",
    "class_index",
    "xmin",
    "ymin",
    "xmax",
    "ymax",
    "image_width",
    "image_height",
    "requested_side",
    "crop_side",
    "crop_mode",
    "crop_left",
    "crop_top",
    "crop_right",
    "crop_bottom",
    "source_crop_left",
    "source_crop_top",
    "source_crop_right",
    "source_crop_bottom",
    "padding_left",
    "padding_top",
    "padding_right",
    "padding_bottom",
    "context_ratio",
    "sequence_group",
)


@dataclass(frozen=True)
class SquareCropPlan:
    """A square crop window and any edge padding required to realize it."""

    crop_left: int
    crop_top: int
    crop_right: int
    crop_bottom: int
    source_crop_left: int
    source_crop_top: int
    source_crop_right: int
    source_crop_bottom: int
    padding_left: int
    padding_top: int
    padding_right: int
    padding_bottom: int
    requested_side: int
    crop_mode: str

    @property
    def crop_side(self) -> int:
        """Return the final width and height of the square crop."""

        return self.crop_right - self.crop_left

    @property
    def uses_edge_padding(self) -> bool:
        """Return whether this plan needs nonblack edge-replication padding."""

        return any(
            (
                self.padding_left,
                self.padding_top,
                self.padding_right,
                self.padding_bottom,
            )
        )


def parse_arguments() -> argparse.Namespace:
    """Read crop-build options from the command line."""

    parser = argparse.ArgumentParser(
        description="Build square contextual damage-classification crops."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=(
            "Versioned output directory. It must not already exist so the "
            "legacy crop dataset remains untouched."
        ),
    )
    parser.add_argument(
        "--context-ratio",
        type=float,
        default=CONTEXT_RATIO,
        help=(
            "Total additional square context relative to the longest box "
            "dimension. Must be between 0.25 and 0.40."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate every source object and report the planned build only.",
    )

    args = parser.parse_args()

    if not 0.25 <= args.context_ratio <= 0.40:
        parser.error("--context-ratio must be between 0.25 and 0.40")

    return args


def load_split_rows(split: str) -> list[dict[str, str]]:
    """Load one fixed image-level split manifest."""

    split_path = SPLIT_DIRECTORY / f"{split}.csv"

    if not split_path.is_file():
        raise FileNotFoundError(
            f"Split manifest not found: {split_path}"
        )

    with split_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def integer_box_envelope(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Return integer bounds that fully contain a valid source annotation."""

    coordinates = (xmin, ymin, xmax, ymax)

    if not all(math.isfinite(value) for value in coordinates):
        raise ValueError(f"Bounding box has non-finite coordinates: {coordinates}")
    if xmax <= xmin or ymax <= ymin:
        raise ValueError(f"Bounding box has no area: {coordinates}")
    if xmin < 0 or ymin < 0 or xmax > image_width or ymax > image_height:
        raise ValueError(
            "Bounding box extends outside the source image: "
            f"box={coordinates}, image={image_width}x{image_height}"
        )

    left = math.floor(xmin)
    top = math.floor(ymin)
    right = math.ceil(xmax)
    bottom = math.ceil(ymax)

    if right <= left or bottom <= top:
        raise ValueError(
            f"Bounding box has an empty integer envelope: {coordinates}"
        )

    return left, top, right, bottom


def choose_axis_start(
    box_start: int,
    box_end: int,
    box_center: float,
    side: int,
    image_length: int,
) -> int:
    """Center a crop while preserving the annotation and native pixels."""

    valid_start_minimum = box_end - side
    valid_start_maximum = box_start

    # When the square fits along this axis, shift it inside the image.
    if side <= image_length:
        valid_start_minimum = max(valid_start_minimum, 0)
        valid_start_maximum = min(
            valid_start_maximum,
            image_length - side,
        )

    if valid_start_minimum > valid_start_maximum:
        raise ValueError(
            "A square crop cannot contain the annotation on one image axis."
        )

    centered_start = math.floor(box_center - side / 2)

    return min(
        max(centered_start, valid_start_minimum),
        valid_start_maximum,
    )


def calculate_square_crop_plan(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    image_width: int,
    image_height: int,
    context_ratio: float = CONTEXT_RATIO,
) -> SquareCropPlan:
    """Plan a full-annotation square crop with minimum artificial padding.

    Most crops are shifted inside the source image. If extra context cannot fit,
    the crop uses the largest native square that still contains the annotation.
    For the rare annotations wider or taller than the source's short side, an
    edge-replication fallback preserves the full annotation without black bars.
    """

    if image_width <= 0 or image_height <= 0:
        raise ValueError(
            f"Image dimensions must be positive: {image_width}x{image_height}"
        )
    if not 0.0 <= context_ratio:
        raise ValueError("Context ratio must not be negative")

    box_left, box_top, box_right, box_bottom = integer_box_envelope(
        xmin=xmin,
        ymin=ymin,
        xmax=xmax,
        ymax=ymax,
        image_width=image_width,
        image_height=image_height,
    )
    envelope_side = max(box_right - box_left, box_bottom - box_top)
    requested_side = max(
        envelope_side,
        math.ceil(
            max(xmax - xmin, ymax - ymin) * (1.0 + context_ratio)
        ),
    )
    maximum_native_square_side = min(image_width, image_height)

    if envelope_side <= maximum_native_square_side:
        crop_side = min(requested_side, maximum_native_square_side)
        crop_mode = (
            "in_image"
            if crop_side == requested_side
            else "context_limited"
        )
    else:
        # No source-native square can contain the full annotation. Keep the
        # smallest valid square and replicate only the missing source edge.
        crop_side = envelope_side
        crop_mode = "edge_padded"

    crop_left = choose_axis_start(
        box_start=box_left,
        box_end=box_right,
        box_center=(xmin + xmax) / 2,
        side=crop_side,
        image_length=image_width,
    )
    crop_top = choose_axis_start(
        box_start=box_top,
        box_end=box_bottom,
        box_center=(ymin + ymax) / 2,
        side=crop_side,
        image_length=image_height,
    )
    crop_right = crop_left + crop_side
    crop_bottom = crop_top + crop_side

    if (
        crop_left > box_left
        or crop_top > box_top
        or crop_right < box_right
        or crop_bottom < box_bottom
    ):
        raise RuntimeError("Square-crop plan does not contain its annotation.")

    source_crop_left = max(0, crop_left)
    source_crop_top = max(0, crop_top)
    source_crop_right = min(image_width, crop_right)
    source_crop_bottom = min(image_height, crop_bottom)

    padding_left = source_crop_left - crop_left
    padding_top = source_crop_top - crop_top
    padding_right = crop_right - source_crop_right
    padding_bottom = crop_bottom - source_crop_bottom

    if source_crop_right <= source_crop_left or source_crop_bottom <= source_crop_top:
        raise RuntimeError("Square-crop plan has no intersection with the image.")

    if crop_mode != "edge_padded" and any(
        (padding_left, padding_top, padding_right, padding_bottom)
    ):
        raise RuntimeError(
            "Native square crop unexpectedly requires artificial padding."
        )

    return SquareCropPlan(
        crop_left=crop_left,
        crop_top=crop_top,
        crop_right=crop_right,
        crop_bottom=crop_bottom,
        source_crop_left=source_crop_left,
        source_crop_top=source_crop_top,
        source_crop_right=source_crop_right,
        source_crop_bottom=source_crop_bottom,
        padding_left=padding_left,
        padding_top=padding_top,
        padding_right=padding_right,
        padding_bottom=padding_bottom,
        requested_side=requested_side,
        crop_mode=crop_mode,
    )


def extract_square_crop(
    image: Image.Image,
    plan: SquareCropPlan,
) -> Image.Image:
    """Extract a plan's square pixels, using edge replication only if needed."""

    crop = image.crop(
        (
            plan.source_crop_left,
            plan.source_crop_top,
            plan.source_crop_right,
            plan.source_crop_bottom,
        )
    )

    if plan.uses_edge_padding:
        crop_array = np.asarray(crop)
        crop_array = np.pad(
            crop_array,
            (
                (plan.padding_top, plan.padding_bottom),
                (plan.padding_left, plan.padding_right),
                (0, 0),
            ),
            mode="edge",
        )
        crop = Image.fromarray(crop_array)

    if crop.size != (plan.crop_side, plan.crop_side):
        raise RuntimeError(
            "Saved crop is not square: "
            f"expected={plan.crop_side}, actual={crop.size}"
        )

    return crop


def output_paths(output_directory: Path) -> tuple[Path, Path]:
    """Return the self-contained manifest and metadata paths for a dataset."""

    return (
        output_directory / MANIFEST_FILENAME,
        output_directory / METADATA_FILENAME,
    )


def create_staging_directory(output_directory: Path) -> Path:
    """Create a non-destructive same-filesystem staging directory."""

    if output_directory.exists():
        raise FileExistsError(
            "Refusing to overwrite an existing crop dataset: "
            f"{output_directory}"
        )

    staging_directory = output_directory.with_name(
        f".{output_directory.name}_staging"
    )

    if staging_directory.exists():
        raise FileExistsError(
            "A previous staged build exists and was preserved for diagnosis: "
            f"{staging_directory}"
        )

    staging_directory.mkdir(parents=True)

    return staging_directory


def build_crop_records(
    output_directory: Path,
    context_ratio: float,
    staging_directory: Path | None,
) -> tuple[list[dict[str, object]], Counter[str]]:
    """Create all crop records and optionally write JPEGs into staging."""

    records: list[dict[str, object]] = []
    mode_counts: Counter[str] = Counter()
    processed_images = 0

    for split in SPLIT_NAMES:
        split_rows = load_split_rows(split)

        for row in split_rows:
            image_path = Path(row["image_path"])
            annotation_path = Path(row["annotation_path"])

            try:
                annotation = parse_annotation(annotation_path)

                with Image.open(image_path) as opened_image:
                    image_width, image_height = opened_image.size

                    if (
                        annotation.width != image_width
                        or annotation.height != image_height
                    ):
                        raise ValueError(
                            "Annotation and source image dimensions disagree: "
                            f"annotation={annotation.width}x{annotation.height}, "
                            f"image={image_width}x{image_height}"
                        )

                    source_image = (
                        opened_image.convert("RGB")
                        if staging_directory is not None
                        else None
                    )

                    for object_index, damage_object in enumerate(
                        annotation.objects
                    ):
                        if damage_object.label not in TARGET_LABELS:
                            continue

                        box = damage_object.bounding_box
                        plan = calculate_square_crop_plan(
                            xmin=box.xmin,
                            ymin=box.ymin,
                            xmax=box.xmax,
                            ymax=box.ymax,
                            image_width=image_width,
                            image_height=image_height,
                            context_ratio=context_ratio,
                        )

                        relative_crop_path = (
                            Path(split)
                            / damage_object.label
                            / (
                                f"{image_path.stem}_"
                                f"object_{object_index:02d}.jpg"
                            )
                        )

                        if staging_directory is not None:
                            if source_image is None:
                                raise RuntimeError("Source image was not loaded.")

                            staged_crop_path = (
                                staging_directory / relative_crop_path
                            )
                            staged_crop_path.parent.mkdir(
                                parents=True,
                                exist_ok=True,
                            )
                            crop = extract_square_crop(source_image, plan)
                            crop.save(
                                staged_crop_path,
                                format="JPEG",
                                quality=JPEG_QUALITY,
                            )

                        records.append(
                            {
                                "split": split,
                                "country": row["country"],
                                "source_image_path": image_path.as_posix(),
                                "annotation_path": annotation_path.as_posix(),
                                "object_index": object_index,
                                "source_object_id": (
                                    f"{annotation_path.as_posix()}"
                                    f"#object_{object_index:02d}"
                                ),
                                "crop_relative_path": (
                                    relative_crop_path.as_posix()
                                ),
                                "crop_path": (
                                    output_directory / relative_crop_path
                                ).as_posix(),
                                "label": damage_object.label,
                                "class_index": damage_object.class_index,
                                "xmin": box.xmin,
                                "ymin": box.ymin,
                                "xmax": box.xmax,
                                "ymax": box.ymax,
                                "image_width": image_width,
                                "image_height": image_height,
                                "requested_side": plan.requested_side,
                                "crop_side": plan.crop_side,
                                "crop_mode": plan.crop_mode,
                                "crop_left": plan.crop_left,
                                "crop_top": plan.crop_top,
                                "crop_right": plan.crop_right,
                                "crop_bottom": plan.crop_bottom,
                                "source_crop_left": plan.source_crop_left,
                                "source_crop_top": plan.source_crop_top,
                                "source_crop_right": plan.source_crop_right,
                                "source_crop_bottom": plan.source_crop_bottom,
                                "padding_left": plan.padding_left,
                                "padding_top": plan.padding_top,
                                "padding_right": plan.padding_right,
                                "padding_bottom": plan.padding_bottom,
                                "context_ratio": context_ratio,
                                "sequence_group": row["sequence_group"],
                            }
                        )
                        mode_counts[plan.crop_mode] += 1

            except (
                FileNotFoundError,
                OSError,
                UnidentifiedImageError,
                ValueError,
                RuntimeError,
            ) as error:
                raise RuntimeError(
                    "Failed to create a crop plan for "
                    f"image={image_path}, annotation={annotation_path}: {error}"
                ) from error

            processed_images += 1

            if processed_images % 2_500 == 0:
                print(
                    f"Processed {processed_images:,} source images and "
                    f"planned {len(records):,} crops..."
                )

    return records, mode_counts


def crop_counts_by_split_and_label(
    records: list[dict[str, object]],
) -> dict[str, dict[str, int]]:
    """Build a JSON-friendly crop count table."""

    counts: Counter[tuple[str, str]] = Counter(
        (str(record["split"]), str(record["label"]))
        for record in records
    )

    return {
        split: {
            label: counts[(split, label)]
            for label in CLASS_NAMES
        }
        for split in SPLIT_NAMES
    }


def verify_staged_dataset(
    staging_directory: Path,
    records: list[dict[str, object]],
) -> None:
    """Check that staging contains exactly the square crop artifact described."""

    validate_crop_file_integrity(
        staging_directory,
        records,
        expected_side_field="crop_side",
    )

    for record in records:
        box_left, box_top, box_right, box_bottom = integer_box_envelope(
            xmin=float(record["xmin"]),
            ymin=float(record["ymin"]),
            xmax=float(record["xmax"]),
            ymax=float(record["ymax"]),
            image_width=int(record["image_width"]),
            image_height=int(record["image_height"]),
        )

        if (
            int(record["crop_left"]) > box_left
            or int(record["crop_top"]) > box_top
            or int(record["crop_right"]) < box_right
            or int(record["crop_bottom"]) < box_bottom
        ):
            raise RuntimeError(
                "Crop does not fully contain its annotation: "
                f"{record['source_object_id']}"
            )

        padding = sum(
            int(record[name])
            for name in (
                "padding_left",
                "padding_top",
                "padding_right",
                "padding_bottom",
            )
        )
        crop_mode = str(record["crop_mode"])

        if crop_mode == "edge_padded" and padding == 0:
            raise RuntimeError("Edge-padded crop has no recorded padding.")
        if crop_mode != "edge_padded" and padding != 0:
            raise RuntimeError("Native crop has unexpected recorded padding.")


def build_metadata(
    records: list[dict[str, object]],
    mode_counts: Counter[str],
    context_ratio: float,
) -> dict[str, object]:
    """Create provenance metadata for a reproducible crop dataset."""

    split_paths = {
        split: SPLIT_DIRECTORY / f"{split}.csv"
        for split in SPLIT_NAMES
    }

    return {
        "dataset_version": DATASET_VERSION,
        "created_at_utc": utc_now(),
        "context_ratio": context_ratio,
        "jpeg_quality": JPEG_QUALITY,
        "class_mapping": CLASS_TO_INDEX,
        "split_manifests": {
            split: {
                "path": split_path.as_posix(),
                "sha256": sha256_file(split_path),
            }
            for split, split_path in split_paths.items()
        },
        "crop_counts": crop_counts_by_split_and_label(records),
        "total_crops": len(records),
        "crop_mode_counts": dict(sorted(mode_counts.items())),
        "edge_padding_policy": (
            "Replicate the nearest source-image edge only when a valid "
            "annotation envelope is wider or taller than the image's short "
            "side and no in-image square can retain it."
        ),
        "manifest_filename": MANIFEST_FILENAME,
    }


def print_summary(
    records: list[dict[str, object]],
    mode_counts: Counter[str],
    output_directory: Path,
    dry_run: bool,
) -> None:
    """Print the planned or published crop inventory."""

    counts = crop_counts_by_split_and_label(records)
    total_by_split = {
        split: sum(counts[split].values())
        for split in SPLIT_NAMES
    }

    print("\nSquare classification crop summary")
    print("-----------------------------------")
    print(f"Dataset version: {DATASET_VERSION}")
    print(f"Build mode: {'dry run' if dry_run else 'published'}")
    print(f"Output directory: {output_directory}")
    print(f"Total crops: {len(records):,}")

    for split in SPLIT_NAMES:
        print(f"\n{split.upper()} ({total_by_split[split]:,} crops)")

        for label in CLASS_NAMES:
            print(f"{label}: {counts[split][label]:,}")

    print("\nCrop construction modes")
    print("-----------------------")

    for mode in ("in_image", "context_limited", "edge_padded"):
        print(f"{mode}: {mode_counts[mode]:,}")


def main() -> None:
    """Build and atomically publish a validated square-crop dataset."""

    args = parse_arguments()

    if args.dry_run:
        records, mode_counts = build_crop_records(
            output_directory=args.output_directory,
            context_ratio=args.context_ratio,
            staging_directory=None,
        )
        print_summary(
            records=records,
            mode_counts=mode_counts,
            output_directory=args.output_directory,
            dry_run=True,
        )
        return

    staging_directory = create_staging_directory(args.output_directory)

    try:
        records, mode_counts = build_crop_records(
            output_directory=args.output_directory,
            context_ratio=args.context_ratio,
            staging_directory=staging_directory,
        )
        manifest_path, metadata_path = output_paths(staging_directory)
        write_csv_atomic(manifest_path, MANIFEST_FIELDNAMES, records)
        verify_staged_dataset(staging_directory, records)

        write_json_atomic(
            metadata_path,
            build_metadata(
                records=records,
                mode_counts=mode_counts,
                context_ratio=args.context_ratio,
            ),
        )

        staging_directory.rename(args.output_directory)

    except Exception:
        print(
            "Crop build failed. The staging directory was preserved for "
            f"inspection: {staging_directory}"
        )
        raise

    print_summary(
        records=records,
        mode_counts=mode_counts,
        output_directory=args.output_directory,
        dry_run=False,
    )
    manifest_path, metadata_path = output_paths(args.output_directory)
    print(f"\nManifest: {manifest_path}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()

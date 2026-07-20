"""Filesystem integrity checks shared by crop builders and experiment runners."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src.utils.experiment_artifacts import resolve_path


IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


@dataclass(frozen=True)
class CropFileIntegrity:
    """Summary returned after every manifest crop passes validation."""

    record_count: int
    image_count: int


def validate_declared_crop_paths(
    dataset_directory: Path,
    records: Sequence[Mapping[str, object]],
) -> None:
    """Ensure declared project paths identify each relative crop exactly."""

    invalid_paths: list[str] = []
    for record in records:
        relative_path = Path(str(record["crop_relative_path"]))
        expected_path = (dataset_directory / relative_path).resolve()
        declared_path_value = record.get("crop_path")
        declared_path = (
            resolve_path(str(declared_path_value))
            if declared_path_value not in (None, "")
            else None
        )
        if declared_path != expected_path:
            invalid_paths.append(
                "Manifest crop path does not match crop_relative_path: "
                f"{declared_path_value!r}"
            )
            if len(invalid_paths) >= 20:
                break

    if invalid_paths:
        raise RuntimeError(
            "Crop manifest declares inconsistent crop paths. "
            f"Examples={invalid_paths}"
        )


def validate_crop_file_integrity(
    dataset_directory: Path,
    records: Sequence[Mapping[str, object]],
    *,
    expected_side_field: str | None = None,
) -> CropFileIntegrity:
    """Verify exact file inventory, unique identities, RGB mode, and squareness.

    Builders may provide ``expected_side_field`` to additionally certify each
    image against its planned pixel dimensions. Experiment runners can omit it
    when their frozen manifest intentionally exposes only stable core fields.
    """

    if not records:
        raise ValueError("Cannot validate an empty crop manifest")

    relative_paths: list[Path] = []
    source_object_ids: list[str] = []
    for record in records:
        relative_path = Path(str(record["crop_relative_path"]))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(
                "crop_relative_path must stay inside the dataset directory: "
                f"{relative_path}"
            )
        relative_paths.append(relative_path)
        source_object_ids.append(str(record["source_object_id"]))

    if len(set(relative_paths)) != len(relative_paths):
        raise RuntimeError("Crop records contain duplicate output paths.")
    if len(set(source_object_ids)) != len(source_object_ids):
        raise RuntimeError("Crop records contain duplicate source objects.")

    expected_paths = {
        (dataset_directory / relative_path).resolve()
        for relative_path in relative_paths
    }
    actual_paths = {
        path.resolve()
        for path in dataset_directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }
    if actual_paths != expected_paths:
        missing_paths = sorted(expected_paths - actual_paths)
        extra_paths = sorted(actual_paths - expected_paths)
        raise RuntimeError(
            "Crop files do not match the manifest records. "
            f"Missing={len(missing_paths)}, extra={len(extra_paths)}. "
            f"Missing examples={missing_paths[:5]}, "
            f"extra examples={extra_paths[:5]}"
        )

    invalid_images: list[str] = []
    for record, relative_path in zip(records, relative_paths):
        crop_path = dataset_directory / relative_path
        with Image.open(crop_path) as crop:
            if crop.mode != "RGB" or crop.width != crop.height:
                invalid_images.append(
                    f"{crop_path} mode={crop.mode} size={crop.size}"
                )
                continue

            if expected_side_field is not None:
                expected_side = int(record[expected_side_field])
                if crop.size != (expected_side, expected_side):
                    invalid_images.append(
                        f"{crop_path} expected={expected_side}x{expected_side} "
                        f"actual={crop.size}"
                    )

        if len(invalid_images) >= 20:
            break

    if invalid_images:
        raise RuntimeError(
            "Crop image integrity failure. Examples: "
            f"{invalid_images}"
        )

    return CropFileIntegrity(
        record_count=len(records),
        image_count=len(actual_paths),
    )

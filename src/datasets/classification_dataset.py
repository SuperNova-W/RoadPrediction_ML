"""TensorFlow input pipeline for damage-classification crops."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    import tensorflow as tf

from src.utils.classes import CLASS_NAMES, CLASS_TO_INDEX
from src.utils.experiment_artifacts import resolve_path


DATASET_DIRECTORY = Path("data/processed/classification")

IMAGE_HEIGHT = 224
IMAGE_WIDTH = 224
DEFAULT_BATCH_SIZE = 32
RANDOM_SEED = 42

# These are the provenance fields needed to train from a versioned crop
# manifest.  The square-crop builder may add more geometry fields, but the
# input pipeline deliberately depends only on this stable subset.
REQUIRED_CROP_MANIFEST_FIELDS = frozenset(
    {
        "split",
        "country",
        "source_image_path",
        "source_object_id",
        "crop_relative_path",
        "label",
        "class_index",
        "sequence_group",
    }
)


@dataclass(frozen=True)
class CropRecord(Mapping[str, object]):
    """One classification crop described by a versioned manifest.

    ``crop_path`` is resolved from ``crop_relative_path`` against either the
    manifest directory or an explicit published-crop root. This keeps copied
    experiment-subset manifests independent of the current working directory.
    """

    split: str
    country: str
    source_image_path: Path
    source_object_id: str
    crop_relative_path: Path
    crop_path: Path
    label: str
    class_index: int
    sequence_group: str
    manifest_values: Mapping[str, str]

    def __getitem__(self, field_name: str) -> object:
        """Expose the original CSV values to mapping-based consumers.

        Attribute access intentionally returns typed values such as the
        resolved ``crop_path``. Mapping access preserves the exact manifest
        spelling, which keeps frozen subset CSVs and prediction joins stable.
        """

        if field_name == "crop_path" and field_name not in self.manifest_values:
            return self.crop_path.as_posix()
        return self.manifest_values[field_name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.manifest_values)

    def __len__(self) -> int:
        return len(self.manifest_values)

    def to_manifest_row(self) -> dict[str, object]:
        """Return a plain row suitable for :class:`csv.DictWriter`."""

        return dict(self.manifest_values)


@dataclass(frozen=True)
class CropManifest:
    """A validated manifest plus the stable column order it was loaded with."""

    path: Path
    fieldnames: tuple[str, ...]
    records: tuple[CropRecord, ...]


RecordLike: TypeAlias = CropRecord | Mapping[str, object]


def _required_manifest_value(
    row: dict[str, str | None],
    field_name: str,
    line_number: int,
    manifest_path: Path,
) -> str:
    """Read one non-empty CSV value with an actionable validation error."""

    value = row.get(field_name)
    if value is None or not value.strip():
        raise ValueError(
            f"Missing '{field_name}' at line {line_number} in {manifest_path}."
        )
    return value.strip()


def _resolve_crop_path(
    manifest_path: Path,
    crop_relative_path: str,
    line_number: int,
    crop_root: Path | None,
) -> tuple[Path, Path]:
    """Resolve a crop path safely against its manifest or explicit crop root."""

    relative_path = Path(crop_relative_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(
            "crop_relative_path must stay inside its manifest directory; "
            f"got '{crop_relative_path}' at line {line_number} in {manifest_path}."
        )

    base_directory = manifest_path.parent if crop_root is None else crop_root
    return relative_path, (base_directory / relative_path).resolve()


def load_crop_manifest(
    manifest_path: Path | str,
    *,
    split: str | None = None,
    crop_root: Path | str | None = None,
    require_existing_files: bool = False,
) -> CropManifest:
    """Load one validated crop manifest and retain its complete CSV rows.

    ``crop_root`` is required when a frozen subset manifest has been copied
    away from the published crop dataset. Its ``crop_relative_path`` values
    still refer to that dataset root, not the subset manifest's directory.
    """

    resolved_manifest_path = Path(manifest_path).resolve()
    if not resolved_manifest_path.is_file():
        raise FileNotFoundError(
            f"Crop manifest not found: {resolved_manifest_path}"
        )

    resolved_crop_root = (
        None if crop_root is None else resolve_path(crop_root)
    )
    records: list[CropRecord] = []
    with resolved_manifest_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing_fields = REQUIRED_CROP_MANIFEST_FIELDS - set(fieldnames)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"Crop manifest is missing required columns: {missing}. "
                f"Path: {resolved_manifest_path}"
            )

        for line_number, row in enumerate(reader, start=2):
            record_split = _required_manifest_value(
                row,
                "split",
                line_number,
                resolved_manifest_path,
            )
            if split is not None and record_split != split:
                continue

            label = _required_manifest_value(
                row,
                "label",
                line_number,
                resolved_manifest_path,
            )
            if label not in CLASS_TO_INDEX:
                raise ValueError(
                    f"Unknown class label '{label}' at line {line_number} in "
                    f"{resolved_manifest_path}. Expected one of {CLASS_NAMES}."
                )

            class_index_text = _required_manifest_value(
                row,
                "class_index",
                line_number,
                resolved_manifest_path,
            )
            try:
                class_index = int(class_index_text)
            except ValueError as error:
                raise ValueError(
                    f"Invalid class_index '{class_index_text}' at line "
                    f"{line_number} in {resolved_manifest_path}."
                ) from error

            expected_class_index = CLASS_TO_INDEX[label]
            if class_index != expected_class_index:
                raise ValueError(
                    f"Label/index mismatch at line {line_number} in "
                    f"{resolved_manifest_path}: {label} maps to "
                    f"{expected_class_index}, not {class_index}."
                )

            crop_relative_path_text = _required_manifest_value(
                row,
                "crop_relative_path",
                line_number,
                resolved_manifest_path,
            )
            crop_relative_path, crop_path = _resolve_crop_path(
                resolved_manifest_path,
                crop_relative_path_text,
                line_number,
                resolved_crop_root,
            )
            if require_existing_files and not crop_path.is_file():
                raise FileNotFoundError(
                    f"Crop file listed at line {line_number} is missing: {crop_path}"
                )

            manifest_values = {
                field_name: str(value or "")
                for field_name, value in row.items()
                if field_name is not None
            }
            records.append(
                CropRecord(
                    split=record_split,
                    country=_required_manifest_value(
                        row,
                        "country",
                        line_number,
                        resolved_manifest_path,
                    ),
                    source_image_path=Path(
                        _required_manifest_value(
                            row,
                            "source_image_path",
                            line_number,
                            resolved_manifest_path,
                        )
                    ),
                    source_object_id=_required_manifest_value(
                        row,
                        "source_object_id",
                        line_number,
                        resolved_manifest_path,
                    ),
                    crop_relative_path=crop_relative_path,
                    crop_path=crop_path,
                    label=label,
                    class_index=class_index,
                    sequence_group=_required_manifest_value(
                        row,
                        "sequence_group",
                        line_number,
                        resolved_manifest_path,
                    ),
                    manifest_values=MappingProxyType(manifest_values),
                )
            )

    return CropManifest(
        path=resolved_manifest_path,
        fieldnames=fieldnames,
        records=tuple(records),
    )


def load_manifest_records(
    manifest_path: Path | str,
    *,
    split: str | None = None,
    crop_root: Path | str | None = None,
    require_existing_files: bool = False,
) -> list[CropRecord]:
    """Load validated crop records from a square-crop ``manifest.csv``.

    The returned order is the CSV order.  Pass ``split`` to keep one named
    split, and ``require_existing_files=True`` when a caller needs an early
    file-presence check in addition to CSV validation.
    """

    return list(
        load_crop_manifest(
            manifest_path,
            split=split,
            crop_root=crop_root,
            require_existing_files=require_existing_files,
        ).records
    )


def _as_name_set(values: Iterable[str] | str | None) -> set[str] | None:
    """Normalize an optional single name or iterable of names for filtering."""

    if values is None:
        return None
    if isinstance(values, str):
        return {values}
    return set(values)


def filter_crop_records(
    records: Iterable[CropRecord],
    *,
    split: str | None = None,
    include_countries: Iterable[str] | str | None = None,
    exclude_countries: Iterable[str] | str | None = None,
    include_sequence_groups: Iterable[str] | str | None = None,
    exclude_sequence_groups: Iterable[str] | str | None = None,
) -> list[CropRecord]:
    """Return records matching explicit split, country, and group filters.

    Filtering preserves the original manifest order, which is important for
    reproducible non-shuffled validation and evaluation datasets.
    """

    included_countries = _as_name_set(include_countries)
    excluded_countries = _as_name_set(exclude_countries)
    included_groups = _as_name_set(include_sequence_groups)
    excluded_groups = _as_name_set(exclude_sequence_groups)

    if included_countries and excluded_countries:
        overlap = included_countries & excluded_countries
        if overlap:
            raise ValueError(
                "Country filters cannot both include and exclude: "
                f"{sorted(overlap)}"
            )
    if included_groups and excluded_groups:
        overlap = included_groups & excluded_groups
        if overlap:
            raise ValueError(
                "Sequence-group filters cannot both include and exclude: "
                f"{sorted(overlap)}"
            )

    return [
        record
        for record in records
        if (split is None or record.split == split)
        and (
            included_countries is None
            or record.country in included_countries
        )
        and (
            excluded_countries is None
            or record.country not in excluded_countries
        )
        and (
            included_groups is None
            or record.sequence_group in included_groups
        )
        and (
            excluded_groups is None
            or record.sequence_group not in excluded_groups
        )
    ]


def _dataset_path_and_label(record: RecordLike) -> tuple[str, int]:
    """Return the resolved input path and validated class index for a record."""

    if isinstance(record, CropRecord):
        crop_path = record.crop_path
        class_index = record.class_index
    else:
        crop_path_value = record.get("crop_path")
        class_index_value = record.get("class_index")
        if crop_path_value in (None, "") or class_index_value in (None, ""):
            raise ValueError(
                "Every dataset record needs non-empty crop_path and class_index."
            )
        crop_path = resolve_path(str(crop_path_value))
        try:
            class_index = int(class_index_value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid class_index in dataset record: {class_index_value!r}"
            ) from error

    if class_index not in range(len(CLASS_NAMES)):
        raise ValueError(
            f"Class index must be in [0, {len(CLASS_NAMES) - 1}], "
            f"got {class_index}."
        )
    return crop_path.as_posix(), class_index


def build_dataset_from_records(
    records: Iterable[RecordLike],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    shuffle: bool = False,
    seed: int = RANDOM_SEED,
    image_size: tuple[int, int] = (IMAGE_HEIGHT, IMAGE_WIDTH),
) -> tf.data.Dataset:
    """Build a deterministic manifest-driven dataset with ordinary resize.

    Square crops are decoded as RGB JPEGs and resized directly to
    ``image_size``.  Unlike the legacy directory loader below, this pipeline
    intentionally never inserts aspect-ratio padding or black bars.
    """

    import tensorflow as tf

    record_list = list(records)
    if not record_list:
        raise ValueError("Cannot build a TensorFlow dataset from zero crop records.")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")
    if len(image_size) != 2 or any(dimension <= 0 for dimension in image_size):
        raise ValueError("image_size must contain two positive integer dimensions.")

    inputs = [_dataset_path_and_label(record) for record in record_list]
    paths = [path for path, _ in inputs]
    labels = [label for _, label in inputs]
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))

    if shuffle:
        dataset = dataset.shuffle(
            buffer_size=len(record_list),
            seed=seed,
            reshuffle_each_iteration=True,
        )

    options = tf.data.Options()
    options.experimental_deterministic = True
    dataset = dataset.with_options(options)

    def decode_and_resize(
        path: tf.Tensor,
        label: tf.Tensor,
    ) -> tuple[tf.Tensor, tf.Tensor]:
        image = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        image.set_shape((None, None, 3))
        image = tf.image.resize(
            image,
            size=image_size,
            method="bilinear",
        )
        return tf.cast(image, tf.float32), tf.cast(label, tf.int32)

    dataset = dataset.map(
        decode_and_resize,
        num_parallel_calls=tf.data.AUTOTUNE,
    )
    dataset = dataset.batch(batch_size, drop_remainder=False)
    return dataset.prefetch(tf.data.AUTOTUNE)


def load_split(
    split: str,
    batch_size: int,
    shuffle: bool,
) -> tf.data.Dataset:
    """Load one classification split from its class directories."""

    import tensorflow as tf

    split_directory = DATASET_DIRECTORY / split

    if not split_directory.is_dir():
        raise FileNotFoundError(
            f"Classification split not found: {split_directory}\n"
            "Run python -m scripts.create_classification_crops first."
        )

    dataset = tf.keras.utils.image_dataset_from_directory(
        directory=split_directory,
        labels="inferred",
        label_mode="int",
        class_names=list(CLASS_NAMES),
        color_mode="rgb",
        batch_size=batch_size,
        image_size=(IMAGE_HEIGHT, IMAGE_WIDTH),
        shuffle=shuffle,
        seed=RANDOM_SEED if shuffle else None,
        interpolation="bilinear",
        # Add padding instead of stretching crops into a square.
        pad_to_aspect_ratio=True,
        verbose=False,
    )

    def prepare_batch(
        images: tf.Tensor,
        labels: tf.Tensor,
    ) -> tuple[tf.Tensor, tf.Tensor]:
        """Ensure consistent TensorFlow data types."""

        images = tf.cast(images, tf.float32)
        labels = tf.cast(labels, tf.int32)

        return images, labels

    dataset = dataset.map(
        prepare_batch,
        num_parallel_calls=tf.data.AUTOTUNE,
    )

    # Prepare the next batch while the model processes the current one.
    return dataset.prefetch(tf.data.AUTOTUNE)


def build_classification_datasets(
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[
    tf.data.Dataset,
    tf.data.Dataset,
    tf.data.Dataset,
]:
    """Build training, validation, and test datasets."""

    train_dataset = load_split(
        split="train",
        batch_size=batch_size,
        shuffle=True,
    )

    validation_dataset = load_split(
        split="val",
        batch_size=batch_size,
        shuffle=False,
    )

    test_dataset = load_split(
        split="test",
        batch_size=batch_size,
        shuffle=False,
    )

    return train_dataset, validation_dataset, test_dataset


def smoke_test() -> None:
    """Load one batch and verify its shapes and value ranges."""

    import tensorflow as tf

    train_dataset, validation_dataset, test_dataset = (
        build_classification_datasets()
    )

    images, labels = next(iter(train_dataset))

    print(f"Class mapping: {CLASS_TO_INDEX}")
    print(f"Image batch shape: {tuple(images.shape)}")
    print(f"Label batch shape: {tuple(labels.shape)}")
    print(f"Image dtype: {images.dtype.name}")
    print(f"Label dtype: {labels.dtype.name}")
    print(f"Minimum pixel value: {tf.reduce_min(images).numpy():.1f}")
    print(f"Maximum pixel value: {tf.reduce_max(images).numpy():.1f}")
    print(f"Labels in first batch: {labels.numpy()}")
    print(f"Validation batches: {validation_dataset.cardinality().numpy()}")
    print(f"Test batches: {test_dataset.cardinality().numpy()}")
    print("Dataset smoke test passed.")


if __name__ == "__main__":
    smoke_test()

"""TensorFlow input pipeline for damage-classification crops."""

from __future__ import annotations

from pathlib import Path

import tensorflow as tf

from src.utils.classes import CLASS_TO_INDEX


DATASET_DIRECTORY = Path("data/processed/classification")

IMAGE_HEIGHT = 224
IMAGE_WIDTH = 224
DEFAULT_BATCH_SIZE = 32
RANDOM_SEED = 42

# Explicit ordering guarantees that folder names match our class indices.
CLASS_NAMES = list(CLASS_TO_INDEX.keys())


def load_split(
    split: str,
    batch_size: int,
    shuffle: bool,
) -> tf.data.Dataset:
    """Load one classification split from its class directories."""

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
        class_names=CLASS_NAMES,
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

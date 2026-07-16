"""TensorFlow CNN baseline for classifying road-damage crops."""

from __future__ import annotations

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from src.utils.classes import NUM_CLASSES


def build_data_augmentation() -> keras.Sequential:
    """Create transformations applied only during training."""

    return keras.Sequential(
        [
            # A horizontal flip preserves longitudinal/transverse meaning.
            layers.RandomFlip(
                mode="horizontal",
                name="random_horizontal_flip",
            ),
            layers.RandomTranslation(
                height_factor=0.05,
                width_factor=0.05,
                fill_mode="reflect",
                name="random_translation",
            ),
            layers.RandomZoom(
                height_factor=(-0.10, 0.10),
                width_factor=(-0.10, 0.10),
                fill_mode="reflect",
                name="random_zoom",
            ),
            layers.RandomContrast(
                factor=0.15,
                name="random_contrast",
            ),
        ],
        name="training_augmentation",
    )


def convolution_block(
    inputs: keras.KerasTensor,
    filters: int,
    block_name: str,
) -> keras.KerasTensor:
    """Learn image features and reduce their spatial dimensions."""

    x = layers.Conv2D(
        filters=filters,
        kernel_size=3,
        padding="same",
        use_bias=False,
        name=f"{block_name}_conv",
    )(inputs)

    x = layers.BatchNormalization(
        name=f"{block_name}_batch_norm"
    )(x)

    x = layers.ReLU(
        name=f"{block_name}_relu"
    )(x)

    x = layers.MaxPooling2D(
        pool_size=2,
        name=f"{block_name}_pool",
    )(x)

    return x


def build_custom_cnn(
    input_shape: tuple[int, int, int] = (224, 224, 3),
    num_classes: int = NUM_CLASSES,
) -> keras.Model:
    """Build a four-class road-damage classifier."""

    inputs = keras.Input(
        shape=input_shape,
        name="road_damage_image",
    )

    # Augmentation runs when training=True and switches off for evaluation.
    x = build_data_augmentation()(inputs)

    # Convert pixel values from [0, 255] to [0, 1].
    x = layers.Rescaling(
        scale=1.0 / 255.0,
        name="rescale_pixels",
    )(x)

    x = convolution_block(x, filters=32, block_name="block1")
    x = convolution_block(x, filters=64, block_name="block2")
    x = convolution_block(x, filters=128, block_name="block3")

    # Replace each feature map with its average activation.
    x = layers.GlobalAveragePooling2D(
        name="global_average_pool"
    )(x)

    x = layers.Dense(
        units=64,
        activation="relu",
        name="dense_features",
    )(x)

    x = layers.Dropout(
        rate=0.30,
        name="dropout",
    )(x)

    # These are raw logits; softmax will be handled by the loss.
    outputs = layers.Dense(
        units=num_classes,
        name="class_logits",
    )(x)

    return keras.Model(
        inputs=inputs,
        outputs=outputs,
        name="custom_damage_cnn",
    )


def smoke_test() -> None:
    """Verify preprocessing and output tensor dimensions."""

    keras.utils.set_random_seed(42)

    model = build_custom_cnn()

    images = tf.random.uniform(
        shape=(2, 224, 224, 3),
        minval=0,
        maxval=255,
        dtype=tf.float32,
        seed=42,
    )

    # training=False disables augmentation and dropout.
    logits = model(images, training=False)

    rescaling_layer = model.get_layer("rescale_pixels")
    normalized_images = rescaling_layer(images)

    expected_shape = (2, NUM_CLASSES)
    actual_shape = tuple(logits.shape)

    if actual_shape != expected_shape:
        raise RuntimeError(
            f"Expected output shape {expected_shape}, got {actual_shape}"
        )

    normalized_minimum = float(
        tf.reduce_min(normalized_images).numpy()
    )
    normalized_maximum = float(
        tf.reduce_max(normalized_images).numpy()
    )

    if normalized_minimum < 0 or normalized_maximum > 1:
        raise RuntimeError(
            "Image normalization produced values outside [0, 1]."
        )

    print(f"TensorFlow version: {tf.__version__}")
    print(f"Input shape: {tuple(images.shape)}")
    print(f"Output shape: {actual_shape}")
    print(
        "Normalized range: "
        f"{normalized_minimum:.4f} to {normalized_maximum:.4f}"
    )
    print(f"Model parameters: {model.count_params():,}")
    print("Model smoke test passed.")

    model.summary()


if __name__ == "__main__":
    smoke_test()

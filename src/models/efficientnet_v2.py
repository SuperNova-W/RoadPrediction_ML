"""EfficientNetV2-B1 transfer-learning classifier for road-damage crops.

An ImageNet-pretrained EfficientNetV2-B1 backbone is reused as a feature
extractor; only the small classification head is new. Training happens in two
stages the caller drives: a frozen-backbone stage that trains just the head,
then an optional fine-tuning stage after :func:`unfreeze_backbone`.

Two project-specific choices are baked in here:

* Augmentation is shared with the from-scratch baseline via
  ``build_data_augmentation`` so both models see identical, orientation-safe
  transforms. Rotation and vertical flips are deliberately absent — they would
  swap the D00 (longitudinal) and D10 (transverse) crack semantics.
* No external rescaling is applied. EfficientNetV2 rescales and normalizes
  inputs internally (``include_preprocessing=True``) and expects float pixels in
  the ``[0, 255]`` range, which is exactly what the manifest pipeline yields.
"""

from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers

from src.models.custom_cnn import build_data_augmentation
from src.utils.classes import NUM_CLASSES


def build_efficientnet_v2_b1(
    input_shape: tuple[int, int, int] = (224, 224, 3),
    num_classes: int = NUM_CLASSES,
    dropout_rate: float = 0.30,
    weights: str | None = "imagenet",
) -> tuple[keras.Model, keras.Model]:
    """Build the classifier and return it with its backbone for stage control.

    The backbone starts frozen so the first training stage only learns the head.
    It is called with ``training=False`` so its BatchNormalization layers stay in
    inference mode even after :func:`unfreeze_backbone` — their running
    statistics never drift during fine-tuning on this comparatively small,
    imbalanced dataset.

    Returns ``(model, backbone)``; the caller toggles ``backbone.trainable`` and
    recompiles between stages.
    """

    if not 0.0 <= dropout_rate < 1.0:
        raise ValueError("dropout_rate must be in [0, 1).")

    backbone = keras.applications.EfficientNetV2B1(
        include_top=False,
        weights=weights,
        input_shape=input_shape,
        pooling=None,
    )
    backbone.trainable = False

    inputs = keras.Input(shape=input_shape, name="road_damage_image")
    x = build_data_augmentation()(inputs)
    x = backbone(x, training=False)
    x = layers.GlobalAveragePooling2D(name="global_average_pool")(x)
    x = layers.Dropout(dropout_rate, name="head_dropout")(x)
    outputs = layers.Dense(num_classes, name="class_logits")(x)

    model = keras.Model(
        inputs=inputs,
        outputs=outputs,
        name="efficientnet_v2_b1_damage",
    )
    return model, backbone


def unfreeze_backbone(backbone: keras.Model) -> int:
    """Unfreeze the backbone for fine-tuning and report its trainable layers.

    BatchNormalization layers are left frozen so only their scale/offset can
    adapt while their statistics remain fixed; combined with the
    ``training=False`` call in :func:`build_efficientnet_v2_b1`, this is the
    recommended recipe for fine-tuning a pretrained convolutional backbone.
    The caller must recompile the model afterwards for the change to take effect.
    """

    backbone.trainable = True
    trainable_layers = 0
    for layer in backbone.layers:
        if isinstance(layer, layers.BatchNormalization):
            layer.trainable = False
        elif layer.trainable_weights:
            trainable_layers += 1
    return trainable_layers


def count_trainable_parameters(model: keras.Model) -> int:
    """Return the number of trainable scalar parameters in a model."""

    return int(
        sum(int(weight.numpy().size) for weight in model.trainable_weights)
    )

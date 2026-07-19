"""Sparse categorical focal loss for imbalanced multiclass training.

Focal loss down-weights easy, confident examples so the gradient concentrates on
the hard, rare ones — here the minority damage classes (D20 alligator, D40
pothole) that plain weighted cross-entropy could not lift. With ``gamma=0`` and
no ``alpha`` it reduces exactly to cross-entropy.

The optional per-class ``alpha`` acts as a class weight baked into the loss, so a
caller using focal loss should not also pass ``class_weight`` to ``fit`` (that
would double-count the imbalance).

This module imports TensorFlow at load time and is therefore imported lazily, only
when focal loss is actually requested. The loss is registered as serializable so a
model compiled with it saves cleanly; downstream reloads use ``compile=False`` and
never reconstruct it.
"""

from __future__ import annotations

from collections.abc import Sequence

import tensorflow as tf
from tensorflow import keras


@keras.utils.register_keras_serializable(package="road_damage")
class SparseCategoricalFocalLoss(keras.losses.Loss):
    """Focal loss for integer labels and (by default) raw logits."""

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Sequence[float] | None = None,
        from_logits: bool = True,
        name: str = "sparse_categorical_focal_loss",
        reduction: str = "sum_over_batch_size",
        **kwargs: object,
    ) -> None:
        super().__init__(name=name, reduction=reduction, **kwargs)
        if gamma < 0:
            raise ValueError("gamma must be non-negative")
        self.gamma = float(gamma)
        self.alpha = None if alpha is None else [float(value) for value in alpha]
        self.from_logits = bool(from_logits)
        self._alpha_tensor = (
            None
            if self.alpha is None
            else tf.constant(self.alpha, dtype=tf.float32)
        )

    def call(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        labels = tf.reshape(tf.cast(y_true, tf.int32), [-1])
        if self.from_logits:
            log_probs = tf.nn.log_softmax(y_pred, axis=-1)
        else:
            log_probs = tf.math.log(tf.clip_by_value(y_pred, 1e-12, 1.0))

        true_log_prob = tf.gather(log_probs, labels, batch_dims=1)
        cross_entropy = -true_log_prob
        true_prob = tf.exp(true_log_prob)
        focal = tf.pow(1.0 - true_prob, self.gamma) * cross_entropy

        if self._alpha_tensor is not None:
            focal = tf.gather(self._alpha_tensor, labels) * focal

        # Per-example loss; the base class applies the configured reduction.
        return focal

    def get_config(self) -> dict[str, object]:
        config = super().get_config()
        config.update(
            {
                "gamma": self.gamma,
                "alpha": self.alpha,
                "from_logits": self.from_logits,
            }
        )
        return config

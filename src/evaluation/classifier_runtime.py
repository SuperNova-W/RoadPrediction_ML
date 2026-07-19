"""Minimal runtime checks shared by classifier training and evaluation."""

from __future__ import annotations

from typing import Any


def evaluate_compiled_dataset(
    model: Any,
    dataset: Any,
) -> dict[str, float]:
    """Return compiled Keras loss and accuracy from ``model.evaluate``.

    This routes through the compiled metric path. It is kept for the evaluator's
    optional compiled-vs-eager diagnostic, but must not be used to select
    checkpoints or certify a model: on some accelerators (notably Apple Metal)
    the compiled validation state can report numbers that a freshly reloaded
    model does not reproduce. Use :func:`evaluate_eager_dataset` for anything
    that must match a redeployed model.
    """

    metrics = model.evaluate(dataset, verbose=0, return_dict=True)
    required_metrics = ("loss", "accuracy")
    missing_metrics = [name for name in required_metrics if name not in metrics]
    if missing_metrics:
        raise RuntimeError(
            "Model evaluation did not return the expected metrics: "
            f"{missing_metrics}. Received: {sorted(metrics)}"
        )
    return {name: float(metrics[name]) for name in required_metrics}


def evaluate_eager_dataset(
    model: Any,
    dataset: Any,
) -> dict[str, float]:
    """Return loss and accuracy from a plain eager forward pass.

    This is the deployable inference path: ``model(x, training=False)`` with a
    manual sparse-categorical loss and an argmax accuracy. It deliberately
    avoids ``model.evaluate``'s compiled metric state, which can drift from a
    plain forward pass on some accelerators. The monitored validation loss, the
    fresh-process certification, and the final reported metrics all go through
    this function so early stopping, checkpoint selection, and deployment agree.

    The per-example mean loss matches ``model.evaluate`` when the compiled path
    is healthy, so a divergence between the two is itself the signal to trust.
    """

    import tensorflow as tf
    from tensorflow import keras

    loss_function = keras.losses.SparseCategoricalCrossentropy(
        from_logits=True,
        reduction="sum",
    )
    total_loss = 0.0
    correct_predictions = 0
    total_examples = 0

    for images, labels in dataset:
        labels = tf.reshape(labels, [-1])
        logits = model(images, training=False)
        total_loss += float(loss_function(labels, logits).numpy())
        predictions = tf.argmax(logits, axis=1, output_type=labels.dtype)
        correct_predictions += int(
            tf.reduce_sum(tf.cast(predictions == labels, tf.int64)).numpy()
        )
        total_examples += int(tf.shape(labels)[0].numpy())

    if total_examples == 0:
        raise ValueError("Cannot evaluate an empty dataset.")

    return {
        "loss": total_loss / total_examples,
        "accuracy": correct_predictions / total_examples,
        "number_of_examples": float(total_examples),
    }


def evaluate_eager_predictions(
    model: Any,
    dataset: Any,
) -> dict[str, Any]:
    """Return the eager loss plus per-example true and predicted labels.

    This is the same eager forward pass as :func:`evaluate_eager_dataset`, but it
    also returns the label arrays so callers can compute richer metrics (macro-F1,
    balanced accuracy, per-class recall) without a second pass. Used by the
    validation callback so early stopping can monitor a class-balanced metric.
    """

    import numpy as np
    import tensorflow as tf
    from tensorflow import keras

    loss_function = keras.losses.SparseCategoricalCrossentropy(
        from_logits=True,
        reduction="sum",
    )
    total_loss = 0.0
    true_batches: list[np.ndarray] = []
    predicted_batches: list[np.ndarray] = []
    total_examples = 0

    for images, labels in dataset:
        labels = tf.reshape(labels, [-1])
        logits = model(images, training=False)
        total_loss += float(loss_function(labels, logits).numpy())
        predictions = tf.argmax(logits, axis=1, output_type=labels.dtype)
        true_batches.append(np.asarray(labels.numpy()).reshape(-1))
        predicted_batches.append(np.asarray(predictions.numpy()).reshape(-1))
        total_examples += int(tf.shape(labels)[0].numpy())

    if total_examples == 0:
        raise ValueError("Cannot evaluate an empty dataset.")

    return {
        "loss": total_loss / total_examples,
        "true_labels": np.concatenate(true_batches),
        "predicted_labels": np.concatenate(predicted_batches),
        "number_of_examples": total_examples,
    }

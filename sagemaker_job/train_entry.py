"""SageMaker training entry point for the EfficientNetV2 damage classifier.

SageMaker runs this file inside the training container. It maps SageMaker's
conventions onto ``scripts.train_efficientnet_v2``:

* the crop dataset arrives on the ``training`` input channel
  (``SM_CHANNEL_TRAINING``);
* every experiment artifact is written under ``SM_OUTPUT_DATA_DIR`` so it is
  captured in ``output.tar.gz``;
* the certified checkpoint is copied to ``SM_MODEL_DIR`` so it is captured in
  ``model.tar.gz`` as the deployable artifact;
* SageMaker hyperparameters arrive as trailing ``--key value`` CLI args and are
  passed straight through to the training script.

The container's code root (``/opt/ml/code``) holds this file plus the ``src`` and
``scripts`` packages (uploaded via the estimator's ``dependencies``), so the
normal ``from scripts...`` / ``from src...`` imports resolve unchanged, and the
fresh-process certification subprocess works exactly as it does locally.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# In the SageMaker container ``scripts`` and ``src`` are siblings of this file
# under /opt/ml/code; in the local repo they live one level up (the repo root).
# Put whichever directory actually contains them on the path so the imports work
# in both layouts.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "scripts").is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))


def _strip_injected_args(args: list[str], names: tuple[str, ...]) -> list[str]:
    """Drop SageMaker-injected ``--name value`` / ``--name=value`` flags.

    The TensorFlow container always appends a ``--model_dir <s3-path>``
    hyperparameter that our trainer's argparse does not define; pass everything
    else through untouched.
    """

    result: list[str] = []
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
            continue
        if arg in names:
            skip_value = True  # also drop the following value token
            continue
        if any(arg.startswith(name + "=") for name in names):
            continue
        result.append(arg)
    return result


def _dataset_directory(channel: Path) -> Path:
    """Locate the directory that holds manifest.csv within the input channel."""

    if (channel / "manifest.csv").is_file():
        return channel
    candidates = sorted(channel.glob("*/manifest.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No manifest.csv found in the training channel: {channel}"
        )
    return candidates[0].parent


def main() -> None:
    channel = Path(
        os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
    )
    output_dir = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")
    model_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
    dataset_directory = _dataset_directory(channel)

    # SageMaker appends hyperparameters as trailing --key value args; keep them,
    # minus the framework-injected --model_dir (our trainer has no such flag).
    passthrough = _strip_injected_args(sys.argv[1:], ("--model_dir", "--model-dir"))

    # Print the resolved environment first so a mis-mounted channel or bad
    # hyperparameter is obvious at the very top of the CloudWatch log.
    print("=" * 74, flush=True)
    print("SageMaker training entry point", flush=True)
    print(f"  training channel   : {channel}", flush=True)
    print(f"  dataset directory  : {dataset_directory}", flush=True)
    print(f"  output data dir    : {output_dir}", flush=True)
    print(f"  model dir          : {model_dir}", flush=True)
    print(f"  hyperparameters    : {' '.join(passthrough)}", flush=True)
    print("=" * 74, flush=True)

    sys.argv = [
        "train_efficientnet_v2",
        "--square-dataset-directory",
        str(dataset_directory),
        "--experiments-directory",
        output_dir,
        *passthrough,
    ]

    from scripts.train_efficientnet_v2 import main as train_main

    try:
        train_main()
    except BaseException:
        print("\n" + "=" * 74, flush=True)
        print(
            "TRAINING FAILED — traceback follows; a failure.json with the same "
            "error is written under the output data dir.",
            flush=True,
        )
        print("=" * 74, flush=True)
        raise

    # Promote the certified checkpoint (and its completion record) into the
    # model artifact so `estimator.model_data` points at a usable model.
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    checkpoints = sorted(Path(output_dir).glob("*/checkpoints/restored.keras"))
    if not checkpoints:
        print(
            "WARNING: no restored.keras found under "
            f"{output_dir}; SM_MODEL_DIR will be empty.",
            flush=True,
        )
        return
    shutil.copy2(checkpoints[-1], Path(model_dir) / "restored.keras")
    for artifact_name in ("completion.json", "config.json"):
        matches = sorted(Path(output_dir).glob(f"*/{artifact_name}"))
        if matches:
            shutil.copy2(matches[-1], Path(model_dir) / artifact_name)
    print(f"Copied deployable checkpoint to {model_dir}", flush=True)


if __name__ == "__main__":
    main()

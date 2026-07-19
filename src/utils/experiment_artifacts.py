"""Small, durable helpers for experiment artifacts and supervised commands.

The functions in this module intentionally know nothing about a particular
model, dataset, or experiment layout.  They make experiment runners easier to
audit by centralising path handling, atomic artifact writes, content hashes,
and the small amount of process/lock bookkeeping that is shared between runs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, TextIO


# This module lives at ``src/utils``.  Resolving from its own location keeps
# experiment paths stable even when a script is launched outside the project.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PathInput = str | Path


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp suitable for durable records."""

    return datetime.now(timezone.utc).isoformat()


def resolve_path(path: PathInput, *, root: Path = PROJECT_ROOT) -> Path:
    """Resolve an absolute path or a path relative to the project root.

    The target does not need to exist.  ``root`` is injectable for tests or a
    deliberately isolated experiment workspace.
    """

    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def project_relative(path: PathInput, *, root: Path = PROJECT_ROOT) -> str:
    """Return a stable project-relative path when possible.

    Paths outside ``root`` remain absolute so an artifact never records a
    misleading relative path.
    """

    resolved_path = resolve_path(path, root=root)
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def sha256_file(path: PathInput, *, chunk_size: int = 1_048_576) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text_write(
    path: PathInput,
    write_content: Callable[[TextIO], None],
    *,
    newline: str | None = None,
) -> None:
    """Write one UTF-8 file via a sibling temporary file and atomic replace."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline=newline,
        ) as output_file:
            write_content(output_file)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, destination)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        finally:
            raise


def write_json_atomic(path: PathInput, payload: Any) -> None:
    """Write JSON atomically, avoiding half-written experiment records."""

    def write_content(output_file: TextIO) -> None:
        json.dump(payload, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")

    _atomic_text_write(path, write_content)


def read_json(path: PathInput) -> Any:
    """Read and decode a JSON artifact.

    Callers that require an object should validate the returned type at their
    boundary, since valid JSON can also be a list, scalar, or null.
    """

    with Path(path).open(encoding="utf-8") as input_file:
        return json.load(input_file)


def read_json_object(path: PathInput) -> dict[str, Any]:
    """Read a JSON object and reject valid JSON values of any other type."""

    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def write_text_atomic(path: PathInput, content: str) -> None:
    """Write UTF-8 text atomically."""

    _atomic_text_write(path, lambda output_file: output_file.write(content))


def write_csv_atomic(
    path: PathInput,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> None:
    """Write a CSV atomically with the supplied stable column order."""

    ordered_fieldnames = list(fieldnames)
    if not ordered_fieldnames:
        raise ValueError("CSV fieldnames must not be empty")

    def write_content(output_file: TextIO) -> None:
        writer = csv.DictWriter(output_file, fieldnames=ordered_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    _atomic_text_write(path, write_content, newline="")


@dataclass(frozen=True)
class LoggedCommandResult:
    """Outcome and provenance for one command streamed to an experiment log."""

    command: tuple[str, ...]
    log_path: Path
    returncode: int
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float


def run_logged_command(
    command: Sequence[str | Path],
    log_path: PathInput,
    *,
    cwd: PathInput | None = PROJECT_ROOT,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    echo: bool = True,
) -> LoggedCommandResult:
    """Run a command without a shell while teeing combined output to a log.

    ``env`` is passed directly to :class:`subprocess.Popen`; provide a complete
    environment when using it.  Set ``check=False`` to retain a non-zero result
    instead of raising :class:`subprocess.CalledProcessError`.
    """

    normalized_command = tuple(str(part) for part in command)
    if not normalized_command:
        raise ValueError("command must contain at least one argument")

    resolved_log_path = Path(log_path)
    resolved_log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_cwd = None if cwd is None else str(Path(cwd))
    rendered_command = shlex.join(normalized_command)
    started_at_utc = utc_now()
    started_monotonic = time.monotonic()

    if echo:
        print(f"\n$ {rendered_command}", flush=True)

    with resolved_log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Started at UTC: {started_at_utc}\n")
        log_file.write(f"Command: {rendered_command}\n")
        if resolved_cwd is not None:
            log_file.write(f"Working directory: {resolved_cwd}\n")
        log_file.write("\n")
        log_file.flush()

        process = subprocess.Popen(
            normalized_command,
            cwd=resolved_cwd,
            env=None if env is None else dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout is None:  # Defensive: PIPE above should guarantee it.
            raise RuntimeError("Could not capture child-process output")

        with process.stdout:
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                if echo:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        returncode = process.wait()
        finished_at_utc = utc_now()
        elapsed_seconds = time.monotonic() - started_monotonic
        log_file.write(f"\nFinished at UTC: {finished_at_utc}\n")
        log_file.write(f"Exit code: {returncode}\n")
        log_file.write(f"Elapsed seconds: {elapsed_seconds:.3f}\n")

    result = LoggedCommandResult(
        command=normalized_command,
        log_path=resolved_log_path,
        returncode=returncode,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
        elapsed_seconds=elapsed_seconds,
    )
    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, normalized_command)
    return result


class FileLockError(RuntimeError):
    """Raised when another process already owns an exclusive artifact lock."""


@contextmanager
def exclusive_file_lock(
    lock_path: PathInput,
    *,
    purpose: str = "experiment runner",
) -> Iterator[Path]:
    """Hold an exclusive, inspectable lock for the duration of a ``with`` block.

    A forced termination intentionally leaves the lock file behind, making an
    interrupted run visible instead of allowing a second runner to overwrite
    its artifacts.  Normal exits remove only the lock token owned by this call.
    """

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex

    try:
        with path.open("x", encoding="utf-8") as lock_file:
            lock_file.write(
                f"pid={os.getpid()} acquired_at_utc={utc_now()} "
                f"token={token} purpose={purpose}\n"
            )
    except FileExistsError as error:
        raise FileLockError(
            f"Lock already exists: {path}. Inspect it before removing it."
        ) from error

    try:
        yield path
    finally:
        try:
            lock_contents = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            lock_contents = ""
        if f"token={token}" in lock_contents:
            path.unlink()

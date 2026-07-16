"""Extract the nested ZIP64 RDD2022 archives using Python's standard library."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZipInfo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract nested RDD2022 country archives."
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path(
            "data/raw/archives/RDD2022_released_through_CRDDC2022.zip"
        ),
        help="Path to RDD2022_released_through_CRDDC2022.zip.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("data/raw/RDD2022"),
        help="Directory where the expanded RDD2022 dataset will be written.",
    )
    return parser.parse_args()


def safe_extract(archive: ZipFile, destination: Path) -> int:
    """Extract archive members while preventing path-traversal writes."""
    destination = destination.resolve()
    extracted_file_count = 0

    for member in archive.infolist():
        target_path = (destination / member.filename).resolve()

        try:
            target_path.relative_to(destination)
        except ValueError as error:
            raise ValueError(
                f"Unsafe archive path detected: {member.filename}"
            ) from error

        archive.extract(member, path=destination)

        if not member.is_dir():
            extracted_file_count += 1

    return extracted_file_count


def country_archives(release_archive: ZipFile) -> list[ZipInfo]:
    """Return the embedded country-level ZIP files."""
    return [
        member
        for member in release_archive.infolist()
        if not member.is_dir() and member.filename.lower().endswith(".zip")
    ]


def main() -> int:
    args = parse_args()

    if not args.archive.is_file():
        print(f"ERROR: Archive not found: {args.archive}", file=sys.stderr)
        return 2

    if args.destination.exists() and any(args.destination.iterdir()):
        print(
            f"ERROR: Destination is not empty: {args.destination}\n"
            "Choose an empty destination to avoid overwriting files.",
            file=sys.stderr,
        )
        return 2

    args.destination.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(args.archive) as release_archive:
            archives = country_archives(release_archive)

            if not archives:
                raise ValueError("No country ZIP files were found.")

            total_files = 0

            for member in archives:
                country_name = Path(member.filename).stem
                print(f"Extracting {country_name}...")

                with release_archive.open(member) as country_stream:
                    with ZipFile(country_stream) as country_archive:
                        total_files += safe_extract(
                            archive=country_archive,
                            destination=args.destination,
                        )

                print(f"Finished {country_name}.")

    except (BadZipFile, OSError, ValueError) as error:
        print(f"ERROR: Extraction failed: {error}", file=sys.stderr)
        return 1

    print(f"\nExtraction complete: {len(archives)} sources, {total_files:,} files.")
    print(f"Dataset directory: {args.destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

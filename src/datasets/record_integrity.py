"""Generic leakage checks for manifest record roles and dataset splits."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations


def assert_record_sets_disjoint(
    record_sets: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    identity_fields: Sequence[str],
    description: str,
) -> None:
    """Fail if any two named record sets share a protected identity value."""

    if len(record_sets) < 2:
        raise ValueError("At least two record sets are required")
    if not identity_fields:
        raise ValueError("At least one identity field is required")

    for (left_name, left_records), (right_name, right_records) in combinations(
        record_sets.items(),
        2,
    ):
        for field_name in identity_fields:
            left_values = {str(record[field_name]) for record in left_records}
            right_values = {str(record[field_name]) for record in right_records}
            overlap = left_values & right_values
            if overlap:
                raise RuntimeError(
                    f"{description}: {left_name} and {right_name} overlap on "
                    f"{field_name}: {sorted(overlap)[:5]}"
                )

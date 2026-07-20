"""Tests for generic split and experiment-role leakage checks."""

from __future__ import annotations

import unittest

from src.datasets.record_integrity import assert_record_sets_disjoint


class RecordIntegrityTests(unittest.TestCase):
    def test_disjoint_record_sets_pass(self) -> None:
        assert_record_sets_disjoint(
            {
                "train": [{"sequence_group": "group_1"}],
                "val": [{"sequence_group": "group_2"}],
            },
            identity_fields=("sequence_group",),
            description="leakage",
        )

    def test_overlap_identifies_role_and_field(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "train and val overlap on sequence_group",
        ):
            assert_record_sets_disjoint(
                {
                    "train": [{"sequence_group": "group_1"}],
                    "val": [{"sequence_group": "group_1"}],
                },
                identity_fields=("sequence_group",),
                description="leakage",
            )


if __name__ == "__main__":
    unittest.main()

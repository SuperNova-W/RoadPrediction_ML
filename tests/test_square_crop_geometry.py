"""Unit tests for square contextual crop geometry."""

import unittest

from scripts.create_classification_crops import calculate_square_crop_plan


class SquareCropGeometryTests(unittest.TestCase):
    """Exercise normal, boundary, capped, and fallback crop plans."""

    def test_interior_box_produces_centered_square(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=40,
            ymin=45,
            xmax=60,
            ymax=55,
            image_width=100,
            image_height=100,
            context_ratio=0.30,
        )

        self.assertEqual((plan.crop_left, plan.crop_top), (37, 37))
        self.assertEqual((plan.crop_right, plan.crop_bottom), (63, 63))
        self.assertEqual(plan.crop_mode, "in_image")
        self.assertFalse(plan.uses_edge_padding)

    def test_top_left_box_shifts_inside_the_source_image(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=0,
            ymin=0,
            xmax=10,
            ymax=20,
            image_width=100,
            image_height=100,
            context_ratio=0.30,
        )

        self.assertEqual((plan.crop_left, plan.crop_top), (0, 0))
        self.assertEqual((plan.crop_right, plan.crop_bottom), (26, 26))
        self.assertEqual(plan.crop_mode, "in_image")

    def test_bottom_right_box_shifts_inside_the_source_image(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=90,
            ymin=80,
            xmax=100,
            ymax=100,
            image_width=100,
            image_height=100,
            context_ratio=0.30,
        )

        self.assertEqual((plan.crop_left, plan.crop_top), (74, 74))
        self.assertEqual((plan.crop_right, plan.crop_bottom), (100, 100))
        self.assertEqual(plan.crop_mode, "in_image")

    def test_context_is_capped_without_losing_the_annotation(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=30,
            ymin=10,
            xmax=61,
            ymax=20,
            image_width=100,
            image_height=40,
            context_ratio=0.30,
        )

        self.assertEqual(plan.requested_side, 41)
        self.assertEqual(plan.crop_side, 40)
        self.assertEqual(plan.crop_mode, "context_limited")
        self.assertFalse(plan.uses_edge_padding)
        self.assertLessEqual(plan.crop_left, 30)
        self.assertGreaterEqual(plan.crop_right, 61)

    def test_wide_box_uses_explicit_nonblack_padding_fallback(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=20,
            ymin=5,
            xmax=80,
            ymax=10,
            image_width=100,
            image_height=30,
            context_ratio=0.30,
        )

        self.assertEqual(plan.crop_side, 60)
        self.assertEqual(plan.crop_mode, "edge_padded")
        self.assertTrue(plan.uses_edge_padding)
        self.assertLessEqual(plan.crop_left, 20)
        self.assertGreaterEqual(plan.crop_right, 80)
        self.assertLessEqual(plan.crop_top, 5)
        self.assertGreaterEqual(plan.crop_bottom, 10)

    def test_fractional_box_keeps_its_integer_envelope(self) -> None:
        plan = calculate_square_crop_plan(
            xmin=0.9,
            ymin=0.9,
            xmax=1.1,
            ymax=1.1,
            image_width=100,
            image_height=100,
            context_ratio=0.30,
        )

        self.assertEqual(plan.crop_side, 2)
        self.assertEqual(plan.crop_left, 0)
        self.assertEqual(plan.crop_top, 0)
        self.assertGreaterEqual(plan.crop_right, 2)
        self.assertGreaterEqual(plan.crop_bottom, 2)

    def test_out_of_bounds_box_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "extends outside"):
            calculate_square_crop_plan(
                xmin=-1,
                ymin=0,
                xmax=10,
                ymax=10,
                image_width=100,
                image_height=100,
                context_ratio=0.30,
            )


if __name__ == "__main__":
    unittest.main()

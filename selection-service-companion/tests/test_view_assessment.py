from __future__ import annotations

from typing import get_args
import unittest

from selection_service_companion.view_assessment import (
    AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
    MaskReviewPrompt,
    ReviewReason,
    assess_local_view,
    view_assessment_policy_descriptor,
    view_assessment_policy_digest,
)


def _mask(width: int, height: int, foreground: set[tuple[int, int]]) -> bytes:
    data = bytearray((width * height + 7) // 8)
    for x, y in foreground:
        pixel = y * width + x
        data[pixel >> 3] |= 1 << (pixel & 7)
    return bytes(data)


def _block(x0: int, y0: int, x1: int, y1: int) -> set[tuple[int, int]]:
    return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


class LocalMaskReviewPolicyTests(unittest.TestCase):
    def test_policy_is_versioned_and_retires_tracker_and_support_reasons(
        self,
    ) -> None:
        self.assertEqual(
            AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
            "local-view-assessment/v2",
        )
        vocabulary = set(get_args(ReviewReason))
        self.assertEqual(
            vocabulary,
            {
                "prompt-inconsistent",
                "target-materially-clipped",
                "severely-fragmented",
                "box-spill-or-neighbour-leak",
                "empty-or-degenerate-mask",
            },
        )
        self.assertNotIn("propagation-uncertain", vocabulary)
        self.assertNotIn("weak-gaussian-support", vocabulary)
        descriptor = view_assessment_policy_descriptor()
        self.assertEqual(descriptor["clippedMinimumBoundaryRatio"], 0.2)
        self.assertEqual(descriptor["fragmentMinimumDisconnectedRatio"], 0.1)
        self.assertEqual(descriptor["boxSpillMinimumRatio"], 0.2)
        self.assertRegex(view_assessment_policy_digest(), r"^sha256:[a-f0-9]{64}$")

    def test_good_interior_mask_without_a_prompt_family(self) -> None:
        result = assess_local_view(
            width=8,
            height=8,
            mask=_mask(8, 8, _block(2, 2, 5, 5)),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertIsNone(result.primary_reason)
        self.assertEqual(result.actionable_reasons, ())
        # A missing Prompt family is reported as absent, never as a reason.
        self.assertIsNone(result.diagnostics.prompt_point_count)
        self.assertIsNone(result.diagnostics.prompt_violation_count)
        self.assertIsNone(result.diagnostics.box_spill_pixels)
        self.assertIsNone(result.diagnostics.box_spill_ratio)

    def test_any_boundary_contact_does_not_cause_review(self) -> None:
        # A 4x4 block with four edge-contact pixels: the retired policy
        # flagged any one-pixel contact; material clipping requires a margin.
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(0, 2, 3, 5)),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.diagnostics.boundary_pixels, 4)

    def test_thin_object_touching_the_edge_stays_good(self) -> None:
        # A 1px-wide vertical stroke has a high boundary ratio but only two
        # contact pixels, below the material clipping margin.
        result = assess_local_view(
            width=8,
            height=8,
            mask=_mask(8, 8, {(4, y) for y in range(8)}),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.diagnostics.boundary_pixels, 2)

    def test_material_boundary_clipping_enters_review(self) -> None:
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(0, 0, 7, 7)),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(result.reasons, ("target-materially-clipped",))
        self.assertEqual(result.primary_reason, "target-materially-clipped")
        self.assertEqual(result.diagnostics.boundary_pixels, 15)
        self.assertAlmostEqual(
            result.diagnostics.boundary_contact_ratio, 15 / 64
        )

    def test_tiny_extra_components_are_not_severe_fragmentation(self) -> None:
        # Ten speckle pixels exceed the retired largest-component ratio rule
        # but are not material disconnected mass.
        foreground = _block(1, 1, 5, 10) | {
            (8, 2),
            (9, 2),
            (8, 4),
            (9, 4),
            (8, 6),
            (9, 6),
            (8, 8),
            (9, 8),
            (8, 10),
            (9, 10),
        }
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, foreground),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.diagnostics.connected_components, 6)

    def test_material_disconnected_mass_is_severely_fragmented(self) -> None:
        foreground = _block(2, 2, 5, 6) | _block(10, 9, 13, 13)
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, foreground),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(result.reasons, ("severely-fragmented",))
        self.assertEqual(result.diagnostics.connected_components, 2)
        self.assertAlmostEqual(
            result.diagnostics.largest_component_ratio, 0.5
        )

    def test_empty_mask_fails_with_one_structured_reason(self) -> None:
        result = assess_local_view(width=8, height=8, mask=_mask(8, 8, set()))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reasons, ("empty-or-degenerate-mask",))
        self.assertEqual(result.primary_reason, "empty-or-degenerate-mask")
        self.assertEqual(result.actionable_reasons, ())
        self.assertEqual(result.diagnostics.foreground_pixels, 0)

    def test_degenerate_tiny_mask_fails(self) -> None:
        result = assess_local_view(
            width=8,
            height=8,
            mask=_mask(8, 8, {(2, 2), (3, 2), (2, 3)}),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reasons, ("empty-or-degenerate-mask",))

    def test_full_frame_mask_fails(self) -> None:
        result = assess_local_view(
            width=8,
            height=8,
            mask=_mask(8, 8, _block(0, 0, 7, 7)),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reasons, ("empty-or-degenerate-mask",))

    def test_positive_point_outside_the_mask_is_prompt_inconsistent(
        self,
    ) -> None:
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(2, 2, 7, 7)),
            prompt=MaskReviewPrompt(positive_points=((10, 10),)),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(result.reasons, ("prompt-inconsistent",))
        self.assertEqual(result.diagnostics.prompt_point_count, 1)
        self.assertEqual(result.diagnostics.prompt_violation_count, 1)

    def test_negative_point_inside_the_mask_is_prompt_inconsistent(self) -> None:
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(2, 2, 7, 7)),
            prompt=MaskReviewPrompt(
                positive_points=((4, 4),),
                negative_points=((3, 3),),
            ),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(result.reasons, ("prompt-inconsistent",))
        self.assertEqual(result.diagnostics.prompt_point_count, 2)
        self.assertEqual(result.diagnostics.prompt_violation_count, 1)

    def test_consistent_prompt_family_produces_no_reason(self) -> None:
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(2, 2, 7, 7)),
            prompt=MaskReviewPrompt(
                positive_points=((4, 4), (5, 5)),
                negative_points=((10, 10),),
                box_xyxy=(1, 1, 9, 9),
            ),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.diagnostics.prompt_point_count, 3)
        self.assertEqual(result.diagnostics.prompt_violation_count, 0)
        self.assertEqual(result.diagnostics.box_spill_pixels, 0)

    def test_gross_box_spill_enters_review(self) -> None:
        # One connected stroke: inside the margined Box plus a gross leak.
        foreground = _block(4, 4, 26, 6)
        result = assess_local_view(
            width=32,
            height=16,
            mask=_mask(32, 16, foreground),
            prompt=MaskReviewPrompt(
                positive_points=((6, 5),),
                box_xyxy=(2, 2, 12, 12),
            ),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(result.reasons, ("box-spill-or-neighbour-leak",))
        self.assertEqual(result.diagnostics.box_spill_pixels, 36)
        self.assertAlmostEqual(
            result.diagnostics.box_spill_ratio or 0.0, 36 / 69
        )

    def test_minor_box_overflow_is_not_gross_spill(self) -> None:
        foreground = _block(4, 4, 9, 9) | {(17, 5)}
        result = assess_local_view(
            width=24,
            height=24,
            mask=_mask(24, 24, foreground),
            prompt=MaskReviewPrompt(box_xyxy=(2, 2, 14, 14)),
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.diagnostics.box_spill_pixels, 1)

    def test_absent_box_family_never_fabricates_spill(self) -> None:
        result = assess_local_view(
            width=16,
            height=16,
            mask=_mask(16, 16, _block(2, 2, 7, 7)),
            prompt=MaskReviewPrompt(positive_points=((4, 4),)),
        )

        self.assertEqual(result.status, "good")
        self.assertIsNone(result.diagnostics.box_spill_pixels)
        self.assertIsNone(result.diagnostics.box_spill_ratio)

    def test_multiple_reasons_emit_in_deterministic_action_order(self) -> None:
        corner = _block(0, 0, 9, 3) | _block(0, 4, 3, 9)
        foreground = corner | _block(16, 16, 20, 19)
        result = assess_local_view(
            width=24,
            height=24,
            mask=_mask(24, 24, foreground),
            prompt=MaskReviewPrompt(positive_points=((20, 2),)),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(
            result.reasons,
            (
                "prompt-inconsistent",
                "target-materially-clipped",
                "severely-fragmented",
            ),
        )
        self.assertEqual(result.primary_reason, "prompt-inconsistent")
        self.assertEqual(
            result.actionable_reasons,
            ("prompt-inconsistent", "target-materially-clipped"),
        )
        self.assertEqual(
            result.policy_version,
            AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        )

    def test_out_of_bounds_prompt_point_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assess_local_view(
                width=8,
                height=8,
                mask=_mask(8, 8, _block(2, 2, 5, 5)),
                prompt=MaskReviewPrompt(positive_points=((8, 2),)),
            )

    def test_invalid_prompt_box_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assess_local_view(
                width=8,
                height=8,
                mask=_mask(8, 8, _block(2, 2, 5, 5)),
                prompt=MaskReviewPrompt(box_xyxy=(4, 4, 2, 6)),
            )

    def test_mask_length_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assess_local_view(width=8, height=8, mask=bytes(7))


if __name__ == "__main__":
    unittest.main()

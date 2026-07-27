from __future__ import annotations

import unittest

from selection_service_companion.view_assessment import (
    AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
    PropagationDiagnostic,
    SupportDiagnostic,
    assess_local_view,
    local_view_support_diagnostic_id,
)


def _mask(width: int, height: int, foreground: set[tuple[int, int]]) -> bytes:
    data = bytearray((width * height + 7) // 8)
    for x, y in foreground:
        pixel = y * width + x
        data[pixel >> 3] |= 1 << (pixel & 7)
    return bytes(data)


class LocalViewAssessmentPolicyTests(unittest.TestCase):
    def test_support_diagnostic_identity_binds_its_inputs_and_result(self) -> None:
        diagnostic_id = local_view_support_diagnostic_id(
            scene_id="splat-1",
            scene_version="scene-v1",
            view_id="generated-00",
            rgb_digest="sha256:" + "a" * 64,
            stable_mask_digest="sha256:" + "b" * 64,
            observed_gaussian_count=3,
        )

        self.assertEqual(
            diagnostic_id,
            "sha256:0d59600b3bee614e7721059c893536652a13e7c25e3f834e166dcec4c54d0eee",
        )
        self.assertNotEqual(
            diagnostic_id,
            local_view_support_diagnostic_id(
                scene_id="splat-1",
                scene_version="scene-v1",
                view_id="generated-00",
                rgb_digest="sha256:" + "a" * 64,
                stable_mask_digest="sha256:" + "b" * 64,
                observed_gaussian_count=4,
            ),
        )

    def test_emits_multiple_reasons_in_deterministic_action_order(self) -> None:
        width = 8
        height = 8
        result = assess_local_view(
            width=width,
            height=height,
            mask=_mask(
                width,
                height,
                {
                    (0, 1),
                    (0, 2),
                    (1, 1),
                    (1, 2),
                    (6, 6),
                    (7, 6),
                },
            ),
            propagation=PropagationDiagnostic(
                policy_version="generated-view-mask/v1",
                projected_support_count=1,
                prompt_count=1,
            ),
            support=SupportDiagnostic(
                policy_version="anchor-support-probe/v1",
                observed_gaussian_count=3,
            ),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(
            result.reasons,
            (
                "target-at-boundary",
                "fragmented-mask",
                "weak-gaussian-support",
                "propagation-uncertain",
            ),
        )
        self.assertEqual(result.primary_reason, "target-at-boundary")
        self.assertEqual(
            result.actionable_reasons,
            ("target-at-boundary", "fragmented-mask"),
        )
        self.assertEqual(
            result.policy_version,
            AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        )

    def test_missing_support_diagnostic_does_not_invent_weak_support(self) -> None:
        width = 8
        height = 8
        result = assess_local_view(
            width=width,
            height=height,
            mask=_mask(
                width,
                height,
                {(x, y) for y in range(2, 6) for x in range(2, 6)},
            ),
            propagation=None,
            support=None,
        )

        self.assertEqual(result.status, "good")
        self.assertEqual(result.reasons, ())
        self.assertIsNone(result.primary_reason)
        self.assertEqual(result.actionable_reasons, ())
        self.assertIsNone(result.diagnostics.observed_gaussian_count)
        self.assertIsNone(result.support_policy_version)

    def test_empty_mask_fails_without_fabricating_review_semantics(self) -> None:
        result = assess_local_view(
            width=8,
            height=8,
            mask=_mask(8, 8, set()),
            propagation=None,
            support=None,
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reasons, ())
        self.assertIsNone(result.primary_reason)
        self.assertEqual(result.actionable_reasons, ())


if __name__ == "__main__":
    unittest.main()

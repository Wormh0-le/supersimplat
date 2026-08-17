from __future__ import annotations

import math
import unittest

from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
    build_local_evidence_mapping,
    direct_evidence_capability,
    rasterize_projected_direct_evidence,
)
from selection_service_companion.masking import MaskSessionError
from selection_service_companion.reference_gaussian_evidence import (
    PixelEvidenceWeight,
    PixelEvidenceWeights,
)


def weights(
    positive: float,
    negative: float,
    visible: float,
    boundary: float,
) -> PixelEvidenceWeights:
    return PixelEvidenceWeights(
        width=1,
        height=1,
        values=(PixelEvidenceWeight(
            region="test",
            positive=positive,
            negative=negative,
            visible=visible,
            boundary=boundary,
        ),),
    )


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


class DirectEvidenceIdentityTests(unittest.TestCase):
    def test_checked_in_source_and_runtime_identity_are_explicit(self) -> None:
        capability = direct_evidence_capability()

        self.assertEqual(
            capability["status"], "ready" if cuda_available() else "unavailable"
        )
        self.assertEqual(capability["sourceRevision"], DIRECT_EVIDENCE_SOURCE_REVISION)
        self.assertEqual(
            capability["rasterImplementationId"],
            DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        )
        self.assertEqual(
            capability["evidenceBackendId"], DIRECT_EVIDENCE_BACKEND_ID
        )
        self.assertEqual(
            capability["runtimeBuildId"], DIRECT_EVIDENCE_RUNTIME_BUILD_ID
        )
        self.assertEqual(capability["supportedComputeCapabilities"], ["8.9"])

    def test_render_target_and_evidence_identity_mapping_is_fail_closed(self) -> None:
        mapping, evidence_ids, render_ids = build_local_evidence_mapping(
            [20, 10, 30],
            [10],
            [10, 20],
        )
        self.assertEqual(mapping, (-2, 0, -1))
        self.assertEqual(evidence_ids, (10,))
        self.assertEqual(render_ids, (20, 10, 30))

        invalid = (
            ([10, 10], [10], [10]),
            ([10], [10, 11], [10]),
            ([10], [0x1_0000_0000], [0x1_0000_0000]),
        )
        for render, evidence, target in invalid:
            with self.subTest(render=render, evidence=evidence, target=target):
                with self.assertRaises(MaskSessionError):
                    build_local_evidence_mapping(render, evidence, target)

        mapping, evidence_ids, _ = build_local_evidence_mapping(
            [10], [10, 11], [10, 11]
        )
        self.assertEqual(mapping, (0,))
        self.assertEqual(evidence_ids, (10, 11))


@unittest.skipUnless(cuda_available(), "CUDA is required")
class LockedGpuDirectEvidenceTests(unittest.TestCase):
    @staticmethod
    def _projected(*, two_gaussians: bool = False):
        import torch

        count = 2 if two_gaussians else 1
        return {
            "means2d": torch.tensor(
                [[[0.5, 0.5]] * count], dtype=torch.float32, device="cuda"
            ),
            "conics": torch.tensor(
                [[[1.0, 0.0, 1.0]] * count],
                dtype=torch.float32,
                device="cuda",
            ),
            "opacities": torch.tensor(
                [[0.5] * count], dtype=torch.float32, device="cuda"
            ),
            "isect_offsets": torch.tensor(
                [[[0]]], dtype=torch.int32, device="cuda"
            ),
            "flatten_ids": torch.tensor(
                list(range(count)), dtype=torch.int32, device="cuda"
            ),
        }

    def _render(
        self,
        pixel_weights: PixelEvidenceWeights,
        *,
        two_gaussians: bool = False,
        evidence_ids: tuple[int, ...] = (7,),
        target_ids: tuple[int, ...] = (7,),
    ):
        import torch

        count = 2 if two_gaussians else 1
        colors = torch.tensor(
            [[[1.0, 0.0, 0.0]] * count], dtype=torch.float32, device="cuda"
        )
        return rasterize_projected_direct_evidence(
            meta=self._projected(two_gaussians=two_gaussians),
            evaluated_colors=colors,
            background=torch.zeros((1, 3), dtype=torch.float32, device="cuda"),
            render_stable_gaussian_ids=tuple(range(7, 7 + count)),
            evidence_stable_gaussian_ids=evidence_ids,
            target_stable_gaussian_ids=target_ids,
            pixel_weights=pixel_weights,
            width=1,
            height=1,
        )

    def test_same_decision_rgb_and_independent_pnv_share_one_weight(self) -> None:
        result = self._render(weights(2.0, 3.0, 5.0, 7.0))

        self.assertTrue(math.isclose(float(result.alpha.item()), 0.5))
        self.assertTrue(math.isclose(float(result.rgb[0, 0, 0].item()), 0.5))
        self.assertTrue(math.isclose(float(result.positive_mass.item()), 1.0))
        self.assertTrue(math.isclose(float(result.negative_mass.item()), 1.5))
        self.assertTrue(math.isclose(float(result.visible_mass.item()), 2.5))
        self.assertTrue(math.isclose(float(result.boundary_mass.item()), 3.5))
        self.assertNotEqual(
            float(result.positive_mass.item()) + float(result.negative_mass.item()),
            float(result.visible_mass.item()) + 1.0,
        )

    def test_enabling_evidence_writes_does_not_change_authoritative_rgb(self) -> None:
        rgb_only = self._render(weights(0.0, 0.0, 0.0, 0.0))
        with_evidence = self._render(weights(1.0, 1.0, 1.0, 1.0))

        self.assertEqual(rgb_only.service_rgb_digest, with_evidence.service_rgb_digest)
        self.assertEqual(rgb_only.service_rgb_bytes, with_evidence.service_rgb_bytes)
        self.assertEqual(float(rgb_only.positive_mass.item()), 0.0)

    def test_out_of_set_target_triggers_boundary_diagnostic_but_occluder_stays(self) -> None:
        result = self._render(
            weights(1.0, 0.0, 1.0, 0.0),
            two_gaussians=True,
            evidence_ids=(7,),
            target_ids=(7, 8),
        )

        self.assertEqual(result.stable_gaussian_ids, (7,))
        self.assertEqual(result.boundary_contact_stable_gaussian_ids, (8,))
        self.assertTrue(math.isclose(float(result.positive_mass.item()), 0.5))
        self.assertTrue(math.isclose(float(result.alpha.item()), 0.75))

    def test_later_included_view_expansion_recovers_seed_boundary_target(self) -> None:
        seeded = self._render(
            weights(1.0, 0.0, 1.0, 0.0),
            two_gaussians=True,
            evidence_ids=(7,),
            target_ids=(7, 8),
        )
        expanded = self._render(
            weights(1.0, 0.0, 1.0, 0.0),
            two_gaussians=True,
            evidence_ids=(7, 8),
            target_ids=(7, 8),
        )

        self.assertEqual(seeded.boundary_contact_stable_gaussian_ids, (8,))
        self.assertEqual(expanded.boundary_contact_stable_gaussian_ids, ())
        self.assertEqual(expanded.stable_gaussian_ids, (7, 8))
        self.assertTrue(
            math.isclose(float(expanded.positive_mass[1].item()), 0.25)
        )

    def test_non_target_occluder_affects_rgb_and_transmittance_without_evidence_writes(self) -> None:
        result = self._render(
            weights(1.0, 0.0, 1.0, 0.0),
            two_gaussians=True,
            evidence_ids=(7,),
            target_ids=(7,),
        )

        self.assertEqual(result.boundary_contact_stable_gaussian_ids, ())
        self.assertTrue(math.isclose(float(result.positive_mass.item()), 0.5))
        self.assertTrue(math.isclose(float(result.visible_mass.item()), 0.5))
        self.assertTrue(math.isclose(float(result.alpha.item()), 0.75))
        self.assertTrue(math.isclose(float(result.rgb[0, 0, 0].item()), 0.75))


if __name__ == "__main__":
    unittest.main()

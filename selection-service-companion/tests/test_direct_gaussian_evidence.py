from __future__ import annotations

import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import selection_service_companion.direct_gaussian_evidence as direct_evidence_module
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
    build_local_evidence_mapping,
    direct_evidence_capability,
    rasterize_projected_authoritative_rgb,
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
            DIRECT_EVIDENCE_SOURCE_REVISION,
            "sha256:3c14ab06a3f60c893de9e86d7242269e0eb43b253b1808ebbec8e60b59fae917",
        )
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
        self.assertEqual(
            DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
            "sha256:b87858ec0baaeea5cc272e02273f8f3a13410f4322c33c088fed4b4144ecf1e0",
        )
        self.assertEqual(
            capability["abiVersion"], "supersimplat-direct-evidence-abi/v2"
        )
        self.assertEqual(
            DIRECT_EVIDENCE_ABI_VERSION, "supersimplat-direct-evidence-abi/v2"
        )
        self.assertEqual(capability["supportedComputeCapabilities"], ["8.9"])

    def test_stale_loaded_extension_cannot_advertise_ready(self) -> None:
        stale = SimpleNamespace(
            __name__="supersimplat_direct_evidence_stale",
            abi_version="supersimplat-direct-evidence-abi/v1",
        )
        with patch.object(direct_evidence_module, "_EXTENSION", stale):
            capability = direct_evidence_capability()

        self.assertEqual(capability["status"], "unavailable")

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
            "depths": torch.tensor(
                [[float(index + 1) for index in range(count)]],
                dtype=torch.float32,
                device="cuda",
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

    def test_invalid_projected_depth_fails_closed_before_direct_evidence_dispatch(
        self,
    ) -> None:
        import torch

        valid = self._projected(two_gaussians=True)
        invalid_depths = {
            "missing": None,
            "wrong-shape": torch.tensor(
                [1.0, 2.0], dtype=torch.float32, device="cuda"
            ),
            "wrong-dtype": torch.tensor(
                [[1.0, 2.0]], dtype=torch.float64, device="cuda"
            ),
            "non-contiguous": torch.tensor(
                [[1.0, 0.0, 2.0, 0.0]], dtype=torch.float32, device="cuda"
            )[:, ::2],
            "non-finite": torch.tensor(
                [[1.0, float("nan")]], dtype=torch.float32, device="cuda"
            ),
            "wrong-device": torch.tensor(
                [[1.0, 2.0]], dtype=torch.float32, device="cpu"
            ),
        }
        for name, depths in invalid_depths.items():
            with self.subTest(name=name):
                meta = dict(valid)
                if depths is None:
                    del meta["depths"]
                else:
                    meta["depths"] = depths
                with self.assertRaises(MaskSessionError) as raised:
                    rasterize_projected_direct_evidence(
                        meta=meta,
                        evaluated_colors=torch.ones(
                            (1, 2, 3), dtype=torch.float32, device="cuda"
                        ),
                        background=torch.zeros(
                            (1, 3), dtype=torch.float32, device="cuda"
                        ),
                        render_stable_gaussian_ids=(7, 8),
                        evidence_stable_gaussian_ids=(7, 8),
                        target_stable_gaussian_ids=(7, 8),
                        pixel_weights=weights(1.0, 0.0, 1.0, 0.0),
                        width=1,
                        height=1,
                    )
                self.assertEqual(
                    raised.exception.code, "rendererInvalidEvidenceMapping"
                )

    def test_missing_projected_depth_fails_closed_before_authoritative_rgb_dispatch(
        self,
    ) -> None:
        import torch

        meta = self._projected()
        del meta["depths"]
        with self.assertRaises(MaskSessionError) as raised:
            rasterize_projected_authoritative_rgb(
                meta=meta,
                evaluated_colors=torch.ones(
                    (1, 1, 3), dtype=torch.float32, device="cuda"
                ),
                background=torch.zeros(
                    (1, 3), dtype=torch.float32, device="cuda"
                ),
                width=1,
                height=1,
            )
        self.assertEqual(raised.exception.code, "rendererFailure")

    def test_projected_depth_rows_reach_the_compiled_abi_without_reordering(
        self,
    ) -> None:
        import torch

        meta = self._projected(two_gaussians=True)
        meta["depths"] = torch.tensor(
            [[11.0, 29.0]], dtype=torch.float32, device="cuda"
        )
        meta["flatten_ids"] = torch.tensor(
            [1, 0], dtype=torch.int32, device="cuda"
        )
        real_extension = direct_evidence_module._load_extension()
        self.assertEqual(real_extension.abi_version, DIRECT_EVIDENCE_ABI_VERSION)
        self.assertEqual(
            real_extension.__name__,
            "supersimplat_direct_evidence_"
            + DIRECT_EVIDENCE_RUNTIME_BUILD_ID.removeprefix("sha256:")[:16],
        )
        compiled_rows = real_extension.probe_projected_depth_rows(
            meta["depths"], meta["flatten_ids"]
        )
        self.assertEqual(
            compiled_rows.detach().cpu().tolist(),
            [29.0, 11.0],
        )
        captured: list[tuple[object, ...]] = []

        class RecordingExtension:
            def rasterize_direct_evidence(self, *args: object):
                captured.append(args)
                return real_extension.rasterize_direct_evidence(*args)

        with patch.object(
            direct_evidence_module,
            "_load_extension",
            return_value=RecordingExtension(),
        ):
            rasterize_projected_direct_evidence(
                meta=meta,
                evaluated_colors=torch.tensor(
                    [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
                    dtype=torch.float32,
                    device="cuda",
                ),
                background=torch.zeros(
                    (1, 3), dtype=torch.float32, device="cuda"
                ),
                render_stable_gaussian_ids=(7, 8),
                evidence_stable_gaussian_ids=(7, 8),
                target_stable_gaussian_ids=(7, 8),
                pixel_weights=weights(1.0, 0.0, 1.0, 0.0),
                width=1,
                height=1,
            )

        self.assertEqual(len(captured), 1)
        abi_args = captured[0]
        abi_depths = abi_args[1]
        abi_flatten_ids = abi_args[7]
        self.assertEqual(abi_depths.data_ptr(), meta["depths"].data_ptr())
        self.assertEqual(abi_depths.stride(), meta["depths"].stride())
        self.assertEqual(abi_flatten_ids.detach().cpu().tolist(), [1, 0])
        self.assertEqual(
            abi_depths[0, abi_flatten_ids.to(torch.int64)]
            .detach()
            .cpu()
            .tolist(),
            [29.0, 11.0],
        )

    def test_same_decision_rgb_and_independent_pnv_share_one_weight(self) -> None:
        result = self._render(weights(2.0, 3.0, 5.0, 7.0))

        self.assertEqual(
            result.service_rgb_digest,
            "sha256:25ff297dd78c82468376d6e2c93b672b49c01fb125a2812b94f8f9693a51b67e",
        )
        self.assertEqual(result.service_rgb_bytes, bytes((128, 0, 0)))
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

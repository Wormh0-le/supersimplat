from __future__ import annotations

import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import selection_service_companion.direct_gaussian_evidence as direct_evidence_module
from selection_service_companion.depth_moments import (
    DepthMomentValidityPolicy,
    ScalarDepthContributor,
    derive_depth_moment_readout,
    rasterize_scalar_depth_moments,
)
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
            "sha256:dd40059d5bdd9fa9a06e6a9752f77775084ca1924878bf7a3c4504a46b89242e",
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
            "sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f",
        )
        self.assertEqual(
            capability["abiVersion"], "supersimplat-direct-evidence-abi/v3"
        )
        self.assertEqual(
            DIRECT_EVIDENCE_ABI_VERSION, "supersimplat-direct-evidence-abi/v3"
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
        depth_moments_enabled: bool = False,
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
            depth_moments_enabled=depth_moments_enabled,
        )

    def test_moment_image_is_allocated_only_when_explicitly_enabled(self) -> None:
        import torch

        real_extension = direct_evidence_module._load_extension()
        disabled_raw_shapes: list[tuple[int, ...]] = []

        class RecordingExtension:
            def rasterize_direct_evidence(self, *args: object):
                output = real_extension.rasterize_direct_evidence(*args)
                disabled_raw_shapes.append(tuple(output[3].shape))
                return output

        with patch.object(
            direct_evidence_module,
            "_load_extension",
            return_value=RecordingExtension(),
        ):
            disabled = self._render(
                weights(2.0, 3.0, 5.0, 7.0),
                depth_moments_enabled=False,
            )
        enabled = self._render(
            weights(2.0, 3.0, 5.0, 7.0),
            depth_moments_enabled=True,
        )

        self.assertEqual(disabled_raw_shapes, [(0,)])
        self.assertIsNone(disabled.depth_moments)
        self.assertEqual(disabled.telemetry.depth_moment_buffer_bytes, 0)
        self.assertGreater(disabled.telemetry.peak_vram_bytes, 0)
        self.assertIsNotNone(enabled.depth_moments)
        self.assertEqual(enabled.depth_moments.dtype, torch.float32)
        self.assertTrue(enabled.depth_moments.is_contiguous())
        self.assertEqual(tuple(enabled.depth_moments.shape), (1, 1, 3))
        self.assertEqual(
            enabled.depth_moments.detach().cpu().tolist(),
            [[[0.5, 0.5, 0.5]]],
        )
        self.assertEqual(enabled.telemetry.depth_moment_buffer_bytes, 12)
        self.assertGreater(enabled.telemetry.peak_vram_bytes, 0)
        self.assertEqual(disabled.service_rgb_digest, enabled.service_rgb_digest)
        self.assertEqual(disabled.service_rgb_bytes, enabled.service_rgb_bytes)
        self.assertEqual(disabled.stable_gaussian_ids, enabled.stable_gaussian_ids)
        self.assertEqual(
            disabled.boundary_contact_stable_gaussian_ids,
            enabled.boundary_contact_stable_gaussian_ids,
        )
        self.assertTrue(torch.equal(disabled.rgb, enabled.rgb))
        self.assertTrue(torch.equal(disabled.alpha, enabled.alpha))
        self.assertTrue(torch.equal(disabled.positive_mass, enabled.positive_mass))
        self.assertTrue(torch.equal(disabled.negative_mass, enabled.negative_mass))
        self.assertTrue(torch.equal(disabled.visible_mass, enabled.visible_mass))
        self.assertTrue(torch.equal(disabled.boundary_mass, enabled.boundary_mass))

    def test_cuda_depth_moments_match_the_scalar_accepted_chain(self) -> None:
        import torch

        cases = (
            (
                "zero-mass",
                ((0.5, 0.5),),
                ((1.0, 0.0, 1.0),),
                (0.0,),
                (4.0,),
                (ScalarDepthContributor(0.0, 0.0, 4.0),),
            ),
            (
                "one-layer",
                ((0.5, 0.5),),
                ((1.0, 0.0, 1.0),),
                (0.5,),
                (4.0,),
                (ScalarDepthContributor(0.0, 0.5, 4.0),),
            ),
            (
                "two-layer",
                ((0.5, 0.5), (0.5, 0.5)),
                ((1.0, 0.0, 1.0), (1.0, 0.0, 1.0)),
                (0.5, 0.5),
                (2.0, 6.0),
                (
                    ScalarDepthContributor(0.0, 0.5, 2.0),
                    ScalarDepthContributor(0.0, 0.5, 6.0),
                ),
            ),
            (
                "rejected-and-terminated",
                (
                    (1.5, 0.5),
                    (0.5, 0.5),
                    (0.5, 0.5),
                    (0.5, 0.5),
                    (0.5, 0.5),
                    (0.5, 0.5),
                ),
                (
                    (-2.0, 0.0, 0.0),
                    (1.0, 0.0, 1.0),
                    (1.0, 0.0, 1.0),
                    (1.0, 0.0, 1.0),
                    (1.0, 0.0, 1.0),
                    (1.0, 0.0, 1.0),
                ),
                (1.0, 0.001, 0.5, 1.0, 1.0, 0.5),
                (100.0, 100.0, 3.0, 5.0, 100.0, 200.0),
                (
                    ScalarDepthContributor(-1.0, 1.0, 100.0),
                    ScalarDepthContributor(0.0, 0.001, 100.0),
                    ScalarDepthContributor(0.0, 0.5, 3.0),
                    ScalarDepthContributor(0.0, 1.0, 5.0),
                    ScalarDepthContributor(0.0, 1.0, 100.0),
                    ScalarDepthContributor(0.0, 0.5, 200.0),
                ),
            ),
        )
        policy = DepthMomentValidityPolicy(
            policy_id="depth-moment-minimum-m0/cuda-parity-test-v1",
            minimum_m0=0.01,
        )
        for name, means, conics, opacities, depths, contributors in cases:
            with self.subTest(name=name):
                count = len(depths)
                meta = {
                    "means2d": torch.tensor(
                        [means], dtype=torch.float32, device="cuda"
                    ),
                    "conics": torch.tensor(
                        [conics], dtype=torch.float32, device="cuda"
                    ),
                    "opacities": torch.tensor(
                        [opacities], dtype=torch.float32, device="cuda"
                    ),
                    "depths": torch.tensor(
                        [depths], dtype=torch.float32, device="cuda"
                    ),
                    "isect_offsets": torch.tensor(
                        [[[0]]], dtype=torch.int32, device="cuda"
                    ),
                    "flatten_ids": torch.arange(
                        count, dtype=torch.int32, device="cuda"
                    ),
                }
                result = rasterize_projected_direct_evidence(
                    meta=meta,
                    evaluated_colors=torch.ones(
                        (1, count, 3), dtype=torch.float32, device="cuda"
                    ),
                    background=torch.zeros(
                        (1, 3), dtype=torch.float32, device="cuda"
                    ),
                    render_stable_gaussian_ids=tuple(range(7, 7 + count)),
                    evidence_stable_gaussian_ids=tuple(range(7, 7 + count)),
                    target_stable_gaussian_ids=tuple(range(7, 7 + count)),
                    pixel_weights=weights(1.0, 1.0, 1.0, 1.0),
                    width=1,
                    height=1,
                    depth_moments_enabled=True,
                )
                scalar = rasterize_scalar_depth_moments(contributors)
                expected = torch.tensor(
                    [[[scalar.m0, scalar.m1, scalar.m2]]],
                    dtype=torch.float32,
                )
                torch.testing.assert_close(
                    result.depth_moments.detach().cpu(),
                    expected,
                    rtol=1.0e-6,
                    atol=1.0e-6,
                )
                actual_readout = derive_depth_moment_readout(
                    result.depth_moments.detach().cpu(), policy=policy
                )
                expected_readout = derive_depth_moment_readout(
                    expected, policy=policy
                )
                self.assertTrue(
                    torch.equal(actual_readout.valid, expected_readout.valid)
                )
                torch.testing.assert_close(
                    actual_readout.cwed,
                    expected_readout.cwed,
                    rtol=1.0e-6,
                    atol=1.0e-6,
                    equal_nan=True,
                )
                torch.testing.assert_close(
                    actual_readout.variance,
                    expected_readout.variance,
                    rtol=1.0e-6,
                    atol=1.0e-6,
                    equal_nan=True,
                )
                if name == "two-layer":
                    self.assertTrue(bool(actual_readout.valid.item()))
                    self.assertGreater(float(actual_readout.variance.item()), 0.0)

    def test_nonfinite_moments_do_not_replace_valid_rgb_or_evidence(self) -> None:
        import torch

        baseline = self._render(
            weights(2.0, 3.0, 5.0, 7.0),
            depth_moments_enabled=False,
        )
        real_extension = direct_evidence_module._load_extension()

        class NonfiniteMomentExtension:
            def rasterize_direct_evidence(self, *args: object):
                output = list(real_extension.rasterize_direct_evidence(*args))
                output[3] = torch.full_like(output[3], float("nan"))
                return output

        with patch.object(
            direct_evidence_module,
            "_load_extension",
            return_value=NonfiniteMomentExtension(),
        ):
            result = self._render(
                weights(2.0, 3.0, 5.0, 7.0),
                depth_moments_enabled=True,
            )

        self.assertIsNotNone(result.depth_moments)
        readout = derive_depth_moment_readout(
            result.depth_moments,
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/nonfinite-test-v1",
                minimum_m0=0.01,
            ),
        )
        self.assertFalse(bool(readout.valid.item()))
        self.assertTrue(bool(torch.isnan(readout.cwed).all().item()))
        self.assertTrue(bool(torch.isnan(readout.variance).all().item()))
        self.assertEqual(result.service_rgb_digest, baseline.service_rgb_digest)
        self.assertTrue(torch.equal(result.alpha, baseline.alpha))
        self.assertTrue(torch.equal(result.positive_mass, baseline.positive_mass))
        self.assertTrue(torch.equal(result.negative_mass, baseline.negative_mass))
        self.assertTrue(torch.equal(result.visible_mass, baseline.visible_mass))
        self.assertTrue(torch.equal(result.boundary_mass, baseline.boundary_mass))

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

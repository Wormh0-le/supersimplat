from __future__ import annotations

import unittest

from selection_service_companion.depth_moments import (
    DepthMomentValidityPolicy,
    ScalarDepthContributor,
    derive_depth_moment_readout,
    rasterize_scalar_depth_moments,
)


class DepthMomentReferenceTests(unittest.TestCase):
    def test_zero_mass_is_explicitly_invalid(self) -> None:
        import torch

        moments = rasterize_scalar_depth_moments(())
        self.assertEqual((moments.m0, moments.m1, moments.m2), (0.0, 0.0, 0.0))

        readout = derive_depth_moment_readout(
            torch.tensor([[[moments.m0, moments.m1, moments.m2]]]),
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/test-v1",
                minimum_m0=0.01,
            ),
        )

        self.assertEqual(readout.valid.dtype, torch.bool)
        self.assertFalse(bool(readout.valid[0, 0].item()))
        self.assertTrue(bool(torch.isnan(readout.cwed[0, 0]).item()))
        self.assertTrue(bool(torch.isnan(readout.variance[0, 0]).item()))

    def test_one_layer_cwed_is_the_contributor_depth(self) -> None:
        import torch

        moments = rasterize_scalar_depth_moments((
            ScalarDepthContributor(sigma=0.0, opacity=0.5, projected_depth=4.0),
        ))
        self.assertEqual((moments.m0, moments.m1, moments.m2), (0.5, 2.0, 8.0))

        readout = derive_depth_moment_readout(
            torch.tensor([[[moments.m0, moments.m1, moments.m2]]]),
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/test-v1",
                minimum_m0=0.01,
            ),
        )

        self.assertTrue(bool(readout.valid[0, 0].item()))
        self.assertEqual(float(readout.cwed[0, 0].item()), 4.0)
        self.assertEqual(float(readout.variance[0, 0].item()), 0.0)

    def test_two_layers_produce_weighted_depth_and_positive_dispersion(self) -> None:
        import torch

        moments = rasterize_scalar_depth_moments((
            ScalarDepthContributor(sigma=0.0, opacity=0.5, projected_depth=2.0),
            ScalarDepthContributor(sigma=0.0, opacity=0.5, projected_depth=6.0),
        ))
        self.assertEqual((moments.m0, moments.m1, moments.m2), (0.75, 2.5, 11.0))

        readout = derive_depth_moment_readout(
            torch.tensor([[[moments.m0, moments.m1, moments.m2]]]),
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/test-v1",
                minimum_m0=0.01,
            ),
        )

        self.assertTrue(bool(readout.valid[0, 0].item()))
        self.assertAlmostEqual(float(readout.cwed[0, 0].item()), 10.0 / 3.0, places=6)
        self.assertAlmostEqual(
            float(readout.variance[0, 0].item()), 32.0 / 9.0, delta=1.0e-6
        )

    def test_minimum_mass_is_selected_by_the_versioned_caller_policy(self) -> None:
        import torch

        raw = torch.tensor([[[0.005, 0.015, 0.045]]], dtype=torch.float32)
        strict = derive_depth_moment_readout(
            raw,
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/strict-test-v1",
                minimum_m0=0.01,
            ),
        )
        permissive = derive_depth_moment_readout(
            raw,
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/permissive-test-v1",
                minimum_m0=0.001,
            ),
        )

        self.assertFalse(bool(strict.valid[0, 0].item()))
        self.assertTrue(bool(permissive.valid[0, 0].item()))
        self.assertEqual(permissive.policy.policy_id, "depth-moment-minimum-m0/permissive-test-v1")
        self.assertAlmostEqual(float(permissive.cwed[0, 0].item()), 3.0, places=6)

    def test_rejected_and_post_termination_contributors_never_enter_moments(self) -> None:
        moments = rasterize_scalar_depth_moments((
            ScalarDepthContributor(sigma=-1000.0, opacity=1.0, projected_depth=100.0),
            ScalarDepthContributor(sigma=0.0, opacity=0.001, projected_depth=100.0),
            ScalarDepthContributor(sigma=0.0, opacity=0.5, projected_depth=3.0),
            ScalarDepthContributor(sigma=0.0, opacity=1.0, projected_depth=5.0),
            ScalarDepthContributor(sigma=0.0, opacity=1.0, projected_depth=100.0),
            ScalarDepthContributor(sigma=0.0, opacity=0.5, projected_depth=200.0),
        ))

        self.assertAlmostEqual(moments.m0, 0.995, places=12)
        self.assertAlmostEqual(moments.m1, 3.975, places=12)
        self.assertAlmostEqual(moments.m2, 16.875, places=12)

    def test_variance_clamping_is_bounded_and_nonfinite_pixels_are_invalid(self) -> None:
        import torch

        readout = derive_depth_moment_readout(
            torch.tensor(
                [[
                    [1.0, 3.0, 8.9999995],
                    [1.0, 3.0, 8.9],
                    [1.0, float("nan"), 9.0],
                ]],
                dtype=torch.float32,
            ),
            policy=DepthMomentValidityPolicy(
                policy_id="depth-moment-minimum-m0/test-v1",
                minimum_m0=0.01,
            ),
        )

        self.assertEqual(readout.valid.tolist(), [[True, False, False]])
        self.assertEqual(float(readout.variance[0, 0].item()), 0.0)
        self.assertTrue(bool(torch.isnan(readout.cwed[0, 1:]).all().item()))
        self.assertTrue(bool(torch.isnan(readout.variance[0, 1:]).all().item()))


if __name__ == "__main__":
    unittest.main()

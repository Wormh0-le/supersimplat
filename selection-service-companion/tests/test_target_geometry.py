"""Ticket 08 TargetGeometryHint derivation policy tests (pure CPU fixtures).

Every fixture is hand-computed exact arithmetic over identity/simple cameras:
the derivation must replay deterministically, bound its visible points, filter
invalid/background/separated support, and never emit ownership data.
"""

from __future__ import annotations

import struct
import unittest

from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.support_probe import AnchorSupportProbeCamera
from selection_service_companion.target_geometry import (
    derive_target_geometry_hint,
    local_key_view_policy_digest,
    target_geometry_policy_digest,
)


# 4x4 identity camera: camera coordinates equal world coordinates.
PROBE_CAMERA = AnchorSupportProbeCamera(
    world_to_camera=(
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ),
    fx=10.0,
    fy=10.0,
    cx=2.0,
    cy=2.0,
    width=4,
    height=4,
    near=0.1,
    far=100.0,
)

# 8x8 identity camera for the usable/separated fixtures.
PROBE_CAMERA_8 = AnchorSupportProbeCamera(
    world_to_camera=PROBE_CAMERA.world_to_camera,
    fx=8.0,
    fy=8.0,
    cx=4.0,
    cy=4.0,
    width=8,
    height=8,
    near=0.1,
    far=100.0,
)

# 16x16 identity camera for the stride-bound fixture.
PROBE_CAMERA_16 = AnchorSupportProbeCamera(
    world_to_camera=PROBE_CAMERA.world_to_camera,
    fx=4.0,
    fy=4.0,
    cx=8.0,
    cy=8.0,
    width=16,
    height=16,
    near=0.1,
    far=100.0,
)


def _planes(
    gaussians: tuple[tuple[tuple[float, float, float], float], ...]
) -> list[tuple[memoryview, memoryview]]:
    means = b"".join(struct.pack("<3f", *mean) for mean, _ in gaussians)
    logits = b"".join(struct.pack("<f", logit) for _, logit in gaussians)
    return [(memoryview(means), memoryview(logits))]


def _mask(width: int, height: int, pixels: tuple[int, ...]) -> bytes:
    data = bytearray((width * height + 7) // 8)
    for pixel in pixels:
        data[pixel >> 3] |= 1 << (pixel & 7)
    return bytes(data)


class TargetGeometryHintDerivationTests(unittest.TestCase):
    def test_first_hit_keeps_the_nearest_gaussian_per_mask_pixel(self) -> None:
        # (0, 0, 2) and (0, 0, 5) both project to pixel (2, 2) = 10; the
        # nearer mean is the first-hit visible-surface sample. Projections:
        # (-0.1875, -0.1875, 2) -> (1, 1) = 5; (0, -0.25, 2) -> (2, 1) = 6.
        planes = _planes(
            (
                ((0.0, 0.0, 5.0), 1.0),
                ((0.0, 0.0, 2.0), 1.0),
                ((-0.1875, -0.1875, 2.0), 1.0),
                ((0.0, -0.25, 2.0), 1.0),
                ((0.0, 0.0, -5.0), 1.0),   # behind the camera: excluded
                ((0.0, 0.0, 2.0), -1.0),   # alpha < 0.5: excluded
            )
        )
        hint = derive_target_geometry_hint(
            planes=planes,
            camera=PROBE_CAMERA,
            mask=_mask(4, 4, (5, 6, 10)),
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        # Ascending source pixel order: 5, 6, 10.
        self.assertEqual(
            hint.visible_points,
            ((-0.1875, -0.1875, 2.0), (0.0, -0.25, 2.0), (0.0, 0.0, 2.0)),
        )
        self.assertEqual(hint.center, (0.0, -0.1875, 2.0))
        self.assertAlmostEqual(hint.extent[0], 1e-3)
        self.assertAlmostEqual(hint.extent[1], 1.4826 * 0.0625)
        self.assertAlmostEqual(hint.extent[2], 1e-3)
        self.assertEqual(hint.quality, "limited")
        self.assertEqual(hint.reasons, ("sparseSupport",))

    def test_first_hit_skips_a_nearer_gaussian_below_the_opacity_gate(self) -> None:
        planes = _planes(
            (
                ((0.0, 0.0, 2.0), -0.5),  # alpha < 0.5: not a visible surface
                ((0.0, 0.0, 5.0), 1.0),
            )
        )
        hint = derive_target_geometry_hint(
            planes=planes, camera=PROBE_CAMERA, mask=_mask(4, 4, (10,))
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(hint.visible_points, ((0.0, 0.0, 5.0),))

    def test_usable_cluster_golden_vector(self) -> None:
        # z = 4, u = round(4 + 2x), v = round(4 + 2y): eight distinct
        # non-border pixels from exact-decimal world means.
        gaussians = tuple(
            ((x, y, 4.0), 1.0)
            for x, y in (
                (-1.0, -1.0), (0.0, -1.0), (1.0, -1.0),
                (-1.0, 0.0), (1.0, 0.0),
                (-1.0, 1.0), (0.0, 1.0), (1.0, 1.0),
            )
        )
        hint = derive_target_geometry_hint(
            planes=_planes(gaussians),
            camera=PROBE_CAMERA_8,
            mask=_mask(8, 8, (18, 20, 22, 34, 38, 50, 52, 54)),
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(
            hint.visible_points,
            (
                (-1.0, -1.0, 4.0), (0.0, -1.0, 4.0), (1.0, -1.0, 4.0),
                (-1.0, 0.0, 4.0), (1.0, 0.0, 4.0),
                (-1.0, 1.0, 4.0), (0.0, 1.0, 4.0), (1.0, 1.0, 4.0),
            ),
        )
        self.assertEqual(hint.center, (0.0, 0.0, 4.0))
        self.assertAlmostEqual(hint.extent[0], 1.4826)
        self.assertAlmostEqual(hint.extent[1], 1.4826)
        self.assertAlmostEqual(hint.extent[2], 1e-3)
        self.assertEqual(hint.quality, "usable")
        self.assertEqual(hint.reasons, ())

    def test_separated_background_support_is_filtered(self) -> None:
        # Eight in-cluster means at z = 4 plus three separated means at z = 20
        # on distinct pixels; the separated 3/11 fraction exceeds 0.25 and is
        # filtered before center/extent statistics.
        cluster = tuple(
            ((x, y, 4.0), 1.0)
            for x, y in (
                (-0.5, -0.5), (0.0, -0.5), (0.5, -0.5),
                (-0.5, 0.0), (0.5, 0.0),
                (-0.5, 0.5), (0.0, 0.5), (0.5, 0.5),
            )
        )
        separated = (
            ((-5.0, -2.5, 20.0), 1.0),   # pixel (2, 3) = 26
            ((0.0, 0.0, 20.0), 1.0),     # pixel (4, 4) = 36
            ((5.0, 2.5, 20.0), 1.0),     # pixel (6, 5) = 46
        )
        hint = derive_target_geometry_hint(
            planes=_planes(cluster + separated),
            camera=PROBE_CAMERA_8,
            mask=_mask(
                8, 8, (26, 27, 28, 29, 35, 36, 37, 43, 44, 45, 46)
            ),
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(len(hint.visible_points), 8)
        self.assertEqual(hint.center, (0.0, 0.0, 4.0))
        self.assertAlmostEqual(hint.extent[0], 0.7413)
        self.assertAlmostEqual(hint.extent[1], 0.7413)
        self.assertAlmostEqual(hint.extent[2], 1e-3)
        self.assertEqual(hint.quality, "limited")
        self.assertEqual(hint.reasons, ("separatedSupportFiltered",))
        self.assertEqual(hint.prompt_support, "usable")

    def test_frame_boundary_contact_lowers_quality(self) -> None:
        gaussians = tuple(
            ((x, y, 4.0), 1.0)
            for x, y in (
                (-1.0, -1.0), (0.0, -1.0), (1.0, -1.0),
                (-1.0, 0.0), (1.0, 0.0),
                (-1.0, 1.0), (0.0, 1.0), (1.0, 1.0),
            )
        )
        # Pixel 0 sits on the frame border with no Gaussian support at all;
        # border contact alone lowers quality.
        hint = derive_target_geometry_hint(
            planes=_planes(gaussians),
            camera=PROBE_CAMERA_8,
            mask=_mask(8, 8, (0, 18, 20, 22, 34, 38, 50, 52, 54)),
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(len(hint.visible_points), 8)
        self.assertEqual(hint.quality, "limited")
        self.assertEqual(hint.reasons, ("frameBoundaryContact",))
        self.assertEqual(hint.prompt_support, "limited")

    def test_visible_points_are_bounded_by_a_deterministic_stride(self) -> None:
        # 100 first-hit samples on pixels (u, v) for u, v in 1..10 of the 16x16
        # frame: world (u - 8, v - 8, 4) projects exactly to pixel v * 16 + u.
        gaussians = tuple(
            ((float(u - 8), float(v - 8), 4.0), 1.0)
            for v in range(1, 11)
            for u in range(1, 11)
        )
        pixels = tuple(v * 16 + u for v in range(1, 11) for u in range(1, 11))
        hint = derive_target_geometry_hint(
            planes=_planes(gaussians),
            camera=PROBE_CAMERA_16,
            mask=_mask(16, 16, pixels),
        )

        self.assertIsNotNone(hint)
        assert hint is not None
        expected_ordered = tuple(
            (float(u - 8), float(v - 8), 4.0)
            for v in range(1, 11)
            for u in range(1, 11)
        )
        self.assertEqual(hint.visible_points, expected_ordered[::2])
        self.assertEqual(len(hint.visible_points), 50)
        self.assertEqual(hint.visible_points[0], (-7.0, -7.0, 4.0))
        self.assertEqual(hint.visible_points[1], (-5.0, -7.0, 4.0))
        # Statistics run over the bounded (strided) set: every row survives
        # with u in {1, 3, 5, 7, 9}, so x medians to -3.0, y to -2.5.
        self.assertEqual(hint.center, (-3.0, -2.5, 4.0))
        self.assertEqual(hint.quality, "usable")

    def test_empty_support_derives_no_hint(self) -> None:
        planes = _planes((((0.0, 0.0, 5.0), 1.0),))
        self.assertIsNone(
            derive_target_geometry_hint(
                planes=planes, camera=PROBE_CAMERA, mask=_mask(4, 4, (0,))
            )
        )

    def test_derivation_replays_deterministically(self) -> None:
        gaussians = tuple(
            ((x, y, 4.0), 1.0)
            for x, y in (
                (-1.0, -1.0), (0.0, -1.0), (1.0, -1.0),
                (-1.0, 0.0), (1.0, 0.0),
                (-1.0, 1.0), (0.0, 1.0), (1.0, 1.0),
            )
        )
        mask = _mask(8, 8, (18, 20, 22, 34, 38, 50, 52, 54))
        first = derive_target_geometry_hint(
            planes=_planes(gaussians), camera=PROBE_CAMERA_8, mask=mask
        )
        second = derive_target_geometry_hint(
            planes=_planes(gaussians), camera=PROBE_CAMERA_8, mask=mask
        )
        self.assertEqual(first, second)


class TargetGeometryPolicyDigestTests(unittest.TestCase):
    def test_geometry_policy_descriptor_golden_digest(self) -> None:
        expected_descriptor = {
            "version": "target-geometry/v2",
            "minLogitOpacity": 0.0,
            "maxVisiblePoints": 64,
            "outlierMinDistance": 0.05,
            "outlierMedianFactor": 3.0,
            "extentMadScale": 1.4826,
            "extentEpsilon": 1e-3,
            "sparseSupportCount": 8,
            "separatedDropFraction": 0.25,
            "promptSupportMinCount": 4,
            "promptSupportPromotableReasons": ["separatedSupportFiltered"],
            "visiblePointIdentity": "distinct-first-hit-world-mean-v1",
        }
        self.assertEqual(
            target_geometry_policy_digest(),
            canonical_json_digest(expected_descriptor),
        )

    def test_planner_policy_descriptor_golden_digest(self) -> None:
        expected_descriptor = {
            "version": "local-key-view-planner/v3",
            "extentRadiusFloor": 0.05,
            "distanceExtentFactor": 4.0,
            "distanceNearFactor": 4.0,
            "viewOffsetsDegrees": [
                [30.0, 0.0],
                [-30.0, 0.0],
                [0.0, 20.0],
                [60.0, 0.0],
                [-60.0, 0.0],
                [30.0, 20.0],
                [-30.0, 20.0],
                [0.0, 40.0],
            ],
            "initialAutomaticViewCountRange": [4, 8],
            "initialAutomaticViewCount": 4,
            "viewsPerBatch": 4,
            "minProjectedSizeFraction": 0.05,
            "visibilityFailFraction": 0.25,
            "visibilityLimitedFraction": 0.5,
            "replacementDistanceFactors": [0.7, 0.45],
            "retainFailedSlots": True,
        }
        self.assertEqual(
            local_key_view_policy_digest(),
            canonical_json_digest(expected_descriptor),
        )


if __name__ == "__main__":
    unittest.main()

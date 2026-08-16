"""Ticket 08/16B bounded local Key-View planner policy tests (pure CPU fixtures).

The planner turns one TargetGeometryHint derivation into a bounded local fan:
left/right azimuth plus modest elevation around the hint center, conservative
per-candidate validation, bounded closer replacement, and deterministic batch
identity. It never runs a renderer, SAM, or ownership classification.
"""

from __future__ import annotations

import math
import unittest

from selection_service_companion.target_geometry import (
    AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
    PlanExhaustedError,
    PlannerFailureError,
    local_key_view_policy_descriptor,
    local_key_view_policy_digest,
    plan_local_key_views,
)


# Anchor at (0, 0, 10) looking at the world origin (OpenCV convention:
# right +x, down -y, forward -z), 1024x768 pinhole.
ANCHOR_CAMERA: dict[str, object] = {
    "revision": 0,
    "cameraToWorld": [
        1.0, 0.0, 0.0, 0.0,
        0.0, -1.0, 0.0, 0.0,
        0.0, 0.0, -1.0, 10.0,
        0.0, 0.0, 0.0, 1.0,
    ],
    "projection": {
        "model": "pinhole",
        "fx": 800.0,
        "fy": 800.0,
        "cx": 512.0,
        "cy": 384.0,
        "width": 1024,
        "height": 768,
        "near": 0.1,
        "far": 100.0,
    },
    "conventionVersion": "opencv-camera-to-world/v1",
}

CENTER = (0.0, 0.0, 0.0)
EXTENT = (0.5, 0.5, 0.5)
VISIBLE_POINTS = tuple(
    (x, y, z)
    for x in (-0.4, 0.4)
    for y in (-0.4, 0.4)
    for z in (-0.1, 0.1)
)


def _position(view: object) -> tuple[float, float, float]:
    camera_to_world = view.camera_binding["cameraToWorld"]  # type: ignore[index, attr-defined]
    return (
        float(camera_to_world[3]),
        float(camera_to_world[7]),
        float(camera_to_world[11]),
    )


def _assert_looks_at_center(
    test: unittest.TestCase, view: object, distance: float
) -> None:
    camera_binding = view.camera_binding  # type: ignore[attr-defined]
    test.assertEqual(camera_binding["conventionVersion"], "opencv-camera-to-world/v1")
    test.assertEqual(camera_binding["projection"], ANCHOR_CAMERA["projection"])
    camera_to_world = camera_binding["cameraToWorld"]
    position = _position(view)
    test.assertAlmostEqual(math.dist(position, CENTER), distance, places=7)
    forward = (camera_to_world[2], camera_to_world[6], camera_to_world[10])
    for axis in range(3):
        test.assertAlmostEqual(
            forward[axis],
            (CENTER[axis] - position[axis]) / distance,
            places=7,
        )


class LocalKeyViewPlannerTests(unittest.TestCase):
    def test_policy_identity_records_the_initial_product_range(self) -> None:
        descriptor = local_key_view_policy_descriptor()

        self.assertEqual(
            AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
            "local-key-view-planner/v2",
        )
        self.assertEqual(descriptor["version"], AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION)
        self.assertEqual(descriptor["initialAutomaticViewCountRange"], [4, 8])
        self.assertEqual(descriptor["initialAutomaticViewCount"], 4)
        self.assertRegex(local_key_view_policy_digest(), r"^sha256:[a-f0-9]{64}$")

    def test_default_batch_is_left_right_elevated(self) -> None:
        views = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=EXTENT,
            visible_points=VISIBLE_POINTS,
            batch_ordinal=0,
        )

        self.assertEqual(
            [view.view_id for view in views],
            ["key-view-0-0", "key-view-0-1", "key-view-0-2", "key-view-0-3"],
        )
        for view in views:
            self.assertEqual(view.quality, "usable")
            self.assertEqual(view.reasons, ())
            _assert_looks_at_center(self, view, 10.0)
        left, right, elevated, far_left = (_position(view) for view in views)
        # Azimuth offsets sweep symmetrically around the anchor direction.
        self.assertAlmostEqual(left[0], 10.0 * math.sin(math.radians(30.0)), places=7)
        self.assertAlmostEqual(left[2], 10.0 * math.cos(math.radians(30.0)), places=7)
        self.assertAlmostEqual(right[0], -left[0], places=7)
        self.assertAlmostEqual(right[2], left[2], places=7)
        self.assertAlmostEqual(left[1], 0.0, places=7)
        self.assertAlmostEqual(right[1], 0.0, places=7)
        # The elevated view rises along the azimuth axis (world +y here).
        self.assertAlmostEqual(elevated[0], 0.0, places=7)
        self.assertGreater(elevated[1], 3.0)
        self.assertAlmostEqual(
            elevated[1], 10.0 * math.sin(math.radians(20.0)), places=7
        )
        self.assertAlmostEqual(
            far_left[0], 10.0 * math.sin(math.radians(60.0)), places=7
        )

    def test_generate_more_batches_walk_the_bounded_offset_sequence(self) -> None:
        batch_one = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=EXTENT,
            visible_points=VISIBLE_POINTS,
            batch_ordinal=1,
        )
        self.assertEqual(
            [view.view_id for view in batch_one],
            ["key-view-1-0", "key-view-1-1", "key-view-1-2", "key-view-1-3"],
        )
        far_right = _position(batch_one[0])
        self.assertAlmostEqual(
            far_right[0], -10.0 * math.sin(math.radians(60.0)), places=7
        )
        self.assertAlmostEqual(
            far_right[2], 10.0 * math.cos(math.radians(60.0)), places=7
        )

    def test_exhausted_batch_fails_closed(self) -> None:
        with self.assertRaises(PlanExhaustedError):
            plan_local_key_views(
                anchor_camera_binding=ANCHOR_CAMERA,
                center=CENTER,
                extent=EXTENT,
                visible_points=VISIBLE_POINTS,
                batch_ordinal=2,
            )

    def test_invalid_batch_ordinal_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            plan_local_key_views(
                anchor_camera_binding=ANCHOR_CAMERA,
                center=CENTER,
                extent=EXTENT,
                visible_points=VISIBLE_POINTS,
                batch_ordinal=-1,
            )

    def test_projected_size_failure_triggers_bounded_closer_replacement(self) -> None:
        # 800 * 0.4 / 10 = 32 < 38.4 fails the primary distance; the 0.7x
        # replacement reaches 45.7 >= 38.4 and wins.
        views = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=(0.4, 0.4, 0.4),
            visible_points=VISIBLE_POINTS,
            batch_ordinal=0,
        )

        self.assertEqual(len(views), 4)
        for view in views:
            _assert_looks_at_center(self, view, 7.0)
            self.assertEqual(view.quality, "usable")

    def test_clipping_failure_triggers_bounded_closer_replacement(self) -> None:
        camera = {
            **ANCHOR_CAMERA,
            "projection": {**ANCHOR_CAMERA["projection"], "far": 8.0},  # type: ignore[index, dict-item]
        }
        views = plan_local_key_views(
            anchor_camera_binding=camera,
            center=CENTER,
            extent=EXTENT,
            visible_points=VISIBLE_POINTS,
            batch_ordinal=0,
        )

        self.assertEqual(len(views), 4)
        for view in views:
            position = _position(view)
            self.assertAlmostEqual(math.dist(position, CENTER), 7.0, places=7)

    def test_marginal_visibility_marks_the_view_limited(self) -> None:
        # Three in-frame samples plus seven clipped far away: 0.3 visibility
        # sits inside [0.25, 0.5), so every candidate is accepted Limited.
        visible = (
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (-0.1, 0.0, 0.0),
            *tuple((100.0 + index, 100.0, 100.0) for index in range(7)),
        )
        views = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=EXTENT,
            visible_points=visible,
            batch_ordinal=0,
        )

        self.assertEqual(len(views), 4)
        for view in views:
            self.assertEqual(view.quality, "limited")
            self.assertEqual(view.reasons, ("reducedVisibility",))

    def test_failed_visibility_drops_candidates_and_fails_closed(self) -> None:
        visible = (
            (0.0, 0.0, 0.0),
            *tuple((100.0 + index, 100.0, 100.0) for index in range(9)),
        )
        with self.assertRaises(PlannerFailureError):
            plan_local_key_views(
                anchor_camera_binding=ANCHOR_CAMERA,
                center=CENTER,
                extent=EXTENT,
                visible_points=visible,
                batch_ordinal=0,
            )

    def test_tiny_target_beyond_replacement_bounds_fails_closed(self) -> None:
        # 800 * 0.05 / depth is below the 38.4px useful-size floor even at the
        # closest bounded replacement distance.
        with self.assertRaises(PlannerFailureError):
            plan_local_key_views(
                anchor_camera_binding=ANCHOR_CAMERA,
                center=CENTER,
                extent=(0.05, 0.05, 0.05),
                visible_points=VISIBLE_POINTS,
                batch_ordinal=0,
            )

    def test_planning_replays_deterministically(self) -> None:
        first = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=EXTENT,
            visible_points=VISIBLE_POINTS,
            batch_ordinal=0,
        )
        second = plan_local_key_views(
            anchor_camera_binding=ANCHOR_CAMERA,
            center=CENTER,
            extent=EXTENT,
            visible_points=VISIBLE_POINTS,
            batch_ordinal=0,
        )
        self.assertEqual(
            [view.view_id for view in first], [view.view_id for view in second]
        )
        for first_view, second_view in zip(first, second, strict=True):
            self.assertEqual(
                first_view.camera_binding["cameraToWorld"],
                second_view.camera_binding["cameraToWorld"],
            )
            self.assertEqual(first_view.quality, second_view.quality)


if __name__ == "__main__":
    unittest.main()

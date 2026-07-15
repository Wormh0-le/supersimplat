from __future__ import annotations

import hashlib
import unittest

from selection_service_companion.evidence import (
    ContributorSample,
    RenderedContributorView,
)
from selection_service_companion.generated_views import (
    CameraPreflightResult,
    GeneratedViewCandidate,
    GeneratedViewCameraPlan,
    GeneratedViewPlan,
    GeneratedViewPolicy,
    PlannedGeneratedViewCandidate,
    quality_gate_tracks,
)
from selection_service_companion.masking import MaskSessionError, RegisteredFrame, RegisteredFrameSet


def digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class GeneratedViewFixtureRenderer:
    """Small same-renderer fixture with a pre-rendered generated orbit."""

    renderer_id = "gsplat"
    render_config_version = "generated-1008-v1"

    def __init__(self) -> None:
        self.seed_regions = []
        self.rendered_view_ids = []
        self._anchor_png = b"anchor-png"
        self._generated_png = b"generated-png"

    def render(self, *, scene_snapshot, frame):
        del scene_snapshot
        self.rendered_view_ids.append(frame.view_id)
        contributors = {
            "anchor": (
                ContributorSample(stable_id=1, x_px=4, y_px=4, mass=3.0),
                ContributorSample(stable_id=99, x_px=0, y_px=0, mass=2.0),
            ),
            "ring-01": (ContributorSample(stable_id=2, x_px=4, y_px=4, mass=3.0),),
            "upper-00": (ContributorSample(stable_id=3, x_px=4, y_px=4, mass=3.0),),
            "replacement-00": (ContributorSample(stable_id=4, x_px=4, y_px=4, mass=3.0),),
        }[frame.view_id]
        return RenderedContributorView(
            view_id=frame.view_id,
            rgb_frame_digest=frame.frame_digest,
            width=frame.width,
            height=frame.height,
            support_bounds=(0, 0, frame.width, frame.height),
            contributors=contributors,
        )

    def plan_views(
        self,
        *,
        scene_snapshot,
        anchor_frame,
        seed_region,
        initial_budget,
        replacement_budget,
        resolution,
    ):
        del scene_snapshot, anchor_frame, resolution
        self.seed_regions.append(seed_region)
        self.asserted_budgets = (initial_budget, replacement_budget)
        candidate = lambda view_id, category, azimuth, elevation=None, replacement_of=None: PlannedGeneratedViewCandidate(
            view_id=view_id,
            camera={"azimuthDegrees": azimuth, "elevationDegrees": elevation or 0.0},
            category=category,
            azimuth_degrees=azimuth,
            elevation_degrees=elevation,
            replacement_of=replacement_of,
        )
        return GeneratedViewCameraPlan(
            frame_set_id="frames-1",
            primary=(
                candidate("ring-01", "ring", 30.0),
                candidate("upper-00", "upper", 0.0, 30.0),
            ),
            replacements=(
                candidate("replacement-00", "replacement", 15.0, replacement_of="ring-01"),
            ),
        )

    def preflight(self, *, scene_snapshot, candidate, seed_region, resolution):
        del scene_snapshot, seed_region, resolution
        return CameraPreflightResult(True, candidate.camera, {"policyVersion": "fixture-v1"})

    def render_generated(self, *, scene_snapshot, candidate, preflight, resolution):
        del scene_snapshot, preflight
        return RegisteredFrame(
            view_id=candidate.view_id,
            frame_digest=digest(self._generated_png),
            width=resolution,
            height=resolution,
            image_png=self._generated_png,
            source="generated",
            camera=candidate.camera,
        )


class LowIncrementFixtureRenderer(GeneratedViewFixtureRenderer):
    """A plan whose fourth hidden view is already rendered before early stop."""

    def render(self, *, scene_snapshot, frame):
        if frame.view_id == "anchor":
            return super().render(scene_snapshot=scene_snapshot, frame=frame)
        self.rendered_view_ids.append(frame.view_id)
        return RenderedContributorView(
            view_id=frame.view_id,
            rgb_frame_digest=frame.frame_digest,
            width=frame.width,
            height=frame.height,
            support_bounds=(0, 0, frame.width, frame.height),
            contributors=(ContributorSample(stable_id=1, x_px=4, y_px=4, mass=3.0),),
        )

    def plan_views(
        self,
        *,
        scene_snapshot,
        anchor_frame,
        seed_region,
        initial_budget,
        replacement_budget,
        resolution,
    ):
        del scene_snapshot, anchor_frame, resolution
        self.seed_regions.append(seed_region)
        self.asserted_budgets = (initial_budget, replacement_budget)

        def candidate(index: int) -> PlannedGeneratedViewCandidate:
            return PlannedGeneratedViewCandidate(
                view_id=f"low-{index}",
                camera={"azimuthDegrees": float(index * 30)},
                category="ring",
                azimuth_degrees=float(index * 30),
            )

        return GeneratedViewCameraPlan(
            frame_set_id="frames-1",
            primary=tuple(candidate(index) for index in range(1, 5)),
            replacements=(),
        )


class GeneratedViewPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor_png = b"anchor-png"
        self.anchor = RegisteredFrame(
            view_id="anchor",
            frame_digest=digest(self.anchor_png),
            width=8,
            height=8,
            image_png=self.anchor_png,
            source="anchor",
            camera={
                "rayOrigin": [0.0, -4.0, 0.0],
                "rayDirection": [0.0, 1.0, 0.0],
                "seedDistance": 4.0,
            },
        )
        self.frame_set = RegisteredFrameSet(
            canonical="anchor",
            frame_set_id="frames-1",
            frame_set_version="anchor-v1",
            ordered_views=(self.anchor,),
        )
        self.scene_snapshot = {
            "gaussians": [
                {"stableId": 1, "mean": [0.0, 0.0, 0.0]},
                {"stableId": 2, "mean": [1.0, 0.0, 0.0]},
                {"stableId": 3, "mean": [0.0, 1.0, 0.0]},
                {"stableId": 4, "mean": [0.0, 0.0, 1.0]},
                {"stableId": 99, "mean": [100.0, 0.0, 0.0]},
            ]
        }
        self.mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": "anchor",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 8,
                                "height": 8,
                                "foregroundPixels": [[4, 4]],
                            },
                        }
                    ],
                }
            ]
        }

    def test_plans_bounded_generated_views_from_anchor_contributor_seed(self) -> None:
        renderer = GeneratedViewFixtureRenderer()

        prepared = GeneratedViewPolicy().prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        self.assertEqual(renderer.asserted_budgets, (16, 8))
        self.assertEqual(prepared.seed_region.source, "anchor_contributors")
        self.assertEqual(prepared.seed_region.stable_ids, (1,))
        self.assertEqual(prepared.seed_region.center, (0.0, 0.0, 0.0))
        self.assertEqual(
            [frame.view_id for frame in prepared.initial_frame_set.ordered_views],
            ["anchor", "ring-01", "upper-00"],
        )
        self.assertEqual(
            [candidate.frame.view_id for candidate in prepared.replacements],
            ["replacement-00"],
        )
        self.assertEqual(prepared.initial_frame_set.ordered_views[0], self.anchor)
        self.assertNotIn("imagePngBase64", prepared.public_frame_set()["orderedViews"][1])

    def test_seed_region_discards_a_spatial_anchor_contributor_outlier(self) -> None:
        renderer = GeneratedViewFixtureRenderer()
        outlier_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": "anchor",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 8,
                                "height": 8,
                                "foregroundPixels": [[0, 0], [4, 4]],
                            },
                        }
                    ],
                }
            ]
        }

        prepared = GeneratedViewPolicy().prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=outlier_mask_set,
            renderer=renderer,
            resolution=8,
        )

        self.assertEqual(prepared.seed_region.stable_ids, (1,))
        self.assertEqual(prepared.seed_region.center, (0.0, 0.0, 0.0))

    def test_replaces_a_quality_rejected_candidate_and_reports_limited_coverage(self) -> None:
        renderer = GeneratedViewFixtureRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )
        preliminary_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        self.mask_set["tracks"][0]["frames"][0],
                        {
                            "viewId": "ring-01",
                            "status": "rejected",
                            "rejectionReason": "Mask quality gate rejected this view.",
                        },
                        {
                            "viewId": "upper-00",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 8,
                                "height": 8,
                                "foregroundPixels": [[4, 4]],
                            },
                        },
                    ],
                }
            ]
        }

        selected = policy.select_frame_set(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            preliminary_mask_set=preliminary_mask_set,
            renderer=renderer,
        )
        final_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        self.mask_set["tracks"][0]["frames"][0],
                        {
                            "viewId": "upper-00",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 8,
                                "height": 8,
                                "foregroundPixels": [[4, 4]],
                            },
                        },
                        {
                            "viewId": "replacement-00",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 8,
                                "height": 8,
                                "foregroundPixels": [[4, 4]],
                            },
                        },
                    ],
                }
            ]
        }
        report = policy.coverage_report(
            scene_snapshot=self.scene_snapshot,
            frame_set=selected.frame_set,
            mask_set=final_mask_set,
            renderer=renderer,
            render_config_version=prepared.plan.render_config_version,
            preliminary_rejections=selected.rejected_views,
            attempted_view_ids=selected.attempted_view_ids,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "replacement-00", "upper-00"],
        )
        self.assertEqual(selected.rejected_views[0]["viewId"], "ring-01")
        self.assertEqual(selected.rejected_views[0]["replacementOf"], "ring-01")
        self.assertEqual(report["status"], "insufficient_coverage")
        self.assertEqual(report["coveredContributorIds"], [1, 3, 4, 99])
        self.assertEqual(report["unseenCandidateIds"], [2])
        self.assertEqual(
            policy.public_coverage_report(report),
            {
                "frameSetVersion": selected.frame_set.frame_set_version,
                "renderConfigVersion": "generated-1008-v1",
                "attemptedViews": 4,
                "acceptedViews": 3,
                "rejectedViewCount": 1,
                "status": "insufficient_coverage",
            },
        )

    def test_early_stop_reports_every_preliminary_view_attempt(self) -> None:
        renderer = LowIncrementFixtureRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def accepted(view_id: str) -> dict[str, object]:
            return {
                "viewId": view_id,
                "status": "accepted",
                "binaryMask": {
                    "encoding": "sparse-points-v1",
                    "width": 8,
                    "height": 8,
                    "foregroundPixels": [[4, 4]],
                },
            }

        preliminary_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        accepted(frame.view_id)
                        for frame in prepared.initial_frame_set.ordered_views
                    ],
                }
            ]
        }
        selected = policy.select_frame_set(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            preliminary_mask_set=preliminary_mask_set,
            renderer=renderer,
        )
        final_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        accepted(frame.view_id)
                        for frame in selected.frame_set.ordered_views
                    ],
                }
            ]
        }

        report = policy.coverage_report(
            scene_snapshot=self.scene_snapshot,
            frame_set=selected.frame_set,
            mask_set=final_mask_set,
            renderer=renderer,
            render_config_version=prepared.plan.render_config_version,
            attempted_view_ids=selected.attempted_view_ids,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "low-1", "low-2", "low-3"],
        )
        self.assertEqual(
            selected.attempted_view_ids,
            ("anchor", "low-1", "low-2", "low-3", "low-4"),
        )
        self.assertEqual(report["attemptedViews"], 5)

    def test_rejects_an_anchor_mask_that_contradicts_a_point_prompt(self) -> None:
        renderer = GeneratedViewFixtureRenderer()
        tracks = self.mask_set["tracks"]

        with self.assertRaisesRegex(MaskSessionError, "point prompt"):
            quality_gate_tracks(
                scene_snapshot=self.scene_snapshot,
                frame_set=self.frame_set,
                tracks=tracks,
                renderer=renderer,
                prompt_log=(
                    {
                        "operation": "New",
                        "prompt": {
                            "viewId": "anchor",
                            "xPx": 3,
                            "yPx": 3,
                            "polarity": "include",
                        },
                    },
                ),
            )


if __name__ == "__main__":
    unittest.main()

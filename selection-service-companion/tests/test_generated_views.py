from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
import unittest

from selection_service_companion.evidence import (
    ContributorSample,
    RenderedContributorView,
)
from selection_service_companion.generated_views import (
    CameraPreflightResult,
    GeneratedViewCameraPlan,
    GeneratedViewPolicy,
    NEIGHBOR_ANOMALY_POLICY_ID,
    NEIGHBOR_ANOMALY_THRESHOLDS,
    PlannedGeneratedViewCandidate,
    SeedRegion,
    quality_gate_tracks,
)
from selection_service_companion.masking import MaskSessionError, RegisteredFrame, RegisteredFrameSet


def digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class GeneratedViewFixtureRenderer:
    """Small same-renderer fixture with a bounded generated camera plan."""

    renderer_id = "gsplat"
    render_config_version = "generated-1008-v1"

    def __init__(self) -> None:
        self.seed_regions = []
        self.rendered_view_ids = []
        self._anchor_png = b"anchor-png"
        self._generated_png = b"generated-png"

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
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
        scene_snapshot: Mapping[str, Any],
        anchor_frame: RegisteredFrame,
        seed_region: SeedRegion,
        initial_budget: int,
        replacement_budget: int,
        resolution: int,
    ) -> GeneratedViewCameraPlan:
        del scene_snapshot, anchor_frame, resolution
        self.seed_regions.append(seed_region)
        self.asserted_budgets = (initial_budget, replacement_budget)

        def candidate(
            view_id: str,
            category: str,
            azimuth: float,
            elevation: float | None = None,
            replacement_of: str | None = None,
        ) -> PlannedGeneratedViewCandidate:
            return PlannedGeneratedViewCandidate(
                view_id=view_id,
                camera={
                    "azimuthDegrees": azimuth,
                    "elevationDegrees": elevation or 0.0,
                },
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

    def preflight(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        seed_region: SeedRegion,
        resolution: int,
    ) -> CameraPreflightResult:
        del scene_snapshot, seed_region
        return CameraPreflightResult(
            True,
            candidate.camera,
            {
                "policyVersion": "fixture-v1",
                "attempts": [{
                    "projectedCenterX": resolution / 2,
                    "projectedCenterY": resolution / 2,
                    "projectedRadius": resolution / 4,
                }],
            },
        )

    def render_generated(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        preflight: CameraPreflightResult,
        resolution: int,
    ) -> RegisteredFrame:
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
    """A plan that reaches the low-increment stop after three hidden views."""

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
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
        scene_snapshot: Mapping[str, Any],
        anchor_frame: RegisteredFrame,
        seed_region: SeedRegion,
        initial_budget: int,
        replacement_budget: int,
        resolution: int,
    ) -> GeneratedViewCameraPlan:
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


class MaximumAttemptBudgetFixtureRenderer(GeneratedViewFixtureRenderer):
    """Produces the exact 16 planned plus 8 replacement camera limit."""

    def plan_views(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        anchor_frame: RegisteredFrame,
        seed_region: SeedRegion,
        initial_budget: int,
        replacement_budget: int,
        resolution: int,
    ) -> GeneratedViewCameraPlan:
        del scene_snapshot, anchor_frame, resolution
        self.seed_regions.append(seed_region)
        self.asserted_budgets = (initial_budget, replacement_budget)
        primary = tuple(
            PlannedGeneratedViewCandidate(
                view_id=f"planned-{index}",
                camera={"azimuthDegrees": float(index)},
                category="ring",
                azimuth_degrees=float(index),
            )
            for index in range(initial_budget)
        )
        return GeneratedViewCameraPlan(
            frame_set_id="frames-1",
            primary=primary,
            replacements=tuple(
                PlannedGeneratedViewCandidate(
                    view_id=f"replacement-{index}",
                    camera={"azimuthDegrees": float(index) + 0.5},
                    category="replacement",
                    azimuth_degrees=float(index) + 0.5,
                    replacement_of=primary[index].view_id,
                )
                for index in range(replacement_budget)
            ),
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
            [candidate.view_id for candidate in prepared.primary],
            ["ring-01", "upper-00"],
        )
        self.assertEqual(
            [candidate.view_id for candidate in prepared.replacements],
            ["replacement-00"],
        )
        self.assertEqual(prepared.anchor_frame_set, self.frame_set)
        self.assertEqual(renderer.rendered_view_ids, ["anchor"])

    def test_accepts_the_exact_16_plus_8_camera_attempt_budget(self) -> None:
        renderer = MaximumAttemptBudgetFixtureRenderer()

        prepared = GeneratedViewPolicy().prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        self.assertEqual(renderer.asserted_budgets, (16, 8))
        self.assertEqual(len(prepared.primary), 16)
        self.assertEqual(len(prepared.replacements), 8)

    def test_neighbor_anomaly_policy_matches_controlled_calibration_fixture(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[2]
            / "docs/benchmarks/fixtures/generated-view-neighbor-anomaly-v1.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(fixture["policyId"], NEIGHBOR_ANOMALY_POLICY_ID)
        self.assertEqual(fixture["thresholds"], NEIGHBOR_ANOMALY_THRESHOLDS)
        self.assertEqual(
            fixture["controlledCases"][1]["expectedRejectionReason"],
            "projected_seed_overlap_neighbor",
        )

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
        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            frames = []
            for frame in frame_set.ordered_views:
                if frame.view_id == "ring-01":
                    foreground = [
                        [x_px, y_px]
                        for y_px in range(frame.height)
                        for x_px in range(frame.width)
                        if (x_px, y_px) not in {(0, 0), (1, 0), (2, 0), (3, 0)}
                    ]
                    frames.append(
                        {
                            "viewId": frame.view_id,
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": frame.width,
                                "height": frame.height,
                                "foregroundPixels": foreground,
                            },
                        }
                    )
                    continue
                frames.append(
                    {
                        "viewId": frame.view_id,
                        "status": "accepted",
                        "binaryMask": {
                            "encoding": "sparse-points-v1",
                            "width": frame.width,
                            "height": frame.height,
                            "foregroundPixels": [[4, 4]],
                        },
                    }
                )
            return (
                [{"trackId": "primary", "role": "include", "frames": frames}],
                {
                    "trackingConfidenceByView": {
                        frame.view_id: 0.9 for frame in frame_set.ordered_views
                    },
                },
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
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
            render_config_version=prepared.render_config_version,
            preliminary_rejections=selected.rejected_views,
            attempted_view_ids=selected.attempted_view_ids,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "replacement-00", "upper-00"],
        )
        self.assertEqual(selected.rejected_views[0]["viewId"], "ring-01")
        self.assertEqual(selected.rejected_views[0]["stage"], "neighbor_anomaly")
        self.assertEqual(selected.rejected_views[0]["reason"], "mask_area")
        self.assertEqual(selected.rejected_views[0]["replacementOf"], "ring-01")
        self.assertEqual(
            selected.quality_diagnostics["rejections"][0]["diagnostic"]["metrics"][
                "acceptedNeighborViewId"
            ],
            "anchor",
        )
        self.assertEqual(report["status"], "insufficient_coverage")
        self.assertEqual(report["coveredContributorIds"], [1, 3, 4, 99])
        self.assertEqual(report["unseenCandidateIds"], [2])
        self.assertEqual(
            policy.public_coverage_report(report),
            {
                "frameSetVersion": selected.frame_set.frame_set_version,
                "renderConfigVersion": "generated-1008-v1+generated-8x8-v1",
                "attemptedViews": 4,
                "acceptedViews": 3,
                "rejectedViewCount": 1,
                "status": "insufficient_coverage",
            },
        )

    def test_early_stop_avoids_later_candidate_rendering(self) -> None:
        renderer = LowIncrementFixtureRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def accepted(frame: RegisteredFrame) -> dict[str, object]:
            return {
                "viewId": frame.view_id,
                "status": "accepted",
                "binaryMask": {
                    "encoding": "sparse-points-v1",
                    "width": frame.width,
                    "height": frame.height,
                    "foregroundPixels": [[4, 4]],
                },
            }

        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            return (
                [
                    {
                        "trackId": "primary",
                        "role": "include",
                        "frames": [
                            accepted(frame) for frame in frame_set.ordered_views
                        ],
                    }
                ],
                {
                    "trackingConfidenceByView": {
                        frame.view_id: 0.9 for frame in frame_set.ordered_views
                    },
                },
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
        )
        final_mask_set = {
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        accepted(frame)
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
            render_config_version=prepared.render_config_version,
            attempted_view_ids=selected.attempted_view_ids,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "low-1", "low-2", "low-3"],
        )
        self.assertEqual(
            selected.attempted_view_ids,
            ("anchor", "low-1", "low-2", "low-3"),
        )
        self.assertEqual(report["attemptedViews"], 4)

    def test_rejects_a_candidate_without_projected_seed_metrics(self) -> None:
        class MissingMetricRenderer(GeneratedViewFixtureRenderer):
            def preflight(
                self,
                *,
                scene_snapshot: Mapping[str, Any],
                candidate: PlannedGeneratedViewCandidate,
                seed_region: SeedRegion,
                resolution: int,
            ) -> CameraPreflightResult:
                del scene_snapshot, seed_region, resolution
                return CameraPreflightResult(
                    True, candidate.camera, {"policyVersion": "fixture-v1"}
                )

        renderer = MissingMetricRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            return (
                [{
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": frame.view_id,
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": frame.width,
                                "height": frame.height,
                                "foregroundPixels": [[4, 4]],
                            },
                        }
                        for frame in frame_set.ordered_views
                    ],
                }],
                {
                    "trackingConfidenceByView": {
                        frame.view_id: 0.9 for frame in frame_set.ordered_views
                    },
                },
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views], ["anchor"]
        )
        self.assertEqual(
            selected.rejected_views[0]["reason"], "projected_seed_overlap_unavailable"
        )

    def test_rejects_a_candidate_without_tracking_confidence(self) -> None:
        renderer = GeneratedViewFixtureRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            return (
                [{
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": frame.view_id,
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": frame.width,
                                "height": frame.height,
                                "foregroundPixels": [[4, 4]],
                            },
                        }
                        for frame in frame_set.ordered_views
                    ],
                }],
                None,
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views], ["anchor"]
        )
        self.assertEqual(
            selected.rejected_views[0]["reason"], "tracking_confidence_unavailable"
        )

    def test_rejects_a_candidate_with_anomalously_low_tracking_confidence(self) -> None:
        renderer = GeneratedViewFixtureRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            return (
                [{
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": frame.view_id,
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": frame.width,
                                "height": frame.height,
                                "foregroundPixels": [[4, 4]],
                            },
                        }
                        for frame in frame_set.ordered_views
                    ],
                }],
                {
                    "trackingConfidenceByView": {
                        frame.view_id: 0.1
                        if frame.view_id == "ring-01"
                        else 0.9
                        for frame in frame_set.ordered_views
                    },
                },
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
        )

        self.assertEqual(selected.rejected_views[0]["viewId"], "ring-01")
        self.assertEqual(selected.rejected_views[0]["reason"], "tracking_confidence")
        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "replacement-00", "upper-00"],
        )

    def test_rejects_a_projected_seed_overlap_anomalous_to_the_accepted_neighbor(
        self,
    ) -> None:
        class RelativeOverlapRenderer(GeneratedViewFixtureRenderer):
            def preflight(
                self,
                *,
                scene_snapshot: Mapping[str, Any],
                candidate: PlannedGeneratedViewCandidate,
                seed_region: SeedRegion,
                resolution: int,
            ) -> CameraPreflightResult:
                del scene_snapshot, seed_region, resolution
                if candidate.view_id == "upper-00":
                    center, radius = 2.5, 0.5
                else:
                    center, radius = 4.0, 2.0
                return CameraPreflightResult(
                    accepted=True,
                    camera=candidate.camera,
                    diagnostics={
                        "policyVersion": "fixture-v1",
                        "attempts": [
                            {
                                "projectedCenterX": center,
                                "projectedCenterY": center,
                                "projectedRadius": radius,
                            }
                        ],
                    },
                )

        renderer = RelativeOverlapRenderer()
        policy = GeneratedViewPolicy()
        prepared = policy.prepare(
            scene_snapshot=self.scene_snapshot,
            anchor_frame_set=self.frame_set,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
        )

        def track_prefix(
            frame_set: RegisteredFrameSet,
        ) -> tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]:
            frames: list[dict[str, object]] = []
            for frame in frame_set.ordered_views:
                foreground = (
                    [[x_px, y_px] for y_px in range(2, 6) for x_px in range(2, 6)]
                    if frame.source == "generated"
                    else [[4, 4]]
                )
                frames.append(
                    {
                        "viewId": frame.view_id,
                        "status": "accepted",
                        "binaryMask": {
                            "encoding": "sparse-points-v1",
                            "width": frame.width,
                            "height": frame.height,
                            "foregroundPixels": foreground,
                        },
                    }
                )
            return (
                [{"trackId": "primary", "role": "include", "frames": frames}],
                {
                    "trackingConfidenceByView": {
                        frame.view_id: 0.9 for frame in frame_set.ordered_views
                    },
                },
            )

        selected = policy.select_incrementally(
            prepared=prepared,
            scene_snapshot=self.scene_snapshot,
            anchor_mask_set=self.mask_set,
            renderer=renderer,
            resolution=8,
            track_prefix=track_prefix,
        )

        self.assertEqual(
            [frame.view_id for frame in selected.frame_set.ordered_views],
            ["anchor", "ring-01"],
        )
        self.assertEqual(
            selected.rejected_views[0]["reason"], "projected_seed_overlap_neighbor"
        )
        metrics = selected.quality_diagnostics["rejections"][0]["diagnostic"][
            "metrics"
        ]
        self.assertEqual(metrics["acceptedNeighborViewId"], "ring-01")
        self.assertEqual(metrics["acceptedNeighborProjectedSeedRegionOverlap"], 1.0)
        self.assertEqual(metrics["projectedSeedRegionOverlap"], 0.0625)
        self.assertEqual(metrics["projectedSeedRegionOverlapRatio"], 0.0625)

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

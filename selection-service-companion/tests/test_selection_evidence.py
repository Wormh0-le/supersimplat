from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from selection_service_companion.evidence import (
    ContributorSample,
    RenderedContributorView,
    StaticContributorRenderer,
    build_evidence_snapshot,
    selection_result_ids,
)
from selection_service_companion.masking import MaskSessionError, register_frame_set


class SelectionEvidenceTests(unittest.TestCase):
    def test_moderate_anchor_parity_disables_only_negative_evidence(self) -> None:
        frame_set = register_frame_set(
            {
                "frameSetId": "frames-1",
                "frameSetVersion": "anchor-v1",
                "orderedViews": [
                    {
                        "viewId": "anchor-view",
                        "frameDigest": "sha256:anchor-rgb-v1",
                        "width": 4,
                        "height": 3,
                    }
                ],
            }
        )
        bindings = {
            "requestId": "request-1",
            "sessionId": "session-1",
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": "sha256:model-v1",
        }
        mask_set = {
            "status": "complete",
            "requestId": "request-1",
            "sessionId": "session-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "modelManifestDigest": "sha256:model-v1",
            "threshold": 0.0,
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": "anchor-view",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 4,
                                "height": 3,
                                "foregroundPixels": [[1, 1]],
                            },
                        }
                    ],
                }
            ],
        }
        renderer = StaticContributorRenderer(
            {
                "anchor-view": RenderedContributorView(
                    view_id="anchor-view",
                    rgb_frame_digest="sha256:anchor-rgb-v1",
                    width=4,
                    height=3,
                    support_bounds=(0, 0, 2, 2),
                    contributors=(
                        ContributorSample(stable_id=10, x_px=1, y_px=1, mass=3.0),
                        ContributorSample(stable_id=20, x_px=0, y_px=0, mass=3.0),
                    ),
                    anchor_parity="moderate",
                )
            }
        )

        evidence = build_evidence_snapshot(
            bindings=bindings,
            scene_snapshot={"gaussians": [{"stableId": 10}, {"stableId": 20}]},
            frame_set=frame_set,
            mask_set=mask_set,
            renderer=renderer,
        )

        self.assertEqual(evidence["records"][0]["classification"], "selected")
        self.assertEqual(evidence["records"][1], {
            "stableId": 20,
            "positiveEvidence": 0.0,
            "negativeEvidence": 0.0,
            "effectiveObservation": 0.0,
            "posterior": 0.5,
            "uncertaintyReason": "unobserved",
            "classification": "uncertain",
        })
        self.assertFalse(evidence["views"][0]["negativeEvidenceAllowed"])

    def test_severe_anchor_parity_fails_before_evidence_is_lifted(self) -> None:
        frame_set = register_frame_set(
            {
                "frameSetId": "frames-1",
                "frameSetVersion": "anchor-v1",
                "orderedViews": [
                    {
                        "viewId": "anchor-view",
                        "frameDigest": "sha256:anchor-rgb-v1",
                        "width": 2,
                        "height": 2,
                    }
                ],
            }
        )
        renderer = StaticContributorRenderer(
            {
                "anchor-view": RenderedContributorView(
                    view_id="anchor-view",
                    rgb_frame_digest="sha256:anchor-rgb-v1",
                    width=2,
                    height=2,
                    support_bounds=(0, 0, 2, 2),
                    contributors=(
                        ContributorSample(stable_id=10, x_px=0, y_px=0, mass=1.0),
                    ),
                    anchor_parity="severe",
                )
            }
        )

        with self.assertRaisesRegex(MaskSessionError, "parity"):
            build_evidence_snapshot(
                bindings={
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "targetSplatId": "splat-1",
                    "sceneId": "scene-1",
                    "sceneVersion": "snapshot-v1",
                    "operation": "New",
                    "correctionRound": 0,
                    "deterministicSeed": "seed-1",
                    "promptLogRevision": 1,
                    "frameSetVersion": "anchor-v1",
                    "renderConfigVersion": "effective-rgb-v1",
                    "modelManifestDigest": "sha256:model-v1",
                },
                scene_snapshot={"gaussians": [{"stableId": 10}]},
                frame_set=frame_set,
                mask_set={
                    "status": "complete",
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "promptLogRevision": 1,
                    "frameSetVersion": "anchor-v1",
                    "modelManifestDigest": "sha256:model-v1",
                    "threshold": 0.0,
                    "tracks": [
                        {
                            "trackId": "primary",
                            "role": "include",
                            "frames": [
                                {
                                    "viewId": "anchor-view",
                                    "status": "accepted",
                                    "binaryMask": {
                                        "encoding": "sparse-points-v1",
                                        "width": 2,
                                        "height": 2,
                                        "foregroundPixels": [[0, 0]],
                                    },
                                }
                            ],
                        }
                    ],
                },
                renderer=renderer,
            )

    def test_uses_only_bounded_anchor_contributor_support_for_three_state_evidence(self) -> None:
        frame_set = register_frame_set(
            {
                "frameSetId": "frames-1",
                "frameSetVersion": "anchor-v1",
                "orderedViews": [
                    {
                        "viewId": "anchor-view",
                        "frameDigest": "sha256:anchor-rgb-v1",
                        "width": 4,
                        "height": 3,
                    },
                    {
                        "viewId": "not-found-view",
                        "frameDigest": "sha256:not-found-rgb-v1",
                        "width": 4,
                        "height": 3,
                    },
                ],
            }
        )
        renderer = StaticContributorRenderer(
            {
                "anchor-view": RenderedContributorView(
                    view_id="anchor-view",
                    rgb_frame_digest="sha256:anchor-rgb-v1",
                    width=4,
                    height=3,
                    support_bounds=(0, 0, 2, 2),
                    contributors=(
                        ContributorSample(stable_id=10, x_px=1, y_px=1, mass=3.0),
                        ContributorSample(stable_id=20, x_px=0, y_px=0, mass=3.0),
                        ContributorSample(stable_id=40, x_px=1, y_px=1, mass=0.05),
                        ContributorSample(stable_id=50, x_px=1, y_px=1, mass=1.0),
                        ContributorSample(stable_id=50, x_px=0, y_px=0, mass=1.0),
                    ),
                ),
                "not-found-view": RenderedContributorView(
                    view_id="not-found-view",
                    rgb_frame_digest="sha256:not-found-rgb-v1",
                    width=4,
                    height=3,
                    support_bounds=(0, 0, 1, 1),
                    contributors=(
                        ContributorSample(stable_id=30, x_px=0, y_px=0, mass=99.0),
                    ),
                ),
            }
        )
        bindings = {
            "requestId": "request-1",
            "sessionId": "session-1",
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": "sha256:model-v1",
        }
        mask_set = {
            "status": "complete",
            "requestId": "request-1",
            "sessionId": "session-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "modelManifestDigest": "sha256:model-v1",
            "threshold": 0.0,
            "tracks": [
                {
                    "trackId": "primary",
                    "role": "include",
                    "frames": [
                        {
                            "viewId": "anchor-view",
                            "status": "accepted",
                            "binaryMask": {
                                "encoding": "sparse-points-v1",
                                "width": 4,
                                "height": 3,
                                "foregroundPixels": [[1, 1]],
                            },
                        },
                        {
                            "viewId": "not-found-view",
                            "status": "not_found",
                            "rejectionReason": "No reliable Anchor continuation was found.",
                        },
                    ],
                }
            ],
        }

        evidence = build_evidence_snapshot(
            bindings=bindings,
            scene_snapshot={
                "gaussians": [{"stableId": stable_id} for stable_id in (10, 20, 30, 40, 50)]
            },
            frame_set=frame_set,
            mask_set=mask_set,
            renderer=renderer,
        )

        self.assertEqual(evidence["policy"], {
            "id": "selection-evidence-policy/v1",
            "renderConfigVersion": "effective-rgb-v1",
            "contributorSemantics": "alpha-times-transmittance/v1",
            "evidenceScale": "contributor-mass/v1",
            "betaPrior": {"alpha": 1, "beta": 1},
            "minimumEffectiveObservation": 0.1,
            "selectedPosteriorThreshold": 0.8,
            "rejectedPosteriorThreshold": 0.2,
        })
        self.assertEqual(evidence["frameSetId"], "frames-1")
        self.assertEqual(
            evidence["records"],
            [
                {
                    "stableId": 10,
                    "positiveEvidence": 3.0,
                    "negativeEvidence": 0.0,
                    "effectiveObservation": 3.0,
                    "posterior": 0.8,
                    "uncertaintyReason": None,
                    "classification": "selected",
                },
                {
                    "stableId": 20,
                    "positiveEvidence": 0.0,
                    "negativeEvidence": 3.0,
                    "effectiveObservation": 3.0,
                    "posterior": 0.2,
                    "uncertaintyReason": None,
                    "classification": "rejected",
                },
                {
                    "stableId": 30,
                    "positiveEvidence": 0.0,
                    "negativeEvidence": 0.0,
                    "effectiveObservation": 0.0,
                    "posterior": 0.5,
                    "uncertaintyReason": "unobserved",
                    "classification": "uncertain",
                },
                {
                    "stableId": 40,
                    "positiveEvidence": 0.05,
                    "negativeEvidence": 0.0,
                    "effectiveObservation": 0.05,
                    "posterior": 1.05 / 2.05,
                    "uncertaintyReason": "insufficient_observation",
                    "classification": "uncertain",
                },
                {
                    "stableId": 50,
                    "positiveEvidence": 1.0,
                    "negativeEvidence": 1.0,
                    "effectiveObservation": 2.0,
                    "posterior": 0.5,
                    "uncertaintyReason": "undecided_or_conflicting",
                    "classification": "uncertain",
                },
            ],
        )
        self.assertEqual(renderer.rendered_view_ids, ["anchor-view"])

    def test_binds_controlled_front_back_overlap_fixture_to_supported_evidence(self) -> None:
        fixture_root = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "benchmarks"
            / "fixtures"
            / "controlled-overlap"
        )
        controlled = json.loads(
            (fixture_root / "controlled_front_back_overlap.json").read_text(
                encoding="utf-8"
            )
        )
        fixture_frame_set = json.loads(
            (fixture_root / "frame-set-v1" / "frame-set.json").read_text(
                encoding="utf-8"
            )
        )
        fixture_mask_set = json.loads(
            (
                fixture_root / "frame-set-v1" / "mask-set-v1" / "mask-set.json"
            ).read_text(encoding="utf-8")
        )
        anchor = next(
            frame
            for frame in fixture_frame_set["frames"]
            if frame["category"] == "anchor"
        )
        width, height = fixture_frame_set["resolution"]
        anchor_bytes = (
            fixture_root / "frame-set-v1" / anchor["file"]
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(anchor_bytes).hexdigest(), anchor["sha256"]
        )
        self.assertEqual(fixture_mask_set["frames"][0]["status"], "accepted")
        self.assertEqual(
            hashlib.sha256(
                (fixture_root / "frame-set-v1" / "mask-set-v1" / "masks.npz").read_bytes()
            ).hexdigest(),
            fixture_mask_set["masks"]["sha256"],
        )
        self.assertEqual(
            fixture_mask_set["mask_derivation"]["kind"],
            "same-renderer-top-contributor-instance-mask",
        )

        target_start, target_end = controlled["groundTruth"]["selected"]
        distractor_start, distractor_end = controlled["groundTruth"]["rejected"]
        frame_set = register_frame_set(
            {
                "frameSetId": "controlled-overlap:anchor",
                "frameSetVersion": fixture_frame_set["frame_set_version"],
                "orderedViews": [
                    {
                        "viewId": anchor["candidate_id"],
                        "frameDigest": f"sha256:{anchor['sha256']}",
                        "width": width,
                        "height": height,
                    }
                ],
            }
        )
        bindings = {
            "requestId": "controlled-request-1",
            "sessionId": "controlled-session-1",
            "targetSplatId": "controlled-overlap",
            "sceneId": "controlled-overlap",
            "sceneVersion": "fixture-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "controlled-seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": fixture_frame_set["frame_set_version"],
            "renderConfigVersion": "gsplat-controlled-overlap-v1",
            "modelManifestDigest": "sha256:fixture-model-v1",
        }
        evidence = build_evidence_snapshot(
            bindings=bindings,
            scene_snapshot={
                "gaussians": [
                    {"stableId": target_start},
                    {"stableId": target_end},
                    {"stableId": distractor_start},
                    {"stableId": distractor_end},
                ]
            },
            frame_set=frame_set,
            mask_set={
                "status": "complete",
                "requestId": bindings["requestId"],
                "sessionId": bindings["sessionId"],
                "promptLogRevision": bindings["promptLogRevision"],
                "frameSetVersion": bindings["frameSetVersion"],
                "modelManifestDigest": bindings["modelManifestDigest"],
                "threshold": 0.0,
                "tracks": [
                    {
                        "trackId": "primary",
                        "role": "include",
                        "frames": [
                            {
                                "viewId": anchor["candidate_id"],
                                "status": "accepted",
                                "binaryMask": {
                                    "encoding": "sparse-points-v1",
                                    "width": width,
                                    "height": height,
                                    "foregroundPixels": [[1, 1]],
                                },
                            }
                        ],
                    }
                ],
            },
            renderer=StaticContributorRenderer(
                {
                    anchor["candidate_id"]: RenderedContributorView(
                        view_id=anchor["candidate_id"],
                        rgb_frame_digest=f"sha256:{anchor['sha256']}",
                        width=width,
                        height=height,
                        support_bounds=(0, 0, 2, 2),
                        contributors=(
                            ContributorSample(
                                stable_id=target_start,
                                x_px=1,
                                y_px=1,
                                mass=3.0,
                            ),
                            ContributorSample(
                                stable_id=distractor_start,
                                x_px=0,
                                y_px=0,
                                mass=3.0,
                            ),
                        ),
                    )
                }
            ),
        )

        self.assertEqual(
            selection_result_ids(evidence),
            ([target_start], [target_end, distractor_end], [distractor_start]),
        )


if __name__ == "__main__":
    unittest.main()

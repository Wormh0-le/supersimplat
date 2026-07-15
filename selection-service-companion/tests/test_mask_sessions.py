from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
from types import ModuleType
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from selection_service_companion.server import create_server
from selection_service_companion.evidence import ContributorSample, RenderedContributorView
from selection_service_companion.masking import (
    MaskProduction,
    MaskSessionError,
    PointMaskAdapter,
    RegisteredFrame,
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
    _build_sam3_predictor,
    register_frame_set,
)
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = "https://editor.example"


class PointFixtureContributorRenderer:
    """Deterministic same-RGB contributor fixture for mask-session contracts."""

    renderer_id = "gsplat"

    def render(self, *, scene_snapshot, frame):
        stable_ids = sorted(gaussian["stableId"] for gaussian in scene_snapshot["gaussians"])
        contributors = []
        if stable_ids:
            contributors.append(
                ContributorSample(
                    stable_id=stable_ids[0],
                    x_px=min(10, frame.width - 1),
                    y_px=min(20, frame.height - 1),
                    mass=3.0,
                )
            )
        if len(stable_ids) >= 3:
            contributors.append(
                ContributorSample(stable_id=stable_ids[2], x_px=0, y_px=0, mass=3.0)
            )
        return RenderedContributorView(
            view_id=frame.view_id,
            rgb_frame_digest=frame.frame_digest,
            width=frame.width,
            height=frame.height,
            support_bounds=(0, 0, frame.width, frame.height),
            contributors=tuple(contributors),
        )

class MaskSessionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / "state")
        # The sparse-point adapter is a deterministic reference fixture.  It
        # is injected only in these contract tests, never enabled by default.
        self.state.mask_adapters["point-mask-v1"] = PointMaskAdapter()
        self.state.contributor_renderer = PointFixtureContributorRenderer()
        self.lock_file = self.directory / "uv.lock"
        self.lock_file.write_text("locked companion dependencies\n", encoding="utf-8")
        self.state.install_release("0.1.0", self.lock_file)

        weights = self.directory / "point-mask.bin"
        weights.write_bytes(b"separately acquired point-mask adapter weights")
        self.weights = weights
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / "point-mask.json"
        manifest.write_text(
            json.dumps(
                {
                    "digest": "sha256:point-mask-v1",
                    "adapterId": "point-mask-v1",
                    "modelName": "Point Mask v1",
                    "checkpointDigest": f"sha256:{checkpoint_digest}",
                    "sourceCommit": "point-mask-source-v1",
                    "licenseName": "MIT",
                    "licenseUrl": "https://example.test/point-mask-license",
                    "runtimeConfigDigest": "sha256:point-mask-runtime-v1",
                }
            ),
            encoding="utf-8",
        )
        self.model_manifest_digest = self.state.install_model(manifest, weights)["digest"]

        self.server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=[EDITOR_ORIGIN],
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    def request_json(self, path: str, method: str, body: dict[str, object]) -> dict[str, object]:
        with urlopen(
            Request(
                f"{self.endpoint}{path}",
                data=json.dumps(body).encode(),
                method=method,
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )
        ) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    @staticmethod
    def snapshot() -> dict[str, object]:
        return {
            "protocolVersion": "1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "gaussianCount": 3,
            "coordinateConvention": "right-handed/world",
            "attributeSchema": "gaussian-v1",
            "stableIdSchema": "uint32",
            "appearancePolicy": "dc-sh-v1",
            "renderConfiguration": {
                "version": "effective-rgb-v1",
                "backgroundRgba": [0, 0, 0, 1],
                "alphaMode": "opaque-background",
                "shBands": 3,
                "rasterizer": "playcanvas-gsplat-classic",
            },
            "gaussians": [
                {
                    "stableId": stable_id,
                    "mean": [stable_id, 0, 0],
                    "rotation": [0, 0, 0, 1],
                    "logScale": [0, 0, 0],
                    "logitOpacity": 0,
                    "dc": [0, 0, 0],
                    "sh": [],
                }
                for stable_id in [3, 7, 9]
            ],
        }

    def test_publishes_one_complete_immutable_anchor_mask_set(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [
                {
                    "viewId": "anchor-view",
                    "frameDigest": "sha256:anchor-frame-v1",
                    "width": 64,
                    "height": 48,
                }
            ],
        }
        registered = self.request_json("/frame-sets/anchor-v1", "PUT", frame_set)
        self.assertEqual(registered, {
            "status": "registered",
            "frameSetVersion": "anchor-v1",
        })

        snapshot = self.snapshot()
        self.request_json("/scene-snapshots/scene-1/snapshot-v1", "PUT", snapshot)
        with urlopen(
            Request(
                f"{self.endpoint}/object-selection-sessions",
                data=json.dumps(
                    {
                        "target": {"targetSplatId": "splat-1"},
                        "frameSetVersion": frame_set["frameSetVersion"],
                        "modelManifestDigest": self.model_manifest_digest,
                    }
                ).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )
        ) as response:
            self.assertEqual(response.status, HTTPStatus.CREATED)
            session_id = json.load(response)["sessionId"]

        bindings = {
            "requestId": "request-1",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        preview = {
            **bindings,
            "target": {"targetSplatId": "splat-1"},
            "promptLog": [
                {
                    "operation": "New",
                    "prompt": {
                        "promptId": "prompt-1",
                        "viewId": "anchor-view",
                        "frameDigest": "sha256:anchor-frame-v1",
                        "frameWidth": 64,
                        "frameHeight": 48,
                        "xPx": 10,
                        "yPx": 20,
                        "polarity": "include",
                    },
                }
            ],
        }

        result = self.request_json(
            f"/object-selection-sessions/{session_id}/previews", "POST", preview
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selectedIds"], [3])
        self.assertEqual(result["uncertainIds"], [7])
        self.assertEqual(result["rejectedIds"], [9])
        self.assertEqual(result["maskSet"], {
            "status": "complete",
            "requestId": "request-1",
            "sessionId": session_id,
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "modelManifestDigest": self.model_manifest_digest,
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
                                "width": 64,
                                "height": 48,
                                "foregroundPixels": [[10, 20]],
                            },
                        }
                    ],
                }
            ],
        })

        repeated = self.request_json(
            f"/object-selection-sessions/{session_id}/previews", "POST", preview
        )
        self.assertEqual(repeated, result)

    def test_rejects_a_malformed_frame_set_with_a_structured_error(self) -> None:
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    f"{self.endpoint}/frame-sets/anchor-v1",
                    data=b"{not-json",
                    method="PUT",
                    headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
                )
            )

        self.assertEqual(error.exception.code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(json.load(error.exception), {
            "status": "invalidRequest",
            "code": "invalidFrameSet",
            "message": "request body is not valid JSON",
        })

    def test_releases_an_unclaimed_frame_set_idempotently(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.request_json("/frame-sets/anchor-v1", "PUT", frame_set)

        for _ in range(2):
            with urlopen(Request(
                f"{self.endpoint}/frame-sets/anchor-v1",
                method="DELETE",
                headers={"Origin": EDITOR_ORIGIN},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.NO_CONTENT)

        self.assertNotIn("anchor-v1", self.state._frame_sets)

    def test_refuses_to_release_a_frame_set_claimed_by_a_session(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.state.register_frame_set(frame_set)
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)

        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f"{self.endpoint}/frame-sets/anchor-v1",
                method="DELETE",
                headers={"Origin": EDITOR_ORIGIN},
            ))

        self.assertEqual(error.exception.code, HTTPStatus.CONFLICT)
        self.assertEqual(json.load(error.exception)["status"], "frameSetInUse")
        self.assertIn("anchor-v1", self.state._frame_sets)

    def test_recovers_and_cleans_a_session_by_its_open_request_id(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.request_json("/frame-sets/anchor-v1", "PUT", frame_set)
        admission = {
            "frameSetVersion": "anchor-v1",
            "modelManifestDigest": self.model_manifest_digest,
            "openRequestId": "open-recovery-1",
        }

        def open_session() -> dict[str, object]:
            with urlopen(Request(
                f"{self.endpoint}/object-selection-sessions",
                data=json.dumps(admission).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.CREATED)
                return json.load(response)

        first = open_session()
        recovered = open_session()
        self.assertEqual(first, recovered)
        self.assertEqual(first["openRequestId"], admission["openRequestId"])
        session_id = first["sessionId"]
        self.assertIsInstance(session_id, str)
        assert isinstance(session_id, str)
        self.assertTrue(self.state.has_object_selection_session(session_id))

        with urlopen(Request(
            f"{self.endpoint}/object-selection-sessions/open-requests/open-recovery-1",
            method="DELETE",
            headers={"Origin": EDITOR_ORIGIN},
        )) as response:
            self.assertEqual(response.status, HTTPStatus.NO_CONTENT)

        self.assertFalse(self.state.has_object_selection_session(session_id))
        self.assertNotIn("anchor-v1", self.state._frame_sets)

    def test_rejects_frame_bytes_in_the_point_only_prompt_log(self) -> None:
        frame_set = register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        })

        with self.assertRaises(MaskSessionError) as error:
            PointMaskAdapter._validate_point_prompt({
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "imagePngBase64": "must-stay-in-frame-set",
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            }, frame_set)

        self.assertEqual(error.exception.code, "invalidPromptLog")

    def test_point_reference_masks_are_ordered_row_major(self) -> None:
        outcome = PointMaskAdapter._frame_outcome(
            RegisteredFrame(
                view_id="anchor-view",
                frame_digest="sha256:anchor-frame-v1",
                width=16,
                height=16,
            ),
            [(0, 10, "include"), (10, 0, "include")],
        )

        self.assertEqual(
            outcome["binaryMask"]["foregroundPixels"],
            [[10, 0], [0, 10]],
        )

    def test_sam31_rejects_a_candidate_that_contradicts_anchor_points(self) -> None:
        outcome = Sam3PointMaskAdapter._mask_outcome_from_response(
            {
                "outputs": {
                    "out_binary_masks": [[[True, False], [False, False]]],
                },
            },
            RegisteredFrame(
                view_id="anchor-view",
                frame_digest="sha256:anchor-frame-v1",
                width=2,
                height=2,
            ),
            points=[[1, 0], [0, 0]],
            point_labels=[1, 0],
        )

        self.assertEqual(outcome["status"], "rejected")
        self.assertIn("point prompts", outcome["rejectionReason"])

    def test_sam31_prefers_the_highest_scoring_prompt_consistent_candidate(self) -> None:
        outcome = Sam3PointMaskAdapter._mask_outcome_from_response(
            {
                "outputs": {
                    "out_binary_masks": [
                        [[False, True], [False, False]],
                        [[False, True], [True, False]],
                    ],
                    "out_probs": [0.1, 0.9],
                },
            },
            RegisteredFrame(
                view_id="anchor-view",
                frame_digest="sha256:anchor-frame-v1",
                width=2,
                height=2,
            ),
            points=[[1, 0]],
            point_labels=[1],
        )

        self.assertEqual(outcome["status"], "accepted")
        self.assertEqual(outcome["binaryMask"]["data"], "Bg==")

    def test_sam31_reports_an_empty_model_output_as_not_found(self) -> None:
        outcome = Sam3PointMaskAdapter._mask_outcome_from_response(
            {"outputs": {"out_binary_masks": []}},
            RegisteredFrame(
                view_id="anchor-view",
                frame_digest="sha256:anchor-frame-v1",
                width=2,
                height=2,
            ),
            points=[[1, 0]],
            point_labels=[1],
        )

        self.assertEqual(outcome["status"], "not_found")

    def test_sam31_rejects_a_full_frame_candidate_as_too_coarse(self) -> None:
        outcome = Sam3PointMaskAdapter._mask_outcome_from_response(
            {
                "outputs": {
                    "out_binary_masks": [[[True, True], [True, True]]],
                },
            },
            RegisteredFrame(
                view_id="anchor-view",
                frame_digest="sha256:anchor-frame-v1",
                width=2,
                height=2,
            ),
            points=[[1, 0]],
            point_labels=[1],
        )

        self.assertEqual(outcome["status"], "rejected")
        self.assertIn("area validation", outcome["rejectionReason"])

    def test_deduplicates_concurrent_preview_lifting_for_one_request_id(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.state.register_frame_set(frame_set)
        self.state.register_scene_snapshot(self.snapshot())
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        bindings = {
            "requestId": "request-1",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        prompt_log = [{
            "operation": "New",
            "prompt": {
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            },
        }]
        started = Event()
        release = Event()

        class BlockingContributorRenderer:
            renderer_id = "gsplat"

            def render(self, *, scene_snapshot, frame):
                started.set()
                release.wait(timeout=2)
                return PointFixtureContributorRenderer().render(
                    scene_snapshot=scene_snapshot,
                    frame=frame,
                )

        self.state.contributor_renderer = BlockingContributorRenderer()
        results: list[tuple[dict[str, object], dict[str, object]]] = []
        failures: list[BaseException] = []

        def update_preview() -> None:
            try:
                results.append(
                    self.state.update_preview(
                        bindings=bindings,
                        prompt_log=prompt_log,
                    )
                )
            except BaseException as error:
                failures.append(error)

        update_thread = Thread(target=update_preview)
        update_thread.start()
        self.assertTrue(started.wait(timeout=2))
        with self.assertRaises(MaskSessionError) as duplicate_error:
            self.state.update_preview(bindings=bindings, prompt_log=prompt_log)
        self.assertEqual(duplicate_error.exception.code, "updateInProgress")
        release.set()
        update_thread.join(timeout=2)

        self.assertEqual(failures, [])
        self.assertEqual(len(results), 1)
        mask_set, evidence_snapshot = results[0]
        self.assertEqual(mask_set["status"], "complete")
        self.assertEqual(evidence_snapshot["requestId"], "request-1")
        self.assertFalse(self.state.cancel_mask_update(session_id, "request-1"))

    def test_cancellation_and_close_hold_the_preview_lease_until_evidence_is_settled(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.state.register_frame_set(frame_set)
        self.state.register_scene_snapshot(self.snapshot())
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        bindings = {
            "requestId": "request-1",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        prompt_log = [{
            "operation": "New",
            "prompt": {
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            },
        }]
        prior = self.state.update_mask_session(
            bindings={**bindings, "requestId": "request-0"},
            prompt_log=prompt_log,
        )
        self.state.build_evidence_snapshot(
            bindings={**bindings, "requestId": "request-0"},
            mask_set=prior,
        )

        started = Event()
        release = Event()

        class BlockingPointMaskAdapter:
            def produce_tracks(self, *, model, frame_set, prompt_log, cancelled):
                started.set()
                release.wait(timeout=2)
                return PointMaskAdapter().produce_tracks(
                    model=model,
                    frame_set=frame_set,
                    prompt_log=prompt_log,
                    cancelled=lambda: False,
                )

        self.state.mask_adapters["point-mask-v1"] = BlockingPointMaskAdapter()
        failures: list[BaseException] = []

        def update() -> None:
            try:
                self.state.update_mask_session(bindings=bindings, prompt_log=prompt_log)
            except BaseException as error:
                failures.append(error)

        update_thread = Thread(target=update)
        update_thread.start()
        self.assertTrue(started.wait(timeout=2))
        self.assertTrue(self.state.cancel_mask_update(session_id, "request-1"))
        release.set()
        update_thread.join(timeout=2)

        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], MaskSessionError)
        self.assertEqual(failures[0].code, "cancelled")

        self.state.mask_adapters["point-mask-v1"] = PointMaskAdapter()
        recovered = self.state.update_mask_session(
            bindings={**bindings, "requestId": "request-2"},
            prompt_log=prompt_log,
        )

        self.assertEqual(recovered["status"], "complete")
        self.assertEqual(
            self.state.update_mask_session(
                bindings={**bindings, "requestId": "request-0"},
                prompt_log=prompt_log,
            ),
            prior,
        )

        contributor_started = Event()
        contributor_release = Event()

        class BlockingContributorRenderer:
            renderer_id = "gsplat"

            def render(self, *, scene_snapshot, frame):
                contributor_started.set()
                contributor_release.wait(timeout=2)
                return PointFixtureContributorRenderer().render(
                    scene_snapshot=scene_snapshot,
                    frame=frame,
                )

        self.state.contributor_renderer = BlockingContributorRenderer()
        evidence_failures: list[BaseException] = []

        def lift_evidence() -> None:
            try:
                self.state.build_evidence_snapshot(
                    bindings={**bindings, "requestId": "request-2"},
                    mask_set=recovered,
                )
            except BaseException as error:
                evidence_failures.append(error)

        evidence_thread = Thread(target=lift_evidence)
        evidence_thread.start()
        self.assertTrue(contributor_started.wait(timeout=2))
        self.assertTrue(self.state.cancel_mask_update(session_id, "request-2"))
        contributor_release.set()
        evidence_thread.join(timeout=2)

        self.assertEqual(len(evidence_failures), 1)
        self.assertIsInstance(evidence_failures[0], MaskSessionError)
        self.assertEqual(evidence_failures[0].code, "cancelled")
        active = self.state._mask_sessions[session_id]
        self.assertNotIn("request-2", active.completed_evidence_snapshots)
        self.assertFalse(self.state.cancel_mask_update(session_id, "request-0"))

        closing_mask_set = self.state.update_mask_session(
            bindings={**bindings, "requestId": "request-3"},
            prompt_log=prompt_log,
        )
        closing_started = Event()
        closing_release = Event()

        class ClosingContributorRenderer:
            renderer_id = "gsplat"

            def render(self, *, scene_snapshot, frame):
                closing_started.set()
                closing_release.wait(timeout=2)
                return PointFixtureContributorRenderer().render(
                    scene_snapshot=scene_snapshot,
                    frame=frame,
                )

        self.state.contributor_renderer = ClosingContributorRenderer()
        closing_failures: list[BaseException] = []

        def lift_while_closing() -> None:
            try:
                self.state.build_evidence_snapshot(
                    bindings={**bindings, "requestId": "request-3"},
                    mask_set=closing_mask_set,
                )
            except BaseException as error:
                closing_failures.append(error)

        closing_thread = Thread(target=lift_while_closing)
        closing_thread.start()
        self.assertTrue(closing_started.wait(timeout=2))
        self.assertTrue(self.state.close_object_selection_session(session_id))
        self.assertTrue(self.state.has_object_selection_session(session_id))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["capacity"]["activeSessions"], 1
        )
        closing_release.set()
        closing_thread.join(timeout=2)

        self.assertEqual(len(closing_failures), 1)
        self.assertIsInstance(closing_failures[0], MaskSessionError)
        self.assertEqual(closing_failures[0].code, "cancelled")
        self.assertFalse(self.state.has_object_selection_session(session_id))

    def test_closing_a_session_drains_inference_before_releasing_capacity(self) -> None:
        anchor_frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.state.register_frame_set(anchor_frame_set)
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        bindings = {
            "requestId": "draining-request",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        prompt_log = [{
            "operation": "New",
            "prompt": {
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            },
        }]
        started = Event()
        release = Event()

        class BlockingPointMaskAdapter:
            def produce_tracks(self, *, model, frame_set, prompt_log, cancelled):
                started.set()
                release.wait(timeout=2)
                return PointMaskAdapter().produce_tracks(
                    model=model,
                    frame_set=frame_set,
                    prompt_log=prompt_log,
                    cancelled=lambda: False,
                )

        self.state.mask_adapters["point-mask-v1"] = BlockingPointMaskAdapter()
        failures: list[BaseException] = []

        def update() -> None:
            try:
                self.state.update_mask_session(bindings=bindings, prompt_log=prompt_log)
            except BaseException as error:
                failures.append(error)

        update_thread = Thread(target=update)
        update_thread.start()
        self.assertTrue(started.wait(timeout=2))
        self.assertTrue(self.state.close_object_selection_session(session_id))
        self.assertTrue(self.state.has_object_selection_session(session_id))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["capacity"]["activeSessions"], 1
        )
        with self.assertRaises(MaskSessionError) as closing_error:
            self.state.update_mask_session(
                bindings={**bindings, "requestId": "closing-request"},
                prompt_log=prompt_log,
            )
        self.assertEqual(closing_error.exception.code, "cancelled")

        next_frame_set = {
            **anchor_frame_set,
            "frameSetVersion": "anchor-v2",
        }
        self.state.register_frame_set(next_frame_set)
        self.assertIsNone(self.state.open_object_selection_session(
            frame_set_version="anchor-v2",
            model_manifest_digest=self.model_manifest_digest,
        ))
        self.assertNotIn("anchor-v2", self.state._frame_sets)

        release.set()
        update_thread.join(timeout=2)

        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], MaskSessionError)
        self.assertEqual(failures[0].code, "cancelled")
        self.assertFalse(self.state.has_object_selection_session(session_id))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["capacity"]["activeSessions"], 0
        )

        self.state.register_frame_set(next_frame_set)
        self.assertIsNotNone(self.state.open_object_selection_session(
            frame_set_version="anchor-v2",
            model_manifest_digest=self.model_manifest_digest,
        ))

    def test_stale_versions_and_absent_weights_preserve_the_prior_mask_set(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.state.register_frame_set(frame_set)
        self.state.register_scene_snapshot(self.snapshot())
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        bindings = {
            "requestId": "request-0",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        prompt_log = [{
            "operation": "New",
            "prompt": {
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            },
        }]
        prior = self.state.update_mask_session(bindings=bindings, prompt_log=prompt_log)

        with self.assertRaises(MaskSessionError) as conflict_error:
            self.state.update_mask_session(
                bindings={**bindings, "frameSetVersion": "anchor-v2"},
                prompt_log=prompt_log,
            )
        self.assertEqual(conflict_error.exception.code, "requestIdConflict")

        with self.assertRaises(MaskSessionError) as stale_error:
            self.state.update_mask_session(
                bindings={
                    **bindings,
                    "requestId": "request-stale",
                    "frameSetVersion": "anchor-v2",
                },
                prompt_log=prompt_log,
            )
        self.assertEqual(stale_error.exception.code, "staleFrameSet")

        self.weights.write_bytes(b"weights changed after installation")
        with self.assertRaises(MaskSessionError) as missing_weights_error:
            self.state.update_mask_session(
                bindings={**bindings, "requestId": "request-missing-weights"},
                prompt_log=prompt_log,
            )
        self.assertEqual(missing_weights_error.exception.code, "modelUnavailable")

        self.assertEqual(
            self.state.update_mask_session(bindings=bindings, prompt_log=prompt_log),
            prior,
        )

    def test_model_failure_returns_an_actionable_bound_result_and_preserves_retry(self) -> None:
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        self.request_json("/frame-sets/anchor-v1", "PUT", frame_set)
        self.request_json("/scene-snapshots/scene-1/snapshot-v1", "PUT", self.snapshot())
        with urlopen(
            Request(
                f"{self.endpoint}/object-selection-sessions",
                data=json.dumps({
                    "target": {"targetSplatId": "splat-1"},
                    "frameSetVersion": "anchor-v1",
                    "modelManifestDigest": self.model_manifest_digest,
                }).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )
        ) as response:
            session_id = json.load(response)["sessionId"]
        bindings = {
            "requestId": "request-model-failure",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        preview = {
            **bindings,
            "target": {"targetSplatId": "splat-1"},
            "promptLog": [{
                "operation": "New",
                "prompt": {
                    "promptId": "prompt-1",
                    "viewId": "anchor-view",
                    "frameDigest": "sha256:anchor-frame-v1",
                    "frameWidth": 64,
                    "frameHeight": 48,
                    "xPx": 10,
                    "yPx": 20,
                    "polarity": "include",
                },
            }],
        }

        class FailingPointMaskAdapter:
            def produce_tracks(self, **_kwargs):
                raise RuntimeError("model runtime stopped")

        self.state.mask_adapters["point-mask-v1"] = FailingPointMaskAdapter()
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    f"{self.endpoint}/object-selection-sessions/{session_id}/previews",
                    data=json.dumps(preview).encode(),
                    method="POST",
                    headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
                )
            )
        self.assertEqual(error.exception.code, HTTPStatus.CONFLICT)
        self.assertEqual(json.load(error.exception), {
            "status": "maskSessionError",
            "code": "modelFailure",
            "message": "The promptable-mask adapter failed; verify the installed model runtime and retry.",
            **bindings,
        })

        self.state.mask_adapters["point-mask-v1"] = PointMaskAdapter()
        self.assertEqual(
            self.request_json(
                f"/object-selection-sessions/{session_id}/previews", "POST", preview
            )["status"],
            "complete",
        )

    def test_sam31_adapter_consumes_the_anchor_frame_and_verified_weights(self) -> None:
        image_png = b"\x89PNG\r\n\x1a\nanchor-frame"
        image_base64 = base64.b64encode(image_png).decode("ascii")
        frame_digest = f"sha256:{hashlib.sha256(image_png).hexdigest()}"
        weights = self.directory / "sam31.pt"
        weights.write_bytes(b"separately acquired sam3.1 weights")
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / "sam31.json"
        manifest.write_text(
            json.dumps(
                {
                    "digest": "sha256:sam31-v1",
                    "adapterId": "sam3.1",
                    "modelName": "SAM 3.1",
                    "checkpointDigest": f"sha256:{checkpoint_digest}",
                    "sourceCommit": "sam3-source-v1",
                    "licenseName": "SAM License",
                    "licenseUrl": "https://example.test/sam-license",
                    "runtimeConfigDigest": SAM31_RUNTIME_CONFIG_DIGEST,
                }
            ),
            encoding="utf-8",
        )
        model_manifest_digest = self.state.install_model(manifest, weights)["digest"]
        calls: list[dict[str, object]] = []
        test_case = self

        class FakeSam3Predictor:
            def handle_request(self, request: dict[str, object]) -> dict[str, object]:
                calls.append(request)
                if request["type"] == "start_session":
                    test_case.assertEqual(
                        Path(str(request["resource_path"])).read_bytes(), image_png
                    )
                    return {"session_id": "sam-session"}
                if request["type"] == "add_prompt":
                    return {
                        "outputs": {
                            "out_binary_masks": [
                                [[True, False], [False, False]],
                                [[False, True], [False, False]],
                            ],
                            "out_probs": [0.1, 0.9],
                        }
                    }
                return {"is_success": True}

        self.state.mask_adapters["sam3.1"] = Sam3PointMaskAdapter(
            build_predictor=lambda model: FakeSam3Predictor()
        )
        self.state.register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": frame_digest,
                "width": 2,
                "height": 2,
                "imagePngBase64": image_base64,
            }],
        })
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        result = self.state.update_mask_session(
            bindings={
                "requestId": "sam-request-1",
                "sessionId": session_id,
                "targetSplatId": "splat-1",
                "sceneId": "scene-1",
                "sceneVersion": "snapshot-v1",
                "operation": "New",
                "correctionRound": 0,
                "deterministicSeed": "seed-1",
                "promptLogRevision": 1,
                "frameSetVersion": "anchor-v1",
                "renderConfigVersion": "effective-rgb-v1",
                "modelManifestDigest": model_manifest_digest,
            },
            prompt_log=[{
                "operation": "New",
                "prompt": {
                    "promptId": "prompt-1",
                    "viewId": "anchor-view",
                    "frameDigest": frame_digest,
                    "frameWidth": 2,
                    "frameHeight": 2,
                    "xPx": 1,
                    "yPx": 0,
                    "polarity": "include",
                },
            }],
        )

        self.assertEqual(result["tracks"], [{
            "trackId": "primary",
            "role": "include",
            "frames": [{
                "viewId": "anchor-view",
                "status": "accepted",
                "binaryMask": {
                    "encoding": "bitset-lsb-v1",
                    "width": 2,
                    "height": 2,
                    "data": "Ag==",
                },
            }],
        }])
        self.assertEqual(result["threshold"], 0.5)
        self.assertEqual(result["diagnostics"], {
            "adapterId": "sam3.1",
            "candidateSelection": {
                "scoreSemantics": (
                    "sam3.1.out_probs is an adapter-local candidate quality score "
                    "used only to order candidates that satisfy point and area validation."
                ),
                "selectedCandidateIndex": 1,
                "alternatives": [
                    {
                        "candidateIndex": 0,
                        "foregroundPixelCount": 1,
                        "areaValid": True,
                        "pointConsistent": False,
                        "selected": False,
                        "qualityScore": 0.1,
                    },
                    {
                        "candidateIndex": 1,
                        "foregroundPixelCount": 1,
                        "areaValid": True,
                        "pointConsistent": True,
                        "selected": True,
                        "qualityScore": 0.9,
                    },
                ],
            },
        })
        self.assertEqual(calls, [
            {
                "type": "start_session",
                "resource_path": calls[0]["resource_path"],
                "offload_video_to_cpu": True,
                "offload_state_to_cpu": False,
            },
            {
                "type": "add_prompt",
                "session_id": "sam-session",
                "frame_index": 0,
                "points": [[1, 0]],
                "point_labels": [1],
                "clear_old_points": True,
                "rel_coordinates": False,
                "obj_id": 1,
                "output_prob_thresh": 0.5,
            },
            {
                "type": "close_session",
                "session_id": "sam-session",
                "run_gc_collect": False,
            },
        ])

    def test_sam31_builder_uses_the_pinned_runtime_configuration(self) -> None:
        weights = self.directory / "sam31-runtime.pt"
        weights.write_bytes(b"separately acquired sam3.1 weights")
        calls: list[dict[str, object]] = []
        sam3_module = ModuleType("sam3")
        sam3_module.__path__ = []
        model_builder_module = ModuleType("sam3.model_builder")

        def build_sam3_multiplex_video_predictor(**kwargs: object) -> object:
            calls.append(kwargs)
            return object()

        model_builder_module.build_sam3_multiplex_video_predictor = (
            build_sam3_multiplex_video_predictor
        )
        with patch.dict(sys.modules, {
            "sam3": sam3_module,
            "sam3.model_builder": model_builder_module,
        }):
            predictor = _build_sam3_predictor({"weightsPath": str(weights)})

        self.assertIsNotNone(predictor)
        self.assertEqual(calls, [{
            "checkpoint_path": str(weights),
            "max_num_objects": 8,
            "multiplex_count": 16,
            "use_fa3": False,
            "use_rope_real": True,
            "compile": False,
            "warm_up": False,
            "session_expiration_sec": 1200,
            "default_output_prob_thresh": 0.5,
            "async_loading_frames": False,
        }])

    def test_rejects_an_installed_manifest_without_a_compatible_adapter(self) -> None:
        weights = self.directory / "unsupported-adapter.bin"
        weights.write_bytes(b"separately acquired unsupported adapter weights")
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / "unsupported-adapter.json"
        manifest.write_text(
            json.dumps(
                {
                    "digest": "sha256:unsupported-adapter-v1",
                    "adapterId": "unsupported-adapter-v1",
                    "modelName": "Unsupported adapter",
                    "checkpointDigest": f"sha256:{checkpoint_digest}",
                    "sourceCommit": "sam3-source-v1",
                    "licenseName": "SAM License",
                    "licenseUrl": "https://example.test/sam-license",
                    "runtimeConfigDigest": "sha256:sam-runtime-v1",
                }
            ),
            encoding="utf-8",
        )
        incompatible_manifest_digest = self.state.install_model(manifest, weights)["digest"]
        self.state.register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        })

        with self.assertRaises(MaskSessionError) as error:
            self.state.open_object_selection_session(
                frame_set_version="anchor-v1",
                model_manifest_digest=incompatible_manifest_digest,
            )

        self.assertEqual(error.exception.code, "incompatibleManifest")
        self.assertNotIn("anchor-v1", self.state._frame_sets)

    def test_rejects_an_invalid_complete_mask_set_before_publishing_or_lifting(self) -> None:
        self.state.register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        })
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None
        bindings = {
            "requestId": "invalid-mask-request",
            "sessionId": session_id,
            "targetSplatId": "splat-1",
            "sceneId": "scene-1",
            "sceneVersion": "snapshot-v1",
            "operation": "New",
            "correctionRound": 0,
            "deterministicSeed": "seed-1",
            "promptLogRevision": 1,
            "frameSetVersion": "anchor-v1",
            "renderConfigVersion": "effective-rgb-v1",
            "modelManifestDigest": self.model_manifest_digest,
        }
        prompt_log = [{
            "operation": "New",
            "prompt": {
                "promptId": "prompt-1",
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "frameWidth": 64,
                "frameHeight": 48,
                "xPx": 10,
                "yPx": 20,
                "polarity": "include",
            },
        }]

        invalid_tracks = [
            [{
                "trackId": "primary",
                "role": "exclude",
                "frames": [{
                    "viewId": "anchor-view",
                    "status": "accepted",
                    "binaryMask": {
                        "encoding": "sparse-points-v1",
                        "width": 64,
                        "height": 48,
                        "foregroundPixels": [[10, 20]],
                    },
                }],
            }],
            [{
                "trackId": "primary",
                "role": "include",
                "frames": [{
                    "viewId": "anchor-view",
                    "status": "accepted",
                    "binaryMask": {},
                }],
            }],
        ]

        for tracks in invalid_tracks:
            class InvalidMaskAdapter:
                def produce_tracks(self, **_kwargs):
                    return MaskProduction(tracks=tracks, threshold=0.0)

            self.state.mask_adapters["point-mask-v1"] = InvalidMaskAdapter()
            with self.assertRaises(MaskSessionError) as error:
                self.state.update_mask_session(bindings=bindings, prompt_log=prompt_log)
            self.assertEqual(error.exception.code, "incompleteMaskSet")

        self.state.mask_adapters["point-mask-v1"] = PointMaskAdapter()
        recovered = self.state.update_mask_session(
            bindings=bindings,
            prompt_log=prompt_log,
        )
        self.assertEqual(recovered["status"], "complete")

    def test_rejects_conflicting_model_reinstallation_without_mutating_an_active_session(self) -> None:
        self.state.register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        })
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)

        replacement_weights = self.directory / "replacement-point-mask.bin"
        replacement_weights.write_bytes(b"different separately acquired point-mask weights")
        replacement_digest = hashlib.sha256(replacement_weights.read_bytes()).hexdigest()
        replacement_manifest = self.directory / "replacement-point-mask.json"
        replacement_manifest.write_text(
            json.dumps({
                "digest": self.model_manifest_digest,
                "adapterId": "point-mask-v1",
                "modelName": "Point Mask v1",
                "checkpointDigest": f"sha256:{replacement_digest}",
                "sourceCommit": "point-mask-source-v2",
                "licenseName": "MIT",
                "licenseUrl": "https://example.test/point-mask-license",
                "runtimeConfigDigest": "sha256:point-mask-runtime-v2",
            }),
            encoding="utf-8",
        )

        original = self.state.models()
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.state.install_model(replacement_manifest, replacement_weights)
        self.assertEqual(self.state.models(), original)
        self.assertTrue(self.state.has_object_selection_session(str(session_id)))
        active_model, _adapter = self.state._require_mask_adapter(
            self.model_manifest_digest
        )
        self.assertEqual(active_model["checkpointDigest"], original[0]["checkpointDigest"])

    def test_closing_a_mask_session_reclaims_its_frame_and_scene_caches(self) -> None:
        image_png = b"\x89PNG\r\n\x1a\nanchor-frame"
        self.state.register_frame_set({
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor-v1",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": f"sha256:{hashlib.sha256(image_png).hexdigest()}",
                "width": 64,
                "height": 48,
                "imagePngBase64": base64.b64encode(image_png).decode("ascii"),
            }],
        })
        self.state.register_scene_snapshot(self.snapshot())
        session_id = self.state.open_object_selection_session(
            frame_set_version="anchor-v1",
            model_manifest_digest=self.model_manifest_digest,
        )
        self.assertIsNotNone(session_id)
        assert session_id is not None

        self.assertIn("anchor-v1", self.state._frame_sets)
        self.assertIsNotNone(self.state.scene_snapshot("scene-1", "snapshot-v1"))
        self.assertTrue(self.state.close_object_selection_session(session_id))

        self.assertEqual(self.state._frame_sets, {})
        self.assertIsNone(self.state.scene_snapshot("scene-1", "snapshot-v1"))
        self.assertEqual(self.state._mask_sessions, {})

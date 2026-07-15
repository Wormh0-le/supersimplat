from __future__ import annotations

import hashlib
from contextlib import redirect_stdout
from http import HTTPStatus
from io import StringIO
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.cli import main
from selection_service_companion.evidence import (
    ContributorSample,
    RenderedContributorView,
    StaticContributorRenderer,
)
from selection_service_companion.masking import (
    PointMaskAdapter,
    SAM31_RUNTIME_CONFIG_DIGEST,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = "https://editor.example"


class CompanionControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / "state")
        self.lock_file = self.directory / "uv.lock"
        self.lock_file.write_text("locked companion dependencies\n", encoding="utf-8")
        self.state.install_release("0.1.0", self.lock_file)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def install_model(
        self,
        *,
        adapter_id: str = "sam3.1",
        model_name: str = "SAM 3.1",
        runtime_config_digest: str | None = None,
    ) -> str:
        weights = self.directory / "sam31.pt"
        weights.write_bytes(b"separately acquired model weights")
        digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / "sam31.json"
        manifest.write_text(
            """{
  "digest": "sha256:model-v1",
  "adapterId": "%s",
  "modelName": "%s",
  "checkpointDigest": "sha256:%s",
  "sourceCommit": "abc123",
  "licenseName": "SAM License",
  "licenseUrl": "https://example.test/license",
  "runtimeConfigDigest": "%s"
}
""" % (
                adapter_id,
                model_name,
                digest,
                runtime_config_digest or (
                    SAM31_RUNTIME_CONFIG_DIGEST
                    if adapter_id == "sam3.1"
                    else "sha256:runtime-v1"
                ),
            ),
            encoding="utf-8",
        )
        return self.state.install_model(manifest, weights)["digest"]

    def test_registers_a_separately_stored_model_without_bundling_weights(self) -> None:
        model_digest = self.install_model()

        capabilities = self.state.capabilities([EDITOR_ORIGIN])

        self.assertEqual(capabilities["protocolVersion"], "1")
        self.assertEqual(capabilities["capacity"], {"maximumActiveSessions": 1, "activeSessions": 0})
        self.assertEqual(capabilities["modelManifests"], [{
            "digest": model_digest,
            "adapterId": "sam3.1",
            "modelName": "SAM 3.1",
            "weightsBundled": False,
        }])
        self.assertEqual(capabilities["renderer"]["status"], "unavailable")

    def test_keeps_the_reference_point_adapter_out_of_production_capabilities(self) -> None:
        self.install_model(adapter_id="point-mask-v1", model_name="Point Mask v1")

        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["modelManifests"],
            [],
        )

    def test_rejects_a_sam31_manifest_with_an_unpinned_runtime_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtimeConfigDigest"):
            self.install_model(runtime_config_digest="sha256:runtime-v1")

    def test_records_the_actual_lock_file_digest_when_installing_a_release(self) -> None:
        data_directory = self.directory / "cli-state"

        with redirect_stdout(StringIO()):
            result = main([
                "--data-dir", str(data_directory),
                "install",
                "--release", "0.1.0",
                "--lock-file", str(self.lock_file),
            ])

        release = json.loads((data_directory / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(result, 0)
        self.assertEqual(
            release["lockDigest"],
            f"sha256:{hashlib.sha256(self.lock_file.read_bytes()).hexdigest()}",
        )

    def test_rejects_a_release_when_its_verified_lock_file_changes(self) -> None:
        self.lock_file.write_text("changed locked companion dependencies\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "lock changed"):
            self.state.require_release()

    def test_excludes_a_changed_model_artifact_from_capabilities(self) -> None:
        self.install_model()
        (self.directory / "sam31.pt").write_bytes(b"changed after installation")

        capabilities = self.state.capabilities([EDITOR_ORIGIN])

        self.assertEqual(capabilities["modelManifests"], [])

    def test_excludes_a_missing_model_artifact_from_capabilities(self) -> None:
        self.install_model()
        (self.directory / "sam31.pt").unlink()

        capabilities = self.state.capabilities([EDITOR_ORIGIN])

        self.assertEqual(capabilities["modelManifests"], [])

    def test_enforces_exact_editor_origin_cors_for_health_and_capabilities(self) -> None:
        server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=[EDITOR_ORIGIN],
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urlopen(Request(f"{endpoint}/health", headers={"Origin": EDITOR_ORIGIN})) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], EDITOR_ORIGIN)
                self.assertEqual(response.headers["Vary"], "Origin")

            with urlopen(Request(
                f"{endpoint}/capabilities",
                method="OPTIONS",
                headers={"Origin": EDITOR_ORIGIN},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.NO_CONTENT)
                self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, POST, PUT, DELETE, OPTIONS")
                self.assertEqual(response.headers["Access-Control-Allow-Headers"], "Content-Type")

            with self.assertRaises(HTTPError) as error:
                urlopen(Request(f"{endpoint}/capabilities", headers={"Origin": "https://untrusted.example"}))
            self.assertEqual(error.exception.code, HTTPStatus.FORBIDDEN)

            with self.assertRaises(HTTPError) as error:
                urlopen(f"{endpoint}/capabilities")
            self.assertEqual(error.exception.code, HTTPStatus.FORBIDDEN)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_admits_exactly_one_object_selection_session_and_releases_capacity_on_close(self) -> None:
        server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=[EDITOR_ORIGIN],
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urlopen(Request(
                f"{endpoint}/object-selection-sessions",
                data=b"{}",
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.CREATED)
                session_id = json.load(response)["sessionId"]

            with urlopen(Request(f"{endpoint}/capabilities", headers={"Origin": EDITOR_ORIGIN})) as response:
                self.assertEqual(json.load(response)["capacity"], {
                    "maximumActiveSessions": 1,
                    "activeSessions": 1,
                })

            with self.assertRaises(HTTPError) as error:
                urlopen(Request(
                    f"{endpoint}/object-selection-sessions",
                    data=b"{}",
                    method="POST",
                    headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
                ))
            self.assertEqual(error.exception.code, HTTPStatus.CONFLICT)
            self.assertEqual(json.load(error.exception)["status"], "busy")

            with urlopen(Request(
                f"{endpoint}/object-selection-sessions/{session_id}",
                method="DELETE",
                headers={"Origin": EDITOR_ORIGIN},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.NO_CONTENT)

            with urlopen(Request(f"{endpoint}/capabilities", headers={"Origin": EDITOR_ORIGIN})) as response:
                self.assertEqual(json.load(response)["capacity"], {
                    "maximumActiveSessions": 1,
                    "activeSessions": 0,
                })
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_exchanges_a_versioned_scene_snapshot_before_a_deterministic_preview(self) -> None:
        # The sparse-point reference adapter is explicitly test-injected; the
        # production Companion exposes only model-backed adapters.
        self.state.mask_adapters["point-mask-v1"] = PointMaskAdapter()
        self.state.contributor_renderer = StaticContributorRenderer(
            {
                "anchor-view": RenderedContributorView(
                    view_id="anchor-view",
                    rgb_frame_digest="sha256:anchor-frame-v1",
                    width=64,
                    height=48,
                    support_bounds=(0, 0, 11, 21),
                    contributors=(
                        ContributorSample(stable_id=3, x_px=10, y_px=20, mass=3.0),
                        ContributorSample(stable_id=9, x_px=0, y_px=0, mass=3.0),
                    ),
                )
            }
        )
        model_manifest_digest = self.install_model(
            adapter_id="point-mask-v1", model_name="Point Mask v1"
        )
        server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=[EDITOR_ORIGIN],
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        frame_set = {
            "frameSetId": "frames-1",
            "frameSetVersion": "anchor:anchor-view",
            "orderedViews": [{
                "viewId": "anchor-view",
                "frameDigest": "sha256:anchor-frame-v1",
                "width": 64,
                "height": 48,
            }],
        }
        snapshot = {
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
        try:
            with urlopen(Request(
                f"{endpoint}/frame-sets/anchor%3Aanchor-view",
                data=json.dumps(frame_set).encode(),
                method="PUT",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertEqual(json.load(response)["status"], "registered")

            with urlopen(Request(
                f"{endpoint}/object-selection-sessions",
                data=json.dumps({
                    "target": {"targetSplatId": "splat-1"},
                    "frameSetVersion": frame_set["frameSetVersion"],
                    "modelManifestDigest": model_manifest_digest,
                }).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                session_id = json.load(response)["sessionId"]

            preview_bindings = {
                "requestId": "request-1",
                "sessionId": session_id,
                "targetSplatId": "splat-1",
                "sceneId": snapshot["sceneId"],
                "sceneVersion": snapshot["sceneVersion"],
                "operation": "New",
                "correctionRound": 0,
                "deterministicSeed": "seed-1",
                "promptLogRevision": 1,
                "frameSetVersion": "anchor:anchor-view",
                "renderConfigVersion": snapshot["renderConfiguration"]["version"],
                "modelManifestDigest": model_manifest_digest,
            }
            preview = {
                **preview_bindings,
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
            with urlopen(Request(
                f"{endpoint}/object-selection-sessions/{session_id}/previews",
                data=json.dumps(preview).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                cache_miss = json.load(response)
            self.assertEqual(cache_miss, {
                "status": "sceneCacheMiss",
                **preview_bindings,
            })

            with urlopen(Request(
                f"{endpoint}/scene-snapshots/scene-1/snapshot-v1",
                data=json.dumps(snapshot).encode(),
                method="PUT",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertEqual(json.load(response)["status"], "registered")

            with urlopen(Request(
                f"{endpoint}/object-selection-sessions/{session_id}/previews",
                data=json.dumps(preview).encode(),
                method="POST",
                headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
            )) as response:
                result = json.load(response)
            self.assertEqual(result, {
                "status": "complete",
                **preview_bindings,
                "selectedIds": [3],
                "uncertainIds": [7],
                "rejectedIds": [9],
                "frameSet": frame_set,
                "maskSet": {
                    "status": "complete",
                    "requestId": "request-1",
                    "sessionId": session_id,
                    "promptLogRevision": 1,
                    "frameSetVersion": "anchor:anchor-view",
                    "modelManifestDigest": model_manifest_digest,
                    "threshold": 0.0,
                    "tracks": [{
                        "trackId": "primary",
                        "role": "include",
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
                },
                "evidenceSnapshot": {
                    **preview_bindings,
                    "frameSetId": "frames-1",
                    "policy": {
                        "id": "selection-evidence-policy/v1",
                        "renderConfigVersion": "effective-rgb-v1",
                        "contributorSemantics": "alpha-times-transmittance/v1",
                        "evidenceScale": "contributor-mass/v1",
                        "betaPrior": {"alpha": 1, "beta": 1},
                        "minimumEffectiveObservation": 0.1,
                        "selectedPosteriorThreshold": 0.8,
                        "rejectedPosteriorThreshold": 0.2,
                    },
                    "records": [
                        {
                            "stableId": 3,
                            "positiveEvidence": 3.0,
                            "negativeEvidence": 0.0,
                            "effectiveObservation": 3.0,
                            "posterior": 0.8,
                            "uncertaintyReason": None,
                            "classification": "selected",
                        },
                        {
                            "stableId": 7,
                            "positiveEvidence": 0.0,
                            "negativeEvidence": 0.0,
                            "effectiveObservation": 0.0,
                            "posterior": 0.5,
                            "uncertaintyReason": "unobserved",
                            "classification": "uncertain",
                        },
                        {
                            "stableId": 9,
                            "positiveEvidence": 0.0,
                            "negativeEvidence": 3.0,
                            "effectiveObservation": 3.0,
                            "posterior": 0.2,
                            "uncertaintyReason": None,
                            "classification": "rejected",
                        },
                    ],
                    "views": [
                        {
                            "viewId": "anchor-view",
                            "status": "accepted",
                            "rendererId": "gsplat",
                            "rgbFrameDigest": "sha256:anchor-frame-v1",
                            "supportBounds": {"x0": 0, "y0": 0, "x1": 11, "y1": 21},
                            "contributorCount": 2,
                            "anchorParity": "normal",
                            "negativeEvidenceAllowed": True,
                        }
                    ],
                },
                "coverageReport": {
                    "frameSetVersion": "anchor:anchor-view",
                    "renderConfigVersion": "effective-rgb-v1",
                    "attemptedViews": 1,
                    "acceptedViews": 1,
                    "rejectedViewCount": 0,
                    "status": "insufficient_coverage",
                },
            })

            with self.assertRaises(HTTPError) as error:
                urlopen(Request(
                    f"{endpoint}/object-selection-sessions/{session_id}/previews/request-1",
                    method="DELETE",
                    headers={"Origin": EDITOR_ORIGIN},
                ))
            self.assertEqual(error.exception.code, HTTPStatus.CONFLICT)
            self.assertEqual(json.load(error.exception), {
                "status": "maskSessionError",
                "code": "alreadyComplete",
                "message": "The Mask Set update already completed and cannot be cancelled.",
                "sessionId": session_id,
                "requestId": "request-1",
            })
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_rejects_private_network_http_for_the_trusted_lan_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_server(
                state=self.state,
                endpoint="http://192.168.1.20:8787",
                profile="trusted-lan",
                allowed_origins=[EDITOR_ORIGIN],
            )

    def test_requires_a_certificate_before_binding_a_trusted_lan_endpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "certificate"):
            create_server(
                state=self.state,
                endpoint="https://192.168.1.20:8787",
                profile="trusted-lan",
                allowed_origins=[EDITOR_ORIGIN],
            )

    def test_rejects_public_or_unspecified_trusted_lan_endpoints(self) -> None:
        for endpoint in ("https://8.8.8.8:8787", "https://0.0.0.0:8787"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "private-network"):
                    create_server(
                        state=self.state,
                        endpoint=endpoint,
                        profile="trusted-lan",
                        allowed_origins=[EDITOR_ORIGIN],
                        certificate=self.directory / "unused.pem",
                        private_key=self.directory / "unused-key.pem",
                    )


if __name__ == "__main__":
    unittest.main()

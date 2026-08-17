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
from selection_service_companion.masking import (
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    SAM31_RUNTIME_CONFIG_DIGEST,
    sam3_image_instance_capabilities,
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
        adapter_id: str = "sam3-image-instance/v1",
        model_name: str = "SAM 3 Image",
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
                    else SAM3_IMAGE_RUNTIME_CONFIG_DIGEST
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
        prompt_capabilities = sam3_image_instance_capabilities()
        self.assertEqual(capabilities["modelManifests"], [{
            "digest": model_digest,
            "adapterId": "sam3-image-instance/v1",
            "modelName": "SAM 3 Image",
            "weightsBundled": False,
            "promptCapabilities": prompt_capabilities,
        }])
        self.assertIn("aiSelectMaskProposals", capabilities["supportedOperations"])
        self.assertIn(
            "autoMaskProposalSetSchemaV3",
            capabilities["supportedOperations"],
        )
        self.assertEqual(
            capabilities["referenceCandidateReLift"]["runtimeBuildId"],
            "sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4",
        )
        self.assertEqual(capabilities["renderer"]["status"], "unavailable")

    def test_keeps_the_reference_point_adapter_out_of_production_capabilities(self) -> None:
        self.install_model(adapter_id="point-mask-v1", model_name="Point Mask v1")

        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["modelManifests"],
            [],
        )

    def test_candidate_re_lift_occupies_the_single_global_operation_slot(self) -> None:
        with self.state._session_lock:
            self.state._active_evidence_operation = "re-lift-1"
        try:
            self.assertEqual(
                self.state.capabilities([EDITOR_ORIGIN])["capacity"],
                {"maximumActiveSessions": 1, "activeSessions": 1},
            )
        finally:
            with self.state._session_lock:
                self.state._active_evidence_operation = None

    def test_rejects_a_sam31_manifest_with_an_unpinned_runtime_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtimeConfigDigest"):
            self.install_model(
                adapter_id="sam3.1",
                model_name="SAM 3.1",
                runtime_config_digest="sha256:runtime-v1",
            )

    def test_rejects_a_sam3_image_manifest_with_an_unpinned_runtime_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtimeConfigDigest"):
            self.install_model(runtime_config_digest="sha256:runtime-v1")

    def test_keeps_the_legacy_sam31_fixture_out_of_current_prompt_capabilities(self) -> None:
        self.install_model(adapter_id="sam3.1", model_name="SAM 3.1")

        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])["modelManifests"],
            [],
        )

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
        self.install_model()
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
                self.assertTrue(json.load(response)["companionInstanceId"])

            with urlopen(Request(
                f"{endpoint}/capabilities",
                headers={"Origin": EDITOR_ORIGIN},
            )) as response:
                runtime_profile = json.load(response)
                self.assertIn("activeModelManifest", runtime_profile)
                self.assertNotIn("modelManifests", runtime_profile)

            with urlopen(Request(
                f"{endpoint}/capabilities",
                method="OPTIONS",
                headers={"Origin": EDITOR_ORIGIN},
            )) as response:
                self.assertEqual(response.status, HTTPStatus.NO_CONTENT)
                self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, POST, PUT, DELETE, OPTIONS")
                self.assertEqual(
                    response.headers["Access-Control-Allow-Headers"],
                    "Content-Type, X-SceneSnapshot-Chunk-Digest, X-Spatial-Scene-Chunk-Digest",
                )

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

    def test_rejects_legacy_object_session_and_frame_set_routes(self) -> None:
        self.install_model()
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
            requests = (
                Request(
                    f"{endpoint}/object-selection-sessions",
                    data=b"{}",
                    method="POST",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/json",
                    },
                ),
                Request(
                    f"{endpoint}/frame-sets/legacy",
                    data=b"{}",
                    method="PUT",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/json",
                    },
                ),
            )
            for request in requests:
                with self.subTest(url=request.full_url):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request)
                    self.assertEqual(error.exception.code, HTTPStatus.NOT_FOUND)
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

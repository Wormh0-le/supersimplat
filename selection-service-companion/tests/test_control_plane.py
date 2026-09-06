from __future__ import annotations

import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState

EDITOR_ORIGIN = "https://editor.example"


class UnavailableSam3ImageInstanceAdapter:
    def runtime_profile_capability(
        self, model: dict[str, object]
    ) -> dict[str, object]:
        return {
            "status": "unavailable",
            "authoritativeRgb": {
                "artifact": True,
                "companionReference": True,
            },
            "promptCapabilities": {
                "positivePoints": True,
                "negativePoints": True,
                "positiveInstanceBox": True,
                "previousLogitsRefinement": True,
                "singlePointMultimask": False,
            },
            "message": "test adapter is unavailable",
        }


class CompanionControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.checkpoint = (
            self.directory
            / "models"
            / "facebook--sam3"
            / "snapshots"
            / "master"
            / "sam3.pt"
        )
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_bytes(b"modelscope cache fixture")
        self.state = CompanionState(
            self.directory / "state",
            model_cache_root=self.directory / "models",
        )
        self.state.mask_adapters["sam3-image-instance/v1"] = (  # type: ignore[assignment]
            UnavailableSam3ImageInstanceAdapter()
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_capabilities_do_not_expose_a_model_catalog(self) -> None:
        capabilities = self.state.capabilities([EDITOR_ORIGIN])

        self.assertEqual(capabilities["protocolVersion"], "1")
        self.assertEqual(capabilities["capacity"], {"maximumActiveSessions": 1, "activeSessions": 0})
        self.assertNotIn("modelManifests", capabilities)
        self.assertIn("aiSelectMaskProposals", capabilities["supportedOperations"])
        self.assertIn(
            "autoMaskProposalSetSchemaV3",
            capabilities["supportedOperations"],
        )
        self.assertEqual(
            capabilities["referenceCandidateReLift"]["runtimeBuildId"],
            DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
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

from __future__ import annotations

import hashlib
from http import HTTPStatus
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = "https://editor.example"


class CompanionControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / "state")
        self.state.install_release("0.1.0", "sha256:locked-release")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def install_model(self) -> str:
        weights = self.directory / "sam31.pt"
        weights.write_bytes(b"separately acquired model weights")
        digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / "sam31.json"
        manifest.write_text(
            """{
  "digest": "sha256:model-v1",
  "adapterId": "sam3.1",
  "modelName": "SAM 3.1",
  "checkpointDigest": "sha256:%s",
  "sourceCommit": "abc123",
  "licenseName": "SAM License",
  "licenseUrl": "https://example.test/license",
  "runtimeConfigDigest": "sha256:runtime-v1"
}
""" % digest,
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
                self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET, OPTIONS")
                self.assertEqual(response.headers["Access-Control-Allow-Headers"], "Content-Type")

            with self.assertRaises(HTTPError) as error:
                urlopen(Request(f"{endpoint}/capabilities", headers={"Origin": "https://untrusted.example"}))
            self.assertEqual(error.exception.code, HTTPStatus.FORBIDDEN)
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
                endpoint="https://selection.lan:8787",
                profile="trusted-lan",
                allowed_origins=[EDITOR_ORIGIN],
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from selection_service_companion.masking import (
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    SAM31_RUNTIME_CONFIG_DIGEST,
    sam3_image_instance_capabilities,
)
from selection_service_companion.state import (
    AI_SELECT_READINESS_PROTOCOL_VERSION,
    AI_SELECT_RUNTIME_PROFILE_ID,
    CompanionState,
)


EDITOR_ORIGIN = "https://editor.example"


class ReadySam3ImageInstanceAdapter:
    def runtime_profile_capability(
        self, model: dict[str, object]
    ) -> dict[str, object]:
        capabilities = sam3_image_instance_capabilities()
        return {
            "status": "ready",
            "authoritativeRgb": {
                "artifact": True,
                "companionReference": True,
            },
            "promptCapabilities": {
                "positivePoints": True,
                "negativePoints": True,
                "positiveInstanceBox": True,
                "previousLogitsRefinement": True,
                "singlePointMultimask": True,
                "negativeBox": False,
                "promptBrush": False,
                "maskConstraints": False,
                "text": False,
            },
            "compilerPolicyVersion": capabilities["compilerPolicyVersion"],
            "adapterCapabilityDigest": capabilities["capabilityDigest"],
        }


class RuntimeProfileReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.lock_file = self.directory / "uv.lock"
        self.lock_file.write_text("locked", encoding="utf-8")
        self.state = CompanionState(self.directory)
        self.state.install_release("test", self.lock_file)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def install_model(
        self,
        digest: str,
        *,
        adapter_id: str = "sam3.1",
        runtime_config_digest: str = SAM31_RUNTIME_CONFIG_DIGEST,
    ) -> dict[str, object]:
        weights = self.directory / f"{digest.replace(':', '-')}.pt"
        weights.write_bytes(digest.encode("utf-8"))
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / f"{digest.replace(':', '-')}.json"
        manifest.write_text(
            json.dumps(
                {
                    "digest": digest,
                    "adapterId": adapter_id,
                    "modelName": f"Historical {digest}",
                    "checkpointDigest": f"sha256:{checkpoint_digest}",
                    "sourceCommit": "historical-source",
                    "licenseName": "test",
                    "licenseUrl": "https://example.invalid/license",
                    "runtimeConfigDigest": runtime_config_digest,
                }
            ),
            encoding="utf-8",
        )
        return self.state.install_model(manifest, weights)

    def test_lightweight_health_has_one_process_identity_and_reuses_release_validation(
        self,
    ) -> None:
        first = self.state.health()
        replacement = CompanionState(self.directory).health()
        self.lock_file.write_text("changed after process validation", encoding="utf-8")
        second = self.state.health()

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["companionInstanceId"])
        self.assertNotEqual(
            first["companionInstanceId"],
            replacement["companionInstanceId"],
        )

    def test_zero_installed_manifests_cannot_resolve_an_active_model(self) -> None:
        with self.assertRaisesRegex(ValueError, "no compatible installed"):
            self.state.runtime_profile_capabilities([EDITOR_ORIGIN])

    def test_exactly_one_manifest_resolves_automatically_and_crosses_singularly(
        self,
    ) -> None:
        installed = self.install_model("sha256:historical-one")

        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])

        self.assertEqual(
            result["runtimeProfileId"],
            AI_SELECT_RUNTIME_PROFILE_ID,
        )
        self.assertEqual(
            result["protocolVersion"],
            AI_SELECT_READINESS_PROTOCOL_VERSION,
        )
        self.assertEqual(
            result["activeModelManifest"]["digest"],
            installed["digest"],
        )
        self.assertNotIn("modelManifests", result)
        self.assertFalse(result["activeModelManifest"]["initialized"])
        self.assertEqual(
            result["imageInstanceProvider"]["status"],
            "unavailable",
        )

    def test_multiple_manifests_require_an_explicit_operator_choice(self) -> None:
        self.install_model("sha256:historical-one")
        selected = self.install_model("sha256:historical-two")

        with self.assertRaisesRegex(ValueError, "operator must choose"):
            self.state.runtime_profile_capabilities([EDITOR_ORIGIN])

        self.state.configure_active_model_manifest(selected["digest"])
        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        self.assertEqual(
            result["activeModelManifest"]["digest"],
            selected["digest"],
        )

    def test_historical_provider_does_not_advertise_removed_prompts_as_current(
        self,
    ) -> None:
        self.install_model("sha256:historical-one")

        provider = self.state.runtime_profile_capabilities(
            [EDITOR_ORIGIN]
        )["imageInstanceProvider"]

        self.assertTrue(provider["authoritativeRgb"]["artifact"])
        self.assertFalse(provider["authoritativeRgb"]["companionReference"])
        self.assertFalse(
            provider["promptCapabilities"]["previousLogitsRefinement"]
        )
        self.assertFalse(provider["promptCapabilities"]["negativeBox"])
        self.assertFalse(provider["promptCapabilities"]["promptBrush"])
        self.assertFalse(provider["promptCapabilities"]["maskConstraints"])
        self.assertFalse(provider["promptCapabilities"]["text"])

    def test_current_adapter_capability_advertises_rgb_and_opaque_refinement(
        self,
    ) -> None:
        adapter_id = "sam3-image-instance/v1"
        self.state.mask_adapters[adapter_id] = ReadySam3ImageInstanceAdapter()  # type: ignore[assignment]
        self.install_model(
            "sha256:sam3-image-instance",
            adapter_id=adapter_id,
            runtime_config_digest=SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
        )

        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        provider = result["imageInstanceProvider"]

        self.assertTrue(result["activeModelManifest"]["initialized"])
        self.assertEqual(provider["status"], "ready")
        self.assertTrue(provider["authoritativeRgb"]["artifact"])
        self.assertTrue(provider["authoritativeRgb"]["companionReference"])
        self.assertTrue(
            provider["promptCapabilities"]["previousLogitsRefinement"]
        )
        self.assertTrue(provider["promptCapabilities"]["singlePointMultimask"])
        expected = sam3_image_instance_capabilities()
        self.assertEqual(
            provider["compilerPolicyVersion"],
            expected["compilerPolicyVersion"],
        )
        self.assertEqual(
            provider["adapterCapabilityDigest"],
            expected["capabilityDigest"],
        )

    def test_unavailable_current_adapter_omits_the_pass_through_digests(
        self,
    ) -> None:
        adapter_id = "sam3-image-instance/v1"
        # The real adapter reports unavailable when the checkpoint cannot be
        # initialized in this environment; readiness must stay truthful and
        # must not advertise capability digests for a non-ready provider.
        self.install_model(
            "sha256:sam3-image-instance",
            adapter_id=adapter_id,
            runtime_config_digest=SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
        )

        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        provider = result["imageInstanceProvider"]

        self.assertEqual(provider["status"], "unavailable")
        self.assertFalse(result["activeModelManifest"]["initialized"])
        self.assertNotIn("compilerPolicyVersion", provider)
        self.assertNotIn("adapterCapabilityDigest", provider)
        self.assertTrue(provider["promptCapabilities"]["positivePoints"])


if __name__ == "__main__":
    unittest.main()

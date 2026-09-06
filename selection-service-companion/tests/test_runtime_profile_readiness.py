from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import selection_service_companion.state as state_module
from selection_service_companion.direct_gaussian_evidence import (
    direct_evidence_capability,
)
from selection_service_companion.image_instance_prompt_synthesis import (
    prompt_synthesis_policy_digest,
)
from selection_service_companion.lift_readiness import (
    default_lift_readiness_policy,
)
from selection_service_companion.masking import (
    sam3_image_instance_capabilities,
)
from selection_service_companion.state import (
    AI_SELECT_READINESS_PROTOCOL_VERSION,
    AI_SELECT_RUNTIME_PROFILE_ID,
    CompanionState,
)
from selection_service_companion.target_geometry import (
    local_key_view_policy_digest,
    target_geometry_policy_digest,
)
from selection_service_companion.view_assessment import (
    view_assessment_policy_digest,
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
                "singlePointMultimask": False,
            },
            "compilerPolicyVersion": capabilities["compilerPolicyVersion"],
            "adapterCapabilityDigest": capabilities["capabilityDigest"],
        }


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


class RuntimeProfileReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
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
            self.directory,
            model_cache_root=self.directory / "models",
        )
        self.state.mask_adapters["sam3-image-instance/v1"] = (  # type: ignore[assignment]
            UnavailableSam3ImageInstanceAdapter()
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lightweight_health_has_one_process_identity(
        self,
    ) -> None:
        first = self.state.health()
        replacement = CompanionState(self.directory).health()
        second = self.state.health()

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["companionInstanceId"])
        self.assertNotEqual(
            first["companionInstanceId"],
            replacement["companionInstanceId"],
        )

    def test_missing_modelscope_checkpoint_cannot_resolve_the_current_model(self) -> None:
        self.checkpoint.unlink()
        with self.assertRaisesRegex(ValueError, "not present in the ModelScope cache"):
            self.state.runtime_profile_capabilities([EDITOR_ORIGIN])

    def test_modelscope_cache_resolves_the_fixed_current_model(
        self,
    ) -> None:
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
            "operator-sam3-image-instance-v1",
        )
        self.assertNotIn("modelManifests", result)
        self.assertFalse(result["activeModelManifest"]["initialized"])
        self.assertEqual(
            result["imageInstanceProvider"]["status"],
            "unavailable",
        )

    def test_internal_cwed_qualification_does_not_enter_browser_runtime_profile(
        self,
    ) -> None:
        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        serialized = json.dumps(result, sort_keys=True).lower()

        for forbidden in ("cwed", "depthmoment", "depth_moment"):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn(
            "aiSelectDepthMoments",
            result["supportedOperations"],
        )

    def test_current_adapter_capability_advertises_rgb_and_opaque_refinement(
        self,
    ) -> None:
        adapter_id = "sam3-image-instance/v1"
        self.state.mask_adapters[adapter_id] = ReadySam3ImageInstanceAdapter()  # type: ignore[assignment]

        direct = direct_evidence_capability()
        direct["status"] = "ready"
        renderer = {
            "id": "gsplat",
            "status": "ready",
            "rgbRendererVersion": "gsplat-direct-evidence-rgb/v1",
            "rasterImplementationId": direct["rasterImplementationId"],
            "runtimeBuildId": direct["runtimeBuildId"],
        }
        with (
            patch.object(
                state_module,
                "direct_evidence_capability",
                return_value=direct,
            ),
            patch.object(self.state, "_renderer_capability", return_value=renderer),
        ):
            result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        provider = result["imageInstanceProvider"]

        self.assertTrue(result["activeModelManifest"]["initialized"])
        self.assertEqual(provider["status"], "ready")
        self.assertTrue(provider["authoritativeRgb"]["artifact"])
        self.assertTrue(provider["authoritativeRgb"]["companionReference"])
        self.assertTrue(
            provider["promptCapabilities"]["previousLogitsRefinement"]
        )
        self.assertFalse(provider["promptCapabilities"]["singlePointMultimask"])
        expected = sam3_image_instance_capabilities()
        self.assertEqual(
            provider["compilerPolicyVersion"],
            expected["compilerPolicyVersion"],
        )
        self.assertEqual(
            provider["adapterCapabilityDigest"],
            expected["capabilityDigest"],
        )
        production = result["productionIdentity"]
        self.assertEqual(production["status"], "ready")
        record = production["record"]
        self.assertEqual(record["schemaVersion"], 1)
        self.assertEqual(
            record["model"]["adapterId"], "sam3-image-instance/v1"
        )
        self.assertEqual(
            record["prompt"]["compilerPolicyVersion"],
            expected["compilerPolicyVersion"],
        )
        self.assertEqual(
            record["prompt"]["synthesisPolicyDigest"],
            prompt_synthesis_policy_digest(),
        )
        self.assertEqual(
            record["geometry"]["targetGeometryPolicyDigest"],
            target_geometry_policy_digest(),
        )
        self.assertEqual(
            record["geometry"]["localViewPolicyDigest"],
            local_key_view_policy_digest(),
        )
        self.assertEqual(
            record["maskReview"]["policyDigest"],
            view_assessment_policy_digest(),
        )
        self.assertEqual(
            record["evidence"]["evidenceBackendKind"],
            "production-direct",
        )
        self.assertEqual(
            record["liftReadiness"]["policyId"],
            "lift-readiness/production-v1",
        )
        self.assertEqual(
            record["liftReadiness"]["policyDigest"],
            default_lift_readiness_policy()["readinessPolicyDigest"],
        )
        self.assertRegex(record["identityDigest"], r"^sha256:[a-f0-9]{64}$")

    def test_unavailable_current_adapter_omits_the_pass_through_digests(
        self,
    ) -> None:
        # The real adapter reports unavailable when the checkpoint cannot be
        # initialized in this environment; readiness must stay truthful and
        # must not advertise capability digests for a non-ready provider.
        result = self.state.runtime_profile_capabilities([EDITOR_ORIGIN])
        provider = result["imageInstanceProvider"]

        self.assertEqual(provider["status"], "unavailable")
        self.assertFalse(result["activeModelManifest"]["initialized"])
        self.assertNotIn("compilerPolicyVersion", provider)
        self.assertNotIn("adapterCapabilityDigest", provider)
        self.assertTrue(provider["promptCapabilities"]["positivePoints"])


if __name__ == "__main__":
    unittest.main()

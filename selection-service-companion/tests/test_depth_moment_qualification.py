from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from selection_service_companion.depth_moment_qualification import (
    QUALIFIED_DEPTH_MOMENT_POLICY_ID,
    load_internal_depth_moment_capability,
    validate_depth_moment_qualification_record,
)
from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_BUILD_FLAGS,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
)
def digest(character: str) -> str:
    return "sha256:" + (character * 64)


def qualification_record() -> dict[str, object]:
    record: dict[str, object] = {
        "schemaId": "depth-moment-cwed-qualification/run-v1",
        "qualificationId": "depth-moment-cwed-foundation/qualified-v1",
        "issue": 53,
        "status": "qualified",
        "recordedAt": "2026-08-25T00:00:00Z",
        "runtime": {
            "operatingSystem": "Linux",
            "driverVersion": "580.178.04",
            "gpuName": "NVIDIA GeForce RTX 4090 D",
            "computeCapability": "8.9",
        },
        "directEvidence": {
            "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
            "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
            "buildFlags": list(DIRECT_EVIDENCE_BUILD_FLAGS),
            "supportedComputeCapabilities": ["8.9"],
        },
        "momentPolicy": {
            "policyId": QUALIFIED_DEPTH_MOMENT_POLICY_ID,
            "minimumM0": 1.0 / 255.0,
            "selectionRule": "same-decision-minimum-accepted-alpha/v1",
            "readout": "M0/M1/M2-float32-cwed-variance/v1",
        },
        "supportedEnvelope": {
            "computeCapabilities": ["8.9"],
            "maxWidth": 1008,
            "maxHeight": 1008,
            "maxPixels": 1008 * 1008,
            "maxRenderGaussianCount": 16384,
            "maxEvidenceGaussianCount": 16384,
            "maxIntersectionCount": 262144,
            "maxConcurrentConsumers": 1,
        },
        "fixtures": [
            {
                "fixtureId": "controlled-overlap-anchor-1008/v1",
                "scenePath": (
                    "selection-service-companion/tests/fixtures/ai-select-v1/"
                    "controlled-overlap/controlled_front_back_overlap.ply"
                ),
                "sceneSha256": (
                    "sha256:cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8"
                    "f2177964ad36aa6e"
                ),
                "cameraManifest": {
                    "model": "pinhole",
                    "convention": "opencv-world-to-camera",
                },
                "cameraBindingDigest": digest("a"),
                "resolution": [1008, 1008],
                "renderWorkingSetToken": digest("b"),
                "evidenceWorkingSetToken": digest("c"),
                "renderGaussianCount": 16384,
                "evidenceGaussianCount": 16384,
                "projectedGaussianCount": 16384,
                "intersectionCount": 200000,
            }
        ],
        "measurements": {
            "warmupCount": 2,
            "sampleCount": 7,
            "latencyMs": {
                name: {"median": 1.0, "p95": 1.5, "maximum": 2.0}
                for name in (
                    "withoutMoments",
                    "withMoments",
                    "readoutConstruction",
                    "cacheHitValidation",
                    "recomputation",
                    "downstreamConsumer",
                )
            },
            "transferAndHash": {
                "synchronizeOnlyMs": 0.1,
                "gpuToCpuMs": 1.0,
                "sha256Ms": 1.0,
                "bytes": 1008 * 1008 * 13,
                "synchronizationIncluded": True,
            },
            "comparison": {
                "cacheHitToRecomputationRatio": 0.01,
                "cacheHitToReadoutConstructionRatio": 0.5,
                "cacheHitToDownstreamConsumerRatio": 2.0,
            },
            "memory": {
                "withoutMomentsPeakVramBytes": 1,
                "withMomentsPeakVramBytes": 2,
                "readoutPeakVramBytes": 3,
                "cacheValidationPeakVramBytes": 3,
                "momentBufferBytes": 1008 * 1008 * 3 * 4,
                "ownedTensorBufferBytes": 1008 * 1008 * 13,
                "transientHostBytes": 1008 * 1008 * 13,
                "transientDeviceBytes": 1008 * 1008 * 13,
            },
        },
        "semanticParity": {
            "status": "passed",
            "mandatoryCases": [
                "zero-mass",
                "one-layer",
                "two-layer",
                "rejected-and-terminated",
            ],
            "rtol": 1.0e-6,
            "atol": 1.0e-6,
            "maximumMomentAbsoluteError": 0.0,
            "productionEvidenceAtol": 2.0e-5,
            "maximumProductionEvidenceAbsoluteError": 1.0e-6,
            "withoutMomentsOutputDigest": digest("e"),
            "withMomentsProductionOutputDigest": digest("1"),
            "depthMomentTensorDigest": digest("f"),
            "authoritativeRgbUnchanged": True,
            "evidenceUnchanged": True,
            "boundaryBehaviorUnchanged": True,
        },
        "failureOutcomes": {
            name: {
                "passed": True,
                "method": "fault-injection" if name != "supportedFixtureOom" else "measured",
                "result": "unavailable-no-partial-readout",
            }
            for name in (
                "sourceMismatch",
                "runtimeMismatch",
                "capabilityMismatch",
                "allocationFailure",
                "cancellation",
                "supportedFixtureOom",
            )
        },
        "compilerDiagnostics": {
            "tool": "cuobjdump --dump-resource-usage",
            "arch": "sm_89",
            "directEvidenceKernelRegisters": 36,
            "projectedDepthProbeKernelRegisters": 10,
            "stackBytes": 0,
            "sharedBytes": 0,
            "localBytes": 0,
            "rawOutputSha256": digest("d"),
        },
        "promotionGate": {
            "passed": True,
            "checks": [
                "semantic-parity",
                "identity-fail-closed",
                "no-supported-fixture-oom",
                "failure-atomicity",
                "checked-measurements",
            ],
        },
    }
    for name in ("allocationFailure", "cancellation"):
        outcome = record["failureOutcomes"][name]
        outcome.update({
            "priorReadoutPreserved": True,
            "productionArtifactsPreserved": True,
            "productionOutputDigestBefore": digest("8"),
            "productionOutputDigestAfter": digest("8"),
        })
    record["recordDigest"] = canonical_json_digest(record)
    return record


class DepthMomentQualificationRecordTests(unittest.TestCase):
    def test_validated_record_binds_policy_identity_and_execution_envelope(self) -> None:
        capability = validate_depth_moment_qualification_record(
            qualification_record()
        )

        self.assertEqual(capability.status, "ready")
        self.assertEqual(capability.policy.policy_id, QUALIFIED_DEPTH_MOMENT_POLICY_ID)
        self.assertAlmostEqual(capability.policy.minimum_m0, 1.0 / 255.0)
        self.assertTrue(
            capability.supports_execution(
                width=1008,
                height=1008,
                render_gaussian_count=16384,
                evidence_gaussian_count=16384,
                intersection_count=262144,
            )
        )
        self.assertFalse(
            capability.supports_execution(
                width=1009,
                height=1008,
                render_gaussian_count=16384,
                evidence_gaussian_count=16384,
                intersection_count=262144,
            )
        )

    def test_record_rejects_identity_gate_and_atomicity_mismatches(self) -> None:
        mutations = {
            "source": lambda record: record["directEvidence"].__setitem__(
                "sourceRevision", digest("0")
            ),
            "runtime": lambda record: record["directEvidence"].__setitem__(
                "runtimeBuildId", digest("0")
            ),
            "allocation": lambda record: record["failureOutcomes"][
                "allocationFailure"
            ].__setitem__("passed", False),
            "promotion": lambda record: record["promotionGate"].__setitem__(
                "passed", False
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                stale = deepcopy(qualification_record())
                mutate(stale)
                del stale["recordDigest"]
                stale["recordDigest"] = canonical_json_digest(stale)
                with self.assertRaises(ValueError):
                    validate_depth_moment_qualification_record(stale)

    def test_runtime_loader_rejects_unqualified_gpu_and_driver_facts(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "qualification.json"
            record = qualification_record()
            path.write_text(json.dumps(record), encoding="utf-8")
            direct = {
                "status": "ready",
                "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
                "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
                "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
                "detectedComputeCapability": "8.9",
            }
            for field, value in (
                ("gpuName", "Another 8.9 GPU"),
                ("driverVersion", "999.0"),
            ):
                with self.subTest(field=field):
                    runtime_facts = {**record["runtime"], "status": "ready"}
                    runtime_facts[field] = value
                    with (
                        patch(
                            "selection_service_companion.depth_moment_qualification.current_depth_moment_runtime_facts",
                            return_value=runtime_facts,
                        ),
                        patch(
                            "selection_service_companion.depth_moment_qualification.direct_evidence_capability",
                            return_value=direct,
                        ),
                    ):
                        capability = load_internal_depth_moment_capability(path)
                    self.assertEqual(capability.status, "unavailable")
                    self.assertEqual(
                        capability.reason,
                        "runtime-facts-not-qualified",
                    )

    def test_runtime_loader_fails_closed_outside_the_qualified_gpu_identity(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "qualification.json"
            path.write_text(
                json.dumps(qualification_record()),
                encoding="utf-8",
            )
            runtime = {
                "status": "ready",
                "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
                "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
                "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
                "detectedComputeCapability": "9.0",
            }
            record = qualification_record()
            with (
                patch(
                    "selection_service_companion.depth_moment_qualification.current_depth_moment_runtime_facts",
                    return_value={**record["runtime"], "status": "ready"},
                ),
                patch(
                    "selection_service_companion.depth_moment_qualification.direct_evidence_capability",
                    return_value=runtime,
                ),
            ):
                capability = load_internal_depth_moment_capability(path)

        self.assertEqual(capability.status, "unavailable")
        self.assertEqual(capability.reason, "compute-capability-not-qualified")
        self.assertFalse(
            capability.supports_execution(
                width=1,
                height=1,
                render_gaussian_count=1,
                evidence_gaussian_count=1,
                intersection_count=1,
            )
        )


if __name__ == "__main__":
    unittest.main()

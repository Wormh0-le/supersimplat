"""Version-bound locked-GPU qualification for internal CWED readouts.

The record in this module's package is an internal capability input, not a
Browser Runtime Profile capability.  A consumer may opt into depth moments only
when the checked record exactly matches the current Direct Evidence identity and
its execution falls inside the measured envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Final, Literal, Mapping, Sequence

from .depth_moments import DepthMomentValidityPolicy
from .digests import canonical_json_digest
from .direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_BUILD_FLAGS,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
    DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES,
    direct_evidence_capability,
)
from .renderer_runtime import (
    CurrentProcessGsplatInspection,
    GsplatRuntime,
    StaticGsplatRuntimeInspection,
    EXPECTED_CUDA_VERSION,
    EXPECTED_GSPLAT_SOURCE_COMMIT,
    EXPECTED_GSPLAT_VERSION,
    EXPECTED_OPERATING_SYSTEM,
    EXPECTED_PYTHON_VERSION,
    EXPECTED_RENDERER_LOCK_DIGEST,
    EXPECTED_TORCH_VERSION,
)


DEPTH_MOMENT_QUALIFICATION_SCHEMA_ID: Final = (
    "depth-moment-cwed-qualification/run-v1"
)
QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID: Final = (
    "depth-moment-cwed-foundation/qualified-v1"
)
QUALIFIED_DEPTH_MOMENT_POLICY_ID: Final = (
    "depth-moment-minimum-m0/qualified-v1"
)
QUALIFIED_DEPTH_MOMENT_MINIMUM_M0: Final = 1.0 / 255.0
DEFAULT_DEPTH_MOMENT_QUALIFICATION_PATH: Final = (
    Path(__file__).with_name("qualifications")
    / "depth-moment-cwed-foundation-cc89-v1.json"
)

_TOP_LEVEL_KEYS: Final = {
    "schemaId",
    "qualificationId",
    "issue",
    "status",
    "recordedAt",
    "runtime",
    "directEvidence",
    "momentPolicy",
    "supportedEnvelope",
    "fixtures",
    "measurements",
    "semanticParity",
    "failureOutcomes",
    "compilerDiagnostics",
    "promotionGate",
    "recordDigest",
}
_RUNTIME_KEYS: Final = {
    "operatingSystem",
    "pythonVersion",
    "torchVersion",
    "cudaVersion",
    "driverVersion",
    "gpuName",
    "computeCapability",
    "gsplatVersion",
    "gsplatSourceCommit",
    "rendererLockDigest",
    "uvLockSha256",
}
_DIRECT_EVIDENCE_KEYS: Final = {
    "abiVersion",
    "sourceRevision",
    "runtimeBuildId",
    "rasterImplementationId",
    "evidenceBackendId",
    "buildFlags",
    "supportedComputeCapabilities",
}
_POLICY_KEYS: Final = {
    "policyId",
    "minimumM0",
    "selectionRule",
    "readout",
}
_ENVELOPE_KEYS: Final = {
    "computeCapabilities",
    "maxWidth",
    "maxHeight",
    "maxPixels",
    "maxRenderGaussianCount",
    "maxEvidenceGaussianCount",
    "maxIntersectionCount",
    "maxConcurrentConsumers",
}
_FIXTURE_KEYS: Final = {
    "fixtureId",
    "scenePath",
    "sceneSha256",
    "cameraManifest",
    "cameraBindingDigest",
    "resolution",
    "renderWorkingSetToken",
    "evidenceWorkingSetToken",
    "renderGaussianCount",
    "evidenceGaussianCount",
    "projectedGaussianCount",
    "intersectionCount",
}
_DISTRIBUTION_KEYS: Final = {"median", "p95", "maximum"}
_LATENCY_KEYS: Final = {
    "withoutMoments",
    "withMoments",
    "readoutConstruction",
    "cacheHitValidation",
    "recomputation",
    "downstreamConsumer",
}
_FAILURE_KEYS: Final = {
    "sourceMismatch",
    "runtimeMismatch",
    "capabilityMismatch",
    "allocationFailure",
    "cancellation",
    "supportedFixtureOom",
}
_REQUIRED_PARITY_CASES: Final = {
    "zero-mass",
    "one-layer",
    "two-layer",
    "rejected-and-terminated",
}
_DIGEST_PREFIX: Final = "sha256:"


class DepthMomentQualificationError(ValueError):
    """A checked CWED qualification record is incomplete or incompatible."""


@dataclass(frozen=True)
class DepthMomentExecutionEnvelope:
    compute_capabilities: tuple[str, ...]
    max_width: int
    max_height: int
    max_pixels: int
    max_render_gaussian_count: int
    max_evidence_gaussian_count: int
    max_intersection_count: int
    max_concurrent_consumers: int

    def as_dict(self) -> dict[str, object]:
        return {
            "computeCapabilities": list(self.compute_capabilities),
            "maxWidth": self.max_width,
            "maxHeight": self.max_height,
            "maxPixels": self.max_pixels,
            "maxRenderGaussianCount": self.max_render_gaussian_count,
            "maxEvidenceGaussianCount": self.max_evidence_gaussian_count,
            "maxIntersectionCount": self.max_intersection_count,
            "maxConcurrentConsumers": self.max_concurrent_consumers,
        }

    def supports(
        self,
        *,
        width: int,
        height: int,
        render_gaussian_count: int,
        evidence_gaussian_count: int,
        intersection_count: int | None = None,
    ) -> bool:
        values = (
            width,
            height,
            render_gaussian_count,
            evidence_gaussian_count,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            return False
        if width <= 0 or height <= 0:
            return False
        if render_gaussian_count <= 0 or evidence_gaussian_count <= 0:
            return False
        if (
            width > self.max_width
            or height > self.max_height
            or width * height > self.max_pixels
            or render_gaussian_count > self.max_render_gaussian_count
            or evidence_gaussian_count > self.max_evidence_gaussian_count
        ):
            return False
        if intersection_count is not None:
            if (
                isinstance(intersection_count, bool)
                or not isinstance(intersection_count, int)
                or intersection_count < 0
                or intersection_count > self.max_intersection_count
            ):
                return False
        return True


DepthMomentCapabilityStatus = Literal["ready", "unavailable"]


@dataclass(frozen=True)
class DepthMomentInternalCapability:
    """Companion-only readiness for one exact qualified CWED foundation."""

    status: DepthMomentCapabilityStatus
    reason: str
    qualification_id: str
    qualification_digest: str
    policy: DepthMomentValidityPolicy | None
    envelope: DepthMomentExecutionEnvelope | None
    direct_evidence_abi_version: str
    direct_evidence_source_revision: str
    direct_evidence_runtime_build_id: str

    def supports_execution(
        self,
        *,
        width: int,
        height: int,
        render_gaussian_count: int,
        evidence_gaussian_count: int,
        intersection_count: int | None = None,
    ) -> bool:
        return (
            self.status == "ready"
            and self.envelope is not None
            and self.envelope.supports(
                width=width,
                height=height,
                render_gaussian_count=render_gaussian_count,
                evidence_gaussian_count=evidence_gaussian_count,
                intersection_count=intersection_count,
            )
        )

    @classmethod
    def unavailable(cls, reason: str) -> "DepthMomentInternalCapability":
        return cls(
            status="unavailable",
            reason=reason,
            qualification_id=QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
            qualification_digest="",
            policy=None,
            envelope=None,
            direct_evidence_abi_version=DIRECT_EVIDENCE_ABI_VERSION,
            direct_evidence_source_revision=DIRECT_EVIDENCE_SOURCE_REVISION,
            direct_evidence_runtime_build_id=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DepthMomentQualificationError(f"{name} must be an object.")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    name: str,
) -> Mapping[str, object]:
    result = _mapping(value, name)
    if set(result) != expected:
        raise DepthMomentQualificationError(f"{name} keys are incomplete or stale.")
    return result


def _non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DepthMomentQualificationError(f"{name} must be a non-empty string.")
    return value


def _digest(value: object, name: str) -> str:
    result = _non_empty(value, name)
    if (
        len(result) != len(_DIGEST_PREFIX) + 64
        or not result.startswith(_DIGEST_PREFIX)
        or any(character not in "0123456789abcdef" for character in result[7:])
    ):
        raise DepthMomentQualificationError(
            f"{name} must be a canonical SHA-256 digest."
        )
    return result


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DepthMomentQualificationError(f"{name} must be a positive integer.")
    return value


def _nonnegative_number(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise DepthMomentQualificationError(
            f"{name} must be a finite non-negative number."
        )
    return float(value)


def _string_sequence(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DepthMomentQualificationError(f"{name} must be a string sequence.")
    result = tuple(_non_empty(item, name) for item in value)
    if not result or len(set(result)) != len(result):
        raise DepthMomentQualificationError(
            f"{name} must be non-empty and contain unique values."
        )
    return result


def _validate_runtime(value: object) -> tuple[Mapping[str, object], str]:
    runtime = _exact_keys(value, _RUNTIME_KEYS, "runtime")
    expected = {
        "operatingSystem": EXPECTED_OPERATING_SYSTEM,
        "pythonVersion": EXPECTED_PYTHON_VERSION,
        "torchVersion": EXPECTED_TORCH_VERSION,
        "cudaVersion": EXPECTED_CUDA_VERSION,
        "gsplatVersion": EXPECTED_GSPLAT_VERSION,
        "gsplatSourceCommit": EXPECTED_GSPLAT_SOURCE_COMMIT,
        "rendererLockDigest": EXPECTED_RENDERER_LOCK_DIGEST,
        "uvLockSha256": EXPECTED_RENDERER_LOCK_DIGEST,
    }
    for key, expected_value in expected.items():
        if runtime.get(key) != expected_value:
            raise DepthMomentQualificationError(
                f"runtime {key} does not match the locked Companion identity."
            )
    _non_empty(runtime.get("driverVersion"), "runtime driverVersion")
    _non_empty(runtime.get("gpuName"), "runtime gpuName")
    compute_capability = _non_empty(
        runtime.get("computeCapability"), "runtime computeCapability"
    )
    return runtime, compute_capability


def _validate_direct_evidence(value: object) -> tuple[str, ...]:
    direct = _exact_keys(value, _DIRECT_EVIDENCE_KEYS, "directEvidence")
    expected = {
        "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
        "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
    }
    for key, expected_value in expected.items():
        if direct.get(key) != expected_value:
            raise DepthMomentQualificationError(
                f"directEvidence {key} does not match the checked implementation."
            )
    if tuple(direct.get("buildFlags", ())) != DIRECT_EVIDENCE_BUILD_FLAGS:
        raise DepthMomentQualificationError(
            "directEvidence buildFlags do not match the checked implementation."
        )
    supported = _string_sequence(
        direct.get("supportedComputeCapabilities"),
        "directEvidence supportedComputeCapabilities",
    )
    expected_supported = tuple(
        f"{major}.{minor}"
        for major, minor in DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES
    )
    if supported != expected_supported:
        raise DepthMomentQualificationError(
            "The qualification must cover every advertised compute capability."
        )
    return supported


def _validate_policy(value: object) -> DepthMomentValidityPolicy:
    policy = _exact_keys(value, _POLICY_KEYS, "momentPolicy")
    if policy.get("policyId") != QUALIFIED_DEPTH_MOMENT_POLICY_ID:
        raise DepthMomentQualificationError("momentPolicy identity is not qualified.")
    minimum_m0 = _nonnegative_number(policy.get("minimumM0"), "minimumM0")
    if minimum_m0 != QUALIFIED_DEPTH_MOMENT_MINIMUM_M0:
        raise DepthMomentQualificationError(
            "momentPolicy minimumM0 does not match the frozen selection rule."
        )
    if policy.get("selectionRule") != "same-decision-minimum-accepted-alpha/v1":
        raise DepthMomentQualificationError("momentPolicy selection rule is stale.")
    if policy.get("readout") != "M0/M1/M2-float32-cwed-variance/v1":
        raise DepthMomentQualificationError("momentPolicy readout identity is stale.")
    return DepthMomentValidityPolicy(
        policy_id=QUALIFIED_DEPTH_MOMENT_POLICY_ID,
        minimum_m0=minimum_m0,
    )


def _validate_envelope(
    value: object,
    *,
    supported_compute_capabilities: tuple[str, ...],
    runtime_compute_capability: str,
) -> DepthMomentExecutionEnvelope:
    envelope = _exact_keys(value, _ENVELOPE_KEYS, "supportedEnvelope")
    compute_capabilities = _string_sequence(
        envelope.get("computeCapabilities"),
        "supportedEnvelope computeCapabilities",
    )
    if (
        compute_capabilities != supported_compute_capabilities
        or runtime_compute_capability not in compute_capabilities
    ):
        raise DepthMomentQualificationError(
            "supportedEnvelope does not cover the advertised locked GPU runtime."
        )
    result = DepthMomentExecutionEnvelope(
        compute_capabilities=compute_capabilities,
        max_width=_positive_int(envelope.get("maxWidth"), "maxWidth"),
        max_height=_positive_int(envelope.get("maxHeight"), "maxHeight"),
        max_pixels=_positive_int(envelope.get("maxPixels"), "maxPixels"),
        max_render_gaussian_count=_positive_int(
            envelope.get("maxRenderGaussianCount"),
            "maxRenderGaussianCount",
        ),
        max_evidence_gaussian_count=_positive_int(
            envelope.get("maxEvidenceGaussianCount"),
            "maxEvidenceGaussianCount",
        ),
        max_intersection_count=_positive_int(
            envelope.get("maxIntersectionCount"),
            "maxIntersectionCount",
        ),
        max_concurrent_consumers=_positive_int(
            envelope.get("maxConcurrentConsumers"),
            "maxConcurrentConsumers",
        ),
    )
    if result.max_concurrent_consumers != 1:
        raise DepthMomentQualificationError(
            "CWED qualification permits one downstream consumer at a time."
        )
    if result.max_pixels > result.max_width * result.max_height:
        raise DepthMomentQualificationError(
            "supportedEnvelope maxPixels exceeds its declared dimensions."
        )
    return result


def _validate_fixtures(
    value: object,
    *,
    envelope: DepthMomentExecutionEnvelope,
) -> None:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DepthMomentQualificationError("fixtures must be a sequence.")
    if not value:
        raise DepthMomentQualificationError("At least one GPU fixture is required.")
    fixture_ids: set[str] = set()
    for index, raw_fixture in enumerate(value):
        fixture = _exact_keys(raw_fixture, _FIXTURE_KEYS, f"fixtures[{index}]")
        fixture_id = _non_empty(fixture.get("fixtureId"), "fixtureId")
        if fixture_id in fixture_ids:
            raise DepthMomentQualificationError("fixtureId values must be unique.")
        fixture_ids.add(fixture_id)
        _non_empty(fixture.get("scenePath"), "scenePath")
        _digest(fixture.get("sceneSha256"), "sceneSha256")
        camera = _mapping(fixture.get("cameraManifest"), "cameraManifest")
        if not camera:
            raise DepthMomentQualificationError("cameraManifest cannot be empty.")
        _digest(fixture.get("cameraBindingDigest"), "cameraBindingDigest")
        _digest(fixture.get("renderWorkingSetToken"), "renderWorkingSetToken")
        _digest(fixture.get("evidenceWorkingSetToken"), "evidenceWorkingSetToken")
        resolution = fixture.get("resolution")
        if (
            isinstance(resolution, (str, bytes, bytearray))
            or not isinstance(resolution, Sequence)
            or len(resolution) != 2
        ):
            raise DepthMomentQualificationError("fixture resolution is invalid.")
        width = _positive_int(resolution[0], "fixture width")
        height = _positive_int(resolution[1], "fixture height")
        render_count = _positive_int(
            fixture.get("renderGaussianCount"), "renderGaussianCount"
        )
        evidence_count = _positive_int(
            fixture.get("evidenceGaussianCount"), "evidenceGaussianCount"
        )
        projected_count = _positive_int(
            fixture.get("projectedGaussianCount"), "projectedGaussianCount"
        )
        intersection_count = _positive_int(
            fixture.get("intersectionCount"), "intersectionCount"
        )
        if projected_count > render_count or not envelope.supports(
            width=width,
            height=height,
            render_gaussian_count=render_count,
            evidence_gaussian_count=evidence_count,
            intersection_count=intersection_count,
        ):
            raise DepthMomentQualificationError(
                "A measured fixture falls outside the supported execution envelope."
            )


def _validate_measurements(value: object) -> None:
    measurements = _exact_keys(
        value,
        {
            "warmupCount",
            "sampleCount",
            "latencyMs",
            "transferAndHash",
            "comparison",
            "memory",
        },
        "measurements",
    )
    _positive_int(measurements.get("warmupCount"), "warmupCount")
    _positive_int(measurements.get("sampleCount"), "sampleCount")
    latency = _exact_keys(measurements.get("latencyMs"), _LATENCY_KEYS, "latencyMs")
    for name in _LATENCY_KEYS:
        distribution = _exact_keys(
            latency.get(name), _DISTRIBUTION_KEYS, f"latencyMs {name}"
        )
        median = _nonnegative_number(distribution.get("median"), f"{name} median")
        p95 = _nonnegative_number(distribution.get("p95"), f"{name} p95")
        maximum = _nonnegative_number(
            distribution.get("maximum"), f"{name} maximum"
        )
        if not median <= p95 <= maximum:
            raise DepthMomentQualificationError(
                f"latencyMs {name} distribution is not ordered."
            )
    transfer = _exact_keys(
        measurements.get("transferAndHash"),
        {
            "synchronizeOnlyMs",
            "gpuToCpuMs",
            "sha256Ms",
            "bytes",
            "synchronizationIncluded",
        },
        "transferAndHash",
    )
    _nonnegative_number(transfer.get("synchronizeOnlyMs"), "synchronizeOnlyMs")
    _nonnegative_number(transfer.get("gpuToCpuMs"), "gpuToCpuMs")
    _nonnegative_number(transfer.get("sha256Ms"), "sha256Ms")
    _positive_int(transfer.get("bytes"), "transferAndHash bytes")
    if transfer.get("synchronizationIncluded") is not True:
        raise DepthMomentQualificationError(
            "GPU transfer measurements must include synchronization."
        )
    comparison = _exact_keys(
        measurements.get("comparison"),
        {
            "cacheHitToRecomputationRatio",
            "cacheHitToReadoutConstructionRatio",
            "cacheHitToDownstreamConsumerRatio",
        },
        "comparison",
    )
    for name, raw_value in comparison.items():
        _nonnegative_number(raw_value, f"comparison {name}")
    memory = _exact_keys(
        measurements.get("memory"),
        {
            "withoutMomentsPeakVramBytes",
            "withMomentsPeakVramBytes",
            "readoutPeakVramBytes",
            "cacheValidationPeakVramBytes",
            "momentBufferBytes",
            "ownedTensorBufferBytes",
            "transientHostBytes",
            "transientDeviceBytes",
        },
        "memory",
    )
    for name, raw_value in memory.items():
        _positive_int(raw_value, f"memory {name}")


def _validate_semantic_parity(value: object) -> None:
    parity = _exact_keys(
        value,
        {
            "status",
            "mandatoryCases",
            "rtol",
            "atol",
            "maximumMomentAbsoluteError",
            "productionEvidenceAtol",
            "maximumProductionEvidenceAbsoluteError",
            "withoutMomentsOutputDigest",
            "withMomentsProductionOutputDigest",
            "depthMomentTensorDigest",
            "authoritativeRgbUnchanged",
            "evidenceUnchanged",
            "boundaryBehaviorUnchanged",
        },
        "semanticParity",
    )
    if parity.get("status") != "passed":
        raise DepthMomentQualificationError("semanticParity did not pass.")
    if set(_string_sequence(parity.get("mandatoryCases"), "mandatoryCases")) != (
        _REQUIRED_PARITY_CASES
    ):
        raise DepthMomentQualificationError(
            "semanticParity does not include every mandatory scalar/CUDA fixture."
        )
    for name in ("rtol", "atol", "maximumMomentAbsoluteError"):
        _nonnegative_number(parity.get(name), f"semanticParity {name}")
    production_atol = _nonnegative_number(
        parity.get("productionEvidenceAtol"),
        "semanticParity productionEvidenceAtol",
    )
    production_error = _nonnegative_number(
        parity.get("maximumProductionEvidenceAbsoluteError"),
        "semanticParity maximumProductionEvidenceAbsoluteError",
    )
    if production_error > production_atol:
        raise DepthMomentQualificationError(
            "Moment mode changed production Evidence beyond the declared tolerance."
        )
    _digest(parity.get("withoutMomentsOutputDigest"), "withoutMomentsOutputDigest")
    _digest(
        parity.get("withMomentsProductionOutputDigest"),
        "withMomentsProductionOutputDigest",
    )
    _digest(parity.get("depthMomentTensorDigest"), "depthMomentTensorDigest")
    for name in (
        "authoritativeRgbUnchanged",
        "evidenceUnchanged",
        "boundaryBehaviorUnchanged",
    ):
        if parity.get(name) is not True:
            raise DepthMomentQualificationError(
                f"semanticParity {name} must remain true."
            )


def _validate_failure_outcomes(value: object) -> None:
    outcomes = _exact_keys(value, _FAILURE_KEYS, "failureOutcomes")
    preservation_keys = {
        "priorReadoutPreserved",
        "productionArtifactsPreserved",
        "productionOutputDigestBefore",
        "productionOutputDigestAfter",
    }
    for name, raw_outcome in outcomes.items():
        expected_keys = {"passed", "method", "result"}
        if name in {"allocationFailure", "cancellation"}:
            expected_keys |= preservation_keys
        outcome = _exact_keys(
            raw_outcome,
            expected_keys,
            f"failureOutcomes {name}",
        )
        if outcome.get("passed") is not True:
            raise DepthMomentQualificationError(
                f"failureOutcomes {name} did not pass."
            )
        _non_empty(outcome.get("method"), f"failureOutcomes {name} method")
        _non_empty(outcome.get("result"), f"failureOutcomes {name} result")
        if name in {"allocationFailure", "cancellation"}:
            if (
                outcome.get("priorReadoutPreserved") is not True
                or outcome.get("productionArtifactsPreserved") is not True
            ):
                raise DepthMomentQualificationError(
                    f"failureOutcomes {name} did not preserve prior artifacts."
                )
            before = _digest(
                outcome.get("productionOutputDigestBefore"),
                f"failureOutcomes {name} productionOutputDigestBefore",
            )
            after = _digest(
                outcome.get("productionOutputDigestAfter"),
                f"failureOutcomes {name} productionOutputDigestAfter",
            )
            if before != after:
                raise DepthMomentQualificationError(
                    f"failureOutcomes {name} changed production artifacts."
                )


def _validate_compiler_diagnostics(value: object, compute_capability: str) -> None:
    diagnostics = _exact_keys(
        value,
        {
            "tool",
            "arch",
            "directEvidenceKernelRegisters",
            "projectedDepthProbeKernelRegisters",
            "stackBytes",
            "sharedBytes",
            "localBytes",
            "rawOutputSha256",
        },
        "compilerDiagnostics",
    )
    if diagnostics.get("tool") != "cuobjdump --dump-resource-usage":
        raise DepthMomentQualificationError("compilerDiagnostics tool is stale.")
    if diagnostics.get("arch") != f"sm_{compute_capability.replace('.', '')}":
        raise DepthMomentQualificationError("compilerDiagnostics arch is incompatible.")
    for name in (
        "directEvidenceKernelRegisters",
        "projectedDepthProbeKernelRegisters",
    ):
        _positive_int(diagnostics.get(name), f"compilerDiagnostics {name}")
    for name in ("stackBytes", "sharedBytes", "localBytes"):
        _nonnegative_number(diagnostics.get(name), f"compilerDiagnostics {name}")
    _digest(diagnostics.get("rawOutputSha256"), "rawOutputSha256")


def _validate_promotion_gate(value: object) -> None:
    gate = _exact_keys(value, {"passed", "checks"}, "promotionGate")
    if gate.get("passed") is not True:
        raise DepthMomentQualificationError("promotionGate did not pass.")
    required = {
        "semantic-parity",
        "identity-fail-closed",
        "no-supported-fixture-oom",
        "failure-atomicity",
        "checked-measurements",
    }
    if set(_string_sequence(gate.get("checks"), "promotionGate checks")) != required:
        raise DepthMomentQualificationError("promotionGate checks are incomplete.")


def validate_depth_moment_qualification_record(
    record: Mapping[str, object],
) -> DepthMomentInternalCapability:
    """Validate one complete checked record and freeze its internal capability."""

    document = _exact_keys(record, _TOP_LEVEL_KEYS, "qualification record")
    if document.get("schemaId") != DEPTH_MOMENT_QUALIFICATION_SCHEMA_ID:
        raise DepthMomentQualificationError("qualification schema is stale.")
    if document.get("qualificationId") != QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID:
        raise DepthMomentQualificationError("qualification identity is stale.")
    if document.get("issue") != 53 or document.get("status") != "qualified":
        raise DepthMomentQualificationError("qualification status is not promotable.")
    _non_empty(document.get("recordedAt"), "recordedAt")
    expected_record_digest = _digest(document.get("recordDigest"), "recordDigest")
    unsigned = dict(document)
    del unsigned["recordDigest"]
    if canonical_json_digest(unsigned) != expected_record_digest:
        raise DepthMomentQualificationError("qualification record digest mismatches.")

    _, runtime_compute_capability = _validate_runtime(document.get("runtime"))
    supported = _validate_direct_evidence(document.get("directEvidence"))
    policy = _validate_policy(document.get("momentPolicy"))
    envelope = _validate_envelope(
        document.get("supportedEnvelope"),
        supported_compute_capabilities=supported,
        runtime_compute_capability=runtime_compute_capability,
    )
    _validate_fixtures(document.get("fixtures"), envelope=envelope)
    _validate_measurements(document.get("measurements"))
    _validate_semantic_parity(document.get("semanticParity"))
    _validate_failure_outcomes(document.get("failureOutcomes"))
    _validate_compiler_diagnostics(
        document.get("compilerDiagnostics"), runtime_compute_capability
    )
    _validate_promotion_gate(document.get("promotionGate"))

    return DepthMomentInternalCapability(
        status="ready",
        reason="qualified-exact-runtime-and-envelope",
        qualification_id=QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
        qualification_digest=expected_record_digest,
        policy=policy,
        envelope=envelope,
        direct_evidence_abi_version=DIRECT_EVIDENCE_ABI_VERSION,
        direct_evidence_source_revision=DIRECT_EVIDENCE_SOURCE_REVISION,
        direct_evidence_runtime_build_id=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    )


def _current_uv_lock_digest() -> str | None:
    module_path = Path(__file__).resolve()
    candidates = (
        module_path.parents[2] / "uv.lock",
        module_path.with_name("qualifications") / "uv.lock",
    )
    for candidate in candidates:
        try:
            payload = candidate.read_bytes()
        except OSError:
            continue
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return None


def current_depth_moment_runtime_facts() -> dict[str, object]:
    """Inspect the actual process, lock, GPU, and driver identities."""

    facts = CurrentProcessGsplatInspection().facts()
    status = GsplatRuntime(StaticGsplatRuntimeInspection(facts)).status()
    uv_lock_digest = _current_uv_lock_digest()
    return {
        "status": status.status,
        "operatingSystem": facts.operating_system,
        "pythonVersion": facts.python_version,
        "torchVersion": facts.torch_version,
        "cudaVersion": facts.cuda_version,
        "driverVersion": facts.driver_version,
        "gpuName": facts.gpu_name,
        "computeCapability": facts.compute_capability,
        "gsplatVersion": facts.gsplat_version,
        "gsplatSourceCommit": facts.gsplat_source_commit,
        "rendererLockDigest": uv_lock_digest,
        "uvLockSha256": uv_lock_digest,
    }


def load_internal_depth_moment_capability(
    path: Path = DEFAULT_DEPTH_MOMENT_QUALIFICATION_PATH,
) -> DepthMomentInternalCapability:
    """Load the checked record and match it to the running Direct Evidence GPU."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise DepthMomentQualificationError(
                "qualification record root must be an object."
            )
        capability = validate_depth_moment_qualification_record(document)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DepthMomentInternalCapability.unavailable(
            "qualification-record-unavailable"
        )

    runtime_facts = current_depth_moment_runtime_facts()
    if runtime_facts.get("status") != "ready":
        return replace(capability, status="unavailable", reason="runtime-unavailable")
    expected_runtime = document.get("runtime")
    if not isinstance(expected_runtime, Mapping) or any(
        runtime_facts.get(key) != value
        for key, value in expected_runtime.items()
    ):
        return replace(
            capability,
            status="unavailable",
            reason="runtime-facts-not-qualified",
        )

    runtime = direct_evidence_capability()
    if runtime.get("status") != "ready":
        return replace(capability, status="unavailable", reason="runtime-unavailable")
    expected_identity = {
        "abiVersion": capability.direct_evidence_abi_version,
        "sourceRevision": capability.direct_evidence_source_revision,
        "runtimeBuildId": capability.direct_evidence_runtime_build_id,
    }
    if any(runtime.get(key) != value for key, value in expected_identity.items()):
        return replace(
            capability,
            status="unavailable",
            reason="direct-evidence-identity-not-qualified",
        )
    detected = runtime.get("detectedComputeCapability")
    if (
        not isinstance(detected, str)
        or capability.envelope is None
        or detected not in capability.envelope.compute_capabilities
    ):
        return replace(
            capability,
            status="unavailable",
            reason="compute-capability-not-qualified",
        )
    return capability


__all__ = [
    "DEFAULT_DEPTH_MOMENT_QUALIFICATION_PATH",
    "DEPTH_MOMENT_QUALIFICATION_SCHEMA_ID",
    "QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID",
    "QUALIFIED_DEPTH_MOMENT_MINIMUM_M0",
    "QUALIFIED_DEPTH_MOMENT_POLICY_ID",
    "DepthMomentExecutionEnvelope",
    "DepthMomentInternalCapability",
    "DepthMomentQualificationError",
    "current_depth_moment_runtime_facts",
    "load_internal_depth_moment_capability",
    "validate_depth_moment_qualification_record",
]

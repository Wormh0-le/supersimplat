"""Process-local exact-identity lifecycle for Companion CWED moment readouts.

This module deliberately owns no Browser payload. It binds one complete
same-decision moment image to the exact render/request/runtime identities that
minted it, validates tensor digests before reuse, and fails closed when a
shadow consumer cannot obtain a current readout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from threading import Lock
from typing import Any, Final, Literal, Mapping, Sequence

from .depth_moment_qualification import DepthMomentInternalCapability
from .depth_moments import (
    DepthMomentValidityPolicy,
    derive_depth_moment_readout,
    validate_depth_moment_tensor,
)
from .digests import canonical_json_digest


DEPTH_MOMENT_READOUT_SCHEMA_ID: Final = "depth-moment-readout/internal-v2"
_PROJECTED_ROW_MAPPING_SCHEMA_ID: Final = (
    "direct-evidence-projected-row-mapping/internal-v1"
)
_DIGEST_PREFIX: Final = "sha256:"
_DIGEST_LENGTH: Final = len(_DIGEST_PREFIX) + 64
_MAX_STABLE_GAUSSIAN_ID: Final = (1 << 32) - 1
_CONSUMER_PERMIT_LOCK = Lock()
_ACTIVE_CONSUMER_COUNT = 0
_ADMISSION_KEYS: Final = {
    "requestBinding",
    "targetSplatId",
    "viewId",
    "cameraBindingDigest",
    "rgbDigest",
    "stableMaskDigest",
    "evidencePolicyDigest",
    "renderWorkingSetToken",
    "evidenceWorkingSetToken",
    "stableGaussianIds",
    "rasterImplementationId",
    "evidenceBackendKind",
    "evidenceBackendId",
    "runtimeBuildId",
}
_REQUEST_BINDING_KEYS: Final = {
    "targetContextId",
    "contextRevision",
    "dependencyToken",
}
_DEPENDENCY_KEYS: Final = {
    "splatId",
    "renderStateToken",
    "geometryToken",
    "gaussianIdentityToken",
    "worldTransformToken",
}


class DepthMomentReadoutError(ValueError):
    """A Companion-internal moment readout failed exact validation."""


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_LENGTH
        and value.startswith(_DIGEST_PREFIX)
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _require_non_empty(value: object, name: str) -> str:
    if not _is_non_empty_string(value):
        raise DepthMomentReadoutError(f"{name} must be a non-empty string.")
    return str(value)


def _require_digest(value: object, name: str) -> str:
    if not _is_digest(value):
        raise DepthMomentReadoutError(f"{name} must be a canonical SHA-256 digest.")
    return str(value)


def _require_nonnegative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DepthMomentReadoutError(f"{name} must be a non-negative integer.")
    return value


def _policy_digest(policy: DepthMomentValidityPolicy) -> str:
    return canonical_json_digest({
        "schemaId": "depth-moment-validity-policy/internal-v1",
        "policyId": policy.policy_id,
        "minimumM0": float(policy.minimum_m0),
    })


def _validated_projected_row_ids(values: Sequence[int]) -> tuple[int, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise DepthMomentReadoutError(
            "Projected-row Stable Gaussian IDs must be an ordered sequence."
        )
    result: list[int] = []
    try:
        source_values = values.tolist() if hasattr(values, "tolist") else values
        for value in source_values:
            if hasattr(value, "item"):
                value = value.item()
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > _MAX_STABLE_GAUSSIAN_ID
            ):
                raise DepthMomentReadoutError(
                    "Projected-row Stable Gaussian IDs must be uint32 values."
                )
            result.append(value)
    except TypeError as error:
        raise DepthMomentReadoutError(
            "Projected-row Stable Gaussian IDs must be an ordered sequence."
        ) from error
    if not result or len(set(result)) != len(result):
        raise DepthMomentReadoutError(
            "Projected-row Stable Gaussian IDs must be non-empty and unique."
        )
    return tuple(result)


def projected_row_mapping_digest(values: Sequence[int]) -> str:
    """Digest the exact Stable-ID order consumed by projected tensor rows."""

    stable_ids = _validated_projected_row_ids(values)
    return canonical_json_digest({
        "schemaId": _PROJECTED_ROW_MAPPING_SCHEMA_ID,
        "stableGaussianIdsByProjectedRow": list(stable_ids),
    })


@dataclass(frozen=True)
class DepthMomentTargetDependency:
    splat_id: str
    render_state_token: str
    geometry_token: str
    gaussian_identity_token: str
    world_transform_token: str

    def __post_init__(self) -> None:
        for name, value in (
            ("splat_id", self.splat_id),
            ("render_state_token", self.render_state_token),
            ("geometry_token", self.geometry_token),
            ("gaussian_identity_token", self.gaussian_identity_token),
            ("world_transform_token", self.world_transform_token),
        ):
            _require_non_empty(value, name)

    def as_dict(self) -> dict[str, object]:
        return {
            "splatId": self.splat_id,
            "renderStateToken": self.render_state_token,
            "geometryToken": self.geometry_token,
            "gaussianIdentityToken": self.gaussian_identity_token,
            "worldTransformToken": self.world_transform_token,
        }


@dataclass(frozen=True)
class DepthMomentRequestBinding:
    target_context_id: str
    context_revision: int
    dependency: DepthMomentTargetDependency

    def __post_init__(self) -> None:
        _require_non_empty(self.target_context_id, "target_context_id")
        _require_nonnegative_integer(self.context_revision, "context_revision")
        if not isinstance(self.dependency, DepthMomentTargetDependency):
            raise DepthMomentReadoutError(
                "request binding requires an exact target dependency."
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "targetContextId": self.target_context_id,
            "contextRevision": self.context_revision,
            "dependencyToken": self.dependency.as_dict(),
        }


@dataclass(frozen=True)
class DepthMomentReadoutIdentity:
    request_binding: DepthMomentRequestBinding
    target_splat_id: str
    view_id: str
    camera_binding_digest: str
    rgb_digest: str
    render_working_set_token: str
    projected_row_mapping_digest: str
    direct_evidence_abi_version: str
    direct_evidence_source_revision: str
    direct_evidence_runtime_build_id: str
    qualification_id: str
    qualification_digest: str
    execution_envelope_digest: str
    moment_policy_id: str
    moment_minimum_m0: float
    width: int
    height: int
    moment_policy_digest: str = field(init=False)
    identity_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request_binding, DepthMomentRequestBinding):
            raise DepthMomentReadoutError(
                "Depth-moment identity requires an exact request binding."
            )
        for name, value in (
            ("target_splat_id", self.target_splat_id),
            ("view_id", self.view_id),
            ("direct_evidence_abi_version", self.direct_evidence_abi_version),
            ("qualification_id", self.qualification_id),
            ("moment_policy_id", self.moment_policy_id),
        ):
            _require_non_empty(value, name)
        if self.request_binding.dependency.splat_id != self.target_splat_id:
            raise DepthMomentReadoutError(
                "Depth-moment target and dependency identities do not match."
            )
        for name, value in (
            ("camera_binding_digest", self.camera_binding_digest),
            ("rgb_digest", self.rgb_digest),
            ("render_working_set_token", self.render_working_set_token),
            ("projected_row_mapping_digest", self.projected_row_mapping_digest),
            ("direct_evidence_source_revision", self.direct_evidence_source_revision),
            ("direct_evidence_runtime_build_id", self.direct_evidence_runtime_build_id),
            ("qualification_digest", self.qualification_digest),
            ("execution_envelope_digest", self.execution_envelope_digest),
        ):
            _require_digest(value, name)
        if (
            isinstance(self.moment_minimum_m0, bool)
            or not isinstance(self.moment_minimum_m0, (int, float))
            or not math.isfinite(float(self.moment_minimum_m0))
            or self.moment_minimum_m0 <= 0.0
        ):
            raise DepthMomentReadoutError(
                "Depth-moment minimum M0 must be finite and positive."
            )
        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise DepthMomentReadoutError(f"{name} must be a positive integer.")
        policy = DepthMomentValidityPolicy(
            policy_id=self.moment_policy_id,
            minimum_m0=float(self.moment_minimum_m0),
        )
        object.__setattr__(self, "moment_policy_digest", _policy_digest(policy))
        object.__setattr__(
            self,
            "identity_digest",
            canonical_json_digest(self.identity_payload()),
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "schemaId": DEPTH_MOMENT_READOUT_SCHEMA_ID,
            "requestBinding": self.request_binding.as_dict(),
            "targetSplatId": self.target_splat_id,
            "viewId": self.view_id,
            "cameraBindingDigest": self.camera_binding_digest,
            "rgbDigest": self.rgb_digest,
            "renderWorkingSetToken": self.render_working_set_token,
            "projectedRowMappingDigest": self.projected_row_mapping_digest,
            "directEvidence": {
                "abiVersion": self.direct_evidence_abi_version,
                "sourceRevision": self.direct_evidence_source_revision,
                "runtimeBuildId": self.direct_evidence_runtime_build_id,
            },
            "qualification": {
                "qualificationId": self.qualification_id,
                "qualificationDigest": self.qualification_digest,
                "executionEnvelopeDigest": self.execution_envelope_digest,
            },
            "momentPolicy": {
                "policyId": self.moment_policy_id,
                "minimumM0": float(self.moment_minimum_m0),
                "policyDigest": self.moment_policy_digest,
            },
            "shape": {"width": self.width, "height": self.height},
        }

    @property
    def slot(self) -> tuple[str, str]:
        return (self.request_binding.target_context_id, self.view_id)


def _parse_request_binding(value: object) -> DepthMomentRequestBinding:
    if not isinstance(value, Mapping) or set(value) != _REQUEST_BINDING_KEYS:
        raise DepthMomentReadoutError(
            "Depth-moment request binding must contain the exact current keys."
        )
    dependency = value.get("dependencyToken")
    if not isinstance(dependency, Mapping) or set(dependency) != _DEPENDENCY_KEYS:
        raise DepthMomentReadoutError(
            "Depth-moment dependency token must contain the exact current keys."
        )
    return DepthMomentRequestBinding(
        target_context_id=_require_non_empty(
            value.get("targetContextId"), "targetContextId"
        ),
        context_revision=_require_nonnegative_integer(
            value.get("contextRevision"), "contextRevision"
        ),
        dependency=DepthMomentTargetDependency(
            splat_id=_require_non_empty(dependency.get("splatId"), "splatId"),
            render_state_token=_require_non_empty(
                dependency.get("renderStateToken"), "renderStateToken"
            ),
            geometry_token=_require_non_empty(
                dependency.get("geometryToken"), "geometryToken"
            ),
            gaussian_identity_token=_require_non_empty(
                dependency.get("gaussianIdentityToken"),
                "gaussianIdentityToken",
            ),
            world_transform_token=_require_non_empty(
                dependency.get("worldTransformToken"), "worldTransformToken"
            ),
        ),
    )


def create_depth_moment_readout_identity(
    admission: Mapping[str, object],
    *,
    render_stable_ids_by_projected_row: Sequence[int],
    capability: DepthMomentInternalCapability,
    width: int,
    height: int,
) -> DepthMomentReadoutIdentity:
    """Bind one expected readout to an exact qualified Direct Evidence render."""

    if not isinstance(admission, Mapping) or set(admission) != _ADMISSION_KEYS:
        raise DepthMomentReadoutError(
            "Depth-moment identity requires the exact admitted Evidence keys."
        )
    if (
        not isinstance(capability, DepthMomentInternalCapability)
        or capability.status != "ready"
        or capability.policy is None
        or capability.envelope is None
    ):
        raise DepthMomentReadoutError(
            "Depth-moment identity requires a ready qualified capability."
        )
    policy = capability.policy
    if admission.get("evidenceBackendKind") != "production-direct":
        raise DepthMomentReadoutError(
            "Depth moments may bind only production Direct Evidence."
        )
    if (
        admission.get("runtimeBuildId")
        != capability.direct_evidence_runtime_build_id
    ):
        raise DepthMomentReadoutError(
            "Depth-moment runtime identity does not match Direct Evidence admission."
        )
    return DepthMomentReadoutIdentity(
        request_binding=_parse_request_binding(admission.get("requestBinding")),
        target_splat_id=_require_non_empty(
            admission.get("targetSplatId"), "targetSplatId"
        ),
        view_id=_require_non_empty(admission.get("viewId"), "viewId"),
        camera_binding_digest=_require_digest(
            admission.get("cameraBindingDigest"), "cameraBindingDigest"
        ),
        rgb_digest=_require_digest(admission.get("rgbDigest"), "rgbDigest"),
        render_working_set_token=_require_digest(
            admission.get("renderWorkingSetToken"), "renderWorkingSetToken"
        ),
        projected_row_mapping_digest=projected_row_mapping_digest(
            render_stable_ids_by_projected_row
        ),
        direct_evidence_abi_version=capability.direct_evidence_abi_version,
        direct_evidence_source_revision=(
            capability.direct_evidence_source_revision
        ),
        direct_evidence_runtime_build_id=(
            capability.direct_evidence_runtime_build_id
        ),
        qualification_id=capability.qualification_id,
        qualification_digest=capability.qualification_digest,
        execution_envelope_digest=canonical_json_digest(
            capability.envelope.as_dict()
        ),
        moment_policy_id=policy.policy_id,
        moment_minimum_m0=float(policy.minimum_m0),
        width=width,
        height=height,
    )


def _tensor_digest(tensor: Any) -> str:
    import torch

    if not isinstance(tensor, torch.Tensor) or not tensor.is_contiguous():
        raise DepthMomentReadoutError(
            "Depth-moment tensor digests require contiguous torch tensors."
        )
    cpu = tensor.detach().to(device="cpu").contiguous()
    header = json.dumps(
        {"dtype": str(cpu.dtype), "shape": list(cpu.shape)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    hasher = hashlib.sha256()
    hasher.update(header)
    hasher.update(b"\0")
    hasher.update(cpu.numpy().tobytes(order="C"))
    return f"sha256:{hasher.hexdigest()}"


@dataclass(frozen=True)
class DepthMomentTensorDigests:
    raw_depth_moments: str
    valid: str
    cwed: str
    variance: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rawDepthMoments": self.raw_depth_moments,
            "valid": self.valid,
            "cwed": self.cwed,
            "variance": self.variance,
        }


@dataclass(frozen=True)
class DepthMomentTelemetry:
    depth_moment_buffer_bytes: int
    peak_vram_bytes: int
    owned_tensor_buffer_bytes: int = 0
    projected_gaussian_count: int = 0
    evidence_gaussian_count: int = 0
    intersection_count: int = 0

    def __post_init__(self) -> None:
        _require_nonnegative_integer(
            self.depth_moment_buffer_bytes, "depth_moment_buffer_bytes"
        )
        _require_nonnegative_integer(self.peak_vram_bytes, "peak_vram_bytes")
        _require_nonnegative_integer(
            self.owned_tensor_buffer_bytes, "owned_tensor_buffer_bytes"
        )
        _require_nonnegative_integer(
            self.projected_gaussian_count, "projected_gaussian_count"
        )
        _require_nonnegative_integer(
            self.evidence_gaussian_count, "evidence_gaussian_count"
        )
        _require_nonnegative_integer(self.intersection_count, "intersection_count")

    def as_dict(self) -> dict[str, int]:
        return {
            "depthMomentBufferBytes": self.depth_moment_buffer_bytes,
            "ownedTensorBufferBytes": self.owned_tensor_buffer_bytes,
            "peakVramBytes": self.peak_vram_bytes,
            "projectedGaussianCount": self.projected_gaussian_count,
            "evidenceGaussianCount": self.evidence_gaussian_count,
            "intersectionCount": self.intersection_count,
        }


@dataclass(frozen=True, init=False)
class DepthMomentReadoutRecord:
    """Immutable process-local owner of one exact raw and derived readout."""

    identity: DepthMomentReadoutIdentity
    policy: DepthMomentValidityPolicy
    tensor_digests: DepthMomentTensorDigests
    telemetry: DepthMomentTelemetry
    readout_digest: str
    _raw_depth_moments: Any = field(repr=False, compare=False)
    _valid: Any = field(repr=False, compare=False)
    _cwed: Any = field(repr=False, compare=False)
    _variance: Any = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        identity: DepthMomentReadoutIdentity,
        raw_depth_moments: Any,
        policy: DepthMomentValidityPolicy,
        telemetry: DepthMomentTelemetry,
    ) -> None:
        import torch

        if not isinstance(identity, DepthMomentReadoutIdentity):
            raise DepthMomentReadoutError(
                "Depth-moment readout requires an exact identity."
            )
        if not isinstance(policy, DepthMomentValidityPolicy):
            raise DepthMomentReadoutError(
                "Depth-moment readout requires a versioned policy."
            )
        if (
            identity.moment_policy_id != policy.policy_id
            or identity.moment_minimum_m0 != float(policy.minimum_m0)
            or identity.moment_policy_digest != _policy_digest(policy)
        ):
            raise DepthMomentReadoutError(
                "Depth-moment readout policy does not match its identity."
            )
        if not isinstance(telemetry, DepthMomentTelemetry):
            raise DepthMomentReadoutError(
                "Depth-moment readout requires measured telemetry."
            )
        try:
            validate_depth_moment_tensor(
                raw_depth_moments,
                width=identity.width,
                height=identity.height,
                require_finite=True,
            )
        except ValueError as error:
            raise DepthMomentReadoutError(
                "Depth moments must be complete finite contiguous float32 [H,W,3] for the bound Camera/RGB identity."
            ) from error
        expected_buffer_bytes = identity.width * identity.height * 3 * 4
        if telemetry.depth_moment_buffer_bytes != expected_buffer_bytes:
            raise DepthMomentReadoutError(
                "Depth-moment telemetry does not match the owned raw tensor."
            )

        owned_raw = raw_depth_moments.detach().clone().contiguous()
        derived = derive_depth_moment_readout(owned_raw, policy=policy)
        owned_valid = derived.valid.detach().clone().contiguous()
        owned_cwed = derived.cwed.detach().clone().contiguous()
        owned_variance = derived.variance.detach().clone().contiguous()
        tensor_digests = DepthMomentTensorDigests(
            raw_depth_moments=_tensor_digest(owned_raw),
            valid=_tensor_digest(owned_valid),
            cwed=_tensor_digest(owned_cwed),
            variance=_tensor_digest(owned_variance),
        )
        owned_tensor_buffer_bytes = sum(
            tensor.numel() * tensor.element_size()
            for tensor in (owned_raw, owned_valid, owned_cwed, owned_variance)
        )
        measured_peak_vram_bytes = telemetry.peak_vram_bytes
        if owned_raw.is_cuda:
            measured_peak_vram_bytes = max(
                measured_peak_vram_bytes,
                int(torch.cuda.max_memory_allocated(owned_raw.device)),
            )
        measured_telemetry = DepthMomentTelemetry(
            depth_moment_buffer_bytes=telemetry.depth_moment_buffer_bytes,
            owned_tensor_buffer_bytes=owned_tensor_buffer_bytes,
            peak_vram_bytes=measured_peak_vram_bytes,
            projected_gaussian_count=telemetry.projected_gaussian_count,
            evidence_gaussian_count=telemetry.evidence_gaussian_count,
            intersection_count=telemetry.intersection_count,
        )
        payload = {
            "schemaId": DEPTH_MOMENT_READOUT_SCHEMA_ID,
            "identity": identity.identity_payload(),
            "identityDigest": identity.identity_digest,
            "tensorDigests": tensor_digests.as_dict(),
        }
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "tensor_digests", tensor_digests)
        object.__setattr__(self, "telemetry", measured_telemetry)
        object.__setattr__(self, "readout_digest", canonical_json_digest(payload))
        object.__setattr__(self, "_raw_depth_moments", owned_raw)
        object.__setattr__(self, "_valid", owned_valid)
        object.__setattr__(self, "_cwed", owned_cwed)
        object.__setattr__(self, "_variance", owned_variance)

    @property
    def raw_depth_moments(self) -> Any:
        return self._raw_depth_moments.clone()

    @property
    def valid(self) -> Any:
        return self._valid.clone()

    @property
    def cwed(self) -> Any:
        return self._cwed.clone()

    @property
    def variance(self) -> Any:
        return self._variance.clone()

    def validate(self) -> bool:
        """Recheck canonical identity and every owned tensor before reuse."""

        try:
            current_tensor_digests = DepthMomentTensorDigests(
                raw_depth_moments=_tensor_digest(self._raw_depth_moments),
                valid=_tensor_digest(self._valid),
                cwed=_tensor_digest(self._cwed),
                variance=_tensor_digest(self._variance),
            )
            expected_identity_digest = canonical_json_digest(
                self.identity.identity_payload()
            )
            payload = {
                "schemaId": DEPTH_MOMENT_READOUT_SCHEMA_ID,
                "identity": self.identity.identity_payload(),
                "identityDigest": expected_identity_digest,
                "tensorDigests": current_tensor_digests.as_dict(),
            }
            return (
                self.identity.identity_digest == expected_identity_digest
                and current_tensor_digests == self.tensor_digests
                and canonical_json_digest(payload) == self.readout_digest
            )
        except (DepthMomentReadoutError, TypeError, ValueError) as error:
            if _readout_failure_reason(error) in {
                "depth-moment-capacity-unavailable",
                "depth-moment-runtime-unavailable",
            }:
                raise
            return False


DepthMomentLookupStatus = Literal["available", "unavailable", "stale"]


@dataclass(frozen=True)
class DepthMomentLookupResult:
    status: DepthMomentLookupStatus
    reason: str
    readout: DepthMomentReadoutRecord | None = None


@dataclass(frozen=True)
class _DepthMomentCacheEntry:
    identity: DepthMomentReadoutIdentity
    status: DepthMomentLookupStatus
    reason: str
    readout: DepthMomentReadoutRecord | None


@dataclass(frozen=True)
class _ValidatedDepthMomentPublish:
    readout: DepthMomentReadoutRecord
    validation_digest: str


class DepthMomentReadoutCache:
    """Process-local cache that never remaps a readout across identities."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], _DepthMomentCacheEntry] = {}
        self._lock = Lock()

    def validate_for_publish(
        self,
        readout: DepthMomentReadoutRecord,
    ) -> _ValidatedDepthMomentPublish:
        """Perform expensive tensor-integrity proof before the commit lock."""

        if not isinstance(readout, DepthMomentReadoutRecord) or not readout.validate():
            raise DepthMomentReadoutError(
                "Only a complete digest-valid depth-moment readout may be cached."
            )
        return _ValidatedDepthMomentPublish(
            readout=readout,
            validation_digest=readout.readout_digest,
        )

    def publish_validated(
        self,
        validated: _ValidatedDepthMomentPublish,
        *,
        expected_recomputed_digest: str | None = None,
    ) -> DepthMomentLookupResult:
        """Atomically publish a readout whose full tensor proof just passed."""

        if (
            not isinstance(validated, _ValidatedDepthMomentPublish)
            or validated.validation_digest != validated.readout.readout_digest
        ):
            raise DepthMomentReadoutError(
                "Depth-moment publication requires a current validation token."
            )
        readout = validated.readout
        if expected_recomputed_digest is not None:
            _require_digest(
                expected_recomputed_digest, "expected_recomputed_digest"
            )
            if readout.readout_digest != expected_recomputed_digest:
                entry = _DepthMomentCacheEntry(
                    identity=readout.identity,
                    status="stale",
                    reason="recomputed-digest-mismatch",
                    readout=None,
                )
                with self._lock:
                    self._entries[readout.identity.slot] = entry
                return DepthMomentLookupResult(
                    status=entry.status,
                    reason=entry.reason,
                )
        entry = _DepthMomentCacheEntry(
            identity=readout.identity,
            status="available",
            reason="exact-cache-hit",
            readout=readout,
        )
        with self._lock:
            self._entries[readout.identity.slot] = entry
        return DepthMomentLookupResult(
            status="available",
            reason="published",
            readout=readout,
        )

    def publish(
        self,
        readout: DepthMomentReadoutRecord,
        *,
        expected_recomputed_digest: str | None = None,
    ) -> DepthMomentLookupResult:
        validated = self.validate_for_publish(readout)
        return self.publish_validated(
            validated,
            expected_recomputed_digest=expected_recomputed_digest,
        )

    def mark_unavailable(
        self,
        identity: DepthMomentReadoutIdentity,
        *,
        reason: str,
        preserve_available: bool = False,
    ) -> DepthMomentLookupResult:
        if not isinstance(identity, DepthMomentReadoutIdentity):
            raise DepthMomentReadoutError(
                "Unavailable depth-moment state requires an exact identity."
            )
        _require_non_empty(reason, "reason")
        entry = _DepthMomentCacheEntry(
            identity=identity,
            status="unavailable",
            reason=reason,
            readout=None,
        )
        with self._lock:
            current = self._entries.get(identity.slot)
            if not (
                preserve_available
                and current is not None
                and current.identity == identity
                and current.status == "available"
                and current.readout is not None
            ):
                self._entries[identity.slot] = entry
        return DepthMomentLookupResult(status="unavailable", reason=reason)

    def lookup(
        self,
        identity: DepthMomentReadoutIdentity,
    ) -> DepthMomentLookupResult:
        if not isinstance(identity, DepthMomentReadoutIdentity):
            raise DepthMomentReadoutError(
                "Depth-moment lookup requires an exact identity."
            )
        with self._lock:
            entry = self._entries.get(identity.slot)
        if entry is None:
            return DepthMomentLookupResult(
                status="unavailable",
                reason="readout-unavailable",
            )
        if entry.identity != identity:
            stale = _DepthMomentCacheEntry(
                identity=identity,
                status="stale",
                reason="bound-identity-mismatch",
                readout=None,
            )
            with self._lock:
                if self._entries.get(identity.slot) == entry:
                    self._entries[identity.slot] = stale
            return DepthMomentLookupResult(
                status="stale",
                reason="bound-identity-mismatch",
            )
        if entry.readout is None:
            return DepthMomentLookupResult(
                status=entry.status,
                reason=entry.reason,
            )
        try:
            is_valid = entry.readout.validate()
        except Exception as error:
            reason = _readout_failure_reason(error)
            unavailable = _DepthMomentCacheEntry(
                identity=identity,
                status="unavailable",
                reason=reason,
                readout=None,
            )
            with self._lock:
                if self._entries.get(identity.slot) == entry:
                    self._entries[identity.slot] = unavailable
            return DepthMomentLookupResult(
                status="unavailable",
                reason=reason,
            )
        if not is_valid:
            stale = _DepthMomentCacheEntry(
                identity=identity,
                status="stale",
                reason="tensor-digest-mismatch",
                readout=None,
            )
            with self._lock:
                if self._entries.get(identity.slot) == entry:
                    self._entries[identity.slot] = stale
            return DepthMomentLookupResult(
                status="stale",
                reason="tensor-digest-mismatch",
            )
        return DepthMomentLookupResult(
            status="available",
            reason="exact-cache-hit",
            readout=entry.readout,
        )

    def clear(self) -> None:
        """Dispose all process-local readouts, as happens on Companion restart."""

        with self._lock:
            self._entries.clear()


def _readout_failure_reason(error: Exception) -> str:
    explicit_reasons = frozenset({
        "depth-moment-capacity-unavailable",
        "depth-moment-runtime-unavailable",
    })
    try:
        import torch
    except ImportError:
        torch = None
    current: BaseException | None = error
    visited: set[int] = set()
    runtime_failure = False
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        explicit_reason = getattr(current, "reason", None)
        if explicit_reason in explicit_reasons:
            return str(explicit_reason)
        if isinstance(current, MemoryError) or (
            torch is not None
            and isinstance(current, torch.OutOfMemoryError)
        ):
            return "depth-moment-capacity-unavailable"
        if isinstance(current, RuntimeError):
            runtime_failure = True
        current = current.__cause__ or current.__context__
    if runtime_failure:
        return "depth-moment-runtime-unavailable"
    if isinstance(error, DepthMomentReadoutError):
        return "depth-moments-unavailable"
    return "depth-moment-consumer-failed"


@dataclass
class DepthMomentConsumerRegistration:
    """Internal opt-in consumer for one qualified Direct Evidence operation."""

    cache: DepthMomentReadoutCache = field(repr=False)
    capability: DepthMomentInternalCapability
    expected_recomputed_digest: str | None = None
    _result: DepthMomentLookupResult = field(init=False, repr=False)
    _prepared_identity: DepthMomentReadoutIdentity | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _cancelled: bool = field(default=False, init=False, repr=False)
    _terminal: bool = field(default=False, init=False, repr=False)
    _permit_held: bool = field(default=False, init=False, repr=False)
    _result_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.cache, DepthMomentReadoutCache):
            raise DepthMomentReadoutError(
                "Depth-moment consumer requires a process-local cache."
            )
        if (
            not isinstance(self.capability, DepthMomentInternalCapability)
            or self.capability.status != "ready"
            or self.capability.policy is None
            or self.capability.envelope is None
        ):
            raise DepthMomentReadoutError(
                "Depth-moment consumer requires a ready qualified capability."
            )
        if self.expected_recomputed_digest is not None:
            _require_digest(
                self.expected_recomputed_digest,
                "expected_recomputed_digest",
            )
        self._result = DepthMomentLookupResult(
            status="unavailable",
            reason="readout-not-consumed",
        )

    @property
    def policy(self) -> DepthMomentValidityPolicy:
        policy = self.capability.policy
        if policy is None:  # Guarded by construction; retained for type narrowing.
            raise DepthMomentReadoutError(
                "Depth-moment capability has no qualified policy."
            )
        return policy

    @property
    def result(self) -> DepthMomentLookupResult:
        with self._result_lock:
            return self._result

    def _record_result(
        self,
        result: DepthMomentLookupResult,
        *,
        terminal: bool = False,
    ) -> DepthMomentLookupResult:
        with self._result_lock:
            self._result = result
            self._terminal = self._terminal or terminal
        if terminal:
            self._release_consumer_permit()
        return result

    def _acquire_consumer_permit_locked(self) -> bool:
        """Acquire capacity while the caller holds the registration state lock."""

        global _ACTIVE_CONSUMER_COUNT

        envelope = self.capability.envelope
        if envelope is None:
            return False
        with _CONSUMER_PERMIT_LOCK:
            if _ACTIVE_CONSUMER_COUNT >= envelope.max_concurrent_consumers:
                return False
            _ACTIVE_CONSUMER_COUNT += 1
            self._permit_held = True
            return True

    def _release_consumer_permit(self) -> None:
        global _ACTIVE_CONSUMER_COUNT

        with _CONSUMER_PERMIT_LOCK:
            if not self._permit_held:
                return
            self._permit_held = False
            _ACTIVE_CONSUMER_COUNT -= 1

    def cancel(self) -> DepthMomentLookupResult:
        """Cancel before publication; a completed readout remains authoritative."""

        with self._result_lock:
            if self._terminal:
                return self._result
            self._cancelled = True
            self._terminal = True
            identity = self._prepared_identity
            result = DepthMomentLookupResult(
                status="unavailable",
                reason="depth-moment-cancelled",
            )
            self._result = result
        if identity is not None:
            result = self.cache.mark_unavailable(
                identity,
                reason="depth-moment-cancelled",
                preserve_available=True,
            )
            with self._result_lock:
                self._result = result
        self._release_consumer_permit()
        return result

    def abandon(self, *, reason: str) -> DepthMomentLookupResult:
        """Release an unpublished operation after a surrounding render failure."""

        _require_non_empty(reason, "reason")
        with self._result_lock:
            if self._terminal:
                return self._result
            identity = self._prepared_identity
        if identity is not None:
            return self.unavailable(identity, reason=reason)
        return self._record_result(
            DepthMomentLookupResult(status="unavailable", reason=reason),
            terminal=True,
        )

    def _create_identity(
        self,
        *,
        admission: Mapping[str, object],
        render_stable_ids_by_projected_row: Sequence[int],
        width: int,
        height: int,
    ) -> DepthMomentReadoutIdentity:
        return create_depth_moment_readout_identity(
            admission,
            render_stable_ids_by_projected_row=(
                render_stable_ids_by_projected_row
            ),
            capability=self.capability,
            width=width,
            height=height,
        )

    def prepare_execution(
        self,
        *,
        admission: Mapping[str, object],
        render_stable_ids_by_projected_row: Sequence[int],
        evidence_gaussian_count: int,
        width: int,
        height: int,
    ) -> bool:
        """Authorize moment allocation only inside the qualified envelope."""

        with self._result_lock:
            if self._terminal:
                return False
        try:
            identity = self._create_identity(
                admission=admission,
                render_stable_ids_by_projected_row=(
                    render_stable_ids_by_projected_row
                ),
                width=width,
                height=height,
            )
        except Exception as error:
            self._identity_failure(error)
            return False
        if not self.capability.supports_execution(
            width=width,
            height=height,
            render_gaussian_count=len(render_stable_ids_by_projected_row),
            evidence_gaussian_count=evidence_gaussian_count,
        ):
            self.unavailable(
                identity,
                reason="depth-moment-envelope-unavailable",
            )
            return False
        with self._result_lock:
            if self._terminal or self._cancelled:
                return False
            self._prepared_identity = identity
            permitted = self._acquire_consumer_permit_locked()
        if not permitted:
            self.unavailable(
                identity,
                reason="depth-moment-capacity-unavailable",
            )
            return False
        return True

    def _identity_failure(
        self,
        error: Exception,
    ) -> DepthMomentLookupResult:
        reason = (
            "depth-moment-identity-invalid"
            if isinstance(error, DepthMomentReadoutError)
            else _readout_failure_reason(error)
        )
        return self._record_result(
            DepthMomentLookupResult(
                status="unavailable",
                reason=reason,
            ),
            terminal=True,
        )

    def consume_complete(
        self,
        *,
        admission: Mapping[str, object],
        render_stable_ids_by_projected_row: Sequence[int],
        raw_depth_moments: Any,
        width: int,
        height: int,
        depth_moment_buffer_bytes: int,
        peak_vram_bytes: int,
        projected_gaussian_count: int | None = None,
        evidence_gaussian_count: int | None = None,
        intersection_count: int | None = None,
    ) -> DepthMomentLookupResult:
        with self._result_lock:
            if self._terminal or self._cancelled:
                return self._result
            prepared = self._prepared_identity is not None
        if not prepared and not self.prepare_execution(
            admission=admission,
            render_stable_ids_by_projected_row=(
                render_stable_ids_by_projected_row
            ),
            evidence_gaussian_count=(
                len(admission.get("stableGaussianIds", ()))
                if evidence_gaussian_count is None
                else evidence_gaussian_count
            ),
            width=width,
            height=height,
        ):
            return self.result
        try:
            identity = self._create_identity(
                admission=admission,
                render_stable_ids_by_projected_row=(
                    render_stable_ids_by_projected_row
                ),
                width=width,
                height=height,
            )
        except Exception as error:
            return self._identity_failure(error)
        projected_count = (
            len(render_stable_ids_by_projected_row)
            if projected_gaussian_count is None
            else projected_gaussian_count
        )
        evidence_count = (
            len(admission.get("stableGaussianIds", ()))
            if evidence_gaussian_count is None
            else evidence_gaussian_count
        )
        intersections = 0 if intersection_count is None else intersection_count
        if (
            projected_count != len(render_stable_ids_by_projected_row)
            or not self.capability.supports_execution(
                width=width,
                height=height,
                render_gaussian_count=len(render_stable_ids_by_projected_row),
                evidence_gaussian_count=evidence_count,
                intersection_count=intersections,
            )
        ):
            return self.unavailable(
                identity,
                reason="depth-moment-envelope-unavailable",
            )
        try:
            readout = DepthMomentReadoutRecord(
                identity=identity,
                raw_depth_moments=raw_depth_moments,
                policy=self.policy,
                telemetry=DepthMomentTelemetry(
                    depth_moment_buffer_bytes=depth_moment_buffer_bytes,
                    peak_vram_bytes=peak_vram_bytes,
                    projected_gaussian_count=projected_count,
                    evidence_gaussian_count=evidence_count,
                    intersection_count=intersections,
                ),
            )
            validated = self.cache.validate_for_publish(readout)
            with self._result_lock:
                if self._terminal or self._cancelled:
                    return self._result
                result = self.cache.publish_validated(
                    validated,
                    expected_recomputed_digest=self.expected_recomputed_digest,
                )
                self._result = result
                self._terminal = True
            self._release_consumer_permit()
            return result
        except Exception as error:
            # Preserve operational categories while keeping shadow failures
            # subordinate to valid production RGB/P/N/V publication.
            result = self.cache.mark_unavailable(
                identity,
                reason=_readout_failure_reason(error),
                preserve_available=True,
            )
        return self._record_result(result, terminal=True)

    def consume_source_failure(
        self,
        *,
        admission: Mapping[str, object],
        render_stable_ids_by_projected_row: Sequence[int],
        width: int,
        height: int,
        error: Exception,
    ) -> DepthMomentLookupResult:
        """Bind an optional source failure without publishing partial moments."""

        try:
            identity = self._create_identity(
                admission=admission,
                render_stable_ids_by_projected_row=(
                    render_stable_ids_by_projected_row
                ),
                width=width,
                height=height,
            )
        except Exception as identity_error:
            return self._identity_failure(identity_error)
        return self.unavailable(
            identity,
            reason=_readout_failure_reason(error),
        )

    def unavailable(
        self,
        identity: DepthMomentReadoutIdentity,
        *,
        reason: str,
    ) -> DepthMomentLookupResult:
        return self._record_result(
            self.cache.mark_unavailable(
                identity,
                reason=reason,
                preserve_available=True,
            ),
            terminal=True,
        )


__all__ = [
    "DEPTH_MOMENT_READOUT_SCHEMA_ID",
    "DepthMomentConsumerRegistration",
    "DepthMomentLookupResult",
    "DepthMomentReadoutCache",
    "DepthMomentReadoutError",
    "DepthMomentReadoutIdentity",
    "DepthMomentReadoutRecord",
    "DepthMomentRequestBinding",
    "DepthMomentTargetDependency",
    "DepthMomentTelemetry",
    "DepthMomentTensorDigests",
    "create_depth_moment_readout_identity",
    "projected_row_mapping_digest",
]

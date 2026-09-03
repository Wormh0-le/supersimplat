"""Deterministic component-level Target Scope State shadow records.

The module owns pure schema construction, component lineage, Scope Epoch and
Scope Revision transitions, and exact restoration. It consumes accepted S0
Conservative Seed shadow records without changing production Evidence,
readiness, Candidate, Browser protocol, or Native Selection behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from itertools import product
import json
import math
from threading import Lock
from typing import Any, Final, cast

from .conservative_seed import (
    ConservativeSeedError,
    create_conservative_seed_target_geometry,
    is_conservative_seed_shadow_record,
)
from .digests import route_b_artifact_digest
from .gaussian_evidence_contract import (
    is_evidence_working_set,
    resolve_evidence_working_set_boundary,
)


_VALIDATED_STATE_DIGEST_CACHE_LIMIT: Final = 256
_validated_state_digests: set[str] = set()
_validated_state_digest_order: list[str] = []
_validated_state_digest_lock = Lock()


TARGET_SCOPE_COMPONENT_POLICY_SCHEMA_VERSION: Final = 1
TARGET_SCOPE_STATE_SCHEMA_VERSION: Final = 3
TARGET_SCOPE_STATE_KIND: Final = "target-scope-state/experimental-shadow"
_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_MAX_STABLE_GAUSSIAN_ID: Final = (1 << 32) - 1
_MAX_FINITE_FLOAT: Final = float.fromhex("0x1.fffffffffffffp+1023")
_MIN_POSITIVE_FLOAT: Final = float.fromhex("0x0.0000000000001p-1022")
_POLICY_KEYS: Final = {
    "schemaVersion",
    "policyId",
    "adjacencyScaleMultiplier",
    "boundsScaleMultiplier",
}
TARGET_SCOPE_DISCOVERY_POLICY_SCHEMA_VERSION: Final = 2
TARGET_SCOPE_DISCOVERY_SOURCE_SCHEMA_VERSION: Final = 2
_DISCOVERY_DOMAIN_SCHEMA_VERSION: Final = 2
_DISCOVERY_POLICY_KEYS: Final = {
    "schemaVersion",
    "policyId",
    "maximumSourceRecordsPerEpoch",
    "maximumAdmittedStableGaussianIdsPerEpoch",
    "discoveryDomain",
}
_DISCOVERY_DOMAIN_KEYS: Final = {
    "schemaVersion",
    "domainId",
    "targetGeometryHint",
    "spatialBounds",
    "maximumSourceExtent",
    "maximumDomainDistanceScaleMultiplier",
    "gaussianSupportScaleMultiplier",
}
_DISCOVERY_ARTIFACT_REF_KEYS: Final = {
    "schemaVersion",
    "artifactKind",
    "artifactId",
    "artifactDigest",
    "viewIds",
}
_DISCOVERY_AUTHORITY_COMMON_KEYS: Final = {
    "schemaVersion",
    "authorityKind",
    "producerId",
    "status",
    "resultDigest",
    "derivationPolicyDigest",
    "authorityEvidence",
}
_DISCOVERY_SOURCE_AUTHORITY: Final = {
    "evidence-working-set-boundary-contact": {
        "authorityKind": "boundary-contact-result",
        "producerPrefix": "evidence-working-set-boundary-resolver/",
        "statuses": {"expanded", "failed-closed-boundary-contact"},
        "artifactKind": "gaussian-evidence-artifact",
        "minimumArtifacts": 1,
        "maximumArtifacts": 1,
        "requiresStableAuthority": False,
    },
    "core-external-included-positive-support": {
        "authorityKind": "included-stable-observation",
        "producerPrefix": "included-stable-observation/",
        "statuses": {"included-stable"},
        "artifactKind": "included-stable-observation",
        "minimumArtifacts": 1,
        "maximumArtifacts": 1,
        "requiresStableAuthority": True,
    },
    "coherent-cross-view-support": {
        "authorityKind": "coherent-included-stable-result",
        "producerPrefix": "coherent-included-stable-support/",
        "statuses": {"included-stable"},
        "artifactKind": "included-stable-observation",
        "minimumArtifacts": 2,
        "maximumArtifacts": 8,
        "requiresStableAuthority": True,
    },
    "reviewed-target-local-spatial-support": {
        "authorityKind": "reviewed-target-local-support",
        "producerPrefix": "reviewed-target-local-support/",
        "statuses": {"reviewed"},
        "artifactKind": "target-geometry-hint-review",
        "minimumArtifacts": 1,
        "maximumArtifacts": 1,
        "requiresStableAuthority": False,
    },
    "user-confirmed-expert-recovery": {
        "authorityKind": "user-confirmed-decision",
        "producerPrefix": "user-confirmed-decision/",
        "statuses": {"user-confirmed"},
        "artifactKind": "user-confirmed-decision",
        "minimumArtifacts": 1,
        "maximumArtifacts": 1,
        "requiresStableAuthority": True,
    },
}
_DISCOVERY_SOURCE_INPUT_KEYS: Final = {
    "schemaVersion",
    "sourceKind",
    "targetSplatId",
    "dependencyToken",
    "scopeEpochId",
    "targetGeometryDigest",
    "componentPolicyDigest",
    "discoveryPolicyDigest",
    "discoveryDomainDigest",
    "sourceArtifactRefs",
    "sourceAuthority",
    "admittedStableGaussianIds",
    "spatialBounds",
    "reason",
}
_DISCOVERY_SOURCE_KEYS: Final = _DISCOVERY_SOURCE_INPUT_KEYS | {
    "sourceAuthorityDigest",
    "derivedResultDigest",
    "sourceRecordDigest",
}
_NON_REJECTION_DISCOVERY_KINDS: Final = {
    "low-visibility",
    "low-support",
    "s1-failure",
    "s1-depth-unavailable",
    "technical-failure",
}
_TARGET_SCOPE_REVISION_KINDS: Final = {
    "new-observation",
    "scope-transition",
    *_NON_REJECTION_DISCOVERY_KINDS,
}
_SUBCOMPONENT_DECISION_POLICY_ID: Final = (
    "target-scope-subcomponents/explicit-stable-id-partition-v1"
)
_SUBCOMPONENT_DECISION_KEYS: Final = {
    "schemaVersion",
    "policyId",
    "parentComponentId",
    "parentStableGaussianIds",
    "childStableGaussianIdPartitions",
    "provenanceDigests",
}
_STATE_KEYS: Final = {
    "schemaVersion",
    "stateKind",
    "status",
    "scopeEpochId",
    "scopeRevision",
    "epochBinding",
    "requestBinding",
    "targetSplatId",
    "targetStableGaussianIds",
    "targetGeometryDigest",
    "targetGeometry",
    "coreStableGaussianIds",
    "coreComponents",
    "discoveryEnvelopeLedger",
    "activeFrontierStableGaussianIds",
    "activeFrontierComponents",
    "rejectedFrontierStableGaussianIds",
    "rejectedFrontierComponents",
    "rejectedFrontierLedger",
    "requiredContextStableGaussianIds",
    "seedPartition",
    "seedRecord",
    "componentPolicy",
    "componentPolicyDigest",
    "discoveryPolicy",
    "discoveryPolicyDigest",
    "componentLineageLedger",
    "subcomponentDecisionLedger",
    "scopeRevisionLedger",
    "revisionProvenanceLedger",
    "provenance",
    "provenanceDigest",
    "stateDigest",
}
_ACTIVE_FRONTIER_STATES: Final = {
    "new",
    "observing",
    "conflicted",
    "promotion-pending",
    "retained",
    "reopened",
}
_EPOCH_ROTATION_REASONS: Final = {
    "authoritative-stable-mask-correction",
    "participation-change",
    "observation-removal",
    "observation-replacement",
    "incompatible-target-dependency-change",
    "target-restart",
}
_LINEAGE_RELATIONS: Final = {
    "introduced",
    "retired",
    "continued",
    "split",
    "merge",
    "resegmented",
}
_COMPONENT_HISTORY_REFERENCE_KEYS: Final = {
    "componentId",
    "stableGaussianIds",
    "state",
    "provenanceDigests",
    "ageRevisions",
    "createdAtScopeRevision",
    "stateEnteredScopeRevision",
}


class TargetScopeStateError(ValueError):
    """Base error for Target Scope State pure-state operations."""


class TargetScopeStateValidationError(TargetScopeStateError):
    """A Target Scope State input or immutable record is malformed."""


class TargetScopeStateTransitionError(TargetScopeStateError):
    """A requested transition violates within-epoch state invariants."""


class TargetScopeStateIncompatibilityError(TargetScopeStateError):
    """A request is incompatible with the bound epoch or restoration identity."""


class TargetScopeStateInternalError(TargetScopeStateError):
    """A constructed Target Scope State violated internal invariants."""


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _contains_negative_zero(value: object) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        return numeric == 0.0 and math.copysign(1.0, numeric) < 0.0
    if isinstance(value, Mapping):
        return any(_contains_negative_zero(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_negative_zero(item) for item in value)
    return False


def _clamp_finite(value: float) -> float:
    if math.isfinite(value):
        return value
    return math.copysign(_MAX_FINITE_FLOAT, value)


def _exp_finite(value: float) -> float:
    try:
        return max(math.exp(value), _MIN_POSITIVE_FLOAT)
    except OverflowError:
        return _MAX_FINITE_FLOAT


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _remember_validated_state_digest(digest_value: str) -> None:
    with _validated_state_digest_lock:
        if digest_value in _validated_state_digests:
            return
        _validated_state_digests.add(digest_value)
        _validated_state_digest_order.append(digest_value)
        if len(_validated_state_digest_order) > _VALIDATED_STATE_DIGEST_CACHE_LIMIT:
            expired = _validated_state_digest_order.pop(0)
            _validated_state_digests.remove(expired)


def _validated_state_digest_is_cached(digest_value: str) -> bool:
    with _validated_state_digest_lock:
        return digest_value in _validated_state_digests


def _nonnegative_safe_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_SAFE_INTEGER
    )


def _stable_id(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_STABLE_GAUSSIAN_ID
    )


def _sorted_stable_ids(value: object, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_stable_id(stable_id) for stable_id in value)
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _canonical_stable_ids(
    value: object,
    *,
    label: str,
    allow_empty: bool = True,
) -> list[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(
            f"{label} Stable Gaussian IDs are invalid."
        )
    stable_ids = list(value)
    if (
        (not allow_empty and not stable_ids)
        or any(not _stable_id(stable_id) for stable_id in stable_ids)
        or len(stable_ids) != len(set(stable_ids))
    ):
        raise TargetScopeStateValidationError(
            f"{label} Stable Gaussian IDs are invalid."
        )
    return sorted(cast(list[int], stable_ids))


def _canonical_digest_list(
    value: object,
    *,
    label: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(
            f"{label} provenance digests are invalid."
        )
    digests = list(value)
    if (
        (not allow_empty and not digests)
        or any(not _digest(item) for item in digests)
        or len(digests) != len(set(digests))
    ):
        raise TargetScopeStateValidationError(
            f"{label} provenance digests are invalid."
        )
    return sorted(cast(list[str], digests))


def _canonical_string_list(
    value: object,
    *,
    label: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(f"{label} values are invalid.")
    strings = list(value)
    if (
        (not allow_empty and not strings)
        or any(
            not isinstance(item, str) or not item.strip() or item != item.strip()
            for item in strings
        )
        or len(strings) != len(set(strings))
    ):
        raise TargetScopeStateValidationError(f"{label} values are invalid.")
    return sorted(cast(list[str], strings))


def _validated_dependency_token(value: object) -> dict[str, str]:
    dependency_keys = {
        "splatId",
        "renderStateToken",
        "geometryToken",
        "gaussianIdentityToken",
        "worldTransformToken",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != dependency_keys
        or any(not _nonempty_string(value.get(key)) for key in dependency_keys)
    ):
        raise TargetScopeStateValidationError(
            "Target Scope dependency token is invalid."
        )
    return cast(dict[str, str], deepcopy(dict(value)))


def _canonical_spatial_bounds(value: object) -> dict[str, list[float]]:
    if not isinstance(value, Mapping) or set(value) != {"minimum", "maximum"}:
        raise TargetScopeStateValidationError(
            "Target Scope discovery spatial bounds are invalid."
        )
    canonical: dict[str, list[float]] = {}
    for name in ("minimum", "maximum"):
        vector = value.get(name)
        if (
            not isinstance(vector, Sequence)
            or isinstance(vector, (str, bytes))
            or len(vector) != 3
            or any(not _finite_number(item) for item in vector)
        ):
            raise TargetScopeStateValidationError(
                "Target Scope discovery spatial bounds are invalid."
            )
        canonical[name] = [
            0.0 if float(item) == 0.0 else float(item) for item in vector
        ]
    if any(
        canonical["minimum"][axis] > canonical["maximum"][axis] for axis in range(3)
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery spatial bounds are invalid."
        )
    return canonical


def _canonical_domain_target_geometry_hint(
    value: object,
) -> dict[str, object] | None:
    if value is None:
        return None
    expected_keys = {
        "schemaVersion",
        "producerId",
        "targetSplatId",
        "sourceArtifactDigest",
        "center",
        "extent",
        "authorityDigest",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise TargetScopeStateValidationError(
            "Discovery domain Target Geometry Hint authority is invalid."
        )
    center = value.get("center")
    extent = value.get("extent")
    if (
        value.get("schemaVersion") != 1
        or value.get("producerId") != "target-geometry-hint-domain/v1"
        or not _nonempty_string(value.get("targetSplatId"))
        or not _digest(value.get("sourceArtifactDigest"))
        or not isinstance(center, Sequence)
        or isinstance(center, (str, bytes))
        or len(center) != 3
        or any(not _finite_number(coordinate) for coordinate in center)
        or not isinstance(extent, Sequence)
        or isinstance(extent, (str, bytes))
        or len(extent) != 3
        or any(
            not _finite_number(coordinate) or float(coordinate) <= 0.0
            for coordinate in extent
        )
    ):
        raise TargetScopeStateValidationError(
            "Discovery domain Target Geometry Hint authority is invalid."
        )
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "producerId": "target-geometry-hint-domain/v1",
        "targetSplatId": value["targetSplatId"],
        "sourceArtifactDigest": value["sourceArtifactDigest"],
        "center": [
            0.0 if float(coordinate) == 0.0 else float(coordinate)
            for coordinate in center
        ],
        "extent": [float(coordinate) for coordinate in extent],
    }
    canonical = {**payload, "authorityDigest": route_b_artifact_digest(payload)}
    if value != canonical:
        raise TargetScopeStateValidationError(
            "Discovery domain Target Geometry Hint authority is invalid."
        )
    return canonical


def _canonical_discovery_domain(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or frozenset(value) not in {
        frozenset(_DISCOVERY_DOMAIN_KEYS),
        frozenset(_DISCOVERY_DOMAIN_KEYS | {"domainDigest"}),
    }:
        raise TargetScopeStateValidationError(
            "Target Scope discovery domain is invalid."
        )
    domain_id = value.get("domainId")
    target_geometry_hint = _canonical_domain_target_geometry_hint(
        value.get("targetGeometryHint")
    )
    extent = value.get("maximumSourceExtent")
    domain_distance_multiplier = value.get("maximumDomainDistanceScaleMultiplier")
    support_multiplier = value.get("gaussianSupportScaleMultiplier")
    if (
        value.get("schemaVersion") != _DISCOVERY_DOMAIN_SCHEMA_VERSION
        or not isinstance(domain_id, str)
        or not domain_id.startswith("target-local-discovery-domain/")
        or "/v" not in domain_id
        or not domain_id.rsplit("/v", 1)[-1].isdigit()
        or not isinstance(extent, Sequence)
        or isinstance(extent, (str, bytes))
        or len(extent) != 3
        or any(not _finite_number(item) or float(item) <= 0.0 for item in extent)
        or not _finite_number(domain_distance_multiplier)
        or float(cast(float, domain_distance_multiplier)) <= 0.0
        or float(cast(float, domain_distance_multiplier)) > 256.0
        or not _finite_number(support_multiplier)
        or float(cast(float, support_multiplier)) <= 0.0
        or float(cast(float, support_multiplier)) > 16.0
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery domain identity or extent is invalid."
        )
    payload: dict[str, object] = {
        "schemaVersion": _DISCOVERY_DOMAIN_SCHEMA_VERSION,
        "domainId": domain_id,
        "targetGeometryHint": target_geometry_hint,
        "spatialBounds": _canonical_spatial_bounds(value.get("spatialBounds")),
        "maximumSourceExtent": [float(item) for item in extent],
        "maximumDomainDistanceScaleMultiplier": float(
            cast(float, domain_distance_multiplier)
        ),
        "gaussianSupportScaleMultiplier": float(cast(float, support_multiplier)),
    }
    canonical = {**payload, "domainDigest": route_b_artifact_digest(payload)}
    if "domainDigest" in value and value["domainDigest"] != canonical["domainDigest"]:
        raise TargetScopeStateValidationError(
            "Target Scope discovery domain digest is invalid."
        )
    return canonical


def create_target_scope_discovery_policy(value: object) -> dict[str, object]:
    """Create one finite, target-local Discovery Envelope policy."""

    if not isinstance(value, Mapping) or set(value) != _DISCOVERY_POLICY_KEYS:
        raise TargetScopeStateValidationError(
            "Target Scope discovery policy is incomplete or has unknown fields."
        )
    policy_id = value.get("policyId")
    maximum_sources = value.get("maximumSourceRecordsPerEpoch")
    maximum_stable_ids = value.get("maximumAdmittedStableGaussianIdsPerEpoch")
    prefix = "target-scope-discovery/experimental-shadow-v"
    if (
        value.get("schemaVersion") != TARGET_SCOPE_DISCOVERY_POLICY_SCHEMA_VERSION
        or not isinstance(policy_id, str)
        or not policy_id.startswith(prefix)
        or not policy_id.removeprefix(prefix).isdigit()
        or not _nonnegative_safe_integer(maximum_sources)
        or int(cast(int, maximum_sources)) <= 0
        or not _nonnegative_safe_integer(maximum_stable_ids)
        or int(cast(int, maximum_stable_ids)) <= 0
        or int(cast(int, maximum_stable_ids)) > _MAX_STABLE_GAUSSIAN_ID + 1
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery policy identity or budget is invalid."
        )
    domain = _canonical_discovery_domain(value.get("discoveryDomain"))
    payload: dict[str, object] = {
        "schemaVersion": TARGET_SCOPE_DISCOVERY_POLICY_SCHEMA_VERSION,
        "policyId": policy_id,
        "maximumSourceRecordsPerEpoch": int(cast(int, maximum_sources)),
        "maximumAdmittedStableGaussianIdsPerEpoch": int(cast(int, maximum_stable_ids)),
        "discoveryDomain": domain,
    }
    return {**payload, "policyDigest": route_b_artifact_digest(payload)}


def validate_target_scope_discovery_policy(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _DISCOVERY_POLICY_KEYS | {
        "policyDigest"
    }:
        raise TargetScopeStateValidationError(
            "Target Scope discovery policy is invalid."
        )
    expected = create_target_scope_discovery_policy(
        {key: value[key] for key in _DISCOVERY_POLICY_KEYS}
    )
    if (
        _contains_negative_zero(value)
        or value.get("policyDigest") != expected["policyDigest"]
        or value != expected
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery policy digest is invalid."
        )
    return expected


def _canonical_discovery_artifact_refs(
    value: object, *, source_kind: str
) -> list[dict[str, object]]:
    authority_contract = _DISCOVERY_SOURCE_AUTHORITY[source_kind]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(
            "Target Scope discovery artifact references are invalid."
        )
    references: list[dict[str, object]] = []
    for reference in value:
        if (
            not isinstance(reference, Mapping)
            or set(reference) != _DISCOVERY_ARTIFACT_REF_KEYS
        ):
            raise TargetScopeStateValidationError(
                "Target Scope discovery artifact reference is invalid."
            )
        if (
            reference.get("schemaVersion") != 1
            or reference.get("artifactKind") != authority_contract["artifactKind"]
            or not _nonempty_string(reference.get("artifactId"))
            or not _digest(reference.get("artifactDigest"))
        ):
            raise TargetScopeStateValidationError(
                "Target Scope discovery artifact identity is invalid."
            )
        references.append(
            {
                "schemaVersion": 1,
                "artifactKind": reference["artifactKind"],
                "artifactId": str(reference["artifactId"]).strip(),
                "artifactDigest": reference["artifactDigest"],
                "viewIds": _canonical_string_list(
                    reference.get("viewIds"), label="Discovery artifact View"
                ),
            }
        )
    minimum = int(authority_contract["minimumArtifacts"])
    maximum = int(authority_contract["maximumArtifacts"])
    artifact_ids = [str(reference["artifactId"]) for reference in references]
    artifact_digests = [str(reference["artifactDigest"]) for reference in references]
    if (
        not minimum <= len(references) <= maximum
        or len(artifact_ids) != len(set(artifact_ids))
        or len(artifact_digests) != len(set(artifact_digests))
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery artifact cardinality is invalid."
        )
    references.sort(key=route_b_artifact_digest)
    if source_kind == "coherent-cross-view-support":
        coherent_view_lists = [
            cast(list[str], reference["viewIds"]) for reference in references
        ]
        coherent_views = {view_ids[0] for view_ids in coherent_view_lists if view_ids}
        if any(len(view_ids) != 1 for view_ids in coherent_view_lists) or len(
            coherent_views
        ) != len(references):
            raise TargetScopeStateValidationError(
                "Coherent cross-View discovery requires two bound Views."
            )
    return references


def _canonical_boundary_contact_result(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TargetScopeStateValidationError(
            "Boundary-contact authority result is invalid."
        )
    status = value.get("status")
    if status == "failed-closed":
        if (
            set(value) != {"status", "reason", "contactStableGaussianIds"}
            or value.get("reason") != "evidence-working-set-boundary-contact"
        ):
            raise TargetScopeStateValidationError(
                "Boundary-contact authority result is invalid."
            )
        return {
            "status": "failed-closed",
            "reason": "evidence-working-set-boundary-contact",
            "contactStableGaussianIds": _canonical_stable_ids(
                value.get("contactStableGaussianIds"),
                label="Boundary-contact result",
                allow_empty=False,
            ),
        }
    if status == "expanded":
        if set(value) != {
            "status",
            "contactStableGaussianIds",
            "evidenceWorkingSet",
        } or not is_evidence_working_set(value.get("evidenceWorkingSet")):
            raise TargetScopeStateValidationError(
                "Boundary-contact authority result is invalid."
            )
        contact_ids = _canonical_stable_ids(
            value.get("contactStableGaussianIds"),
            label="Boundary-contact result",
            allow_empty=False,
        )
        evidence_working_set = cast(Mapping[str, Any], value["evidenceWorkingSet"])
        if not set(contact_ids).issubset(
            set(cast(list[int], evidence_working_set["stableGaussianIds"]))
        ):
            raise TargetScopeStateValidationError(
                "Expanded boundary authority does not cover contact support."
            )
        return {
            "status": "expanded",
            "contactStableGaussianIds": contact_ids,
            "evidenceWorkingSet": deepcopy(dict(evidence_working_set)),
        }
    raise TargetScopeStateValidationError(
        "Boundary-contact authority result is invalid."
    )


def _canonical_boundary_resolver_input(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TargetScopeStateValidationError(
            "Boundary-contact resolver input is invalid."
        )
    replay_result = resolve_evidence_working_set_boundary(value)
    try:
        _canonical_boundary_contact_result(replay_result)
    except TargetScopeStateValidationError as error:
        raise TargetScopeStateValidationError(
            "Boundary-contact resolver input is invalid."
        ) from error
    return deepcopy(dict(value))


def _canonical_boundary_resolver_binding(value: object) -> dict[str, object]:
    expected_keys = {
        "schemaVersion",
        "targetSplatId",
        "dependencyToken",
        "renderWorkingSetToken",
        "evidenceWorkingSetToken",
    }
    if (
        not isinstance(value, Mapping)
        or value.get("schemaVersion") != 1
        or set(value) != expected_keys
        or not _nonempty_string(value.get("targetSplatId"))
        or not _digest(value.get("renderWorkingSetToken"))
        or not _digest(value.get("evidenceWorkingSetToken"))
    ):
        raise TargetScopeStateValidationError(
            "Boundary-contact resolver binding is invalid."
        )
    canonical = {key: deepcopy(value[key]) for key in sorted(expected_keys)}
    canonical["dependencyToken"] = _validated_dependency_token(
        value.get("dependencyToken")
    )
    return canonical


def _canonical_discovery_authority(
    value: object, *, source_kind: str
) -> dict[str, object]:
    contract = _DISCOVERY_SOURCE_AUTHORITY[source_kind]
    expected_keys = set(_DISCOVERY_AUTHORITY_COMMON_KEYS)
    evidence_keys = {
        "schemaVersion",
        "producerId",
        "status",
        "derivationPolicyDigest",
        "sourceArtifactRefs",
    }
    if bool(contract["requiresStableAuthority"]):
        expected_keys |= {"participation", "stableMaskDigest"}
        evidence_keys |= {"participation", "stableMaskDigest"}
    if source_kind == "evidence-working-set-boundary-contact":
        evidence_keys |= {"boundaryBinding", "boundaryInput", "boundaryResult"}
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise TargetScopeStateValidationError(
            "Target Scope discovery source authority is incomplete."
        )
    producer_id = value.get("producerId")
    evidence = value.get("authorityEvidence")
    if (
        value.get("schemaVersion") != 1
        or value.get("authorityKind") != contract["authorityKind"]
        or value.get("status") not in contract["statuses"]
        or not isinstance(producer_id, str)
        or not producer_id.startswith(str(contract["producerPrefix"]))
        or "/v" not in producer_id
        or not producer_id.rsplit("/v", 1)[-1].isdigit()
        or not _digest(value.get("resultDigest"))
        or not _digest(value.get("derivationPolicyDigest"))
        or not isinstance(evidence, Mapping)
        or set(evidence) != evidence_keys
        or evidence.get("schemaVersion") != 1
        or evidence.get("producerId") != producer_id
        or evidence.get("status") != value.get("status")
        or evidence.get("derivationPolicyDigest") != value.get("derivationPolicyDigest")
        or (
            bool(contract["requiresStableAuthority"])
            and (
                value.get("participation") != "included"
                or not _digest(value.get("stableMaskDigest"))
                or evidence.get("participation") != value.get("participation")
                or evidence.get("stableMaskDigest") != value.get("stableMaskDigest")
            )
        )
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery source authority is invalid."
        )
    canonical_evidence = deepcopy(dict(cast(Mapping[str, Any], evidence)))
    canonical_evidence["sourceArtifactRefs"] = _canonical_discovery_artifact_refs(
        evidence.get("sourceArtifactRefs"), source_kind=source_kind
    )
    if source_kind == "evidence-working-set-boundary-contact":
        canonical_evidence["boundaryBinding"] = _canonical_boundary_resolver_binding(
            evidence.get("boundaryBinding")
        )
        canonical_input = _canonical_boundary_resolver_input(
            evidence.get("boundaryInput")
        )
        canonical_evidence["boundaryInput"] = canonical_input
        canonical_evidence["boundaryResult"] = _canonical_boundary_contact_result(
            evidence.get("boundaryResult")
        )
        replay_result = _canonical_boundary_contact_result(
            resolve_evidence_working_set_boundary(canonical_input)
        )
        boundary_binding = cast(
            Mapping[str, Any], canonical_evidence["boundaryBinding"]
        )
        render_working_set = cast(
            Mapping[str, Any], canonical_input["renderWorkingSet"]
        )
        evidence_working_set = cast(
            Mapping[str, Any], canonical_input["evidenceWorkingSet"]
        )
        if (
            canonical_evidence["boundaryResult"] != replay_result
            or render_working_set["dependencyToken"]
            != boundary_binding["dependencyToken"]
            or render_working_set["targetSplatId"] != boundary_binding["targetSplatId"]
            or evidence_working_set["targetSplatId"]
            != boundary_binding["targetSplatId"]
            or render_working_set["renderWorkingSetToken"]
            != boundary_binding["renderWorkingSetToken"]
            or evidence_working_set["evidenceWorkingSetToken"]
            != boundary_binding["evidenceWorkingSetToken"]
        ):
            raise TargetScopeStateValidationError(
                "Boundary-contact authority does not replay against its binding."
            )
    if evidence != canonical_evidence or value.get(
        "resultDigest"
    ) != route_b_artifact_digest(canonical_evidence):
        raise TargetScopeStateValidationError(
            "Target Scope discovery authority result digest is invalid."
        )
    canonical = {key: deepcopy(value[key]) for key in sorted(expected_keys)}
    canonical["authorityEvidence"] = canonical_evidence
    return canonical


def _create_target_scope_discovery_source(value: object) -> dict[str, object]:
    """Create one typed, epoch-bound seed-independent discovery source."""

    if not isinstance(value, Mapping) or set(value) != _DISCOVERY_SOURCE_INPUT_KEYS:
        raise TargetScopeStateValidationError(
            "Target Scope discovery source is incomplete or has unknown fields."
        )
    source_kind = value.get("sourceKind")
    target_splat_id = value.get("targetSplatId")
    reason = value.get("reason")
    if (
        value.get("schemaVersion") != TARGET_SCOPE_DISCOVERY_SOURCE_SCHEMA_VERSION
        or not isinstance(source_kind, str)
        or source_kind not in _DISCOVERY_SOURCE_AUTHORITY
        or not _nonempty_string(target_splat_id)
        or not isinstance(reason, str)
        or not reason.strip()
        or not _digest(value.get("scopeEpochId"))
        or not _digest(value.get("targetGeometryDigest"))
        or not _digest(value.get("componentPolicyDigest"))
        or not _digest(value.get("discoveryPolicyDigest"))
        or not _digest(value.get("discoveryDomainDigest"))
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery source identity is invalid."
        )
    dependency = _validated_dependency_token(value.get("dependencyToken"))
    if dependency["splatId"] != target_splat_id:
        raise TargetScopeStateValidationError(
            "Target Scope discovery source target dependency is invalid."
        )
    references = _canonical_discovery_artifact_refs(
        value.get("sourceArtifactRefs"), source_kind=source_kind
    )
    authority = _canonical_discovery_authority(
        value.get("sourceAuthority"), source_kind=source_kind
    )
    authority_evidence = cast(Mapping[str, Any], authority["authorityEvidence"])
    if authority_evidence["sourceArtifactRefs"] != references:
        raise TargetScopeStateValidationError(
            "Discovery source artifacts do not match authority evidence."
        )
    if source_kind == "evidence-working-set-boundary-contact":
        boundary_binding = cast(
            Mapping[str, Any], authority_evidence["boundaryBinding"]
        )
        if (
            boundary_binding["targetSplatId"] != target_splat_id
            or boundary_binding["dependencyToken"] != dependency
        ):
            raise TargetScopeStateValidationError(
                "Boundary-contact authority binding does not match discovery target."
            )
    admitted_ids = _canonical_stable_ids(
        value.get("admittedStableGaussianIds"),
        label="Discovery source",
        allow_empty=False,
    )
    if source_kind == "evidence-working-set-boundary-contact":
        boundary_result = cast(Mapping[str, Any], authority_evidence["boundaryResult"])
        if admitted_ids != boundary_result["contactStableGaussianIds"]:
            raise TargetScopeStateValidationError(
                "Boundary-contact authority IDs do not match derived support."
            )
    bounds = _canonical_spatial_bounds(value.get("spatialBounds"))
    authority_payload: dict[str, object] = {
        "schemaVersion": TARGET_SCOPE_DISCOVERY_SOURCE_SCHEMA_VERSION,
        "sourceKind": source_kind,
        "targetSplatId": target_splat_id,
        "dependencyToken": dependency,
        "scopeEpochId": value["scopeEpochId"],
        "targetGeometryDigest": value["targetGeometryDigest"],
        "componentPolicyDigest": value["componentPolicyDigest"],
        "discoveryPolicyDigest": value["discoveryPolicyDigest"],
        "discoveryDomainDigest": value["discoveryDomainDigest"],
        "sourceArtifactRefs": references,
        "sourceAuthority": authority,
    }
    source_authority_digest = route_b_artifact_digest(authority_payload)
    derived_payload: dict[str, object] = {
        "sourceAuthorityDigest": source_authority_digest,
        "admittedStableGaussianIds": admitted_ids,
        "spatialBounds": bounds,
    }
    derived_result_digest = route_b_artifact_digest(derived_payload)
    record_payload: dict[str, object] = {
        **authority_payload,
        "sourceAuthorityDigest": source_authority_digest,
        "admittedStableGaussianIds": admitted_ids,
        "spatialBounds": bounds,
        "reason": reason.strip(),
        "derivedResultDigest": derived_result_digest,
    }
    return {
        **record_payload,
        "sourceRecordDigest": route_b_artifact_digest(record_payload),
    }


def _validate_target_scope_discovery_source(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _DISCOVERY_SOURCE_KEYS:
        raise TargetScopeStateValidationError(
            "Target Scope discovery source is invalid."
        )
    expected = _create_target_scope_discovery_source(
        {key: value[key] for key in _DISCOVERY_SOURCE_INPUT_KEYS}
    )
    bounds = cast(Mapping[str, Sequence[float]], value["spatialBounds"])
    if value != expected or any(
        float(coordinate) == 0.0 and math.copysign(1.0, float(coordinate)) < 0.0
        for vector in bounds.values()
        for coordinate in vector
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery source record is not canonical."
        )
    return expected


def _validated_request_binding(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "targetContextId",
        "contextRevision",
        "dependencyToken",
    }:
        raise TargetScopeStateValidationError(
            "Target Scope request binding is invalid."
        )
    dependency = value.get("dependencyToken")
    dependency_keys = {
        "splatId",
        "renderStateToken",
        "geometryToken",
        "gaussianIdentityToken",
        "worldTransformToken",
    }
    if (
        not _nonempty_string(value.get("targetContextId"))
        or not _nonnegative_safe_integer(value.get("contextRevision"))
        or not isinstance(dependency, Mapping)
        or set(dependency) != dependency_keys
        or any(not _nonempty_string(dependency.get(key)) for key in dependency_keys)
    ):
        raise TargetScopeStateValidationError(
            "Target Scope request binding is invalid."
        )
    return deepcopy(dict(value))


def create_target_scope_component_policy(value: object) -> dict[str, object]:
    """Validate one explicit experimental componentization policy."""

    if not isinstance(value, Mapping) or set(value) != _POLICY_KEYS:
        raise TargetScopeStateValidationError(
            "Target Scope component policy is incomplete or has unknown fields."
        )
    policy_id = value.get("policyId")
    if (
        value.get("schemaVersion") != TARGET_SCOPE_COMPONENT_POLICY_SCHEMA_VERSION
        or not isinstance(policy_id, str)
        or not policy_id.startswith("target-scope-components/experimental-shadow-v")
        or not policy_id.removeprefix(
            "target-scope-components/experimental-shadow-v"
        ).isdigit()
        or not _finite_number(value.get("adjacencyScaleMultiplier"))
        or float(value["adjacencyScaleMultiplier"]) <= 0.0
        or not _finite_number(value.get("boundsScaleMultiplier"))
        or float(value["boundsScaleMultiplier"]) <= 0.0
    ):
        raise TargetScopeStateValidationError(
            "Target Scope component policy identity or bounds are invalid."
        )
    payload: dict[str, object] = {
        "schemaVersion": TARGET_SCOPE_COMPONENT_POLICY_SCHEMA_VERSION,
        "policyId": policy_id,
        "adjacencyScaleMultiplier": float(value["adjacencyScaleMultiplier"]),
        "boundsScaleMultiplier": float(value["boundsScaleMultiplier"]),
    }
    return {**payload, "policyDigest": route_b_artifact_digest(payload)}


def validate_target_scope_component_policy(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _POLICY_KEYS | {"policyDigest"}:
        raise TargetScopeStateValidationError(
            "Target Scope component policy is invalid."
        )
    expected = create_target_scope_component_policy(
        {key: value[key] for key in _POLICY_KEYS}
    )
    if value.get("policyDigest") != expected["policyDigest"]:
        raise TargetScopeStateValidationError(
            "Target Scope component policy digest is invalid."
        )
    return expected


def create_target_scope_subcomponent_decision(
    value: object,
) -> dict[str, object]:
    """Create one versioned, provenance-bound deterministic split decision."""

    if (
        not isinstance(value, Mapping)
        or set(value) != _SUBCOMPONENT_DECISION_KEYS
        or value.get("schemaVersion") != 1
        or value.get("policyId") != _SUBCOMPONENT_DECISION_POLICY_ID
        or not _digest(value.get("parentComponentId"))
    ):
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decision is invalid."
        )
    parent_ids = _canonical_stable_ids(
        value.get("parentStableGaussianIds"),
        label="Subcomponent parent",
        allow_empty=False,
    )
    raw_partitions = value.get("childStableGaussianIdPartitions")
    if (
        not isinstance(raw_partitions, Sequence)
        or isinstance(raw_partitions, (str, bytes))
        or len(raw_partitions) < 2
    ):
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decision requires at least two children."
        )
    partitions = [
        _canonical_stable_ids(
            partition,
            label="Subcomponent child",
            allow_empty=False,
        )
        for partition in raw_partitions
    ]
    partitions.sort(key=lambda partition: partition[0])
    flattened = [stable_id for partition in partitions for stable_id in partition]
    if len(flattened) != len(set(flattened)) or sorted(flattened) != parent_ids:
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent children must exactly partition the parent."
        )
    provenance = _canonical_digest_list(
        value.get("provenanceDigests"),
        label="Subcomponent decision",
    )
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "policyId": _SUBCOMPONENT_DECISION_POLICY_ID,
        "parentComponentId": value["parentComponentId"],
        "parentStableGaussianIds": parent_ids,
        "childStableGaussianIdPartitions": partitions,
        "provenanceDigests": provenance,
    }
    return {**payload, "decisionDigest": route_b_artifact_digest(payload)}


def validate_target_scope_subcomponent_decision(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _SUBCOMPONENT_DECISION_KEYS | {
        "decisionDigest"
    }:
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decision is invalid."
        )
    expected = create_target_scope_subcomponent_decision(
        {key: value[key] for key in _SUBCOMPONENT_DECISION_KEYS}
    )
    if value.get("decisionDigest") != expected["decisionDigest"]:
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decision digest is invalid."
        )
    return expected


def _canonical_subcomponent_decisions(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decisions are invalid."
        )
    decisions = [
        cast(
            dict[str, Any],
            validate_target_scope_subcomponent_decision(decision),
        )
        for decision in value
    ]
    decisions.sort(key=lambda decision: str(decision["decisionDigest"]))
    if len(decisions) != len(
        {decision["decisionDigest"] for decision in decisions}
    ) or len(decisions) != len(
        {decision["parentComponentId"] for decision in decisions}
    ):
        raise TargetScopeStateValidationError(
            "Target Scope subcomponent decisions are duplicated."
        )
    return decisions


def _validated_geometry(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schemaVersion",
        "targetSplatId",
        "stableGaussianIds",
        "rows",
        "geometryDigest",
    }:
        raise TargetScopeStateValidationError(
            "Target Scope geometry record is invalid."
        )
    try:
        expected = create_conservative_seed_target_geometry(
            target_splat_id=value.get("targetSplatId"),
            rows=value.get("rows"),
        )
    except ConservativeSeedError as error:
        raise TargetScopeStateValidationError(
            "Target Scope geometry record is invalid."
        ) from error
    if (
        value.get("schemaVersion") != expected["schemaVersion"]
        or value.get("stableGaussianIds") != expected["stableGaussianIds"]
        or value.get("geometryDigest") != expected["geometryDigest"]
    ):
        raise TargetScopeStateValidationError(
            "Target Scope geometry identity is invalid."
        )
    return cast(dict[str, Any], expected)


def _connected_index_groups(
    count: int,
    is_connected: Callable[[int, int], bool],
) -> list[list[int]]:
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(count):
        for right in range(left + 1, count):
            if not is_connected(left, right):
                continue
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(left_root, right_root)
    grouped: dict[int, list[int]] = {}
    for index in range(count):
        grouped.setdefault(find(index), []).append(index)
    return sorted(grouped.values(), key=lambda group: group[0])


def _connected_groups(
    rows: list[dict[str, Any]],
    adjacency_scale_multiplier: float,
) -> list[list[dict[str, Any]]]:
    def adjacent(left_index: int, right_index: int) -> bool:
        left = rows[left_index]
        right = rows[right_index]
        scale = max(
            float(left["maximumScale"]),
            float(right["maximumScale"]),
        )
        normalized_left = [float(coordinate) / scale for coordinate in left["center"]]
        normalized_right = [float(coordinate) / scale for coordinate in right["center"]]
        return (
            math.dist(normalized_left, normalized_right) <= adjacency_scale_multiplier
        )

    return [
        [rows[index] for index in group]
        for group in _connected_index_groups(len(rows), adjacent)
    ]


def _component_identity(
    *,
    target_splat_id: str,
    target_geometry_digest: str,
    component_policy_digest: str,
    stable_ids: list[int],
) -> str:
    return route_b_artifact_digest(
        {
            "schemaVersion": 1,
            "targetSplatId": target_splat_id,
            "targetGeometryDigest": target_geometry_digest,
            "componentPolicyDigest": component_policy_digest,
            "stableGaussianIds": stable_ids,
        }
    )


def _component_skeletons(
    *,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
    stable_ids: list[int],
    state: str,
    provenance_digests: list[str],
) -> list[dict[str, Any]]:
    selected = set(stable_ids)
    rows: list[dict[str, Any]] = []
    for source in geometry["rows"]:
        stable_id = int(source["stableGaussianId"])
        if stable_id not in selected:
            continue
        log_scales = [float(value) for value in source["logScales"]]
        rows.append(
            {
                "stableGaussianId": stable_id,
                "center": [float(value) for value in source["center"]],
                "maximumScale": _exp_finite(max(log_scales)),
                "logScaleVolume": sum(log_scales),
            }
        )
    groups = (
        _connected_groups(rows, float(policy["adjacencyScaleMultiplier"]))
        if rows
        else []
    )
    result: list[dict[str, Any]] = []
    radius_multiplier = float(policy["boundsScaleMultiplier"])
    for group in groups:
        ids = [int(row["stableGaussianId"]) for row in group]
        component_id = _component_identity(
            target_splat_id=str(geometry["targetSplatId"]),
            target_geometry_digest=str(geometry["geometryDigest"]),
            component_policy_digest=str(policy["policyDigest"]),
            stable_ids=ids,
        )
        minimum = [_MAX_FINITE_FLOAT, _MAX_FINITE_FLOAT, _MAX_FINITE_FLOAT]
        maximum = [-_MAX_FINITE_FLOAT, -_MAX_FINITE_FLOAT, -_MAX_FINITE_FLOAT]
        for row in group:
            radius = _clamp_finite(radius_multiplier * float(row["maximumScale"]))
            for axis in range(3):
                center = float(row["center"][axis])
                minimum[axis] = min(
                    minimum[axis],
                    _clamp_finite(center - radius),
                )
                maximum[axis] = max(
                    maximum[axis],
                    _clamp_finite(center + radius),
                )
        result.append(
            {
                "componentId": component_id,
                "stableGaussianIds": ids,
                "worldSpaceBounds": {"minimum": minimum, "maximum": maximum},
                "materialSummary": {
                    "gaussianCount": len(ids),
                    "totalLogScaleVolume": _clamp_finite(
                        sum(float(row["logScaleVolume"]) for row in group)
                    ),
                    "maximumDeclaredScale": max(
                        float(row["maximumScale"]) for row in group
                    ),
                },
                "state": state,
                "provenanceDigests": list(provenance_digests),
            }
        )
    return result


def _canonical_frontier_groups(
    value: object,
    *,
    rejected: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetScopeStateValidationError(
            "Target Scope Frontier groups are invalid."
        )
    merged: dict[tuple[str, tuple[str, ...]], set[int]] = {}
    observed: set[int] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {
            "stableGaussianIds",
            "state",
            "provenanceDigests",
        }:
            raise TargetScopeStateValidationError(
                "Target Scope Frontier group is invalid."
            )
        state = item.get("state")
        if (
            not isinstance(state, str)
            or (rejected and state != "rejected")
            or (not rejected and state not in _ACTIVE_FRONTIER_STATES)
        ):
            raise TargetScopeStateValidationError(
                "Target Scope Frontier state is invalid."
            )
        stable_ids = _canonical_stable_ids(
            item.get("stableGaussianIds"),
            label="Frontier",
            allow_empty=False,
        )
        if observed.intersection(stable_ids):
            raise TargetScopeStateValidationError(
                "Target Scope Frontier Stable Gaussian IDs are duplicated."
            )
        observed.update(stable_ids)
        provenance = _canonical_digest_list(
            item.get("provenanceDigests"),
            label="Frontier",
        )
        merged.setdefault((state, tuple(provenance)), set()).update(stable_ids)
    groups = [
        {
            "stableGaussianIds": sorted(stable_ids),
            "state": key[0],
            "provenanceDigests": list(key[1]),
        }
        for key, stable_ids in merged.items()
    ]
    groups.sort(
        key=lambda group: (
            int(group["stableGaussianIds"][0]),
            str(group["state"]),
            tuple(group["provenanceDigests"]),
        )
    )
    return groups


def _frontier_skeletons(
    *,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not groups:
        return []
    all_ids = sorted(
        stable_id for group in groups for stable_id in group["stableGaussianIds"]
    )
    partition = _component_skeletons(
        geometry=geometry,
        policy=policy,
        stable_ids=all_ids,
        state="partition",
        provenance_digests=[],
    )
    group_by_id: dict[int, dict[str, Any]] = {}
    for group in groups:
        for stable_id in group["stableGaussianIds"]:
            group_by_id[stable_id] = group
    result: list[dict[str, Any]] = []
    for component in partition:
        component_groups = {
            (
                str(group_by_id[stable_id]["state"]),
                tuple(group_by_id[stable_id]["provenanceDigests"]),
            )
            for stable_id in component["stableGaussianIds"]
        }
        if len(component_groups) != 1:
            raise TargetScopeStateTransitionError(
                "A deterministic component cannot be split by state labels; "
                "change component membership through an explicit Scope transition."
            )
        state, provenance = next(iter(component_groups))
        component["state"] = state
        component["provenanceDigests"] = list(provenance)
        result.append(component)
    result.sort(key=lambda component: int(component["stableGaussianIds"][0]))
    return result


def _state_components(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        *cast(list[dict[str, Any]], value["coreComponents"]),
        *cast(list[dict[str, Any]], value["activeFrontierComponents"]),
        *cast(list[dict[str, Any]], value["rejectedFrontierComponents"]),
    ]


def _lineage_relation(
    *,
    parent_count: int,
    child_count: int,
    same_membership: bool,
) -> str:
    if parent_count == 0:
        return "introduced"
    if child_count == 0:
        return "retired"
    if parent_count == 1 and child_count > 1:
        return "split"
    if parent_count > 1 and child_count == 1:
        return "merge"
    if parent_count == 1 and child_count == 1 and same_membership:
        return "continued"
    return "resegmented"


def _component_history_reference(
    component: Mapping[str, Any],
) -> dict[str, Any]:
    return {key: deepcopy(component[key]) for key in _COMPONENT_HISTORY_REFERENCE_KEYS}


def _transition_child_reference(
    *,
    child: Mapping[str, Any],
    parents: list[dict[str, Any]],
    scope_revision: int,
    revision_source_digests: list[str],
) -> dict[str, Any]:
    component_id = str(child["componentId"])
    members = set(child["stableGaussianIds"])
    overlapping = [
        parent
        for parent in parents
        if members.intersection(parent["stableGaussianIds"])
    ]
    previous = next(
        (parent for parent in overlapping if parent["componentId"] == component_id),
        None,
    )
    created_at_scope_revision = scope_revision
    state_entered_scope_revision = scope_revision
    if previous is not None:
        created_at_scope_revision = int(previous["createdAtScopeRevision"])
        if previous["state"] == child["state"]:
            state_entered_scope_revision = int(previous["stateEnteredScopeRevision"])
    provenance = set(revision_source_digests)
    for parent in overlapping:
        provenance.update(parent["provenanceDigests"])
    declared_provenance = set(child["provenanceDigests"])
    if not declared_provenance.issubset(provenance):
        raise TargetScopeStateTransitionError(
            "Component provenance must be bound by the revision or parent history."
        )
    return {
        "componentId": component_id,
        "stableGaussianIds": list(child["stableGaussianIds"]),
        "state": str(child["state"]),
        "provenanceDigests": sorted(provenance),
        "ageRevisions": (scope_revision - state_entered_scope_revision),
        "createdAtScopeRevision": created_at_scope_revision,
        "stateEnteredScopeRevision": state_entered_scope_revision,
    }


def _transition_lineage(
    *,
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
    from_revision: int | None,
    to_revision: int,
    subcomponent_decisions: list[dict[str, Any]],
    revision_source_digests: list[str],
    context_stable_gaussian_ids: list[int],
) -> list[dict[str, Any]]:
    parent_sets = [set(component["stableGaussianIds"]) for component in parents]
    child_sets = [set(component["stableGaussianIds"]) for component in children]
    parent_count = len(parents)
    count = parent_count + len(children)

    def lineage_connected(left: int, right: int) -> bool:
        if left >= parent_count or right < parent_count:
            return False
        return bool(parent_sets[left] & child_sets[right - parent_count])

    index_groups = _connected_index_groups(count, lineage_connected)
    decisions_by_parent = {
        str(decision["parentComponentId"]): decision
        for decision in subcomponent_decisions
    }
    used_decision_digests: set[str] = set()
    records: list[dict[str, Any]] = []
    context_set: set[int] = set(context_stable_gaussian_ids)
    for indices in index_groups:
        parent_components = [
            parents[index] for index in indices if index < parent_count
        ]
        child_components = [
            children[index - parent_count] for index in indices if index >= parent_count
        ]
        parent_refs = sorted(
            (
                _component_history_reference(component)
                for component in parent_components
            ),
            key=lambda reference: str(reference["componentId"]),
        )
        child_refs = sorted(
            (
                _transition_child_reference(
                    child=component,
                    parents=parent_components,
                    scope_revision=to_revision,
                    revision_source_digests=revision_source_digests,
                )
                for component in child_components
            ),
            key=lambda reference: str(reference["componentId"]),
        )
        parent_ids = [str(reference["componentId"]) for reference in parent_refs]
        child_ids = [str(reference["componentId"]) for reference in child_refs]
        parent_members = (
            set().union(
                *(
                    set(component["stableGaussianIds"])
                    for component in parent_components
                )
            )
            if parent_components
            else set()
        )
        child_members = (
            set().union(
                *(set(component["stableGaussianIds"]) for component in child_components)
            )
            if child_components
            else set()
        )
        relation = _lineage_relation(
            parent_count=len(parent_components),
            child_count=len(child_components),
            same_membership=parent_members == child_members,
        )
        decision_digests: list[str] = []
        for parent in parent_components:
            parent_id = str(parent["componentId"])
            parent_membership: set[int] = set(
                cast(list[int], parent["stableGaussianIds"])
            )
            component_partitions: list[list[int]] = [
                sorted(
                    parent_membership & set(cast(list[int], child["stableGaussianIds"]))
                )
                for child in child_components
                if parent_membership & set(cast(list[int], child["stableGaussianIds"]))
            ]
            retained_members: set[int] = {
                stable_id
                for partition in component_partitions
                for stable_id in partition
            }
            retired_members = parent_membership - retained_members
            retired_to_context: list[int] = sorted(retired_members & context_set)
            retired_out_of_scope: list[int] = sorted(retired_members - context_set)
            disposition_partitions: list[list[int]] = sorted(
                component_partitions
                + ([retired_to_context] if retired_to_context else [])
                + ([retired_out_of_scope] if retired_out_of_scope else []),
                key=lambda partition: partition[0],
            )
            requires_decision = len(disposition_partitions) > 1
            decision = decisions_by_parent.get(parent_id)
            if not requires_decision:
                if decision is not None:
                    raise TargetScopeStateTransitionError(
                        "A subcomponent decision was supplied for an intact component."
                    )
                continue
            if (
                decision is None
                or decision["parentStableGaussianIds"] != parent["stableGaussianIds"]
                or decision["childStableGaussianIdPartitions"] != disposition_partitions
                or not set(cast(list[str], decision["provenanceDigests"])).issubset(
                    revision_source_digests
                )
            ):
                raise TargetScopeStateTransitionError(
                    "Partial component membership requires an exact versioned "
                    "subcomponent decision."
                )
            decision_digest = str(decision["decisionDigest"])
            decision_digests.append(decision_digest)
            used_decision_digests.add(decision_digest)
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "relation": relation,
            "fromScopeRevision": from_revision,
            "toScopeRevision": to_revision,
            "revisionSourceDigests": list(revision_source_digests),
            "parentComponentIds": parent_ids,
            "childComponentIds": child_ids,
            "parentMemberships": parent_refs,
            "childMemberships": child_refs,
            "sharedStableGaussianIds": sorted(parent_members & child_members),
            "introducedStableGaussianIds": sorted(child_members - parent_members),
            "retiredStableGaussianIds": sorted(parent_members - child_members),
            "retiredToContextStableGaussianIds": sorted(
                (parent_members - child_members) & context_set
            ),
            "retiredOutOfScopeStableGaussianIds": sorted(
                (parent_members - child_members) - context_set
            ),
            "subcomponentDecisionDigests": sorted(decision_digests),
        }
        records.append(
            {
                **payload,
                "lineageDigest": route_b_artifact_digest(payload),
            }
        )
    supplied_decision_digests = {
        str(decision["decisionDigest"]) for decision in subcomponent_decisions
    }
    if used_decision_digests != supplied_decision_digests:
        raise TargetScopeStateTransitionError(
            "Every subcomponent decision must bind exactly one component split."
        )
    records.sort(key=lambda record: str(record["lineageDigest"]))
    return records


def _bind_components(
    *,
    skeletons: list[dict[str, Any]],
    lineage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    references_by_id = {
        str(reference["componentId"]): reference
        for record in lineage
        for reference in record["childMemberships"]
    }
    result: list[dict[str, Any]] = []
    for skeleton in skeletons:
        component_id = str(skeleton["componentId"])
        reference = references_by_id.get(component_id)
        if reference is None:
            raise TargetScopeStateInternalError(
                "A current component is missing its lineage history."
            )
        payload: dict[str, object] = {
            **deepcopy(skeleton),
            "provenanceDigests": deepcopy(reference["provenanceDigests"]),
            "lineageRecordDigests": sorted(
                str(record["lineageDigest"])
                for record in lineage
                if component_id in record["childComponentIds"]
            ),
            "ageRevisions": reference["ageRevisions"],
            "createdAtScopeRevision": reference["createdAtScopeRevision"],
            "stateEnteredScopeRevision": reference["stateEnteredScopeRevision"],
        }
        result.append(
            {
                **payload,
                "componentDigest": route_b_artifact_digest(payload),
            }
        )
    result.sort(key=lambda component: int(component["stableGaussianIds"][0]))
    return result


def _append_rejected_frontier_events(
    *,
    previous_ledger: list[dict[str, Any]],
    rejected_components: list[dict[str, Any]],
    active_components: list[dict[str, Any]],
    scope_revision: int,
    authorized_reopen_sources: Mapping[str, set[int]],
) -> list[dict[str, Any]]:
    latest_by_component: dict[str, Mapping[str, Any]] = {}
    for event in previous_ledger:
        latest_by_component[str(event["componentId"])] = event
    latest_rejections = [
        event for event in latest_by_component.values() if event["event"] == "rejected"
    ]

    reopen_pairs: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for component in active_components:
        component_ids = set(component["stableGaussianIds"])
        overlapping_rejections = [
            event
            for event in latest_rejections
            if component_ids & set(event["stableGaussianIds"])
        ]
        if any(
            not set(event["stableGaussianIds"]).issubset(component_ids)
            for event in overlapping_rejections
        ):
            raise TargetScopeStateTransitionError(
                "A rejected Frontier component requires complete component provenance to reopen."
            )
        if overlapping_rejections and (
            component["state"] != "reopened"
            or component["stateEnteredScopeRevision"] != scope_revision
        ):
            raise TargetScopeStateTransitionError(
                "A rejected Frontier component must explicitly reopen."
            )
        if (
            component["state"] == "reopened"
            and component["stateEnteredScopeRevision"] == scope_revision
            and not overlapping_rejections
        ):
            raise TargetScopeStateTransitionError(
                "Rejected Frontier event history is invalid."
            )
        reopen_pairs.extend((event, component) for event in overlapping_rejections)

    appended: list[dict[str, Any]] = []
    for component in rejected_components:
        if (
            component["state"] != "rejected"
            or component["stateEnteredScopeRevision"] != scope_revision
        ):
            continue
        component_id = str(component["componentId"])
        previous_event = latest_by_component.get(component_id)
        if previous_event is not None and previous_event["event"] != "reopened":
            raise TargetScopeStateTransitionError(
                "Rejected Frontier event history is invalid."
            )
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "event": "rejected",
            "scopeRevision": scope_revision,
            "componentId": component_id,
            "stableGaussianIds": deepcopy(component["stableGaussianIds"]),
            "componentDigest": component["componentDigest"],
            "provenanceDigests": deepcopy(component["provenanceDigests"]),
            "previousEventDigest": (
                previous_event["eventDigest"] if previous_event is not None else None
            ),
        }
        appended.append({**payload, "eventDigest": route_b_artifact_digest(payload)})

    for previous_event, component in reopen_pairs:
        new_provenance = set(component["provenanceDigests"]) - set(
            previous_event["provenanceDigests"]
        )
        authorized_ids = {
            stable_id
            for source_digest in new_provenance
            for stable_id in authorized_reopen_sources.get(source_digest, set())
        }
        if not set(previous_event["stableGaussianIds"]).issubset(authorized_ids):
            raise TargetScopeStateTransitionError(
                "A rejected Frontier component requires a new authoritative observation or discovery source to reopen."
            )
        payload = {
            "schemaVersion": 1,
            "event": "reopened",
            "scopeRevision": scope_revision,
            "componentId": previous_event["componentId"],
            "stableGaussianIds": deepcopy(previous_event["stableGaussianIds"]),
            "componentDigest": component["componentDigest"],
            "provenanceDigests": deepcopy(component["provenanceDigests"]),
            "previousEventDigest": previous_event["eventDigest"],
        }
        appended.append({**payload, "eventDigest": route_b_artifact_digest(payload)})

    appended.sort(key=lambda event: str(event["eventDigest"]))
    return [*deepcopy(previous_ledger), *appended]


def _seed_partition(seed_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(seed_record[key])
        for key in (
            "recordDigest",
            "seedPolicyDigest",
            "admittedStableGaussianIds",
            "coreCandidateStableGaussianIds",
            "satelliteStableGaussianIds",
            "filteredStableGaussianIds",
            "unevaluatedStableGaussianIds",
        )
    }


def _epoch_binding(
    *,
    request_binding: Mapping[str, Any],
    target_splat_id: str,
    target_geometry_digest: str,
    component_policy_digest: str,
    discovery_policy_digest: str,
    epoch_origin_digest: str,
    previous_scope_epoch_id: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "targetContextId": request_binding["targetContextId"],
        "targetSplatId": target_splat_id,
        "dependencyToken": deepcopy(request_binding["dependencyToken"]),
        "targetGeometryDigest": target_geometry_digest,
        "componentPolicyDigest": component_policy_digest,
        "discoveryPolicyDigest": discovery_policy_digest,
        "epochOriginDigest": epoch_origin_digest,
        "previousScopeEpochId": previous_scope_epoch_id,
    }
    return payload


def _scope_revision_snapshot(
    *,
    scope_revision: int,
    request_binding: Mapping[str, Any],
    core_ids: list[int],
    active_ids: list[int],
    rejected_ids: list[int],
    context_ids: list[int],
    discovery_source_digests: list[str],
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "scopeRevision": scope_revision,
        "requestBinding": deepcopy(request_binding),
        "coreStableGaussianIds": list(core_ids),
        "activeFrontierStableGaussianIds": list(active_ids),
        "rejectedFrontierStableGaussianIds": list(rejected_ids),
        "requiredContextStableGaussianIds": list(context_ids),
        "discoverySourceDigests": sorted(set(discovery_source_digests)),
    }
    return {
        **payload,
        "scopeRevisionDigest": route_b_artifact_digest(payload),
    }


def _build_state(
    *,
    scope_epoch_id: str,
    scope_revision: int,
    epoch_binding: Mapping[str, Any],
    request_binding: Mapping[str, Any],
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
    core_ids: list[int],
    core_components: list[dict[str, Any]],
    active_ids: list[int],
    active_components: list[dict[str, Any]],
    rejected_ids: list[int],
    rejected_components: list[dict[str, Any]],
    rejected_ledger: list[dict[str, Any]],
    context_ids: list[int],
    seed_partition: Mapping[str, Any],
    seed_record: Mapping[str, Any],
    lineage_ledger: list[dict[str, Any]],
    subcomponent_decision_ledger: list[dict[str, Any]],
    scope_revision_ledger: list[dict[str, Any]],
    revision_provenance_ledger: list[dict[str, Any]],
    provenance: Mapping[str, Any],
    discovery_policy: Mapping[str, Any],
    discovery_envelope_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": TARGET_SCOPE_STATE_SCHEMA_VERSION,
        "stateKind": TARGET_SCOPE_STATE_KIND,
        "status": "experimental-shadow",
        "scopeEpochId": scope_epoch_id,
        "scopeRevision": scope_revision,
        "epochBinding": deepcopy(epoch_binding),
        "requestBinding": deepcopy(request_binding),
        "targetSplatId": geometry["targetSplatId"],
        "targetStableGaussianIds": deepcopy(geometry["stableGaussianIds"]),
        "targetGeometryDigest": geometry["geometryDigest"],
        "targetGeometry": deepcopy(geometry),
        "coreStableGaussianIds": core_ids,
        "coreComponents": core_components,
        "discoveryEnvelopeLedger": discovery_envelope_ledger,
        "activeFrontierStableGaussianIds": active_ids,
        "activeFrontierComponents": active_components,
        "rejectedFrontierStableGaussianIds": rejected_ids,
        "rejectedFrontierComponents": rejected_components,
        "rejectedFrontierLedger": rejected_ledger,
        "requiredContextStableGaussianIds": context_ids,
        "seedPartition": deepcopy(seed_partition),
        "seedRecord": deepcopy(seed_record),
        "componentPolicy": deepcopy(policy),
        "componentPolicyDigest": policy["policyDigest"],
        "discoveryPolicy": deepcopy(discovery_policy),
        "discoveryPolicyDigest": discovery_policy["policyDigest"],
        "componentLineageLedger": lineage_ledger,
        "subcomponentDecisionLedger": subcomponent_decision_ledger,
        "scopeRevisionLedger": scope_revision_ledger,
        "revisionProvenanceLedger": revision_provenance_ledger,
        "provenance": deepcopy(provenance),
        "provenanceDigest": provenance["revisionProvenanceDigest"],
    }
    state = {**payload, "stateDigest": route_b_artifact_digest(payload)}
    if not is_target_scope_state(state):
        raise TargetScopeStateInternalError(
            "Target Scope State failed internal validation."
        )
    return state


def bootstrap_target_scope_state_from_seed(
    *,
    seed_record: object,
    target_geometry: object,
    component_policy: object,
    discovery_policy: object,
) -> dict[str, Any]:
    """Create experimental Scope revision zero from one accepted S0 record."""

    if not is_conservative_seed_shadow_record(seed_record) or not isinstance(
        seed_record, Mapping
    ):
        raise TargetScopeStateValidationError(
            "Target Scope revision zero requires a valid S0 shadow record."
        )
    seed = cast(Mapping[str, Any], seed_record)
    geometry = _validated_geometry(target_geometry)
    policy = cast(
        dict[str, Any],
        validate_target_scope_component_policy(component_policy),
    )
    discovery = cast(
        dict[str, Any],
        validate_target_scope_discovery_policy(discovery_policy),
    )
    if (
        seed.get("targetSplatId") != geometry["targetSplatId"]
        or seed.get("targetGeometryDigest") != geometry["geometryDigest"]
        or seed.get("targetStableGaussianIds") != geometry["stableGaussianIds"]
    ):
        raise TargetScopeStateIncompatibilityError(
            "Target Scope Seed and target geometry identities do not match."
        )
    request_binding = _validated_request_binding(seed["requestBinding"])
    if request_binding["dependencyToken"]["splatId"] != geometry["targetSplatId"]:
        raise TargetScopeStateIncompatibilityError(
            "Target Scope dependency and target identities do not match."
        )
    seed_digest = str(seed["recordDigest"])
    core_ids = list(seed["admittedStableGaussianIds"])
    rows_by_id = {int(row["stableGaussianId"]): row for row in geometry["rows"]}
    if not _discovery_domain_is_target_local(
        core_stable_ids=core_ids,
        target_splat_id=str(geometry["targetSplatId"]),
        policy=discovery,
        rows_by_id=rows_by_id,
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery domain must be target-local to initial Core or bind a Target Geometry Hint."
        )
    core_skeletons = _component_skeletons(
        geometry=geometry,
        policy=policy,
        stable_ids=core_ids,
        state="core",
        provenance_digests=[seed_digest],
    )
    lineage = _transition_lineage(
        parents=[],
        children=core_skeletons,
        from_revision=None,
        to_revision=0,
        subcomponent_decisions=[],
        revision_source_digests=[seed_digest],
        context_stable_gaussian_ids=[],
    )
    core_components = _bind_components(
        skeletons=core_skeletons,
        lineage=lineage,
    )
    provenance_payload: dict[str, object] = {
        "kind": "seed-shadow-bootstrap",
        "reason": "accepted-s0-shadow-record",
        "previousStateDigest": None,
        "epochOriginDigest": seed_digest,
        "sourceDigests": [seed_digest],
    }
    provenance = {
        **provenance_payload,
        "revisionProvenanceDigest": route_b_artifact_digest(provenance_payload),
    }
    epoch_binding = _epoch_binding(
        request_binding=request_binding,
        target_splat_id=str(geometry["targetSplatId"]),
        target_geometry_digest=str(geometry["geometryDigest"]),
        component_policy_digest=str(policy["policyDigest"]),
        discovery_policy_digest=str(discovery["policyDigest"]),
        epoch_origin_digest=seed_digest,
        previous_scope_epoch_id=None,
    )
    return _build_state(
        scope_epoch_id=route_b_artifact_digest(epoch_binding),
        scope_revision=0,
        epoch_binding=epoch_binding,
        request_binding=request_binding,
        geometry=geometry,
        policy=policy,
        core_ids=core_ids,
        core_components=core_components,
        active_ids=[],
        active_components=[],
        rejected_ids=[],
        rejected_components=[],
        rejected_ledger=[],
        context_ids=[],
        seed_partition=_seed_partition(seed),
        seed_record=seed,
        lineage_ledger=lineage,
        subcomponent_decision_ledger=[],
        scope_revision_ledger=[
            _scope_revision_snapshot(
                scope_revision=0,
                request_binding=request_binding,
                core_ids=core_ids,
                active_ids=[],
                rejected_ids=[],
                context_ids=[],
                discovery_source_digests=[],
            )
        ],
        revision_provenance_ledger=[provenance],
        provenance=provenance,
        discovery_policy=discovery,
        discovery_envelope_ledger=[],
    )


def _revise_target_scope_state(
    *,
    previous_state: object,
    target_geometry: object,
    request_binding: object,
    core_stable_gaussian_ids: object,
    active_frontier: object,
    rejected_frontier: object,
    required_context_stable_gaussian_ids: object,
    revision_provenance: object,
    subcomponent_decisions: object = None,
    discovery_envelope_ledger: object = None,
    authorized_reopen_digests: object = None,
) -> dict[str, Any]:
    """Publish one immutable, monotonic revision inside the current epoch."""

    if not is_target_scope_state(previous_state) or not isinstance(
        previous_state, Mapping
    ):
        raise TargetScopeStateValidationError("Previous Target Scope State is invalid.")
    previous = cast(Mapping[str, Any], previous_state)
    geometry = _validated_geometry(target_geometry)
    if (
        geometry["targetSplatId"] != previous["targetSplatId"]
        or geometry["geometryDigest"] != previous["targetGeometryDigest"]
        or geometry["stableGaussianIds"] != previous["targetStableGaussianIds"]
    ):
        raise TargetScopeStateIncompatibilityError(
            "A Target Scope revision cannot change target geometry inside an epoch."
        )
    policy = cast(
        dict[str, Any],
        validate_target_scope_component_policy(previous["componentPolicy"]),
    )
    discovery = cast(
        dict[str, Any],
        validate_target_scope_discovery_policy(previous["discoveryPolicy"]),
    )
    raw_discovery_ledger = (
        previous["discoveryEnvelopeLedger"]
        if discovery_envelope_ledger is None
        else discovery_envelope_ledger
    )
    if not isinstance(raw_discovery_ledger, Sequence) or isinstance(
        raw_discovery_ledger, (str, bytes)
    ):
        raise TargetScopeStateValidationError(
            "Target Scope discovery Envelope ledger is invalid."
        )
    ledger = [
        _validate_target_scope_discovery_source(source)
        for source in raw_discovery_ledger
    ]
    previous_discovery_ledger = cast(
        list[dict[str, object]], previous["discoveryEnvelopeLedger"]
    )
    if (
        len(ledger) < len(previous_discovery_ledger)
        or ledger[: len(previous_discovery_ledger)] != previous_discovery_ledger
    ):
        raise TargetScopeStateTransitionError(
            "The Target Scope discovery Envelope ledger is append-only within an epoch."
        )
    if len({str(source["sourceRecordDigest"]) for source in ledger}) != len(ledger):
        raise TargetScopeStateValidationError(
            "Target Scope discovery Envelope source digests are duplicated."
        )
    if len({str(source["sourceAuthorityDigest"]) for source in ledger}) != len(ledger):
        raise TargetScopeStateValidationError(
            "Target Scope discovery Envelope authorities are duplicated."
        )
    reopen_digests = set(
        _canonical_digest_list(
            [] if authorized_reopen_digests is None else authorized_reopen_digests,
            label="Frontier reopen",
            allow_empty=True,
        )
    )
    binding = _validated_request_binding(request_binding)
    previous_binding = cast(Mapping[str, Any], previous["requestBinding"])
    if (
        binding["targetContextId"] != previous_binding["targetContextId"]
        or binding["dependencyToken"] != previous_binding["dependencyToken"]
        or int(binding["contextRevision"]) < int(previous_binding["contextRevision"])
    ):
        raise TargetScopeStateIncompatibilityError(
            "A Target Scope revision cannot replace its epoch identity."
        )
    if not isinstance(revision_provenance, Mapping) or set(revision_provenance) != {
        "kind",
        "reason",
        "sourceDigests",
    }:
        raise TargetScopeStateValidationError(
            "Target Scope revision provenance is invalid."
        )
    kind = revision_provenance.get("kind")
    reason = revision_provenance.get("reason")
    if (
        kind not in _TARGET_SCOPE_REVISION_KINDS
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise TargetScopeStateValidationError(
            "Target Scope revision provenance is invalid."
        )
    if reason in _EPOCH_ROTATION_REASONS:
        raise TargetScopeStateIncompatibilityError(
            "Authoritative invalidation must rotate the Scope Epoch."
        )
    source_digests = _canonical_digest_list(
        revision_provenance.get("sourceDigests"),
        label="Revision",
    )
    decisions = _canonical_subcomponent_decisions(subcomponent_decisions)
    previous_decision_digests = {
        str(decision["decisionDigest"])
        for decision in cast(
            list[dict[str, Any]],
            previous["subcomponentDecisionLedger"],
        )
    }
    if previous_decision_digests.intersection(
        str(decision["decisionDigest"]) for decision in decisions
    ):
        raise TargetScopeStateValidationError(
            "A subcomponent decision cannot be republished in the same epoch."
        )
    source_digests = sorted(
        set(source_digests)
        | {str(decision["decisionDigest"]) for decision in decisions}
    )
    target_ids = set(previous["targetStableGaussianIds"])
    core_ids = _canonical_stable_ids(core_stable_gaussian_ids, label="Core")
    context_ids = _canonical_stable_ids(
        required_context_stable_gaussian_ids,
        label="Context",
    )
    active_groups = _canonical_frontier_groups(active_frontier, rejected=False)
    rejected_groups = _canonical_frontier_groups(rejected_frontier, rejected=True)
    active_ids = sorted(
        stable_id for group in active_groups for stable_id in group["stableGaussianIds"]
    )
    rejected_ids = sorted(
        stable_id
        for group in rejected_groups
        for stable_id in group["stableGaussianIds"]
    )
    roles = [set(core_ids), set(active_ids), set(rejected_ids), set(context_ids)]
    if any(not role.issubset(target_ids) for role in roles) or any(
        roles[left] & roles[right]
        for left in range(len(roles))
        for right in range(left + 1, len(roles))
    ):
        raise TargetScopeStateTransitionError(
            "Target Scope role sets must be disjoint and target-bounded."
        )
    if not set(previous["coreStableGaussianIds"]).issubset(core_ids):
        raise TargetScopeStateTransitionError(
            "Core cannot shrink inside one Scope Epoch."
        )
    latest_rejection_events: dict[str, Mapping[str, Any]] = {}
    for event in cast(list[Mapping[str, Any]], previous["rejectedFrontierLedger"]):
        latest_rejection_events[str(event["componentId"])] = event
    rejected_ledger_tail_ids = {
        int(stable_id)
        for event in latest_rejection_events.values()
        if event["event"] == "rejected"
        for stable_id in event["stableGaussianIds"]
    }
    requested_reopened_ids = {
        int(stable_id)
        for group in active_groups
        if group["state"] == "reopened"
        for stable_id in group["stableGaussianIds"]
    }
    reopened_history_sources = {
        str(source_digest)
        for event in latest_rejection_events.values()
        if event["event"] == "rejected"
        and set(event["stableGaussianIds"]).issubset(requested_reopened_ids)
        for source_digest in event["provenanceDigests"]
    }
    source_digests = sorted(set(source_digests) | reopened_history_sources)
    previous_active_ids = set(previous["activeFrontierStableGaussianIds"])
    introduced_core_ids = set(core_ids) - set(previous["coreStableGaussianIds"])
    if not introduced_core_ids.issubset(previous_active_ids):
        raise TargetScopeStateTransitionError(
            "New support must enter active Frontier before Core."
        )
    introduced_rejected_ids = set(rejected_ids) - set(
        previous["rejectedFrontierStableGaussianIds"]
    )
    if not introduced_rejected_ids.issubset(previous_active_ids):
        raise TargetScopeStateTransitionError(
            "New rejected Frontier support must originate in active Frontier."
        )
    introduced_active_ids = (
        set(active_ids) - previous_active_ids - rejected_ledger_tail_ids
    )
    previous_discovery_sources = {
        str(source["sourceRecordDigest"])
        for source in cast(list[Mapping[str, Any]], previous["discoveryEnvelopeLedger"])
    }
    new_discovery_sources = {
        str(source["sourceRecordDigest"]) for source in ledger
    } - previous_discovery_sources
    new_discovery_authorities = {
        str(source["sourceRecordDigest"]): {
            int(stable_id)
            for stable_id in cast(list[int], source["admittedStableGaussianIds"])
        }
        for source in ledger
        if str(source["sourceRecordDigest"]) in new_discovery_sources
    }
    if not reopen_digests.issubset(new_discovery_authorities):
        raise TargetScopeStateValidationError(
            "Frontier reopen authority must name a newly appended discovery source."
        )
    if introduced_active_ids and any(
        not any(
            source_digest in set(group["provenanceDigests"])
            and stable_id in admitted_ids
            for source_digest, admitted_ids in new_discovery_authorities.items()
        )
        for group in active_groups
        for stable_id in introduced_active_ids & set(group["stableGaussianIds"])
    ):
        raise TargetScopeStateTransitionError(
            "New active Frontier support requires a fresh authoritative observation or discovery source."
        )
    if rejected_ledger_tail_ids & (set(core_ids) | set(context_ids)):
        raise TargetScopeStateTransitionError(
            "Rejected Frontier support cannot become Core or required Context."
        )
    envelope_ids = {
        int(stable_id)
        for source in cast(list[Mapping[str, Any]], previous["discoveryEnvelopeLedger"])
        for stable_id in source["admittedStableGaussianIds"]
    }
    protected_active = envelope_ids & set(previous["activeFrontierStableGaussianIds"])
    if not protected_active.issubset(
        set(core_ids) | set(active_ids) | set(rejected_ids)
    ):
        raise TargetScopeStateTransitionError(
            "Active Discovery Envelope support must remain Core, active Frontier, or rejected Frontier."
        )
    if kind in _NON_REJECTION_DISCOVERY_KINDS and not protected_active.issubset(
        set(active_ids)
    ):
        raise TargetScopeStateTransitionError(
            "Low support, S1/depth absence, or technical failure cannot reject or erase Discovery Envelope support or promote it out of active Frontier."
        )

    scope_revision = int(previous["scopeRevision"]) + 1
    core_skeletons = _component_skeletons(
        geometry=geometry,
        policy=policy,
        stable_ids=core_ids,
        state="core",
        provenance_digests=source_digests,
    )
    active_skeletons = _frontier_skeletons(
        geometry=geometry,
        policy=policy,
        groups=active_groups,
    )
    rejected_skeletons = _frontier_skeletons(
        geometry=geometry,
        policy=policy,
        groups=rejected_groups,
    )
    parents = _state_components(previous)
    skeletons = core_skeletons + active_skeletons + rejected_skeletons
    lineage = _transition_lineage(
        parents=parents,
        children=skeletons,
        from_revision=int(previous["scopeRevision"]),
        to_revision=scope_revision,
        subcomponent_decisions=decisions,
        revision_source_digests=source_digests,
        context_stable_gaussian_ids=context_ids,
    )
    components = _bind_components(
        skeletons=skeletons,
        lineage=lineage,
    )
    core_components = [
        component for component in components if component["state"] == "core"
    ]
    active_components = [
        component
        for component in components
        if component["state"] in _ACTIVE_FRONTIER_STATES
    ]
    rejected_components = [
        component for component in components if component["state"] == "rejected"
    ]
    rejected_ledger = _append_rejected_frontier_events(
        previous_ledger=cast(list[dict[str, Any]], previous["rejectedFrontierLedger"]),
        rejected_components=rejected_components,
        active_components=active_components,
        scope_revision=scope_revision,
        authorized_reopen_sources={
            source_digest: new_discovery_authorities[source_digest]
            for source_digest in reopen_digests
        },
    )
    previous_provenance = cast(Mapping[str, Any], previous["provenance"])
    provenance_payload: dict[str, object] = {
        "kind": kind,
        "reason": reason,
        "previousStateDigest": previous["stateDigest"],
        "epochOriginDigest": previous_provenance["epochOriginDigest"],
        "sourceDigests": source_digests,
    }
    provenance = {
        **provenance_payload,
        "revisionProvenanceDigest": route_b_artifact_digest(provenance_payload),
    }
    prior_lineage = cast(list[dict[str, Any]], previous["componentLineageLedger"])
    lineage_ledger = deepcopy(prior_lineage) + lineage
    lineage_ledger.sort(
        key=lambda record: (
            int(record["toScopeRevision"]),
            str(record["lineageDigest"]),
        )
    )
    previous_decisions = cast(
        list[dict[str, Any]],
        previous["subcomponentDecisionLedger"],
    )
    decision_ledger = deepcopy(previous_decisions) + deepcopy(decisions)
    decision_ledger.sort(key=lambda decision: str(decision["decisionDigest"]))
    return _build_state(
        scope_epoch_id=str(previous["scopeEpochId"]),
        scope_revision=scope_revision,
        epoch_binding=cast(Mapping[str, Any], previous["epochBinding"]),
        request_binding=binding,
        geometry=geometry,
        policy=policy,
        core_ids=core_ids,
        core_components=core_components,
        active_ids=active_ids,
        active_components=active_components,
        rejected_ids=rejected_ids,
        rejected_components=rejected_components,
        rejected_ledger=rejected_ledger,
        context_ids=context_ids,
        seed_partition=cast(Mapping[str, Any], previous["seedPartition"]),
        seed_record=cast(Mapping[str, Any], previous["seedRecord"]),
        lineage_ledger=lineage_ledger,
        subcomponent_decision_ledger=decision_ledger,
        scope_revision_ledger=[
            *deepcopy(previous["scopeRevisionLedger"]),
            _scope_revision_snapshot(
                scope_revision=scope_revision,
                request_binding=binding,
                core_ids=core_ids,
                active_ids=active_ids,
                rejected_ids=rejected_ids,
                context_ids=context_ids,
                discovery_source_digests=[
                    str(source["sourceRecordDigest"]) for source in ledger
                ],
            ),
        ],
        revision_provenance_ledger=[
            *deepcopy(previous["revisionProvenanceLedger"]),
            deepcopy(provenance),
        ],
        provenance=provenance,
        discovery_policy=discovery,
        discovery_envelope_ledger=ledger,
    )


def revise_target_scope_state(
    *,
    previous_state: object,
    target_geometry: object,
    request_binding: object,
    core_stable_gaussian_ids: object,
    active_frontier: object,
    rejected_frontier: object,
    required_context_stable_gaussian_ids: object,
    revision_provenance: object,
    subcomponent_decisions: object = None,
) -> dict[str, Any]:
    """Publish one ordinary immutable revision inside the current Scope Epoch."""

    return _revise_target_scope_state(
        previous_state=previous_state,
        target_geometry=target_geometry,
        request_binding=request_binding,
        core_stable_gaussian_ids=core_stable_gaussian_ids,
        active_frontier=active_frontier,
        rejected_frontier=rejected_frontier,
        required_context_stable_gaussian_ids=required_context_stable_gaussian_ids,
        revision_provenance=revision_provenance,
        subcomponent_decisions=subcomponent_decisions,
    )


def _target_scope_discovery_source_payload(
    state: Mapping[str, Any],
) -> dict[str, object]:
    request_binding = cast(Mapping[str, Any], state["requestBinding"])
    discovery_policy = cast(Mapping[str, Any], state["discoveryPolicy"])
    discovery_domain = cast(Mapping[str, Any], discovery_policy["discoveryDomain"])
    return {
        "schemaVersion": TARGET_SCOPE_DISCOVERY_SOURCE_SCHEMA_VERSION,
        "targetSplatId": state["targetSplatId"],
        "dependencyToken": deepcopy(request_binding["dependencyToken"]),
        "scopeEpochId": state["scopeEpochId"],
        "targetGeometryDigest": state["targetGeometryDigest"],
        "componentPolicyDigest": state["componentPolicyDigest"],
        "discoveryPolicyDigest": state["discoveryPolicyDigest"],
        "discoveryDomainDigest": discovery_domain["domainDigest"],
    }


def create_target_scope_boundary_contact_shadow_source(
    *,
    target_scope_state: object,
    boundary_result: object,
    boundary_input: object,
    boundary_binding: object,
    source_artifact: object,
    spatial_bounds: object,
    reason: object,
) -> dict[str, object]:
    """Bind one versioned Working Set boundary result for shadow admission."""

    if not is_target_scope_state(target_scope_state) or not isinstance(
        target_scope_state, Mapping
    ):
        raise TargetScopeStateValidationError(
            "Boundary-contact shadow discovery requires a valid Target Scope State."
        )
    canonical_result = _canonical_boundary_contact_result(boundary_result)
    canonical_input = _canonical_boundary_resolver_input(boundary_input)
    replay_result = _canonical_boundary_contact_result(
        resolve_evidence_working_set_boundary(canonical_input)
    )
    if canonical_result != replay_result:
        raise TargetScopeStateValidationError(
            "Boundary-contact result does not replay from its resolver input."
        )
    canonical_binding = _canonical_boundary_resolver_binding(boundary_binding)
    state_request_binding = cast(
        Mapping[str, Any], target_scope_state["requestBinding"]
    )
    if (
        canonical_binding["targetSplatId"] != target_scope_state["targetSplatId"]
        or canonical_binding["dependencyToken"]
        != state_request_binding["dependencyToken"]
    ):
        raise TargetScopeStateValidationError(
            "Boundary-contact resolver binding does not match Target Scope State."
        )
    input_render_working_set = cast(
        Mapping[str, Any], canonical_input["renderWorkingSet"]
    )
    input_evidence_working_set = cast(
        Mapping[str, Any], canonical_input["evidenceWorkingSet"]
    )
    if (
        input_render_working_set["dependencyToken"]
        != canonical_binding["dependencyToken"]
        or input_render_working_set["targetSplatId"]
        != canonical_binding["targetSplatId"]
        or input_evidence_working_set["targetSplatId"]
        != canonical_binding["targetSplatId"]
        or input_render_working_set["renderWorkingSetToken"]
        != canonical_binding["renderWorkingSetToken"]
        or input_evidence_working_set["evidenceWorkingSetToken"]
        != canonical_binding["evidenceWorkingSetToken"]
    ):
        raise TargetScopeStateValidationError(
            "Boundary-contact resolver input does not match its binding."
        )
    canonical_status = (
        "failed-closed-boundary-contact"
        if canonical_result["status"] == "failed-closed"
        else "expanded"
    )
    if not isinstance(source_artifact, Mapping) or set(source_artifact) != {
        "artifactId",
        "artifactDigest",
        "viewIds",
    }:
        raise TargetScopeStateValidationError(
            "Boundary-contact shadow discovery artifact is invalid."
        )
    source_artifact_refs = _canonical_discovery_artifact_refs(
        [
            {
                "schemaVersion": 1,
                "artifactKind": "gaussian-evidence-artifact",
                **source_artifact,
            }
        ],
        source_kind="evidence-working-set-boundary-contact",
    )
    producer_id = "evidence-working-set-boundary-resolver/v1"
    derivation_policy_digest = route_b_artifact_digest(
        {"schemaVersion": 1, "producerId": producer_id}
    )
    authority_evidence = {
        "schemaVersion": 1,
        "producerId": producer_id,
        "status": canonical_status,
        "derivationPolicyDigest": derivation_policy_digest,
        "sourceArtifactRefs": source_artifact_refs,
        "boundaryBinding": canonical_binding,
        "boundaryInput": canonical_input,
        "boundaryResult": canonical_result,
    }
    payload = {
        **_target_scope_discovery_source_payload(target_scope_state),
        "sourceKind": "evidence-working-set-boundary-contact",
        "sourceArtifactRefs": source_artifact_refs,
        "sourceAuthority": {
            "schemaVersion": 1,
            "authorityKind": "boundary-contact-result",
            "producerId": producer_id,
            "status": canonical_status,
            "resultDigest": route_b_artifact_digest(authority_evidence),
            "derivationPolicyDigest": derivation_policy_digest,
            "authorityEvidence": authority_evidence,
        },
        "admittedStableGaussianIds": canonical_result["contactStableGaussianIds"],
        "spatialBounds": spatial_bounds,
        "reason": reason,
    }
    return _create_target_scope_discovery_source(payload)


def create_target_scope_observation_shadow_source(
    *,
    target_scope_state: object,
    observation: object,
) -> dict[str, object]:
    """Bind one typed Included/User-Confirmed observation for shadow use."""

    if not is_target_scope_state(target_scope_state) or not isinstance(
        target_scope_state, Mapping
    ):
        raise TargetScopeStateValidationError(
            "Observation shadow discovery requires a valid Target Scope State."
        )
    expected_keys = {
        "schemaVersion",
        "status",
        "sourceKind",
        "producerId",
        "derivationPolicyDigest",
        "artifactRefs",
        "participation",
        "stableMaskDigest",
        "supportedStableGaussianIds",
        "spatialBounds",
        "reason",
    }
    if (
        not isinstance(observation, Mapping)
        or set(observation) != expected_keys
        or observation.get("schemaVersion") != 1
    ):
        raise TargetScopeStateValidationError(
            "Observation shadow discovery input is invalid."
        )
    source_kind = observation.get("sourceKind")
    status = observation.get("status")
    if source_kind not in _DISCOVERY_SOURCE_AUTHORITY:
        raise TargetScopeStateValidationError(
            "Observation shadow discovery source family is invalid."
        )
    contract = _DISCOVERY_SOURCE_AUTHORITY[str(source_kind)]
    if not bool(contract["requiresStableAuthority"]):
        raise TargetScopeStateValidationError(
            "Observation shadow discovery source family is invalid."
        )
    artifact_refs = observation.get("artifactRefs")
    if (
        not isinstance(artifact_refs, Sequence)
        or isinstance(artifact_refs, (str, bytes))
        or any(
            not isinstance(reference, Mapping)
            or set(reference) != {"artifactId", "artifactDigest", "viewIds"}
            for reference in artifact_refs
        )
    ):
        raise TargetScopeStateValidationError(
            "Observation shadow discovery artifacts are invalid."
        )
    source_artifact_refs = _canonical_discovery_artifact_refs(
        [
            {
                "schemaVersion": 1,
                "artifactKind": contract["artifactKind"],
                **reference,
            }
            for reference in artifact_refs
        ],
        source_kind=str(source_kind),
    )
    authority_evidence = {
        "schemaVersion": 1,
        "producerId": observation.get("producerId"),
        "status": status,
        "derivationPolicyDigest": observation.get("derivationPolicyDigest"),
        "sourceArtifactRefs": source_artifact_refs,
        "participation": observation.get("participation"),
        "stableMaskDigest": observation.get("stableMaskDigest"),
    }
    payload = {
        **_target_scope_discovery_source_payload(target_scope_state),
        "sourceKind": source_kind,
        "sourceArtifactRefs": source_artifact_refs,
        "sourceAuthority": {
            "schemaVersion": 1,
            "authorityKind": contract["authorityKind"],
            "producerId": observation.get("producerId"),
            "status": status,
            "resultDigest": route_b_artifact_digest(authority_evidence),
            "derivationPolicyDigest": observation.get("derivationPolicyDigest"),
            "participation": observation.get("participation"),
            "stableMaskDigest": observation.get("stableMaskDigest"),
            "authorityEvidence": authority_evidence,
        },
        "admittedStableGaussianIds": observation.get("supportedStableGaussianIds"),
        "spatialBounds": observation.get("spatialBounds"),
        "reason": observation.get("reason"),
    }
    return _create_target_scope_discovery_source(payload)


def create_target_scope_reviewed_support_shadow_source(
    *,
    target_scope_state: object,
    review: object,
) -> dict[str, object]:
    """Bind one versioned target-local support review for shadow use."""

    if not is_target_scope_state(target_scope_state) or not isinstance(
        target_scope_state, Mapping
    ):
        raise TargetScopeStateValidationError(
            "Reviewed support discovery requires a valid Target Scope State."
        )
    expected_keys = {
        "schemaVersion",
        "status",
        "producerId",
        "derivationPolicyDigest",
        "artifactRef",
        "supportedStableGaussianIds",
        "spatialBounds",
        "reason",
    }
    if (
        not isinstance(review, Mapping)
        or set(review) != expected_keys
        or review.get("schemaVersion") != 1
    ):
        raise TargetScopeStateValidationError(
            "Reviewed support discovery input is invalid."
        )
    artifact_ref = review.get("artifactRef")
    if not isinstance(artifact_ref, Mapping) or set(artifact_ref) != {
        "artifactId",
        "artifactDigest",
        "viewIds",
    }:
        raise TargetScopeStateValidationError(
            "Reviewed support discovery artifact is invalid."
        )
    source_artifact_refs = _canonical_discovery_artifact_refs(
        [
            {
                "schemaVersion": 1,
                "artifactKind": "target-geometry-hint-review",
                **artifact_ref,
            }
        ],
        source_kind="reviewed-target-local-spatial-support",
    )
    authority_evidence = {
        "schemaVersion": 1,
        "producerId": review.get("producerId"),
        "status": review.get("status"),
        "derivationPolicyDigest": review.get("derivationPolicyDigest"),
        "sourceArtifactRefs": source_artifact_refs,
    }
    payload = {
        **_target_scope_discovery_source_payload(target_scope_state),
        "sourceKind": "reviewed-target-local-spatial-support",
        "sourceArtifactRefs": source_artifact_refs,
        "sourceAuthority": {
            "schemaVersion": 1,
            "authorityKind": "reviewed-target-local-support",
            "producerId": review.get("producerId"),
            "status": review.get("status"),
            "resultDigest": route_b_artifact_digest(authority_evidence),
            "derivationPolicyDigest": review.get("derivationPolicyDigest"),
            "authorityEvidence": authority_evidence,
        },
        "admittedStableGaussianIds": review.get("supportedStableGaussianIds"),
        "spatialBounds": review.get("spatialBounds"),
        "reason": review.get("reason"),
    }
    return _create_target_scope_discovery_source(payload)


def _discovery_domain_is_target_local(
    *,
    core_stable_ids: Sequence[int],
    target_splat_id: str,
    policy: Mapping[str, Any],
    rows_by_id: Mapping[int, Mapping[str, Any]],
) -> bool:
    domain = cast(Mapping[str, Any], policy["discoveryDomain"])
    anchor_ids = list(core_stable_ids)
    domain_bounds = cast(Mapping[str, list[float]], domain["spatialBounds"])
    corners = tuple(
        product(
            *(
                (
                    float(domain_bounds["minimum"][axis]),
                    float(domain_bounds["maximum"][axis]),
                )
                for axis in range(3)
            )
        )
    )
    distance_multiplier = float(domain["maximumDomainDistanceScaleMultiplier"])
    hint = domain.get("targetGeometryHint")
    if hint is not None and (
        not isinstance(hint, Mapping) or hint["targetSplatId"] != target_splat_id
    ):
        return False
    hint_local = False
    if isinstance(hint, Mapping):
        hint_center = cast(list[float], hint["center"])
        hint_extent = cast(list[float], hint["extent"])
        hint_local = all(
            all(
                abs(corner[axis] - float(hint_center[axis]))
                <= float(hint_extent[axis]) * distance_multiplier
                for axis in range(3)
            )
            for corner in corners
        )
    core_local = bool(anchor_ids) and any(
        all(
            all(
                abs(
                    corner[axis]
                    - float(cast(list[float], rows_by_id[stable_id]["center"])[axis])
                )
                <= math.exp(
                    max(
                        float(value)
                        for value in cast(
                            list[float], rows_by_id[stable_id]["logScales"]
                        )
                    )
                )
                * distance_multiplier
                for axis in range(3)
            )
            for corner in corners
        )
        for stable_id in anchor_ids
    )
    return hint_local or core_local


def _gaussian_support_within_discovery_domain(
    *,
    stable_ids: Sequence[int],
    policy: Mapping[str, Any],
    rows_by_id: Mapping[int, Mapping[str, Any]],
) -> bool:
    domain = cast(Mapping[str, Any], policy["discoveryDomain"])
    domain_bounds = cast(Mapping[str, list[float]], domain["spatialBounds"])
    support_multiplier = float(domain["gaussianSupportScaleMultiplier"])
    for stable_id in stable_ids:
        row = rows_by_id[stable_id]
        center = cast(list[float], row["center"])
        support = (
            math.exp(max(float(value) for value in cast(list[float], row["logScales"])))
            * support_multiplier
        )
        if any(
            float(center[axis]) - support < float(domain_bounds["minimum"][axis])
            or float(center[axis]) + support > float(domain_bounds["maximum"][axis])
            for axis in range(3)
        ):
            return False
    return True


def _validate_discovery_source_spatial_domain(
    *,
    source: Mapping[str, Any],
    policy: Mapping[str, Any],
    rows_by_id: Mapping[int, Mapping[str, Any]],
) -> None:
    domain = cast(Mapping[str, Any], policy["discoveryDomain"])
    domain_bounds = cast(Mapping[str, list[float]], domain["spatialBounds"])
    source_bounds = cast(Mapping[str, list[float]], source["spatialBounds"])
    maximum_extent = cast(list[float], domain["maximumSourceExtent"])
    admitted_ids = cast(list[int], source["admittedStableGaussianIds"])
    if source["discoveryDomainDigest"] != domain["domainDigest"]:
        raise TargetScopeStateIncompatibilityError(
            "Target Scope discovery source domain does not match the epoch."
        )
    if any(
        float(source_bounds["minimum"][axis]) < float(domain_bounds["minimum"][axis])
        or float(source_bounds["maximum"][axis]) > float(domain_bounds["maximum"][axis])
        or float(source_bounds["maximum"][axis]) - float(source_bounds["minimum"][axis])
        > float(maximum_extent[axis])
        for axis in range(3)
    ):
        raise TargetScopeStateTransitionError(
            "Target Scope discovery source bounds exceed the target-local domain."
        )
    if any(
        float(rows_by_id[stable_id]["center"][axis])
        < float(source_bounds["minimum"][axis])
        or float(rows_by_id[stable_id]["center"][axis])
        > float(source_bounds["maximum"][axis])
        for stable_id in admitted_ids
        for axis in range(3)
    ):
        raise TargetScopeStateTransitionError(
            "Target Scope discovery admission must be spatially bounded."
        )
    if not _gaussian_support_within_discovery_domain(
        stable_ids=admitted_ids,
        policy=policy,
        rows_by_id=rows_by_id,
    ):
        raise TargetScopeStateTransitionError(
            "Target Scope discovery Gaussian support exceeds the target-local domain."
        )


def admit_target_scope_discovery_sources(
    *,
    previous_state: object,
    target_geometry: object,
    request_binding: object,
    sources: object,
) -> dict[str, Any]:
    """Atomically admit a deterministic batch into the shadow Envelope/Frontier."""

    if not is_target_scope_state(previous_state) or not isinstance(
        previous_state, Mapping
    ):
        raise TargetScopeStateValidationError("Previous Target Scope State is invalid.")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        raise TargetScopeStateValidationError(
            "Target Scope discovery admission sources are invalid."
        )
    canonical_by_record: dict[str, dict[str, object]] = {}
    for source in sources:
        canonical = _validate_target_scope_discovery_source(source)
        canonical_by_record[str(canonical["sourceRecordDigest"])] = canonical
    if not canonical_by_record:
        raise TargetScopeStateValidationError(
            "Target Scope discovery admission requires at least one source."
        )
    canonical_by_authority: dict[str, dict[str, object]] = {}
    for source in sorted(
        canonical_by_record.values(),
        key=lambda item: str(item["sourceRecordDigest"]),
    ):
        authority_digest = str(source["sourceAuthorityDigest"])
        previous_authority = canonical_by_authority.get(authority_digest)
        if (
            previous_authority is not None
            and previous_authority["derivedResultDigest"]
            != source["derivedResultDigest"]
        ):
            raise TargetScopeStateTransitionError(
                "One discovery authority cannot produce conflicting derived support."
            )
        canonical_by_authority[authority_digest] = source
    previous = cast(Mapping[str, Any], previous_state)
    geometry = _validated_geometry(target_geometry)
    binding = _validated_request_binding(request_binding)
    if (
        geometry["targetSplatId"] != previous["targetSplatId"]
        or geometry["geometryDigest"] != previous["targetGeometryDigest"]
        or geometry["stableGaussianIds"] != previous["targetStableGaussianIds"]
        or binding["targetContextId"] != previous["requestBinding"]["targetContextId"]
        or binding["dependencyToken"] != previous["requestBinding"]["dependencyToken"]
        or int(binding["contextRevision"])
        < int(previous["requestBinding"]["contextRevision"])
    ):
        raise TargetScopeStateIncompatibilityError(
            "Target Scope discovery admission does not match the current epoch."
        )
    policy = cast(Mapping[str, Any], previous["discoveryPolicy"])
    domain = cast(Mapping[str, Any], policy["discoveryDomain"])
    expected_identity = {
        "targetSplatId": previous["targetSplatId"],
        "dependencyToken": previous["requestBinding"]["dependencyToken"],
        "scopeEpochId": previous["scopeEpochId"],
        "targetGeometryDigest": previous["targetGeometryDigest"],
        "componentPolicyDigest": previous["componentPolicyDigest"],
        "discoveryPolicyDigest": previous["discoveryPolicyDigest"],
        "discoveryDomainDigest": domain["domainDigest"],
    }
    target_ids = set(previous["targetStableGaussianIds"])
    rows_by_id = {int(row["stableGaussianId"]): row for row in geometry["rows"]}
    for source in canonical_by_record.values():
        if any(source[key] != value for key, value in expected_identity.items()):
            raise TargetScopeStateIncompatibilityError(
                "Target Scope discovery source identity does not match the epoch."
            )
        admitted_ids = cast(list[int], source["admittedStableGaussianIds"])
        if not set(admitted_ids).issubset(target_ids):
            raise TargetScopeStateTransitionError(
                "Target Scope discovery admission must be target-bounded."
            )
        _validate_discovery_source_spatial_domain(
            source=source,
            policy=policy,
            rows_by_id=rows_by_id,
        )

    prior_ledger = cast(list[dict[str, object]], previous["discoveryEnvelopeLedger"])
    prior_by_authority = {
        str(source["sourceAuthorityDigest"]): source for source in prior_ledger
    }
    new_sources: list[dict[str, object]] = []
    for authority_digest, source in canonical_by_authority.items():
        prior_source = prior_by_authority.get(authority_digest)
        if (
            prior_source is not None
            and prior_source["derivedResultDigest"] != source["derivedResultDigest"]
        ):
            raise TargetScopeStateTransitionError(
                "Discovery authority reuse cannot change derived Stable IDs or bounds."
            )
        if prior_source is None:
            new_sources.append(source)
    new_sources.sort(key=lambda source: str(source["sourceRecordDigest"]))
    if not new_sources:
        return deepcopy(dict(previous))
    if len(prior_ledger) + len(new_sources) > int(
        policy["maximumSourceRecordsPerEpoch"]
    ):
        raise TargetScopeStateTransitionError(
            "Target Scope discovery source-record budget is exhausted."
        )
    ledger = [*deepcopy(prior_ledger), *deepcopy(new_sources)]
    envelope_ids = {
        int(stable_id)
        for source in ledger
        for stable_id in cast(list[int], source["admittedStableGaussianIds"])
    }
    if len(envelope_ids) > int(policy["maximumAdmittedStableGaussianIdsPerEpoch"]):
        raise TargetScopeStateTransitionError(
            "Target Scope discovery Stable Gaussian ID budget is exhausted."
        )
    admitted_ids = {
        int(stable_id)
        for source in new_sources
        for stable_id in cast(list[int], source["admittedStableGaussianIds"])
    }
    core_ids = set(previous["coreStableGaussianIds"])
    context_ids = set(previous["requiredContextStableGaussianIds"])
    if admitted_ids & core_ids:
        raise TargetScopeStateTransitionError(
            "Discovery sources must enter active Frontier, never Core directly."
        )
    context_ids -= admitted_ids

    previous_active = cast(list[dict[str, Any]], previous["activeFrontierComponents"])
    previous_rejected = cast(
        list[dict[str, Any]], previous["rejectedFrontierComponents"]
    )
    current_rejected_by_id = {
        str(component["componentId"]): component for component in previous_rejected
    }
    latest_rejection_events: dict[str, Mapping[str, Any]] = {}
    for event in cast(list[Mapping[str, Any]], previous["rejectedFrontierLedger"]):
        latest_rejection_events[str(event["componentId"])] = event
    reopenable_rejections = [
        current_rejected_by_id.get(component_id)
        or {
            "componentId": component_id,
            "stableGaussianIds": deepcopy(event["stableGaussianIds"]),
            "state": "rejected",
            "provenanceDigests": deepcopy(event["provenanceDigests"]),
        }
        for component_id, event in latest_rejection_events.items()
        if event["event"] == "rejected"
    ]
    for component in reopenable_rejections:
        component_ids = set(component["stableGaussianIds"])
        if component_ids & admitted_ids and not component_ids.issubset(admitted_ids):
            raise TargetScopeStateTransitionError(
                "A rejected Frontier component requires complete component provenance to reopen."
            )
    reopened_ids = {
        int(stable_id)
        for component in reopenable_rejections
        if set(component["stableGaussianIds"]).issubset(admitted_ids)
        for stable_id in component["stableGaussianIds"]
    }
    reopenable_ids = {
        int(stable_id)
        for component in reopenable_rejections
        for stable_id in component["stableGaussianIds"]
    }
    new_ids = (
        admitted_ids - set(previous["activeFrontierStableGaussianIds"]) - reopenable_ids
    )
    active_ids = sorted(
        set(previous["activeFrontierStableGaussianIds"]) | admitted_ids | reopened_ids
    )
    active_partitions = _component_skeletons(
        geometry=geometry,
        policy=cast(Mapping[str, Any], previous["componentPolicy"]),
        stable_ids=active_ids,
        state="partition",
        provenance_digests=[],
    )
    active_groups: list[dict[str, object]] = []
    all_previous_components = [*previous_active, *reopenable_rejections]
    for partition in active_partitions:
        partition_ids = set(partition["stableGaussianIds"])
        prior_components = [
            component
            for component in all_previous_components
            if partition_ids & set(component["stableGaussianIds"])
        ]
        source_digests = {
            str(source["sourceRecordDigest"])
            for source in new_sources
            if partition_ids & set(cast(list[int], source["admittedStableGaussianIds"]))
        }
        provenance_digests = sorted(
            source_digests
            | {
                str(provenance_digest)
                for component in prior_components
                for provenance_digest in component["provenanceDigests"]
            }
        )
        if partition_ids & reopened_ids:
            state = "reopened"
        elif partition_ids & new_ids:
            state = "new"
        else:
            prior_states = {
                str(component["state"])
                for component in prior_components
                if component["state"] in _ACTIVE_FRONTIER_STATES
            }
            if len(prior_states) != 1:
                raise TargetScopeStateTransitionError(
                    "Discovery admission cannot ambiguously merge active Frontier states."
                )
            state = prior_states.pop()
        active_groups.append(
            {
                "stableGaussianIds": deepcopy(partition["stableGaussianIds"]),
                "state": state,
                "provenanceDigests": provenance_digests,
            }
        )
    rejected_groups = [
        {
            "stableGaussianIds": deepcopy(component["stableGaussianIds"]),
            "state": "rejected",
            "provenanceDigests": deepcopy(component["provenanceDigests"]),
        }
        for component in previous_rejected
        if not set(component["stableGaussianIds"]).issubset(reopened_ids)
    ]
    new_source_digests = sorted(
        str(source["sourceRecordDigest"]) for source in new_sources
    )
    return _revise_target_scope_state(
        previous_state=previous,
        target_geometry=geometry,
        request_binding=binding,
        core_stable_gaussian_ids=sorted(core_ids),
        active_frontier=active_groups,
        rejected_frontier=rejected_groups,
        required_context_stable_gaussian_ids=sorted(context_ids),
        revision_provenance={
            "kind": "scope-transition",
            "reason": "bounded-discovery-envelope-admission",
            "sourceDigests": new_source_digests,
        },
        discovery_envelope_ledger=ledger,
        authorized_reopen_digests=new_source_digests,
    )


def rotate_target_scope_epoch(
    *,
    previous_state: object,
    seed_record: object,
    target_geometry: object,
    component_policy: object,
    discovery_policy: object = None,
    reason: object,
    source_digests: object,
) -> dict[str, Any]:
    """Start a fresh revision-zero epoch after authoritative invalidation."""

    if not is_target_scope_state(previous_state) or not isinstance(
        previous_state, Mapping
    ):
        raise TargetScopeStateValidationError("Previous Target Scope State is invalid.")
    if not isinstance(reason, str) or reason not in _EPOCH_ROTATION_REASONS:
        raise TargetScopeStateValidationError(
            "Scope Epoch rotation requires an authoritative invalidation reason."
        )
    if not is_conservative_seed_shadow_record(seed_record) or not isinstance(
        seed_record, Mapping
    ):
        raise TargetScopeStateValidationError(
            "Scope Epoch rotation requires a valid replacement S0 shadow record."
        )
    previous = cast(Mapping[str, Any], previous_state)
    seed = cast(Mapping[str, Any], seed_record)
    sources = _canonical_digest_list(
        source_digests,
        label="Scope Epoch rotation",
    )
    replacement = bootstrap_target_scope_state_from_seed(
        seed_record=seed,
        target_geometry=target_geometry,
        component_policy=component_policy,
        discovery_policy=(
            previous["discoveryPolicy"]
            if discovery_policy is None
            else discovery_policy
        ),
    )
    geometry = _validated_geometry(target_geometry)
    policy = cast(Mapping[str, Any], replacement["componentPolicy"])
    discovery = cast(Mapping[str, Any], replacement["discoveryPolicy"])
    binding = cast(Mapping[str, Any], replacement["requestBinding"])
    seed_digest = str(seed["recordDigest"])
    all_sources = sorted(set(sources) | {seed_digest})
    rotation_payload: dict[str, object] = {
        "previousScopeEpochId": previous["scopeEpochId"],
        "previousStateDigest": previous["stateDigest"],
        "reason": reason,
        "sourceDigests": all_sources,
        "replacementSeedRecordDigest": seed_digest,
    }
    epoch_origin_digest = route_b_artifact_digest(rotation_payload)
    provenance_payload: dict[str, object] = {
        "kind": "epoch-rotation",
        "reason": reason,
        "previousStateDigest": previous["stateDigest"],
        "epochOriginDigest": epoch_origin_digest,
        "sourceDigests": all_sources,
    }
    provenance = {
        **provenance_payload,
        "revisionProvenanceDigest": route_b_artifact_digest(provenance_payload),
    }
    epoch_binding = _epoch_binding(
        request_binding=binding,
        target_splat_id=str(replacement["targetSplatId"]),
        target_geometry_digest=str(replacement["targetGeometryDigest"]),
        component_policy_digest=str(replacement["componentPolicyDigest"]),
        discovery_policy_digest=str(replacement["discoveryPolicyDigest"]),
        epoch_origin_digest=epoch_origin_digest,
        previous_scope_epoch_id=str(previous["scopeEpochId"]),
    )
    core_ids = deepcopy(replacement["coreStableGaussianIds"])
    core_skeletons = _component_skeletons(
        geometry=geometry,
        policy=policy,
        stable_ids=core_ids,
        state="core",
        provenance_digests=all_sources,
    )
    lineage = _transition_lineage(
        parents=[],
        children=core_skeletons,
        from_revision=None,
        to_revision=0,
        subcomponent_decisions=[],
        revision_source_digests=all_sources,
        context_stable_gaussian_ids=[],
    )
    core_components = _bind_components(
        skeletons=core_skeletons,
        lineage=lineage,
    )
    return _build_state(
        scope_epoch_id=route_b_artifact_digest(epoch_binding),
        scope_revision=0,
        epoch_binding=epoch_binding,
        request_binding=binding,
        geometry=geometry,
        policy=policy,
        core_ids=core_ids,
        core_components=core_components,
        active_ids=[],
        active_components=[],
        rejected_ids=[],
        rejected_components=[],
        rejected_ledger=[],
        context_ids=[],
        seed_partition=cast(Mapping[str, Any], replacement["seedPartition"]),
        seed_record=seed,
        lineage_ledger=lineage,
        subcomponent_decision_ledger=[],
        scope_revision_ledger=[
            _scope_revision_snapshot(
                scope_revision=0,
                request_binding=binding,
                core_ids=core_ids,
                active_ids=[],
                rejected_ids=[],
                context_ids=[],
                discovery_source_digests=[],
            )
        ],
        revision_provenance_ledger=[provenance],
        provenance=provenance,
        discovery_policy=discovery,
        discovery_envelope_ledger=[],
    )


def _component_list_is_valid(
    components: object,
    *,
    expected_states: set[str],
    expected_ids: list[int],
    scope_revision: int,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    if not isinstance(components, list):
        return False
    canonical_memberships = [
        component["stableGaussianIds"]
        for component in _component_skeletons(
            geometry=geometry,
            policy=policy,
            stable_ids=expected_ids,
            state="partition",
            provenance_digests=[],
        )
    ]
    if (
        any(not isinstance(component, Mapping) for component in components)
        or [component.get("stableGaussianIds") for component in components]
        != canonical_memberships
    ):
        return False
    observed: list[int] = []
    previous_first: int | None = None
    for component in components:
        if not isinstance(component, Mapping) or set(component) != {
            "componentId",
            "stableGaussianIds",
            "worldSpaceBounds",
            "materialSummary",
            "state",
            "provenanceDigests",
            "lineageRecordDigests",
            "ageRevisions",
            "createdAtScopeRevision",
            "stateEnteredScopeRevision",
            "componentDigest",
        }:
            return False
        stable_ids = component["stableGaussianIds"]
        provenance = component["provenanceDigests"]
        lineage = component["lineageRecordDigests"]
        if (
            not _sorted_stable_ids(stable_ids, allow_empty=False)
            or component["state"] not in expected_states
            or not _digest(component["componentId"])
            or component["componentId"]
            != _component_identity(
                target_splat_id=str(geometry["targetSplatId"]),
                target_geometry_digest=str(geometry["geometryDigest"]),
                component_policy_digest=str(policy["policyDigest"]),
                stable_ids=cast(list[int], stable_ids),
            )
            or not _digest(component["componentDigest"])
            or not isinstance(provenance, list)
            or provenance != sorted(set(provenance))
            or any(not _digest(item) for item in provenance)
            or not isinstance(lineage, list)
            or not lineage
            or lineage != sorted(set(lineage))
            or any(not _digest(item) for item in lineage)
            or not _nonnegative_safe_integer(component["ageRevisions"])
            or not _nonnegative_safe_integer(component["createdAtScopeRevision"])
            or not _nonnegative_safe_integer(component["stateEnteredScopeRevision"])
            or int(component["ageRevisions"]) > scope_revision
            or int(component["createdAtScopeRevision"]) > scope_revision
            or int(component["stateEnteredScopeRevision"]) > scope_revision
            or int(component["createdAtScopeRevision"])
            > int(component["stateEnteredScopeRevision"])
            or int(component["ageRevisions"])
            != scope_revision - int(component["stateEnteredScopeRevision"])
        ):
            return False
        bounds = component["worldSpaceBounds"]
        material = component["materialSummary"]
        if (
            not isinstance(bounds, Mapping)
            or set(bounds) != {"minimum", "maximum"}
            or not all(
                isinstance(bounds[name], list)
                and len(bounds[name]) == 3
                and all(_finite_number(item) for item in bounds[name])
                for name in ("minimum", "maximum")
            )
            or any(
                float(bounds["minimum"][axis]) > float(bounds["maximum"][axis])
                for axis in range(3)
            )
            or not isinstance(material, Mapping)
            or set(material)
            != {
                "gaussianCount",
                "totalLogScaleVolume",
                "maximumDeclaredScale",
            }
            or material["gaussianCount"] != len(stable_ids)
            or not _finite_number(material["totalLogScaleVolume"])
            or not _finite_number(material["maximumDeclaredScale"])
            or float(material["maximumDeclaredScale"]) <= 0.0
        ):
            return False
        expected_components = _component_skeletons(
            geometry=geometry,
            policy=policy,
            stable_ids=cast(list[int], stable_ids),
            state=str(component["state"]),
            provenance_digests=cast(list[str], provenance),
        )
        if (
            len(expected_components) != 1
            or component["componentId"] != expected_components[0]["componentId"]
            or component["worldSpaceBounds"]
            != expected_components[0]["worldSpaceBounds"]
            or component["materialSummary"] != expected_components[0]["materialSummary"]
        ):
            return False
        first_id = stable_ids[0]
        if previous_first is not None and first_id <= previous_first:
            return False
        previous_first = first_id
        payload = {
            key: deepcopy(value)
            for key, value in component.items()
            if key != "componentDigest"
        }
        if component["componentDigest"] != route_b_artifact_digest(payload):
            return False
        observed.extend(stable_ids)
    return sorted(observed) == expected_ids and len(observed) == len(set(observed))


def _seed_partition_is_valid(
    value: object,
    *,
    target_ids: set[int],
    core_ids: set[int],
) -> bool:
    keys = {
        "recordDigest",
        "seedPolicyDigest",
        "admittedStableGaussianIds",
        "coreCandidateStableGaussianIds",
        "satelliteStableGaussianIds",
        "filteredStableGaussianIds",
        "unevaluatedStableGaussianIds",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        return False
    if not _digest(value["recordDigest"]) or not _digest(value["seedPolicyDigest"]):
        return False
    if any(
        not _sorted_stable_ids(value[key])
        for key in keys
        if key.endswith("StableGaussianIds")
    ):
        return False
    admitted = set(value["admittedStableGaussianIds"])
    seed_core = set(value["coreCandidateStableGaussianIds"])
    satellite = set(value["satelliteStableGaussianIds"])
    filtered = set(value["filteredStableGaussianIds"])
    unevaluated = set(value["unevaluatedStableGaussianIds"])
    return (
        admitted == seed_core | satellite
        and not seed_core & satellite
        and not admitted & filtered
        and not admitted & unevaluated
        and not filtered & unevaluated
        and admitted | filtered | unevaluated == target_ids
        and admitted.issubset(core_ids)
    )


def _subcomponent_decision_ledger_is_valid(
    value: object,
    *,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    if not isinstance(value, list):
        return False
    if value != sorted(
        value,
        key=lambda decision: str(decision["decisionDigest"]),
    ):
        return False
    observed: set[str] = set()
    for decision in value:
        try:
            validated = validate_target_scope_subcomponent_decision(decision)
        except TargetScopeStateError:
            return False
        digest_value = str(validated["decisionDigest"])
        if digest_value in observed or validated[
            "parentComponentId"
        ] != _component_identity(
            target_splat_id=str(geometry["targetSplatId"]),
            target_geometry_digest=str(geometry["geometryDigest"]),
            component_policy_digest=str(policy["policyDigest"]),
            stable_ids=cast(
                list[int],
                validated["parentStableGaussianIds"],
            ),
        ):
            return False
        observed.add(digest_value)
    return True


def _lineage_ledger_is_valid(
    value: object,
    *,
    target_ids: set[int],
    scope_revision: int,
    components: list[dict[str, Any]],
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
    subcomponent_decisions: list[dict[str, Any]],
    scope_revision_ledger: list[Mapping[str, Any]],
    revision_provenance_ledger: list[Mapping[str, Any]],
) -> bool:
    if not isinstance(value, list):
        return False
    if value != sorted(
        value,
        key=lambda record: (
            int(record["toScopeRevision"]),
            str(record["lineageDigest"]),
        ),
    ):
        return False
    decisions_by_digest = {
        str(decision["decisionDigest"]): decision for decision in subcomponent_decisions
    }
    decision_usage_counts: dict[str, int] = {}
    by_digest: dict[str, Mapping[str, Any]] = {}
    children_by_revision: dict[int, dict[str, Mapping[str, Any]]] = {}
    records_by_revision: dict[int, list[Mapping[str, Any]]] = {}
    consumed_by_revision: dict[int, set[str]] = {}

    def references_valid(references: object, revision: int) -> bool:
        if not isinstance(references, list):
            return False
        component_ids: list[str] = []
        for reference in references:
            if (
                not isinstance(reference, Mapping)
                or set(reference) != _COMPONENT_HISTORY_REFERENCE_KEYS
                or not _digest(reference["componentId"])
                or not _sorted_stable_ids(
                    reference["stableGaussianIds"],
                    allow_empty=False,
                )
                or not set(reference["stableGaussianIds"]).issubset(target_ids)
                or reference["componentId"]
                != _component_identity(
                    target_splat_id=str(geometry["targetSplatId"]),
                    target_geometry_digest=str(geometry["geometryDigest"]),
                    component_policy_digest=str(policy["policyDigest"]),
                    stable_ids=cast(list[int], reference["stableGaussianIds"]),
                )
                or reference["state"]
                not in {"core", "rejected", *_ACTIVE_FRONTIER_STATES}
                or not isinstance(reference["provenanceDigests"], list)
                or not reference["provenanceDigests"]
                or reference["provenanceDigests"]
                != sorted(set(reference["provenanceDigests"]))
                or any(not _digest(item) for item in reference["provenanceDigests"])
                or not _nonnegative_safe_integer(reference["ageRevisions"])
                or not _nonnegative_safe_integer(reference["createdAtScopeRevision"])
                or not _nonnegative_safe_integer(reference["stateEnteredScopeRevision"])
                or int(reference["createdAtScopeRevision"])
                > int(reference["stateEnteredScopeRevision"])
                or int(reference["stateEnteredScopeRevision"]) > revision
                or int(reference["ageRevisions"])
                != revision - int(reference["stateEnteredScopeRevision"])
            ):
                return False
            component_ids.append(str(reference["componentId"]))
        return component_ids == sorted(set(component_ids))

    for record in value:
        if not isinstance(record, Mapping) or set(record) != {
            "schemaVersion",
            "relation",
            "fromScopeRevision",
            "toScopeRevision",
            "revisionSourceDigests",
            "parentComponentIds",
            "childComponentIds",
            "parentMemberships",
            "childMemberships",
            "sharedStableGaussianIds",
            "introducedStableGaussianIds",
            "retiredStableGaussianIds",
            "retiredToContextStableGaussianIds",
            "retiredOutOfScopeStableGaussianIds",
            "subcomponentDecisionDigests",
            "lineageDigest",
        }:
            return False
        relation = record["relation"]
        from_revision = record["fromScopeRevision"]
        to_revision = record["toScopeRevision"]
        parents = record["parentComponentIds"]
        children = record["childComponentIds"]
        parent_refs = record["parentMemberships"]
        child_refs = record["childMemberships"]
        revision_sources = record["revisionSourceDigests"]
        shared_ids = record["sharedStableGaussianIds"]
        introduced_ids = record["introducedStableGaussianIds"]
        retired_ids = record["retiredStableGaussianIds"]
        retired_to_context_ids = record["retiredToContextStableGaussianIds"]
        retired_out_of_scope_ids = record["retiredOutOfScopeStableGaussianIds"]
        decision_digests = record["subcomponentDecisionDigests"]
        payload = {
            key: deepcopy(item)
            for key, item in record.items()
            if key != "lineageDigest"
        }
        if (
            record["schemaVersion"] != 1
            or relation not in _LINEAGE_RELATIONS
            or not _nonnegative_safe_integer(to_revision)
            or int(to_revision) > scope_revision
            or (
                from_revision is not None
                and (
                    not _nonnegative_safe_integer(from_revision)
                    or int(from_revision) + 1 != int(to_revision)
                )
            )
            or (int(to_revision) == 0 and from_revision is not None)
            or (int(to_revision) > 0 and from_revision is None)
            or not isinstance(revision_sources, list)
            or not revision_sources
            or revision_sources != sorted(set(revision_sources))
            or any(not _digest(item) for item in revision_sources)
            or revision_sources
            != revision_provenance_ledger[int(to_revision)]["sourceDigests"]
            or not references_valid(
                parent_refs,
                int(from_revision) if from_revision is not None else 0,
            )
            or not references_valid(child_refs, int(to_revision))
            or not isinstance(parents, list)
            or parents != [reference["componentId"] for reference in parent_refs]
            or not isinstance(children, list)
            or children != [reference["componentId"] for reference in child_refs]
            or not parents
            and not children
            or not _sorted_stable_ids(shared_ids)
            or not _sorted_stable_ids(introduced_ids)
            or not _sorted_stable_ids(retired_ids)
            or not _sorted_stable_ids(retired_to_context_ids)
            or not _sorted_stable_ids(retired_out_of_scope_ids)
            or not isinstance(decision_digests, list)
            or decision_digests != sorted(set(decision_digests))
            or any(
                digest_value not in revision_sources
                for digest_value in decision_digests
            )
            or any(
                digest_value not in decisions_by_digest
                for digest_value in decision_digests
            )
            or record["lineageDigest"] in by_digest
            or record["lineageDigest"] != route_b_artifact_digest(payload)
        ):
            return False
        parent_sets: list[set[int]] = [
            set(cast(list[int], reference["stableGaussianIds"]))
            for reference in parent_refs
        ]
        child_sets: list[set[int]] = [
            set(cast(list[int], reference["stableGaussianIds"]))
            for reference in child_refs
        ]
        parent_members = set().union(*parent_sets) if parent_sets else set()
        child_members = set().union(*child_sets) if child_sets else set()
        context_at_revision: set[int] = set(
            cast(
                list[int],
                scope_revision_ledger[int(to_revision)][
                    "requiredContextStableGaussianIds"
                ],
            )
        )
        if (
            relation
            != _lineage_relation(
                parent_count=len(parent_refs),
                child_count=len(child_refs),
                same_membership=parent_members == child_members,
            )
            or shared_ids != sorted(parent_members & child_members)
            or introduced_ids != sorted(child_members - parent_members)
            or retired_ids != sorted(parent_members - child_members)
            or retired_to_context_ids
            != sorted((parent_members - child_members) & context_at_revision)
            or retired_out_of_scope_ids
            != sorted((parent_members - child_members) - context_at_revision)
            or (not parent_refs and len(child_refs) != 1)
            or (not child_refs and len(parent_refs) != 1)
        ):
            return False
        to_revision_number = int(to_revision)
        if to_revision_number > 0:
            snapshot = scope_revision_ledger[to_revision_number]
            introduced_set = set(introduced_ids)
            if introduced_set & (
                set(snapshot["coreStableGaussianIds"])
                | set(snapshot["rejectedFrontierStableGaussianIds"])
            ):
                return False
            introduced_active = introduced_set & set(
                snapshot["activeFrontierStableGaussianIds"]
            )
            previous_discovery_sources = set(
                scope_revision_ledger[to_revision_number - 1]["discoverySourceDigests"]
            )
            new_discovery_sources = (
                set(snapshot["discoverySourceDigests"]) - previous_discovery_sources
            )
            if introduced_active and not new_discovery_sources:
                return False
        if parent_refs and child_refs:
            connected_groups = _connected_index_groups(
                len(parent_refs) + len(child_refs),
                lambda left, right: (
                    left < len(parent_refs)
                    and right >= len(parent_refs)
                    and bool(parent_sets[left] & child_sets[right - len(parent_refs)])
                ),
            )
            if len(connected_groups) != 1:
                return False
        required_decisions: set[str] = set()
        for parent_reference, parent_membership in zip(parent_refs, parent_sets):
            component_partitions: list[list[int]] = [
                sorted(parent_membership & child_membership)
                for child_membership in child_sets
                if parent_membership & child_membership
            ]
            retained_members: set[int] = {
                stable_id
                for partition in component_partitions
                for stable_id in partition
            }
            retired_members = parent_membership - retained_members
            retired_to_context: list[int] = sorted(
                retired_members & context_at_revision
            )
            retired_out_of_scope: list[int] = sorted(
                retired_members - context_at_revision
            )
            disposition_partitions: list[list[int]] = sorted(
                component_partitions
                + ([retired_to_context] if retired_to_context else [])
                + ([retired_out_of_scope] if retired_out_of_scope else []),
                key=lambda partition: partition[0],
            )
            if len(disposition_partitions) <= 1:
                continue
            matches = [
                digest_value
                for digest_value in decision_digests
                if decisions_by_digest[digest_value]["parentComponentId"]
                == parent_reference["componentId"]
                and decisions_by_digest[digest_value]["parentStableGaussianIds"]
                == parent_reference["stableGaussianIds"]
                and decisions_by_digest[digest_value]["childStableGaussianIdPartitions"]
                == disposition_partitions
                and set(
                    cast(
                        list[str],
                        decisions_by_digest[digest_value]["provenanceDigests"],
                    )
                ).issubset(revision_sources)
            ]
            if len(matches) != 1:
                return False
            required_decisions.add(matches[0])
        if required_decisions != set(decision_digests):
            return False
        for digest_value in required_decisions:
            decision_usage_counts[digest_value] = (
                decision_usage_counts.get(digest_value, 0) + 1
            )

        to_revision_number = int(to_revision)
        child_refs_at_revision = children_by_revision.setdefault(
            to_revision_number,
            {},
        )
        if set(child_refs_at_revision).intersection(children):
            return False
        if from_revision is not None:
            from_revision_number = int(from_revision)
            prior_children = children_by_revision.get(
                from_revision_number,
                {},
            )
            consumed_parents = consumed_by_revision.setdefault(
                from_revision_number,
                set(),
            )
            if (
                not set(parents).issubset(prior_children)
                or consumed_parents.intersection(parents)
                or any(
                    prior_children[parent["componentId"]] != parent
                    for parent in parent_refs
                )
            ):
                return False
            consumed_parents.update(parents)
        for child_reference, child_membership in zip(child_refs, child_sets):
            overlapping_parents = [
                parent
                for parent, parent_membership in zip(parent_refs, parent_sets)
                if child_membership & parent_membership
            ]
            previous = next(
                (
                    parent
                    for parent in overlapping_parents
                    if parent["componentId"] == child_reference["componentId"]
                ),
                None,
            )
            expected_created = (
                int(previous["createdAtScopeRevision"])
                if previous is not None
                else to_revision_number
            )
            expected_state_entered = to_revision_number
            if previous is not None and previous["state"] == child_reference["state"]:
                expected_state_entered = int(previous["stateEnteredScopeRevision"])
            expected_provenance = set(revision_sources)
            for parent in overlapping_parents:
                expected_provenance.update(parent["provenanceDigests"])
            if (
                child_reference["createdAtScopeRevision"] != expected_created
                or child_reference["stateEnteredScopeRevision"]
                != expected_state_entered
                or child_reference["ageRevisions"]
                != to_revision_number - expected_state_entered
                or child_reference["provenanceDigests"] != sorted(expected_provenance)
            ):
                return False
            child_refs_at_revision[str(child_reference["componentId"])] = cast(
                Mapping[str, Any], child_reference
            )
        by_digest[str(record["lineageDigest"])] = cast(
            Mapping[str, Any],
            record,
        )
        records_by_revision.setdefault(to_revision_number, []).append(
            cast(Mapping[str, Any], record)
        )
    if set(decision_usage_counts) != set(decisions_by_digest) or any(
        count != 1 for count in decision_usage_counts.values()
    ):
        return False
    for revision, snapshot in enumerate(scope_revision_ledger):
        references = list(children_by_revision.get(revision, {}).values())
        memberships = [
            stable_id
            for reference in references
            for stable_id in reference["stableGaussianIds"]
        ]
        if len(memberships) != len(set(memberships)):
            return False
        role_contracts = (
            (
                {"core"},
                snapshot["coreStableGaussianIds"],
            ),
            (
                _ACTIVE_FRONTIER_STATES,
                snapshot["activeFrontierStableGaussianIds"],
            ),
            (
                {"rejected"},
                snapshot["rejectedFrontierStableGaussianIds"],
            ),
        )
        for states, expected_ids in role_contracts:
            role_references = sorted(
                (reference for reference in references if reference["state"] in states),
                key=lambda reference: int(reference["stableGaussianIds"][0]),
            )
            observed_ids = sorted(
                stable_id
                for reference in role_references
                for stable_id in reference["stableGaussianIds"]
            )
            canonical_memberships = [
                component["stableGaussianIds"]
                for component in _component_skeletons(
                    geometry=geometry,
                    policy=policy,
                    stable_ids=cast(list[int], expected_ids),
                    state="partition",
                    provenance_digests=[],
                )
            ]
            if (
                observed_ids != expected_ids
                or [reference["stableGaussianIds"] for reference in role_references]
                != canonical_memberships
            ):
                return False

        previous_references = (
            list(children_by_revision.get(revision - 1, {}).values())
            if revision > 0
            else []
        )
        parent_count = len(previous_references)
        combined = previous_references + references
        connected_groups = _connected_index_groups(
            len(combined),
            lambda left, right: (
                left < parent_count
                and right >= parent_count
                and bool(
                    set(combined[left]["stableGaussianIds"])
                    & set(combined[right]["stableGaussianIds"])
                )
            ),
        )
        expected_groups = {
            (
                frozenset(
                    combined[index]["componentId"]
                    for index in group
                    if index < parent_count
                ),
                frozenset(
                    combined[index]["componentId"]
                    for index in group
                    if index >= parent_count
                ),
            )
            for group in connected_groups
        }
        actual_groups = [
            (
                frozenset(record["parentComponentIds"]),
                frozenset(record["childComponentIds"]),
            )
            for record in records_by_revision.get(revision, [])
        ]
        if (
            len(actual_groups) != len(expected_groups)
            or set(actual_groups) != expected_groups
        ):
            return False
    for revision in range(scope_revision):
        if consumed_by_revision.get(revision, set()) != set(
            children_by_revision.get(revision, {})
        ):
            return False
    current_component_ids = {str(component["componentId"]) for component in components}
    if set(children_by_revision.get(scope_revision, {})) != current_component_ids:
        return False
    for component in components:
        lineage_digests = component["lineageRecordDigests"]
        if len(lineage_digests) != 1:
            return False
        record = by_digest.get(str(lineage_digests[0]))
        if (
            record is None
            or record["toScopeRevision"] != scope_revision
            or _component_history_reference(component) not in record["childMemberships"]
        ):
            return False
    return True


def _rejected_ledger_is_valid(
    value: object,
    *,
    target_ids: set[int],
    scope_revision: int,
    active_components: list[dict[str, Any]],
    rejected_components: list[dict[str, Any]],
    lineage_ledger: list[Mapping[str, Any]],
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
    scope_revision_ledger: list[Mapping[str, Any]],
    discovery_sources_by_digest: Mapping[str, Mapping[str, Any]],
    forbidden_rejected_ids: set[int],
) -> bool:
    if not isinstance(value, list):
        return False
    if value != sorted(
        value,
        key=lambda event: (
            int(event["scopeRevision"]),
            str(event["eventDigest"]),
        ),
    ):
        return False
    component_history: dict[tuple[int, str], dict[str, Any]] = {}
    components_by_revision: dict[int, list[dict[str, Any]]] = {}
    for record in lineage_ledger:
        revision = int(record["toScopeRevision"])
        for reference in record["childMemberships"]:
            skeletons = _component_skeletons(
                geometry=geometry,
                policy=policy,
                stable_ids=reference["stableGaussianIds"],
                state=reference["state"],
                provenance_digests=reference["provenanceDigests"],
            )
            if len(skeletons) != 1:
                return False
            component_payload: dict[str, object] = {
                **skeletons[0],
                "provenanceDigests": deepcopy(reference["provenanceDigests"]),
                "lineageRecordDigests": [record["lineageDigest"]],
                "ageRevisions": reference["ageRevisions"],
                "createdAtScopeRevision": reference["createdAtScopeRevision"],
                "stateEnteredScopeRevision": reference["stateEnteredScopeRevision"],
            }
            component = {
                **component_payload,
                "componentDigest": route_b_artifact_digest(component_payload),
            }
            component_history[(revision, str(reference["componentId"]))] = component
            components_by_revision.setdefault(revision, []).append(component)

    observed: set[str] = set()
    observed_rejections: set[tuple[int, str]] = set()
    reopened_children: set[tuple[int, str]] = set()
    tail_by_component: dict[str, Mapping[str, Any]] = {}
    for event in value:
        if not isinstance(event, Mapping) or set(event) != {
            "schemaVersion",
            "event",
            "scopeRevision",
            "componentId",
            "stableGaussianIds",
            "componentDigest",
            "provenanceDigests",
            "previousEventDigest",
            "eventDigest",
        }:
            return False
        payload = {
            key: deepcopy(item) for key, item in event.items() if key != "eventDigest"
        }
        event_revision = int(event["scopeRevision"])
        if (
            not _nonnegative_safe_integer(event["scopeRevision"])
            or event_revision > scope_revision
        ):
            return False
        component_id = str(event["componentId"])
        previous_event = tail_by_component.get(component_id)
        previous_digest = event["previousEventDigest"]
        event_ids = set(event["stableGaussianIds"])
        tracking_skeletons = _component_skeletons(
            geometry=geometry,
            policy=policy,
            stable_ids=event["stableGaussianIds"],
            state=event["event"],
            provenance_digests=event["provenanceDigests"],
        )
        if len(tracking_skeletons) != 1 or (
            tracking_skeletons[0]["componentId"] != component_id
        ):
            return False

        matching_component: dict[str, Any] | None = None
        if event["event"] == "rejected":
            candidate = component_history.get((event_revision, component_id))
            if (
                candidate is not None
                and candidate["state"] == "rejected"
                and candidate["stateEnteredScopeRevision"] == event_revision
            ):
                matching_component = candidate
        else:
            candidates = [
                component
                for component in components_by_revision.get(event_revision, [])
                if component["state"] == "reopened"
                and component["stateEnteredScopeRevision"] == event_revision
                and event_ids.issubset(set(component["stableGaussianIds"]))
                and component["componentDigest"] == event["componentDigest"]
                and component["provenanceDigests"] == event["provenanceDigests"]
            ]
            if len(candidates) == 1:
                matching_component = candidates[0]

        previous_discovery_sources = (
            set(scope_revision_ledger[event_revision - 1]["discoverySourceDigests"])
            if event_revision > 0
            else set()
        )
        new_discovery_sources = (
            set(scope_revision_ledger[event_revision]["discoverySourceDigests"])
            - previous_discovery_sources
        )
        new_event_provenance = set(event["provenanceDigests"]) - (
            set(previous_event["provenanceDigests"])
            if previous_event is not None
            else set()
        )
        authorized_reopen_ids = {
            int(stable_id)
            for source_digest in new_event_provenance & new_discovery_sources
            for stable_id in discovery_sources_by_digest[source_digest][
                "admittedStableGaussianIds"
            ]
        }
        reopen_is_authorized = event_ids.issubset(authorized_reopen_ids)
        if (
            event["schemaVersion"] != 1
            or event["event"] not in {"rejected", "reopened"}
            or matching_component is None
            or (
                event["event"] == "rejected"
                and (
                    matching_component["stableGaussianIds"]
                    != event["stableGaussianIds"]
                    or matching_component["componentDigest"] != event["componentDigest"]
                    or matching_component["provenanceDigests"]
                    != event["provenanceDigests"]
                )
            )
            or not _nonnegative_safe_integer(event["scopeRevision"])
            or event_revision > scope_revision
            or not _digest(event["componentId"])
            or not _sorted_stable_ids(
                event["stableGaussianIds"],
                allow_empty=False,
            )
            or not event_ids.issubset(target_ids)
            or not _digest(event["componentDigest"])
            or not isinstance(event["provenanceDigests"], list)
            or not event["provenanceDigests"]
            or event["provenanceDigests"] != sorted(set(event["provenanceDigests"]))
            or any(not _digest(item) for item in event["provenanceDigests"])
            or (previous_digest is not None and not _digest(previous_digest))
            or previous_digest
            != (previous_event["eventDigest"] if previous_event is not None else None)
            or (
                event["event"] == "rejected"
                and previous_event is not None
                and previous_event["event"] != "reopened"
            )
            or (
                event["event"] == "reopened"
                and (previous_event is None or previous_event["event"] != "rejected")
            )
            or (event["event"] == "reopened" and not reopen_is_authorized)
            or (
                previous_event is not None
                and event["stableGaussianIds"] != previous_event["stableGaussianIds"]
            )
            or event["eventDigest"] in observed
            or event["eventDigest"] != route_b_artifact_digest(payload)
        ):
            return False
        observed.add(str(event["eventDigest"]))
        tail_by_component[component_id] = event
        if event["event"] == "rejected":
            observed_rejections.add((event_revision, component_id))
        else:
            reopened_children.add(
                (event_revision, str(matching_component["componentId"]))
            )

    expected_rejections = {
        (revision, component_id)
        for (revision, component_id), component in component_history.items()
        if component["state"] == "rejected"
        and int(component["stateEnteredScopeRevision"]) == revision
    }
    if observed_rejections != expected_rejections:
        return False
    expected_reopened_children = {
        (revision, component_id)
        for (revision, component_id), component in component_history.items()
        if component["state"] == "reopened"
        and int(component["stateEnteredScopeRevision"]) == revision
    }
    if reopened_children != expected_reopened_children:
        return False

    for revision, component_id in expected_reopened_children:
        component = component_history[(revision, component_id)]
        prior_tails: dict[str, Mapping[str, Any]] = {}
        for event in value:
            if int(event["scopeRevision"]) >= revision:
                break
            prior_tails[str(event["componentId"])] = event
        expected_parent_ids = {
            parent_id
            for parent_id, event in prior_tails.items()
            if event["event"] == "rejected"
            and set(event["stableGaussianIds"]).issubset(
                set(component["stableGaussianIds"])
            )
        }
        observed_parent_ids = {
            str(event["componentId"])
            for event in value
            if int(event["scopeRevision"]) == revision
            and event["event"] == "reopened"
            and event["componentDigest"] == component["componentDigest"]
        }
        if not expected_parent_ids or observed_parent_ids != expected_parent_ids:
            return False

    historical_tails: dict[str, Mapping[str, Any]] = {}
    event_index = 0
    for revision, snapshot in enumerate(scope_revision_ledger):
        while (
            event_index < len(value)
            and int(value[event_index]["scopeRevision"]) <= revision
        ):
            event = cast(Mapping[str, Any], value[event_index])
            historical_tails[str(event["componentId"])] = event
            event_index += 1
        historical_rejected_ids = {
            int(stable_id)
            for event in historical_tails.values()
            if event["event"] == "rejected"
            for stable_id in cast(list[int], event["stableGaussianIds"])
        }
        if historical_rejected_ids & (
            set(snapshot["coreStableGaussianIds"])
            | set(snapshot["activeFrontierStableGaussianIds"])
            | set(snapshot["requiredContextStableGaussianIds"])
        ):
            return False

    for component in rejected_components:
        tail = tail_by_component.get(str(component["componentId"]))
        if (
            tail is None
            or tail["event"] != "rejected"
            or tail["stableGaussianIds"] != component["stableGaussianIds"]
        ):
            return False
    for component in active_components:
        component_ids = set(component["stableGaussianIds"])
        overlapping_tails = [
            event
            for event in tail_by_component.values()
            if component_ids & set(event["stableGaussianIds"])
        ]
        if any(event["event"] == "rejected" for event in overlapping_tails):
            return False
        if component["state"] == "reopened" and not any(
            event["event"] == "reopened"
            and set(event["stableGaussianIds"]).issubset(component_ids)
            for event in overlapping_tails
        ):
            return False
    rejected_tail_ids = {
        int(stable_id)
        for event in tail_by_component.values()
        if event["event"] == "rejected"
        for stable_id in event["stableGaussianIds"]
    }
    if rejected_tail_ids & forbidden_rejected_ids:
        return False
    return True


def _provenance_is_valid(
    value: object,
    *,
    scope_revision: int,
    seed_record_digest: str,
    previous_scope_epoch_id: object,
) -> bool:
    if not isinstance(value, Mapping) or set(value) != {
        "kind",
        "reason",
        "previousStateDigest",
        "epochOriginDigest",
        "sourceDigests",
        "revisionProvenanceDigest",
    }:
        return False
    payload = {
        key: deepcopy(item)
        for key, item in value.items()
        if key != "revisionProvenanceDigest"
    }
    kind = value["kind"]
    sources = value["sourceDigests"]
    if (
        kind
        not in {
            "seed-shadow-bootstrap",
            "epoch-rotation",
            *_TARGET_SCOPE_REVISION_KINDS,
        }
        or not _nonempty_string(value["reason"])
        or not _digest(value["epochOriginDigest"])
        or not isinstance(sources, list)
        or not sources
        or sources != sorted(set(sources))
        or any(not _digest(item) for item in sources)
        or value["revisionProvenanceDigest"] != route_b_artifact_digest(payload)
    ):
        return False
    if scope_revision == 0:
        if kind == "seed-shadow-bootstrap":
            return (
                value["reason"] == "accepted-s0-shadow-record"
                and previous_scope_epoch_id is None
                and value["previousStateDigest"] is None
                and value["epochOriginDigest"] == seed_record_digest
                and sources == [seed_record_digest]
            )
        if (
            kind != "epoch-rotation"
            or value["reason"] not in _EPOCH_ROTATION_REASONS
            or not _digest(previous_scope_epoch_id)
            or not _digest(value["previousStateDigest"])
            or seed_record_digest not in sources
        ):
            return False
        rotation_payload = {
            "previousScopeEpochId": previous_scope_epoch_id,
            "previousStateDigest": value["previousStateDigest"],
            "reason": value["reason"],
            "sourceDigests": sources,
            "replacementSeedRecordDigest": seed_record_digest,
        }
        return value["epochOriginDigest"] == route_b_artifact_digest(rotation_payload)
    return (
        kind in _TARGET_SCOPE_REVISION_KINDS
        and value["reason"] not in _EPOCH_ROTATION_REASONS
        and _digest(value["previousStateDigest"])
    )


def _scope_revision_ledger_is_valid(
    value: object,
    *,
    scope_revision: int,
    target_ids: set[int],
    seed_request_binding: Mapping[str, Any],
    current_request_binding: Mapping[str, Any],
    current_core_ids: list[int],
    current_active_ids: list[int],
    current_rejected_ids: list[int],
    current_context_ids: list[int],
    current_discovery_source_digests: list[str],
) -> bool:
    if not isinstance(value, list) or len(value) != scope_revision + 1:
        return False
    previous_core: set[int] = set()
    previous_active: set[int] = set()
    previous_rejected: set[int] = set()
    previous_discovery_sources: set[str] = set()
    previous_context_revision = -1
    for revision, snapshot in enumerate(value):
        if not isinstance(snapshot, Mapping) or set(snapshot) != {
            "schemaVersion",
            "scopeRevision",
            "requestBinding",
            "coreStableGaussianIds",
            "activeFrontierStableGaussianIds",
            "rejectedFrontierStableGaussianIds",
            "requiredContextStableGaussianIds",
            "discoverySourceDigests",
            "scopeRevisionDigest",
        }:
            return False
        snapshot_binding = _validated_request_binding(snapshot["requestBinding"])
        role_ids = [
            snapshot["coreStableGaussianIds"],
            snapshot["activeFrontierStableGaussianIds"],
            snapshot["rejectedFrontierStableGaussianIds"],
            snapshot["requiredContextStableGaussianIds"],
        ]
        role_sets = [set(ids) for ids in role_ids]
        discovery_sources = snapshot["discoverySourceDigests"]
        discovery_source_set = set(discovery_sources)
        payload = {
            key: deepcopy(item)
            for key, item in snapshot.items()
            if key != "scopeRevisionDigest"
        }
        if (
            snapshot["schemaVersion"] != 1
            or snapshot["scopeRevision"] != revision
            or snapshot["requestBinding"] != snapshot_binding
            or snapshot_binding["targetContextId"]
            != seed_request_binding["targetContextId"]
            or snapshot_binding["dependencyToken"]
            != seed_request_binding["dependencyToken"]
            or int(snapshot_binding["contextRevision"]) < previous_context_revision
            or (revision == 0 and snapshot_binding != seed_request_binding)
            or any(not _sorted_stable_ids(ids) for ids in role_ids)
            or any(not role.issubset(target_ids) for role in role_sets)
            or any(
                role_sets[left] & role_sets[right]
                for left in range(len(role_sets))
                for right in range(left + 1, len(role_sets))
            )
            or not previous_core.issubset(role_sets[0])
            or (
                revision > 0
                and not (role_sets[2] - previous_rejected).issubset(previous_active)
            )
            or not isinstance(discovery_sources, list)
            or discovery_sources != sorted(set(discovery_sources))
            or any(not _digest(item) for item in discovery_sources)
            or not previous_discovery_sources.issubset(discovery_source_set)
            or snapshot["scopeRevisionDigest"] != route_b_artifact_digest(payload)
        ):
            return False
        previous_core = role_sets[0]
        previous_active = role_sets[1]
        previous_rejected = role_sets[2]
        previous_discovery_sources = discovery_source_set
        previous_context_revision = int(snapshot_binding["contextRevision"])
    current = value[-1]
    return (
        current["requestBinding"] == current_request_binding
        and current["coreStableGaussianIds"] == current_core_ids
        and current["activeFrontierStableGaussianIds"] == current_active_ids
        and current["rejectedFrontierStableGaussianIds"] == current_rejected_ids
        and current["requiredContextStableGaussianIds"] == current_context_ids
        and current["discoverySourceDigests"] == current_discovery_source_digests
    )


def _discovery_envelope_ledger_is_valid(
    value: object,
    *,
    scope_epoch_id: str,
    target_splat_id: str,
    dependency_token: Mapping[str, Any],
    target_geometry_digest: str,
    component_policy_digest: str,
    discovery_policy: Mapping[str, Any],
    geometry: Mapping[str, Any],
    scope_revision_ledger: list[Mapping[str, Any]],
    revision_provenance_ledger: list[Mapping[str, Any]],
) -> bool:
    if not isinstance(value, list):
        return False
    validated: list[dict[str, object]] = []
    try:
        validated = [_validate_target_scope_discovery_source(item) for item in value]
    except TargetScopeStateError:
        return False
    source_digests = [str(source["sourceRecordDigest"]) for source in validated]
    authority_digests = [str(source["sourceAuthorityDigest"]) for source in validated]
    if (
        value != validated
        or len(source_digests) != len(set(source_digests))
        or len(authority_digests) != len(set(authority_digests))
        or len(validated) > int(discovery_policy["maximumSourceRecordsPerEpoch"])
    ):
        return False
    target_ids = set(geometry["stableGaussianIds"])
    rows_by_id = {int(row["stableGaussianId"]): row for row in geometry["rows"]}
    admitted_union: set[int] = set()
    for source in validated:
        admitted_ids = cast(list[int], source["admittedStableGaussianIds"])
        if (
            source["targetSplatId"] != target_splat_id
            or source["dependencyToken"] != dependency_token
            or source["scopeEpochId"] != scope_epoch_id
            or source["targetGeometryDigest"] != target_geometry_digest
            or source["componentPolicyDigest"] != component_policy_digest
            or source["discoveryPolicyDigest"] != discovery_policy["policyDigest"]
            or source["discoveryDomainDigest"]
            != discovery_policy["discoveryDomain"]["domainDigest"]
            or not set(admitted_ids).issubset(target_ids)
        ):
            return False
        try:
            _validate_discovery_source_spatial_domain(
                source=source,
                policy=discovery_policy,
                rows_by_id=rows_by_id,
            )
        except TargetScopeStateError:
            return False
        admitted_union.update(admitted_ids)
    if len(admitted_union) > int(
        discovery_policy["maximumAdmittedStableGaussianIdsPerEpoch"]
    ):
        return False

    known_sources: set[str] = set()
    expected_source_digests: list[str] = []
    source_by_digest = {
        str(source["sourceRecordDigest"]): source for source in validated
    }
    for revision, snapshot in enumerate(scope_revision_ledger):
        snapshot_sources = set(snapshot["discoverySourceDigests"])
        new_sources = snapshot_sources - known_sources
        if revision > 0:
            previous_envelope_ids = {
                int(stable_id)
                for source_digest in known_sources
                for stable_id in cast(
                    list[int],
                    source_by_digest[source_digest]["admittedStableGaussianIds"],
                )
            }
            protected_active_ids = previous_envelope_ids & set(
                scope_revision_ledger[revision - 1]["activeFrontierStableGaussianIds"]
            )
            current_active_ids = set(snapshot["activeFrontierStableGaussianIds"])
            current_scoped_ids = (
                set(snapshot["coreStableGaussianIds"])
                | current_active_ids
                | set(snapshot["rejectedFrontierStableGaussianIds"])
            )
            if not protected_active_ids.issubset(current_scoped_ids):
                return False
            if revision_provenance_ledger[revision][
                "kind"
            ] in _NON_REJECTION_DISCOVERY_KINDS and not protected_active_ids.issubset(
                current_active_ids
            ):
                return False
        if (
            not snapshot_sources.issubset(source_by_digest)
            or (revision == 0 and snapshot_sources)
            or not new_sources.issubset(
                set(revision_provenance_ledger[revision]["sourceDigests"])
            )
        ):
            return False
        active_ids = set(snapshot["activeFrontierStableGaussianIds"])
        core_ids = set(snapshot["coreStableGaussianIds"])
        context_ids = set(snapshot["requiredContextStableGaussianIds"])
        newly_admitted_ids = {
            int(stable_id)
            for source_digest in new_sources
            for stable_id in cast(
                list[int],
                source_by_digest[source_digest]["admittedStableGaussianIds"],
            )
        }
        if revision > 0:
            newly_active_ids = active_ids - set(
                scope_revision_ledger[revision - 1]["activeFrontierStableGaussianIds"]
            )
            if not newly_active_ids.issubset(newly_admitted_ids):
                return False
        for source_digest in new_sources:
            admitted_ids = set(
                cast(
                    list[int],
                    source_by_digest[source_digest]["admittedStableGaussianIds"],
                )
            )
            if (
                not admitted_ids.issubset(active_ids)
                or admitted_ids & core_ids
                or admitted_ids & context_ids
            ):
                return False
        expected_source_digests.extend(sorted(new_sources))
        known_sources = snapshot_sources
    return (
        known_sources == set(source_digests)
        and source_digests == expected_source_digests
    )


def _revision_provenance_ledger_is_valid(
    value: object,
    *,
    scope_revision: int,
    seed_record_digest: str,
    previous_scope_epoch_id: object,
    current_provenance: Mapping[str, Any],
) -> bool:
    if not isinstance(value, list) or len(value) != scope_revision + 1:
        return False
    epoch_origin_digest: object = None
    for revision, provenance in enumerate(value):
        if not _provenance_is_valid(
            provenance,
            scope_revision=revision,
            seed_record_digest=seed_record_digest,
            previous_scope_epoch_id=previous_scope_epoch_id,
        ):
            return False
        if not isinstance(provenance, Mapping):
            return False
        if revision == 0:
            epoch_origin_digest = provenance["epochOriginDigest"]
        elif provenance["epochOriginDigest"] != epoch_origin_digest:
            return False
    return value[-1] == current_provenance


def _state_payload_at_revision(
    value: Mapping[str, Any],
    *,
    revision: int,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, object]:
    scope_ledger = cast(list[Mapping[str, Any]], value["scopeRevisionLedger"])
    provenance_ledger = cast(list[Mapping[str, Any]], value["revisionProvenanceLedger"])
    snapshot = scope_ledger[revision]
    lineage_prefix = [
        deepcopy(record)
        for record in cast(list[Mapping[str, Any]], value["componentLineageLedger"])
        if int(record["toScopeRevision"]) <= revision
    ]
    records_at_revision = [
        record
        for record in lineage_prefix
        if int(record["toScopeRevision"]) == revision
    ]
    components: list[dict[str, Any]] = []
    for record in records_at_revision:
        for reference in record["childMemberships"]:
            skeletons = _component_skeletons(
                geometry=geometry,
                policy=policy,
                stable_ids=reference["stableGaussianIds"],
                state=reference["state"],
                provenance_digests=reference["provenanceDigests"],
            )
            if len(skeletons) != 1:
                raise TargetScopeStateInternalError(
                    "Historical component membership is not canonical."
                )
            component_payload: dict[str, object] = {
                **skeletons[0],
                "provenanceDigests": deepcopy(reference["provenanceDigests"]),
                "lineageRecordDigests": [record["lineageDigest"]],
                "ageRevisions": reference["ageRevisions"],
                "createdAtScopeRevision": reference["createdAtScopeRevision"],
                "stateEnteredScopeRevision": reference["stateEnteredScopeRevision"],
            }
            components.append(
                {
                    **component_payload,
                    "componentDigest": route_b_artifact_digest(component_payload),
                }
            )
    components.sort(key=lambda component: int(component["stableGaussianIds"][0]))
    referenced_decisions = {
        digest_value
        for record in lineage_prefix
        for digest_value in record["subcomponentDecisionDigests"]
    }
    decision_prefix = [
        deepcopy(decision)
        for decision in cast(
            list[Mapping[str, Any]], value["subcomponentDecisionLedger"]
        )
        if decision["decisionDigest"] in referenced_decisions
    ]
    rejected_prefix = [
        deepcopy(event)
        for event in cast(list[Mapping[str, Any]], value["rejectedFrontierLedger"])
        if int(event["scopeRevision"]) <= revision
    ]
    core_components = [
        component for component in components if component["state"] == "core"
    ]
    active_components = [
        component
        for component in components
        if component["state"] in _ACTIVE_FRONTIER_STATES
    ]
    rejected_components = [
        component for component in components if component["state"] == "rejected"
    ]
    snapshot_source_digests = set(snapshot["discoverySourceDigests"])
    discovery_prefix = [
        deepcopy(source)
        for source in cast(list[Mapping[str, Any]], value["discoveryEnvelopeLedger"])
        if source["sourceRecordDigest"] in snapshot_source_digests
    ]
    provenance = deepcopy(provenance_ledger[revision])
    return {
        "schemaVersion": TARGET_SCOPE_STATE_SCHEMA_VERSION,
        "stateKind": TARGET_SCOPE_STATE_KIND,
        "status": "experimental-shadow",
        "scopeEpochId": value["scopeEpochId"],
        "scopeRevision": revision,
        "epochBinding": deepcopy(value["epochBinding"]),
        "requestBinding": deepcopy(snapshot["requestBinding"]),
        "targetSplatId": value["targetSplatId"],
        "targetGeometry": deepcopy(value["targetGeometry"]),
        "targetGeometryDigest": value["targetGeometryDigest"],
        "targetStableGaussianIds": deepcopy(value["targetStableGaussianIds"]),
        "coreStableGaussianIds": deepcopy(snapshot["coreStableGaussianIds"]),
        "coreComponents": core_components,
        "discoveryEnvelopeLedger": discovery_prefix,
        "activeFrontierStableGaussianIds": deepcopy(
            snapshot["activeFrontierStableGaussianIds"]
        ),
        "activeFrontierComponents": active_components,
        "rejectedFrontierStableGaussianIds": deepcopy(
            snapshot["rejectedFrontierStableGaussianIds"]
        ),
        "rejectedFrontierComponents": rejected_components,
        "rejectedFrontierLedger": rejected_prefix,
        "requiredContextStableGaussianIds": deepcopy(
            snapshot["requiredContextStableGaussianIds"]
        ),
        "seedPartition": deepcopy(value["seedPartition"]),
        "seedRecord": deepcopy(value["seedRecord"]),
        "componentPolicy": deepcopy(value["componentPolicy"]),
        "componentPolicyDigest": value["componentPolicyDigest"],
        "discoveryPolicy": deepcopy(value["discoveryPolicy"]),
        "discoveryPolicyDigest": value["discoveryPolicyDigest"],
        "componentLineageLedger": lineage_prefix,
        "subcomponentDecisionLedger": decision_prefix,
        "scopeRevisionLedger": deepcopy(scope_ledger[: revision + 1]),
        "revisionProvenanceLedger": deepcopy(provenance_ledger[: revision + 1]),
        "provenance": provenance,
        "provenanceDigest": provenance["revisionProvenanceDigest"],
    }


def _historical_state_chain_is_valid(
    value: Mapping[str, Any],
    *,
    scope_revision: int,
    geometry: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    provenance_ledger = cast(list[Mapping[str, Any]], value["revisionProvenanceLedger"])
    validated_predecessor_digests: list[str] = []
    for revision in range(scope_revision, 0, -1):
        previous_payload = _state_payload_at_revision(
            value,
            revision=revision - 1,
            geometry=geometry,
            policy=policy,
        )
        previous_digest = route_b_artifact_digest(previous_payload)
        validated_predecessor_digests.append(previous_digest)
        if provenance_ledger[revision]["previousStateDigest"] != previous_digest:
            return False
        if _validated_state_digest_is_cached(previous_digest):
            for digest_value in validated_predecessor_digests:
                _remember_validated_state_digest(digest_value)
            return True
    for digest_value in validated_predecessor_digests:
        _remember_validated_state_digest(digest_value)
    return True


def is_target_scope_state(value: object) -> bool:
    """Validate canonical role, lineage, provenance, epoch, and state digests."""

    if not isinstance(value, Mapping) or set(value) != _STATE_KEYS:
        return False
    try:
        if (
            value["schemaVersion"] != TARGET_SCOPE_STATE_SCHEMA_VERSION
            or value["stateKind"] != TARGET_SCOPE_STATE_KIND
            or value["status"] != "experimental-shadow"
            or not _digest(value["scopeEpochId"])
            or not _nonnegative_safe_integer(value["scopeRevision"])
            or not _digest(value["targetGeometryDigest"])
            or not _digest(value["componentPolicyDigest"])
            or not _digest(value["discoveryPolicyDigest"])
            or not _digest(value["provenanceDigest"])
            or not _digest(value["stateDigest"])
            or not _nonempty_string(value["targetSplatId"])
        ):
            return False
        geometry = _validated_geometry(value["targetGeometry"])
        if (
            geometry["targetSplatId"] != value["targetSplatId"]
            or geometry["geometryDigest"] != value["targetGeometryDigest"]
            or geometry["stableGaussianIds"] != value["targetStableGaussianIds"]
            or value["targetGeometry"] != geometry
        ):
            return False
        scope_revision = int(value["scopeRevision"])
        request_binding = _validated_request_binding(value["requestBinding"])
        if request_binding["dependencyToken"]["splatId"] != value["targetSplatId"]:
            return False
        epoch_binding = value["epochBinding"]
        if not isinstance(epoch_binding, Mapping) or set(epoch_binding) != {
            "schemaVersion",
            "targetContextId",
            "targetSplatId",
            "dependencyToken",
            "targetGeometryDigest",
            "componentPolicyDigest",
            "discoveryPolicyDigest",
            "epochOriginDigest",
            "previousScopeEpochId",
        }:
            return False
        if (
            epoch_binding["schemaVersion"] != 1
            or epoch_binding["targetContextId"] != request_binding["targetContextId"]
            or epoch_binding["targetSplatId"] != value["targetSplatId"]
            or epoch_binding["dependencyToken"] != request_binding["dependencyToken"]
            or epoch_binding["targetGeometryDigest"] != value["targetGeometryDigest"]
            or epoch_binding["componentPolicyDigest"] != value["componentPolicyDigest"]
            or epoch_binding["discoveryPolicyDigest"] != value["discoveryPolicyDigest"]
            or not _digest(epoch_binding["epochOriginDigest"])
            or (
                epoch_binding["previousScopeEpochId"] is not None
                and not _digest(epoch_binding["previousScopeEpochId"])
            )
            or value["scopeEpochId"] != route_b_artifact_digest(epoch_binding)
        ):
            return False
        target_ids = value["targetStableGaussianIds"]
        core_ids = value["coreStableGaussianIds"]
        active_ids = value["activeFrontierStableGaussianIds"]
        rejected_ids = value["rejectedFrontierStableGaussianIds"]
        context_ids = value["requiredContextStableGaussianIds"]
        if not _sorted_stable_ids(target_ids, allow_empty=False) or not all(
            _sorted_stable_ids(ids)
            for ids in (core_ids, active_ids, rejected_ids, context_ids)
        ):
            return False
        target_set = set(target_ids)
        role_sets = [
            set(core_ids),
            set(active_ids),
            set(rejected_ids),
            set(context_ids),
        ]
        if any(not role.issubset(target_set) for role in role_sets) or any(
            role_sets[left] & role_sets[right]
            for left in range(len(role_sets))
            for right in range(left + 1, len(role_sets))
        ):
            return False
        policy = validate_target_scope_component_policy(value["componentPolicy"])
        if (
            policy["policyDigest"] != value["componentPolicyDigest"]
            or value["componentPolicy"] != policy
        ):
            return False
        if (
            not _component_list_is_valid(
                value["coreComponents"],
                expected_states={"core"},
                expected_ids=core_ids,
                scope_revision=scope_revision,
                geometry=geometry,
                policy=policy,
            )
            or not _component_list_is_valid(
                value["activeFrontierComponents"],
                expected_states=_ACTIVE_FRONTIER_STATES,
                expected_ids=active_ids,
                scope_revision=scope_revision,
                geometry=geometry,
                policy=policy,
            )
            or not _component_list_is_valid(
                value["rejectedFrontierComponents"],
                expected_states={"rejected"},
                expected_ids=rejected_ids,
                scope_revision=scope_revision,
                geometry=geometry,
                policy=policy,
            )
        ):
            return False
        components = _state_components(cast(Mapping[str, Any], value))
        component_ids = [str(component["componentId"]) for component in components]
        if len(component_ids) != len(set(component_ids)):
            return False
        discovery_policy = validate_target_scope_discovery_policy(
            value["discoveryPolicy"]
        )
        if (
            discovery_policy["policyDigest"] != value["discoveryPolicyDigest"]
            or value["discoveryPolicy"] != discovery_policy
        ):
            return False
        seed_partition = value["seedPartition"]
        seed_record = value["seedRecord"]
        if (
            not isinstance(seed_partition, Mapping)
            or not isinstance(seed_record, Mapping)
            or not is_conservative_seed_shadow_record(seed_record)
            or _seed_partition(seed_record) != seed_partition
            or seed_record["targetSplatId"] != value["targetSplatId"]
            or seed_record["targetGeometryDigest"] != value["targetGeometryDigest"]
            or seed_record["targetStableGaussianIds"] != target_ids
            or seed_record["requestBinding"]["targetContextId"]
            != epoch_binding["targetContextId"]
            or seed_record["requestBinding"]["dependencyToken"]
            != epoch_binding["dependencyToken"]
            or not _seed_partition_is_valid(
                seed_partition,
                target_ids=target_set,
                core_ids=set(core_ids),
            )
        ):
            return False
        rows_by_id = {int(row["stableGaussianId"]): row for row in geometry["rows"]}
        if not _discovery_domain_is_target_local(
            core_stable_ids=cast(
                list[int], seed_partition["admittedStableGaussianIds"]
            ),
            target_splat_id=str(geometry["targetSplatId"]),
            policy=discovery_policy,
            rows_by_id=rows_by_id,
        ):
            return False
        if scope_revision == 0 and (
            core_ids != seed_partition["admittedStableGaussianIds"]
            or active_ids != []
            or rejected_ids != []
            or context_ids != []
            or value["rejectedFrontierLedger"] != []
            or value["subcomponentDecisionLedger"] != []
        ):
            return False
        discovery_envelope_ledger = value["discoveryEnvelopeLedger"]
        if not isinstance(discovery_envelope_ledger, list):
            return False
        discovery_source_digests = [
            str(record["sourceRecordDigest"]) for record in discovery_envelope_ledger
        ]
        scope_revision_ledger = value["scopeRevisionLedger"]
        if not _scope_revision_ledger_is_valid(
            scope_revision_ledger,
            scope_revision=scope_revision,
            target_ids=target_set,
            seed_request_binding=cast(Mapping[str, Any], seed_record["requestBinding"]),
            current_request_binding=request_binding,
            current_core_ids=core_ids,
            current_active_ids=active_ids,
            current_rejected_ids=rejected_ids,
            current_context_ids=context_ids,
            current_discovery_source_digests=sorted(discovery_source_digests),
        ):
            return False
        genesis_scope = scope_revision_ledger[0]
        if (
            genesis_scope["coreStableGaussianIds"]
            != seed_partition["admittedStableGaussianIds"]
            or genesis_scope["activeFrontierStableGaussianIds"] != []
            or genesis_scope["rejectedFrontierStableGaussianIds"] != []
            or genesis_scope["requiredContextStableGaussianIds"] != []
            or genesis_scope["discoverySourceDigests"] != []
        ):
            return False
        decision_ledger = value["subcomponentDecisionLedger"]
        if not isinstance(
            decision_ledger, list
        ) or not _subcomponent_decision_ledger_is_valid(
            decision_ledger,
            geometry=geometry,
            policy=policy,
        ):
            return False
        provenance = value["provenance"]
        provenance_ledger = value["revisionProvenanceLedger"]
        if (
            not isinstance(provenance, Mapping)
            or not _revision_provenance_ledger_is_valid(
                provenance_ledger,
                scope_revision=scope_revision,
                seed_record_digest=str(seed_partition["recordDigest"]),
                previous_scope_epoch_id=epoch_binding["previousScopeEpochId"],
                current_provenance=provenance,
            )
            or value["provenanceDigest"] != provenance["revisionProvenanceDigest"]
            or epoch_binding["epochOriginDigest"]
            != provenance_ledger[0]["epochOriginDigest"]
        ):
            return False
        if not _discovery_envelope_ledger_is_valid(
            discovery_envelope_ledger,
            scope_epoch_id=str(value["scopeEpochId"]),
            target_splat_id=str(value["targetSplatId"]),
            dependency_token=cast(
                Mapping[str, Any], request_binding["dependencyToken"]
            ),
            target_geometry_digest=str(value["targetGeometryDigest"]),
            component_policy_digest=str(value["componentPolicyDigest"]),
            discovery_policy=discovery_policy,
            geometry=geometry,
            scope_revision_ledger=cast(list[Mapping[str, Any]], scope_revision_ledger),
            revision_provenance_ledger=cast(list[Mapping[str, Any]], provenance_ledger),
        ):
            return False
        if not _lineage_ledger_is_valid(
            value["componentLineageLedger"],
            target_ids=target_set,
            scope_revision=scope_revision,
            components=components,
            geometry=geometry,
            policy=policy,
            subcomponent_decisions=decision_ledger,
            scope_revision_ledger=cast(list[Mapping[str, Any]], scope_revision_ledger),
            revision_provenance_ledger=cast(list[Mapping[str, Any]], provenance_ledger),
        ) or not _rejected_ledger_is_valid(
            value["rejectedFrontierLedger"],
            target_ids=target_set,
            scope_revision=scope_revision,
            active_components=cast(
                list[dict[str, Any]],
                value["activeFrontierComponents"],
            ),
            rejected_components=cast(
                list[dict[str, Any]],
                value["rejectedFrontierComponents"],
            ),
            lineage_ledger=cast(
                list[Mapping[str, Any]], value["componentLineageLedger"]
            ),
            geometry=geometry,
            policy=policy,
            scope_revision_ledger=cast(list[Mapping[str, Any]], scope_revision_ledger),
            discovery_sources_by_digest={
                str(source["sourceRecordDigest"]): cast(Mapping[str, Any], source)
                for source in discovery_envelope_ledger
            },
            forbidden_rejected_ids=set(core_ids) | set(context_ids),
        ):
            return False
        if not _historical_state_chain_is_valid(
            cast(Mapping[str, Any], value),
            scope_revision=scope_revision,
            geometry=geometry,
            policy=policy,
        ):
            return False
        payload = {
            key: deepcopy(item) for key, item in value.items() if key != "stateDigest"
        }
        state_digest_is_valid = value["stateDigest"] == route_b_artifact_digest(payload)
        if state_digest_is_valid:
            _remember_validated_state_digest(str(value["stateDigest"]))
        return state_digest_is_valid
    except (
        KeyError,
        OverflowError,
        TargetScopeStateError,
        TypeError,
        ValueError,
    ):
        return False


def canonical_target_scope_state_bytes(value: object) -> bytes:
    if not is_target_scope_state(value) or not isinstance(value, Mapping):
        raise TargetScopeStateValidationError("Target Scope State record is invalid.")
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def target_scope_state_identity(value: object) -> dict[str, object]:
    """Return every externally bound identity required for exact restoration."""

    if not is_target_scope_state(value) or not isinstance(value, Mapping):
        raise TargetScopeStateValidationError("Target Scope State record is invalid.")
    seed_partition = cast(Mapping[str, Any], value["seedPartition"])
    return {
        "scopeEpochId": value["scopeEpochId"],
        "scopeRevision": value["scopeRevision"],
        "stateDigest": value["stateDigest"],
        "requestBindingDigest": route_b_artifact_digest(value["requestBinding"]),
        "targetSplatId": value["targetSplatId"],
        "targetUniverseDigest": route_b_artifact_digest(
            {
                "stableGaussianIds": value["targetStableGaussianIds"],
            }
        ),
        "targetGeometryDigest": value["targetGeometryDigest"],
        "componentPolicyDigest": value["componentPolicyDigest"],
        "discoveryPolicyDigest": value["discoveryPolicyDigest"],
        "provenanceDigest": value["provenanceDigest"],
        "seedRecordDigest": seed_partition["recordDigest"],
    }


def restore_target_scope_state(
    value: object,
    *,
    expected_identity: object,
) -> dict[str, Any]:
    """Copy one prior immutable state only when every bound identity matches."""

    if not isinstance(expected_identity, Mapping):
        raise TargetScopeStateValidationError(
            "Target Scope restoration identity is invalid."
        )
    identity = target_scope_state_identity(value)
    if set(expected_identity) != set(identity) or dict(expected_identity) != identity:
        raise TargetScopeStateIncompatibilityError(
            "Target Scope State cannot be restored under a different identity."
        )
    return deepcopy(dict(cast(Mapping[str, Any], value)))


__all__ = [
    "TARGET_SCOPE_STATE_KIND",
    "TARGET_SCOPE_DISCOVERY_POLICY_SCHEMA_VERSION",
    "TARGET_SCOPE_DISCOVERY_SOURCE_SCHEMA_VERSION",
    "TargetScopeStateError",
    "TargetScopeStateIncompatibilityError",
    "TargetScopeStateInternalError",
    "TargetScopeStateTransitionError",
    "TargetScopeStateValidationError",
    "admit_target_scope_discovery_sources",
    "bootstrap_target_scope_state_from_seed",
    "canonical_target_scope_state_bytes",
    "create_target_scope_component_policy",
    "create_target_scope_boundary_contact_shadow_source",
    "create_target_scope_discovery_policy",
    "create_target_scope_observation_shadow_source",
    "create_target_scope_reviewed_support_shadow_source",
    "create_target_scope_subcomponent_decision",
    "is_target_scope_state",
    "restore_target_scope_state",
    "revise_target_scope_state",
    "rotate_target_scope_epoch",
    "target_scope_state_identity",
    "validate_target_scope_component_policy",
    "validate_target_scope_discovery_policy",
    "validate_target_scope_subcomponent_decision",
]

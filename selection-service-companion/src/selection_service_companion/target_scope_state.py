"""Deterministic component-level Target Scope State shadow records.

The module owns pure schema construction, component lineage, Scope Epoch and
Scope Revision transitions, and exact restoration. It consumes accepted S0
Conservative Seed shadow records without changing production Evidence,
readiness, Candidate, Browser protocol, or Native Selection behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
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


_VALIDATED_STATE_DIGEST_CACHE_LIMIT: Final = 256
_validated_state_digests: set[str] = set()
_validated_state_digest_order: list[str] = []
_validated_state_digest_lock = Lock()


TARGET_SCOPE_COMPONENT_POLICY_SCHEMA_VERSION: Final = 1
TARGET_SCOPE_STATE_SCHEMA_VERSION: Final = 1
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
) -> list[dict[str, Any]]:
    latest_by_component: dict[str, Mapping[str, Any]] = {}
    for event in previous_ledger:
        latest_by_component[str(event["componentId"])] = event
    for component in active_components:
        previous_event = latest_by_component.get(str(component["componentId"]))
        if (
            previous_event is not None
            and previous_event["event"] == "rejected"
            and component["state"] != "reopened"
        ):
            raise TargetScopeStateTransitionError(
                "A rejected Frontier component must explicitly reopen."
            )
    candidates = [
        component
        for component in rejected_components + active_components
        if component["state"] in {"rejected", "reopened"}
        and component["stateEnteredScopeRevision"] == scope_revision
    ]
    appended: list[dict[str, Any]] = []
    for component in candidates:
        component_id = str(component["componentId"])
        previous_event = latest_by_component.get(component_id)
        if (
            component["state"] == "rejected"
            and previous_event is not None
            and previous_event["event"] != "reopened"
        ) or (
            component["state"] == "reopened"
            and (previous_event is None or previous_event["event"] != "rejected")
        ):
            raise TargetScopeStateTransitionError(
                "Rejected Frontier event history is invalid."
            )
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "event": component["state"],
            "scopeRevision": scope_revision,
            "componentId": component_id,
            "stableGaussianIds": deepcopy(component["stableGaussianIds"]),
            "componentDigest": component["componentDigest"],
            "provenanceDigests": deepcopy(component["provenanceDigests"]),
            "previousEventDigest": (
                previous_event["eventDigest"] if previous_event is not None else None
            ),
        }
        event = {**payload, "eventDigest": route_b_artifact_digest(payload)}
        appended.append(event)
        latest_by_component[component_id] = event
    ledger = deepcopy(previous_ledger) + appended
    ledger.sort(
        key=lambda event: (
            int(event["scopeRevision"]),
            str(event["eventDigest"]),
        )
    )
    return ledger


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
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "scopeRevision": scope_revision,
        "requestBinding": deepcopy(request_binding),
        "coreStableGaussianIds": list(core_ids),
        "activeFrontierStableGaussianIds": list(active_ids),
        "rejectedFrontierStableGaussianIds": list(rejected_ids),
        "requiredContextStableGaussianIds": list(context_ids),
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
            )
        ],
        revision_provenance_ledger=[provenance],
        provenance=provenance,
        discovery_envelope_ledger=[],
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
        kind not in {"new-observation", "scope-transition"}
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
            ),
        ],
        revision_provenance_ledger=[
            *deepcopy(previous["revisionProvenanceLedger"]),
            deepcopy(provenance),
        ],
        provenance=provenance,
        discovery_envelope_ledger=[],
    )


def rotate_target_scope_epoch(
    *,
    previous_state: object,
    seed_record: object,
    target_geometry: object,
    component_policy: object,
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
    )
    geometry = _validated_geometry(target_geometry)
    policy = cast(Mapping[str, Any], replacement["componentPolicy"])
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
            )
        ],
        revision_provenance_ledger=[provenance],
        provenance=provenance,
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
            component_history[(revision, str(reference["componentId"]))] = {
                **component_payload,
                "componentDigest": route_b_artifact_digest(component_payload),
            }
    observed: set[str] = set()
    observed_state_entries: set[tuple[int, str, str]] = set()
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
        component_id = str(event["componentId"])
        previous_digest = event["previousEventDigest"]
        previous_event = tail_by_component.get(component_id)
        expected_component = component_history.get(
            (int(event["scopeRevision"]), component_id)
        )
        if (
            event["schemaVersion"] != 1
            or event["event"] not in {"rejected", "reopened"}
            or expected_component is None
            or expected_component["state"] != event["event"]
            or int(event["scopeRevision"])
            != int(expected_component["stateEnteredScopeRevision"])
            or expected_component["stableGaussianIds"] != event["stableGaussianIds"]
            or expected_component["componentDigest"] != event["componentDigest"]
            or expected_component["provenanceDigests"] != event["provenanceDigests"]
            or not _nonnegative_safe_integer(event["scopeRevision"])
            or int(event["scopeRevision"]) > scope_revision
            or not _digest(event["componentId"])
            or not _sorted_stable_ids(
                event["stableGaussianIds"],
                allow_empty=False,
            )
            or not set(event["stableGaussianIds"]).issubset(target_ids)
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
            or (
                previous_event is not None
                and event["stableGaussianIds"] != previous_event["stableGaussianIds"]
            )
            or event["eventDigest"] in observed
            or event["eventDigest"] != route_b_artifact_digest(payload)
        ):
            return False
        digest_value = str(event["eventDigest"])
        observed.add(digest_value)
        tail_by_component[component_id] = event
        observed_state_entries.add(
            (int(event["scopeRevision"]), component_id, str(event["event"]))
        )

    expected_state_entries = {
        (revision, component_id, str(component["state"]))
        for (revision, component_id), component in component_history.items()
        if component["state"] in {"rejected", "reopened"}
        and int(component["stateEnteredScopeRevision"]) == revision
    }
    if observed_state_entries != expected_state_entries:
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
        tail = tail_by_component.get(str(component["componentId"]))
        if tail is not None and tail["event"] == "rejected":
            return False
        if component["state"] == "reopened" and (
            tail is None or tail["event"] != "reopened"
        ):
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
            "new-observation",
            "scope-transition",
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
        kind in {"new-observation", "scope-transition"}
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
) -> bool:
    if not isinstance(value, list) or len(value) != scope_revision + 1:
        return False
    previous_core: set[int] = set()
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
            or snapshot["scopeRevisionDigest"] != route_b_artifact_digest(payload)
        ):
            return False
        previous_core = role_sets[0]
        previous_context_revision = int(snapshot_binding["contextRevision"])
    current = value[-1]
    return (
        current["requestBinding"] == current_request_binding
        and current["coreStableGaussianIds"] == current_core_ids
        and current["activeFrontierStableGaussianIds"] == current_active_ids
        and current["rejectedFrontierStableGaussianIds"] == current_rejected_ids
        and current["requiredContextStableGaussianIds"] == current_context_ids
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
        "discoveryEnvelopeLedger": [],
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
        if value["discoveryEnvelopeLedger"] != []:
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
        if scope_revision == 0 and (
            core_ids != seed_partition["admittedStableGaussianIds"]
            or active_ids != []
            or rejected_ids != []
            or context_ids != []
            or value["rejectedFrontierLedger"] != []
            or value["subcomponentDecisionLedger"] != []
        ):
            return False
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
        ):
            return False
        genesis_scope = scope_revision_ledger[0]
        if (
            genesis_scope["coreStableGaussianIds"]
            != seed_partition["admittedStableGaussianIds"]
            or genesis_scope["activeFrontierStableGaussianIds"] != []
            or genesis_scope["rejectedFrontierStableGaussianIds"] != []
            or genesis_scope["requiredContextStableGaussianIds"] != []
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
    "TargetScopeStateError",
    "TargetScopeStateIncompatibilityError",
    "TargetScopeStateInternalError",
    "TargetScopeStateTransitionError",
    "TargetScopeStateValidationError",
    "bootstrap_target_scope_state_from_seed",
    "canonical_target_scope_state_bytes",
    "create_target_scope_component_policy",
    "create_target_scope_subcomponent_decision",
    "is_target_scope_state",
    "restore_target_scope_state",
    "revise_target_scope_state",
    "rotate_target_scope_epoch",
    "target_scope_state_identity",
    "validate_target_scope_component_policy",
    "validate_target_scope_subcomponent_decision",
]

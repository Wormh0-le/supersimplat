from __future__ import annotations

from copy import deepcopy
import unittest
from typing import Any

from selection_service_companion.conservative_seed import (
    create_conservative_seed_policy,
    create_conservative_seed_target_geometry,
    evaluate_conservative_seed_shadow,
)
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.digests import route_b_artifact_digest
from selection_service_companion.target_scope_state import (
    TargetScopeStateError,
    TargetScopeStateIncompatibilityError,
    TargetScopeStateTransitionError,
    TargetScopeStateValidationError,
    admit_target_scope_discovery_sources,
    bootstrap_target_scope_state_from_seed,
    canonical_target_scope_state_bytes,
    create_target_scope_boundary_contact_shadow_source,
    create_target_scope_component_policy,
    create_target_scope_discovery_policy,
    create_target_scope_discovery_source,
    create_target_scope_observation_shadow_source,
    create_target_scope_subcomponent_decision,
    is_target_scope_state,
    revise_target_scope_state,
    restore_target_scope_state,
    rotate_target_scope_epoch,
    target_scope_state_identity,
    validate_target_scope_discovery_source,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def component_policy() -> dict[str, object]:
    return create_target_scope_component_policy(
        {
            "schemaVersion": 1,
            "policyId": "target-scope-components/experimental-shadow-v1",
            "adjacencyScaleMultiplier": 2.0,
            "boundsScaleMultiplier": 1.0,
        }
    )


def discovery_policy(
    *,
    maximum_sources: int = 8,
    maximum_stable_ids: int = 16,
) -> dict[str, object]:
    return create_target_scope_discovery_policy(
        {
            "schemaVersion": 1,
            "policyId": "target-scope-discovery/experimental-shadow-v1",
            "maximumSourceRecordsPerEpoch": maximum_sources,
            "maximumAdmittedStableGaussianIdsPerEpoch": maximum_stable_ids,
        }
    )


def target_geometry(
    rows: list[tuple[int, tuple[float, float, float]]],
) -> dict[str, object]:
    return create_conservative_seed_target_geometry(
        target_splat_id="splat-1",
        rows=[
            {
                "stableGaussianId": stable_id,
                "center": list(center),
                "logScales": [0.0, 0.0, 0.0],
            }
            for stable_id, center in rows
        ],
    )


def seed_record(
    *,
    stable_ids: list[int],
    positive: list[float],
    negative: list[float],
    visible: list[float],
    geometry: dict[str, object],
) -> dict[str, object]:
    dependency = {
        "splatId": "splat-1",
        "renderStateToken": "render-1",
        "geometryToken": "geometry-1",
        "gaussianIdentityToken": "gaussians-1",
        "worldTransformToken": "world-1",
    }
    working_set = create_evidence_working_set(
        {
            "targetSplatId": "splat-1",
            "coreTargetStableIds": stable_ids,
            "contextStableGaussianIds": [],
        }
    )
    admitted = admit_gaussian_evidence(
        {
            "requestBinding": {
                "targetContextId": "target-context-1",
                "contextRevision": 2,
                "dependencyToken": dependency,
            },
            "targetSplatId": "splat-1",
            "view": {
                "viewId": "anchor-view",
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": digest("a"),
                "rgbDigest": digest("b"),
                "stableMaskDigest": digest("c"),
            },
            "evidencePolicyDigest": digest("d"),
            "renderWorkingSet": {
                "targetSplatId": "splat-1",
                "dependencyToken": dependency,
                "cameraBindingDigest": digest("a"),
                "renderWorkingSetToken": digest("e"),
                "stableGaussianIds": stable_ids,
                "completeness": "complete",
            },
            "evidenceWorkingSet": working_set,
            "rasterImplementationId": "gsplat-direct-evidence/v1",
            "evidenceBackendKind": "production-direct",
            "evidenceBackendId": "global-atomic/direct-v1",
            "runtimeBuildId": "locked-runtime-1",
        }
    )
    assert admitted["status"] == "admitted"
    admission = admitted["admission"]
    assert isinstance(admission, dict)
    artifact = create_gaussian_evidence_artifact(
        admission,
        {
            "positiveMass": positive,
            "negativeMass": negative,
            "visibleMass": visible,
        },
    )
    policy = create_conservative_seed_policy(
        {
            "schemaVersion": 1,
            "policyId": "conservative-seed-s0/experimental-shadow-v1",
            "minimumVisibleMass": 0.1,
            "minimumPositiveRatio": 0.8,
            "maximumNegativeMass": 0.05,
            "maximumConflictRatio": 0.1,
            "connectivityScaleMultiplier": 4.0,
            "minimumSatelliteGaussianCount": 1,
            "minimumSatellitePositiveMass": 0.25,
            "grossOutlierScaleMultiplier": 40.0,
        }
    )
    result = evaluate_conservative_seed_shadow(
        evidence_artifact=artifact,
        target_geometry=geometry,
        policy=policy,
        clock_ns=lambda: 0,
    )
    record = result["record"]
    assert isinstance(record, dict)
    return record


def discovery_source(
    state: dict[str, object],
    *,
    source_kind: str,
    stable_ids: list[int],
    marker: str,
    minimum: tuple[float, float, float],
    maximum: tuple[float, float, float],
    view_ids: list[str] | None = None,
) -> dict[str, object]:
    return create_target_scope_discovery_source(
        {
            "schemaVersion": 1,
            "sourceKind": source_kind,
            "targetSplatId": state["targetSplatId"],
            "dependencyToken": state["requestBinding"]["dependencyToken"],  # type: ignore[index]
            "scopeEpochId": state["scopeEpochId"],
            "targetGeometryDigest": state["targetGeometryDigest"],
            "componentPolicyDigest": state["componentPolicyDigest"],
            "discoveryPolicyDigest": state["discoveryPolicyDigest"],
            "sourceArtifactIds": [f"artifact-{marker}"],
            "sourceViewIds": view_ids or [f"view-{marker}"],
            "sourceArtifactDigests": [digest(marker)],
            "admittedStableGaussianIds": stable_ids,
            "spatialBounds": {
                "minimum": list(minimum),
                "maximum": list(maximum),
            },
            "reason": f"fixture-{source_kind}",
        }
    )


def admit_discovery_ids(
    state: dict[str, Any],
    geometry: dict[str, object],
    *,
    stable_ids: list[int],
    marker: str,
    source_kind: str = "reviewed-target-local-spatial-support",
) -> tuple[dict[str, Any], str]:
    rows = geometry["rows"]
    assert isinstance(rows, list)
    centers_by_id = {
        int(row["stableGaussianId"]): row["center"]
        for row in rows
        if isinstance(row, dict)
    }
    centers = [centers_by_id[stable_id] for stable_id in stable_ids]
    source = discovery_source(
        state,
        source_kind=source_kind,
        stable_ids=stable_ids,
        marker=marker,
        minimum=(
            min(float(center[0]) for center in centers) - 0.25,
            min(float(center[1]) for center in centers) - 0.25,
            min(float(center[2]) for center in centers) - 0.25,
        ),
        maximum=(
            max(float(center[0]) for center in centers) + 0.25,
            max(float(center[1]) for center in centers) + 0.25,
            max(float(center[2]) for center in centers) + 0.25,
        ),
    )
    admitted = admit_target_scope_discovery_sources(
        previous_state=state,
        target_geometry=geometry,
        request_binding=state["requestBinding"],
        sources=[source],
    )
    return admitted, str(source["sourceDigest"])


class TargetScopeStateTests(unittest.TestCase):
    def test_revision_zero_preserves_the_complete_seed_partition(self) -> None:
        geometry = target_geometry(
            [
                (5, (30.0, 0.0, 0.0)),
                (4, (20.0, 0.0, 0.0)),
                (2, (1.0, 0.0, 0.0)),
                (1, (0.0, 0.0, 0.0)),
                (3, (10.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3, 4],
            positive=[0.9, 0.8, 0.35, 0.4],
            negative=[0.0, 0.0, 0.0, 0.2],
            visible=[1.0, 0.9, 0.4, 0.8],
            geometry=geometry,
        )

        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )

        self.assertTrue(is_target_scope_state(state))
        self.assertEqual(state["scopeRevision"], 0)
        self.assertEqual(state["coreStableGaussianIds"], [1, 2, 3])
        self.assertEqual(state["activeFrontierStableGaussianIds"], [])
        self.assertEqual(state["rejectedFrontierStableGaussianIds"], [])
        self.assertEqual(state["requiredContextStableGaussianIds"], [])
        self.assertEqual(
            state["seedPartition"],
            {
                "recordDigest": seed["recordDigest"],
                "seedPolicyDigest": seed["seedPolicyDigest"],
                "admittedStableGaussianIds": [1, 2, 3],
                "coreCandidateStableGaussianIds": [1, 2],
                "satelliteStableGaussianIds": [3],
                "filteredStableGaussianIds": [4],
                "unevaluatedStableGaussianIds": [5],
            },
        )
        self.assertNotEqual(
            state["componentPolicyDigest"],
            seed["seedPolicyDigest"],
        )

    def test_revision_zero_rejects_seed_support_recast_into_any_scope_role(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (8.0, 0.0, 0.0)),
                (3, (16.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.4],
            negative=[0.0, 0.2],
            visible=[1.0, 1.0],
            geometry=geometry,
        )
        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        source = digest("9")

        def rewrite_as_revision_zero(revised: dict[str, Any]) -> dict[str, Any]:
            forged = deepcopy(revised)
            forged["scopeRevision"] = 0
            forged["provenance"] = deepcopy(state["provenance"])
            forged["provenanceDigest"] = state["provenanceDigest"]
            components = [
                *forged["coreComponents"],
                *forged["activeFrontierComponents"],
                *forged["rejectedFrontierComponents"],
            ]
            components_by_id = {
                component["componentId"]: component for component in components
            }
            for component in components:
                component["ageRevisions"] = 0
                component["createdAtScopeRevision"] = 0
                component["stateEnteredScopeRevision"] = 0

            introduced = []
            for record in forged["componentLineageLedger"]:
                if record["toScopeRevision"] != 1:
                    continue
                for child_reference in record["childMemberships"]:
                    child = deepcopy(child_reference)
                    component = components_by_id[child["componentId"]]
                    for key in (
                        "state",
                        "provenanceDigests",
                        "ageRevisions",
                        "createdAtScopeRevision",
                        "stateEnteredScopeRevision",
                    ):
                        if key in child:
                            child[key] = deepcopy(component[key])
                    lineage_payload = {
                        "schemaVersion": 1,
                        "relation": "introduced",
                        "fromScopeRevision": None,
                        "toScopeRevision": 0,
                        "revisionSourceDigests": [seed["recordDigest"]],
                        "parentComponentIds": [],
                        "childComponentIds": [child["componentId"]],
                        "parentMemberships": [],
                        "childMemberships": [child],
                        "sharedStableGaussianIds": [],
                        "introducedStableGaussianIds": child["stableGaussianIds"],
                        "retiredStableGaussianIds": [],
                        "retiredToContextStableGaussianIds": [],
                        "retiredOutOfScopeStableGaussianIds": [],
                        "subcomponentDecisionDigests": [],
                    }
                    introduced.append(
                        {
                            **lineage_payload,
                            "lineageDigest": route_b_artifact_digest(lineage_payload),
                        }
                    )
            introduced.sort(key=lambda record: record["lineageDigest"])
            forged["componentLineageLedger"] = introduced
            lineage_by_component = {
                record["childComponentIds"][0]: record["lineageDigest"]
                for record in introduced
            }
            for component in components:
                component["lineageRecordDigests"] = [
                    lineage_by_component[component["componentId"]]
                ]
                component_payload = {
                    key: value
                    for key, value in component.items()
                    if key != "componentDigest"
                }
                component["componentDigest"] = route_b_artifact_digest(
                    component_payload
                )
            forged["subcomponentDecisionLedger"] = []
            forged["rejectedFrontierLedger"] = []
            forged["revisionProvenanceLedger"] = [deepcopy(state["provenance"])]
            snapshot_payload = {
                "schemaVersion": 1,
                "scopeRevision": 0,
                "requestBinding": deepcopy(forged["requestBinding"]),
                "coreStableGaussianIds": deepcopy(forged["coreStableGaussianIds"]),
                "activeFrontierStableGaussianIds": deepcopy(
                    forged["activeFrontierStableGaussianIds"]
                ),
                "rejectedFrontierStableGaussianIds": deepcopy(
                    forged["rejectedFrontierStableGaussianIds"]
                ),
                "requiredContextStableGaussianIds": deepcopy(
                    forged["requiredContextStableGaussianIds"]
                ),
            }
            forged["scopeRevisionLedger"] = [
                {
                    **snapshot_payload,
                    "scopeRevisionDigest": route_b_artifact_digest(snapshot_payload),
                }
            ]
            payload = {
                key: value for key, value in forged.items() if key != "stateDigest"
            }
            forged["stateDigest"] = route_b_artifact_digest(payload)
            return forged

        for stable_id in (2, 3):
            for role in ("core", "active", "rejected", "context"):
                with self.subTest(stable_id=stable_id, role=role):
                    if role == "core":
                        with self.assertRaisesRegex(
                            TargetScopeStateTransitionError,
                            "must enter active Frontier before Core",
                        ):
                            revise_target_scope_state(
                                previous_state=state,
                                target_geometry=geometry,
                                request_binding=state["requestBinding"],
                                core_stable_gaussian_ids=[1, stable_id],
                                active_frontier=[],
                                rejected_frontier=[],
                                required_context_stable_gaussian_ids=[],
                                revision_provenance={
                                    "kind": "new-observation",
                                    "reason": "invalid-direct-core-introduction",
                                    "sourceDigests": [source],
                                },
                            )
                        continue
                    if role == "active":
                        with self.assertRaisesRegex(
                            TargetScopeStateTransitionError,
                            "fresh authoritative observation or discovery source",
                        ):
                            revise_target_scope_state(
                                previous_state=state,
                                target_geometry=geometry,
                                request_binding=state["requestBinding"],
                                core_stable_gaussian_ids=[1],
                                active_frontier=[
                                    {
                                        "stableGaussianIds": [stable_id],
                                        "state": "new",
                                        "provenanceDigests": [source],
                                    }
                                ],
                                rejected_frontier=[],
                                required_context_stable_gaussian_ids=[],
                                revision_provenance={
                                    "kind": "new-observation",
                                    "reason": "invalid-direct-active-introduction",
                                    "sourceDigests": [source],
                                },
                            )
                        continue
                    if role == "rejected":
                        with self.assertRaisesRegex(
                            TargetScopeStateTransitionError,
                            "must originate in active Frontier",
                        ):
                            revise_target_scope_state(
                                previous_state=state,
                                target_geometry=geometry,
                                request_binding=state["requestBinding"],
                                core_stable_gaussian_ids=[1],
                                active_frontier=[],
                                rejected_frontier=[
                                    {
                                        "stableGaussianIds": [stable_id],
                                        "state": "rejected",
                                        "provenanceDigests": [source],
                                    }
                                ],
                                required_context_stable_gaussian_ids=[],
                                revision_provenance={
                                    "kind": "scope-transition",
                                    "reason": "invalid-direct-rejected-introduction",
                                    "sourceDigests": [source],
                                },
                            )
                        continue
                    if role == "context":
                        tampered = deepcopy(state)
                        tampered["requiredContextStableGaussianIds"] = [stable_id]
                        scope_snapshot = tampered["scopeRevisionLedger"][0]
                        scope_snapshot["requiredContextStableGaussianIds"] = [stable_id]
                        snapshot_payload = {
                            key: value
                            for key, value in scope_snapshot.items()
                            if key != "scopeRevisionDigest"
                        }
                        scope_snapshot["scopeRevisionDigest"] = route_b_artifact_digest(
                            snapshot_payload
                        )
                        payload = {
                            key: value
                            for key, value in tampered.items()
                            if key != "stateDigest"
                        }
                        tampered["stateDigest"] = route_b_artifact_digest(payload)
                    else:
                        tampered = rewrite_as_revision_zero(
                            revise_target_scope_state(
                                previous_state=state,
                                target_geometry=geometry,
                                request_binding=state["requestBinding"],
                                core_stable_gaussian_ids=(
                                    [1, stable_id] if role == "core" else [1]
                                ),
                                active_frontier=(
                                    [
                                        {
                                            "stableGaussianIds": [stable_id],
                                            "state": "new",
                                            "provenanceDigests": [source],
                                        }
                                    ]
                                    if role == "active"
                                    else []
                                ),
                                rejected_frontier=(
                                    [
                                        {
                                            "stableGaussianIds": [stable_id],
                                            "state": "rejected",
                                            "provenanceDigests": [source],
                                        }
                                    ]
                                    if role == "rejected"
                                    else []
                                ),
                                required_context_stable_gaussian_ids=[],
                                revision_provenance={
                                    "kind": "new-observation",
                                    "reason": "coordinated-revision-zero-tamper",
                                    "sourceDigests": [source],
                                },
                            )
                        )
                    self.assertFalse(is_target_scope_state(tampered))

    def test_componentization_is_canonical_across_geometry_row_order(self) -> None:
        rows = [
            (3, (10.0, 0.0, 0.0)),
            (1, (0.0, 0.0, 0.0)),
            (2, (1.0, 0.0, 0.0)),
        ]
        first_geometry = target_geometry(rows)
        second_geometry = target_geometry(list(reversed(rows)))
        first_seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.8, 0.7],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 0.9, 0.8],
            geometry=first_geometry,
        )
        second_seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.8, 0.7],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 0.9, 0.8],
            geometry=second_geometry,
        )

        first = bootstrap_target_scope_state_from_seed(
            seed_record=first_seed,
            target_geometry=first_geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        second = bootstrap_target_scope_state_from_seed(
            seed_record=second_seed,
            target_geometry=second_geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )

        self.assertEqual(
            canonical_target_scope_state_bytes(first),
            canonical_target_scope_state_bytes(second),
        )
        self.assertEqual(
            [component["stableGaussianIds"] for component in first["coreComponents"]],
            [[1, 2], [3]],
        )
        self.assertEqual(
            first["coreComponents"][0]["worldSpaceBounds"],
            {"minimum": [-1.0, -1.0, -1.0], "maximum": [2.0, 1.0, 1.0]},
        )
        tampered = deepcopy(first)
        tampered_component = tampered["coreComponents"][0]
        tampered_component["worldSpaceBounds"]["minimum"][0] = -2.0
        component_payload = {
            key: value
            for key, value in tampered_component.items()
            if key != "componentDigest"
        }
        tampered_component["componentDigest"] = route_b_artifact_digest(
            component_payload
        )
        state_payload = {
            key: value for key, value in tampered.items() if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(state_payload)
        self.assertFalse(is_target_scope_state(tampered))

    def test_validator_rejects_a_coordinated_noncanonical_component_split(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (1.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.9],
            negative=[0.0, 0.0],
            visible=[1.0, 1.0],
            geometry=geometry,
        )
        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        tampered = deepcopy(state)
        components = []
        lineage = []
        for stable_id, center in ((1, 0.0), (2, 1.0)):
            component_id = route_b_artifact_digest(
                {
                    "schemaVersion": 1,
                    "targetSplatId": state["targetSplatId"],
                    "targetGeometryDigest": state["targetGeometryDigest"],
                    "componentPolicyDigest": state["componentPolicyDigest"],
                    "stableGaussianIds": [stable_id],
                }
            )
            reference = {
                "componentId": component_id,
                "stableGaussianIds": [stable_id],
                "state": "core",
                "provenanceDigests": [seed["recordDigest"]],
                "ageRevisions": 0,
                "createdAtScopeRevision": 0,
                "stateEnteredScopeRevision": 0,
            }
            lineage_payload = {
                "schemaVersion": 1,
                "relation": "introduced",
                "fromScopeRevision": None,
                "toScopeRevision": 0,
                "revisionSourceDigests": [seed["recordDigest"]],
                "parentComponentIds": [],
                "childComponentIds": [component_id],
                "parentMemberships": [],
                "childMemberships": [reference],
                "sharedStableGaussianIds": [],
                "introducedStableGaussianIds": [stable_id],
                "retiredStableGaussianIds": [],
                "retiredToContextStableGaussianIds": [],
                "retiredOutOfScopeStableGaussianIds": [],
                "subcomponentDecisionDigests": [],
            }
            lineage_record = {
                **lineage_payload,
                "lineageDigest": route_b_artifact_digest(lineage_payload),
            }
            component_payload = {
                "componentId": component_id,
                "stableGaussianIds": [stable_id],
                "worldSpaceBounds": {
                    "minimum": [center - 1.0, -1.0, -1.0],
                    "maximum": [center + 1.0, 1.0, 1.0],
                },
                "materialSummary": {
                    "gaussianCount": 1,
                    "totalLogScaleVolume": 0.0,
                    "maximumDeclaredScale": 1.0,
                },
                "state": "core",
                "provenanceDigests": [seed["recordDigest"]],
                "lineageRecordDigests": [lineage_record["lineageDigest"]],
                "ageRevisions": 0,
                "createdAtScopeRevision": 0,
                "stateEnteredScopeRevision": 0,
            }
            components.append(
                {
                    **component_payload,
                    "componentDigest": route_b_artifact_digest(component_payload),
                }
            )
            lineage.append(lineage_record)
        tampered["coreComponents"] = components
        tampered["componentLineageLedger"] = sorted(
            lineage,
            key=lambda record: record["lineageDigest"],
        )
        payload = {
            key: value for key, value in tampered.items() if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(payload)

        self.assertFalse(is_target_scope_state(tampered))

    def test_validator_replays_component_age_and_provenance_history(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (8.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1],
            positive=[0.9],
            negative=[0.0],
            visible=[1.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        revision_one, source = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[2], marker="d"
        )

        def resign_component(tampered: dict[str, Any]) -> None:
            component = tampered["activeFrontierComponents"][0]
            lineage_record = next(
                record
                for record in tampered["componentLineageLedger"]
                if component["componentId"] in record["childComponentIds"]
                and record["toScopeRevision"] == 1
            )
            child_reference = next(
                reference
                for reference in lineage_record["childMemberships"]
                if reference["componentId"] == component["componentId"]
            )
            for key in (
                "state",
                "provenanceDigests",
                "ageRevisions",
                "createdAtScopeRevision",
                "stateEnteredScopeRevision",
            ):
                child_reference[key] = deepcopy(component[key])
            lineage_payload = {
                key: value
                for key, value in lineage_record.items()
                if key != "lineageDigest"
            }
            lineage_record["lineageDigest"] = route_b_artifact_digest(lineage_payload)
            tampered["componentLineageLedger"].sort(
                key=lambda record: record["lineageDigest"]
            )
            component["lineageRecordDigests"] = [lineage_record["lineageDigest"]]
            component_payload = {
                key: value
                for key, value in component.items()
                if key != "componentDigest"
            }
            component["componentDigest"] = route_b_artifact_digest(component_payload)
            payload = {
                key: value for key, value in tampered.items() if key != "stateDigest"
            }
            tampered["stateDigest"] = route_b_artifact_digest(payload)

        age_drift = deepcopy(revision_one)
        age_component = age_drift["activeFrontierComponents"][0]
        age_component["createdAtScopeRevision"] = 0
        age_component["stateEnteredScopeRevision"] = 0
        age_component["ageRevisions"] = 1
        resign_component(age_drift)
        self.assertFalse(is_target_scope_state(age_drift))

        provenance_drift = deepcopy(revision_one)
        provenance_drift["activeFrontierComponents"][0]["provenanceDigests"] = sorted(
            [source, digest("e")]
        )
        resign_component(provenance_drift)
        self.assertFalse(is_target_scope_state(provenance_drift))
        parent_drift = deepcopy(revision_one)
        parent_drift["provenance"]["previousStateDigest"] = digest("f")
        provenance_payload = {
            key: value
            for key, value in parent_drift["provenance"].items()
            if key != "revisionProvenanceDigest"
        }
        parent_drift["provenance"]["revisionProvenanceDigest"] = (
            route_b_artifact_digest(provenance_payload)
        )
        parent_drift["provenanceDigest"] = parent_drift["provenance"][
            "revisionProvenanceDigest"
        ]
        parent_drift["revisionProvenanceLedger"][1] = deepcopy(
            parent_drift["provenance"]
        )
        parent_payload = {
            key: value for key, value in parent_drift.items() if key != "stateDigest"
        }
        parent_drift["stateDigest"] = route_b_artifact_digest(parent_payload)
        self.assertFalse(is_target_scope_state(parent_drift))

    def test_empty_core_is_valid_but_role_overlap_and_foreign_ids_fail_closed(
        self,
    ) -> None:
        geometry = target_geometry([(1, (0.0, 0.0, 0.0))])
        seed = seed_record(
            stable_ids=[1],
            positive=[0.0],
            negative=[0.0],
            visible=[0.01],
            geometry=geometry,
        )
        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        self.assertEqual(state["coreStableGaussianIds"], [])
        self.assertTrue(is_target_scope_state(state))

        foreign = deepcopy(state)
        foreign["requiredContextStableGaussianIds"] = [2]
        payload = {key: value for key, value in foreign.items() if key != "stateDigest"}
        foreign["stateDigest"] = route_b_artifact_digest(payload)
        self.assertFalse(is_target_scope_state(foreign))

        admitted_seed = seed_record(
            stable_ids=[1],
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
            geometry=geometry,
        )
        overlap = bootstrap_target_scope_state_from_seed(
            seed_record=admitted_seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        overlap["requiredContextStableGaussianIds"] = [1]
        payload = {key: value for key, value in overlap.items() if key != "stateDigest"}
        overlap["stateDigest"] = route_b_artifact_digest(payload)
        self.assertFalse(is_target_scope_state(overlap))

        with self.assertRaises(TargetScopeStateValidationError):
            create_target_scope_component_policy(
                {
                    "schemaVersion": 1,
                    "policyId": "target-scope-components/experimental-shadow-v1",
                    "adjacencyScaleMultiplier": 0.0,
                    "boundsScaleMultiplier": 1.0,
                }
            )

    def test_split_and_merge_lineage_is_deterministic_and_replayable(self) -> None:
        geometry = target_geometry(
            [
                (5, (4.0, 0.0, 0.0)),
                (1, (-4.0, 0.0, 0.0)),
                (4, (3.0, 0.0, 0.0)),
                (2, (-3.0, 0.0, 0.0)),
                (3, (2.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3, 4, 5],
            positive=[0.9, 0.9, 0.1, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0, 1.0, 1.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        request_binding = deepcopy(revision_zero["requestBinding"])
        request_binding["contextRevision"] = 3
        revision_one, source = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[3, 4, 5], marker="f"
        )
        self.assertEqual(revision_one["scopeRevision"], 1)
        self.assertEqual(
            [
                component["stableGaussianIds"]
                for component in revision_one["activeFrontierComponents"]
            ],
            [[3, 4, 5]],
        )

        second_source = digest("1")
        with self.assertRaisesRegex(
            TargetScopeStateError,
            "cannot be split by state labels",
        ):
            revise_target_scope_state(
                previous_state=revision_one,
                target_geometry=geometry,
                request_binding=request_binding,
                core_stable_gaussian_ids=[1, 2],
                active_frontier=[
                    {
                        "stableGaussianIds": [3],
                        "state": "conflicted",
                        "provenanceDigests": [second_source],
                    },
                    {
                        "stableGaussianIds": [4, 5],
                        "state": "observing",
                        "provenanceDigests": [second_source],
                    },
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-per-gaussian-state-flicker",
                    "sourceDigests": [second_source],
                },
            )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "requires an exact versioned subcomponent decision",
        ):
            revise_target_scope_state(
                previous_state=revision_one,
                target_geometry=geometry,
                request_binding=request_binding,
                core_stable_gaussian_ids=[1, 2, 3],
                active_frontier=[
                    {
                        "stableGaussianIds": [4, 5],
                        "state": "observing",
                        "provenanceDigests": [source, second_source],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "unreviewed-subcomponent-split",
                    "sourceDigests": [second_source],
                },
            )
        split_decision = create_target_scope_subcomponent_decision(
            {
                "schemaVersion": 1,
                "policyId": (
                    "target-scope-subcomponents/explicit-stable-id-partition-v1"
                ),
                "parentComponentId": revision_one["activeFrontierComponents"][0][
                    "componentId"
                ],
                "parentStableGaussianIds": [3, 4, 5],
                "childStableGaussianIdPartitions": [[3], [5, 4]],
                "provenanceDigests": [second_source],
            }
        )
        split = revise_target_scope_state(
            previous_state=revision_one,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[1, 2, 3],
            active_frontier=[
                {
                    "stableGaussianIds": [5, 4],
                    "state": "observing",
                    "provenanceDigests": [source, second_source],
                }
            ],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "deterministic-subcomponent-review",
                "sourceDigests": [second_source],
            },
            subcomponent_decisions=[split_decision],
        )
        split_records = [
            record
            for record in split["componentLineageLedger"]
            if record["toScopeRevision"] == 2 and record["relation"] == "split"
        ]
        self.assertEqual(len(split_records), 1)
        self.assertEqual(len(split_records[0]["parentComponentIds"]), 1)
        self.assertEqual(len(split_records[0]["childComponentIds"]), 2)
        self.assertEqual(split_records[0]["sharedStableGaussianIds"], [3, 4, 5])
        replayed_split = revise_target_scope_state(
            previous_state=revision_one,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[3, 2, 1],
            active_frontier=[
                {
                    "stableGaussianIds": [4, 5],
                    "state": "observing",
                    "provenanceDigests": [second_source, source],
                }
            ],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "deterministic-subcomponent-review",
                "sourceDigests": [second_source],
            },
            subcomponent_decisions=[deepcopy(split_decision)],
        )
        self.assertEqual(
            canonical_target_scope_state_bytes(replayed_split),
            canonical_target_scope_state_bytes(split),
        )
        tampered = deepcopy(split)
        tampered_record = next(
            record
            for record in tampered["componentLineageLedger"]
            if record["toScopeRevision"] == 2 and record["relation"] == "split"
        )
        old_lineage_digest = tampered_record["lineageDigest"]
        tampered_record["relation"] = "resegmented"
        lineage_payload = {
            key: value
            for key, value in tampered_record.items()
            if key != "lineageDigest"
        }
        new_lineage_digest = route_b_artifact_digest(lineage_payload)
        tampered_record["lineageDigest"] = new_lineage_digest
        tampered["componentLineageLedger"].sort(
            key=lambda record: (
                record["toScopeRevision"],
                record["lineageDigest"],
            )
        )
        for component in [
            *tampered["coreComponents"],
            *tampered["activeFrontierComponents"],
        ]:
            if old_lineage_digest not in component["lineageRecordDigests"]:
                continue
            component["lineageRecordDigests"] = [new_lineage_digest]
            component_payload = {
                key: value
                for key, value in component.items()
                if key != "componentDigest"
            }
            component["componentDigest"] = route_b_artifact_digest(component_payload)
        state_payload = {
            key: value for key, value in tampered.items() if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(state_payload)
        self.assertFalse(is_target_scope_state(tampered))

        merged = revise_target_scope_state(
            previous_state=split,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[1, 2, 3, 4, 5],
            active_frontier=[],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "component-support-reunified",
                "sourceDigests": [second_source],
            },
        )
        merge_records = [
            record
            for record in merged["componentLineageLedger"]
            if record["toScopeRevision"] == 3 and record["relation"] == "merge"
        ]
        self.assertEqual(len(merge_records), 1)
        self.assertEqual(len(merge_records[0]["parentComponentIds"]), 2)
        self.assertEqual(len(merge_records[0]["childComponentIds"]), 1)
        self.assertTrue(is_target_scope_state(merged))
        fabricated = deepcopy(merged)
        fabricated_record = next(
            record
            for record in fabricated["componentLineageLedger"]
            if record["toScopeRevision"] == 3 and record["relation"] == "merge"
        )
        old_merge_digest = fabricated_record["lineageDigest"]
        retained_parent = next(
            reference
            for reference in fabricated_record["parentMemberships"]
            if reference["stableGaussianIds"] == [3]
        )
        fabricated_parent = {
            "componentId": route_b_artifact_digest(
                {
                    "schemaVersion": 1,
                    "targetSplatId": fabricated["targetSplatId"],
                    "targetGeometryDigest": fabricated["targetGeometryDigest"],
                    "componentPolicyDigest": fabricated["componentPolicyDigest"],
                    "stableGaussianIds": [5],
                }
            ),
            "stableGaussianIds": [5],
        }
        fabricated_record["parentMemberships"] = sorted(
            [retained_parent, fabricated_parent],
            key=lambda reference: reference["componentId"],
        )
        fabricated_record["parentComponentIds"] = [
            reference["componentId"]
            for reference in fabricated_record["parentMemberships"]
        ]
        fabricated_record["sharedStableGaussianIds"] = [3, 5]
        fabricated_payload = {
            key: value
            for key, value in fabricated_record.items()
            if key != "lineageDigest"
        }
        fabricated_record["lineageDigest"] = route_b_artifact_digest(fabricated_payload)
        for component in fabricated["coreComponents"]:
            if old_merge_digest not in component["lineageRecordDigests"]:
                continue
            component["lineageRecordDigests"] = [fabricated_record["lineageDigest"]]
            component_payload = {
                key: value
                for key, value in component.items()
                if key != "componentDigest"
            }
            component["componentDigest"] = route_b_artifact_digest(component_payload)
        fabricated["componentLineageLedger"].sort(
            key=lambda record: (
                record["toScopeRevision"],
                record["lineageDigest"],
            )
        )
        fabricated_state_payload = {
            key: value for key, value in fabricated.items() if key != "stateDigest"
        }
        fabricated["stateDigest"] = route_b_artifact_digest(fabricated_state_payload)
        self.assertFalse(is_target_scope_state(fabricated))

    def test_partial_membership_churn_requires_complete_subcomponent_decisions(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (1.0, 0.0, 0.0)),
                (3, (2.0, 0.0, 0.0)),
                (4, (3.0, 0.0, 0.0)),
            ]
        )
        empty_seed = seed_record(
            stable_ids=[1, 2, 3, 4],
            positive=[0.1, 0.1, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0, 1.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=empty_seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        parent, first_source = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[1, 2, 3], marker="6"
        )
        parent_component = parent["activeFrontierComponents"][0]
        second_source = digest("7")

        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "requires an exact versioned subcomponent decision",
        ):
            revise_target_scope_state(
                previous_state=parent,
                target_geometry=geometry,
                request_binding=parent["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2, 3],
                        "state": "observing",
                        "provenanceDigests": [first_source, second_source],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[4],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "unreviewed-subcomponent-split",
                    "sourceDigests": [second_source],
                },
            )

        split_decision = create_target_scope_subcomponent_decision(
            {
                "schemaVersion": 1,
                "policyId": (
                    "target-scope-subcomponents/explicit-stable-id-partition-v1"
                ),
                "parentComponentId": parent_component["componentId"],
                "parentStableGaussianIds": [1, 2, 3],
                "childStableGaussianIdPartitions": [[1], [2, 3]],
                "provenanceDigests": [second_source],
            }
        )
        split = revise_target_scope_state(
            previous_state=parent,
            target_geometry=geometry,
            request_binding=parent["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[
                {
                    "stableGaussianIds": [2, 3],
                    "state": "observing",
                    "provenanceDigests": [first_source, second_source],
                }
            ],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[4],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "reviewed-subcomponent-split",
                "sourceDigests": [second_source],
            },
            subcomponent_decisions=[split_decision],
        )
        split_record = next(
            record
            for record in split["componentLineageLedger"]
            if record["toScopeRevision"] == 2 and record["relation"] == "split"
        )
        self.assertEqual(split_record["sharedStableGaussianIds"], [1, 2, 3])
        self.assertEqual(split_record["introducedStableGaussianIds"], [])
        self.assertEqual(split_record["retiredStableGaussianIds"], [])
        self.assertTrue(is_target_scope_state(split))

        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "fresh authoritative observation or discovery source",
        ):
            revise_target_scope_state(
                previous_state=split,
                target_geometry=geometry,
                request_binding=split["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2, 3, 4],
                        "state": "observing",
                        "provenanceDigests": [first_source, second_source, digest("8")],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "new-observation",
                    "reason": "invalid-unversioned-added-support",
                    "sourceDigests": [digest("8")],
                },
            )

        admitted_context, _ = admit_discovery_ids(
            split, geometry, stable_ids=[4], marker="9"
        )
        self.assertEqual(admitted_context["activeFrontierStableGaussianIds"], [2, 3, 4])
        self.assertEqual(admitted_context["requiredContextStableGaussianIds"], [])
        self.assertTrue(is_target_scope_state(admitted_context))

    def test_core_shrink_requires_epoch_rotation_and_restoration_is_exact(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (1.0, 0.0, 0.0)),
                (3, (6.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.9, 0.1],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        request_binding = deepcopy(revision_zero["requestBinding"])
        request_binding["contextRevision"] = 3
        revision_one, source = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[3], marker="2"
        )
        self.assertEqual(revision_one["scopeEpochId"], revision_zero["scopeEpochId"])
        before_failed_transition = canonical_target_scope_state_bytes(revision_one)

        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "Core cannot shrink",
        ):
            revise_target_scope_state(
                previous_state=revision_one,
                target_geometry=geometry,
                request_binding=request_binding,
                core_stable_gaussian_ids=[1],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-core-shrink",
                    "sourceDigests": [digest("3")],
                },
            )
        self.assertEqual(
            canonical_target_scope_state_bytes(revision_one),
            before_failed_transition,
        )

        with self.assertRaisesRegex(
            TargetScopeStateIncompatibilityError,
            "rotate",
        ):
            revise_target_scope_state(
                previous_state=revision_one,
                target_geometry=geometry,
                request_binding=request_binding,
                core_stable_gaussian_ids=[1, 2],
                active_frontier=[
                    {
                        "stableGaussianIds": [3],
                        "state": "new",
                        "provenanceDigests": [source],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "authoritative-stable-mask-correction",
                    "sourceDigests": [digest("3")],
                },
            )

        corrected_seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            geometry=geometry,
        )
        rotated = rotate_target_scope_epoch(
            previous_state=revision_one,
            seed_record=corrected_seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            reason="authoritative-stable-mask-correction",
            source_digests=[digest("4")],
        )
        self.assertEqual(rotated["scopeRevision"], 0)
        self.assertEqual(rotated["coreStableGaussianIds"], [1])
        self.assertNotEqual(rotated["scopeEpochId"], revision_one["scopeEpochId"])
        self.assertTrue(is_target_scope_state(rotated))

        with self.assertRaises(TargetScopeStateError):
            rotate_target_scope_epoch(
                previous_state=revision_one,
                seed_record=corrected_seed,
                target_geometry=geometry,
                component_policy=component_policy(),
                reason="new-observation",
                source_digests=[digest("4")],
            )

        identity = target_scope_state_identity(revision_one)
        restored = restore_target_scope_state(revision_one, expected_identity=identity)
        self.assertEqual(
            canonical_target_scope_state_bytes(restored),
            canonical_target_scope_state_bytes(revision_one),
        )
        restored["scopeRevision"] = 99
        self.assertEqual(revision_one["scopeRevision"], 1)

        mismatched_identity = {**identity, "provenanceDigest": digest("5")}
        with self.assertRaises(TargetScopeStateIncompatibilityError):
            restore_target_scope_state(
                revision_one,
                expected_identity=mismatched_identity,
            )

    def test_revision_zero_epoch_identity_rejects_coordinated_tampering(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (6.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.1],
            negative=[0.0, 0.0],
            visible=[1.0, 1.0],
            geometry=geometry,
        )
        bootstrap = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        rotated = rotate_target_scope_epoch(
            previous_state=bootstrap,
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            reason="authoritative-stable-mask-correction",
            source_digests=[digest("a")],
        )

        def resign(tampered: dict[str, Any]) -> dict[str, Any]:
            provenance_payload = {
                key: value
                for key, value in tampered["provenance"].items()
                if key != "revisionProvenanceDigest"
            }
            tampered["provenance"]["revisionProvenanceDigest"] = (
                route_b_artifact_digest(provenance_payload)
            )
            tampered["provenanceDigest"] = tampered["provenance"][
                "revisionProvenanceDigest"
            ]
            tampered["revisionProvenanceLedger"] = [deepcopy(tampered["provenance"])]
            tampered["scopeEpochId"] = route_b_artifact_digest(tampered["epochBinding"])
            payload = {
                key: value for key, value in tampered.items() if key != "stateDigest"
            }
            tampered["stateDigest"] = route_b_artifact_digest(payload)
            return tampered

        bootstrap_reason = deepcopy(bootstrap)
        bootstrap_reason["provenance"]["reason"] = "forged-bootstrap"
        self.assertFalse(is_target_scope_state(resign(bootstrap_reason)))

        bootstrap_parent = deepcopy(bootstrap)
        bootstrap_parent["epochBinding"]["previousScopeEpochId"] = digest("b")
        self.assertFalse(is_target_scope_state(resign(bootstrap_parent)))

        for reason, previous_epoch_id, origin_digest in (
            ("new-observation", bootstrap["scopeEpochId"], None),
            (
                "authoritative-stable-mask-correction",
                None,
                None,
            ),
            (
                "authoritative-stable-mask-correction",
                bootstrap["scopeEpochId"],
                digest("c"),
            ),
        ):
            with self.subTest(
                reason=reason,
                previous_scope_epoch_id=previous_epoch_id,
                origin_digest=origin_digest,
            ):
                tampered = deepcopy(rotated)
                sources = tampered["provenance"]["sourceDigests"]
                if origin_digest is None:
                    rotation_payload = {
                        "previousScopeEpochId": previous_epoch_id,
                        "previousStateDigest": bootstrap["stateDigest"],
                        "reason": reason,
                        "sourceDigests": sources,
                        "replacementSeedRecordDigest": seed["recordDigest"],
                    }
                    origin_digest = route_b_artifact_digest(rotation_payload)
                tampered["provenance"]["reason"] = reason
                tampered["provenance"]["epochOriginDigest"] = origin_digest
                tampered["epochBinding"]["previousScopeEpochId"] = previous_epoch_id
                tampered["epochBinding"]["epochOriginDigest"] = origin_digest
                self.assertFalse(is_target_scope_state(resign(tampered)))

    def test_state_binds_the_complete_seed_record_not_only_its_partition(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (8.0, 0.0, 0.0)),
            ]
        )
        filtered_seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.0],
            negative=[0.0, 0.0],
            visible=[1.0, 0.0],
            geometry=geometry,
        )
        unevaluated_seed = seed_record(
            stable_ids=[1],
            positive=[0.9],
            negative=[0.0],
            visible=[1.0],
            geometry=geometry,
        )
        state = bootstrap_target_scope_state_from_seed(
            seed_record=unevaluated_seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        request_tamper = deepcopy(state)
        request_tamper["requestBinding"]["contextRevision"] += 1
        request_snapshot = request_tamper["scopeRevisionLedger"][0]
        request_snapshot["requestBinding"] = deepcopy(request_tamper["requestBinding"])
        snapshot_payload = {
            key: value
            for key, value in request_snapshot.items()
            if key != "scopeRevisionDigest"
        }
        request_snapshot["scopeRevisionDigest"] = route_b_artifact_digest(
            snapshot_payload
        )
        request_payload = {
            key: value for key, value in request_tamper.items() if key != "stateDigest"
        }
        request_tamper["stateDigest"] = route_b_artifact_digest(request_payload)
        self.assertFalse(is_target_scope_state(request_tamper))

        tampered = deepcopy(state)
        tampered["seedRecord"] = deepcopy(filtered_seed)
        payload = {
            key: value for key, value in tampered.items() if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(payload)

        self.assertNotEqual(
            filtered_seed["recordDigest"], unevaluated_seed["recordDigest"]
        )
        self.assertFalse(is_target_scope_state(tampered))

    def test_validator_rejects_retire_and_introduce_lineage_decomposition(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (1.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.0, 0.0],
            negative=[0.0, 0.0],
            visible=[0.0, 0.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        revision_one, source_one = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[1, 2], marker="a"
        )
        parent = revision_one["activeFrontierComponents"][0]
        source_two = digest("b")
        decision = create_target_scope_subcomponent_decision(
            {
                "schemaVersion": 1,
                "policyId": (
                    "target-scope-subcomponents/explicit-stable-id-partition-v1"
                ),
                "parentComponentId": parent["componentId"],
                "parentStableGaussianIds": [1, 2],
                "childStableGaussianIdPartitions": [[1], [2]],
                "provenanceDigests": [source_two],
            }
        )
        revision_two = revise_target_scope_state(
            previous_state=revision_one,
            target_geometry=geometry,
            request_binding=revision_one["requestBinding"],
            core_stable_gaussian_ids=[],
            active_frontier=[
                {
                    "stableGaussianIds": [1],
                    "state": "observing",
                    "provenanceDigests": sorted([source_one, source_two]),
                }
            ],
            rejected_frontier=[
                {
                    "stableGaussianIds": [2],
                    "state": "rejected",
                    "provenanceDigests": sorted([source_one, source_two]),
                }
            ],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "partial-frontier-retirement",
                "sourceDigests": sorted([source_two, str(decision["decisionDigest"])]),
            },
            subcomponent_decisions=[decision],
        )
        self.assertTrue(is_target_scope_state(revision_two))

        tampered = deepcopy(revision_two)
        original_record = next(
            record
            for record in tampered["componentLineageLedger"]
            if record["toScopeRevision"] == 2
        )
        parent_reference = deepcopy(original_record["parentMemberships"][0])
        child_reference = deepcopy(
            next(
                reference
                for reference in original_record["childMemberships"]
                if reference["stableGaussianIds"] == [1]
            )
        )
        child_reference["provenanceDigests"] = [source_two]
        retire_payload = {
            "schemaVersion": 1,
            "relation": "retired",
            "fromScopeRevision": 1,
            "toScopeRevision": 2,
            "revisionSourceDigests": [source_two],
            "parentComponentIds": [parent_reference["componentId"]],
            "childComponentIds": [],
            "parentMemberships": [parent_reference],
            "childMemberships": [],
            "sharedStableGaussianIds": [],
            "introducedStableGaussianIds": [],
            "retiredStableGaussianIds": [1, 2],
            "retiredToContextStableGaussianIds": [],
            "retiredOutOfScopeStableGaussianIds": [1, 2],
            "subcomponentDecisionDigests": [],
        }
        introduce_payload = {
            "schemaVersion": 1,
            "relation": "introduced",
            "fromScopeRevision": 1,
            "toScopeRevision": 2,
            "revisionSourceDigests": [source_two],
            "parentComponentIds": [],
            "childComponentIds": [child_reference["componentId"]],
            "parentMemberships": [],
            "childMemberships": [child_reference],
            "sharedStableGaussianIds": [],
            "introducedStableGaussianIds": [1],
            "retiredStableGaussianIds": [],
            "retiredToContextStableGaussianIds": [],
            "retiredOutOfScopeStableGaussianIds": [],
            "subcomponentDecisionDigests": [],
        }
        forged_records = [
            {
                **retire_payload,
                "lineageDigest": route_b_artifact_digest(retire_payload),
            },
            {
                **introduce_payload,
                "lineageDigest": route_b_artifact_digest(introduce_payload),
            },
        ]
        tampered["componentLineageLedger"] = sorted(
            [
                *(
                    record
                    for record in tampered["componentLineageLedger"]
                    if record["toScopeRevision"] != 2
                ),
                *forged_records,
            ],
            key=lambda record: (record["toScopeRevision"], record["lineageDigest"]),
        )
        tampered["subcomponentDecisionLedger"] = []
        provenance = tampered["provenance"]
        provenance["sourceDigests"] = [source_two]
        provenance_payload = {
            key: value
            for key, value in provenance.items()
            if key != "revisionProvenanceDigest"
        }
        provenance["revisionProvenanceDigest"] = route_b_artifact_digest(
            provenance_payload
        )
        tampered["provenanceDigest"] = provenance["revisionProvenanceDigest"]
        tampered["revisionProvenanceLedger"][2] = deepcopy(provenance)
        child_component = tampered["activeFrontierComponents"][0]
        child_component["provenanceDigests"] = [source_two]
        child_component["lineageRecordDigests"] = [
            next(
                record["lineageDigest"]
                for record in forged_records
                if record["relation"] == "introduced"
            )
        ]
        component_payload = {
            key: value
            for key, value in child_component.items()
            if key != "componentDigest"
        }
        child_component["componentDigest"] = route_b_artifact_digest(component_payload)
        state_payload = {
            key: value for key, value in tampered.items() if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(state_payload)

        self.assertFalse(is_target_scope_state(tampered))

    def test_revision_zero_accepts_finite_extreme_log_scale_geometry(self) -> None:
        geometry = create_conservative_seed_target_geometry(
            target_splat_id="splat-1",
            rows=[
                {
                    "stableGaussianId": 1,
                    "center": [0.0, 0.0, 0.0],
                    "logScales": [700.0, 700.0, 700.0],
                }
            ],
        )
        seed = seed_record(
            stable_ids=[1],
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
            geometry=geometry,
        )

        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )

        self.assertTrue(is_target_scope_state(state))
        self.assertEqual(
            state["coreComponents"][0]["materialSummary"]["totalLogScaleVolume"],
            2100.0,
        )

    def test_malformed_inputs_raise_target_scope_domain_errors(self) -> None:
        with self.assertRaises(TargetScopeStateValidationError):
            create_target_scope_component_policy(
                {
                    "schemaVersion": 1,
                    "policyId": "target-scope-components/experimental-shadow-v1",
                    "adjacencyScaleMultiplier": 10**10000,
                    "boundsScaleMultiplier": 1.0,
                }
            )

        geometry = target_geometry([(1, (0.0, 0.0, 0.0))])
        seed = seed_record(
            stable_ids=[1],
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
            geometry=geometry,
        )
        state = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        with self.assertRaises(TargetScopeStateValidationError):
            revise_target_scope_state(
                previous_state=state,
                target_geometry=geometry,
                request_binding=state["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": [],
                    "sourceDigests": [digest("8")],
                },
            )
        with self.assertRaises(TargetScopeStateValidationError):
            rotate_target_scope_epoch(
                previous_state=state,
                seed_record=seed,
                target_geometry=geometry,
                component_policy=component_policy(),
                reason=[],
                source_digests=[digest("8")],
            )

    def test_rejected_frontier_remains_separate_from_required_context(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
                (3, (6.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.1],
            negative=[0.0, 0.0],
            visible=[1.0, 1.0],
            geometry=geometry,
        )
        revision_zero = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        active, discovery_source_digest = admit_discovery_ids(
            revision_zero, geometry, stable_ids=[2], marker="5"
        )
        source = digest("6")
        revised = revise_target_scope_state(
            previous_state=active,
            target_geometry=geometry,
            request_binding=active["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[
                {
                    "stableGaussianIds": [2],
                    "state": "rejected",
                    "provenanceDigests": sorted([discovery_source_digest, source]),
                }
            ],
            required_context_stable_gaussian_ids=[3],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "component-rejection-fixture",
                "sourceDigests": [source],
            },
        )

        self.assertEqual(revised["rejectedFrontierStableGaussianIds"], [2])
        self.assertEqual(revised["requiredContextStableGaussianIds"], [3])
        self.assertEqual(revised["rejectedFrontierComponents"][0]["state"], "rejected")
        self.assertEqual(revised["rejectedFrontierLedger"][0]["event"], "rejected")
        self.assertEqual(len(revised["discoveryEnvelopeLedger"]), 1)
        self.assertTrue(is_target_scope_state(revised))
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "cannot become Core or required Context"
        ):
            revise_target_scope_state(
                previous_state=revised,
                target_geometry=geometry,
                request_binding=revised["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[2, 3],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-rejected-to-context",
                    "sourceDigests": [digest("a")],
                },
            )
        tampered_event_state = deepcopy(revised)
        tampered_event = tampered_event_state["rejectedFrontierLedger"][0]
        tampered_event["componentDigest"] = digest("c")
        tampered_event["provenanceDigests"] = [digest("d")]
        event_payload = {
            key: value for key, value in tampered_event.items() if key != "eventDigest"
        }
        tampered_event["eventDigest"] = route_b_artifact_digest(event_payload)
        tampered_payload = {
            key: value
            for key, value in tampered_event_state.items()
            if key != "stateDigest"
        }
        tampered_event_state["stateDigest"] = route_b_artifact_digest(tampered_payload)
        self.assertFalse(is_target_scope_state(tampered_event_state))
        out_of_range_history = deepcopy(revised)
        out_of_range_event = out_of_range_history["rejectedFrontierLedger"][-1]
        out_of_range_event["scopeRevision"] = 999
        out_of_range_event_payload = {
            key: value
            for key, value in out_of_range_event.items()
            if key != "eventDigest"
        }
        out_of_range_event["eventDigest"] = route_b_artifact_digest(
            out_of_range_event_payload
        )
        out_of_range_payload = {
            key: value
            for key, value in out_of_range_history.items()
            if key != "stateDigest"
        }
        out_of_range_history["stateDigest"] = route_b_artifact_digest(
            out_of_range_payload
        )
        self.assertFalse(is_target_scope_state(out_of_range_history))
        retired_rejection = revise_target_scope_state(
            previous_state=revised,
            target_geometry=geometry,
            request_binding=revised["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[3],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "retire-rejected-frontier",
                "sourceDigests": [digest("e")],
            },
        )
        self.assertTrue(is_target_scope_state(retired_rejection))
        post_retirement = revise_target_scope_state(
            previous_state=retired_rejection,
            target_geometry=geometry,
            request_binding=retired_rejection["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[3],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "post-retirement-history-fixture",
                "sourceDigests": [digest("f")],
            },
        )
        tampered_history = deepcopy(post_retirement)
        retirement_snapshot = tampered_history["scopeRevisionLedger"][-2]
        retirement_snapshot["requiredContextStableGaussianIds"] = [2, 3]
        retirement_snapshot_payload = {
            key: value
            for key, value in retirement_snapshot.items()
            if key != "scopeRevisionDigest"
        }
        retirement_snapshot["scopeRevisionDigest"] = route_b_artifact_digest(
            retirement_snapshot_payload
        )
        history_payload = {
            key: value
            for key, value in tampered_history.items()
            if key != "stateDigest"
        }
        tampered_history["stateDigest"] = route_b_artifact_digest(history_payload)
        self.assertFalse(is_target_scope_state(tampered_history))
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "cannot become Core or required Context"
        ):
            revise_target_scope_state(
                previous_state=retired_rejection,
                target_geometry=geometry,
                request_binding=retired_rejection["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[2, 3],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-retired-rejection-laundering",
                    "sourceDigests": [digest("8")],
                },
            )
        retired_recovery = create_target_scope_observation_shadow_source(
            target_scope_state=retired_rejection,
            observation={
                "status": "user-confirmed",
                "sourceKind": "user-confirmed-expert-recovery",
                "artifactId": "retired-expert-observation",
                "artifactDigest": digest("9"),
                "viewIds": ["retired-expert-view"],
                "supportedStableGaussianIds": [2],
                "spatialBounds": {
                    "minimum": [2.75, -0.25, -0.25],
                    "maximum": [3.25, 0.25, 0.25],
                },
                "reason": "user-confirmed-retired-recovery",
            },
        )
        reopened_retired = admit_target_scope_discovery_sources(
            previous_state=retired_rejection,
            target_geometry=geometry,
            request_binding=retired_rejection["requestBinding"],
            sources=[retired_recovery],
        )
        self.assertEqual(reopened_retired["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(
            [event["event"] for event in reopened_retired["rejectedFrontierLedger"]],
            ["rejected", "reopened"],
        )
        missing_historical_event = deepcopy(retired_rejection)
        missing_historical_event["rejectedFrontierLedger"] = []
        missing_event_payload = {
            key: value
            for key, value in missing_historical_event.items()
            if key != "stateDigest"
        }
        missing_historical_event["stateDigest"] = route_b_artifact_digest(
            missing_event_payload
        )
        self.assertFalse(is_target_scope_state(missing_historical_event))
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "must explicitly reopen",
        ):
            revise_target_scope_state(
                previous_state=revised,
                target_geometry=geometry,
                request_binding=revised["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2],
                        "state": "new",
                        "provenanceDigests": [digest("7")],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[3],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-rejection-bypass",
                    "sourceDigests": [digest("7")],
                },
            )

        recovery_source = discovery_source(
            revised,
            source_kind="user-confirmed-expert-recovery",
            stable_ids=[2],
            marker="7",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
            view_ids=["expert-view"],
        )
        reopened = admit_target_scope_discovery_sources(
            previous_state=revised,
            target_geometry=geometry,
            request_binding=revised["requestBinding"],
            sources=[recovery_source],
        )
        self.assertEqual(reopened["rejectedFrontierStableGaussianIds"], [])
        self.assertEqual(reopened["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(
            [event["event"] for event in reopened["rejectedFrontierLedger"]],
            ["rejected", "reopened"],
        )
        self.assertEqual(reopened["discoveryEnvelopeLedger"][-1], recovery_source)
        self.assertEqual(len(reopened["discoveryEnvelopeLedger"]), 2)
        self.assertTrue(is_target_scope_state(reopened))

        broken_history = deepcopy(reopened)
        reopened_event = broken_history["rejectedFrontierLedger"][-1]
        reopened_event["previousEventDigest"] = None
        event_payload = {
            key: value for key, value in reopened_event.items() if key != "eventDigest"
        }
        reopened_event["eventDigest"] = route_b_artifact_digest(event_payload)
        broken_payload = {
            key: value for key, value in broken_history.items() if key != "stateDigest"
        }
        broken_history["stateDigest"] = route_b_artifact_digest(broken_payload)
        self.assertFalse(is_target_scope_state(broken_history))

        invalid = deepcopy(revised)
        invalid["requiredContextStableGaussianIds"] = [2, 3]
        payload = {key: value for key, value in invalid.items() if key != "stateDigest"}
        invalid["stateDigest"] = route_b_artifact_digest(payload)
        self.assertFalse(is_target_scope_state(invalid))

    def test_discovery_source_families_are_bounded_deduped_and_deterministic(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
                (3, (6.0, 0.0, 0.0)),
                (4, (9.0, 0.0, 0.0)),
                (5, (12.0, 0.0, 0.0)),
                (6, (15.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3, 4, 5, 6],
            positive=[0.9, 0.1, 0.1, 0.1, 0.1, 0.1],
            negative=[0.0] * 6,
            visible=[1.0] * 6,
            geometry=geometry,
        )
        initial = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        negative_zero_bounds = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[1],
            marker="0",
            minimum=(-0.0, -0.0, -0.0),
            maximum=(0.0, 0.0, 0.0),
        )
        positive_zero_bounds = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[1],
            marker="0",
            minimum=(0.0, 0.0, 0.0),
            maximum=(0.0, 0.0, 0.0),
        )
        self.assertEqual(negative_zero_bounds, positive_zero_bounds)
        source_specs = [
            ("evidence-working-set-boundary-contact", 2, "a", ["view-a"]),
            ("core-external-included-positive-support", 3, "b", ["view-b"]),
            ("coherent-cross-view-support", 4, "c", ["view-c1", "view-c2"]),
            ("reviewed-target-local-spatial-support", 5, "d", ["anchor-view"]),
            ("user-confirmed-expert-recovery", 6, "e", ["view-e"]),
        ]
        sources = [
            discovery_source(
                initial,
                source_kind=source_kind,
                stable_ids=[stable_id],
                marker=marker,
                minimum=(stable_id * 3.0 - 3.25, -0.25, -0.25),
                maximum=(stable_id * 3.0 - 2.75, 0.25, 0.25),
                view_ids=view_ids,
            )
            for source_kind, stable_id, marker, view_ids in source_specs
        ]
        zero_wire_payload = {
            key: deepcopy(value)
            for key, value in sources[0].items()
            if key != "sourceDigest"
        }
        zero_wire_payload["spatialBounds"] = {
            "minimum": [2.75, 0.0, 0.0],
            "maximum": [3.25, 0.0, 0.0],
        }
        sources[0] = create_target_scope_discovery_source(zero_wire_payload)
        coherent_payload = {
            key: deepcopy(value)
            for key, value in sources[2].items()
            if key != "sourceDigest"
        }
        coherent_payload["sourceViewIds"] = list(
            reversed(coherent_payload["sourceViewIds"])  # type: ignore[arg-type]
        )
        recreated_coherent = create_target_scope_discovery_source(coherent_payload)
        self.assertEqual(recreated_coherent, sources[2])
        for source in sources:
            self.assertEqual(validate_target_scope_discovery_source(source), source)

        forward = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=[sources[1], sources[0], sources[4], sources[2], sources[3]],
        )
        reverse = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=list(reversed(sources)),
        )
        self.assertEqual(
            canonical_target_scope_state_bytes(forward),
            canonical_target_scope_state_bytes(reverse),
        )
        signed_zero_tamper = deepcopy(forward)
        zero_source = next(
            record
            for record in signed_zero_tamper["discoveryEnvelopeLedger"]
            if record["sourceDigest"] == sources[0]["sourceDigest"]
        )
        zero_source["spatialBounds"]["minimum"][1] = -0.0
        self.assertEqual(signed_zero_tamper["stateDigest"], forward["stateDigest"])
        self.assertFalse(is_target_scope_state(signed_zero_tamper))
        self.assertEqual(forward["coreStableGaussianIds"], [1])
        self.assertEqual(forward["activeFrontierStableGaussianIds"], [2, 3, 4, 5, 6])
        self.assertEqual(forward["rejectedFrontierStableGaussianIds"], [])
        self.assertEqual(forward["requiredContextStableGaussianIds"], [])
        self.assertEqual(
            [record["sourceKind"] for record in forward["discoveryEnvelopeLedger"]],
            [
                record["sourceKind"]
                for record in sorted(
                    sources, key=lambda record: str(record["sourceDigest"])
                )
            ],
        )
        self.assertTrue(
            all(
                component["state"] == "new"
                for component in forward["activeFrontierComponents"]
            )
        )
        replay = admit_target_scope_discovery_sources(
            previous_state=forward,
            target_geometry=geometry,
            request_binding=forward["requestBinding"],
            sources=[sources[0], sources[0]],
        )
        self.assertEqual(replay["scopeRevision"], forward["scopeRevision"])
        self.assertEqual(
            canonical_target_scope_state_bytes(replay),
            canonical_target_scope_state_bytes(forward),
        )

    def test_discovery_budget_and_epoch_reset_fail_closed_without_partial_state(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
                (3, (6.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            geometry=geometry,
        )
        policy = discovery_policy(maximum_sources=1, maximum_stable_ids=1)
        initial = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=policy,
        )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "fresh authoritative observation or discovery source",
        ):
            revise_target_scope_state(
                previous_state=initial,
                target_geometry=geometry,
                request_binding=initial["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2],
                        "state": "new",
                        "provenanceDigests": [digest("f")],
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-unbound-frontier-introduction",
                    "sourceDigests": [digest("f")],
                },
            )
        contextual = revise_target_scope_state(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[2],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "context-before-discovery-fixture",
                "sourceDigests": [digest("0")],
            },
        )
        context_source = discovery_source(
            contextual,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="9",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        admitted_from_context = admit_target_scope_discovery_sources(
            previous_state=contextual,
            target_geometry=geometry,
            request_binding=contextual["requestBinding"],
            sources=[context_source],
        )
        self.assertEqual(admitted_from_context["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(admitted_from_context["requiredContextStableGaussianIds"], [])
        first = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="a",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        admitted = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=[first, first],
        )
        self.assertEqual(len(admitted["discoveryEnvelopeLedger"]), 1)
        self.assertEqual(admitted["activeFrontierStableGaussianIds"], [2])

        duplicate = admit_target_scope_discovery_sources(
            previous_state=admitted,
            target_geometry=geometry,
            request_binding=admitted["requestBinding"],
            sources=[first],
        )
        self.assertEqual(duplicate["stateDigest"], admitted["stateDigest"])
        before_invalid = canonical_target_scope_state_bytes(admitted)
        second = discovery_source(
            admitted,
            source_kind="core-external-included-positive-support",
            stable_ids=[2],
            marker="b",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "source-record budget"
        ):
            admit_target_scope_discovery_sources(
                previous_state=admitted,
                target_geometry=geometry,
                request_binding=admitted["requestBinding"],
                sources=[second],
            )
        over_stable_id_budget = discovery_source(
            initial,
            source_kind="coherent-cross-view-support",
            stable_ids=[2, 3],
            marker="c",
            minimum=(2.75, -0.25, -0.25),
            maximum=(6.25, 0.25, 0.25),
            view_ids=["view-c1", "view-c2"],
        )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "Stable Gaussian ID budget"
        ):
            admit_target_scope_discovery_sources(
                previous_state=initial,
                target_geometry=geometry,
                request_binding=initial["requestBinding"],
                sources=[over_stable_id_budget],
            )
        out_of_target = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[99],
            marker="d",
            minimum=(0.0, 0.0, 0.0),
            maximum=(100.0, 100.0, 100.0),
        )
        with self.assertRaisesRegex(TargetScopeStateTransitionError, "target-bounded"):
            admit_target_scope_discovery_sources(
                previous_state=initial,
                target_geometry=geometry,
                request_binding=initial["requestBinding"],
                sources=[out_of_target],
            )
        spatially_unbounded = {
            key: deepcopy(value)
            for key, value in first.items()
            if key != "sourceDigest"
        }
        spatially_unbounded["spatialBounds"] = {
            "minimum": [float("-inf"), 0.0, 0.0],
            "maximum": [float("inf"), 1.0, 1.0],
        }
        with self.assertRaisesRegex(TargetScopeStateValidationError, "spatial bounds"):
            create_target_scope_discovery_source(spatially_unbounded)
        out_of_bounds = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="e",
            minimum=(20.0, -0.25, -0.25),
            maximum=(21.0, 0.25, 0.25),
        )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "spatially bounded"
        ):
            admit_target_scope_discovery_sources(
                previous_state=initial,
                target_geometry=geometry,
                request_binding=initial["requestBinding"],
                sources=[out_of_bounds],
            )
        self.assertEqual(canonical_target_scope_state_bytes(admitted), before_invalid)

        rotated = rotate_target_scope_epoch(
            previous_state=admitted,
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=policy,
            reason="authoritative-stable-mask-correction",
            source_digests=[digest("f")],
        )
        self.assertEqual(rotated["discoveryEnvelopeLedger"], [])
        fresh = discovery_source(
            rotated,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="a",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        reset_admission = admit_target_scope_discovery_sources(
            previous_state=rotated,
            target_geometry=geometry,
            request_binding=rotated["requestBinding"],
            sources=[fresh],
        )
        self.assertEqual(len(reset_admission["discoveryEnvelopeLedger"]), 1)

    def test_rejected_frontier_reopens_only_with_new_discovery_provenance(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
                (3, (4.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            geometry=geometry,
        )
        initial = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        first = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="a",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        discovered = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=[first],
        )
        first_digest = str(first["sourceDigest"])
        rejected = revise_target_scope_state(
            previous_state=discovered,
            target_geometry=geometry,
            request_binding=discovered["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[
                {
                    "stableGaussianIds": [2],
                    "state": "rejected",
                    "provenanceDigests": sorted([first_digest, digest("b")]),
                }
            ],
            required_context_stable_gaussian_ids=[3],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "component-rejection-fixture",
                "sourceDigests": [digest("b")],
            },
        )
        self.assertEqual(len(rejected["discoveryEnvelopeLedger"]), 1)
        self.assertEqual(rejected["requiredContextStableGaussianIds"], [3])
        metadata_variant_payload = {
            key: deepcopy(value)
            for key, value in first.items()
            if key != "sourceDigest"
        }
        metadata_variant_payload["reason"] = "metadata-only-rewording"
        metadata_variant = create_target_scope_discovery_source(
            metadata_variant_payload
        )
        metadata_replay = admit_target_scope_discovery_sources(
            previous_state=rejected,
            target_geometry=geometry,
            request_binding=rejected["requestBinding"],
            sources=[metadata_variant],
        )
        self.assertEqual(metadata_replay["stateDigest"], rejected["stateDigest"])
        self.assertEqual(metadata_replay["rejectedFrontierStableGaussianIds"], [2])
        self.assertEqual(len(metadata_replay["discoveryEnvelopeLedger"]), 1)
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "new authoritative observation or discovery source",
        ):
            revise_target_scope_state(
                previous_state=rejected,
                target_geometry=geometry,
                request_binding=rejected["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2],
                        "state": "reopened",
                        "provenanceDigests": sorted([first_digest, digest("b")]),
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[3],
                revision_provenance={
                    "kind": "new-observation",
                    "reason": "unchanged-observation-replay",
                    "sourceDigests": [first_digest],
                },
            )

        fresh_observation_digest = digest("e")
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "new authoritative observation or discovery source",
        ):
            revise_target_scope_state(
                previous_state=rejected,
                target_geometry=geometry,
                request_binding=rejected["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[
                    {
                        "stableGaussianIds": [2],
                        "state": "reopened",
                        "provenanceDigests": sorted(
                            [first_digest, digest("b"), fresh_observation_digest]
                        ),
                    }
                ],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[3],
                revision_provenance={
                    "kind": "new-observation",
                    "reason": "unversioned-observation-recovery",
                    "sourceDigests": [fresh_observation_digest],
                },
            )
        merged_recovery_source = discovery_source(
            rejected,
            source_kind="user-confirmed-expert-recovery",
            stable_ids=[2, 3],
            marker="d",
            minimum=(2.75, -0.25, -0.25),
            maximum=(4.25, 0.25, 0.25),
            view_ids=["expert-merged-view"],
        )
        merged_recovery = admit_target_scope_discovery_sources(
            previous_state=rejected,
            target_geometry=geometry,
            request_binding=rejected["requestBinding"],
            sources=[merged_recovery_source],
        )
        self.assertEqual(merged_recovery["activeFrontierStableGaussianIds"], [2, 3])
        self.assertEqual(merged_recovery["requiredContextStableGaussianIds"], [])
        self.assertEqual(
            merged_recovery["activeFrontierComponents"][0]["state"], "reopened"
        )
        self.assertEqual(
            [event["event"] for event in merged_recovery["rejectedFrontierLedger"]],
            ["rejected", "reopened"],
        )
        recovery = create_target_scope_observation_shadow_source(
            target_scope_state=rejected,
            observation={
                "status": "user-confirmed",
                "sourceKind": "user-confirmed-expert-recovery",
                "artifactId": "expert-observation-c",
                "artifactDigest": digest("c"),
                "viewIds": ["expert-view"],
                "supportedStableGaussianIds": [2],
                "spatialBounds": {
                    "minimum": [2.75, -0.25, -0.25],
                    "maximum": [3.25, 0.25, 0.25],
                },
                "reason": "user-confirmed-expert-recovery",
            },
        )
        reopened = admit_target_scope_discovery_sources(
            previous_state=rejected,
            target_geometry=geometry,
            request_binding=rejected["requestBinding"],
            sources=[recovery],
        )
        self.assertEqual(reopened["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(reopened["rejectedFrontierStableGaussianIds"], [])
        self.assertEqual(
            reopened["discoveryEnvelopeLedger"][:-1],
            rejected["discoveryEnvelopeLedger"],
        )
        self.assertEqual(reopened["requiredContextStableGaussianIds"], [3])
        self.assertEqual(reopened["activeFrontierComponents"][0]["state"], "reopened")
        self.assertEqual(
            [event["event"] for event in reopened["rejectedFrontierLedger"]],
            ["rejected", "reopened"],
        )
        duplicate = admit_target_scope_discovery_sources(
            previous_state=reopened,
            target_geometry=geometry,
            request_binding=reopened["requestBinding"],
            sources=[recovery],
        )
        self.assertEqual(duplicate["stateDigest"], reopened["stateDigest"])

    def test_s1_or_technical_failure_cannot_erase_discovered_support(self) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2],
            positive=[0.9, 0.1],
            negative=[0.0, 0.0],
            visible=[1.0, 1.0],
            geometry=geometry,
        )
        initial = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        source = discovery_source(
            initial,
            source_kind="reviewed-target-local-spatial-support",
            stable_ids=[2],
            marker="a",
            minimum=(2.75, -0.25, -0.25),
            maximum=(3.25, 0.25, 0.25),
        )
        discovered = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=[source],
        )
        before_failure = canonical_target_scope_state_bytes(discovered)
        for failure_kind in (
            "low-visibility",
            "low-support",
            "s1-failure",
            "s1-depth-unavailable",
            "technical-failure",
        ):
            with (
                self.subTest(failure_kind=failure_kind),
                self.assertRaisesRegex(
                    TargetScopeStateTransitionError, "cannot reject or erase"
                ),
            ):
                revise_target_scope_state(
                    previous_state=discovered,
                    target_geometry=geometry,
                    request_binding=discovered["requestBinding"],
                    core_stable_gaussian_ids=[1],
                    active_frontier=[],
                    rejected_frontier=[
                        {
                            "stableGaussianIds": [2],
                            "state": "rejected",
                            "provenanceDigests": [source["sourceDigest"]],
                        }
                    ],
                    required_context_stable_gaussian_ids=[],
                    revision_provenance={
                        "kind": failure_kind,
                        "reason": "failed-observation-must-not-remove-support",
                        "sourceDigests": [digest("b")],
                    },
                )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "must remain Core, active Frontier"
        ):
            revise_target_scope_state(
                previous_state=discovered,
                target_geometry=geometry,
                request_binding=discovered["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-unrecorded-retirement",
                    "sourceDigests": [digest("c")],
                },
            )
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError, "promote it out of active Frontier"
        ):
            revise_target_scope_state(
                previous_state=discovered,
                target_geometry=geometry,
                request_binding=discovered["requestBinding"],
                core_stable_gaussian_ids=[1, 2],
                active_frontier=[],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "technical-failure",
                    "reason": "invalid-failure-promotion",
                    "sourceDigests": [digest("d")],
                },
            )
        rejection_digest = digest("e")
        valid_rejection = revise_target_scope_state(
            previous_state=discovered,
            target_geometry=geometry,
            request_binding=discovered["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[
                {
                    "stableGaussianIds": [2],
                    "state": "rejected",
                    "provenanceDigests": sorted(
                        [str(source["sourceDigest"]), rejection_digest]
                    ),
                }
            ],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "valid-rejection-before-coordinated-tamper",
                "sourceDigests": [rejection_digest],
            },
        )
        tampered_failure = deepcopy(valid_rejection)
        tampered_provenance = tampered_failure["revisionProvenanceLedger"][-1]
        tampered_provenance["kind"] = "technical-failure"
        provenance_payload = {
            key: value
            for key, value in tampered_provenance.items()
            if key != "revisionProvenanceDigest"
        }
        tampered_provenance["revisionProvenanceDigest"] = route_b_artifact_digest(
            provenance_payload
        )
        tampered_failure["provenance"] = deepcopy(tampered_provenance)
        tampered_failure["provenanceDigest"] = tampered_provenance[
            "revisionProvenanceDigest"
        ]
        state_payload = {
            key: value
            for key, value in tampered_failure.items()
            if key != "stateDigest"
        }
        tampered_failure["stateDigest"] = route_b_artifact_digest(state_payload)
        self.assertFalse(is_target_scope_state(tampered_failure))
        self.assertEqual(canonical_target_scope_state_bytes(discovered), before_failure)
        self.assertEqual(discovered["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(len(discovered["discoveryEnvelopeLedger"]), 1)

    def test_shadow_adapters_create_bound_boundary_and_observation_sources(
        self,
    ) -> None:
        geometry = target_geometry(
            [
                (1, (0.0, 0.0, 0.0)),
                (2, (3.0, 0.0, 0.0)),
                (3, (6.0, 0.0, 0.0)),
            ]
        )
        seed = seed_record(
            stable_ids=[1, 2, 3],
            positive=[0.9, 0.1, 0.1],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            geometry=geometry,
        )
        initial = bootstrap_target_scope_state_from_seed(
            seed_record=seed,
            target_geometry=geometry,
            component_policy=component_policy(),
            discovery_policy=discovery_policy(),
        )
        boundary = create_target_scope_boundary_contact_shadow_source(
            target_scope_state=initial,
            boundary_result={
                "status": "failed-closed",
                "reason": "evidence-working-set-boundary-contact",
                "contactStableGaussianIds": [2],
            },
            source_artifact={
                "artifactId": "working-set-boundary:view-a",
                "artifactDigest": digest("a"),
                "viewId": "view-a",
            },
            spatial_bounds={
                "minimum": [2.75, -0.25, -0.25],
                "maximum": [3.25, 0.25, 0.25],
            },
        )
        observation = create_target_scope_observation_shadow_source(
            target_scope_state=initial,
            observation={
                "status": "included-stable",
                "sourceKind": "core-external-included-positive-support",
                "artifactId": "evidence:view-b",
                "artifactDigest": digest("b"),
                "viewIds": ["view-b"],
                "supportedStableGaussianIds": [3],
                "spatialBounds": {
                    "minimum": [5.75, -0.25, -0.25],
                    "maximum": [6.25, 0.25, 0.25],
                },
                "reason": "new-included-stable-positive-support",
            },
        )
        self.assertEqual(
            boundary["sourceKind"], "evidence-working-set-boundary-contact"
        )
        self.assertEqual(
            observation["sourceKind"],
            "core-external-included-positive-support",
        )
        admitted = admit_target_scope_discovery_sources(
            previous_state=initial,
            target_geometry=geometry,
            request_binding=initial["requestBinding"],
            sources=[observation, boundary],
        )
        self.assertEqual(admitted["activeFrontierStableGaussianIds"], [2, 3])
        self.assertEqual(len(admitted["discoveryEnvelopeLedger"]), 2)


if __name__ == "__main__":
    unittest.main()

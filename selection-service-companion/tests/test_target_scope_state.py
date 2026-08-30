from __future__ import annotations

from copy import deepcopy
import unittest

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
    bootstrap_target_scope_state_from_seed,
    canonical_target_scope_state_bytes,
    create_target_scope_component_policy,
    create_target_scope_subcomponent_decision,
    is_target_scope_state,
    revise_target_scope_state,
    restore_target_scope_state,
    rotate_target_scope_epoch,
    target_scope_state_identity,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def component_policy() -> dict[str, object]:
    return create_target_scope_component_policy({
        "schemaVersion": 1,
        "policyId": "target-scope-components/experimental-shadow-v1",
        "adjacencyScaleMultiplier": 2.0,
        "boundsScaleMultiplier": 1.0,
    })


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
    working_set = create_evidence_working_set({
        "targetSplatId": "splat-1",
        "coreTargetStableIds": stable_ids,
        "contextStableGaussianIds": [],
    })
    admitted = admit_gaussian_evidence({
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
    })
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
    policy = create_conservative_seed_policy({
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
    })
    result = evaluate_conservative_seed_shadow(
        evidence_artifact=artifact,
        target_geometry=geometry,
        policy=policy,
        clock_ns=lambda: 0,
    )
    record = result["record"]
    assert isinstance(record, dict)
    return record


class TargetScopeStateTests(unittest.TestCase):
    def test_revision_zero_preserves_the_complete_seed_partition(self) -> None:
        geometry = target_geometry([
            (5, (30.0, 0.0, 0.0)),
            (4, (20.0, 0.0, 0.0)),
            (2, (1.0, 0.0, 0.0)),
            (1, (0.0, 0.0, 0.0)),
            (3, (10.0, 0.0, 0.0)),
        ])
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
        )
        second = bootstrap_target_scope_state_from_seed(
            seed_record=second_seed,
            target_geometry=second_geometry,
            component_policy=component_policy(),
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
            key: value
            for key, value in tampered.items()
            if key != "stateDigest"
        }
        tampered["stateDigest"] = route_b_artifact_digest(state_payload)
        self.assertFalse(is_target_scope_state(tampered))

    def test_empty_core_is_valid_but_role_overlap_and_foreign_ids_fail_closed(self) -> None:
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
        )
        self.assertEqual(state["coreStableGaussianIds"], [])
        self.assertTrue(is_target_scope_state(state))

        foreign = deepcopy(state)
        foreign["requiredContextStableGaussianIds"] = [2]
        payload = {
            key: value
            for key, value in foreign.items()
            if key != "stateDigest"
        }
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
        )
        overlap["requiredContextStableGaussianIds"] = [1]
        payload = {
            key: value
            for key, value in overlap.items()
            if key != "stateDigest"
        }
        overlap["stateDigest"] = route_b_artifact_digest(payload)
        self.assertFalse(is_target_scope_state(overlap))

        with self.assertRaises(TargetScopeStateValidationError):
            create_target_scope_component_policy({
                "schemaVersion": 1,
                "policyId": "target-scope-components/experimental-shadow-v1",
                "adjacencyScaleMultiplier": 0.0,
                "boundsScaleMultiplier": 1.0,
            })



    def test_split_and_merge_lineage_is_deterministic_and_replayable(self) -> None:
        geometry = target_geometry([
            (5, (4.0, 0.0, 0.0)),
            (1, (-4.0, 0.0, 0.0)),
            (4, (3.0, 0.0, 0.0)),
            (2, (-3.0, 0.0, 0.0)),
            (3, (2.0, 0.0, 0.0)),
        ])
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
        )
        request_binding = deepcopy(revision_zero["requestBinding"])
        request_binding["contextRevision"] = 3
        source = digest("f")
        revision_one = revise_target_scope_state(
            previous_state=revision_zero,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[2, 1],
            active_frontier=[{
                "stableGaussianIds": [5, 3, 4],
                "state": "new",
                "provenanceDigests": [source],
            }],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "new-observation",
                "reason": "core-external-support",
                "sourceDigests": [source],
            },
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
                active_frontier=[{
                    "stableGaussianIds": [4, 5],
                    "state": "observing",
                    "provenanceDigests": [source, second_source],
                }],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "unreviewed-subcomponent-split",
                    "sourceDigests": [second_source],
                },
            )
        split_decision = create_target_scope_subcomponent_decision({
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
        })
        split = revise_target_scope_state(
            previous_state=revision_one,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[1, 2, 3],
            active_frontier=[{
                "stableGaussianIds": [5, 4],
                "state": "observing",
                "provenanceDigests": [source, second_source],
            }],
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
            active_frontier=[{
                "stableGaussianIds": [4, 5],
                "state": "observing",
                "provenanceDigests": [second_source, source],
            }],
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
            if record["toScopeRevision"] == 2
            and record["relation"] == "split"
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
            component["componentDigest"] = route_b_artifact_digest(
                component_payload
            )
        state_payload = {
            key: value
            for key, value in tampered.items()
            if key != "stateDigest"
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
            if record["toScopeRevision"] == 3
            and record["relation"] == "merge"
        )
        old_merge_digest = fabricated_record["lineageDigest"]
        retained_parent = next(
            reference
            for reference in fabricated_record["parentMemberships"]
            if reference["stableGaussianIds"] == [3]
        )
        fabricated_parent = {
            "componentId": route_b_artifact_digest({
                "schemaVersion": 1,
                "targetSplatId": fabricated["targetSplatId"],
                "targetGeometryDigest": fabricated["targetGeometryDigest"],
                "componentPolicyDigest": fabricated["componentPolicyDigest"],
                "stableGaussianIds": [5],
            }),
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
        fabricated_record["lineageDigest"] = route_b_artifact_digest(
            fabricated_payload
        )
        for component in fabricated["coreComponents"]:
            if old_merge_digest not in component["lineageRecordDigests"]:
                continue
            component["lineageRecordDigests"] = [
                fabricated_record["lineageDigest"]
            ]
            component_payload = {
                key: value
                for key, value in component.items()
                if key != "componentDigest"
            }
            component["componentDigest"] = route_b_artifact_digest(
                component_payload
            )
        fabricated["componentLineageLedger"].sort(
            key=lambda record: (
                record["toScopeRevision"],
                record["lineageDigest"],
            )
        )
        fabricated_state_payload = {
            key: value
            for key, value in fabricated.items()
            if key != "stateDigest"
        }
        fabricated["stateDigest"] = route_b_artifact_digest(
            fabricated_state_payload
        )
        self.assertFalse(is_target_scope_state(fabricated))


    def test_core_shrink_requires_epoch_rotation_and_restoration_is_exact(self) -> None:
        geometry = target_geometry([
            (1, (0.0, 0.0, 0.0)),
            (2, (1.0, 0.0, 0.0)),
            (3, (6.0, 0.0, 0.0)),
        ])
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
        )
        request_binding = deepcopy(revision_zero["requestBinding"])
        request_binding["contextRevision"] = 3
        source = digest("2")
        revision_one = revise_target_scope_state(
            previous_state=revision_zero,
            target_geometry=geometry,
            request_binding=request_binding,
            core_stable_gaussian_ids=[1, 2],
            active_frontier=[{
                "stableGaussianIds": [3],
                "state": "new",
                "provenanceDigests": [source],
            }],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[],
            revision_provenance={
                "kind": "new-observation",
                "reason": "new-included-observation",
                "sourceDigests": [source],
            },
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
                active_frontier=[{
                    "stableGaussianIds": [3],
                    "state": "new",
                    "provenanceDigests": [source],
                }],
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


    def test_revision_zero_accepts_finite_extreme_log_scale_geometry(self) -> None:
        geometry = create_conservative_seed_target_geometry(
            target_splat_id="splat-1",
            rows=[{
                "stableGaussianId": 1,
                "center": [0.0, 0.0, 0.0],
                "logScales": [700.0, 700.0, 700.0],
            }],
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
        )

        self.assertTrue(is_target_scope_state(state))
        self.assertEqual(
            state["coreComponents"][0]["materialSummary"][
                "totalLogScaleVolume"
            ],
            2100.0,
        )


    def test_malformed_inputs_raise_target_scope_domain_errors(self) -> None:
        with self.assertRaises(TargetScopeStateValidationError):
            create_target_scope_component_policy({
                "schemaVersion": 1,
                "policyId": "target-scope-components/experimental-shadow-v1",
                "adjacencyScaleMultiplier": 10 ** 10000,
                "boundsScaleMultiplier": 1.0,
            })

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
        geometry = target_geometry([
            (1, (0.0, 0.0, 0.0)),
            (2, (3.0, 0.0, 0.0)),
            (3, (6.0, 0.0, 0.0)),
        ])
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
        )
        source = digest("6")
        revised = revise_target_scope_state(
            previous_state=revision_zero,
            target_geometry=geometry,
            request_binding=revision_zero["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[],
            rejected_frontier=[{
                "stableGaussianIds": [2],
                "state": "rejected",
                "provenanceDigests": [source],
            }],
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
        self.assertEqual(revised["discoveryEnvelopeLedger"], [])
        self.assertTrue(is_target_scope_state(revised))
        with self.assertRaisesRegex(
            TargetScopeStateTransitionError,
            "must explicitly reopen",
        ):
            revise_target_scope_state(
                previous_state=revised,
                target_geometry=geometry,
                request_binding=revised["requestBinding"],
                core_stable_gaussian_ids=[1],
                active_frontier=[{
                    "stableGaussianIds": [2],
                    "state": "new",
                    "provenanceDigests": [digest("7")],
                }],
                rejected_frontier=[],
                required_context_stable_gaussian_ids=[3],
                revision_provenance={
                    "kind": "scope-transition",
                    "reason": "invalid-rejection-bypass",
                    "sourceDigests": [digest("7")],
                },
            )

        reopened = revise_target_scope_state(
            previous_state=revised,
            target_geometry=geometry,
            request_binding=revised["requestBinding"],
            core_stable_gaussian_ids=[1],
            active_frontier=[{
                "stableGaussianIds": [2],
                "state": "reopened",
                "provenanceDigests": [digest("7")],
            }],
            rejected_frontier=[],
            required_context_stable_gaussian_ids=[3],
            revision_provenance={
                "kind": "scope-transition",
                "reason": "component-reopen-fixture",
                "sourceDigests": [digest("7")],
            },
        )
        self.assertEqual(reopened["rejectedFrontierStableGaussianIds"], [])
        self.assertEqual(reopened["activeFrontierStableGaussianIds"], [2])
        self.assertEqual(
            [event["event"] for event in reopened["rejectedFrontierLedger"]],
            ["rejected", "reopened"],
        )
        self.assertEqual(reopened["discoveryEnvelopeLedger"], [])
        self.assertTrue(is_target_scope_state(reopened))

        broken_history = deepcopy(reopened)
        reopened_event = broken_history["rejectedFrontierLedger"][-1]
        reopened_event["previousEventDigest"] = None
        event_payload = {
            key: value
            for key, value in reopened_event.items()
            if key != "eventDigest"
        }
        reopened_event["eventDigest"] = route_b_artifact_digest(event_payload)
        broken_payload = {
            key: value
            for key, value in broken_history.items()
            if key != "stateDigest"
        }
        broken_history["stateDigest"] = route_b_artifact_digest(broken_payload)
        self.assertFalse(is_target_scope_state(broken_history))

        invalid = deepcopy(revised)
        invalid["requiredContextStableGaussianIds"] = [2, 3]
        payload = {
            key: value
            for key, value in invalid.items()
            if key != "stateDigest"
        }
        invalid["stateDigest"] = route_b_artifact_digest(payload)
        self.assertFalse(is_target_scope_state(invalid))


if __name__ == "__main__":
    unittest.main()

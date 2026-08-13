from __future__ import annotations

from copy import deepcopy
import unittest

from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.reference_gaussian_evidence_aggregation import (
    ReferenceGaussianEvidenceAggregationError,
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
    is_reference_gaussian_evidence_aggregation_result,
    reference_aggregation_policy,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def dependency() -> dict[str, object]:
    return {
        "splatId": "editor-splat:1",
        "renderStateToken": "render-v1",
        "geometryToken": "geometry-v1",
        "gaussianIdentityToken": "gaussians-v1",
        "worldTransformToken": "transform-v1",
    }


def request_binding() -> dict[str, object]:
    return {
        "targetContextId": "ai-target-context-1",
        "contextRevision": 3,
        "dependencyToken": dependency(),
    }


def current_input(
    view_id: str,
    *,
    stable_ids: list[int] | None = None,
    participation: str = "included",
    stable_mask_digest: str | None = None,
    evidence_policy_digest: str | None = None,
    evidence_backend_id: str = "complete-contributor/reference-v1",
    target_geometry_hint_seed_digest: str | None = None,
) -> dict[str, object]:
    ids = stable_ids or [5, 9, 11, 13]
    camera_digest = digest("a" if view_id == "view-1" else "f")
    mask_digest = stable_mask_digest or digest(view_id[-1])
    working_set_input: dict[str, object] = {
        "targetSplatId": "editor-splat:1",
        "coreTargetStableIds": ids[:-1],
        "contextStableGaussianIds": ids[-1:],
    }
    if target_geometry_hint_seed_digest is not None:
        working_set_input["targetGeometryHintSeedDigest"] = (
            target_geometry_hint_seed_digest
        )
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": participation,
            "cameraBindingDigest": camera_digest,
            "rgbDigest": digest("b"),
            "stableMaskDigest": mask_digest,
        },
        "evidencePolicyDigest": evidence_policy_digest or digest("e"),
        "renderWorkingSet": {
            "targetSplatId": "editor-splat:1",
            "dependencyToken": dependency(),
            "cameraBindingDigest": camera_digest,
            "renderWorkingSetToken": digest("d"),
            "stableGaussianIds": sorted({*ids, 42}),
            "completeness": "complete",
        },
        "evidenceWorkingSet": create_evidence_working_set(working_set_input),
        "rasterImplementationId": "gsplat-reference-rgb/v1",
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": evidence_backend_id,
        "runtimeBuildId": "locked-runtime-build-1",
    }


def artifact(
    value: dict[str, object],
    *,
    positive: list[float],
    negative: list[float],
    visible: list[float],
) -> dict[str, object]:
    result = admit_gaussian_evidence(value)
    assert result["status"] == "admitted"
    return create_gaussian_evidence_artifact(
        result["admission"],
        {
            "positiveMass": positive,
            "negativeMass": negative,
            "visibleMass": visible,
        },
    )


def aggregation_input(
    views: list[dict[str, object]],
    *,
    classification_scope: list[int] | None = None,
) -> dict[str, object]:
    evidence_working_set = deepcopy(
        views[0]["currentInput"]["evidenceWorkingSet"]
    )
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "classificationUniverseStableGaussianIds": [5, 9, 11, 13, 42],
        "classificationScopeStableGaussianIds": (
            classification_scope
            if classification_scope is not None
            else list(evidence_working_set["stableGaussianIds"])
        ),
        "evidenceWorkingSet": evidence_working_set,
        "views": views,
    }


class ReferenceGaussianEvidenceAggregationTests(unittest.TestCase):
    def test_single_and_consistent_multiview_evidence_produce_four_distinct_classes(
        self,
    ) -> None:
        first_input = current_input("view-1")
        first_artifact = artifact(
            first_input,
            positive=[0.9, 0.05, 0.5, 0.0],
            negative=[0.05, 0.9, 0.5, 0.0],
            visible=[1.0, 1.0, 1.0, 0.0],
        )
        second_input = current_input("view-2")
        second_artifact = artifact(
            second_input,
            positive=[0.8, 0.0, 0.1, 0.0],
            negative=[0.0, 0.8, 0.1, 0.0],
            visible=[1.0, 1.0, 0.2, 0.0],
        )
        original_first = deepcopy(first_artifact)

        single = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [{"currentInput": first_input, "artifact": first_artifact}]
            ),
            default_reference_aggregation_policy(),
        )
        multi = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    {"currentInput": first_input, "artifact": first_artifact},
                    {"currentInput": second_input, "artifact": second_artifact},
                ]
            ),
            default_reference_aggregation_policy(),
        )

        expected_classes = {
            "selectedStableGaussianIds": [5],
            "rejectedStableGaussianIds": [9],
            "uncertainStableGaussianIds": [11, 13],
            "outOfScopeStableGaussianIds": [42],
        }
        for key, expected in expected_classes.items():
            self.assertEqual(single[key], expected)
            self.assertEqual(multi[key], expected)
        self.assertEqual(multi["candidateInputStableGaussianIds"], [5])
        self.assertEqual(
            [source["artifactDigest"] for source in multi["sourceEvidenceArtifacts"]],
            [first_artifact["artifactDigest"], second_artifact["artifactDigest"]],
        )
        self.assertEqual(first_artifact, original_first)

    def test_per_view_cap_exposes_and_limits_close_view_dominance(self) -> None:
        close_input = current_input("view-1", stable_ids=[5])
        close_artifact = artifact(
            close_input,
            positive=[100.0],
            negative=[0.0],
            visible=[100.0],
        )
        context_input = current_input("view-2", stable_ids=[5])
        context_artifact = artifact(
            context_input,
            positive=[0.0],
            negative=[1.0],
            visible=[1.0],
        )
        value = aggregation_input(
            [
                {"currentInput": close_input, "artifact": close_artifact},
                {"currentInput": context_input, "artifact": context_artifact},
            ]
        )

        raw = aggregate_reference_gaussian_evidence(
            value,
            reference_aggregation_policy(aggregation_mode="raw-mass-sum/v1"),
        )
        capped = aggregate_reference_gaussian_evidence(
            value,
            default_reference_aggregation_policy(),
        )

        raw_record = raw["gaussians"][0]
        capped_record = capped["gaussians"][0]
        self.assertEqual(raw_record["effectivePositiveMass"], 100.0)
        self.assertEqual(raw_record["effectiveNegativeMass"], 1.0)
        self.assertEqual(capped_record["effectivePositiveMass"], 1.0)
        self.assertEqual(capped_record["effectiveNegativeMass"], 1.0)
        self.assertEqual(capped_record["perView"][0]["normalizationScale"], 0.01)
        self.assertEqual(
            capped["aggregationPolicy"]["normalizationMode"],
            "scale-pnv-by-visible-cap/v1",
        )
        self.assertNotEqual(raw["resultDigest"], capped["resultDigest"])

    def test_mixed_conflicting_and_insufficient_support_remain_uncertain(self) -> None:
        first_input = current_input("view-1", stable_ids=[5, 9, 11])
        first_artifact = artifact(
            first_input,
            positive=[0.7, 0.9, 0.05],
            negative=[0.3, 0.0, 0.0],
            visible=[1.0, 1.0, 0.05],
        )
        second_input = current_input("view-2", stable_ids=[5, 9, 11])
        second_artifact = artifact(
            second_input,
            positive=[0.0, 0.0, 0.0],
            negative=[0.0, 0.9, 0.0],
            visible=[0.0, 1.0, 0.0],
        )

        result = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    {"currentInput": first_input, "artifact": first_artifact},
                    {"currentInput": second_input, "artifact": second_artifact},
                ]
            ),
            default_reference_aggregation_policy(),
        )

        records = {
            record["stableGaussianId"]: record for record in result["gaussians"]
        }
        self.assertEqual(records[5]["uncertaintyReason"], "mixed-positive-negative")
        self.assertEqual(records[9]["uncertaintyReason"], "conflicting-views")
        self.assertEqual(
            records[11]["uncertaintyReason"], "unobserved-or-insufficient"
        )
        self.assertEqual(result["uncertainStableGaussianIds"], [5, 9, 11])
        self.assertNotIn(11, result["rejectedStableGaussianIds"])

    def test_exclude_reinclude_and_stable_mask_replacement_use_exact_current_inputs(
        self,
    ) -> None:
        first_input = current_input("view-1", stable_ids=[5])
        first_artifact = artifact(
            first_input,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )
        second_input = current_input("view-2", stable_ids=[5])
        second_artifact = artifact(
            second_input,
            positive=[0.0],
            negative=[1.0],
            visible=[1.0],
        )
        included_views = [
            {"currentInput": first_input, "artifact": first_artifact},
            {"currentInput": second_input, "artifact": second_artifact},
        ]

        included = aggregate_reference_gaussian_evidence(
            aggregation_input(included_views),
            default_reference_aggregation_policy(),
        )
        excluded = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    included_views[0],
                    {
                        "currentInput": current_input(
                            "view-2",
                            stable_ids=[5],
                            participation="excluded",
                        )
                    },
                ]
            ),
            default_reference_aggregation_policy(),
        )
        reincluded = aggregate_reference_gaussian_evidence(
            aggregation_input(list(reversed(included_views))),
            default_reference_aggregation_policy(),
        )

        self.assertEqual(included["uncertainStableGaussianIds"], [5])
        self.assertEqual(excluded["selectedStableGaussianIds"], [5])
        self.assertNotEqual(included["resultDigest"], excluded["resultDigest"])
        self.assertEqual(reincluded["resultDigest"], included["resultDigest"])
        replacement_input = current_input(
            "view-2", stable_ids=[5], stable_mask_digest=digest("3")
        )
        with self.assertRaisesRegex(ValueError, "current compatible Evidence"):
            aggregate_reference_gaussian_evidence(
                aggregation_input(
                    [
                        included_views[0],
                        {
                            "currentInput": replacement_input,
                            "artifact": second_artifact,
                        },
                    ]
                ),
                default_reference_aggregation_policy(),
            )

    def test_result_binds_policy_artifact_set_target_dependency_and_backends(
        self,
    ) -> None:
        value = current_input("view-1", stable_ids=[5, 42])
        source = artifact(
            value,
            positive=[1.0, 0.8],
            negative=[0.0, 0.0],
            visible=[1.0, 0.8],
        )

        result = aggregate_reference_gaussian_evidence(
            aggregation_input([{"currentInput": value, "artifact": source}]),
            default_reference_aggregation_policy(),
        )

        self.assertEqual(result["selectedStableGaussianIds"], [5, 42])
        self.assertEqual(
            result["evidenceArtifactSet"],
            [{"viewId": "view-1", "artifactDigest": source["artifactDigest"]}],
        )
        self.assertEqual(
            result["referenceBackendIdentities"],
            [
                {
                    "rasterImplementationId": "gsplat-reference-rgb/v1",
                    "evidenceBackendKind": "reference-contributor",
                    "evidenceBackendId": "complete-contributor/reference-v1",
                    "runtimeBuildId": "locked-runtime-build-1",
                }
            ],
        )
        self.assertTrue(is_reference_gaussian_evidence_aggregation_result(result))
        changed = deepcopy(result)
        changed["selectedStableGaussianIds"] = []
        self.assertFalse(is_reference_gaussian_evidence_aggregation_result(changed))
        forged = deepcopy(result)
        forged["gaussians"][0]["rawPositiveMass"] = "not-a-number"
        forged_payload = {
            key: item for key, item in forged.items() if key != "resultDigest"
        }
        forged["resultDigest"] = canonical_json_digest(forged_payload)
        self.assertFalse(is_reference_gaussian_evidence_aggregation_result(forged))

    def test_later_view_evidence_can_select_ids_absent_from_anchor_geometry(self) -> None:
        expanded_input = current_input("view-2", stable_ids=[42])
        expanded_artifact = artifact(
            expanded_input,
            positive=[0.8],
            negative=[0.0],
            visible=[0.8],
        )

        result = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    {
                        "currentInput": expanded_input,
                        "artifact": expanded_artifact,
                    }
                ]
            ),
            default_reference_aggregation_policy(),
        )

        self.assertEqual(result["selectedStableGaussianIds"], [42])
        self.assertNotIn("targetGeometryHintDigest", result)

    def test_geometry_seed_alone_cannot_make_unwritten_ids_out_of_scope(self) -> None:
        seeded_input = current_input(
            "view-1",
            stable_ids=[5],
            target_geometry_hint_seed_digest=digest("6"),
        )
        seeded_artifact = artifact(
            seeded_input,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )

        result = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    {
                        "currentInput": seeded_input,
                        "artifact": seeded_artifact,
                    }
                ],
                classification_scope=[5, 9, 11, 13, 42],
            ),
            default_reference_aggregation_policy(),
        )

        self.assertEqual(result["selectedStableGaussianIds"], [5])
        self.assertEqual(result["uncertainStableGaussianIds"], [9, 11, 13, 42])
        self.assertEqual(result["outOfScopeStableGaussianIds"], [])

        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceAggregationError,
            "TargetGeometryHint-seeded Evidence cannot narrow",
        ):
            aggregate_reference_gaussian_evidence(
                aggregation_input(
                    [
                        {
                            "currentInput": seeded_input,
                            "artifact": seeded_artifact,
                        }
                    ],
                    classification_scope=[5],
                ),
                default_reference_aggregation_policy(),
            )

    def test_missing_or_non_finite_aggregate_evidence_fails_without_a_result(
        self,
    ) -> None:
        first_input = current_input("view-1", stable_ids=[5])
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceAggregationError,
            "missing current compatible Evidence",
        ):
            aggregate_reference_gaussian_evidence(
                aggregation_input([{"currentInput": first_input}]),
                default_reference_aggregation_policy(),
            )

        second_input = current_input("view-2", stable_ids=[5])
        first_artifact = artifact(
            first_input,
            positive=[1e308],
            negative=[0.0],
            visible=[1e308],
        )
        second_artifact = artifact(
            second_input,
            positive=[1e308],
            negative=[0.0],
            visible=[1e308],
        )
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceAggregationError,
            "finite",
        ):
            aggregate_reference_gaussian_evidence(
                aggregation_input(
                    [
                        {"currentInput": first_input, "artifact": first_artifact},
                        {
                            "currentInput": second_input,
                            "artifact": second_artifact,
                        },
                    ]
                ),
                reference_aggregation_policy(
                    aggregation_mode="raw-mass-sum/v1"
                ),
            )

    def test_policy_threshold_changes_require_a_new_versioned_policy(self) -> None:
        changed = default_reference_aggregation_policy()
        changed["minimumAggregateVisibleMass"] = 0.2
        payload = {
            key: item
            for key, item in changed.items()
            if key != "aggregationPolicyDigest"
        }
        changed["aggregationPolicyDigest"] = canonical_json_digest(payload)
        value = current_input("view-1", stable_ids=[5])
        source = artifact(
            value,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )

        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceAggregationError,
            "identity or thresholds",
        ):
            aggregate_reference_gaussian_evidence(
                aggregation_input([{"currentInput": value, "artifact": source}]),
                changed,
            )

    def test_excluded_only_scope_is_unobserved_not_negative_or_out_of_scope(
        self,
    ) -> None:
        included_input = current_input("view-1", stable_ids=[5, 9])
        included_artifact = artifact(
            included_input,
            positive=[1.0, 0.0],
            negative=[0.0, 0.0],
            visible=[1.0, 0.0],
        )
        excluded_input = current_input(
            "view-2", stable_ids=[5, 9], participation="excluded"
        )

        result = aggregate_reference_gaussian_evidence(
            aggregation_input(
                [
                    {
                        "currentInput": included_input,
                        "artifact": included_artifact,
                    },
                    {"currentInput": excluded_input},
                ]
            ),
            default_reference_aggregation_policy(),
        )

        self.assertIn(9, result["uncertainStableGaussianIds"])
        self.assertNotIn(9, result["rejectedStableGaussianIds"])
        self.assertNotIn(9, result["outOfScopeStableGaussianIds"])

    def test_included_artifacts_must_share_evidence_and_backend_identity(self) -> None:
        first_input = current_input("view-1", stable_ids=[5])
        first_artifact = artifact(
            first_input,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )
        changed_policy_input = current_input(
            "view-2", stable_ids=[5], evidence_policy_digest=digest("7")
        )
        changed_policy_artifact = artifact(
            changed_policy_input,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )
        changed_backend_input = current_input(
            "view-2", stable_ids=[5], evidence_backend_id="autograd/reference-v1"
        )
        changed_backend_artifact = artifact(
            changed_backend_input,
            positive=[1.0],
            negative=[0.0],
            visible=[1.0],
        )

        for incompatible_input, incompatible_artifact in (
            (changed_policy_input, changed_policy_artifact),
            (changed_backend_input, changed_backend_artifact),
        ):
            with self.assertRaisesRegex(
                ReferenceGaussianEvidenceAggregationError,
                "incompatible source identities",
            ):
                aggregate_reference_gaussian_evidence(
                    aggregation_input(
                        [
                            {
                                "currentInput": first_input,
                                "artifact": first_artifact,
                            },
                            {
                                "currentInput": incompatible_input,
                                "artifact": incompatible_artifact,
                            },
                        ]
                    ),
                    default_reference_aggregation_policy(),
                )


if __name__ == "__main__":
    unittest.main()

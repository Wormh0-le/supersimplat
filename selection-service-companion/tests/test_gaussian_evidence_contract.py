from __future__ import annotations

import json
from pathlib import Path
import unittest

from selection_service_companion.gaussian_evidence_contract import (
    GaussianEvidenceContractError,
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
    expand_evidence_working_set,
    gaussian_evidence_artifact_matches_admission,
    is_current_gaussian_evidence_artifact,
    is_gaussian_evidence_artifact,
    resolve_evidence_working_set_boundary,
)


CONTRACT_VECTORS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / 'test/fixtures/ai-select-gaussian-evidence-contract-vectors.json'
    ).read_text(encoding='utf-8')
)


def digest(letter: str) -> str:
    return f'sha256:{letter * 64}'


def dependency(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'splatId': 'editor-splat:1',
        'renderStateToken': 'render-v1',
        'geometryToken': 'geometry-v1',
        'gaussianIdentityToken': 'gaussians-v1',
        'worldTransformToken': 'transform-v1',
        **(overrides or {}),
    }


def request_binding(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'targetContextId': 'ai-target-context-1',
        'contextRevision': 3,
        'dependencyToken': dependency(),
        **(overrides or {}),
    }


def view(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'viewId': 'view-1',
        'renderStatus': 'ready',
        'participation': 'included',
        'cameraBindingDigest': digest('a'),
        'rgbDigest': digest('b'),
        'stableMaskDigest': digest('c'),
        **(overrides or {}),
    }


def render_working_set(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'targetSplatId': 'editor-splat:1',
        'dependencyToken': dependency(),
        'cameraBindingDigest': digest('a'),
        'renderWorkingSetToken': digest('d'),
        'stableGaussianIds': [5, 9, 42],
        'completeness': 'complete',
        **(overrides or {}),
    }


def evidence_working_set(
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    return create_evidence_working_set({
        'targetSplatId': 'editor-splat:1',
        'coreTargetStableIds': [5],
        'contextStableGaussianIds': [9],
        **(overrides or {}),
    })


def admission_input(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'requestBinding': request_binding(),
        'targetSplatId': 'editor-splat:1',
        'view': view(),
        'evidencePolicyDigest': digest('e'),
        'renderWorkingSet': render_working_set(),
        'evidenceWorkingSet': evidence_working_set(),
        'rasterImplementationId': 'gsplat-reference-rgb/v1',
        'evidenceBackendKind': 'reference-contributor',
        'evidenceBackendId': 'complete-contributor/reference-v1',
        'runtimeBuildId': 'locked-runtime-build-1',
        **(overrides or {}),
    }


def admitted(value: dict[str, object] | None = None) -> dict[str, object]:
    result = admit_gaussian_evidence(value or admission_input())
    assert result['status'] == 'admitted'
    return result['admission']


def masses(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return {
        'positiveMass': [0.5, 0.0],
        'negativeMass': [0.0, 0.25],
        'visibleMass': [0.5, 0.25],
        **(overrides or {}),
    }


class GaussianEvidenceContractTests(unittest.TestCase):
    def test_admits_only_the_current_included_stable_view(self) -> None:
        current = admitted()

        self.assertEqual(current['viewId'], 'view-1')
        self.assertEqual(current['stableGaussianIds'], [5, 9])
        self.assertEqual(current['stableMaskDigest'], digest('c'))

    def test_shared_browser_and_companion_vector_has_matching_digests(self) -> None:
        vector_input = {
            **CONTRACT_VECTORS['admissionInput'],
            'evidenceWorkingSet': CONTRACT_VECTORS['evidenceWorkingSet'],
        }
        result = admit_gaussian_evidence(vector_input)

        self.assertEqual(result['status'], 'admitted')
        current = result['admission']
        self.assertEqual(current['stableGaussianIds'], [2, 5, 9])
        self.assertEqual(
            current['evidenceWorkingSetToken'],
            CONTRACT_VECTORS['evidenceWorkingSet']['evidenceWorkingSetToken'],
        )
        artifact = create_gaussian_evidence_artifact(current, {
            'positiveMass': CONTRACT_VECTORS['artifact']['positiveMass'],
            'negativeMass': CONTRACT_VECTORS['artifact']['negativeMass'],
            'visibleMass': CONTRACT_VECTORS['artifact']['visibleMass'],
            'boundaryMass': CONTRACT_VECTORS['artifact']['boundaryMass'],
        })
        self.assertEqual(artifact, CONTRACT_VECTORS['artifact'])

    def test_excluded_and_no_stable_mask_fail_closed_before_computation(self) -> None:
        self.assertEqual(
            admit_gaussian_evidence(admission_input({
                'view': view({'participation': 'excluded'}),
            })),
            {'status': 'rejected', 'reason': 'view-excluded'},
        )
        self.assertEqual(
            admit_gaussian_evidence(admission_input({
                'view': {
                    key: value
                    for key, value in view().items()
                    if key != 'stableMaskDigest'
                },
            })),
            {'status': 'rejected', 'reason': 'stable-mask-unavailable'},
        )

    def test_spatial_direct_admits_target_evidence_ids_absent_from_render_set(
        self,
    ) -> None:
        expanded = evidence_working_set({
            'contextStableGaussianIds': [99],
        })
        direct = admission_input({
            'evidenceWorkingSet': expanded,
            'evidenceBackendKind': 'production-direct',
            'evidenceBackendId': 'global-atomic/direct-v1',
        })

        result = admit_gaussian_evidence(direct)

        self.assertEqual(result['status'], 'admitted')
        self.assertEqual(result['admission']['stableGaussianIds'], [5, 99])

    def test_out_of_scope_occluders_stay_in_render_without_pnv_writes(self) -> None:
        current = admitted()
        artifact = create_gaussian_evidence_artifact(current, masses())

        self.assertEqual(artifact['stableGaussianIds'], [5, 9])
        self.assertNotIn(42, artifact['stableGaussianIds'])
        self.assertTrue(is_gaussian_evidence_artifact(artifact))
        self.assertTrue(gaussian_evidence_artifact_matches_admission(artifact, current))
        self.assertNotIn('viewSource', artifact)
        self.assertNotIn('promptArtifactDigest', artifact)

    def test_target_geometry_seed_expands_only_from_an_included_stable_view(self) -> None:
        seeded = evidence_working_set({
            'targetGeometryHintSeedDigest': digest('f'),
        })
        expanded = expand_evidence_working_set(seeded, {
            'sourceView': {
                'viewId': 'later-view',
                'renderStatus': 'ready',
                'participation': 'included',
                'stableMaskDigest': digest('1'),
            },
            'coreTargetStableIds': [42],
            'contextStableGaussianIds': [],
        })

        self.assertEqual(expanded['stableGaussianIds'], [5, 9, 42])
        self.assertNotEqual(
            expanded['evidenceWorkingSetToken'],
            seeded['evidenceWorkingSetToken'],
        )
        with self.assertRaisesRegex(GaussianEvidenceContractError, 'Included Stable View'):
            expand_evidence_working_set(seeded, {
                'sourceView': {
                    'viewId': 'excluded-view',
                    'renderStatus': 'ready',
                    'participation': 'excluded',
                    'stableMaskDigest': digest('2'),
                },
                'coreTargetStableIds': [42],
                'contextStableGaussianIds': [],
            })

    def test_boundary_contact_requires_expansion_or_fails_closed(self) -> None:
        current = evidence_working_set()
        failed = resolve_evidence_working_set_boundary({
            'renderWorkingSet': render_working_set(),
            'evidenceWorkingSet': current,
            'boundaryStableGaussianIds': [42],
            'resolution': 'fail-closed',
        })
        self.assertEqual(failed, {
            'status': 'failed-closed',
            'reason': 'evidence-working-set-boundary-contact',
            'contactStableGaussianIds': [42],
        })

        expanded = resolve_evidence_working_set_boundary({
            'renderWorkingSet': render_working_set(),
            'evidenceWorkingSet': current,
            'boundaryStableGaussianIds': [42],
            'resolution': 'expand',
            'expansion': {
                'sourceView': {
                    'viewId': 'later-view',
                    'renderStatus': 'ready',
                    'participation': 'included',
                    'stableMaskDigest': digest('1'),
                },
                'coreTargetStableIds': [42],
                'contextStableGaussianIds': [],
            },
        })
        self.assertEqual(expanded['status'], 'expanded')
        self.assertEqual(
            expanded['evidenceWorkingSet']['stableGaussianIds'], [5, 9, 42]
        )

    def test_every_material_identity_change_invalidates_reference_evidence(self) -> None:
        original = admission_input()
        artifact = create_gaussian_evidence_artifact(admitted(original), masses())
        self.assertTrue(is_current_gaussian_evidence_artifact(artifact, original))

        changed = admission_input({
            'runtimeBuildId': 'locked-runtime-build-2',
        })
        self.assertFalse(is_current_gaussian_evidence_artifact(artifact, changed))
        changed_mask = admission_input({
            'view': view({'stableMaskDigest': digest('3')}),
        })
        self.assertFalse(
            is_current_gaussian_evidence_artifact(artifact, changed_mask)
        )

    def test_reference_and_production_direct_artifacts_are_admitted_but_cannot_collide(self) -> None:
        reference_admission = admitted()
        production_admission = admitted(admission_input({
            'rasterImplementationId': 'supersimplat-direct-evidence/v1',
            'evidenceBackendKind': 'production-direct',
            'evidenceBackendId': 'global-atomic/direct-v1',
            'runtimeBuildId': 'direct-runtime-build-1',
        }))
        reference_artifact = create_gaussian_evidence_artifact(
            reference_admission, masses()
        )
        production_artifact = create_gaussian_evidence_artifact(
            production_admission, masses()
        )

        self.assertTrue(is_gaussian_evidence_artifact(reference_artifact))
        self.assertTrue(is_gaussian_evidence_artifact(production_artifact))
        self.assertNotEqual(
            reference_artifact['artifactDigest'],
            production_artifact['artifactDigest'],
        )
        self.assertFalse(
            gaussian_evidence_artifact_matches_admission(
                reference_artifact, production_admission
            )
        )

    def test_contract_rejects_partial_artifacts(self) -> None:
        artifact = create_gaussian_evidence_artifact(admitted(), masses())
        with self.assertRaisesRegex(
            GaussianEvidenceContractError,
            'complete finite non-negative P/N/V arrays',
        ):
            create_gaussian_evidence_artifact(admitted(), {
                'positiveMass': [0.5, 0.0],
                'negativeMass': [0.0, 0.25],
            })
        with self.assertRaisesRegex(
            GaussianEvidenceContractError,
            'complete finite non-negative P/N/V arrays',
        ):
            create_gaussian_evidence_artifact(admitted(), masses({
                'positiveMass': [10 ** 10000, 0.0],
            }))
        with self.assertRaisesRegex(
            GaussianEvidenceContractError,
            'complete finite non-negative P/N/V arrays',
        ):
            create_gaussian_evidence_artifact(admitted(), masses({
                'positiveMass': [float('inf'), 0.0],
            }))
        self.assertFalse(is_gaussian_evidence_artifact({
            **artifact,
            'visibleMass': [0.5],
        }))


if __name__ == '__main__':
    unittest.main()

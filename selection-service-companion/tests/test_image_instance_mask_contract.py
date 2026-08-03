from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import unittest

from selection_service_companion.image_instance_mask_contract import (
    create_companion_rgb_artifact_ref,
    create_image_instance_prompt_artifact,
    create_image_instance_mask_result,
    create_previous_prediction_logits_ref,
    image_instance_mask_request_identity_digest,
    is_image_instance_mask_request,
    is_image_instance_prompt_artifact,
    is_image_instance_rgb_input,
    is_previous_prediction_logits_ref,
    is_image_instance_mask_result,
    image_instance_mask_result_matches_request,
    previous_logits_ref_matches_image_instance_mask_request,
    resolve_previous_logits_ref_for_image_instance_mask_request,
    resolve_image_instance_rgb_input,
)


def digest(letter: str) -> str:
    return f'sha256:{letter * 64}'


PNG_BASE64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAE'
    'AAH2FzhVAAAAAElFTkSuQmCC'
)
PNG_BYTES = base64.b64decode(PNG_BASE64)
RGB_DIGEST = f'sha256:{hashlib.sha256(PNG_BYTES).hexdigest()}'
CONTRACT_VECTORS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / 'test/fixtures/ai-select-image-instance-mask-contract-vectors.json'
    ).read_text(encoding='utf-8')
)


class ImageInstanceMaskContractTests(unittest.TestCase):
    def test_prompt_artifact_matches_the_browser_canonical_golden_vector(self) -> None:
        artifact = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': 'target-1',
            'contextRevision': 4,
            'viewId': 'view-1',
            'rgbDigest': digest('a'),
            'cameraBindingDigest': digest('b'),
            'adapterCapabilityDigest': digest('c'),
            'positivePoints': [{'xPx': 2, 'yPx': 3}],
            'negativePoints': [],
            'positiveBox': {'x0Px': 1, 'y0Px': 1, 'x1Px': 6, 'y1Px': 5},
            'multimaskOutput': False,
        })

        self.assertTrue(is_image_instance_prompt_artifact(artifact))
        self.assertEqual(
            artifact['artifactDigest'],
            'sha256:c86a598d516d70eacc12049d4cadd5dfacd8ff5adae8de9bb76f6d2223d87b7d',
        )

    def test_shared_golden_vectors_distinguish_stale_and_replaced_identities(self) -> None:
        prompt = CONTRACT_VECTORS['prompt']
        prompt_input = {
            key: value for key, value in prompt.items() if key != 'artifactDigest'
        }
        reference = CONTRACT_VECTORS['previousLogitsRef']
        reference_input = {
            key: value for key, value in reference.items() if key != 'refDigest'
        }

        self.assertTrue(is_image_instance_prompt_artifact(prompt))
        self.assertEqual(
            create_image_instance_prompt_artifact(prompt_input)['artifactDigest'],
            prompt['artifactDigest'],
        )
        unicode_prompt = CONTRACT_VECTORS['unicodePrompt']
        unicode_prompt_input = {
            key: value
            for key, value in unicode_prompt.items()
            if key != 'artifactDigest'
        }
        self.assertTrue(is_image_instance_prompt_artifact(unicode_prompt))
        self.assertEqual(
            create_image_instance_prompt_artifact(unicode_prompt_input)['artifactDigest'],
            unicode_prompt['artifactDigest'],
        )
        self.assertEqual(
            image_instance_mask_request_identity_digest(CONTRACT_VECTORS['identity']),
            CONTRACT_VECTORS['identityDigest'],
        )
        self.assertEqual(
            image_instance_mask_request_identity_digest(
                CONTRACT_VECTORS['staleIdentity']
            ),
            CONTRACT_VECTORS['staleIdentityDigest'],
        )
        self.assertEqual(
            image_instance_mask_request_identity_digest(
                CONTRACT_VECTORS['replacementIdentity']
            ),
            CONTRACT_VECTORS['replacementIdentityDigest'],
        )
        self.assertTrue(is_previous_prediction_logits_ref(reference))
        self.assertEqual(
            create_previous_prediction_logits_ref(reference_input)['refDigest'],
            reference['refDigest'],
        )
        result = CONTRACT_VECTORS['result']
        result_input = {
            key: value for key, value in result.items() if key != 'resultDigest'
        }
        self.assertTrue(is_image_instance_mask_result(result))
        self.assertEqual(
            create_image_instance_mask_result(result_input)['resultDigest'],
            result['resultDigest'],
        )

    def test_shared_numeric_bounds_reject_browser_unrepresentable_values(self) -> None:
        prompt = CONTRACT_VECTORS['unicodePrompt']
        prompt_input = {
            key: value for key, value in prompt.items() if key != 'artifactDigest'
        }
        boundaries = CONTRACT_VECTORS['numericBoundaries']

        self.assertTrue(is_image_instance_prompt_artifact(
            create_image_instance_prompt_artifact({
                **prompt_input,
                'contextRevision': boundaries['largestSafeInteger'],
            })
        ))
        with self.assertRaises(ValueError):
            create_image_instance_prompt_artifact({
                **prompt_input,
                'contextRevision': boundaries['firstUnsafeInteger'],
            })
        with self.assertRaises(ValueError):
            create_image_instance_prompt_artifact({
                **prompt_input,
                'targetContextId': CONTRACT_VECTORS['invalidStrings']['loneHighSurrogate'],
            })

    def request(self, overrides: dict[str, object] | None = None) -> dict[str, object]:
        identity: dict[str, object] = {
            'targetContextId': 'target-1',
            'contextRevision': 4,
            'viewId': 'view-1',
            'rgbDigest': RGB_DIGEST,
            'promptArtifactDigest': digest('d'),
            'adapterId': 'sam3-image-instance/v1',
            'modelManifestDigest': 'sam3-image-manifest-v1',
            'runtimeDigest': digest('e'),
            'companionInstanceId': 'companion-1',
            'inferenceAttemptId': 'attempt-1',
        }
        prompt = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': identity['targetContextId'],
            'contextRevision': identity['contextRevision'],
            'viewId': identity['viewId'],
            'rgbDigest': identity['rgbDigest'],
            'cameraBindingDigest': digest('b'),
            'adapterCapabilityDigest': digest('c'),
            'positivePoints': [{'xPx': 0, 'yPx': 0}],
            'negativePoints': [],
            'multimaskOutput': True,
        })
        request: dict[str, object] = {
            'schemaVersion': 1,
            'identity': {
                **identity,
                'promptArtifactDigest': prompt['artifactDigest'],
            },
            'rgb': {
                'rgbDigest': RGB_DIGEST,
                'width': 1,
                'height': 1,
                'artifact': {
                    'pngBase64': PNG_BASE64,
                    'digest': RGB_DIGEST,
                    'width': 1,
                    'height': 1,
                },
            },
            'prompt': prompt,
        }
        return {**request, **(overrides or {})}

    def test_request_requires_exact_rgb_payload_or_current_companion_reference(self) -> None:
        artifact_request = self.request()
        self.assertTrue(is_image_instance_mask_request(artifact_request))

        companion_request = self.request({
            'rgb': {
                'rgbDigest': RGB_DIGEST,
                'width': 1,
                'height': 1,
                'companionRgbRef': create_companion_rgb_artifact_ref({
                    'schemaVersion': 1,
                    'companionInstanceId': 'companion-1',
                    'stateId': 'rgb-state-1',
                    'rgbDigest': RGB_DIGEST,
                    'width': 1,
                    'height': 1,
                }),
            },
        })
        self.assertTrue(is_image_instance_mask_request(companion_request))
        self.assertEqual(
            resolve_image_instance_rgb_input(
                companion_request['rgb'], lambda reference: PNG_BYTES
            ),
            PNG_BYTES,
        )

        digest_only = self.request({
            'rgb': {'rgbDigest': RGB_DIGEST, 'width': 1, 'height': 1},
        })
        mismatched = self.request({
            'rgb': {
                **artifact_request['rgb'],
                'artifact': {**artifact_request['rgb']['artifact'], 'width': 2},
            },
        })
        self.assertFalse(is_image_instance_mask_request(digest_only))
        self.assertFalse(is_image_instance_mask_request(mismatched))
        self.assertFalse(is_image_instance_rgb_input({
            'rgbDigest': CONTRACT_VECTORS['invalidRgb']['missingImageDataDigest'],
            'width': 1,
            'height': 1,
            'artifact': {
                'pngBase64': CONTRACT_VECTORS['invalidRgb']['missingImageDataPngBase64'],
                'digest': CONTRACT_VECTORS['invalidRgb']['missingImageDataDigest'],
                'width': 1,
                'height': 1,
            },
        }))

    def test_positive_box_without_a_point_is_a_valid_single_mask_seed(self) -> None:
        request = self.request()
        identity = request['identity']
        box_only_prompt = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': identity['targetContextId'],
            'contextRevision': identity['contextRevision'],
            'viewId': identity['viewId'],
            'rgbDigest': identity['rgbDigest'],
            'cameraBindingDigest': digest('b'),
            'adapterCapabilityDigest': digest('c'),
            'positivePoints': [],
            'negativePoints': [],
            'positiveBox': {'x0Px': 0, 'y0Px': 0, 'x1Px': 1, 'y1Px': 1},
            'multimaskOutput': False,
        })
        negative_only_prompt = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': identity['targetContextId'],
            'contextRevision': identity['contextRevision'],
            'viewId': identity['viewId'],
            'rgbDigest': identity['rgbDigest'],
            'cameraBindingDigest': digest('b'),
            'adapterCapabilityDigest': digest('c'),
            'positivePoints': [],
            'negativePoints': [{'xPx': 0, 'yPx': 0}],
            'multimaskOutput': False,
        })

        def request_for(prompt: dict[str, object]) -> dict[str, object]:
            return {
                **request,
                'identity': {
                    **identity,
                    'promptArtifactDigest': prompt['artifactDigest'],
                },
                'prompt': prompt,
            }

        self.assertTrue(is_image_instance_mask_request(request_for(box_only_prompt)))
        self.assertFalse(
            is_image_instance_mask_request(request_for(negative_only_prompt))
        )

    @staticmethod
    def mask_artifact() -> dict[str, object]:
        bits = b'\x01'
        return {
            'encoding': 'bitset-lsb-v1',
            'width': 1,
            'height': 1,
            'data': base64.b64encode(bits).decode('ascii'),
            'digest': f'sha256:{hashlib.sha256(bits).hexdigest()}',
        }

    @staticmethod
    def previous_logits_ref(identity: dict[str, object]) -> dict[str, object]:
        from selection_service_companion.image_instance_mask_contract import (
            create_previous_prediction_logits_ref,
        )

        return create_previous_prediction_logits_ref({
            'schemaVersion': 1,
            'companionInstanceId': identity['companionInstanceId'],
            'stateId': 'logits-state-1',
            'targetContextId': identity['targetContextId'],
            'viewId': identity['viewId'],
            'rgbDigest': identity['rgbDigest'],
            'sourceInferenceAttemptId': 'source-attempt-1',
            'sourceCandidateId': 'source-candidate-1',
            'adapterRuntimeDigest': identity['runtimeDigest'],
            'shape': [1, 288, 288],
            'dtype': 'float32',
            'dataDigest': digest('f'),
        })

    def test_result_and_opaque_refs_are_identity_and_cardinality_bound(self) -> None:
        request = self.request()
        identity = request['identity']
        result = create_image_instance_mask_result({
            'schemaVersion': 1,
            'requestIdentity': identity,
            'masks': [self.mask_artifact()],
            'modelScores': [0.75],
            'previousLogitsRefs': [self.previous_logits_ref(identity)],
            'diagnostics': {'outcome': 'available'},
        })
        self.assertTrue(is_image_instance_mask_result(result))
        self.assertTrue(image_instance_mask_result_matches_request(result, request))

        unavailable = create_image_instance_mask_result({
            'schemaVersion': 1,
            'requestIdentity': identity,
            'masks': [],
            'modelScores': [],
            'diagnostics': {'outcome': 'unavailable'},
        })
        self.assertTrue(image_instance_mask_result_matches_request(unavailable, request))

        ref = self.previous_logits_ref(identity)
        refinement_prompt = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': identity['targetContextId'],
            'contextRevision': identity['contextRevision'],
            'viewId': identity['viewId'],
            'rgbDigest': identity['rgbDigest'],
            'cameraBindingDigest': digest('b'),
            'adapterCapabilityDigest': digest('c'),
            'positivePoints': [{'xPx': 0, 'yPx': 0}],
            'negativePoints': [],
            'previousLogitsRefDigest': ref['refDigest'],
            'multimaskOutput': False,
        })
        refinement_request = {
            **request,
            'identity': {
                **identity,
                'promptArtifactDigest': refinement_prompt['artifactDigest'],
            },
            'prompt': refinement_prompt,
        }
        self.assertTrue(
            previous_logits_ref_matches_image_instance_mask_request(
                ref, refinement_request
            )
        )
        self.assertEqual(
            resolve_previous_logits_ref_for_image_instance_mask_request(
                refinement_request,
                'companion-1',
                lambda ref_digest: ref if ref_digest == ref['refDigest'] else None,
            ),
            ref,
        )
        self.assertIsNone(
            resolve_previous_logits_ref_for_image_instance_mask_request(
                refinement_request,
                'companion-1',
                lambda ref_digest: None,
            )
        )
        stale_resolver_called = False

        def stale_resolver(ref_digest: str) -> dict[str, object]:
            nonlocal stale_resolver_called
            stale_resolver_called = True
            return ref

        with self.assertRaises(ValueError):
            resolve_previous_logits_ref_for_image_instance_mask_request(
                refinement_request,
                'companion-2',
                stale_resolver,
            )
        self.assertFalse(stale_resolver_called)
        self.assertFalse(
            previous_logits_ref_matches_image_instance_mask_request(
                ref,
                {
                    **refinement_request,
                    'identity': {
                        **refinement_request['identity'],
                        'companionInstanceId': 'companion-2',
                    },
                },
            )
        )


if __name__ == '__main__':
    unittest.main()

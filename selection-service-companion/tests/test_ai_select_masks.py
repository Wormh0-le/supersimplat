from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
from typing import Any
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from selection_service_companion.masking import (
    MaskProduction,
    MaskSessionError,
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3ImageInstanceAdapter,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import (
    CompanionState,
    _proposal_identity_digest,
)


EDITOR_ORIGIN = 'https://editor.example'
ADAPTER_ID = 'sam3-image-instance/v1'
PROPOSAL_POLICY_VERSION = 'auto-mask-proposals/bounded-source-order-v2'
RANKING_POLICY_VERSION = 'anchor-mask-ranking/v2'


class ProposalIdentityDigestTests(unittest.TestCase):
    def test_canonicalizes_json_numbers_by_binary64_value(self) -> None:
        self.assertEqual(
            _proposal_identity_digest(
                {
                    'integer': 1,
                    'negativeZero': -0.0,
                    'smallExponent': 1e-7,
                    'fixed': 1e-5,
                    'large': 1e20,
                    'values': [0.1, -2],
                }
            ),
            'sha256:a64229f647814d4cff1565284ed59b3cba0fd8ea7001249fc11f20da65163e58',
        )


# The fake SAM 3 Image runtime never decodes the frame; these bytes only need
# a stable identity so the RGB digest binding can be verified end to end.
IMAGE_PNG = b'\x89PNG\r\n\x1a\nanchor-rgb-frame'
IMAGE_DIGEST = f'sha256:{hashlib.sha256(IMAGE_PNG).hexdigest()}'
IMAGE_WIDTH = 2
IMAGE_HEIGHT = 2

# One foreground pixel at (1, 0): bit index 1 of a single bitset byte.
ACCEPTED_MASK_BITS = bytes([0b00000010])
ACCEPTED_MASK_BASE64 = base64.b64encode(ACCEPTED_MASK_BITS).decode('ascii')


def _canonical_json_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, separators=(',', ':'), sort_keys=True
    ).encode()
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


class FakeSam3ImageRuntime:
    """Records the official SAM 3 Image seam without requiring CUDA."""

    def __init__(self) -> None:
        self.set_image_calls: list[bytes] = []
        self.predict_calls: list[dict[str, object]] = []
        self.masks: list[list[list[bool]]] = [[[False, True], [False, False]]]
        self.scores: list[float] = [0.9]
        self.predict_started: Event | None = None
        self.predict_release: Event | None = None
        self.predict_error: BaseException | None = None

    def set_image(self, rgb_png: bytes) -> dict[str, object]:
        self.set_image_calls.append(rgb_png)
        return {'imageState': len(self.set_image_calls)}

    def predict_inst(
        self, inference_state: object, **kwargs: object
    ) -> tuple[object, object, np.ndarray]:
        self.predict_calls.append({'inferenceState': inference_state, **kwargs})
        if self.predict_started is not None:
            self.predict_started.set()
        if (
            self.predict_release is not None
            and not self.predict_release.wait(timeout=5)
        ):
            raise RuntimeError('test SAM prompt was never released')
        if self.predict_error is not None:
            raise self.predict_error
        count = len(self.masks)
        return (
            self.masks,
            self.scores,
            np.zeros((count, 256, 256), dtype=np.float32),
        )


class AISelectMaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.lock_file = self.directory / 'uv.lock'
        self.lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', self.lock_file)
        self.model_manifest_digest = self.install_sam3_image_manifest(self.state)

        self.runtime = FakeSam3ImageRuntime()
        self.state.mask_adapters[ADAPTER_ID] = Sam3ImageInstanceAdapter(
            build_model=lambda model: self.runtime
        )

        self.server = create_server(
            state=self.state,
            endpoint='http://127.0.0.1:0',
            profile='loopback',
            allowed_origins=[EDITOR_ORIGIN],
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    def install_sam3_image_manifest(
        self,
        state: CompanionState,
        *,
        digest: str = 'sha256:sam3-image-v1',
        source_commit: str = 'sam3-source-v1',
    ) -> str:
        weights = self.directory / 'sam3-image.pt'
        weights.write_bytes(b'separately acquired sam3 image weights')
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / f'{digest.replace(":", "-")}.json'
        manifest.write_text(
            json.dumps({
                'digest': digest,
                'adapterId': ADAPTER_ID,
                'modelName': 'SAM 3 Image',
                'checkpointDigest': f'sha256:{checkpoint_digest}',
                'sourceCommit': source_commit,
                'licenseName': 'SAM License',
                'licenseUrl': 'https://example.test/sam-license',
                'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            }),
            encoding='utf-8',
        )
        return state.install_model(manifest, weights)['digest']

    @staticmethod
    def prompt_state_digest(prompt_state: dict[str, object]) -> str:
        return _canonical_json_digest({
            key: value
            for key, value in prompt_state.items()
            if key != 'digest'
        })

    def request_body(self) -> dict[str, object]:
        points = [
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
        ]
        prompt_state: dict[str, object] = {
            'schemaVersion': 2,
            'viewId': 'anchor-view',
            'rgbDigest': IMAGE_DIGEST,
            'revision': 1,
            'points': points,
            'boxes': [],
        }
        prompt_state['digest'] = self.prompt_state_digest(prompt_state)
        prompt_capabilities = self.state.capabilities([EDITOR_ORIGIN])[
            'modelManifests'
        ][0]['promptCapabilities']
        return {
            'requestBinding': {
                'targetContextId': 'context-1',
                'contextRevision': 0,
                'dependencyToken': {
                    'splatId': 'splat-1',
                    'renderStateToken': 'render-v1',
                    'geometryToken': 'geometry-v1',
                    'gaussianIdentityToken': 'ids-v1',
                    'worldTransformToken': 'world-v1',
                },
            },
            'targetSplatId': 'splat-1',
            'sceneId': 'splat-1',
            'sceneVersion': 'snapshot-v1',
            'viewId': 'anchor-view',
            'cameraBindingDigest': f'sha256:{"1" * 64}',
            'proposalAttemptId': 'proposal-attempt-1',
            'rgbDigest': IMAGE_DIGEST,
            'rgbWidth': IMAGE_WIDTH,
            'rgbHeight': IMAGE_HEIGHT,
            'rgb': {
                'pngBase64': base64.b64encode(IMAGE_PNG).decode('ascii'),
                'digest': IMAGE_DIGEST,
                'width': IMAGE_WIDTH,
                'height': IMAGE_HEIGHT,
            },
            'promptState': prompt_state,
            'modelManifestDigest': self.model_manifest_digest,
            'adapterCapabilityDigest': prompt_capabilities['capabilityDigest'],
            'proposalPolicyVersion': PROPOSAL_POLICY_VERSION,
            'rankingPolicyVersion': RANKING_POLICY_VERSION,
        }

    def refresh_prompt_state_digest(self, request: dict[str, object]) -> None:
        prompt_state = request['promptState']
        prompt_state['digest'] = self.prompt_state_digest(prompt_state)  # type: ignore[index]

    def post_proposals(self, body: dict[str, object]) -> dict[str, object]:
        with urlopen(Request(
            f'{self.endpoint}/ai-select/mask-proposals',
            data=json.dumps(body).encode(),
            method='POST',
            headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
        )) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    def post_proposal_error(
        self, body: dict[str, object]
    ) -> tuple[int, dict[str, object]]:
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f'{self.endpoint}/ai-select/mask-proposals',
                data=json.dumps(body).encode(),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            ))
        return error.exception.code, json.load(error.exception)

    def assert_invalid_request(self, body: dict[str, object]) -> None:
        status, payload = self.post_proposal_error(body)
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(payload['status'], 'invalidRequest')
        self.assertEqual(self.runtime.predict_calls, [])

    def assert_mask_error(
        self, body: dict[str, object], code: str
    ) -> dict[str, object]:
        status, payload = self.post_proposal_error(body)
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], code)
        return payload

    def test_produces_a_bound_single_frame_sam3_image_proposal(self) -> None:
        request = self.request_body()

        response = self.post_proposals(request)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], request['requestBinding'])
        self.assertEqual(response['targetSplatId'], 'splat-1')
        self.assertEqual(response['sceneId'], 'splat-1')
        self.assertEqual(response['sceneVersion'], 'snapshot-v1')
        self.assertEqual(response['viewId'], 'anchor-view')
        self.assertEqual(response['cameraBindingDigest'], request['cameraBindingDigest'])
        self.assertEqual(response['proposalAttemptId'], 'proposal-attempt-1')
        self.assertEqual(response['rgbDigest'], IMAGE_DIGEST)
        self.assertEqual(
            response['promptStateDigest'],
            request['promptState']['digest'],  # type: ignore[index]
        )
        self.assertEqual(response['modelManifestDigest'], self.model_manifest_digest)
        proposal_set = response['proposalSet']
        self.assertEqual(proposal_set['schemaVersion'], 3)
        self.assertEqual(proposal_set['proposalPolicyVersion'], PROPOSAL_POLICY_VERSION)
        self.assertEqual(proposal_set['proposalAttemptId'], 'proposal-attempt-1')
        self.assertNotIn('diagnostics', proposal_set)
        self.assertEqual(len(proposal_set['proposals']), 1)
        proposal = proposal_set['proposals'][0]
        self.assertEqual(proposal['proposalId'], 'proposal-0')
        self.assertEqual(proposal['sourceIndex'], 0)
        self.assertEqual(
            proposal['promptConsistency'],
            {
                'positivePointsSatisfied': True,
                'negativePointsSatisfied': True,
                'positiveBoxesSatisfied': True,
            },
        )
        self.assertEqual(
            proposal['promptDiagnostics'],
            [{
                'promptId': 'prompt-1',
                'family': 'point',
                'polarity': 'include',
                'satisfied': True,
            }],
        )
        mask = proposal['mask']
        self.assertEqual(mask['encoding'], 'bitset-lsb-v1')
        self.assertEqual(mask['width'], IMAGE_WIDTH)
        self.assertEqual(mask['height'], IMAGE_HEIGHT)
        self.assertEqual(mask['data'], ACCEPTED_MASK_BASE64)
        self.assertEqual(
            mask['digest'],
            f'sha256:{hashlib.sha256(base64.b64decode(mask["data"])).hexdigest()}',
        )
        self.assertEqual(response['proposalDecision']['status'], 'selected')
        self.assertEqual(
            response['proposalDecision']['selectedProposalId'],
            proposal['proposalId'],
        )
        self.assertEqual(
            response['proposalDecision']['rankingPolicyVersion'],
            RANKING_POLICY_VERSION,
        )

        # The single positive point takes the multimask instance path.
        self.assertEqual(self.runtime.set_image_calls, [IMAGE_PNG])
        self.assertEqual(len(self.runtime.predict_calls), 1)
        predict = self.runtime.predict_calls[0]
        self.assertEqual(np.asarray(predict['point_coords']).tolist(), [[1.0, 0.0]])
        self.assertEqual(np.asarray(predict['point_labels']).tolist(), [1])
        self.assertIsNone(predict['box'])
        self.assertIsNone(predict['mask_input'])
        self.assertIs(predict['multimask_output'], True)

        # The retained candidate carries one opaque digest-bound logits ref.
        ref = proposal['logitsRef']
        self.assertEqual(ref['schemaVersion'], 1)
        self.assertEqual(
            ref['companionInstanceId'],
            self.state.health()['companionInstanceId'],
        )
        self.assertTrue(ref['stateId'].startswith('logits-'))
        self.assertEqual(ref['targetContextId'], 'context-1')
        self.assertEqual(ref['viewId'], 'anchor-view')
        self.assertEqual(ref['rgbDigest'], IMAGE_DIGEST)
        self.assertEqual(ref['sourceInferenceAttemptId'], 'proposal-attempt-1')
        self.assertEqual(ref['sourceCandidateId'], 'proposal-0')
        self.assertEqual(ref['shape'], [1, 256, 256])
        self.assertEqual(ref['dtype'], 'float32')
        self.assertEqual(
            ref['dataDigest'],
            f'sha256:{hashlib.sha256(np.zeros((1, 256, 256), dtype=np.float32).tobytes()).hexdigest()}',
        )
        ref_fields = {key: value for key, value in ref.items() if key != 'refDigest'}
        self.assertEqual(ref['refDigest'], _canonical_json_digest(ref_fields))
        self.assertEqual(len(self.state._logits_store), 1)

    def test_proposal_digest_survives_browser_json_number_round_trip(self) -> None:
        # The locked adapter can publish an exact 1.0 score. The digest binds
        # its binary64 value instead of a Python- or JavaScript-specific
        # lexical JSON spelling.
        self.runtime.scores = [1.0]

        response = self.post_proposals(self.request_body())
        proposal_set = response['proposalSet']
        payload = {
            key: value
            for key, value in proposal_set.items()
            if key != 'digest'
        }

        self.assertEqual(
            proposal_set['digest'],
            _proposal_identity_digest(payload),
        )

    def test_rejects_a_request_whose_target_and_dependency_bindings_disagree(self) -> None:
        request = self.request_body()
        request['requestBinding']['dependencyToken']['splatId'] = 'other-splat'  # type: ignore[index]

        self.assert_invalid_request(request)

    def test_rejects_a_request_without_a_proposal_attempt_identity(self) -> None:
        request = self.request_body()
        del request['proposalAttemptId']

        self.assert_invalid_request(request)

    def test_rejects_an_rgb_artifact_digest_mismatch(self) -> None:
        request = self.request_body()
        request['rgb']['digest'] = (  # type: ignore[index]
            f'sha256:{hashlib.sha256(b"not the anchor frame").hexdigest()}'
        )

        self.assert_invalid_request(request)

    def test_rejects_an_rgb_artifact_that_disagrees_with_the_request_reference(self) -> None:
        request = self.request_body()
        request['rgbDigest'] = f'sha256:{"9" * 64}'

        self.assert_invalid_request(request)

    def test_rejects_a_request_without_rgb_dimensions(self) -> None:
        request = self.request_body()
        del request['rgbWidth']

        self.assert_invalid_request(request)

    def test_rejects_out_of_bounds_prompt_coordinates(self) -> None:
        for prompt in (
            {'promptId': 'prompt-1', 'xPx': IMAGE_WIDTH, 'yPx': 0, 'polarity': 'include'},
            {'promptId': 'prompt-1', 'xPx': 0, 'yPx': IMAGE_HEIGHT, 'polarity': 'include'},
            {'promptId': 'prompt-1', 'xPx': -1, 'yPx': 0, 'polarity': 'include'},
        ):
            with self.subTest(prompt=prompt):
                request = self.request_body()
                request['promptState']['points'] = [prompt]  # type: ignore[index]
                self.refresh_prompt_state_digest(request)
                self.assert_invalid_request(request)

    def test_rejects_an_empty_prompt_list(self) -> None:
        request = self.request_body()
        request['promptState']['points'] = []  # type: ignore[index]
        self.refresh_prompt_state_digest(request)

        self.assert_invalid_request(request)

    def test_rejects_an_unknown_prompt_polarity(self) -> None:
        request = self.request_body()
        request['promptState']['points'] = [  # type: ignore[index]
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'maybe'},
        ]
        self.refresh_prompt_state_digest(request)

        self.assert_invalid_request(request)

    def test_rejects_a_v1_prompt_state_artifact(self) -> None:
        request = self.request_body()
        prompt_state: dict[str, object] = {
            'schemaVersion': 1,
            'viewId': 'anchor-view',
            'rgbDigest': IMAGE_DIGEST,
            'revision': 1,
            'points': [
                {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
            ],
            'boxes': [],
            'maskConstraints': [],
            'textPrompts': [],
        }
        prompt_state['digest'] = self.prompt_state_digest(prompt_state)
        request['promptState'] = prompt_state

        self.assert_invalid_request(request)

    def test_rejects_removed_prompt_families_even_at_schema_version_2(self) -> None:
        request = self.request_body()
        request['promptState']['maskConstraints'] = []  # type: ignore[index]
        self.refresh_prompt_state_digest(request)

        self.assert_invalid_request(request)

    def test_reports_an_unavailable_model_manifest(self) -> None:
        request = self.request_body()
        request['modelManifestDigest'] = 'sha256:missing-manifest'

        payload = self.assert_mask_error(request, 'modelUnavailable')
        self.assertNotIn('proposalSet', payload)
        self.assertEqual(self.runtime.predict_calls, [])

    def test_reports_an_incompatible_model_manifest(self) -> None:
        weights = self.directory / 'unknown-adapter.bin'
        weights.write_bytes(b'separately acquired unknown adapter weights')
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / 'unknown-adapter.json'
        manifest.write_text(
            json.dumps({
                'digest': 'sha256:unknown-adapter-v1',
                'adapterId': 'unknown-adapter',
                'modelName': 'Unknown Adapter v1',
                'checkpointDigest': f'sha256:{checkpoint_digest}',
                'sourceCommit': 'unknown-adapter-source-v1',
                'licenseName': 'MIT',
                'licenseUrl': 'https://example.test/unknown-adapter-license',
                'runtimeConfigDigest': 'sha256:unknown-adapter-runtime-v1',
            }),
            encoding='utf-8',
        )
        incompatible_digest = self.state.install_model(manifest, weights)['digest']
        request = self.request_body()
        request['modelManifestDigest'] = incompatible_digest

        self.assert_mask_error(request, 'incompatibleManifest')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_a_sam31_manifest_fails_closed_on_the_current_route(self) -> None:
        weights = self.directory / 'sam31-legacy.pt'
        weights.write_bytes(b'separately acquired legacy sam3.1 weights')
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / 'sam31-legacy.json'
        manifest.write_text(
            json.dumps({
                'digest': 'sha256:sam31-legacy-v1',
                'adapterId': 'sam3.1',
                'modelName': 'SAM 3.1 multiplex',
                'checkpointDigest': f'sha256:{checkpoint_digest}',
                'sourceCommit': 'sam3-source-v1',
                'licenseName': 'SAM License',
                'licenseUrl': 'https://example.test/sam-license',
                'runtimeConfigDigest': SAM31_RUNTIME_CONFIG_DIGEST,
            }),
            encoding='utf-8',
        )
        legacy_digest = self.state.install_model(manifest, weights)['digest']
        request = self.request_body()
        request['modelManifestDigest'] = legacy_digest

        self.assert_mask_error(request, 'incompatibleManifest')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_rejects_a_stale_adapter_capability_identity(self) -> None:
        request = self.request_body()
        request['adapterCapabilityDigest'] = f'sha256:{"f" * 64}'

        self.assert_mask_error(request, 'capabilityMismatch')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_rejects_a_stale_proposal_policy_identity(self) -> None:
        request = self.request_body()
        request['proposalPolicyVersion'] = 'auto-mask-proposals/bounded-source-order-v1'

        self.assert_mask_error(request, 'capabilityMismatch')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_rejects_a_stale_ranking_policy_identity(self) -> None:
        request = self.request_body()
        request['rankingPolicyVersion'] = 'anchor-mask-ranking/v1'

        self.assert_mask_error(request, 'capabilityMismatch')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_rejects_a_well_formed_unsupported_negative_box_prompt(self) -> None:
        request = self.request_body()
        request['promptState']['boxes'] = [{  # type: ignore[index]
            'promptId': 'box-1',
            'polarity': 'exclude',
            'x0Px': 0,
            'y0Px': 0,
            'x1Px': 1,
            'y1Px': 1,
        }]
        self.refresh_prompt_state_digest(request)

        self.assert_mask_error(request, 'unsupportedPromptType')
        self.assertEqual(self.runtime.predict_calls, [])

    def test_forwards_a_positive_box_to_the_instance_adapter(self) -> None:
        request = self.request_body()
        request['promptState']['boxes'] = [{  # type: ignore[index]
            'promptId': 'box-1',
            'polarity': 'include',
            'x0Px': 0,
            'y0Px': 0,
            'x1Px': 2,
            'y1Px': 2,
        }]
        self.refresh_prompt_state_digest(request)

        response = self.post_proposals(request)

        self.assertEqual(len(self.runtime.predict_calls), 1)
        predict = self.runtime.predict_calls[0]
        self.assertIs(predict['multimask_output'], False)
        self.assertEqual(np.asarray(predict['box']).tolist(), [0.0, 0.0, 2.0, 2.0])
        self.assertIsNone(predict['mask_input'])
        self.assertIs(predict['normalize_coords'], True)
        proposal = response['proposalSet']['proposals'][0]
        self.assertTrue(proposal['promptConsistency']['positiveBoxesSatisfied'])
        self.assertEqual(
            [(item['family'], item['promptId']) for item in proposal['promptDiagnostics']],
            [
                ('point', 'prompt-1'),
                ('box', 'box-1'),
            ],
        )

    def test_publishes_an_empty_proposal_set_when_the_adapter_finds_no_mask(
        self,
    ) -> None:
        self.runtime.masks = [[[False, False], [False, False]]]

        first = self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(first['proposalSet']['proposals'], [])
        self.assertEqual(first['proposalDecision']['status'], 'unavailable')
        self.assertEqual(len(self.runtime.predict_calls), 1)

        replayed = self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(replayed, first)
        self.assertEqual(len(self.runtime.predict_calls), 1)

        retry = self.request_body()
        retry['proposalAttemptId'] = 'proposal-attempt-2'
        retried = self.state.produce_ai_select_mask(retry)
        self.assertEqual(retried['proposalSet']['proposals'], [])
        self.assertEqual(retried['proposalDecision']['status'], 'unavailable')
        self.assertEqual(len(self.runtime.predict_calls), 2)

    def test_preserves_nested_part_and_whole_candidates_as_ambiguous(self) -> None:
        # Both candidates contain the positive point. The first is a local
        # part; the second strictly contains it and adds neighbouring area.
        self.runtime.masks = [
            [[False, True], [False, False]],
            [[True, True], [True, False]],
        ]
        # The oversized candidate deliberately has the much higher raw model
        # score. Ranking must still surface the geometric ambiguity.
        self.runtime.scores = [0.1, 0.99]

        response = self.state.produce_ai_select_mask(self.request_body())

        proposals = response['proposalSet']['proposals']
        self.assertEqual(
            [proposal['sourceIndex'] for proposal in proposals],
            [0, 1],
        )
        self.assertEqual(
            [proposal['modelScore'] for proposal in proposals],
            [0.1, 0.99],
        )
        # Candidate cardinality of masks, scores, and refs matches.
        self.assertEqual(
            [proposal['logitsRef']['sourceCandidateId'] for proposal in proposals],
            ['proposal-0', 'proposal-1'],
        )
        decision = response['proposalDecision']
        self.assertEqual(decision['status'], 'ambiguous')
        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-0', 'proposal-1'],
        )
        self.assertIn(
            'nested-part-vs-whole',
            [reason['code'] for reason in decision['reasons']],
        )
        self.assertIn(
            'neighbour-object-leak-risk',
            [reason['code'] for reason in decision['reasons']],
        )
        self.assertEqual(
            proposals[0]['rankingFeatures']['optionalSupportSanity'],
            {'participated': False, 'changedDecision': False},
        )
        self.assertTrue(
            proposals[0]['rankingFeatures']['pairwiseRelations'][0][
                'materiallyDistinct'
            ]
        )

    def test_point_inconsistent_candidate_is_diagnostic_but_ineligible(self) -> None:
        # The candidate covers (1, 0) only; prompting (0, 1) keeps the raw
        # alternative inspectable but prevents 07A selection.
        request = self.request_body()
        request['promptState']['points'] = [  # type: ignore[index]
            {'promptId': 'prompt-1', 'xPx': 0, 'yPx': 1, 'polarity': 'include'},
        ]
        self.refresh_prompt_state_digest(request)

        response = self.state.produce_ai_select_mask(request)

        proposal = response['proposalSet']['proposals'][0]
        self.assertFalse(
            proposal['promptConsistency']['positivePointsSatisfied']
        )
        self.assertFalse(proposal['rankingFeatures']['eligible'])
        self.assertEqual(response['proposalDecision']['status'], 'unavailable')

    def test_replays_a_matching_mask_request_without_a_second_inference(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        replay = self.state.produce_ai_select_mask(self.request_body())

        self.assertEqual(replay, first)
        self.assertEqual(len(self.runtime.predict_calls), 1)

        # An explicit Retry mints a new attempt identity for the same RGB and
        # prompts and really reruns the adapter without reusing logits.
        retry_request = self.request_body()
        retry_request['proposalAttemptId'] = 'proposal-attempt-2'
        retry = self.state.produce_ai_select_mask(retry_request)

        self.assertEqual(retry['proposalAttemptId'], 'proposal-attempt-2')
        self.assertEqual(
            retry['proposalSet']['proposals'][0]['mask'],
            first['proposalSet']['proposals'][0]['mask'],
        )
        self.assertEqual(len(self.runtime.predict_calls), 2)
        self.assertIsNone(self.runtime.predict_calls[1]['mask_input'])
        retry_ref = retry['proposalSet']['proposals'][0]['logitsRef']
        self.assertEqual(
            retry_ref['sourceInferenceAttemptId'], 'proposal-attempt-2'
        )
        self.assertNotEqual(
            retry_ref['stateId'],
            first['proposalSet']['proposals'][0]['logitsRef']['stateId'],
        )

    def test_a_concurrent_matching_request_joins_the_same_inference(self) -> None:
        self.runtime.predict_started = Event()
        self.runtime.predict_release = Event()
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []
        duplicate_started = Event()

        def produce_into_results(notify_started: Event | None = None) -> None:
            if notify_started is not None:
                notify_started.set()
            try:
                results.append(self.state.produce_ai_select_mask(self.request_body()))
            except BaseException as error:
                errors.append(error)

        first = Thread(target=produce_into_results, daemon=True)
        duplicate = Thread(
            target=lambda: produce_into_results(duplicate_started),
            daemon=True,
        )
        first.start()
        self.assertTrue(self.runtime.predict_started.wait(timeout=1))
        duplicate.start()
        self.assertTrue(duplicate_started.wait(timeout=1))

        self.runtime.predict_release.set()
        first.join(timeout=5)
        duplicate.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(duplicate.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.runtime.predict_calls), 1)

    def test_mask_request_holds_the_single_companion_capacity_lease(self) -> None:
        self.runtime.predict_started = Event()
        self.runtime.predict_release = Event()
        worker = Thread(
            target=lambda: self.state.produce_ai_select_mask(self.request_body()),
            daemon=True,
        )
        worker.start()
        self.assertTrue(self.runtime.predict_started.wait(timeout=1))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['capacity']['activeSessions'],
            1,
        )

        competing_request = self.request_body()
        competing_request['proposalAttemptId'] = 'proposal-attempt-2'
        with self.assertRaisesRegex(MaskSessionError, 'already serving another'):
            self.state.produce_ai_select_mask(competing_request)

        self.runtime.predict_release.set()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['capacity']['activeSessions'],
            0,
        )

    def test_an_invalid_adapter_mask_is_masked_as_a_failure_without_publication(self) -> None:
        class BrokenMaskAdapter:
            def __init__(self) -> None:
                self.invocations = 0

            def produce_tracks(self, **_kwargs: Any) -> MaskProduction:
                self.invocations += 1
                return MaskProduction(
                    tracks=[{
                        'trackId': 'primary',
                        'role': 'include',
                        'frames': [{
                            'viewId': 'anchor-view',
                            'status': 'accepted',
                            'binaryMask': {
                                'encoding': 'bitset-lsb-v1',
                                'width': IMAGE_WIDTH + 1,
                                'height': IMAGE_HEIGHT,
                                'data': ACCEPTED_MASK_BASE64,
                            },
                        }],
                    }],
                    threshold=0.5,
                )

        broken_adapter = BrokenMaskAdapter()
        self.state.mask_adapters[ADAPTER_ID] = broken_adapter  # type: ignore[assignment]

        with self.assertRaises(MaskSessionError) as error:
            self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(error.exception.code, 'incompleteMaskSet')

        # The failed attempt publishes nothing and replays the same failure.
        with self.assertRaises(MaskSessionError) as replayed:
            self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(replayed.exception.code, 'incompleteMaskSet')
        self.assertEqual(broken_adapter.invocations, 1)
        self.assertEqual(self.state._logits_store, {})

    def test_adapter_oom_publishes_no_partial_proposal_set_or_refinement_ref(self) -> None:
        self.runtime.predict_error = RuntimeError('CUDA out of memory')

        payload = self.assert_mask_error(self.request_body(), 'modelFailure')

        # The failed attempt contains no proposalSet and replays atomically
        # without a second adapter execution.
        self.assertNotIn('proposalSet', payload)
        status, replay = self.post_proposal_error(self.request_body())
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(replay['code'], 'modelFailure')
        self.assertNotIn('proposalSet', replay)
        self.assertEqual(len(self.runtime.predict_calls), 1)
        self.assertEqual(self.state._logits_store, {})

    def test_cancellation_publishes_no_partial_proposal_set_or_refinement_ref(self) -> None:
        self.runtime.predict_error = MaskSessionError(
            'cancelled', 'The instance Prompt request was cancelled.'
        )

        self.assert_mask_error(self.request_body(), 'cancelled')
        self.assertEqual(self.state._logits_store, {})

    def test_digest_only_request_resolves_the_companion_rgb_cache(self) -> None:
        first = self.post_proposals(self.request_body())
        self.assertEqual(first['status'], 'complete')

        reference_request = self.request_body()
        del reference_request['rgb']
        reference_request['proposalAttemptId'] = 'proposal-attempt-2'

        second = self.post_proposals(reference_request)

        self.assertEqual(second['status'], 'complete')
        self.assertEqual(second['rgbDigest'], IMAGE_DIGEST)
        self.assertEqual(len(self.runtime.predict_calls), 2)
        self.assertEqual(self.runtime.set_image_calls, [IMAGE_PNG, IMAGE_PNG])

    def test_digest_only_request_without_cached_rgb_fails_before_inference(self) -> None:
        request = self.request_body()
        del request['rgb']

        payload = self.assert_mask_error(request, 'rgbUnresolvable')
        self.assertNotIn('proposalSet', payload)
        self.assertEqual(self.runtime.predict_calls, [])
        self.assertEqual(self.runtime.set_image_calls, [])

    def refinement_request(
        self,
        ref: dict[str, object],
        *,
        attempt_id: str = 'proposal-attempt-2',
        rgb_png: bytes = IMAGE_PNG,
        model_manifest_digest: str | None = None,
    ) -> dict[str, object]:
        rgb_digest = f'sha256:{hashlib.sha256(rgb_png).hexdigest()}'
        prompt_state: dict[str, object] = {
            'schemaVersion': 2,
            'viewId': 'anchor-view',
            'rgbDigest': rgb_digest,
            'revision': 2,
            'points': [
                {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
                {'promptId': 'prompt-2', 'xPx': 0, 'yPx': 1, 'polarity': 'exclude'},
            ],
            'boxes': [],
        }
        prompt_state['digest'] = self.prompt_state_digest(prompt_state)
        request = self.request_body()
        request['proposalAttemptId'] = attempt_id
        request['rgbDigest'] = rgb_digest
        request['rgb'] = {
            'pngBase64': base64.b64encode(rgb_png).decode('ascii'),
            'digest': rgb_digest,
            'width': IMAGE_WIDTH,
            'height': IMAGE_HEIGHT,
        }
        request['promptState'] = prompt_state
        request['previousLogitsRef'] = ref
        if model_manifest_digest is not None:
            request['modelManifestDigest'] = model_manifest_digest
        return request

    def tampered_ref(self, ref: dict[str, object], **patch: object) -> dict[str, object]:
        tampered = {**ref, **patch}
        tampered['refDigest'] = _canonical_json_digest({
            key: value for key, value in tampered.items() if key != 'refDigest'
        })
        return tampered

    def test_a_valid_ref_refines_the_same_image_with_attempt_linkage(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = first['proposalSet']['proposals'][0]['logitsRef']

        refined = self.state.produce_ai_select_mask(self.refinement_request(ref))

        # The stored image state and logits are reused; no fresh set_image or
        # multimask expansion happens for a refinement attempt.
        self.assertEqual(len(self.runtime.set_image_calls), 1)
        self.assertEqual(len(self.runtime.predict_calls), 2)
        predict = self.runtime.predict_calls[1]
        self.assertIsNotNone(predict['mask_input'])
        self.assertIs(predict['multimask_output'], False)
        proposal_set = refined['proposalSet']
        self.assertNotIn('diagnostics', proposal_set)
        self.assertEqual(len(proposal_set['proposals']), 1)
        new_ref = proposal_set['proposals'][0]['logitsRef']
        self.assertEqual(new_ref['sourceInferenceAttemptId'], 'proposal-attempt-1')
        self.assertEqual(new_ref['sourceCandidateId'], 'proposal-0')
        self.assertNotEqual(new_ref['stateId'], ref['stateId'])

    def test_an_unknown_state_id_falls_back_to_fresh_inference(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = self.tampered_ref(
            first['proposalSet']['proposals'][0]['logitsRef'],
            stateId='logits-unknown',
        )

        response = self.state.produce_ai_select_mask(self.refinement_request(ref))

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        predict = self.runtime.predict_calls[1]
        self.assertIsNone(predict['mask_input'])
        self.assertEqual(len(self.runtime.set_image_calls), 2)

    def test_a_companion_restart_invalidates_the_ref(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = first['proposalSet']['proposals'][0]['logitsRef']

        replacement_runtime = FakeSam3ImageRuntime()
        replacement = CompanionState(self.directory / 'state')
        replacement.mask_adapters[ADAPTER_ID] = Sam3ImageInstanceAdapter(
            build_model=lambda model: replacement_runtime
        )

        response = replacement.produce_ai_select_mask(
            self.refinement_request(ref)
        )

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        self.assertEqual(len(replacement_runtime.set_image_calls), 1)
        self.assertIsNone(replacement_runtime.predict_calls[0]['mask_input'])
        self.assertEqual(self.state._logits_store.__len__(), 1)

    def test_an_adapter_runtime_change_invalidates_the_ref(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = first['proposalSet']['proposals'][0]['logitsRef']
        replacement_manifest = self.install_sam3_image_manifest(
            self.state,
            digest='sha256:sam3-image-v2',
            source_commit='sam3-source-v2',
        )

        response = self.state.produce_ai_select_mask(
            self.refinement_request(
                ref, model_manifest_digest=replacement_manifest
            )
        )

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        self.assertIsNone(self.runtime.predict_calls[1]['mask_input'])

    def test_an_rgb_change_invalidates_the_ref(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = first['proposalSet']['proposals'][0]['logitsRef']

        response = self.state.produce_ai_select_mask(
            self.refinement_request(ref, rgb_png=b'\x89PNG\r\n\x1a\nchanged-rgb')
        )

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        predict = self.runtime.predict_calls[1]
        self.assertIsNone(predict['mask_input'])
        self.assertEqual(len(self.runtime.set_image_calls), 2)

    def test_binary_brush_bytes_cannot_validate_as_a_logits_ref(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = first['proposalSet']['proposals'][0]['logitsRef']
        # A binary brush artifact in place of the continuous logits payload
        # can never satisfy the stored float32 logits digest lineage.
        brush_ref = self.tampered_ref(
            ref,
            dataDigest=f'sha256:{hashlib.sha256(ACCEPTED_MASK_BITS).hexdigest()}',
        )

        response = self.state.produce_ai_select_mask(
            self.refinement_request(brush_ref)
        )

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        self.assertIsNone(self.runtime.predict_calls[1]['mask_input'])

    def test_a_structurally_foreign_ref_falls_back_without_error(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        ref = self.tampered_ref(
            first['proposalSet']['proposals'][0]['logitsRef'],
            adapterRuntimeDigest=f'sha256:{"0" * 64}',
        )

        response = self.state.produce_ai_select_mask(self.refinement_request(ref))

        self.assertEqual(
            response['proposalSet']['diagnostics'], {'refinementFallback': True}
        )
        self.assertIsNone(self.runtime.predict_calls[1]['mask_input'])

    def test_a_non_object_ref_is_rejected_as_an_invalid_request(self) -> None:
        request = self.request_body()
        request['previousLogitsRef'] = 'not-a-ref'

        self.assert_invalid_request(request)

    def test_the_logits_store_stays_bounded(self) -> None:
        self.runtime.masks = [
            [[False, True], [False, False]],
            [[True, True], [False, False]],
            [[False, True], [False, True]],
        ]
        self.runtime.scores = [0.9, 0.8, 0.7]

        for attempt in range(1, 5):
            request = self.request_body()
            request['proposalAttemptId'] = f'proposal-attempt-{attempt}'
            self.state.produce_ai_select_mask(request)

        self.assertLessEqual(len(self.state._logits_store), 8)


if __name__ == '__main__':
    unittest.main()

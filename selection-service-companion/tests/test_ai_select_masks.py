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
from selection_service_companion.proposal_ranking import (
    RANKING_POLICY_VERSION,
    add_ranking_features,
    decide_proposals,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import (
    CompanionState,
    _proposal_identity_digest,
)


EDITOR_ORIGIN = 'https://editor.example'
ADAPTER_ID = 'sam3-image-instance/v1'
PROPOSAL_POLICY_VERSION = 'auto-mask-proposals/bounded-source-order-v2'
VIEW_ASSESSMENT_POLICY_VERSION = 'local-view-assessment/v2'


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
IMAGE_WIDTH = 8
IMAGE_HEIGHT = 8


def _mask_grid(*pixels: tuple[int, int]) -> list[list[bool]]:
    """Build one WIDTHxHEIGHT boolean frame for the fake image runtime."""

    grid = [[False] * IMAGE_WIDTH for _ in range(IMAGE_HEIGHT)]
    for x_px, y_px in pixels:
        grid[y_px][x_px] = True
    return grid


def _mask_bits(width: int, height: int, pixels: list[tuple[int, int]]) -> bytes:
    """Encode pixels as the bitset-lsb-v1 payload the route emits."""

    bits = bytearray((width * height + 7) // 8)
    for x_px, y_px in pixels:
        pixel_index = y_px * width + x_px
        bits[pixel_index // 8] |= 1 << (pixel_index % 8)
    return bytes(bits)


# A 4x4 foreground block at rows 0-3, columns 1-4: it contains the default
# positive Point (1, 0), clears the degenerate Mask Review floor, and stays
# below the material boundary-clipping margin (4 boundary pixels).
ACCEPTED_PIXELS = [(x, y) for y in range(4) for x in range(1, 5)]
ACCEPTED_MASK_BITS = _mask_bits(IMAGE_WIDTH, IMAGE_HEIGHT, ACCEPTED_PIXELS)
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
        self.masks: list[list[list[bool]]] = [_mask_grid(*ACCEPTED_PIXELS)]
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
            np.zeros((count, 288, 288), dtype=np.float32),
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
    ) -> str:
        weights = self.directory / 'sam3-image.pt'
        weights.write_bytes(b'separately acquired sam3 image weights')
        manifest = self.directory / f'{digest.replace(":", "-")}.json'
        manifest.write_text(
            json.dumps({
                'digest': digest,
                'adapterId': ADAPTER_ID,
                'modelName': 'SAM 3 Image',
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
        self.assertEqual(proposal_set['schemaVersion'], 4)
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
        # Ticket 07A: the retained candidate carries the slim v3 feature
        # record plus its bound Mask Review; the v1 ranking machinery
        # (pairwise relations, compactness, support sanity, ...) is gone.
        self.assertEqual(
            proposal['rankingFeatures'],
            {
                'promptConsistency': {
                    'positivePointsSatisfied': True,
                    'negativePointsSatisfied': True,
                    'positiveBoxesSatisfied': True,
                },
                'eligible': True,
                'areaFraction': 16 / 64,
                'connectedComponentCount': 1,
                'modelScore': 0.9,
            },
        )
        self.assertEqual(
            proposal['review'],
            {
                'status': 'good',
                'reasons': [],
                'actionableReasons': [],
                'policyVersion': VIEW_ASSESSMENT_POLICY_VERSION,
                'diagnostics': {
                    'framePixels': 64,
                    'foregroundPixels': 16,
                    'boundaryPixels': 4,
                    'boundaryContactRatio': 0.25,
                    'connectedComponents': 1,
                    'largestComponentRatio': 1.0,
                    'promptPointCount': 1,
                    'promptViolationCount': 0,
                    'boxSpillPixels': None,
                    'boxSpillRatio': None,
                },
            },
        )
        decision = response['proposalDecision']
        self.assertEqual(decision['schemaVersion'], 2)
        self.assertEqual(decision['status'], 'selected')
        self.assertEqual(decision['selectedProposalId'], proposal['proposalId'])
        self.assertEqual(decision['alternativeProposalIds'], ['proposal-0'])
        self.assertEqual(decision['rankingPolicyVersion'], RANKING_POLICY_VERSION)
        self.assertEqual(decision['viewId'], 'anchor-view')
        self.assertEqual(decision['rgbDigest'], IMAGE_DIGEST)
        self.assertEqual(
            decision['promptStateDigest'],
            request['promptState']['digest'],  # type: ignore[index]
        )
        self.assertEqual(decision['proposalSetDigest'], proposal_set['digest'])
        self.assertNotIn('reasons', decision)

        # Interactive inference always takes the single-result path.
        self.assertEqual(self.runtime.set_image_calls, [IMAGE_PNG])
        self.assertEqual(len(self.runtime.predict_calls), 1)
        predict = self.runtime.predict_calls[0]
        self.assertEqual(np.asarray(predict['point_coords']).tolist(), [[1.0, 0.0]])
        self.assertEqual(np.asarray(predict['point_labels']).tolist(), [1])
        self.assertIsNone(predict['box'])
        self.assertIsNone(predict['mask_input'])
        self.assertIs(predict['multimask_output'], False)

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
        self.assertEqual(ref['shape'], [1, 288, 288])
        self.assertEqual(ref['dtype'], 'float32')
        self.assertEqual(
            ref['dataDigest'],
            f'sha256:{hashlib.sha256(np.zeros((1, 288, 288), dtype=np.float32).tobytes()).hexdigest()}',
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
        manifest = self.directory / 'unknown-adapter.json'
        manifest.write_text(
            json.dumps({
                'digest': 'sha256:unknown-adapter-v1',
                'adapterId': 'unknown-adapter',
                'modelName': 'Unknown Adapter v1',
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
        manifest = self.directory / 'sam31-legacy.json'
        manifest.write_text(
            json.dumps({
                'digest': 'sha256:sam31-legacy-v1',
                'adapterId': 'sam3.1',
                'modelName': 'SAM 3.1 multiplex',
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
        request['rankingPolicyVersion'] = 'anchor-mask-ranking/v2'

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
        # A Box forces single-mask mode: even a multi-candidate runtime
        # retains at most one response-level candidate.
        self.runtime.masks = [
            _mask_grid(*ACCEPTED_PIXELS),
            _mask_grid(*[(x, y) for y in range(5) for x in range(1, 6)]),
        ]
        self.runtime.scores = [0.9, 0.8]
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
        proposals = response['proposalSet']['proposals']
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
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
        self.runtime.masks = [_mask_grid()]

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

    def test_extra_runtime_candidates_are_not_exposed_for_selection(self) -> None:
        # Defensive fake runtimes may still return multiple arrays even when
        # single-result mode is requested; only the first source result is
        # retained and no ambiguity enters the product state.
        self.runtime.masks = [
            _mask_grid(*ACCEPTED_PIXELS),
            _mask_grid(*[(x, y) for y in range(5) for x in range(1, 6)]),
        ]
        self.runtime.scores = [0.1, 0.99]

        response = self.state.produce_ai_select_mask(self.request_body())

        proposals = response['proposalSet']['proposals']
        self.assertEqual(
            [proposal['sourceIndex'] for proposal in proposals],
            [0],
        )
        self.assertEqual(
            [proposal['modelScore'] for proposal in proposals],
            [0.1],
        )
        # Candidate cardinality of masks, scores, and refs matches.
        self.assertEqual(
            [proposal['logitsRef']['sourceCandidateId'] for proposal in proposals],
            ['proposal-0'],
        )
        for proposal in proposals:
            self.assertTrue(proposal['rankingFeatures']['eligible'])
            self.assertEqual(proposal['review']['status'], 'good')
        decision = response['proposalDecision']
        self.assertEqual(decision['schemaVersion'], 2)
        self.assertEqual(decision['status'], 'selected')
        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-0'],
        )
        self.assertEqual(decision['selectedProposalId'], 'proposal-0')
        self.assertNotIn('reasons', decision)

    def test_one_positive_point_retains_one_reviewed_result(self) -> None:
        self.runtime.masks = [
            _mask_grid(*ACCEPTED_PIXELS),
            _mask_grid(*[(x, y) for y in range(5) for x in range(1, 6)]),
            _mask_grid(*[(x, y) for y in range(6) for x in range(0, 7)]),
            _mask_grid(*[(x, y) for y in range(1, 4) for x in range(1, 5)]),
        ]
        self.runtime.scores = [0.95, 0.9, 0.85, 0.8]

        response = self.state.produce_ai_select_mask(self.request_body())

        self.assertIs(self.runtime.predict_calls[0]['multimask_output'], False)
        proposal_set = response['proposalSet']
        proposals = proposal_set['proposals']
        self.assertEqual(len(proposals), 1)
        self.assertEqual(
            [proposal['proposalId'] for proposal in proposals],
            ['proposal-0'],
        )
        for proposal in proposals:
            self.assertEqual(
                proposal['review']['policyVersion'],
                VIEW_ASSESSMENT_POLICY_VERSION,
            )
            self.assertEqual(
                proposal['review']['diagnostics']['framePixels'],
                IMAGE_WIDTH * IMAGE_HEIGHT,
            )
            self.assertIn('eligible', proposal['rankingFeatures'])
        decision = response['proposalDecision']
        self.assertEqual(decision['status'], 'selected')
        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-0'],
        )

    def test_multiple_points_force_a_single_retained_candidate(self) -> None:
        request = self.request_body()
        request['promptState']['points'] = [  # type: ignore[index]
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
            {'promptId': 'prompt-2', 'xPx': 6, 'yPx': 6, 'polarity': 'exclude'},
        ]
        self.refresh_prompt_state_digest(request)
        self.runtime.masks = [
            _mask_grid(*ACCEPTED_PIXELS),
            _mask_grid(*[(x, y) for y in range(5) for x in range(1, 6)]),
            _mask_grid(*[(x, y) for y in range(6) for x in range(0, 7)]),
        ]
        self.runtime.scores = [0.95, 0.9, 0.85]

        response = self.state.produce_ai_select_mask(request)

        self.assertIs(self.runtime.predict_calls[0]['multimask_output'], False)
        self.assertEqual(len(response['proposalSet']['proposals']), 1)

    def test_the_proposal_set_digest_binds_the_review_records(self) -> None:
        response = self.post_proposals(self.request_body())
        proposal_set = response['proposalSet']

        # Schema 4 is the only emitted proposal set shape; v3 sets are gone.
        self.assertEqual(proposal_set['schemaVersion'], 4)
        payload = {
            key: value
            for key, value in proposal_set.items()
            if key != 'digest'
        }
        self.assertEqual(
            proposal_set['digest'],
            _proposal_identity_digest(payload),
        )

        tampered = json.loads(json.dumps(payload))
        tampered['proposals'][0]['review']['status'] = 'review'
        tampered['proposals'][0]['review']['reasons'] = ['severely-fragmented']
        self.assertNotEqual(
            proposal_set['digest'],
            _proposal_identity_digest(tampered),
        )

    def test_point_inconsistent_candidate_is_diagnostic_but_ineligible(self) -> None:
        # The candidate covers the default block only; prompting the
        # background pixel (0, 1) keeps the raw alternative inspectable but
        # prevents 07A selection.
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
        self.assertEqual(proposal['review']['status'], 'review')
        self.assertIn('prompt-inconsistent', proposal['review']['reasons'])
        decision = response['proposalDecision']
        self.assertEqual(decision['status'], 'unavailable')
        self.assertEqual(decision['alternativeProposalIds'], [])
        self.assertNotIn('selectedProposalId', decision)

    def test_replays_a_matching_mask_request_without_a_second_inference(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        replay = self.state.produce_ai_select_mask(self.request_body())

        self.assertEqual(replay, first)
        self.assertEqual(len(self.runtime.predict_calls), 1)

        # A distinct normal execution mints a new attempt identity for the
        # same RGB and prompts, then reruns the adapter without reusing logits.
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
        import torch

        self.runtime.predict_error = torch.OutOfMemoryError('injected CUDA OOM')

        payload = self.assert_mask_error(
            self.request_body(), 'modelOutOfMemory'
        )

        # The failed attempt contains no proposalSet and replays atomically
        # without a second adapter execution.
        self.assertNotIn('proposalSet', payload)
        status, replay = self.post_proposal_error(self.request_body())
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(replay['code'], 'modelOutOfMemory')
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
            _mask_grid(*ACCEPTED_PIXELS),
            _mask_grid(*[(x, y) for y in range(1, 5) for x in range(2, 6)]),
            _mask_grid(*[(x, y) for y in range(2, 6) for x in range(0, 4)]),
        ]
        self.runtime.scores = [0.9, 0.8, 0.7]

        for attempt in range(1, 5):
            request = self.request_body()
            request['proposalAttemptId'] = f'proposal-attempt-{attempt}'
            self.state.produce_ai_select_mask(request)

        self.assertLessEqual(len(self.state._logits_store), 8)


class AddRankingFeaturesTests(unittest.TestCase):
    """Ticket 07A per-candidate eligibility and Mask Review attachment."""

    WIDTH = 16
    HEIGHT = 16

    def _proposal(
        self,
        pixels: list[tuple[int, int]],
        *,
        declared: dict[str, object] | None = None,
        score: float | None = 0.9,
        source_index: int = 0,
    ) -> dict[str, object]:
        bits = _mask_bits(self.WIDTH, self.HEIGHT, pixels)
        proposal: dict[str, object] = {
            'proposalId': f'proposal-{source_index}',
            'sourceIndex': source_index,
            'mask': {
                'encoding': 'bitset-lsb-v1',
                'width': self.WIDTH,
                'height': self.HEIGHT,
                'data': base64.b64encode(bits).decode('ascii'),
            },
        }
        if score is not None:
            proposal['modelScore'] = score
        if declared is not None:
            proposal['promptConsistency'] = declared
        return proposal

    def _enrich(
        self,
        proposals: list[dict[str, object]],
        *,
        points: list[dict[str, object]] | None = None,
        boxes: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        return add_ranking_features(
            proposals,
            width=self.WIDTH,
            height=self.HEIGHT,
            prompt_state={'points': points or [], 'boxes': boxes or []},
        )

    @staticmethod
    def _block(
        x0: int, y0: int, x1: int, y1: int
    ) -> list[tuple[int, int]]:
        return [(x, y) for y in range(y0, y1) for x in range(x0, x1)]

    def test_a_clean_candidate_is_good_and_eligible(self) -> None:
        declared = {
            'positivePointsSatisfied': True,
            'negativePointsSatisfied': True,
            'positiveBoxesSatisfied': True,
        }

        enriched = self._enrich(
            [self._proposal(self._block(4, 4, 8, 8), declared=declared)],
            points=[{'xPx': 5, 'yPx': 5, 'polarity': 'include'}],
        )

        proposal = enriched[0]
        self.assertEqual(
            proposal['rankingFeatures'],
            {
                'promptConsistency': declared,
                'eligible': True,
                'areaFraction': 16 / 256,
                'connectedComponentCount': 1,
                'modelScore': 0.9,
            },
        )
        review = proposal['review']
        self.assertEqual(review['status'], 'good')
        self.assertEqual(review['reasons'], [])
        self.assertEqual(review['actionableReasons'], [])
        self.assertEqual(review['policyVersion'], VIEW_ASSESSMENT_POLICY_VERSION)
        self.assertNotIn('primaryReason', review)
        self.assertEqual(
            review['diagnostics'],
            {
                'framePixels': 256,
                'foregroundPixels': 16,
                'boundaryPixels': 0,
                'boundaryContactRatio': 0.0,
                'connectedComponents': 1,
                'largestComponentRatio': 1.0,
                'promptPointCount': 1,
                'promptViolationCount': 0,
                'boxSpillPixels': None,
                'boxSpillRatio': None,
            },
        )

    def test_missing_or_invalid_declared_facts_are_recomputed(self) -> None:
        points = [{'xPx': 5, 'yPx': 5, 'polarity': 'include'}]
        for declared in (
            None,
            {'positivePointsSatisfied': 'not-a-boolean'},
            {'unknownFact': True},
            # A partial declaration is not the exact three-fact record and
            # falls back to recomputation like a missing one.
            {'positivePointsSatisfied': True, 'negativePointsSatisfied': True},
        ):
            with self.subTest(declared=declared):
                enriched = self._enrich(
                    [self._proposal(self._block(4, 4, 8, 8), declared=declared)],
                    points=points,
                )
                features = enriched[0]['rankingFeatures']
                self.assertEqual(
                    features['promptConsistency'],
                    {
                        'positivePointsSatisfied': True,
                        'negativePointsSatisfied': True,
                        # No Box family exists, so the fact holds vacuously.
                        'positiveBoxesSatisfied': True,
                    },
                )
                self.assertTrue(features['eligible'])

    def test_recomputed_box_fact_requires_meaningful_overlap(self) -> None:
        box = {'x0Px': 4, 'y0Px': 4, 'x1Px': 8, 'y1Px': 8, 'polarity': 'include'}
        overlapping = self._enrich(
            [self._proposal(self._block(4, 4, 8, 8))], boxes=[box]
        )
        self.assertTrue(
            overlapping[0]['rankingFeatures']['promptConsistency'][
                'positiveBoxesSatisfied'
            ]
        )
        disjoint = self._enrich(
            [self._proposal(self._block(10, 10, 14, 14))], boxes=[box]
        )
        self.assertFalse(
            disjoint[0]['rankingFeatures']['promptConsistency'][
                'positiveBoxesSatisfied'
            ]
        )
        self.assertFalse(disjoint[0]['rankingFeatures']['eligible'])

    def test_an_out_of_frame_box_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self._enrich(
                [self._proposal(self._block(4, 4, 8, 8))],
                boxes=[
                    {
                        'x0Px': 0,
                        'y0Px': 0,
                        'x1Px': self.WIDTH,
                        'y1Px': 4,
                        'polarity': 'include',
                    }
                ],
            )

    def test_a_declared_prompt_contradiction_is_ineligible(self) -> None:
        # The mask actually satisfies the Point, but the declared facts say
        # otherwise; a declared hard contradiction never becomes eligible.
        declared = {
            'positivePointsSatisfied': False,
            'negativePointsSatisfied': True,
            'positiveBoxesSatisfied': True,
        }

        enriched = self._enrich(
            [self._proposal(self._block(4, 4, 8, 8), declared=declared)],
            points=[{'xPx': 5, 'yPx': 5, 'polarity': 'include'}],
        )

        proposal = enriched[0]
        self.assertEqual(proposal['rankingFeatures']['promptConsistency'], declared)
        self.assertFalse(proposal['rankingFeatures']['eligible'])
        self.assertEqual(proposal['review']['status'], 'good')

    def test_a_degenerate_candidate_fails_review_and_is_ineligible(self) -> None:
        enriched = self._enrich(
            [self._proposal([(5, 5), (5, 6), (6, 5)])],
            points=[{'xPx': 5, 'yPx': 5, 'polarity': 'include'}],
        )

        proposal = enriched[0]
        review = proposal['review']
        self.assertEqual(review['status'], 'failed')
        self.assertEqual(review['reasons'], ['empty-or-degenerate-mask'])
        self.assertEqual(review['primaryReason'], 'empty-or-degenerate-mask')
        self.assertEqual(review['actionableReasons'], [])
        self.assertFalse(proposal['rankingFeatures']['eligible'])

    def test_a_materially_boundary_clipped_candidate_enters_review(self) -> None:
        # Two full top rows: 18 boundary pixels at a 0.5625 contact ratio,
        # above the 8-pixel / 0.2 material clipping thresholds.
        pixels = self._block(0, 0, self.WIDTH, 2)

        enriched = self._enrich(
            [self._proposal(pixels)],
            points=[{'xPx': 5, 'yPx': 0, 'polarity': 'include'}],
        )

        proposal = enriched[0]
        review = proposal['review']
        self.assertEqual(review['status'], 'review')
        self.assertEqual(review['reasons'], ['target-materially-clipped'])
        self.assertEqual(review['primaryReason'], 'target-materially-clipped')
        # Review status alone never blocks eligibility.
        self.assertTrue(proposal['rankingFeatures']['eligible'])

    def test_a_severely_fragmented_candidate_enters_review(self) -> None:
        # A 25-pixel main component plus a separate 16-pixel component:
        # 16 disconnected pixels at ~39% disconnected mass, above the
        # 16-pixel / 10% fragmentation thresholds.
        pixels = self._block(2, 4, 7, 9) + self._block(10, 4, 14, 8)

        enriched = self._enrich(
            [self._proposal(pixels)],
            points=[{'xPx': 5, 'yPx': 5, 'polarity': 'include'}],
        )

        proposal = enriched[0]
        review = proposal['review']
        self.assertEqual(review['status'], 'review')
        self.assertEqual(review['reasons'], ['severely-fragmented'])
        self.assertEqual(review['primaryReason'], 'severely-fragmented')
        self.assertEqual(review['diagnostics']['connectedComponents'], 2)
        self.assertEqual(proposal['rankingFeatures']['connectedComponentCount'], 2)
        self.assertTrue(proposal['rankingFeatures']['eligible'])

    def test_gross_box_spill_enters_review(self) -> None:
        # One connected blob extends 5 columns past the Box expanded by 2px:
        # 20 spill pixels at ~42% of the candidate, above the 16-pixel / 20%
        # gross spill thresholds.
        pixels = self._block(4, 4, 16, 8)

        enriched = self._enrich(
            [self._proposal(pixels)],
            points=[{'xPx': 5, 'yPx': 5, 'polarity': 'include'}],
            boxes=[{
                'x0Px': 4,
                'y0Px': 4,
                'x1Px': 8,
                'y1Px': 8,
                'polarity': 'include',
            }],
        )

        proposal = enriched[0]
        review = proposal['review']
        self.assertEqual(review['status'], 'review')
        self.assertEqual(review['reasons'], ['box-spill-or-neighbour-leak'])
        self.assertEqual(review['primaryReason'], 'box-spill-or-neighbour-leak')
        self.assertEqual(review['diagnostics']['boxSpillPixels'], 20)
        self.assertTrue(proposal['rankingFeatures']['eligible'])


class DecideProposalsTests(unittest.TestCase):
    """Ticket 07A default-preview ordering and decision classification."""

    def _proposal(
        self,
        source_index: int,
        *,
        eligible: bool = True,
        score: float | None = None,
    ) -> dict[str, object]:
        proposal: dict[str, object] = {
            'proposalId': f'proposal-{source_index}',
            'sourceIndex': source_index,
            'rankingFeatures': {'eligible': eligible},
        }
        if score is not None:
            proposal['modelScore'] = score
        return proposal

    def _decide(self, proposals: list[dict[str, object]]) -> dict[str, object]:
        return decide_proposals(
            proposals,
            view_id='anchor-view',
            rgb_digest='sha256:rgb',
            prompt_state_digest='sha256:prompt',
            proposal_set_digest='sha256:set',
        )

    def test_default_preview_is_the_highest_score_regardless_of_order(self) -> None:
        decision = self._decide([
            self._proposal(0, score=0.2),
            self._proposal(1, score=0.9),
            self._proposal(2, score=0.5),
        ])

        self.assertEqual(decision['status'], 'ambiguous')
        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-1', 'proposal-2', 'proposal-0'],
        )
        self.assertEqual(decision['selectedProposalId'], 'proposal-1')

    def test_score_ties_are_broken_by_source_index(self) -> None:
        decision = self._decide([
            self._proposal(2, score=0.9),
            self._proposal(0, score=0.9),
            self._proposal(1, score=0.9),
        ])

        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-0', 'proposal-1', 'proposal-2'],
        )
        self.assertEqual(decision['selectedProposalId'], 'proposal-0')

    def test_missing_and_non_finite_scores_sort_last(self) -> None:
        decision = self._decide([
            self._proposal(0),
            self._proposal(1, score=0.1),
            self._proposal(2, score=float('nan')),
            self._proposal(3, score=float('inf')),
        ])

        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-1', 'proposal-0', 'proposal-2', 'proposal-3'],
        )
        self.assertEqual(decision['selectedProposalId'], 'proposal-1')

    def test_alternatives_contain_exactly_the_eligible_ids_in_score_order(self) -> None:
        # The highest raw score belongs to an ineligible candidate; it never
        # enters the alternatives or the default preview.
        decision = self._decide([
            self._proposal(0, score=0.5),
            self._proposal(1, eligible=False, score=0.99),
            self._proposal(2, score=0.7),
            self._proposal(3, eligible=False),
        ])

        self.assertEqual(
            decision['alternativeProposalIds'],
            ['proposal-2', 'proposal-0'],
        )
        self.assertEqual(decision['status'], 'ambiguous')
        self.assertEqual(decision['selectedProposalId'], 'proposal-2')

    def test_one_eligible_candidate_is_selected(self) -> None:
        decision = self._decide([self._proposal(0, score=0.4)])

        self.assertEqual(decision['status'], 'selected')
        self.assertEqual(decision['alternativeProposalIds'], ['proposal-0'])
        self.assertEqual(decision['selectedProposalId'], 'proposal-0')

    def test_no_eligible_candidate_is_unavailable(self) -> None:
        for proposals in (
            [],
            [self._proposal(0, eligible=False, score=0.99)],
        ):
            with self.subTest(proposals=proposals):
                decision = self._decide(proposals)
                self.assertEqual(decision['status'], 'unavailable')
                self.assertEqual(decision['alternativeProposalIds'], [])
                self.assertNotIn('selectedProposalId', decision)

    def test_the_decision_shape_binds_identities_without_reasons(self) -> None:
        decision = self._decide([self._proposal(0, score=0.4)])

        self.assertEqual(decision['schemaVersion'], 2)
        self.assertEqual(decision['rankingPolicyVersion'], RANKING_POLICY_VERSION)
        self.assertEqual(decision['viewId'], 'anchor-view')
        self.assertEqual(decision['rgbDigest'], 'sha256:rgb')
        self.assertEqual(decision['promptStateDigest'], 'sha256:prompt')
        self.assertEqual(decision['proposalSetDigest'], 'sha256:set')
        # The v1 verdict reasons (nested-part-vs-whole, insufficient margin,
        # ...) are deleted; ambiguity is expressed only through status.
        self.assertNotIn('reasons', decision)


if __name__ == '__main__':
    unittest.main()

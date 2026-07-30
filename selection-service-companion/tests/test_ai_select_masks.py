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

from selection_service_companion.masking import (
    MaskProduction,
    MaskSessionError,
    SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
    compile_sam31_visual_prompt_program,
    sam31_visual_prompt_capabilities,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import (
    CompanionState,
    _proposal_identity_digest,
)


EDITOR_ORIGIN = 'https://editor.example'


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


class Sam31VisualPromptCompilerTests(unittest.TestCase):
    def test_compiles_visual_prompt_families_in_a_stable_id_order(self) -> None:
        mask_bytes = bytes([0b00001010, 0])
        mask_digest = f'sha256:{hashlib.sha256(mask_bytes).hexdigest()}'
        prompt_state = {
            'rgbDigest': f'sha256:{"1" * 64}',
            'digest': f'sha256:{"2" * 64}',
            'points': [
                {'promptId': 'point-b', 'xPx': 3, 'yPx': 2, 'polarity': 'exclude'},
                {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
            ],
            'boxes': [
                {
                    'promptId': 'box-b',
                    'polarity': 'include',
                    'x0Px': 2,
                    'y0Px': 0,
                    'x1Px': 3,
                    'y1Px': 1,
                },
                {
                    'promptId': 'box-a',
                    'polarity': 'include',
                    'x0Px': 0,
                    'y0Px': 1,
                    'x1Px': 1,
                    'y1Px': 2,
                },
            ],
            'maskConstraints': [{
                'promptId': 'mask-a',
                'polarity': 'include',
                'artifact': {
                    'encoding': 'bitset-lsb-v1',
                    'width': 4,
                    'height': 3,
                    'data': base64.b64encode(mask_bytes).decode('ascii'),
                    'digest': mask_digest,
                },
            }],
            'textPrompts': [],
        }

        capabilities = sam31_visual_prompt_capabilities()
        program = compile_sam31_visual_prompt_program(
            prompt_state,
            width=4,
            height=3,
            capabilities=capabilities,
        )

        self.assertEqual(
            program.compiler_policy_version,
            SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
        )
        self.assertEqual(
            [point.prompt_id for point in program.points], ['point-a', 'point-b']
        )
        self.assertEqual(
            [box.prompt_id for box in program.boxes], ['box-a', 'box-b']
        )
        self.assertEqual(
            program.boxes[0].normalized_xywh,
            (0.0, 1 / 3, 0.5, 2 / 3),
        )
        self.assertEqual(program.positive_mask_constraint, mask_bytes)
        self.assertEqual(
            program.diagnostics['compiledPromptIds'],
            ['point-a', 'point-b', 'box-a', 'box-b', 'mask-a'],
        )

    def test_declares_only_validated_visual_support(self) -> None:
        capabilities = sam31_visual_prompt_capabilities()

        self.assertTrue(capabilities['boxes'])
        self.assertTrue(capabilities['maskInput'])
        self.assertFalse(capabilities['negativeBoxes'])
        self.assertFalse(capabilities['negativeMaskConstraints'])
        self.assertEqual(capabilities['text'], False)
        self.assertIn('negative-box', capabilities['unsupportedPromptReasons'])

    def test_rejects_mask_padding_bits_before_inference(self) -> None:
        mask_bytes = bytes([0b11111111])
        prompt_state = {
            'rgbDigest': f'sha256:{"1" * 64}',
            'digest': f'sha256:{"2" * 64}',
            'points': [],
            'boxes': [],
            'maskConstraints': [{
                'promptId': 'mask-a',
                'polarity': 'include',
                'artifact': {
                    'encoding': 'bitset-lsb-v1',
                    'width': 2,
                    'height': 2,
                    'data': base64.b64encode(mask_bytes).decode('ascii'),
                    'digest': f'sha256:{hashlib.sha256(mask_bytes).hexdigest()}',
                },
            }],
            'textPrompts': [],
        }

        with self.assertRaisesRegex(
            MaskSessionError, 'outside its dimensions'
        ):
            compile_sam31_visual_prompt_program(
                prompt_state,
                width=2,
                height=2,
                capabilities=sam31_visual_prompt_capabilities(),
            )

# The fake SAM predictor never decodes the frame; these bytes only need a
# stable identity so the RGB digest binding can be verified end to end.
IMAGE_PNG = b'\x89PNG\r\n\x1a\nanchor-rgb-frame'
IMAGE_DIGEST = f'sha256:{hashlib.sha256(IMAGE_PNG).hexdigest()}'
IMAGE_WIDTH = 2
IMAGE_HEIGHT = 2

# One foreground pixel at (1, 0): bit index 1 of a single bitset byte.
ACCEPTED_MASK_BITS = bytes([0b00000010])
ACCEPTED_MASK_BASE64 = base64.b64encode(ACCEPTED_MASK_BITS).decode('ascii')


class FakeSam3Predictor:
    """Records the public SAM session API and returns a configurable mask."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.materialized_png: bytes | None = None
        self.masks: list[list[list[bool]]] = [[[False, True], [False, False]]]
        self.probs: list[float] = [0.9]
        self.add_prompt_started: Event | None = None
        self.add_prompt_release: Event | None = None

    def handle_request(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        if request['type'] == 'start_session':
            frame_path = Path(str(request['resource_path'])) / '000000.png'
            self.materialized_png = frame_path.read_bytes()
            return {'session_id': 'sam-session'}
        if request['type'] == 'add_prompt':
            if self.add_prompt_started is not None:
                self.add_prompt_started.set()
            if self.add_prompt_release is not None and not self.add_prompt_release.wait(timeout=5):
                raise RuntimeError('test SAM prompt was never released')
            return {
                'outputs': {
                    'out_binary_masks': self.masks,
                    'out_probs': self.probs,
                }
            }
        return {'is_success': True}

    @property
    def session_starts(self) -> int:
        return sum(1 for request in self.requests if request['type'] == 'start_session')

    def request_types(self) -> list[object]:
        return [request['type'] for request in self.requests]


class FakeSam3InteractivePredictor:
    """Records the locked interactive-image API without requiring CUDA."""

    def __init__(self) -> None:
        prompt_encoder = type(
            'FakePromptEncoder',
            (),
            {'mask_input_size': (IMAGE_HEIGHT, IMAGE_WIDTH)},
        )()
        self.model = type(
            'FakeInteractiveModel',
            (),
            {'sam_prompt_encoder': prompt_encoder},
        )()
        self.requests: list[dict[str, object]] = []
        self.masks: list[list[list[bool]]] = [
            [[False, True], [False, False]],
        ]
        self.scores: list[float] = [0.9]

    def predict(self, **request: object) -> tuple[object, object, object]:
        self.requests.append(request)
        return self.masks, self.scores, []


class AISelectMaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.lock_file = self.directory / 'uv.lock'
        self.lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', self.lock_file)

        weights = self.directory / 'sam31.pt'
        weights.write_bytes(b'separately acquired sam3.1 weights')
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        manifest = self.directory / 'sam31.json'
        manifest.write_text(
            json.dumps({
                'digest': 'sha256:sam31-v1',
                'adapterId': 'sam3.1',
                'modelName': 'SAM 3.1',
                'checkpointDigest': f'sha256:{checkpoint_digest}',
                'sourceCommit': 'sam3-source-v1',
                'licenseName': 'SAM License',
                'licenseUrl': 'https://example.test/sam-license',
                'runtimeConfigDigest': SAM31_RUNTIME_CONFIG_DIGEST,
            }),
            encoding='utf-8',
        )
        self.model_manifest_digest = self.state.install_model(manifest, weights)['digest']

        self.predictor = FakeSam3Predictor()
        self.state.mask_adapters['sam3.1'] = Sam3PointMaskAdapter(
            build_predictor=lambda model: self.predictor
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

    @staticmethod
    def prompt_state_digest(prompt_state: dict[str, object]) -> str:
        payload = {
            key: value
            for key, value in prompt_state.items()
            if key != 'digest'
        }
        encoded = json.dumps(
            payload,
            separators=(',', ':'),
            sort_keys=True,
        ).encode()
        return f'sha256:{hashlib.sha256(encoded).hexdigest()}'

    def request_body(self) -> dict[str, object]:
        points = [
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
        ]
        prompt_state: dict[str, object] = {
            'schemaVersion': 1,
            'viewId': 'anchor-view',
            'rgbDigest': IMAGE_DIGEST,
            'revision': 1,
            'points': points,
            'boxes': [],
            'maskConstraints': [],
            'textPrompts': [],
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
            'rgb': {
                'pngBase64': base64.b64encode(IMAGE_PNG).decode('ascii'),
                'digest': IMAGE_DIGEST,
                'width': IMAGE_WIDTH,
                'height': IMAGE_HEIGHT,
            },
            'promptState': prompt_state,
            'modelManifestDigest': self.model_manifest_digest,
            'adapterCapabilityDigest': prompt_capabilities['capabilityDigest'],
            'proposalPolicyVersion': 'auto-mask-proposals/bounded-source-order-v1',
            'rankingPolicyVersion': 'anchor-mask-ranking/v1',
        }

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
        self.assertEqual(self.predictor.requests, [])

    def test_produces_a_bound_single_frame_sam_proposal(self) -> None:
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
        self.assertEqual(proposal_set['proposalAttemptId'], 'proposal-attempt-1')
        self.assertEqual(len(proposal_set['proposals']), 1)
        proposal = proposal_set['proposals'][0]
        self.assertEqual(proposal['sourceIndex'], 0)
        self.assertEqual(
            proposal['promptConsistency'],
            {
                'positivePointsSatisfied': True,
                'negativePointsSatisfied': True,
            },
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
            'anchor-mask-ranking/v1',
        )

        # A single-view Frame Set is one SAM pass: start, prompt frame zero,
        # close; never video propagation.
        self.assertEqual(
            self.predictor.request_types(),
            ['start_session', 'add_prompt', 'close_session'],
        )
        self.assertEqual(self.predictor.materialized_png, IMAGE_PNG)
        add_prompt = self.predictor.requests[1]
        self.assertEqual(add_prompt['session_id'], 'sam-session')
        self.assertEqual(add_prompt['frame_index'], 0)
        self.assertEqual(add_prompt['points'], [[1, 0]])
        self.assertEqual(add_prompt['point_labels'], [1])

    def test_proposal_digest_survives_browser_json_number_round_trip(self) -> None:
        # The locked adapter can publish an exact 1.0 score. The digest binds
        # its binary64 value instead of a Python- or JavaScript-specific
        # lexical JSON spelling.
        self.predictor.probs = [1.0]

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

    def test_rejects_an_rgb_digest_mismatch(self) -> None:
        request = self.request_body()
        request['rgb']['digest'] = (  # type: ignore[index]
            f'sha256:{hashlib.sha256(b"not the anchor frame").hexdigest()}'
        )

        self.assert_invalid_request(request)

    def test_rejects_a_malformed_rgb_digest(self) -> None:
        request = self.request_body()
        request['rgb']['digest'] = 'not-a-digest'  # type: ignore[index]

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
                request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
                    request['promptState']  # type: ignore[arg-type]
                )
                self.assert_invalid_request(request)

    def test_rejects_an_empty_prompt_list(self) -> None:
        request = self.request_body()
        request['promptState']['points'] = []  # type: ignore[index]
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )

        self.assert_invalid_request(request)

    def test_rejects_an_unknown_prompt_polarity(self) -> None:
        request = self.request_body()
        request['promptState']['points'] = [  # type: ignore[index]
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'maybe'},
        ]
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )

        self.assert_invalid_request(request)

    def test_reports_an_unavailable_model_manifest(self) -> None:
        request = self.request_body()
        request['modelManifestDigest'] = 'sha256:missing-manifest'

        status, payload = self.post_proposal_error(request)

        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], 'modelUnavailable')
        self.assertEqual(self.predictor.requests, [])

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

        status, payload = self.post_proposal_error(request)

        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], 'incompatibleManifest')
        self.assertEqual(self.predictor.requests, [])

    def test_rejects_a_stale_adapter_capability_identity(self) -> None:
        request = self.request_body()
        request['adapterCapabilityDigest'] = f'sha256:{"f" * 64}'

        status, payload = self.post_proposal_error(request)

        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], 'capabilityMismatch')
        self.assertEqual(self.predictor.requests, [])

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
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )

        status, payload = self.post_proposal_error(request)

        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], 'unsupportedPromptType')
        self.assertEqual(self.predictor.requests, [])

    def test_forwards_positive_box_and_mask_constraint_to_the_visual_adapter(self) -> None:
        interactive_predictor = FakeSam3InteractivePredictor()
        self.state.mask_adapters['sam3.1'] = Sam3PointMaskAdapter(
            build_predictor=lambda model: self.predictor,
            build_interactive_predictor=lambda model, rgb_png: interactive_predictor,
        )
        request = self.request_body()
        request['promptState']['boxes'] = [{  # type: ignore[index]
            'promptId': 'box-1',
            'polarity': 'include',
            'x0Px': 0,
            'y0Px': 0,
            'x1Px': 1,
            'y1Px': 1,
        }]
        request['promptState']['maskConstraints'] = [{  # type: ignore[index]
            'promptId': 'constraint-1',
            'polarity': 'include',
            'artifact': {
                'encoding': 'bitset-lsb-v1',
                'width': IMAGE_WIDTH,
                'height': IMAGE_HEIGHT,
                'data': ACCEPTED_MASK_BASE64,
                'digest': f'sha256:{hashlib.sha256(ACCEPTED_MASK_BITS).hexdigest()}',
            },
        }]
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )
        capabilities = self.state.capabilities([EDITOR_ORIGIN])['modelManifests'][0][
            'promptCapabilities'
        ]
        request['adapterCapabilityDigest'] = capabilities['capabilityDigest']

        response = self.post_proposals(request)

        self.assertTrue(capabilities['boxes'])
        self.assertTrue(capabilities['maskInput'])
        self.assertFalse(capabilities['negativeBoxes'])
        self.assertFalse(capabilities['negativeMaskConstraints'])
        self.assertEqual(len(interactive_predictor.requests), 1)
        adapter_request = interactive_predictor.requests[0]
        self.assertEqual(adapter_request['point_coords'], [[1, 0]])
        self.assertEqual(adapter_request['point_labels'], [1])
        self.assertEqual(adapter_request['box'], [[0, 0, 1, 1]])
        self.assertEqual(
            adapter_request['mask_input'].tolist(),
            [[[0.0, 1.0], [0.0, 0.0]]],
        )
        self.assertTrue(adapter_request['normalize_coords'])
        proposal = response['proposalSet']['proposals'][0]
        self.assertTrue(proposal['promptConsistency']['positiveBoxesSatisfied'])
        self.assertTrue(proposal['promptConsistency']['maskConstraintsSatisfied'])
        self.assertEqual(
            [(item['family'], item['promptId']) for item in proposal['promptDiagnostics']],
            [
                ('point', 'prompt-1'),
                ('box', 'box-1'),
                ('mask-constraint', 'constraint-1'),
            ],
        )

    def test_visual_prompt_contradiction_is_ineligible_for_07a_selection(self) -> None:
        interactive_predictor = FakeSam3InteractivePredictor()
        self.state.mask_adapters['sam3.1'] = Sam3PointMaskAdapter(
            build_predictor=lambda model: self.predictor,
            build_interactive_predictor=lambda model, rgb_png: interactive_predictor,
        )
        request = self.request_body()
        disjoint_constraint = bytes([0b00000100])
        request['promptState']['maskConstraints'] = [{  # type: ignore[index]
            'promptId': 'constraint-1',
            'polarity': 'include',
            'artifact': {
                'encoding': 'bitset-lsb-v1',
                'width': IMAGE_WIDTH,
                'height': IMAGE_HEIGHT,
                'data': base64.b64encode(disjoint_constraint).decode('ascii'),
                'digest': (
                    f'sha256:{hashlib.sha256(disjoint_constraint).hexdigest()}'
                ),
            },
        }]
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )
        request['adapterCapabilityDigest'] = self.state.capabilities(
            [EDITOR_ORIGIN]
        )['modelManifests'][0]['promptCapabilities']['capabilityDigest']

        response = self.post_proposals(request)

        proposal = response['proposalSet']['proposals'][0]
        self.assertFalse(
            proposal['promptConsistency']['maskConstraintsSatisfied']
        )
        self.assertFalse(proposal['rankingFeatures']['eligible'])
        self.assertEqual(response['proposalDecision']['status'], 'unavailable')
        self.assertNotIn('selectedProposalId', response['proposalDecision'])

    def test_publishes_an_empty_proposal_set_when_the_adapter_finds_no_mask(
        self,
    ) -> None:
        self.predictor.masks = [[[False, False], [False, False]]]

        first = self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(first['proposalSet']['proposals'], [])
        self.assertEqual(first['proposalDecision']['status'], 'unavailable')
        self.assertEqual(self.predictor.session_starts, 1)

        replayed = self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(replayed, first)
        self.assertEqual(self.predictor.session_starts, 1)

        retry = self.request_body()
        retry['proposalAttemptId'] = 'proposal-attempt-2'
        retried = self.state.produce_ai_select_mask(retry)
        self.assertEqual(retried['proposalSet']['proposals'], [])
        self.assertEqual(retried['proposalDecision']['status'], 'unavailable')
        self.assertEqual(self.predictor.session_starts, 2)

    def test_preserves_nested_part_and_whole_candidates_as_ambiguous(self) -> None:
        # Both candidates contain the positive point. The first is a local
        # part; the second strictly contains it and adds neighbouring area.
        self.predictor.masks = [
            [[False, True], [False, False]],
            [[True, True], [True, False]],
        ]
        # The oversized candidate deliberately has the much higher raw model
        # score. Ranking must still surface the geometric ambiguity.
        self.predictor.probs = [0.1, 0.99]

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

    def test_publishes_no_proposal_for_a_point_inconsistent_mask(self) -> None:
        # The candidate covers (1, 0) only; prompting (0, 1) rejects it.
        request = self.request_body()
        request['promptState']['points'] = [  # type: ignore[index]
            {'promptId': 'prompt-1', 'xPx': 0, 'yPx': 1, 'polarity': 'include'},
        ]
        request['promptState']['digest'] = self.prompt_state_digest(  # type: ignore[index]
            request['promptState']  # type: ignore[arg-type]
        )

        response = self.state.produce_ai_select_mask(request)

        self.assertEqual(response['proposalSet']['proposals'], [])

    def test_replays_a_matching_mask_request_without_a_second_sam_pass(self) -> None:
        first = self.state.produce_ai_select_mask(self.request_body())
        replay = self.state.produce_ai_select_mask(self.request_body())

        self.assertEqual(replay, first)
        self.assertEqual(self.predictor.session_starts, 1)

        # An explicit Retry mints a new attempt identity for the same RGB and
        # prompts and really reruns the adapter.
        retry_request = self.request_body()
        retry_request['proposalAttemptId'] = 'proposal-attempt-2'
        retry = self.state.produce_ai_select_mask(retry_request)

        self.assertEqual(retry['proposalAttemptId'], 'proposal-attempt-2')
        self.assertEqual(
            retry['proposalSet']['proposals'],
            first['proposalSet']['proposals'],
        )
        self.assertEqual(self.predictor.session_starts, 2)

    def test_a_concurrent_matching_request_joins_the_same_sam_pass(self) -> None:
        self.predictor.add_prompt_started = Event()
        self.predictor.add_prompt_release = Event()
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
        self.assertTrue(self.predictor.add_prompt_started.wait(timeout=1))
        duplicate.start()
        self.assertTrue(duplicate_started.wait(timeout=1))

        self.predictor.add_prompt_release.set()
        first.join(timeout=5)
        duplicate.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(duplicate.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.predictor.session_starts, 1)

    def test_mask_request_holds_the_single_companion_capacity_lease(self) -> None:
        self.predictor.add_prompt_started = Event()
        self.predictor.add_prompt_release = Event()
        worker = Thread(
            target=lambda: self.state.produce_ai_select_mask(self.request_body()),
            daemon=True,
        )
        worker.start()
        self.assertTrue(self.predictor.add_prompt_started.wait(timeout=1))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['capacity']['activeSessions'],
            1,
        )

        competing_request = self.request_body()
        competing_request['proposalAttemptId'] = 'proposal-attempt-2'
        with self.assertRaisesRegex(MaskSessionError, 'already serving another'):
            self.state.produce_ai_select_mask(competing_request)

        self.predictor.add_prompt_release.set()
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
        self.state.mask_adapters['sam3.1'] = broken_adapter  # type: ignore[assignment]

        with self.assertRaises(MaskSessionError) as error:
            self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(error.exception.code, 'incompleteMaskSet')

        # The failed attempt publishes nothing and replays the same failure.
        with self.assertRaises(MaskSessionError) as replayed:
            self.state.produce_ai_select_mask(self.request_body())
        self.assertEqual(replayed.exception.code, 'incompleteMaskSet')
        self.assertEqual(broken_adapter.invocations, 1)

    def test_adapter_oom_publishes_no_partial_proposal_set(self) -> None:
        class OutOfMemoryMaskAdapter:
            def __init__(self) -> None:
                self.invocations = 0

            def produce_tracks(self, **_kwargs: Any) -> MaskProduction:
                self.invocations += 1
                raise RuntimeError('CUDA out of memory')

        adapter = OutOfMemoryMaskAdapter()
        self.state.mask_adapters['sam3.1'] = adapter  # type: ignore[assignment]

        status, payload = self.post_proposal_error(self.request_body())

        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload['status'], 'maskProposalError')
        self.assertEqual(payload['code'], 'modelFailure')

        # The failed attempt contains no proposalSet and replays atomically
        # without a second adapter execution.
        self.assertNotIn('proposalSet', payload)
        status, replay = self.post_proposal_error(self.request_body())
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(replay['code'], 'modelFailure')
        self.assertNotIn('proposalSet', replay)
        self.assertEqual(adapter.invocations, 1)


if __name__ == '__main__':
    unittest.main()

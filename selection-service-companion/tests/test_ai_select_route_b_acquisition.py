from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import struct
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

import numpy as np

from selection_service_companion.image_instance_prompt_synthesis import (
    AI_SELECT_IMAGE_INSTANCE_PROMPT_SYNTHESIS_POLICY_VERSION,
    LimitedImageInstancePrompt,
    prompt_synthesis_policy_digest,
    synthesize_image_instance_prompt,
)
from selection_service_companion.image_instance_mask_contract import (
    create_image_instance_prompt_artifact,
)
from selection_service_companion.masking import (
    SAM3_IMAGE_INSTANCE_ADAPTER_ID,
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    Sam3ImageInstanceAdapter,
    sam3_image_instance_capabilities,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import (
    CompanionState,
    _route_b_camera_binding_digest,
    _route_b_review_box_xyxy,
)


EDITOR_ORIGIN = 'https://editor.example'
CAMERA: dict[str, object] = {
    'revision': 100,
    'cameraToWorld': [
        1.0, 0.0, 0.0, 0.5,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ],
    'projection': {
        'model': 'pinhole',
        'fx': 10.0,
        'fy': 10.0,
        'cx': 2.0,
        'cy': 2.0,
        'width': 4,
        'height': 4,
        'near': 0.1,
        'far': 100.0,
    },
    'conventionVersion': 'opencv-camera-to-world/v1',
}


def _digest(value: object) -> str:
    return 'sha256:' + hashlib.sha256(
        json.dumps(value, separators=(',', ':'), sort_keys=True, allow_nan=False).encode(
            'utf-8'
        )
    ).hexdigest()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack('>I', len(payload))
        + kind
        + payload
        + struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _rgb_artifact(width: int = 4, height: int = 4) -> dict[str, object]:
    raw = b''.join(b'\x00' + bytes([20, 40, 60]) * width for _ in range(height))
    png = b''.join((
        b'\x89PNG\r\n\x1a\n',
        _png_chunk(
            b'IHDR',
            struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0),
        ),
        _png_chunk(b'IDAT', zlib.compress(raw)),
        _png_chunk(b'IEND', b''),
    ))
    return {
        'pngBase64': base64.b64encode(png).decode('ascii'),
        'digest': 'sha256:' + hashlib.sha256(png).hexdigest(),
        'width': width,
        'height': height,
    }


def _mask_artifact(bits: bytes) -> dict[str, object]:
    return {
        'encoding': 'bitset-lsb-v1',
        'width': 4,
        'height': 4,
        'data': base64.b64encode(bits).decode('ascii'),
        'digest': 'sha256:' + hashlib.sha256(bits).hexdigest(),
    }


def _request_binding() -> dict[str, object]:
    return {
        'targetContextId': 'context-1',
        'contextRevision': 7,
        'dependencyToken': {
            'splatId': 'splat-1',
            'renderStateToken': 'render-v1',
            'geometryToken': 'geometry-v1',
            'gaussianIdentityToken': 'ids-v1',
            'worldTransformToken': 'world-v1',
        },
    }


class FakeSam3ImageRuntime:
    """In-memory official-image seam; it has no video/tracker entry point."""

    def __init__(self) -> None:
        self.set_image_calls: list[bytes] = []
        self.predict_calls: list[dict[str, object]] = []
        self.return_empty = False
        self.raise_error = False

    def set_image(self, rgb_png: bytes) -> object:
        self.set_image_calls.append(rgb_png)
        return {'image': len(self.set_image_calls)}

    def predict_inst(self, inference_state: object, **kwargs: object) -> tuple[object, object, object]:
        self.predict_calls.append(dict(kwargs))
        if self.raise_error:
            raise RuntimeError('fake image runtime failure')
        if self.return_empty:
            return [], [], np.zeros((0, 288, 288), dtype=np.float32)
        mask = np.array([
            [False, False, False, False],
            [False, True, True, False],
            [False, True, True, False],
            [False, False, False, False],
        ])
        point_coords = kwargs.get('point_coords')
        point_labels = kwargs.get('point_labels')
        if point_coords is not None and point_labels is not None:
            for (x_px, y_px), label in zip(point_coords, point_labels, strict=True):
                if label == 1:
                    mask[int(y_px), int(x_px)] = True
        return (
            np.asarray([mask]),
            np.asarray([0.9], dtype=np.float32),
            np.zeros((1, 288, 288), dtype=np.float32),
        )


class RouteBAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        lock_file = self.directory / 'uv.lock'
        lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', lock_file)
        weights = self.directory / 'sam3-image.pt'
        weights.write_bytes(b'separately acquired sam3 image weights')
        checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        self.model_manifest_digest = 'sha256:' + ('a' * 64)
        manifest = self.directory / 'sam3-image.json'
        manifest.write_text(
            json.dumps({
                'digest': self.model_manifest_digest,
                'adapterId': SAM3_IMAGE_INSTANCE_ADAPTER_ID,
                'modelName': 'SAM 3 Image',
                'checkpointDigest': f'sha256:{checkpoint_digest}',
                'sourceCommit': 'sam3-source-v1',
                'licenseName': 'SAM License',
                'licenseUrl': 'https://example.test/sam-license',
                'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            }),
            encoding='utf-8',
        )
        self.state.install_model(manifest, weights)
        self.runtime = FakeSam3ImageRuntime()
        self.state.mask_adapters[SAM3_IMAGE_INSTANCE_ADAPTER_ID] = (
            Sam3ImageInstanceAdapter(build_model=lambda _model: self.runtime)
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
        self.rgb = _rgb_artifact()
        self.binding = _request_binding()
        self.hint = self._hint()
        self.plan = self._plan()
        self.capability_digest = sam3_image_instance_capabilities()['capabilityDigest']
        self.companion_instance_id = self.state.runtime_profile_capabilities(
            [EDITOR_ORIGIN]
        )['companionInstanceId']

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    def _hint(
        self, visible_points: list[list[float]] | None = None
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            'schemaVersion': 1,
            'targetContextId': self.binding['targetContextId'],
            'anchorCameraBindingDigest': _digest('anchor-camera'),
            'anchorRgbDigest': _digest('anchor-rgb'),
            'anchorStableMaskDigest': _digest('anchor-mask'),
            'geometryPolicyDigest': _digest('target-geometry/v1'),
            'centerWorld': [0.0, 0.0, 3.0],
            'extentWorld': [0.5, 0.5, 1.5],
            'visiblePoints': (
                visible_points
                if visible_points is not None
                else [
                    [0.0, 0.0, 5.0],
                    [0.25, 0.0, 2.0],
                    [0.125, -0.25, 2.0],
                ]
            ),
            'quality': 'usable',
            'reasons': [],
        }
        return {**payload, 'artifactDigest': _digest(payload)}

    def _plan(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'schemaVersion': 1,
            'targetContextId': self.binding['targetContextId'],
            'anchorStableMaskDigest': self.hint['anchorStableMaskDigest'],
            'targetGeometryHintDigest': self.hint['artifactDigest'],
            'localViewPolicyDigest': _digest('local-key-view-planner/v1'),
            'orderedViews': [{
                'viewId': 'key-view-0-0',
                'cameraBinding': CAMERA,
                'quality': 'usable',
                'reasons': [],
            }],
            'planAttemptId': 'local-key-view-plan-attempt-1',
        }
        return {**payload, 'artifactDigest': _digest(payload)}

    def request_json(self, path: str, body: dict[str, object]) -> dict[str, object]:
        with urlopen(
            Request(
                f'{self.endpoint}{path}',
                data=json.dumps(body).encode('utf-8'),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            )
        ) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    def post_error(
        self, path: str, body: dict[str, object], status: HTTPStatus
    ) -> dict[str, object]:
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    f'{self.endpoint}{path}',
                    data=json.dumps(body).encode('utf-8'),
                    method='POST',
                    headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
                )
            )
        self.assertEqual(error.exception.code, status)
        return json.load(error.exception)

    def _prompt_request(self, **overrides: object) -> dict[str, object]:
        return {
            'requestBinding': self.binding,
            'targetSplatId': 'splat-1',
            'viewId': 'key-view-0-0',
            'viewCameraBinding': CAMERA,
            'viewCameraBindingDigest': _route_b_camera_binding_digest(CAMERA),
            'rgb': self.rgb,
            'targetGeometryHint': self.hint,
            'localKeyViewPlan': self.plan,
            'adapterCapabilityDigest': self.capability_digest,
            'modelManifestDigest': self.model_manifest_digest,
            'runtimeDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            'companionInstanceId': self.companion_instance_id,
            'promptSynthesisAttemptId': 'prompt-attempt-1',
            'promptSynthesisPolicyVersion': (
                AI_SELECT_IMAGE_INSTANCE_PROMPT_SYNTHESIS_POLICY_VERSION
            ),
            **overrides,
        }

    def _inference_request(self, prompt: dict[str, object], **overrides: object) -> dict[str, object]:
        return {
            'schemaVersion': 1,
            'identity': {
                'targetContextId': self.binding['targetContextId'],
                'contextRevision': self.binding['contextRevision'],
                'viewId': 'key-view-0-0',
                'rgbDigest': self.rgb['digest'],
                'promptArtifactDigest': prompt['artifactDigest'],
                'adapterId': SAM3_IMAGE_INSTANCE_ADAPTER_ID,
                'modelManifestDigest': self.model_manifest_digest,
                'runtimeDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
                'companionInstanceId': self.companion_instance_id,
                'inferenceAttemptId': 'inference-attempt-1',
            },
            'rgb': {
                'rgbDigest': self.rgb['digest'],
                'width': self.rgb['width'],
                'height': self.rgb['height'],
                'artifact': self.rgb,
            },
            'prompt': prompt,
            **overrides,
        }

    def _review_request(
        self, prompt: dict[str, object], result: dict[str, object]
    ) -> dict[str, object]:
        return {
            'requestBinding': self.binding,
            'targetSplatId': 'splat-1',
            'viewId': 'key-view-0-0',
            'rgb': self.rgb,
            'prompt': prompt,
            'inferenceResultDigest': result['resultDigest'],
            'chosenMask': result['masks'][0],
            'reviewAttemptId': 'review-attempt-1',
            'reviewPolicyVersion': 'local-view-assessment/v2',
        }

    def test_prompt_synthesis_is_deterministic_and_binds_geometry_plan_rgb_and_camera(self) -> None:
        request = self._prompt_request()
        first = self.request_json('/ai-select/generated-view-prompts', request)
        second = self.request_json('/ai-select/generated-view-prompts', request)

        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'ready')
        prompt = first['prompt']
        self.assertEqual(prompt['positiveBox'], {'x0Px': 0, 'y0Px': 1, 'x1Px': 2, 'y1Px': 3})
        self.assertGreaterEqual(len(prompt['positivePoints']), 1)
        self.assertLessEqual(len(prompt['positivePoints']), 3)
        self.assertEqual(prompt['negativePoints'], [])
        self.assertFalse(prompt['multimaskOutput'])
        self.assertNotIn('previousLogitsRefDigest', prompt)
        self.assertEqual(prompt['rgbDigest'], self.rgb['digest'])
        self.assertEqual(prompt['targetGeometryHintDigest'], self.hint['artifactDigest'])
        self.assertEqual(prompt['localKeyViewPlanDigest'], self.plan['artifactDigest'])
        self.assertEqual(prompt['promptSynthesisPolicyDigest'], prompt_synthesis_policy_digest())

    def test_prompt_synthesis_reports_limited_support_and_rejects_legacy_payloads(self) -> None:
        unavailable_hint = {
            **self.hint,
            'visiblePoints': [[0.0, 0.0, -5.0]],
        }
        without_digest = {
            key: value for key, value in unavailable_hint.items()
            if key != 'artifactDigest'
        }
        unavailable_hint['artifactDigest'] = _digest(without_digest)
        plan_payload = {
            key: value
            for key, value in self.plan.items()
            if key != 'artifactDigest'
        }
        plan_payload['targetGeometryHintDigest'] = unavailable_hint['artifactDigest']
        unavailable_plan = {
            **plan_payload,
            'artifactDigest': _digest(plan_payload),
        }
        request = self._prompt_request(
            targetGeometryHint=unavailable_hint,
            localKeyViewPlan=unavailable_plan,
        )
        response = self.request_json('/ai-select/generated-view-prompts', request)
        self.assertEqual(response['status'], 'limited')
        self.assertNotIn('prompt', response)
        self.assertIn('no-in-frame-visible-surface-support', response['diagnostics'])

        legacy = self._prompt_request(maskPropagation={'policyVersion': 'generated-view-mask/v1'})
        payload = self.post_error(
            '/ai-select/generated-view-prompts', legacy, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_prompt_synthesis_rejects_a_camera_digest_that_does_not_bind_the_camera(self) -> None:
        payload = self.post_error(
            '/ai-select/generated-view-prompts',
            self._prompt_request(viewCameraBindingDigest=_digest('wrong-camera')),
            HTTPStatus.BAD_REQUEST,
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_inference_rejects_an_unpublished_generic_prompt_artifact(self) -> None:
        prompt = create_image_instance_prompt_artifact({
            'schemaVersion': 1,
            'targetContextId': self.binding['targetContextId'],
            'contextRevision': self.binding['contextRevision'],
            'viewId': 'key-view-0-0',
            'rgbDigest': self.rgb['digest'],
            'cameraBindingDigest': _route_b_camera_binding_digest(CAMERA),
            'targetGeometryHintDigest': self.hint['artifactDigest'],
            'localKeyViewPlanDigest': self.plan['artifactDigest'],
            'adapterCapabilityDigest': self.capability_digest,
            'promptSynthesisPolicyDigest': prompt_synthesis_policy_digest(),
            'positivePoints': [{'xPx': 1, 'yPx': 1}],
            'negativePoints': [],
            'positiveBox': {'x0Px': 1, 'y0Px': 1, 'x1Px': 3, 'y1Px': 3},
            'multimaskOutput': False,
        })
        payload = self.post_error(
            '/ai-select/image-instance-masks',
            self._inference_request(prompt),
            HTTPStatus.CONFLICT,
        )
        self.assertEqual(payload['status'], 'imageInstanceMaskError')
        self.assertEqual(payload['code'], 'stalePrompt')

    def test_independent_single_mask_inference_and_review_use_no_tracker_or_logits_payload(self) -> None:
        prompt_response = self.request_json(
            '/ai-select/generated-view-prompts', self._prompt_request()
        )
        prompt = prompt_response['prompt']
        request = self._inference_request(prompt)
        result = self.request_json('/ai-select/image-instance-masks', request)

        self.assertEqual(result['requestIdentity'], request['identity'])
        self.assertEqual(len(result['masks']), 1)
        self.assertEqual(len(result['modelScores']), 1)
        self.assertEqual(result['diagnostics'], {'outcome': 'available'})
        self.assertNotIn('previousLogitsRefs', result)
        self.assertEqual(len(self.runtime.set_image_calls), 1)
        self.assertEqual(len(self.runtime.predict_calls), 1)
        self.assertFalse(self.runtime.predict_calls[0]['multimask_output'])
        self.assertFalse(hasattr(self.runtime, 'handle_request'))

        review = self.request_json(
            '/ai-select/image-instance-mask-reviews',
            self._review_request(prompt, result),
        )
        self.assertEqual(review['assessment']['status'], 'good')
        self.assertEqual(review['chosenMaskDigest'], result['masks'][0]['digest'])
        self.assertEqual(review['inferenceResultDigest'], result['resultDigest'])
        self.assertNotIn('publication', review)

        forged = self._review_request(prompt, result)
        forged['chosenMask'] = _mask_artifact(b'\x00\x00')
        payload = self.post_error(
            '/ai-select/image-instance-mask-reviews',
            forged,
            HTTPStatus.CONFLICT,
        )
        self.assertEqual(payload['status'], 'imageInstanceMaskReviewError')
        self.assertEqual(payload['code'], 'staleInferenceResult')

    def test_single_pixel_prompt_box_reaches_mask_review(self) -> None:
        self.hint = self._hint(visible_points=[[0.5, 0.0, 5.0]])
        self.plan = self._plan()
        prompt = self.request_json(
            '/ai-select/generated-view-prompts', self._prompt_request()
        )['prompt']
        box = prompt['positiveBox']
        self.assertEqual(box['x1Px'], box['x0Px'] + 1)
        self.assertEqual(box['y1Px'], box['y0Px'] + 1)

        result = self.request_json(
            '/ai-select/image-instance-masks', self._inference_request(prompt)
        )
        review = self.request_json(
            '/ai-select/image-instance-mask-reviews',
            self._review_request(prompt, result),
        )
        self.assertEqual(review['assessment']['status'], 'good')

    def test_semantic_unavailable_is_completed_result_while_technical_failure_is_distinct(self) -> None:
        prompt = self.request_json(
            '/ai-select/generated-view-prompts', self._prompt_request()
        )['prompt']
        self.runtime.return_empty = True
        unavailable = self.request_json(
            '/ai-select/image-instance-masks', self._inference_request(prompt)
        )
        self.assertEqual(unavailable['masks'], [])
        self.assertEqual(unavailable['diagnostics'], {'outcome': 'unavailable'})

        self.runtime.return_empty = False
        self.runtime.raise_error = True
        failed_request = self._inference_request(
            prompt,
            identity={
                **self._inference_request(prompt)['identity'],
                'inferenceAttemptId': 'inference-attempt-2',
            },
        )
        failure = self.post_error(
            '/ai-select/image-instance-masks', failed_request, HTTPStatus.CONFLICT
        )
        self.assertEqual(failure['status'], 'imageInstanceMaskError')
        self.assertEqual(failure['code'], 'modelFailure')

    def test_capabilities_advertise_route_b_and_not_the_retired_generated_mask_route(self) -> None:
        capabilities = self.state.capabilities([EDITOR_ORIGIN])
        operations = capabilities['supportedOperations']
        self.assertIn('aiSelectGeneratedViewPromptSynthesis', operations)
        self.assertIn('aiSelectImageInstanceMasks', operations)
        self.assertIn('aiSelectImageInstanceMaskReview', operations)
        self.assertNotIn('aiSelectGeneratedViewMasks', operations)


class PromptSynthesisUnitTests(unittest.TestCase):
    def test_camera_digest_matches_the_browser_json_stringify_golden_vector(self) -> None:
        self.assertEqual(
            _route_b_camera_binding_digest(CAMERA),
            'sha256:622d335e24b616c2bc162f61f46c4670b06668b3391f259caf6b18a905079dac',
        )

    def test_review_converts_an_exclusive_prompt_box_without_expanding_it(self) -> None:
        self.assertEqual(
            _route_b_review_box_xyxy(
                {'x0Px': 2, 'y0Px': 3, 'x1Px': 11, 'y1Px': 13},
                width=20,
                height=20,
            ),
            (2, 3, 10, 12),
        )

    def test_rejects_fully_off_image_support_instead_of_inventing_a_full_frame_box(self) -> None:
        synthesized = synthesize_image_instance_prompt(
            visible_points=[[-10.0, -10.0, 5.0], [10.0, 10.0, 5.0]],
            camera_binding=CAMERA,
            width=4,
            height=4,
        )
        self.assertIsNotNone(synthesized)
        assert synthesized is not None
        self.assertIsInstance(synthesized, LimitedImageInstancePrompt)
        self.assertIn('target-projection-clipped', synthesized.diagnostics)
        self.assertIn('target-materially-clipped', synthesized.diagnostics)

    def test_keeps_near_edge_in_frame_support_as_a_clipped_prompt(self) -> None:
        synthesized = synthesize_image_instance_prompt(
            visible_points=[[0.0, 0.0, 5.0], [1.3, 0.0, 5.0]],
            camera_binding=CAMERA,
            width=4,
            height=4,
        )
        self.assertIsNotNone(synthesized)
        assert synthesized is not None
        self.assertNotIsInstance(synthesized, LimitedImageInstancePrompt)
        self.assertIn('target-projection-clipped', synthesized.diagnostics)


if __name__ == '__main__':
    unittest.main()

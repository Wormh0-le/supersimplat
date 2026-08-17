from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import struct
import tempfile
from threading import Event, Thread
from typing import Any
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion import state as state_module
from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.digests import route_b_artifact_digest
from selection_service_companion.masking import (
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState
from selection_service_companion.target_geometry import (
    AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
    AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
    local_key_view_policy_digest,
    target_geometry_policy_digest,
)


EDITOR_ORIGIN = 'https://editor.example'
RGB_DIGEST = 'sha256:' + hashlib.sha256(b'anchor-rgb').hexdigest()
# Editor-computed and opaque to the Companion: format-valid, never recomputed.
CAMERA_DIGEST = 'sha256:' + hashlib.sha256(b'anchor-camera-binding').hexdigest()

# Identity camera at the world origin: camera coordinates equal world
# coordinates, so every projection below is exact decimal arithmetic.
PACKED_CAMERA: dict[str, object] = {
    'revision': 0,
    'cameraToWorld': [
        1.0, 0.0, 0.0, 0.0,
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

# Hand-computed projections under PACKED_CAMERA (see test_ai_select_support_probe):
#   id 11 (0, 0, 5)        -> (2, 2) = pixel 10, first-hit depth 5
#   id 12 (0.25, 0, 2)     -> (3, 2) = pixel 11, first-hit depth 2
#   id 13 (0.125, -0.25, 2)-> (3, 1) = pixel 7, first-hit depth 2
#   id 14 (0, 0, -5)       -> behind the camera, excluded
#   id 15 (0, 0, 5)        -> logit -0.25 < 0 (opacity < 0.5), excluded
GAUSSIANS: tuple[tuple[int, tuple[float, float, float], float], ...] = (
    (11, (0.0, 0.0, 5.0), 1.0),
    (12, (0.25, 0.0, 2.0), 0.0),
    (13, (0.125, -0.25, 2.0), 2.0),
    (14, (0.0, 0.0, -5.0), 1.0),
    (15, (0.0, 0.0, 5.0), -0.25),
)

# 4x4 = 16 pixels = 2 bytes, LSB-first: pixel p is bit (p & 7) of byte (p >> 3).
FULL_MASK = bytes([0x80, 0x0C])     # pixels {7, 10, 11}: all three projections
EMPTY_MASK = bytes([0x01, 0x00])    # pixel {0}: foreground, but nothing projects there

# First-hit samples ordered by ascending source pixel index; id 11 at ~3.0
# from the provisional median (0.125, 0, 2) is separated support and drops
# out of the robust center/extent.
EXPECTED_CENTER = [0.1875, -0.125, 2.0]
EXPECTED_EXTENT = [0.0926625, 0.185325, 0.001]
# Formal visiblePoints contains only the retained support after robust
# separation filtering; the distant (0, 0, 5) sample is never a Prompt input.
EXPECTED_VISIBLE_POINTS = [[0.125, -0.25, 2.0], [0.25, 0.0, 2.0]]


def _render_scope(
    gaussian_count: int, *, target_row_count: int | None = None
) -> dict[str, object]:
    target_row_count = gaussian_count if target_row_count is None else target_row_count
    target_digest = 'sha256:' + 'b' * 64
    sources = [{
        'splatId': 'splat-1',
        'sourceContentDigest': target_digest,
        'gaussianCount': target_row_count,
    }]
    entries = [{
        'splatId': 'splat-1',
        'role': 'target',
        'sourceContentDigest': target_digest,
        'rowOffset': 0,
        'rowCount': target_row_count,
        'renderIdStart': GAUSSIANS[0][0],
    }]
    if target_row_count < gaussian_count:
        occluder_count = gaussian_count - target_row_count
        occluder_digest = 'sha256:' + 'c' * 64
        sources.append({
            'splatId': 'visible-occluder',
            'sourceContentDigest': occluder_digest,
            'gaussianCount': occluder_count,
        })
        entries.append({
            'splatId': 'visible-occluder',
            'role': 'occluder',
            'sourceContentDigest': occluder_digest,
            'rowOffset': target_row_count,
            'rowCount': occluder_count,
            'renderIdStart': GAUSSIANS[0][0] + target_row_count,
        })
    identity = json.dumps(
        {
            'policyId': 'visible-editor-splats-conservative/v1',
            'targetSplatId': 'splat-1',
            'sources': sources,
        },
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
    return {
        'policyId': 'visible-editor-splats-conservative/v1',
        'targetSplatId': 'splat-1',
        'identityDigest': 'sha256:' + hashlib.sha256(identity).hexdigest(),
        'entries': entries,
    }


def _binary_fixture(
    *, target_row_count: int | None = None
) -> tuple[bytes, BinarySceneSnapshotManifest]:
    count = len(GAUSSIANS)
    payload = b''.join(
        (
            b''.join(struct.pack('<I', stable_id) for stable_id, _, _ in GAUSSIANS),
            b''.join(struct.pack('<3f', *mean) for _, mean, _ in GAUSSIANS),
            struct.pack('<4f', 0.0, 0.0, 0.0, 1.0) * count,
            struct.pack('<3f', 0.0, 0.0, 0.0) * count,
            b''.join(struct.pack('<f', logit) for _, _, logit in GAUSSIANS),
            struct.pack('<3f', 0.0, 0.0, 0.0) * count,
        )
    )
    fields: list[dict[str, object]] = []
    offset = 0
    for name, scalar_type, components in (
        ('stableIds', 'uint32le', 1),
        ('means', 'float32le', 3),
        ('rotationsXyzw', 'float32le', 4),
        ('logScales', 'float32le', 3),
        ('logitOpacities', 'float32le', 1),
        ('dc', 'float32le', 3),
        ('sh', 'float32le', 0),
    ):
        byte_length = count * components * 4
        fields.append(
            {
                'name': name,
                'scalarType': scalar_type,
                'componentCount': components,
                'byteOffset': offset,
                'byteLength': byte_length,
            }
        )
        offset += byte_length
    content: dict[str, object] = {
        'protocolVersion': '1',
        'gaussianCount': count,
        'coordinateConvention': 'right-handed world coordinates; quaternion xyzw',
        'stableIdSchema': 'uint32',
        'attributeSchema': 'mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0',
        'appearancePolicy': 'effective-editor-dc-sh-bands-0',
        'renderConfiguration': {
            'version': 'supersplat-effective-rgb-v1',
            'backgroundRgba': [0.0, 0.0, 0.0, 1.0],
            'alphaMode': 'opaque-background',
            'shBands': 0,
            'rasterizer': 'playcanvas-gsplat-classic',
        },
        'authoritativeRenderScope': _render_scope(
            count, target_row_count=target_row_count
        ),
        'shFloatCountPerGaussian': 0,
        'payloadByteLength': len(payload),
        'fields': fields,
    }
    chunk_byte_length = 64
    chunks = tuple(
        BinarySceneSnapshotChunk(
            index=index,
            offset=index * chunk_byte_length,
            byte_length=len(
                payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]
            ),
            digest='sha256:'
            + hashlib.sha256(
                payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]
            ).hexdigest(),
        )
        for index in range((len(payload) + chunk_byte_length - 1) // chunk_byte_length)
    )
    content_digest = binary_scene_snapshot_content_digest(
        content,
        (payload[chunk.offset:chunk.offset + chunk.byte_length] for chunk in chunks),
    )
    return payload, BinarySceneSnapshotManifest(
        scene_id='splat-1',
        scene_version=content_digest,
        content_digest=content_digest,
        content=content,
        chunk_byte_length=chunk_byte_length,
        chunks=chunks,
    )


def _mask_payload(mask: bytes, width: int = 4, height: int = 4) -> dict[str, object]:
    return {
        'encoding': 'bitset-lsb-v1',
        'width': width,
        'height': height,
        'data': base64.b64encode(mask).decode('ascii'),
        'digest': 'sha256:' + hashlib.sha256(mask).hexdigest(),
    }


def _browser_json_number_round_trip(value: object) -> object:
    """Model JSON.parse/JSON.stringify's integral-number normalization."""

    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_browser_json_number_round_trip(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _browser_json_number_round_trip(item)
            for key, item in value.items()
        }
    return value


def _request_binding() -> dict[str, object]:
    return {
        'targetContextId': 'context-1',
        'contextRevision': 0,
        'dependencyToken': {
            'splatId': 'splat-1',
            'renderStateToken': 'render-v1',
            'geometryToken': 'geometry-v1',
            'gaussianIdentityToken': 'ids-v1',
            'worldTransformToken': 'world-v1',
        },
    }


def _hint_request_body(
    scene_version: str,
    mask: bytes,
    attempt: str = 'target-geometry-hint-attempt-1',
) -> dict[str, object]:
    return {
        'requestBinding': _request_binding(),
        'targetSplatId': 'splat-1',
        'sceneId': 'splat-1',
        'sceneVersion': scene_version,
        'renderConfigVersion': 'supersplat-effective-rgb-v1',
        'geometryAttemptId': attempt,
        'anchorCameraBinding': PACKED_CAMERA,
        'anchorCameraBindingDigest': CAMERA_DIGEST,
        'anchorRgbDigest': RGB_DIGEST,
        'anchorStableMask': _mask_payload(mask),
        'geometryPolicyVersion': AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
    }


def _plan_request_body(
    hint_response: dict[str, Any],
    *,
    batch: int = 0,
    attempt: str = 'local-key-view-plan-attempt-1',
) -> dict[str, object]:
    hint = hint_response['hint']
    return {
        'requestBinding': _request_binding(),
        'targetSplatId': 'splat-1',
        'planAttemptId': attempt,
        'batchOrdinal': batch,
        'anchorCameraBinding': PACKED_CAMERA,
        'anchorCameraBindingDigest': CAMERA_DIGEST,
        'anchorRgbDigest': RGB_DIGEST,
        'anchorStableMaskDigest': hint['anchorStableMaskDigest'],
        'targetGeometryHint': hint,
        'localViewPolicyVersion': AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
    }


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


class TargetGeometryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.lock_file = self.directory / 'uv.lock'
        self.lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', self.lock_file)
        self.payload, self.manifest = _binary_fixture()

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
        self.state.install_model(manifest, weights)
        self.state.mask_adapters['sam3.1'] = Sam3PointMaskAdapter()

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

    def request_json(
        self, path: str, method: str, body: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = None if body is None else json.dumps(body).encode('utf-8')
        with urlopen(
            Request(
                f'{self.endpoint}{path}',
                data=data,
                method=method,
                headers={
                    'Origin': EDITOR_ORIGIN,
                    'Content-Type': 'application/json',
                },
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
                    headers={
                        'Origin': EDITOR_ORIGIN,
                        'Content-Type': 'application/json',
                    },
                )
            )
        self.assertEqual(error.exception.code, status)
        return json.load(error.exception)

    def register_binary_snapshot(self) -> None:
        manifest = self.manifest
        admission = self.request_json(
            '/scene-snapshot-uploads/v1',
            'POST',
            {
                'format': manifest.format,
                'formatVersion': manifest.format_version,
                'sceneId': manifest.scene_id,
                'sceneVersion': manifest.scene_version,
                'contentDigest': manifest.content_digest,
                'content': manifest.content,
                'transfer': {
                    'chunkByteLength': manifest.chunk_byte_length,
                    'chunks': [
                        {
                            'index': chunk.index,
                            'offset': chunk.offset,
                            'byteLength': chunk.byte_length,
                            'digest': chunk.digest,
                        }
                        for chunk in manifest.chunks
                    ],
                },
            },
        )
        self.assertEqual(admission['status'], 'staged')
        upload_id = admission['uploadId']
        self.assertIsInstance(upload_id, str)
        for chunk in manifest.chunks:
            with urlopen(
                Request(
                    f'{self.endpoint}/scene-snapshot-uploads/v1/{upload_id}/chunks/{chunk.index}',
                    data=self.payload[chunk.offset:chunk.offset + chunk.byte_length],
                    method='PUT',
                    headers={
                        'Origin': EDITOR_ORIGIN,
                        'Content-Type': 'application/octet-stream',
                        'X-SceneSnapshot-Chunk-Digest': chunk.digest,
                    },
                )
            ) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
        committed = self.request_json(
            f'/scene-snapshot-uploads/v1/{upload_id}/commit', 'POST', {}
        )
        self.assertEqual(committed['status'], 'committed')

    def produce_hint(self, mask: bytes = FULL_MASK) -> dict[str, object]:
        return self.request_json(
            '/ai-select/target-geometry-hints',
            'POST',
            _hint_request_body(self.manifest.scene_version, mask),
        )

    def test_derives_the_target_geometry_hint_from_the_confirmed_anchor(self) -> None:
        self.register_binary_snapshot()
        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)

        response = self.request_json('/ai-select/target-geometry-hints', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], body['requestBinding'])
        self.assertEqual(response['targetSplatId'], 'splat-1')
        self.assertEqual(response['sceneId'], 'splat-1')
        self.assertEqual(response['sceneVersion'], self.manifest.scene_version)
        self.assertEqual(response['renderConfigVersion'], 'supersplat-effective-rgb-v1')
        self.assertEqual(response['geometryAttemptId'], 'target-geometry-hint-attempt-1')
        self.assertEqual(
            response['geometryPolicyVersion'], AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION
        )
        hint = response['hint']
        self.assertEqual(hint['schemaVersion'], 2)
        self.assertEqual(hint['targetContextId'], 'context-1')
        self.assertEqual(hint['anchorCameraBindingDigest'], CAMERA_DIGEST)
        self.assertEqual(hint['anchorRgbDigest'], RGB_DIGEST)
        self.assertEqual(
            hint['anchorStableMaskDigest'],
            'sha256:' + hashlib.sha256(FULL_MASK).hexdigest(),
        )
        self.assertEqual(hint['geometryPolicyDigest'], target_geometry_policy_digest())
        self.assertEqual(hint['centerWorld'], EXPECTED_CENTER)
        for actual, expected in zip(hint['extentWorld'], EXPECTED_EXTENT, strict=True):
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertEqual(hint['visiblePoints'], EXPECTED_VISIBLE_POINTS)
        self.assertEqual(hint['quality'], 'limited')
        self.assertEqual(hint['promptSupport'], 'limited')
        self.assertEqual(
            hint['reasons'],
            ['sparseSupport', 'separatedSupportFiltered', 'frameBoundaryContact'],
        )
        self.assertEqual(
            hint['artifactDigest'],
            route_b_artifact_digest(
                {key: value for key, value in hint.items() if key != 'artifactDigest'}
            ),
        )

    def test_hint_reports_a_bound_cache_miss_then_completes_after_registration(self) -> None:
        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)

        miss = self.request_json('/ai-select/target-geometry-hints', 'POST', body)

        self.assertEqual(miss['status'], 'sceneCacheMiss')
        self.assertEqual(miss['requestBinding'], body['requestBinding'])
        self.assertEqual(miss['geometryAttemptId'], 'target-geometry-hint-attempt-1')

        self.register_binary_snapshot()
        complete = self.request_json('/ai-select/target-geometry-hints', 'POST', body)
        self.assertEqual(complete['status'], 'complete')

    def test_hint_reports_a_spatial_cache_miss_without_the_working_set(self) -> None:
        body = {
            **_hint_request_body(self.manifest.scene_version, FULL_MASK),
            'sceneTransport': 'spatial-v1',
        }

        miss = self.request_json('/ai-select/target-geometry-hints', 'POST', body)

        self.assertEqual(miss['status'], 'sceneCacheMiss')
        self.assertEqual(miss['requestBinding'], body['requestBinding'])
        self.assertEqual(miss['geometryAttemptId'], 'target-geometry-hint-attempt-1')

    def test_hint_rejects_a_bad_request_binding(self) -> None:
        self.register_binary_snapshot()
        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)
        body['requestBinding'] = {
            **body['requestBinding'],
            'dependencyToken': {
                **body['requestBinding']['dependencyToken'],
                'splatId': 'splat-2',
            },
        }
        payload = self.post_error(
            '/ai-select/target-geometry-hints', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_hint_rejects_an_unsupported_policy_version(self) -> None:
        self.register_binary_snapshot()
        body = {
            **_hint_request_body(self.manifest.scene_version, FULL_MASK),
            'geometryPolicyVersion': 'target-geometry/v0',
        }
        payload = self.post_error(
            '/ai-select/target-geometry-hints', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_hint_rejects_a_stable_mask_digest_mismatch(self) -> None:
        self.register_binary_snapshot()
        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)
        body['anchorStableMask'] = {
            **body['anchorStableMask'],
            'digest': 'sha256:' + ('0' * 64),
        }
        payload = self.post_error(
            '/ai-select/target-geometry-hints', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_hint_fails_closed_when_the_mask_has_no_first_hit_support(self) -> None:
        self.register_binary_snapshot()
        body = _hint_request_body(self.manifest.scene_version, EMPTY_MASK)

        payload = self.post_error(
            '/ai-select/target-geometry-hints', body, HTTPStatus.CONFLICT
        )

        self.assertEqual(payload['status'], 'geometryHintError')
        self.assertEqual(payload['code'], 'geometryUnavailable')

    def test_visible_occluder_cannot_establish_target_geometry(self) -> None:
        self.payload, self.manifest = _binary_fixture(target_row_count=1)
        self.register_binary_snapshot()
        # Pixel 7 observes only an occluder row. The target row projects to
        # pixel 10 and must be the sole geometry-support authority.
        body = _hint_request_body(
            self.manifest.scene_version, bytes([0x80, 0x00])
        )

        payload = self.post_error(
            '/ai-select/target-geometry-hints', body, HTTPStatus.CONFLICT
        )

        self.assertEqual(payload['status'], 'geometryHintError')
        self.assertEqual(payload['code'], 'geometryUnavailable')

    def test_hint_replays_the_same_attempt_idempotently(self) -> None:
        self.register_binary_snapshot()
        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)

        first = self.request_json('/ai-select/target-geometry-hints', 'POST', body)
        replay = self.request_json('/ai-select/target-geometry-hints', 'POST', body)

        self.assertEqual(replay, first)

    def _run_gated_duplicate(
        self, second_body: dict[str, object] | None
    ) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object]]:
        """Block one hint attempt mid-derivation, race a second request, release."""

        original = state_module.derive_target_geometry_hint
        entered = Event()
        release = Event()

        def gated(*args: Any, **kwargs: Any) -> Any:
            entered.set()
            release.wait(10)
            return original(*args, **kwargs)

        body = _hint_request_body(self.manifest.scene_version, FULL_MASK)
        results: dict[str, Any] = {}

        def run_first() -> None:
            try:
                results['first'] = self.request_json(
                    '/ai-select/target-geometry-hints', 'POST', body
                )
            except HTTPError as error:
                results['first'] = {'error': error.code, 'body': json.load(error)}

        state_module.derive_target_geometry_hint = gated  # type: ignore[assignment]
        try:
            thread = Thread(target=run_first, daemon=True)
            thread.start()
            self.assertTrue(entered.wait(10))
            second: dict[str, object] | None = None
            if second_body is not None:
                try:
                    second = self.request_json(
                        '/ai-select/target-geometry-hints', 'POST', second_body
                    )
                except HTTPError as error:
                    second = {'error': error.code, 'body': json.load(error)}
            else:
                try:
                    second = self.request_json(
                        '/ai-select/target-geometry-hints', 'POST', body
                    )
                except HTTPError as error:
                    second = {'error': error.code, 'body': json.load(error)}
        finally:
            release.set()
            state_module.derive_target_geometry_hint = original  # type: ignore[assignment]
        thread.join(10)
        self.assertNotIn('error', results)
        return results['first'], second, body

    def test_hint_replays_a_concurrent_duplicate_attempt(self) -> None:
        self.register_binary_snapshot()

        first, second, _ = self._run_gated_duplicate(None)

        self.assertEqual(first['status'], 'complete')
        self.assertEqual(second, first)

    def test_hint_reports_capacity_full_while_another_attempt_runs(self) -> None:
        self.register_binary_snapshot()
        competing = _hint_request_body(
            self.manifest.scene_version, FULL_MASK, attempt='target-geometry-hint-attempt-2'
        )

        first, second, _ = self._run_gated_duplicate(competing)

        self.assertEqual(first['status'], 'complete')
        assert second is not None
        self.assertEqual(second['error'], HTTPStatus.CONFLICT)
        self.assertEqual(second['body']['status'], 'geometryHintError')
        self.assertEqual(second['body']['code'], 'capacityFull')

    def test_plans_the_first_bounded_local_key_view_batch(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)

        response = self.request_json('/ai-select/local-key-view-plans', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], body['requestBinding'])
        self.assertEqual(response['targetSplatId'], 'splat-1')
        self.assertEqual(response['planAttemptId'], 'local-key-view-plan-attempt-1')
        self.assertEqual(response['batchOrdinal'], 0)
        self.assertEqual(
            response['localViewPolicyVersion'], AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION
        )
        plan = response['plan']
        self.assertEqual(plan['schemaVersion'], 1)
        self.assertEqual(plan['targetContextId'], 'context-1')
        self.assertEqual(
            plan['anchorStableMaskDigest'],
            'sha256:' + hashlib.sha256(FULL_MASK).hexdigest(),
        )
        self.assertEqual(
            plan['targetGeometryHintDigest'], hint_response['hint']['artifactDigest']
        )
        self.assertEqual(plan['localViewPolicyDigest'], local_key_view_policy_digest())
        self.assertEqual(plan['planAttemptId'], 'local-key-view-plan-attempt-1')
        views = plan['orderedViews']
        self.assertEqual(
            [view['viewId'] for view in views],
            ['key-view-0-0', 'key-view-0-1', 'key-view-0-2', 'key-view-0-3'],
        )
        for view in views:
            self.assertEqual(view['quality'], 'usable')
            self.assertEqual(view['reasons'], [])
            camera = view['cameraBinding']
            self.assertEqual(camera['conventionVersion'], 'opencv-camera-to-world/v1')
            self.assertEqual(camera['projection'], PACKED_CAMERA['projection'])
            self.assertNotEqual(
                camera['cameraToWorld'], PACKED_CAMERA['cameraToWorld']
            )
        self.assertEqual(
            plan['artifactDigest'],
            route_b_artifact_digest(
                {key: value for key, value in plan.items() if key != 'artifactDigest'}
            ),
        )

    def test_plan_digest_survives_browser_json_number_round_trip(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)
        response = self.request_json('/ai-select/local-key-view-plans', 'POST', body)
        plan = _browser_json_number_round_trip(response['plan'])
        assert isinstance(plan, dict)

        parsed = self.state._parse_route_b_local_key_view_plan(
            plan,
            target_context_id=body['requestBinding']['targetContextId'],
            target_geometry_hint_digest=hint_response['hint']['artifactDigest'],
            view_id=plan['orderedViews'][0]['viewId'],
            view_camera_binding=plan['orderedViews'][0]['cameraBinding'],
        )

        self.assertEqual(parsed, plan)

    def test_plans_batch_one_with_append_view_ids(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(
            hint_response, batch=1, attempt='local-key-view-plan-attempt-2'
        )

        response = self.request_json('/ai-select/local-key-view-plans', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['batchOrdinal'], 1)
        self.assertEqual(
            [view['viewId'] for view in response['plan']['orderedViews']],
            ['key-view-1-0', 'key-view-1-1', 'key-view-1-2', 'key-view-1-3'],
        )

    def test_plan_reports_plan_exhausted_beyond_the_bounded_sequence(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(
            hint_response, batch=2, attempt='local-key-view-plan-attempt-3'
        )

        payload = self.post_error(
            '/ai-select/local-key-view-plans', body, HTTPStatus.CONFLICT
        )

        self.assertEqual(payload['status'], 'keyViewPlanError')
        self.assertEqual(payload['code'], 'planExhausted')

    def test_plan_rejects_a_tampered_hint_payload(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)
        tampered = _deep_copy(body['targetGeometryHint'])
        tampered['quality'] = 'usable'
        body['targetGeometryHint'] = tampered

        payload = self.post_error(
            '/ai-select/local-key-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_rejects_a_hint_target_context_mismatch(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)
        # A well-formed, self-consistent hint minted for another target still
        # fails the requestBinding identity binding.
        foreign = _deep_copy(body['targetGeometryHint'])
        foreign['targetContextId'] = 'context-9'
        foreign['artifactDigest'] = route_b_artifact_digest(
            {key: value for key, value in foreign.items() if key != 'artifactDigest'}
        )
        body['targetGeometryHint'] = foreign

        payload = self.post_error(
            '/ai-select/local-key-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_rejects_an_anchor_digest_mismatch(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)
        body['anchorRgbDigest'] = 'sha256:' + ('0' * 64)

        payload = self.post_error(
            '/ai-select/local-key-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_rejects_an_unsupported_policy_version(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = {
            **_plan_request_body(hint_response),
            'localViewPolicyVersion': 'local-key-view-planner/v0',
        }
        payload = self.post_error(
            '/ai-select/local-key-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_replays_the_same_attempt_idempotently(self) -> None:
        self.register_binary_snapshot()
        hint_response = self.produce_hint()
        body = _plan_request_body(hint_response)

        first = self.request_json('/ai-select/local-key-view-plans', 'POST', body)
        replay = self.request_json('/ai-select/local-key-view-plans', 'POST', body)

        self.assertEqual(replay, first)

    def test_capabilities_advertise_the_ticket_08_operations(self) -> None:
        expected = [
            'aiSelectAnchorRender',
            'aiSelectAnchorReferenceContributor',
            'aiSelectAnchorSupportProbe',
            'aiSelectMaskProposals',
            'autoMaskProposalSetSchemaV3',
            'aiSelectTargetGeometryHint',
            'aiSelectLocalKeyViewPlanning',
            'aiSelectGeneratedViewPromptSynthesis',
            'aiSelectImageInstanceMasks',
            'aiSelectImageInstanceMaskReview',
            'aiSelectReferenceCandidateReLift',
            'aiSelectProductionDirectEvidence',
            'binarySceneSnapshotRegistrationV1',
            'cameraAwareSpatialWorkingSetV1',
        ]

        runtime_profile = self.request_json('/capabilities', 'GET')
        self.assertEqual(runtime_profile['supportedOperations'], expected)
        legacy = self.state.capabilities([EDITOR_ORIGIN])
        self.assertEqual(legacy['supportedOperations'], expected)


if __name__ == '__main__':
    unittest.main()

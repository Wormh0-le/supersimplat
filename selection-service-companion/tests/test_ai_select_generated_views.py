from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
import math
from pathlib import Path
import struct
import tempfile
from threading import Event, Thread
from typing import Any, Mapping
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.generated_view_planning import (
    AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION,
    AI_SELECT_GENERATED_VIEW_PLANNER_VERSION,
    GENERATED_VIEW_PLAN_COUNT,
    derive_mask_support_seed,
    plan_first_generated_views,
    synthesize_view_prompts,
)
from selection_service_companion.gsplat_renderer import AnchorRenderArtifact
from selection_service_companion.masking import (
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState
from selection_service_companion.support_probe import AnchorSupportProbeCamera
from selection_service_companion.view_assessment import (
    AI_SELECT_LOCAL_VIEW_SUPPORT_POLICY_VERSION,
    AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
    local_view_support_diagnostic_id,
)


EDITOR_ORIGIN = 'https://editor.example'
RGB_DIGEST = 'sha256:' + hashlib.sha256(b'anchor-rgb').hexdigest()

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

# The same camera shifted +0.5 on world x: support projects to view pixels
# (1, 2), (1, 2), (0, 1) as hand-computed below.
VIEW_CAMERA: dict[str, object] = {
    **PACKED_CAMERA,
    'cameraToWorld': [
        1.0, 0.0, 0.0, 0.5,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ],
}

PROBE_CAMERA = AnchorSupportProbeCamera(
    world_to_camera=(
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ),
    fx=10.0,
    fy=10.0,
    cx=2.0,
    cy=2.0,
    width=4,
    height=4,
    near=0.1,
    far=100.0,
)

VIEW_PROBE_CAMERA = AnchorSupportProbeCamera(
    world_to_camera=(
        1.0, 0.0, 0.0, -0.5,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ),
    fx=10.0,
    fy=10.0,
    cx=2.0,
    cy=2.0,
    width=4,
    height=4,
    near=0.1,
    far=100.0,
)

# Hand-computed projections under PACKED_CAMERA (see test_ai_select_support_probe):
#   id 11 (0, 0, 5)        -> (2, 2) = pixel 10, kept
#   id 12 (0.25, 0, 2)     -> (3, 2) = pixel 11, kept
#   id 13 (0.125, -0.25, 2)-> (3, 1) = pixel 7, kept
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


def _planes() -> list[tuple[memoryview, memoryview]]:
    means = b''.join(struct.pack('<3f', *mean) for _, mean, _ in GAUSSIANS)
    logits = b''.join(struct.pack('<f', logit) for _, _, logit in GAUSSIANS)
    return [(memoryview(means), memoryview(logits))]


def _assert_orthonormal_rotation(test: unittest.TestCase, camera_to_world: list[float]) -> None:
    rows = (
        camera_to_world[0:3],
        camera_to_world[4:7],
        camera_to_world[8:11],
    )
    for row in rows:
        test.assertAlmostEqual(sum(component * component for component in row), 1.0, places=9)
    for first, second in ((0, 1), (0, 2), (1, 2)):
        test.assertAlmostEqual(
            sum(rows[first][axis] * rows[second][axis] for axis in range(3)),
            0.0,
            places=9,
        )
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    test.assertAlmostEqual(determinant, 1.0, places=9)


class GeneratedViewPlanningPolicyTests(unittest.TestCase):
    """Direct policy checks over synthetic planes, with no service state."""

    def test_seed_derivation_gates_and_frames_the_mask_support(self) -> None:
        seed = derive_mask_support_seed(
            planes=_planes(), camera=PROBE_CAMERA, mask=FULL_MASK
        )

        self.assertIsNotNone(seed)
        assert seed is not None
        self.assertEqual(seed.support_count, 3)
        # Provisional median (0.125, 0, 2); id 11 at distance ~3.0 is clearly
        # separated support and drops out of the framing center.
        self.assertAlmostEqual(seed.center[0], 0.1875)
        self.assertAlmostEqual(seed.center[1], -0.125)
        self.assertAlmostEqual(seed.center[2], 2.0)
        self.assertAlmostEqual(
            seed.radius, max(0.05, math.dist((0.25, 0.0, 2.0), seed.center) * 2.5)
        )

    def test_seed_derivation_reports_no_support_for_an_empty_mask(self) -> None:
        self.assertIsNone(
            derive_mask_support_seed(
                planes=_planes(), camera=PROBE_CAMERA, mask=EMPTY_MASK
            )
        )

    def test_orbit_planning_sweeps_the_first_ring_neighbours(self) -> None:
        seed = derive_mask_support_seed(
            planes=_planes(), camera=PROBE_CAMERA, mask=FULL_MASK
        )
        assert seed is not None

        views = plan_first_generated_views(camera_binding=PACKED_CAMERA, seed=seed)

        self.assertEqual(len(views), GENERATED_VIEW_PLAN_COUNT)
        self.assertEqual([view.view_id for view in views], ['generated-00', 'generated-01'])
        expected_distance = max(
            math.dist((0.0, 0.0, 0.0), seed.center),
            seed.radius * 4.0,
            0.1 * 4.0,
        )
        directions = []
        for view in views:
            camera = view.camera_binding
            self.assertEqual(camera['conventionVersion'], 'opencv-camera-to-world/v1')
            self.assertEqual(camera['revision'], 0)
            self.assertEqual(camera['projection'], PACKED_CAMERA['projection'])
            camera_to_world = camera['cameraToWorld']
            assert isinstance(camera_to_world, list)
            self.assertEqual(camera_to_world[12:], [0.0, 0.0, 0.0, 1.0])
            _assert_orthonormal_rotation(self, camera_to_world)
            position = (camera_to_world[3], camera_to_world[7], camera_to_world[11])
            self.assertAlmostEqual(math.dist(position, seed.center), expected_distance)
            # The camera looks at the Seed Region: its forward column points
            # from the position at the exact seed center.
            forward = (camera_to_world[2], camera_to_world[6], camera_to_world[10])
            expected_forward = tuple(
                (seed.center[axis] - position[axis]) / expected_distance
                for axis in range(3)
            )
            for axis in range(3):
                self.assertAlmostEqual(forward[axis], expected_forward[axis], places=9)
            directions.append(
                tuple(
                    (position[axis] - seed.center[axis]) / expected_distance
                    for axis in range(3)
                )
            )
        # The +/-45 degree ring neighbours are perpendicular around the orbit axis.
        self.assertAlmostEqual(
            sum(directions[0][axis] * directions[1][axis] for axis in range(3)),
            0.0,
            places=9,
        )
        # Planning is deterministic for one immutable input identity.
        replay = plan_first_generated_views(camera_binding=PACKED_CAMERA, seed=seed)
        self.assertEqual(
            [view.camera_binding for view in replay],
            [view.camera_binding for view in views],
        )

    def test_prompt_synthesis_projects_support_into_the_generated_view(self) -> None:
        synthesized = synthesize_view_prompts(
            planes=_planes(),
            anchor_camera=PROBE_CAMERA,
            view_camera=VIEW_PROBE_CAMERA,
            mask=FULL_MASK,
        )

        self.assertIsNotNone(synthesized)
        assert synthesized is not None
        # Support lands on view pixels (1, 2), (1, 2), (0, 1): the robust
        # centroid (1, 2) first, then the farthest distinct pixel.
        self.assertEqual(synthesized.prompts, ((1, 2), (0, 1)))
        self.assertEqual(synthesized.projected_support_count, 3)

    def test_prompt_synthesis_fails_closed_when_nothing_projects(self) -> None:
        behind = AnchorSupportProbeCamera(
            world_to_camera=(
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, -10.0,
                0.0, 0.0, 0.0, 1.0,
            ),
            fx=10.0,
            fy=10.0,
            cx=2.0,
            cy=2.0,
            width=4,
            height=4,
            near=0.1,
            far=100.0,
        )
        self.assertIsNone(
            synthesize_view_prompts(
                planes=_planes(),
                anchor_camera=PROBE_CAMERA,
                view_camera=behind,
                mask=FULL_MASK,
            )
        )
        self.assertIsNone(
            synthesize_view_prompts(
                planes=_planes(),
                anchor_camera=PROBE_CAMERA,
                view_camera=VIEW_PROBE_CAMERA,
                mask=EMPTY_MASK,
            )
        )


def _binary_fixture() -> tuple[bytes, BinarySceneSnapshotManifest]:
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


def _plan_request_body(scene_version: str, mask: bytes) -> dict[str, object]:
    return {
        'requestBinding': _request_binding(),
        'targetSplatId': 'splat-1',
        'sceneId': 'splat-1',
        'sceneVersion': scene_version,
        'renderConfigVersion': 'supersplat-effective-rgb-v1',
        'planAttemptId': 'plan-attempt-1',
        'anchorCameraBinding': PACKED_CAMERA,
        'anchorRgbDigest': RGB_DIGEST,
        'anchorStableMask': _mask_payload(mask),
        'plannerPolicyVersion': AI_SELECT_GENERATED_VIEW_PLANNER_VERSION,
    }


class AnchorFixtureRenderer:
    """Records the exact camera accepted at the authoritative renderer seam."""

    renderer_id = 'gsplat'
    requires_locked_runtime = False

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render_anchor(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        view_id: str,
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        # The binary-registered scene is a PackedBinarySceneSnapshot, not a
        # Mapping; only the renderer seam bindings are recorded here.
        self.calls.append(
            {
                'viewId': view_id,
                'camera': dict(camera),
                'width': width,
                'height': height,
            }
        )
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=='
        )
        return AnchorRenderArtifact(
            image_png=png,
            rgb_digest=f'sha256:{hashlib.sha256(png).hexdigest()}',
            contributor_digest='sha256:' + ('1' * 64),
        )


class FakeSam3Predictor:
    """Records the public SAM session API and returns a configurable mask."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        # Rows are y, columns are x: the synthesized include prompts (1, 2)
        # and (0, 1) must land on foreground pixels of the returned mask.
        self.masks: list[list[list[bool]]] = [
            [
                [False, False, False, False],
                [True, False, False, False],
                [False, True, False, False],
                [False, False, False, False],
            ]
        ]
        self.probs: list[float] = [0.9]

    def handle_request(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        if request['type'] == 'start_session':
            return {'session_id': 'sam-session'}
        if request['type'] == 'add_prompt':
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


class GeneratedViewRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.lock_file = self.directory / 'uv.lock'
        self.lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', self.lock_file)
        self.payload, self.manifest = _binary_fixture()
        self.renderer = AnchorFixtureRenderer()
        self.state.contributor_renderer = self.renderer  # type: ignore[assignment]

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

    def request_json(
        self, path: str, method: str, body: dict[str, object]
    ) -> dict[str, object]:
        with urlopen(
            Request(
                f'{self.endpoint}{path}',
                data=json.dumps(body).encode('utf-8'),
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

    def test_plans_the_first_generated_views_from_the_confirmed_anchor(self) -> None:
        self.register_binary_snapshot()
        body = _plan_request_body(self.manifest.scene_version, FULL_MASK)

        response = self.request_json('/ai-select/generated-view-plans', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], body['requestBinding'])
        self.assertEqual(response['targetSplatId'], 'splat-1')
        self.assertEqual(response['sceneId'], 'splat-1')
        self.assertEqual(response['sceneVersion'], self.manifest.scene_version)
        self.assertEqual(response['renderConfigVersion'], 'supersplat-effective-rgb-v1')
        self.assertEqual(response['planAttemptId'], 'plan-attempt-1')
        self.assertEqual(
            response['plannerPolicyVersion'], AI_SELECT_GENERATED_VIEW_PLANNER_VERSION
        )
        views = response['views']
        self.assertEqual(
            [view['viewId'] for view in views],
            ['generated-00', 'generated-01'],
        )
        for view in views:
            camera = view['cameraBinding']
            self.assertEqual(camera['conventionVersion'], 'opencv-camera-to-world/v1')
            self.assertEqual(camera['projection'], PACKED_CAMERA['projection'])
            self.assertNotEqual(
                camera['cameraToWorld'], PACKED_CAMERA['cameraToWorld']
            )
        # The same immutable input plans the same cameras deterministically.
        replay = self.request_json('/ai-select/generated-view-plans', 'POST', body)
        self.assertEqual(replay['views'], views)

    def test_plan_reports_a_bound_cache_miss_without_the_scene(self) -> None:
        body = _plan_request_body(self.manifest.scene_version, FULL_MASK)

        response = self.request_json('/ai-select/generated-view-plans', 'POST', body)

        self.assertEqual(response['status'], 'sceneCacheMiss')
        self.assertEqual(response['requestBinding'], body['requestBinding'])
        self.assertEqual(response['planAttemptId'], 'plan-attempt-1')

    def test_plan_rejects_an_unsupported_policy_version(self) -> None:
        self.register_binary_snapshot()
        body = {
            **_plan_request_body(self.manifest.scene_version, FULL_MASK),
            'plannerPolicyVersion': 'generated-view-planner/v0',
        }
        payload = self.post_error(
            '/ai-select/generated-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_rejects_a_stable_mask_digest_mismatch(self) -> None:
        self.register_binary_snapshot()
        body = _plan_request_body(self.manifest.scene_version, FULL_MASK)
        body['anchorStableMask'] = {
            **body['anchorStableMask'],
            'digest': 'sha256:' + ('0' * 64),
        }
        payload = self.post_error(
            '/ai-select/generated-view-plans', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')

    def test_plan_fails_closed_when_the_mask_has_no_observable_support(self) -> None:
        self.register_binary_snapshot()
        body = _plan_request_body(self.manifest.scene_version, EMPTY_MASK)

        payload = self.post_error(
            '/ai-select/generated-view-plans', body, HTTPStatus.CONFLICT
        )

        self.assertEqual(payload['status'], 'plannerError')
        self.assertEqual(payload['code'], 'seedUnavailable')

    def test_renders_a_generated_view_from_the_bound_camera(self) -> None:
        self.register_binary_snapshot()
        planned = self.request_json(
            '/ai-select/generated-view-plans',
            'POST',
            _plan_request_body(self.manifest.scene_version, FULL_MASK),
        )
        view = planned['views'][0]
        body = {
            'requestBinding': _request_binding(),
            'targetSplatId': 'splat-1',
            'sceneId': 'splat-1',
            'sceneVersion': self.manifest.scene_version,
            'renderConfigVersion': 'supersplat-effective-rgb-v1',
            'renderAttemptId': 'render-attempt-1',
            'viewId': view['viewId'],
            'cameraBinding': view['cameraBinding'],
        }

        response = self.request_json('/ai-select/view-renders', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['viewId'], 'generated-00')
        self.assertEqual(response['renderAttemptId'], 'render-attempt-1')
        self.assertEqual(response['cameraBinding'], view['cameraBinding'])
        self.assertEqual(response['rendererId'], 'gsplat')
        self.assertEqual(len(self.renderer.calls), 1)
        self.assertEqual(self.renderer.calls[0]['viewId'], 'generated-00')

    def test_view_render_rejects_the_reserved_anchor_view_id(self) -> None:
        self.register_binary_snapshot()
        body = {
            'requestBinding': _request_binding(),
            'targetSplatId': 'splat-1',
            'sceneId': 'splat-1',
            'sceneVersion': self.manifest.scene_version,
            'renderConfigVersion': 'supersplat-effective-rgb-v1',
            'renderAttemptId': 'render-attempt-1',
            'viewId': 'anchor-view',
            'cameraBinding': PACKED_CAMERA,
        }
        payload = self.post_error(
            '/ai-select/view-renders', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])

    def _mask_request_body(self, scene_version: str) -> dict[str, object]:
        return {
            'requestBinding': _request_binding(),
            'targetSplatId': 'splat-1',
            'sceneId': 'splat-1',
            'sceneVersion': scene_version,
            'renderConfigVersion': 'supersplat-effective-rgb-v1',
            'viewId': 'generated-00',
            'viewCameraBinding': VIEW_CAMERA,
            'maskAttemptId': 'mask-attempt-1',
            'rgb': {
                'pngBase64': base64.b64encode(b'\x89PNG\r\n\x1a\ngenerated-rgb').decode('ascii'),
                'digest': 'sha256:' + hashlib.sha256(b'\x89PNG\r\n\x1a\ngenerated-rgb').hexdigest(),
                'width': 4,
                'height': 4,
            },
            'anchor': {
                'cameraBinding': PACKED_CAMERA,
                'rgbDigest': RGB_DIGEST,
                'stableMask': _mask_payload(FULL_MASK),
            },
            'modelManifestDigest': self.model_manifest_digest,
        }

    def test_produces_a_propagated_mask_bound_to_the_view_and_anchor(self) -> None:
        self.register_binary_snapshot()
        body = self._mask_request_body(self.manifest.scene_version)

        response = self.request_json('/ai-select/generated-view-masks', 'POST', body)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], body['requestBinding'])
        self.assertEqual(response['viewId'], 'generated-00')
        self.assertEqual(response['maskAttemptId'], 'mask-attempt-1')
        self.assertEqual(response['rgbDigest'], body['rgb']['digest'])
        self.assertEqual(response['anchorRgbDigest'], RGB_DIGEST)
        self.assertEqual(response['maskSource'], 'propagated')
        self.assertEqual(response['modelManifestDigest'], self.model_manifest_digest)
        propagation = response['maskPropagation']
        self.assertEqual(
            propagation['policyVersion'], AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION
        )
        self.assertEqual(propagation['projectedSupportCount'], 3)
        self.assertEqual(propagation['promptCount'], 2)
        mask = response['mask']
        self.assertEqual(mask['encoding'], 'bitset-lsb-v1')
        self.assertEqual(mask['width'], 4)
        self.assertEqual(mask['height'], 4)
        mask_bytes = base64.b64decode(mask['data'])
        self.assertEqual(
            mask['digest'], f'sha256:{hashlib.sha256(mask_bytes).hexdigest()}'
        )
        assessment = response['assessment']
        self.assertEqual(assessment['status'], 'review')
        self.assertEqual(
            assessment['reasons'],
            [
                'target-at-boundary',
                'fragmented-mask',
                'weak-gaussian-support',
                'propagation-uncertain',
            ],
        )
        self.assertEqual(
            assessment['actionableReasons'],
            ['target-at-boundary', 'fragmented-mask'],
        )
        self.assertEqual(assessment['primaryReason'], 'target-at-boundary')
        self.assertEqual(
            assessment['policyVersion'],
            AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        )
        self.assertEqual(
            assessment['inputIdentity'],
            {
                'rgbDigest': body['rgb']['digest'],
                'stableMaskDigest': mask['digest'],
                'assessmentPolicyVersion': (
                    AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION
                ),
                'supportPolicyVersion': (
                    AI_SELECT_LOCAL_VIEW_SUPPORT_POLICY_VERSION
                ),
                'supportDiagnosticId': local_view_support_diagnostic_id(
                    scene_id='splat-1',
                    scene_version=self.manifest.scene_version,
                    view_id='generated-00',
                    rgb_digest=body['rgb']['digest'],
                    stable_mask_digest=mask['digest'],
                    observed_gaussian_count=3,
                ),
                'propagationPolicyVersion': (
                    AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION
                ),
            },
        )
        # SAM ran exactly one single-frame pass with the synthesized prompts.
        self.assertEqual(self.predictor.session_starts, 1)
        add_prompts = [
            request for request in self.predictor.requests
            if request['type'] == 'add_prompt'
        ]
        self.assertEqual(len(add_prompts), 1)
        self.assertEqual(add_prompts[0]['points'], [[1, 2], [0, 1]])
        self.assertEqual(add_prompts[0]['point_labels'], [1, 1])

    def test_generated_mask_replays_the_same_attempt_without_a_second_sam_pass(self) -> None:
        self.register_binary_snapshot()
        body = self._mask_request_body(self.manifest.scene_version)

        first = self.request_json('/ai-select/generated-view-masks', 'POST', body)
        replay = self.request_json('/ai-select/generated-view-masks', 'POST', body)

        self.assertEqual(replay, first)
        self.assertEqual(self.predictor.session_starts, 1)

    def test_generated_mask_fails_closed_when_support_does_not_project(self) -> None:
        self.register_binary_snapshot()
        body = self._mask_request_body(self.manifest.scene_version)
        # A view camera ten units behind the support observes nothing.
        body['viewCameraBinding'] = {
            **VIEW_CAMERA,
            'cameraToWorld': [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 10.0,
                0.0, 0.0, 0.0, 1.0,
            ],
        }

        payload = self.post_error(
            '/ai-select/generated-view-masks', body, HTTPStatus.CONFLICT
        )

        self.assertEqual(payload['status'], 'maskError')
        self.assertEqual(payload['code'], 'propagationUnavailable')
        self.assertEqual(self.predictor.session_starts, 0)

    def test_generated_mask_rejects_an_rgb_dimension_mismatch(self) -> None:
        self.register_binary_snapshot()
        body = self._mask_request_body(self.manifest.scene_version)
        body['rgb'] = {**body['rgb'], 'width': 8}
        payload = self.post_error(
            '/ai-select/generated-view-masks', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')
        self.assertEqual(self.predictor.session_starts, 0)

    def test_generated_mask_rejects_the_reserved_anchor_view_id(self) -> None:
        self.register_binary_snapshot()
        body = {**self._mask_request_body(self.manifest.scene_version), 'viewId': 'anchor-view'}
        payload = self.post_error(
            '/ai-select/generated-view-masks', body, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(payload['status'], 'invalidRequest')
        self.assertEqual(self.predictor.session_starts, 0)


if __name__ == '__main__':
    unittest.main()

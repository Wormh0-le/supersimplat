from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import struct
import tempfile
from threading import Thread
from typing import Any, Mapping
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.gsplat_renderer import AnchorRenderArtifact
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = 'https://editor.example'

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

VIEW_CAMERA: dict[str, object] = {
    **PACKED_CAMERA,
    'cameraToWorld': [
        1.0, 0.0, 0.0, 0.5,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ],
}

GAUSSIANS: tuple[tuple[int, tuple[float, float, float], float], ...] = (
    (11, (0.0, 0.0, 5.0), 1.0),
    (12, (0.25, 0.0, 2.0), 0.0),
    (13, (0.125, -0.25, 2.0), 2.0),
)


def _binary_fixture() -> tuple[bytes, BinarySceneSnapshotManifest]:
    count = len(GAUSSIANS)
    source_digest = 'sha256:' + 'b' * 64
    scope_identity = json.dumps(
        {
            'policyId': 'visible-editor-splats-conservative/v1',
            'targetSplatId': 'splat-1',
            'sources': [{
                'splatId': 'splat-1',
                'sourceContentDigest': source_digest,
                'gaussianCount': count,
            }],
        },
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
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
        fields.append({
            'name': name,
            'scalarType': scalar_type,
            'componentCount': components,
            'byteOffset': offset,
            'byteLength': byte_length,
        })
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
        'authoritativeRenderScope': {
            'policyId': 'visible-editor-splats-conservative/v1',
            'targetSplatId': 'splat-1',
            'identityDigest': 'sha256:' + hashlib.sha256(scope_identity).hexdigest(),
            'entries': [{
                'splatId': 'splat-1',
                'role': 'target',
                'sourceContentDigest': source_digest,
                'rowOffset': 0,
                'rowCount': count,
                'renderIdStart': GAUSSIANS[0][0],
            }],
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
            digest='sha256:' + hashlib.sha256(
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


class AnchorFixtureRenderer:
    renderer_id = 'gsplat'
    requires_locked_runtime = False

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.alpha_coverage: float | None = None

    def render_anchor(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        view_id: str,
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        self.calls.append({
            'viewId': view_id,
            'camera': dict(camera),
            'width': width,
            'height': height,
        })
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=='
        )
        return AnchorRenderArtifact(
            image_png=png,
            rgb_digest=f'sha256:{hashlib.sha256(png).hexdigest()}',
            contributor_digest='sha256:' + ('1' * 64),
            alpha_coverage=self.alpha_coverage,
        )


class GeneratedViewRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.payload, self.manifest = _binary_fixture()
        self.renderer = AnchorFixtureRenderer()
        self.state.contributor_renderer = self.renderer  # type: ignore[assignment]
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

    def post_error(self, path: str, body: dict[str, object]) -> dict[str, object]:
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    f'{self.endpoint}{path}',
                    data=json.dumps(body).encode('utf-8'),
                    method='POST',
                    headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
                )
            )
        return json.load(error.exception)

    def register_binary_snapshot(self) -> None:
        manifest = self.manifest
        admission = self.request_json('/scene-snapshot-uploads/v1', {
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
        })
        upload_id = admission['uploadId']
        self.assertEqual(admission['status'], 'staged')
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
            f'/scene-snapshot-uploads/v1/{upload_id}/commit', {}
        )
        self.assertEqual(committed['status'], 'committed')

    def _view_render_body(self, view_id: str) -> dict[str, object]:
        return {
            'requestBinding': _request_binding(),
            'targetSplatId': 'splat-1',
            'sceneId': 'splat-1',
            'sceneVersion': self.manifest.scene_version,
            'renderConfigVersion': 'supersplat-effective-rgb-v1',
            'renderAttemptId': 'render-attempt-1',
            'viewId': view_id,
            'cameraBinding': VIEW_CAMERA,
        }

    def test_renders_a_generated_view_from_the_bound_camera(self) -> None:
        self.register_binary_snapshot()
        response = self.request_json(
            '/ai-select/view-renders', self._view_render_body('key-view-0-0')
        )
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['viewId'], 'key-view-0-0')
        self.assertEqual(response['cameraBinding'], VIEW_CAMERA)
        self.assertEqual(self.renderer.calls[0]['viewId'], 'key-view-0-0')

    def test_view_render_failure_keeps_the_failure_distinct_from_anchor_render(self) -> None:
        self.register_binary_snapshot()
        self.renderer.alpha_coverage = 0.0
        payload = self.post_error(
            '/ai-select/view-renders', self._view_render_body('key-view-0-0')
        )
        self.assertEqual(payload['status'], 'viewRenderError')
        self.assertEqual(payload['code'], 'blankRender')
        anchor = self.request_json('/ai-select/anchor-renders', {
            **self._view_render_body('anchor-view'),
            'cameraBinding': PACKED_CAMERA,
        })
        self.assertEqual(anchor['viewId'], 'anchor-view')

    def test_view_render_rejects_the_reserved_anchor_view_id(self) -> None:
        self.register_binary_snapshot()
        payload = self.post_error(
            '/ai-select/view-renders', self._view_render_body('anchor-view')
        )
        self.assertEqual(payload['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])


if __name__ == '__main__':
    unittest.main()

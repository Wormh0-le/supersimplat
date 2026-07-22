from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import struct
import tempfile
from threading import Thread
from typing import Any
import unittest
from urllib.request import Request, urlopen

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    PackedBinarySceneSnapshot,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.gsplat_renderer import AnchorRenderArtifact
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = "https://editor.example"


class PackedAnchorFixtureRenderer:
    renderer_id = "gsplat"
    requires_locked_runtime = False

    def __init__(self) -> None:
        self.scene_snapshots: list[PackedBinarySceneSnapshot] = []

    def render_anchor(
        self,
        *,
        scene_snapshot: PackedBinarySceneSnapshot,
        view_id: str,
        camera: dict[str, object],
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        assert isinstance(scene_snapshot, PackedBinarySceneSnapshot)
        assert view_id == "anchor-view"
        assert width == 1 and height == 1
        self.scene_snapshots.append(scene_snapshot)
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=="
        )
        return AnchorRenderArtifact(
            image_png=png,
            rgb_digest=f"sha256:{hashlib.sha256(png).hexdigest()}",
            contributor_digest="sha256:" + ("1" * 64),
        )


def _binary_fixture() -> tuple[bytes, BinarySceneSnapshotManifest]:
    payload = struct.pack(
        "<I" + "f" * 14,
        7,
        1.0,
        2.0,
        3.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    content: dict[str, object] = {
        "protocolVersion": "1",
        "gaussianCount": 1,
        "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
        "stableIdSchema": "uint32",
        "attributeSchema": "mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
        "appearancePolicy": "effective-editor-dc-sh-bands-0",
        "renderConfiguration": {
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        "shFloatCountPerGaussian": 0,
        "payloadByteLength": len(payload),
        "fields": [
            {"name": "stableIds", "scalarType": "uint32le", "componentCount": 1, "byteOffset": 0, "byteLength": 4},
            {"name": "means", "scalarType": "float32le", "componentCount": 3, "byteOffset": 4, "byteLength": 12},
            {"name": "rotationsXyzw", "scalarType": "float32le", "componentCount": 4, "byteOffset": 16, "byteLength": 16},
            {"name": "logScales", "scalarType": "float32le", "componentCount": 3, "byteOffset": 32, "byteLength": 12},
            {"name": "logitOpacities", "scalarType": "float32le", "componentCount": 1, "byteOffset": 44, "byteLength": 4},
            {"name": "dc", "scalarType": "float32le", "componentCount": 3, "byteOffset": 48, "byteLength": 12},
            {"name": "sh", "scalarType": "float32le", "componentCount": 0, "byteOffset": 60, "byteLength": 0},
        ],
    }
    chunk_byte_length = 32
    chunks = tuple(
        BinarySceneSnapshotChunk(
            index=index,
            offset=index * chunk_byte_length,
            byte_length=len(payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]),
            digest="sha256:" + hashlib.sha256(
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
        scene_id="splat-1",
        scene_version=content_digest,
        content_digest=content_digest,
        content=content,
        chunk_byte_length=chunk_byte_length,
        chunks=chunks,
    )


class BinarySceneSnapshotRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.state = CompanionState(directory / "state")
        lock_file = directory / "uv.lock"
        lock_file.write_text("locked companion dependencies\n", encoding="utf-8")
        self.state.install_release("0.1.0", lock_file)
        self.renderer = PackedAnchorFixtureRenderer()
        self.state.contributor_renderer = self.renderer  # type: ignore[assignment]
        self.server = create_server(
            state=self.state,
            endpoint="http://127.0.0.1:0",
            profile="loopback",
            allowed_origins=[EDITOR_ORIGIN],
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

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
                f"{self.endpoint}{path}",
                data=json.dumps(body).encode("utf-8"),
                method=method,
                headers={
                    "Origin": EDITOR_ORIGIN,
                    "Content-Type": "application/json",
                },
            )
        ) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    def test_registers_raw_chunks_atomically_and_passes_mmap_snapshot_to_anchor(self) -> None:
        payload, manifest = _binary_fixture()
        manifest_body = {
            "format": manifest.format,
            "formatVersion": manifest.format_version,
            "sceneId": manifest.scene_id,
            "sceneVersion": manifest.scene_version,
            "contentDigest": manifest.content_digest,
            "content": manifest.content,
            "transfer": {
                "chunkByteLength": manifest.chunk_byte_length,
                "chunks": [
                    {
                        "index": chunk.index,
                        "offset": chunk.offset,
                        "byteLength": chunk.byte_length,
                        "digest": chunk.digest,
                    }
                    for chunk in manifest.chunks
                ],
            },
        }
        admission = self.request_json("/scene-snapshot-uploads/v1", "POST", manifest_body)
        self.assertEqual(admission["status"], "staged")
        self.assertEqual(admission["missingChunkIndices"], [0, 1])
        upload_id = admission["uploadId"]
        self.assertIsInstance(upload_id, str)
        self.assertIsNone(self.state.scene_snapshot(manifest.scene_id, manifest.scene_version))

        for chunk in manifest.chunks:
            with urlopen(
                Request(
                    f"{self.endpoint}/scene-snapshot-uploads/v1/{upload_id}/chunks/{chunk.index}",
                    data=payload[chunk.offset:chunk.offset + chunk.byte_length],
                    method="PUT",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/octet-stream",
                        "X-SceneSnapshot-Chunk-Digest": chunk.digest,
                    },
                )
            ) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertEqual(json.load(response)["status"], "stored")

        committed = self.request_json(
            f"/scene-snapshot-uploads/v1/{upload_id}/commit", "POST", {}
        )
        self.assertEqual(committed, {
            "status": "committed",
            "sceneId": manifest.scene_id,
            "sceneVersion": manifest.scene_version,
            "contentDigest": manifest.content_digest,
        })
        replay = self.request_json(
            f"/scene-snapshot-uploads/v1/{upload_id}/commit", "POST", {}
        )
        self.assertEqual(replay["status"], "alreadyCommitted")

        registered = self.state.scene_snapshot(manifest.scene_id, manifest.scene_version)
        self.assertIsNotNone(registered)
        assert registered is not None
        self.assertIsInstance(registered.scene, PackedBinarySceneSnapshot)
        self.assertIsInstance(registered.stable_ids, memoryview)
        self.assertEqual(list(registered.stable_ids), [7])

        response = self.request_json(
            "/ai-select/anchor-renders",
            "POST",
            {
                "requestBinding": {
                    "targetContextId": "context-1",
                    "contextRevision": 0,
                    "dependencyToken": {
                        "splatId": "splat-1",
                        "renderStateToken": "render-v1",
                        "geometryToken": "geometry-v1",
                        "gaussianIdentityToken": "ids-v1",
                        "worldTransformToken": "world-v1",
                    },
                },
                "targetSplatId": "splat-1",
                "sceneId": manifest.scene_id,
                "sceneVersion": manifest.scene_version,
                "renderConfigVersion": "supersplat-effective-rgb-v1",
                "viewId": "anchor-view",
                "cameraBinding": {
                    "revision": 0,
                    "cameraToWorld": [
                        1,
                        0,
                        0,
                        1,
                        0,
                        1,
                        0,
                        2,
                        0,
                        0,
                        1,
                        3,
                        0,
                        0,
                        0,
                        1,
                    ],
                    "projection": {
                        "model": "pinhole",
                        "fx": 100,
                        "fy": 100,
                        "cx": 0.5,
                        "cy": 0.5,
                        "width": 1,
                        "height": 1,
                        "near": 0.1,
                        "far": 100,
                    },
                    "conventionVersion": "opencv-camera-to-world/v1",
                },
            },
        )
        self.assertEqual(response["status"], "complete")
        self.assertEqual(len(self.renderer.scene_snapshots), 1)
        self.assertIs(self.renderer.scene_snapshots[0], registered.scene)

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
from urllib.request import Request, urlopen

from selection_service_companion.gsplat_renderer import AnchorRenderArtifact
from selection_service_companion.spatial_scene_working_set import (
    SpatialChunkDescriptor,
    SpatialSceneManifest,
    SpatialSupportBounds,
    SpatialWorkingSet,
)
from selection_service_companion.state import CompanionState
from selection_service_companion.server import create_server


EDITOR_ORIGIN = "https://editor.example"


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=="
)


class SpatialAnchorRenderer:
    renderer_id = "gsplat"
    requires_locked_runtime = False

    def __init__(self) -> None:
        self.scene_snapshots: list[object] = []

    def render_anchor(
        self,
        *,
        scene_snapshot: object,
        view_id: str,
        camera: object,
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        self.scene_snapshots.append(scene_snapshot)
        return AnchorRenderArtifact(
            image_png=PNG,
            rgb_digest="sha256:" + hashlib.sha256(PNG).hexdigest(),
            contributor_digest="sha256:" + "1" * 64,
        )


def payload() -> bytes:
    return b"".join(
        (
            struct.pack("<I", 0),
            struct.pack("<I", 7),
            struct.pack("<3f", 0.0, 0.0, 5.0),
            struct.pack("<4f", 0.0, 0.0, 0.0, 1.0),
            struct.pack("<3f", 0.0, 0.0, 0.0),
            struct.pack("<f", 0.0),
            struct.pack("<3f", 0.0, 0.0, 0.0),
        )
    )


def manifest() -> SpatialSceneManifest:
    chunk = payload()
    return SpatialSceneManifest(
        scene_id="editor-splat:42",
        scene_version="sha256:" + "a" * 64,
        content_digest="sha256:" + "a" * 64,
        target_splat_id="editor-splat:42",
        total_gaussian_count=1,
        coordinate_convention="right-handed world coordinates; quaternion xyzw",
        stable_id_schema="uint32",
        attribute_schema="mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
        appearance_policy="effective-editor-dc-sh-bands-0",
        render_configuration={
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        sh_float_count_per_gaussian=0,
        chunks=(
            SpatialChunkDescriptor(
                chunk_id="chunk-a",
                chunk_digest="sha256:" + hashlib.sha256(chunk).hexdigest(),
                byte_length=len(chunk),
                gaussian_count=1,
                global_ordinal_min=0,
                global_ordinal_max=0,
                support_bounds=SpatialSupportBounds.finite(
                    (-10.0, -10.0, 1.0), (10.0, 10.0, 9.0)
                ),
            ),
        ),
    )


def request(scene_version: str) -> dict[str, object]:
    return {
        "requestBinding": {
            "targetContextId": "context-1",
            "contextRevision": 2,
            "dependencyToken": {
                "splatId": "editor-splat:42",
                "renderStateToken": "render-1",
                "geometryToken": "geometry-1",
                "gaussianIdentityToken": "identity-1",
                "worldTransformToken": "world-1",
            },
        },
        "targetSplatId": "editor-splat:42",
        "sceneId": "editor-splat:42",
        "sceneVersion": scene_version,
        "renderConfigVersion": "supersplat-effective-rgb-v1",
        "renderAttemptId": "attempt-1",
        "viewId": "anchor-view",
        "sceneTransport": "spatial-v1",
        "cameraBinding": {
            "revision": 0,
            "cameraToWorld": [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            "projection": {
                "model": "pinhole",
                "fx": 10.0,
                "fy": 10.0,
                "cx": 5.0,
                "cy": 5.0,
                "width": 10,
                "height": 10,
                "near": 0.1,
                "far": 10.0,
            },
            "conventionVersion": "opencv-camera-to-world/v1",
        },
    }


class SpatialSceneAnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.renderer = SpatialAnchorRenderer()
        self.state = CompanionState(
            Path(self.temporary_directory.name), contributor_renderer=self.renderer
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_returns_a_bound_scene_chunk_miss_then_renders_only_after_atomic_residency(self) -> None:
        registered = manifest()
        self.state.register_spatial_scene_manifest(registered)
        anchor_request = request(registered.scene_version)

        miss = self.state.render_ai_select_anchor(anchor_request)
        self.assertEqual(miss["status"], "sceneChunkMiss")
        self.assertEqual(miss["requestBinding"], anchor_request["requestBinding"])
        self.assertEqual(miss["cameraBinding"], anchor_request["cameraBinding"])
        self.assertEqual(miss["missingChunkIds"], ["chunk-a"])
        self.assertTrue(str(miss["workingSetToken"]).startswith("sha256:"))
        self.assertEqual(self.renderer.scene_snapshots, [])

        admission = self.state.begin_spatial_scene_chunk_upload(
            registered.scene_id, registered.scene_version, ("chunk-a",)
        )
        chunk = payload()
        self.state.accept_spatial_scene_chunk(
            admission.upload_id or "",
            "chunk-a",
            chunk,
            "sha256:" + hashlib.sha256(chunk).hexdigest(),
        )
        self.state.commit_spatial_scene_chunk_upload(admission.upload_id or "")

        rendered = self.state.render_ai_select_anchor(anchor_request)
        self.assertEqual(rendered["status"], "complete")
        self.assertEqual(len(self.renderer.scene_snapshots), 1)
        self.assertIsInstance(self.renderer.scene_snapshots[0], SpatialWorkingSet)


class SpatialSceneAnchorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.state = CompanionState(directory / "state")
        lock_file = directory / "uv.lock"
        lock_file.write_text("locked companion dependencies\n", encoding="utf-8")
        self.state.install_release("0.1.0", lock_file)
        self.renderer = SpatialAnchorRenderer()
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

    def request_json(self, path: str, method: str, body: dict[str, object]) -> dict[str, object]:
        with urlopen(Request(
            f"{self.endpoint}{path}",
            data=json.dumps(body).encode("utf-8"),
            method=method,
            headers={"Origin": EDITOR_ORIGIN, "Content-Type": "application/json"},
        )) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    @staticmethod
    def manifest_wire(registered: SpatialSceneManifest) -> dict[str, object]:
        return {
            "format": registered.format,
            "formatVersion": registered.format_version,
            "chunkFormat": registered.chunk_format,
            "chunkFormatVersion": registered.chunk_format_version,
            "protocolVersion": registered.protocol_version,
            "sceneId": registered.scene_id,
            "sceneVersion": registered.scene_version,
            "contentDigest": registered.content_digest,
            "targetSplatId": registered.target_splat_id,
            "totalGaussianCount": registered.total_gaussian_count,
            "coordinateConvention": registered.coordinate_convention,
            "stableIdSchema": registered.stable_id_schema,
            "attributeSchema": registered.attribute_schema,
            "appearancePolicy": registered.appearance_policy,
            "renderConfiguration": registered.render_configuration,
            "shFloatCountPerGaussian": registered.sh_float_count_per_gaussian,
            "chunks": [
                {
                    "chunkId": chunk.chunk_id,
                    "chunkDigest": chunk.chunk_digest,
                    "byteLength": chunk.byte_length,
                    "gaussianCount": chunk.gaussian_count,
                    "globalOrdinalMin": chunk.global_ordinal_min,
                    "globalOrdinalMax": chunk.global_ordinal_max,
                    "supportBounds": {
                        "kind": chunk.support_bounds.kind,
                        "min": list(chunk.support_bounds.minimum or ()),
                        "max": list(chunk.support_bounds.maximum or ()),
                    },
                }
                for chunk in registered.chunks
            ],
        }

    def test_uses_manifest_then_scene_chunk_miss_then_raw_selective_upload(self) -> None:
        registered = manifest()
        registration = self.request_json(
            "/spatial-scene-manifests/v1", "POST", self.manifest_wire(registered)
        )
        self.assertEqual(registration["status"], "registered")
        self.assertIsInstance(registration["registrationId"], str)
        self.assertEqual(registration["contentDigest"], registered.content_digest)

        anchor_request = request(registered.scene_version)
        miss = self.request_json("/ai-select/anchor-renders", "POST", anchor_request)
        self.assertEqual(miss["status"], "sceneChunkMiss")
        self.assertEqual(miss["missingChunkIds"], ["chunk-a"])
        self.assertEqual(miss["requestBinding"], anchor_request["requestBinding"])

        admission = self.request_json(
            "/spatial-scene-chunk-uploads/v1",
            "POST",
            {
                "sceneId": registered.scene_id,
                "sceneVersion": registered.scene_version,
                "chunkIds": miss["missingChunkIds"],
            },
        )
        upload_id = admission["uploadId"]
        self.assertIsInstance(upload_id, str)
        chunk = payload()
        with urlopen(Request(
            f"{self.endpoint}/spatial-scene-chunk-uploads/v1/{upload_id}/chunks/chunk-a",
            data=chunk,
            method="PUT",
            headers={
                "Origin": EDITOR_ORIGIN,
                "Content-Type": "application/octet-stream",
                "X-Spatial-Scene-Chunk-Digest": "sha256:" + hashlib.sha256(chunk).hexdigest(),
            },
        )) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            self.assertEqual(json.load(response)["status"], "stored")
        committed = self.request_json(
            f"/spatial-scene-chunk-uploads/v1/{upload_id}/commit", "POST", {}
        )
        self.assertEqual(committed["status"], "committed")
        rendered = self.request_json("/ai-select/anchor-renders", "POST", anchor_request)
        self.assertEqual(rendered["status"], "complete")
        self.assertEqual(len(self.renderer.scene_snapshots), 1)

        with urlopen(Request(
            f"{self.endpoint}/spatial-scene-manifests/v1/{registration['registrationId']}",
            method="DELETE",
            headers={"Origin": EDITOR_ORIGIN},
        )) as released:
            self.assertEqual(released.status, HTTPStatus.NO_CONTENT)
        absent = self.request_json("/ai-select/anchor-renders", "POST", anchor_request)
        self.assertEqual(absent["status"], "sceneCacheMiss")


if __name__ == "__main__":
    unittest.main()

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
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion import support_probe
from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.server import create_server
from selection_service_companion.spatial_scene_working_set import (
    SpatialChunkDescriptor,
    SpatialSceneManifest,
    SpatialSupportBounds,
)
from selection_service_companion.state import CompanionState
from selection_service_companion.support_probe import (
    AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
    AnchorSupportProbeCamera,
    count_observed_gaussians,
)


EDITOR_ORIGIN = "https://editor.example"
RGB_DIGEST = "sha256:" + hashlib.sha256(b"anchor-rgb").hexdigest()

# Identity camera at the world origin: camera coordinates equal world
# coordinates, so every projection below is exact decimal arithmetic.
PACKED_CAMERA: dict[str, object] = {
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
        "cx": 2.0,
        "cy": 2.0,
        "width": 4,
        "height": 4,
        "near": 0.1,
        "far": 100.0,
    },
    "conventionVersion": "opencv-camera-to-world/v1",
}

# Hand-computed projections under PACKED_CAMERA (u = 10 * x/z + 2, v likewise,
# rounded to the nearest integer pixel):
#   id 11 (0, 0, 5)        -> (2, 2) = pixel 10, kept
#   id 12 (0.25, 0, 2)     -> (3, 2) = pixel 11, kept (logit 0 == opacity 0.5)
#   id 13 (0.125, -0.25, 2)-> (3, 1) = pixel 7, kept
#   id 14 (0, 0, -5)       -> behind the camera, excluded
#   id 15 (0, 0, 5)        -> logit -0.25 < 0 (opacity < 0.5), excluded
#   id 16 (4, 0, 2)        -> u = 22 outside the 4x4 frame, excluded
#   id 17 (0, 0, 0.05)     -> in front of the near plane, excluded
#   id 18 (0, 0, 200)      -> beyond the far plane, excluded
#   id 19 (0, 0.5, 2)      -> v = 4.5 outside the 4x4 frame, excluded
GAUSSIANS: tuple[tuple[int, tuple[float, float, float], float], ...] = (
    (11, (0.0, 0.0, 5.0), 1.0),
    (12, (0.25, 0.0, 2.0), 0.0),
    (13, (0.125, -0.25, 2.0), 2.0),
    (14, (0.0, 0.0, -5.0), 1.0),
    (15, (0.0, 0.0, 5.0), -0.25),
    (16, (4.0, 0.0, 2.0), 1.0),
    (17, (0.0, 0.0, 0.05), 1.0),
    (18, (0.0, 0.0, 200.0), 1.0),
    (19, (0.0, 0.5, 2.0), 1.0),
)

# 4x4 = 16 pixels = 2 bytes, LSB-first: pixel p is bit (p & 7) of byte (p >> 3).
FULL_MASK = bytes([0x80, 0x0C])     # pixels {7, 10, 11}: all three projections
SINGLE_MASK = bytes([0x00, 0x04])   # pixel {10} only
EMPTY_MASK = bytes([0x01, 0x00])    # pixel {0}: foreground, but nothing projects there


def _render_scope(
    target_splat_id: str,
    gaussian_count: int,
    render_id_start: int,
    *,
    target_row_count: int | None = None,
) -> dict[str, object]:
    target_row_count = gaussian_count if target_row_count is None else target_row_count
    target_source_digest = "sha256:" + "b" * 64
    sources = [
        {
            "splatId": target_splat_id,
            "sourceContentDigest": target_source_digest,
            "gaussianCount": target_row_count,
        }
    ]
    entries = [
        {
            "splatId": target_splat_id,
            "role": "target",
            "sourceContentDigest": target_source_digest,
            "rowOffset": 0,
            "rowCount": target_row_count,
            "renderIdStart": render_id_start,
        }
    ]
    if target_row_count < gaussian_count:
        occluder_count = gaussian_count - target_row_count
        occluder_digest = "sha256:" + "c" * 64
        sources.append(
            {
                "splatId": "visible-occluder",
                "sourceContentDigest": occluder_digest,
                "gaussianCount": occluder_count,
            }
        )
        entries.append(
            {
                "splatId": "visible-occluder",
                "role": "occluder",
                "sourceContentDigest": occluder_digest,
                "rowOffset": target_row_count,
                "rowCount": occluder_count,
                "renderIdStart": render_id_start + target_row_count,
            }
        )
    identity = "sha256:" + hashlib.sha256(
        json.dumps(
            {
                "policyId": "visible-editor-splats-conservative/v1",
                "targetSplatId": target_splat_id,
                "sources": sources,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "policyId": "visible-editor-splats-conservative/v1",
        "targetSplatId": target_splat_id,
        "identityDigest": identity,
        "entries": entries,
    }


def _binary_fixture(
    *, target_row_count: int | None = None
) -> tuple[bytes, BinarySceneSnapshotManifest]:
    count = len(GAUSSIANS)
    payload = b"".join(
        (
            b"".join(struct.pack("<I", stable_id) for stable_id, _, _ in GAUSSIANS),
            b"".join(struct.pack("<3f", *mean) for _, mean, _ in GAUSSIANS),
            struct.pack("<4f", 0.0, 0.0, 0.0, 1.0) * count,
            struct.pack("<3f", 0.0, 0.0, 0.0) * count,
            b"".join(struct.pack("<f", logit) for _, _, logit in GAUSSIANS),
            struct.pack("<3f", 0.0, 0.0, 0.0) * count,
        )
    )
    fields: list[dict[str, object]] = []
    offset = 0
    for name, scalar_type, components in (
        ("stableIds", "uint32le", 1),
        ("means", "float32le", 3),
        ("rotationsXyzw", "float32le", 4),
        ("logScales", "float32le", 3),
        ("logitOpacities", "float32le", 1),
        ("dc", "float32le", 3),
        ("sh", "float32le", 0),
    ):
        byte_length = count * components * 4
        fields.append(
            {
                "name": name,
                "scalarType": scalar_type,
                "componentCount": components,
                "byteOffset": offset,
                "byteLength": byte_length,
            }
        )
        offset += byte_length
    content: dict[str, object] = {
        "protocolVersion": "1",
        "gaussianCount": count,
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
        "authoritativeRenderScope": _render_scope(
            "splat-1",
            count,
            GAUSSIANS[0][0],
            target_row_count=target_row_count,
        ),
        "shFloatCountPerGaussian": 0,
        "payloadByteLength": len(payload),
        "fields": fields,
    }
    chunk_byte_length = 64
    chunks = tuple(
        BinarySceneSnapshotChunk(
            index=index,
            offset=index * chunk_byte_length,
            byte_length=len(
                payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]
            ),
            digest="sha256:"
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
        scene_id="splat-1",
        scene_version=content_digest,
        content_digest=content_digest,
        content=content,
        chunk_byte_length=chunk_byte_length,
        chunks=chunks,
    )


def _request_body(scene_version: str, mask: bytes) -> dict[str, object]:
    return {
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
        "sceneId": "splat-1",
        "sceneVersion": scene_version,
        "renderConfigVersion": "supersplat-effective-rgb-v1",
        "supportProbeAttemptId": "probe-1",
        "viewId": "anchor-view",
        "cameraBinding": PACKED_CAMERA,
        "rgbDigest": RGB_DIGEST,
        "stableMask": {
            "encoding": "bitset-lsb-v1",
            "width": 4,
            "height": 4,
            "data": base64.b64encode(mask).decode("ascii"),
            "digest": "sha256:" + hashlib.sha256(mask).hexdigest(),
        },
        "supportProbePolicyVersion": AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
    }


def _spatial_payload() -> bytes:
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


def _spatial_manifest() -> SpatialSceneManifest:
    chunk = _spatial_payload()
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
        authoritative_render_scope=_render_scope("editor-splat:42", 1, 7),
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


# 10x10 = 100 pixels = 13 bytes. The single chunk Gaussian at (0, 0, 5)
# projects to pixel (5, 5) = 55, which is bit 7 of byte 6.
SPATIAL_MASK = bytes([0x00] * 6 + [0x80] + [0x00] * 6)


def _spatial_request_body(scene_version: str) -> dict[str, object]:
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
        "supportProbeAttemptId": "probe-1",
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
        "rgbDigest": RGB_DIGEST,
        "stableMask": {
            "encoding": "bitset-lsb-v1",
            "width": 10,
            "height": 10,
            "data": base64.b64encode(SPATIAL_MASK).decode("ascii"),
            "digest": "sha256:" + hashlib.sha256(SPATIAL_MASK).hexdigest(),
        },
        "supportProbePolicyVersion": AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
    }


class AnchorSupportProbeSemanticsTests(unittest.TestCase):
    """Direct policy checks over synthetic planes, with no service state."""

    CAMERA = AnchorSupportProbeCamera(
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

    def test_gates_depth_frustum_and_opacity(self) -> None:
        means = b"".join(
            (
                struct.pack("<3f", 0.0, 0.0, 5.0),    # kept: pixel 10
                struct.pack("<3f", 0.0, 0.0, -5.0),   # behind the camera
                struct.pack("<3f", 0.0, 0.0, 0.05),   # in front of the near plane
                struct.pack("<3f", 0.0, 0.0, 200.0),  # beyond the far plane
                struct.pack("<3f", 4.0, 0.0, 2.0),    # outside the frame in u
                struct.pack("<3f", 0.0, 0.5, 2.0),    # outside the frame in v
                struct.pack("<3f", 0.0, 0.0, 5.0),    # logit -0.25: opacity < 0.5
            )
        )
        logits = struct.pack("<7f", 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -0.25)

        count = count_observed_gaussians(
            planes=[(memoryview(means), memoryview(logits))],
            camera=self.CAMERA,
            mask=FULL_MASK,
        )

        self.assertEqual(count, 1)

    def test_opacity_gate_accepts_logit_zero(self) -> None:
        count = count_observed_gaussians(
            planes=[
                (
                    memoryview(struct.pack("<3f", 0.0, 0.0, 5.0)),
                    memoryview(struct.pack("<f", 0.0)),
                )
            ],
            camera=self.CAMERA,
            mask=bytes([0xFF, 0xFF]),
        )

        self.assertEqual(count, 1)

    def test_the_mask_bit_selects_the_projection_pixel(self) -> None:
        planes = [
            (
                memoryview(struct.pack("<3f", 0.0, 0.0, 5.0)),
                memoryview(struct.pack("<f", 1.0)),
            )
        ]

        self.assertEqual(
            count_observed_gaussians(
                planes=planes, camera=self.CAMERA, mask=SINGLE_MASK
            ),
            1,
        )
        self.assertEqual(
            count_observed_gaussians(
                planes=planes, camera=self.CAMERA, mask=EMPTY_MASK
            ),
            0,
        )

    def test_world_to_camera_translation_is_applied(self) -> None:
        camera = AnchorSupportProbeCamera(
            world_to_camera=(
                1.0, 0.0, 0.0, -1.0,
                0.0, 1.0, 0.0, -2.0,
                0.0, 0.0, 1.0, -3.0,
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
        planes = [
            (
                memoryview(struct.pack("<3f", 1.0, 2.0, 8.0)),  # camera z = 5
                memoryview(struct.pack("<f", 1.0)),
            )
        ]

        self.assertEqual(
            count_observed_gaussians(planes=planes, camera=camera, mask=FULL_MASK),
            1,
        )
        self.assertEqual(
            count_observed_gaussians(planes=planes, camera=camera, mask=EMPTY_MASK),
            0,
        )

    def test_inconsistent_planes_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            count_observed_gaussians(
                planes=[
                    (
                        memoryview(struct.pack("<3f", 0.0, 0.0, 5.0)),
                        memoryview(struct.pack("<2f", 1.0, 1.0)),
                    )
                ],
                camera=self.CAMERA,
                mask=FULL_MASK,
            )


class AnchorSupportProbeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.state = CompanionState(directory / "state")
        self.payload, self.manifest = _binary_fixture()
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

    def post_probe_error(
        self, body: dict[str, object], status: HTTPStatus
    ) -> dict[str, object]:
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    f"{self.endpoint}/ai-select/anchor-support-probes",
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/json",
                    },
                )
            )
        self.assertEqual(error.exception.code, status)
        return json.load(error.exception)

    def register_binary_snapshot(self) -> None:
        manifest = self.manifest
        admission = self.request_json(
            "/scene-snapshot-uploads/v1",
            "POST",
            {
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
            },
        )
        self.assertEqual(admission["status"], "staged")
        upload_id = admission["uploadId"]
        self.assertIsInstance(upload_id, str)
        for chunk in manifest.chunks:
            with urlopen(
                Request(
                    f"{self.endpoint}/scene-snapshot-uploads/v1/{upload_id}/chunks/{chunk.index}",
                    data=self.payload[chunk.offset:chunk.offset + chunk.byte_length],
                    method="PUT",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/octet-stream",
                        "X-SceneSnapshot-Chunk-Digest": chunk.digest,
                    },
                )
            ) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
        committed = self.request_json(
            f"/scene-snapshot-uploads/v1/{upload_id}/commit", "POST", {}
        )
        self.assertEqual(committed["status"], "committed")

    def test_counts_projected_gaussians_over_the_stable_mask(self) -> None:
        self.register_binary_snapshot()
        body = _request_body(self.manifest.scene_version, FULL_MASK)

        response = self.request_json(
            "/ai-select/anchor-support-probes", "POST", body
        )

        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["requestBinding"], body["requestBinding"])
        self.assertEqual(response["targetSplatId"], "splat-1")
        self.assertEqual(response["sceneId"], "splat-1")
        self.assertEqual(response["sceneVersion"], self.manifest.scene_version)
        self.assertEqual(response["renderConfigVersion"], "supersplat-effective-rgb-v1")
        self.assertEqual(response["supportProbeAttemptId"], "probe-1")
        self.assertEqual(response["viewId"], "anchor-view")
        self.assertEqual(response["cameraBinding"], body["cameraBinding"])
        self.assertEqual(response["rgbDigest"], RGB_DIGEST)
        self.assertEqual(
            response["stableMaskDigest"], body["stableMask"]["digest"]  # type: ignore[index]
        )
        self.assertEqual(
            response["supportProbePolicyVersion"],
            AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
        )
        # The verdict is exactly a computability flag and its diagnostic
        # count: no Stable Gaussian IDs or ownership/Evidence-shaped data.
        self.assertEqual(
            response["support"],
            {"computable": True, "observedGaussianCount": 3},
        )

    def test_visible_occluder_cannot_establish_target_support(self) -> None:
        self.payload, self.manifest = _binary_fixture(target_row_count=1)
        self.register_binary_snapshot()
        # Pixel 7 observes only row 2, which belongs to the read-only
        # occluder scope. The single target row projects to pixel 10.
        occluder_only_mask = bytes([0x80, 0x00])
        body = _request_body(self.manifest.scene_version, occluder_only_mask)

        response = self.request_json(
            "/ai-select/anchor-support-probes", "POST", body
        )

        self.assertEqual(
            response["support"],
            {"computable": False, "observedGaussianCount": 0},
        )

    def test_reports_no_computable_support_when_the_mask_misses_every_projection(self) -> None:
        self.register_binary_snapshot()
        body = _request_body(self.manifest.scene_version, EMPTY_MASK)

        response = self.request_json(
            "/ai-select/anchor-support-probes", "POST", body
        )

        self.assertEqual(response["status"], "complete")
        self.assertEqual(
            response["support"],
            {"computable": False, "observedGaussianCount": 0},
        )

    def test_rejects_an_invalid_stable_mask_digest(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)
        body["stableMask"]["digest"] = "sha256:" + hashlib.sha256(b"other").hexdigest()  # type: ignore[index]

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_rejects_stable_mask_dimensions_that_disagree_with_the_camera(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)
        body["stableMask"]["width"] = 5  # type: ignore[index]

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_rejects_an_unsupported_policy_version(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)
        body["supportProbePolicyVersion"] = "anchor-support-probe/v2"

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_rejects_an_empty_probe_attempt_identity(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)
        body["supportProbeAttemptId"] = ""

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_rejects_a_mask_with_dirty_trailing_bits(self) -> None:
        # A 3x3 mask uses 9 of 16 bits; the high 7 bits of byte 1 must be zero.
        dirty = bytes([0x00, 0x02])
        body = _request_body("snapshot-v1", FULL_MASK)
        camera = json.loads(json.dumps(body["cameraBinding"]))
        camera["projection"]["width"] = 3
        camera["projection"]["height"] = 3
        body["cameraBinding"] = camera
        body["stableMask"] = {
            "encoding": "bitset-lsb-v1",
            "width": 3,
            "height": 3,
            "data": base64.b64encode(dirty).decode("ascii"),
            "digest": "sha256:" + hashlib.sha256(dirty).hexdigest(),
        }

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_rejects_a_malformed_rgb_digest(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)
        body["rgbDigest"] = "not-a-digest"

        error = self.post_probe_error(body, HTTPStatus.BAD_REQUEST)

        self.assertEqual(error["status"], "invalidRequest")

    def test_returns_a_bound_cache_miss_for_an_unknown_scene(self) -> None:
        body = _request_body("snapshot-v1", FULL_MASK)

        response = self.request_json(
            "/ai-select/anchor-support-probes", "POST", body
        )

        self.assertEqual(response["status"], "sceneCacheMiss")
        self.assertEqual(response["requestBinding"], body["requestBinding"])
        self.assertEqual(response["targetSplatId"], "splat-1")
        self.assertEqual(response["sceneId"], "splat-1")
        self.assertEqual(response["sceneVersion"], "snapshot-v1")
        self.assertEqual(response["renderConfigVersion"], "supersplat-effective-rgb-v1")
        self.assertEqual(response["supportProbeAttemptId"], "probe-1")
        self.assertEqual(response["viewId"], "anchor-view")
        self.assertEqual(response["cameraBinding"], body["cameraBinding"])

    def test_rejects_a_legacy_json_scene_snapshot_as_a_domain_failure(self) -> None:
        self.request_json(
            "/scene-snapshots/splat-1/snapshot-v1",
            "PUT",
            {
                "protocolVersion": "1",
                "sceneId": "splat-1",
                "sceneVersion": "snapshot-v1",
                "gaussianCount": 1,
                "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
                "attributeSchema": "mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
                "stableIdSchema": "uint32",
                "appearancePolicy": "effective-editor-dc-sh-bands-0",
                "renderConfiguration": {
                    "version": "supersplat-effective-rgb-v1",
                    "backgroundRgba": [0, 0, 0, 1],
                    "alphaMode": "opaque-background",
                    "shBands": 0,
                    "rasterizer": "playcanvas-gsplat-classic",
                },
                "gaussians": [
                    {
                        "stableId": 3,
                        "mean": [0, 0, 0],
                        "rotation": [0, 0, 0, 1],
                        "logScale": [0, 0, 0],
                        "logitOpacity": 0,
                        "dc": [0, 0, 0],
                        "sh": [],
                    }
                ],
            },
        )

        error = self.post_probe_error(
            _request_body("snapshot-v1", FULL_MASK), HTTPStatus.CONFLICT
        )

        self.assertEqual(error["status"], "supportProbeError")
        self.assertEqual(error["code"], "supportProbeFailure")


class AnchorSupportProbeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.state = CompanionState(Path(self.temporary_directory.name))
        self.payload, self.manifest = _binary_fixture()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def register_binary_snapshot(self) -> None:
        admission = self.state.begin_binary_scene_snapshot_upload(self.manifest)
        upload_id = admission.upload_id
        self.assertIsNotNone(upload_id)
        assert upload_id is not None
        for chunk in self.manifest.chunks:
            self.state.accept_binary_scene_snapshot_chunk(
                upload_id,
                chunk.index,
                self.payload[chunk.offset:chunk.offset + chunk.byte_length],
                chunk.digest,
            )
        self.state.commit_binary_scene_snapshot_upload(upload_id)

    def test_the_same_attempt_replays_and_a_new_attempt_reexecutes(self) -> None:
        self.register_binary_snapshot()
        body = _request_body(self.manifest.scene_version, FULL_MASK)

        with patch(
            "selection_service_companion.state.count_observed_gaussians",
            wraps=support_probe.count_observed_gaussians,
        ) as counter:
            first = self.state.probe_ai_select_anchor_support(body)
            replay = self.state.probe_ai_select_anchor_support(body)
            self.assertEqual(replay, first)
            self.assertEqual(counter.call_count, 1)

            new_attempt = _request_body(self.manifest.scene_version, FULL_MASK)
            new_attempt["supportProbeAttemptId"] = "probe-2"
            second = self.state.probe_ai_select_anchor_support(new_attempt)
            self.assertEqual(counter.call_count, 2)

        self.assertEqual(first["support"], {"computable": True, "observedGaussianCount": 3})
        self.assertEqual(second["support"], first["support"])
        self.assertEqual(second["supportProbeAttemptId"], "probe-2")

    def test_spatial_chunk_miss_then_complete_after_atomic_residency(self) -> None:
        registered = _spatial_manifest()
        self.state.register_spatial_scene_manifest(registered)
        body = _spatial_request_body(registered.scene_version)

        miss = self.state.probe_ai_select_anchor_support(body)

        self.assertEqual(miss["status"], "sceneChunkMiss")
        self.assertEqual(miss["requestBinding"], body["requestBinding"])
        self.assertEqual(miss["cameraBinding"], body["cameraBinding"])
        self.assertEqual(miss["supportProbeAttemptId"], "probe-1")
        self.assertEqual(miss["missingChunkIds"], ["chunk-a"])
        self.assertTrue(str(miss["workingSetToken"]).startswith("sha256:"))

        admission = self.state.begin_spatial_scene_chunk_upload(
            registered.scene_id, registered.scene_version, ("chunk-a",)
        )
        chunk = _spatial_payload()
        self.state.accept_spatial_scene_chunk(
            admission.upload_id or "",
            "chunk-a",
            chunk,
            "sha256:" + hashlib.sha256(chunk).hexdigest(),
        )
        self.state.commit_spatial_scene_chunk_upload(admission.upload_id or "")

        complete = self.state.probe_ai_select_anchor_support(body)

        self.assertEqual(complete["status"], "complete")
        self.assertEqual(
            complete["support"], {"computable": True, "observedGaussianCount": 1}
        )
        self.assertEqual(
            complete["stableMaskDigest"],
            "sha256:" + hashlib.sha256(SPATIAL_MASK).hexdigest(),
        )

    def test_spatial_unknown_scene_returns_a_bound_cache_miss(self) -> None:
        body = _spatial_request_body("sha256:" + "b" * 64)

        miss = self.state.probe_ai_select_anchor_support(body)

        self.assertEqual(miss["status"], "sceneCacheMiss")
        self.assertEqual(miss["requestBinding"], body["requestBinding"])
        self.assertEqual(miss["cameraBinding"], body["cameraBinding"])


if __name__ == "__main__":
    unittest.main()

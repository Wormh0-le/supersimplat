"""Ticket 08 real-GPU smoke validation of the Companion render/hint/plan routes.

Runs the REAL GsplatContributorRenderer (locked gsplat/CUDA typed path) behind
a loopback server against the tiny packed 5-Gaussian fixture, and verifies:

  1. locked-runtime readiness + packed binary Scene Snapshot registration;
  2. POST /ai-select/anchor-renders -> 200 complete + real alpha_coverage > 0
     (confirmed in-process on the same production renderer artifact);
  3. POST /ai-select/view-renders with the same camera -> 200 complete;
  4. POST /ai-select/view-renders with a camera pointed at empty space
     -> 409 blankRender (proves the typed-path alpha_coverage gate);
  5. POST /ai-select/target-geometry-hints -> 200 hint with the expected
     fixture center/extent, then POST /ai-select/local-key-view-plans
     -> 200 with 3 bounded local Key Views.

Throwaway validation script: no source or test changes. Run from repo root:

  uv run --project selection-service-companion --locked --extra renderer \
      python .scratch/ai-select-v1/browser-validation/08-gpu-smoke.py

The first rasterization may take minutes while gsplat JIT-compiles its CUDA
kernels.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState
from selection_service_companion.target_geometry import (
    AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
    AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EDITOR_ORIGIN = "https://editor.example"
RGB_DIGEST = "sha256:" + hashlib.sha256(b"anchor-rgb").hexdigest()
CAMERA_DIGEST = "sha256:" + hashlib.sha256(b"anchor-camera-binding").hexdigest()

# The same 5-Gaussian fixture as the route tests: identity 4x4 camera at the
# world origin looking down +z (OpenCV convention).
GAUSSIANS: tuple[tuple[int, tuple[float, float, float], float], ...] = (
    (11, (0.0, 0.0, 5.0), 1.0),
    (12, (0.25, 0.0, 2.0), 0.0),
    (13, (0.125, -0.25, 2.0), 2.0),
    (14, (0.0, 0.0, -5.0), 1.0),
    (15, (0.0, 0.0, 5.0), -0.25),
)

PROJECTION = {
    "model": "pinhole",
    "fx": 10.0,
    "fy": 10.0,
    "cx": 2.0,
    "cy": 2.0,
    "width": 4,
    "height": 4,
    "near": 0.1,
    "far": 100.0,
}

ANCHOR_CAMERA: dict[str, object] = {
    "revision": 0,
    "cameraToWorld": [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ],
    "projection": PROJECTION,
    "conventionVersion": "opencv-camera-to-world/v1",
}

# Camera looking straight up (+y): every fixture Gaussian has y <= 0, so all
# of them sit at or behind the near plane of this view -> blank render.
BLANK_CAMERA: dict[str, object] = {
    "revision": 0,
    "cameraToWorld": [
        1.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, -1.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ],
    "projection": PROJECTION,
    "conventionVersion": "opencv-camera-to-world/v1",
}

# Pixels {7, 10, 11}: the in-frame support projections of ids 11, 12, 13.
FULL_MASK = bytes([0x80, 0x0C])

EXPECTED_CENTER = (0.1875, -0.125, 2.0)
EXPECTED_EXTENT = (0.0926625, 0.185325, 0.001)


def _binary_fixture() -> tuple[bytes, BinarySceneSnapshotManifest]:
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


def _request_binding() -> dict[str, object]:
    return {
        "targetContextId": "context-1",
        "contextRevision": 0,
        "dependencyToken": {
            "splatId": "splat-1",
            "renderStateToken": "render-v1",
            "geometryToken": "geometry-v1",
            "gaussianIdentityToken": "ids-v1",
            "worldTransformToken": "world-v1",
        },
    }


def _render_body(
    scene_version: str, view_id: str, camera: dict[str, object]
) -> dict[str, object]:
    return {
        "requestBinding": _request_binding(),
        "targetSplatId": "splat-1",
        "sceneId": "splat-1",
        "sceneVersion": scene_version,
        "renderConfigVersion": "supersplat-effective-rgb-v1",
        "renderAttemptId": f"render-attempt-{view_id}",
        "viewId": view_id,
        "cameraBinding": camera,
    }


def _mask_payload(mask: bytes) -> dict[str, object]:
    return {
        "encoding": "bitset-lsb-v1",
        "width": 4,
        "height": 4,
        "data": base64.b64encode(mask).decode("ascii"),
        "digest": "sha256:" + hashlib.sha256(mask).hexdigest(),
    }


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)

    payload, manifest = _binary_fixture()
    scene_version = manifest.scene_version

    temporary = tempfile.TemporaryDirectory()
    directory = Path(temporary.name)
    state = CompanionState(directory / "state")
    renderer = state.contributor_renderer
    if renderer is None or getattr(renderer, "renderer_id", None) != "gsplat":
        record("production renderer configured", False, f"renderer={renderer!r}")
        return _summary(results)
    record(
        "production renderer configured",
        getattr(renderer, "requires_locked_runtime", False) is True,
        f"{type(renderer).__name__} requires_locked_runtime="
        f"{getattr(renderer, 'requires_locked_runtime', None)}",
    )

    state.install_release("0.1.0", REPO_ROOT / "selection-service-companion" / "uv.lock")
    capability = state._renderer_capability(state.require_release())
    runtime_status = state.renderer_runtime.status()
    print(
        f"       runtime: status={runtime_status.status} "
        f"cuda={runtime_status.cuda_version} message={runtime_status.message}",
        flush=True,
    )
    if capability["status"] != "ready":
        record(
            "locked runtime ready",
            False,
            f"capability={capability.get('status')}: {capability.get('message')}",
        )
        return _summary(results)
    record("locked runtime ready", True, f"renderer capability {capability['status']}")

    server = create_server(
        state=state,
        endpoint="http://127.0.0.1:0",
        profile="loopback",
        allowed_origins=[EDITOR_ORIGIN],
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"

    def post(path: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
        try:
            with urlopen(
                Request(
                    f"{endpoint}{path}",
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers={
                        "Origin": EDITOR_ORIGIN,
                        "Content-Type": "application/json",
                    },
                )
            ) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    try:
        # Step 1: packed binary Scene Snapshot registration.
        admission_status, admission = post(
            "/scene-snapshot-uploads/v1",
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
        upload_id = admission.get("uploadId")
        committed: dict[str, object] = {}
        if admission_status == 200 and isinstance(upload_id, str):
            chunks_ok = True
            for chunk in manifest.chunks:
                try:
                    with urlopen(
                        Request(
                            f"{endpoint}/scene-snapshot-uploads/v1/{upload_id}/chunks/{chunk.index}",
                            data=payload[chunk.offset:chunk.offset + chunk.byte_length],
                            method="PUT",
                            headers={
                                "Origin": EDITOR_ORIGIN,
                                "Content-Type": "application/octet-stream",
                                "X-SceneSnapshot-Chunk-Digest": chunk.digest,
                            },
                        )
                    ) as response:
                        chunks_ok = chunks_ok and response.status == 200
                except HTTPError:
                    chunks_ok = False
            if chunks_ok:
                _, committed = post(
                    f"/scene-snapshot-uploads/v1/{upload_id}/commit", {}
                )
        record(
            "step 1: packed scene registration",
            committed.get("status") == "committed",
            f"sceneVersion={scene_version[:24]}… committed={committed.get('status')}",
        )

        # Step 2: anchor render on the real gsplat/CUDA typed path.
        print("       rasterizing (gsplat CUDA JIT may take minutes on first run)…", flush=True)
        anchor_status, anchor = post(
            "/ai-select/anchor-renders",
            _render_body(scene_version, "anchor-view", ANCHOR_CAMERA),
        )
        anchor_ok = anchor_status == 200 and anchor.get("status") == "complete"
        png = b""
        nonzero_pixels = -1
        if anchor_ok:
            from io import BytesIO

            from PIL import Image

            png = base64.b64decode(anchor["rgb"]["pngBase64"])
            with Image.open(BytesIO(png)) as image:
                image.load()
                rgb = image.convert("RGB").tobytes()
                nonzero_pixels = sum(
                    1
                    for index in range(0, len(rgb), 3)
                    if rgb[index:index + 3] != b"\x00\x00\x00"
                )
                anchor_ok = (
                    image.size == (4, 4)
                    and anchor["rgb"]["digest"]
                    == f"sha256:{hashlib.sha256(png).hexdigest()}"
                    and anchor["rgb"]["width"] == 4
                    and anchor["rgb"]["height"] == 4
                    and nonzero_pixels > 0
                )
        record(
            "step 2a: anchor render 200 complete, non-trivial PNG",
            anchor_ok,
            f"http={anchor_status} png={len(png)}B non-background-pixels={nonzero_pixels}/16",
        )

        # Direct in-process render through the SAME production renderer: the
        # response wire format carries no alpha_coverage, so confirm the
        # typed artifact really computed it here.
        coverage_detail = "n/a"
        coverage_ok = False
        registered = state.scene_snapshot("splat-1", scene_version)
        try:
            artifact = renderer.render_anchor(
                scene_snapshot=registered.scene,
                view_id="anchor-view",
                camera={
                    "model": "pinhole",
                    "convention": "opencv-world-to-camera",
                    "worldToCamera": [
                        1.0, 0.0, 0.0, 0.0,
                        0.0, 1.0, 0.0, 0.0,
                        0.0, 0.0, 1.0, 0.0,
                        0.0, 0.0, 0.0, 1.0,
                    ],
                    "intrinsics": [10.0, 0.0, 2.0, 0.0, 10.0, 2.0, 0.0, 0.0, 1.0],
                    "nearPlane": 0.1,
                    "farPlane": 100.0,
                },
                width=4,
                height=4,
            )
            coverage_detail = f"alpha_coverage={artifact.alpha_coverage}"
            coverage_ok = (
                artifact.alpha_coverage is not None and artifact.alpha_coverage > 0.0
            )
        except Exception as error:  # noqa: BLE001 — smoke script reports, not raises
            coverage_detail = f"render failed: {type(error).__name__}: {error}"
        record("step 2b: typed artifact alpha_coverage > 0", coverage_ok, coverage_detail)

        # Step 3: same camera through the view-renders route.
        view_status, view = post(
            "/ai-select/view-renders",
            _render_body(scene_version, "key-view-smoke", ANCHOR_CAMERA),
        )
        record(
            "step 3: view render of visible scene 200",
            view_status == 200 and view.get("status") == "complete",
            f"http={view_status} viewId={view.get('viewId')}",
        )

        # Step 4: camera pointed at empty space -> 409 blankRender.
        blank_status, blank = post(
            "/ai-select/view-renders",
            _render_body(scene_version, "key-view-blank", BLANK_CAMERA),
        )
        record(
            "step 4: blank view render rejected",
            blank_status == 409
            and blank.get("status") == "viewRenderError"
            and blank.get("code") == "blankRender",
            f"http={blank_status} body={blank}",
        )

        # Step 5a: TargetGeometryHint route on the real server.
        hint_status, hint_response = post(
            "/ai-select/target-geometry-hints",
            {
                "requestBinding": _request_binding(),
                "targetSplatId": "splat-1",
                "sceneId": "splat-1",
                "sceneVersion": scene_version,
                "renderConfigVersion": "supersplat-effective-rgb-v1",
                "geometryAttemptId": "target-geometry-hint-attempt-1",
                "anchorCameraBinding": ANCHOR_CAMERA,
                "anchorCameraBindingDigest": CAMERA_DIGEST,
                "anchorRgbDigest": RGB_DIGEST,
                "anchorStableMask": _mask_payload(FULL_MASK),
                "geometryPolicyVersion": AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
            },
        )
        hint = hint_response.get("hint", {}) if hint_status == 200 else {}
        center = hint.get("centerWorld", [])
        extent = hint.get("extentWorld", [])
        center_ok = len(center) == 3 and all(
            abs(actual - expected) < 1e-9
            for actual, expected in zip(center, EXPECTED_CENTER, strict=True)
        )
        extent_ok = len(extent) == 3 and all(
            abs(actual - expected) < 1e-6
            for actual, expected in zip(extent, EXPECTED_EXTENT, strict=True)
        )
        print(f"       hint center={center} extent={extent}", flush=True)
        print(
            f"       hint quality={hint.get('quality')} reasons={hint.get('reasons')}",
            flush=True,
        )
        record(
            "step 5a: target geometry hint 200 + expected geometry",
            hint_status == 200
            and hint_response.get("status") == "complete"
            and center_ok
            and extent_ok
            and hint.get("quality") == "limited",
            f"http={hint_status} center-ok={center_ok} extent-ok={extent_ok}",
        )

        # Step 5b: LocalKeyViewPlan route on the real server.
        plan_status, plan_response = post(
            "/ai-select/local-key-view-plans",
            {
                "requestBinding": _request_binding(),
                "targetSplatId": "splat-1",
                "planAttemptId": "local-key-view-plan-attempt-1",
                "batchOrdinal": 0,
                "anchorCameraBinding": ANCHOR_CAMERA,
                "anchorCameraBindingDigest": CAMERA_DIGEST,
                "anchorRgbDigest": RGB_DIGEST,
                "anchorStableMaskDigest": "sha256:"
                + hashlib.sha256(FULL_MASK).hexdigest(),
                "targetGeometryHint": hint,
                "localViewPolicyVersion": AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
            },
        )
        plan = plan_response.get("plan", {}) if plan_status == 200 else {}
        view_ids = [view.get("viewId") for view in plan.get("orderedViews", [])]
        record(
            "step 5b: local key view plan 200 with 3 views",
            plan_status == 200
            and plan_response.get("status") == "complete"
            and view_ids == ["key-view-0-0", "key-view-0-1", "key-view-0-2"],
            f"http={plan_status} viewIds={view_ids}",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        temporary.cleanup()

    return _summary(results)


def _summary(results: list[tuple[str, bool, str]]) -> int:
    failed = [name for name, ok, _ in results if not ok]
    print("=" * 70)
    if failed:
        print(f"SMOKE RESULT: FAIL ({len(failed)} of {len(results)} failed: {failed})")
        return 1
    print(f"SMOKE RESULT: PASS (all {len(results)} checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run Ticket 02B parity/working-set metrics against an unedited SH0--SH3 PLY.

This is a local, operator-run validation harness, not a production import
path.  It deliberately maps an unedited standard 3DGS PLY into the same typed
SoA planes used by the spatial protocol, without materialising per-Gaussian
Python objects.  A browser-produced effective SceneSnapshot remains the
production authority; use this harness only when its raw-Ply/no-edit
assumption is true.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import resource
import tempfile
import time
from typing import Any

import numpy as np

from selection_service_companion.gsplat_renderer import (
    GsplatContributorRenderer,
    LockedGsplatBackend,
)
from selection_service_companion.spatial_scene_working_set import (
    SpatialChunkDescriptor,
    SpatialSceneManifest,
    SpatialSceneStore,
    SpatialSupportBounds,
)


DEFAULT_CHUNK_BYTES = 1 * 1024 * 1024
VALIDITY_CUT = 1.0 / 255.0
OPACITY_GUARD = 1.0 - 2.0 ** -12
WORLD_EPSILON = 1e-5
SCALE_EPSILON = 2.0 ** -18


@dataclass(frozen=True)
class PlyPlanes:
    count: int
    sh_float_count: int
    means: np.ndarray
    rotations_xyzw: np.ndarray
    log_scales: np.ndarray
    logit_opacities: np.ndarray
    dc: np.ndarray
    sh: np.ndarray


def bytes_per_gaussian(sh_float_count: int) -> int:
    return 64 + 4 * sh_float_count


def sh_bands_for(sh_float_count: int) -> int:
    try:
        return {0: 0, 9: 1, 24: 2, 45: 3}[sh_float_count]
    except KeyError as error:
        raise ValueError(
            'Ticket 02B benchmark supports only SH0 through SH3 PLY records'
        ) from error


def sha256(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def read_binary_ply(path: Path) -> PlyPlanes:
    with path.open('rb') as source:
        header = bytearray()
        while not header.endswith(b'end_header\n'):
            byte = source.read(1)
            if not byte:
                raise ValueError('PLY header is incomplete')
            header.extend(byte)
    lines = bytes(header).splitlines()
    if lines[0] != b'ply' or b'format binary_little_endian 1.0' not in lines:
        raise ValueError('Ticket 02B benchmark requires binary_little_endian PLY')
    count = next(
        int(line.split()[-1]) for line in lines if line.startswith(b'element vertex ')
    )
    properties = [
        line.split()[-1].decode('ascii')
        for line in lines
        if line.startswith(b'property float ')
    ]
    if len(properties) != len([line for line in lines if line.startswith(b'property ')]):
        raise ValueError('Ticket 02B benchmark currently supports float-only PLY attributes')
    required = {
        'x', 'y', 'z', 'f_dc_0', 'f_dc_1', 'f_dc_2', 'opacity',
        'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3',
    }
    if not required.issubset(properties):
        raise ValueError('PLY does not have standard 3DGS Gaussian attributes')
    rest = [name for name in properties if name.startswith('f_rest_')]
    rest_indices = sorted(int(name.removeprefix('f_rest_')) for name in rest)
    if rest_indices != list(range(len(rest_indices))):
        raise ValueError('PLY f_rest properties must be contiguous from f_rest_0')
    sh_bands_for(len(rest_indices))
    data = np.memmap(
        path,
        dtype=np.dtype([(name, '<f4') for name in properties]),
        mode='r',
        offset=len(header),
        shape=(count,),
    )
    return PlyPlanes(
        count=count,
        sh_float_count=len(rest_indices),
        means=np.column_stack((data['x'], data['y'], data['z'])).astype(np.float32),
        rotations_xyzw=np.column_stack(
            (data['rot_1'], data['rot_2'], data['rot_3'], data['rot_0'])
        ).astype(np.float32),
        log_scales=np.column_stack(
            (data['scale_0'], data['scale_1'], data['scale_2'])
        ).astype(np.float32),
        logit_opacities=np.asarray(data['opacity'], dtype=np.float32),
        dc=np.column_stack(
            (data['f_dc_0'], data['f_dc_1'], data['f_dc_2'])
        ).astype(np.float32),
        sh=(
            np.column_stack([data[f'f_rest_{index}'] for index in rest_indices]).astype(np.float32)
            if rest_indices else np.empty((count, 0), dtype=np.float32)
        ),
    )


def morton_order(means: np.ndarray) -> np.ndarray:
    minimum = means.min(axis=0)
    maximum = means.max(axis=0)
    quantized = np.floor((means - minimum) / (maximum - minimum) * 1023.0)
    quantized = np.clip(quantized, 0, 1023).astype(np.uint32)
    key = np.zeros(means.shape[0], dtype=np.uint32)
    for bit in range(10):
        key |= ((quantized[:, 0] >> bit) & 1) << (3 * bit)
        key |= ((quantized[:, 1] >> bit) & 1) << (3 * bit + 1)
        key |= ((quantized[:, 2] >> bit) & 1) << (3 * bit + 2)
    return np.lexsort((np.arange(means.shape[0]), key)).astype(np.uint32)


def support_extents(planes: PlyPlanes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The exact v1 support-envelope formula, vectorized over typed planes."""

    rotations = planes.rotations_xyzw.astype(np.float64)
    rotations /= np.linalg.norm(rotations, axis=1)[:, None]
    x, y, z, w = rotations.T
    scales = np.exp(planes.log_scales.astype(np.float64))
    opacity = 1.0 / (1.0 + np.exp(-planes.logit_opacities.astype(np.float64)))
    nonempty = opacity >= VALIDITY_CUT * OPACITY_GUARD
    support_radius = np.sqrt(np.maximum(
        0.0,
        2.0 * np.log(np.maximum(opacity, VALIDITY_CUT) / VALIDITY_CUT),
    ))
    r00, r01, r02 = 1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)
    r10, r11, r12 = 2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)
    r20, r21, r22 = 2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)
    epsilon = WORLD_EPSILON + SCALE_EPSILON * np.maximum(1.0, scales.max(axis=1))
    extent = np.column_stack((
        support_radius * np.sqrt((r00 * scales[:, 0]) ** 2 + (r01 * scales[:, 1]) ** 2 + (r02 * scales[:, 2]) ** 2) + epsilon,
        support_radius * np.sqrt((r10 * scales[:, 0]) ** 2 + (r11 * scales[:, 1]) ** 2 + (r12 * scales[:, 2]) ** 2) + epsilon,
        support_radius * np.sqrt((r20 * scales[:, 0]) ** 2 + (r21 * scales[:, 1]) ** 2 + (r22 * scales[:, 2]) ** 2) + epsilon,
    ))
    return planes.means.astype(np.float64) - extent, planes.means.astype(np.float64) + extent, nonempty


def chunk_payload(planes: PlyPlanes, rows: np.ndarray) -> bytes:
    count = len(rows)
    payload = bytearray(count * bytes_per_gaussian(planes.sh_float_count))
    offset = 0
    for values in (
        rows.astype('<u4', copy=False),
        rows.astype('<u4', copy=False),
        planes.means[rows],
        planes.rotations_xyzw[rows],
        planes.log_scales[rows],
        planes.logit_opacities[rows],
        planes.dc[rows],
        planes.sh[rows],
    ):
        bytes_view = np.ascontiguousarray(
            values, dtype=values.dtype.newbyteorder('<')
        ).view(np.uint8)
        payload[offset:offset + bytes_view.nbytes] = bytes_view.tobytes()
        offset += bytes_view.nbytes
    assert offset == len(payload)
    return bytes(payload)


def camera_for(target: np.ndarray, resolution: int) -> dict[str, object]:
    # A narrow, plausible Anchor aimed at a populated scene corner.  The exact
    # camera is included in the final report, so the selective/full comparison
    # is reproducible rather than an implicit favorable choice.
    eye = target + np.array((0.0, -25.0, 8.0))
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.array((0.0, 0.0, 1.0)))
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    down /= np.linalg.norm(down)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((right, down, forward))
    matrix[:3, 3] = eye
    focal_length = 1800.0 * resolution / 512.0
    return {
        'revision': 0,
        'cameraToWorld': matrix.reshape(-1).tolist(),
        'projection': {
            'model': 'pinhole', 'fx': focal_length, 'fy': focal_length,
            'cx': resolution / 2.0, 'cy': resolution / 2.0,
            'width': resolution, 'height': resolution,
            'near': 0.01, 'far': 1000.0,
        },
        'conventionVersion': 'opencv-camera-to-world/v1',
    }


def renderer_camera(camera: dict[str, object]) -> dict[str, object]:
    matrix = np.asarray(camera['cameraToWorld'], dtype=np.float64).reshape(4, 4)
    rotation = matrix[:3, :3]
    translation = matrix[:3, 3]
    world_to_camera = np.eye(4)
    world_to_camera[:3, :3] = rotation.T
    world_to_camera[:3, 3] = -rotation.T @ translation
    projection = camera['projection']
    assert isinstance(projection, dict)
    return {
        'model': 'pinhole',
        'convention': 'opencv-world-to-camera',
        'worldToCamera': world_to_camera.reshape(-1).tolist(),
        'intrinsics': [
            projection['fx'], 0.0, projection['cx'],
            0.0, projection['fy'], projection['cy'],
            0.0, 0.0, 1.0,
        ],
        'nearPlane': projection['near'],
        'farPlane': projection['far'],
    }


def contributor_global_ids(raster: Any, stable_ids: Any) -> tuple[Any, ...]:
    rows: list[Any] = []
    for image_row in raster.contributor_ids:
        pixels: list[Any] = []
        for ids in image_row:
            pixels.append(tuple(-1 if value < 0 else int(stable_ids[value]) for value in ids))
        rows.append(tuple(pixels))
    return tuple(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--ply', required=True, type=Path)
    parser.add_argument('--chunk-bytes', type=int, default=DEFAULT_CHUNK_BYTES)
    parser.add_argument('--resolution', type=int, default=512)
    parser.add_argument(
        '--target-mode',
        choices=('first-gaussian', 'first-chunk-midpoint'),
        default='first-gaussian',
    )
    args = parser.parse_args()
    if args.resolution <= 0:
        raise ValueError('resolution must be positive')
    started = time.perf_counter()
    planes = read_binary_ply(args.ply)
    parse_seconds = time.perf_counter() - started
    bytes_per_record = bytes_per_gaussian(planes.sh_float_count)
    if args.chunk_bytes < bytes_per_record or args.chunk_bytes > 4 * 1024 * 1024:
        raise ValueError('chunk-bytes must be within one bounded v1 chunk')
    ordering_started = time.perf_counter()
    order = morton_order(planes.means)
    lower, upper, nonempty = support_extents(planes)
    rows_per_chunk = args.chunk_bytes // bytes_per_record
    descriptors: list[SpatialChunkDescriptor] = []
    payloads: dict[str, bytes] = {}
    for index, start in enumerate(range(0, planes.count, rows_per_chunk)):
        rows = np.sort(order[start:start + rows_per_chunk])
        payload = chunk_payload(planes, rows)
        active = rows[nonempty[rows]]
        bounds = SpatialSupportBounds.empty() if not len(active) else SpatialSupportBounds.finite(
            tuple(lower[active].min(axis=0)), tuple(upper[active].max(axis=0))
        )
        chunk_id = f'spatial-{index:08d}'
        payloads[chunk_id] = payload
        descriptors.append(SpatialChunkDescriptor(
            chunk_id=chunk_id,
            chunk_digest=sha256(payload),
            byte_length=len(payload),
            gaussian_count=len(rows),
            global_ordinal_min=int(rows[0]),
            global_ordinal_max=int(rows[-1]),
            support_bounds=bounds,
        ))
    packing_seconds = time.perf_counter() - ordering_started
    # Stable benchmark identity over all typed payload content; the PLY has no
    # editor-side edits, so this names this exact raw/effective fixture.
    content_hash = hashlib.sha256()
    for descriptor in descriptors:
        content_hash.update(descriptor.chunk_digest.encode('ascii'))
    version = 'sha256:' + content_hash.hexdigest()
    manifest = SpatialSceneManifest(
        scene_id='benchmark-splat:real-sh3', scene_version=version, content_digest=version,
        target_splat_id='benchmark-splat:real-sh3', total_gaussian_count=planes.count,
        coordinate_convention='right-handed world coordinates; quaternion xyzw',
        stable_id_schema='uint32',
        attribute_schema=(
            'mean:f32x3;rotation:f32x4;logScale:f32x3;'
            f'logitOpacity:f32;dc:f32x3;sh:f32x{planes.sh_float_count}'
        ),
        appearance_policy=(
            f'effective-editor-dc-sh-bands-{sh_bands_for(planes.sh_float_count)}'
        ),
        render_configuration={
            'version': 'supersplat-effective-rgb-v1', 'backgroundRgba': [0.0, 0.0, 0.0, 1.0],
            'alphaMode': 'opaque-background',
            'shBands': sh_bands_for(planes.sh_float_count),
            'rasterizer': 'playcanvas-gsplat-classic',
        },
        sh_float_count_per_gaussian=planes.sh_float_count, chunks=tuple(descriptors),
    )
    # Both choices are explicit, reproducible Anchor camera fixtures.  The
    # first Gaussian is a tight feature-oriented view; the support midpoint is
    # a deliberately broader view of the same spatial chunk.
    first = descriptors[0].support_bounds
    assert first.minimum is not None and first.maximum is not None
    target = (
        planes.means[int(order[0])].astype(np.float64)
        if args.target_mode == 'first-gaussian'
        else (np.asarray(first.minimum) + np.asarray(first.maximum)) / 2.0
    )
    camera = camera_for(target, args.resolution)
    render_camera = renderer_camera(camera)
    with tempfile.TemporaryDirectory(prefix='supersplat-02b-') as temporary:
        store = SpatialSceneStore(Path(temporary) / 'runtime')
        manifest_started = time.perf_counter()
        store.register_manifest(manifest)
        manifest_seconds = time.perf_counter() - manifest_started
        first_resolution = store.resolve_working_set(manifest.scene_id, manifest.scene_version, camera)
        transfer_started = time.perf_counter()
        admission = store.begin_chunk_upload(
            manifest.scene_id, manifest.scene_version, first_resolution.missing_chunk_ids
        )
        assert admission.upload_id is not None
        for chunk_id in admission.missing_chunk_ids:
            store.accept_chunk(admission.upload_id, chunk_id, payloads[chunk_id], next(
                descriptor.chunk_digest for descriptor in descriptors if descriptor.chunk_id == chunk_id
            ))
        store.commit_chunk_upload(admission.upload_id)
        transfer_seconds = time.perf_counter() - transfer_started
        resolved = store.resolve_working_set(manifest.scene_id, manifest.scene_version, camera)
        assert resolved.working_set is not None
        # Resolve a separate equivalent working set for an independently
        # measured cold mmap-to-tensor assembly. Keep the actual Anchor's
        # working set unassembled until the production call below.
        assembly_probe = store.resolve_working_set(
            manifest.scene_id, manifest.scene_version, camera
        ).working_set
        assert assembly_probe is not None
        selective_assembly_started = time.perf_counter()
        assembly_probe.ordered_tensors()
        selective_assembly_seconds = time.perf_counter() - selective_assembly_started
        del assembly_probe
        # Measure the production first-Anchor path before the legacy parity
        # renderer warms gsplat or materializes contributor Python lists.
        anchor_renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        anchor_render_started = time.perf_counter()
        anchor_artifact = anchor_renderer.render_anchor(
            scene_snapshot=resolved.working_set,
            view_id='anchor-view',
            camera=render_camera,
            width=args.resolution,
            height=args.resolution,
        )
        anchor_render_seconds = time.perf_counter() - anchor_render_started
        backend = LockedGsplatBackend()
        selective_tensors = resolved.working_set.ordered_tensors()
        selective_render_started = time.perf_counter()
        selective = backend.rasterize(
            snapshot=resolved.working_set,
            camera=render_camera,
            width=args.resolution,
            height=args.resolution,
        )
        selective_render_seconds = time.perf_counter() - selective_render_started
        remaining = tuple(
            descriptor.chunk_id for descriptor in descriptors
            if descriptor.chunk_id not in set(first_resolution.required_chunk_ids)
        )
        if remaining:
            extra = store.begin_chunk_upload(manifest.scene_id, manifest.scene_version, remaining)
            if extra.upload_id is not None:
                for chunk_id in extra.missing_chunk_ids:
                    store.accept_chunk(extra.upload_id, chunk_id, payloads[chunk_id], next(
                        descriptor.chunk_digest for descriptor in descriptors if descriptor.chunk_id == chunk_id
                    ))
                store.commit_chunk_upload(extra.upload_id)
        full = store.full_working_set(manifest.scene_id, manifest.scene_version, camera)
        full_tensors = full.ordered_tensors()
        full_render_started = time.perf_counter()
        full_raster = backend.rasterize(
            snapshot=full,
            camera=render_camera,
            width=args.resolution,
            height=args.resolution,
        )
        full_render_seconds = time.perf_counter() - full_render_started
        selective_ids = contributor_global_ids(selective, selective_tensors['stableIds'])
        full_ids = contributor_global_ids(full_raster, full_tensors['stableIds'])
        report = {
            'ply': str(args.ply),
            'rawPlyNoEditAssumption': True,
            'targetMode': args.target_mode,
            'renderResolution': args.resolution,
            'shFloatCountPerGaussian': planes.sh_float_count,
            'effectiveGaussianCount': planes.count,
            'totalBinarySceneSnapshotBytes': sum(descriptor.byte_length for descriptor in descriptors),
            'spatialChunkByteLimit': args.chunk_bytes,
            'totalChunks': len(descriptors),
            'cameraBinding': camera,
            'requiredChunkCount': len(first_resolution.required_chunk_ids),
            'requiredChunkBytes': sum(
                descriptor.byte_length for descriptor in descriptors
                if descriptor.chunk_id in set(first_resolution.required_chunk_ids)
            ),
            'selectedToFullByteRatio': sum(
                descriptor.byte_length for descriptor in descriptors
                if descriptor.chunk_id in set(first_resolution.required_chunk_ids)
            ) / sum(descriptor.byte_length for descriptor in descriptors),
            'timingsSeconds': {
                'parse': parse_seconds, 'packing': packing_seconds, 'manifest': manifest_seconds,
                'requiredChunkTransferAndCommit': transfer_seconds,
                'workingSetAssembly': selective_assembly_seconds,
                'selectiveGsplatRender': selective_render_seconds,
                'anchorRenderAndTypedPublication': anchor_render_seconds,
                'fullGsplatRender': full_render_seconds,
            },
            'memory': {
                'processPeakRssBytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                'selectivePeakVramBytes': selective.peak_vram_bytes,
                'anchorPeakVramBytes': anchor_renderer.last_peak_vram_bytes,
                'fullPeakVramBytes': full_raster.peak_vram_bytes,
            },
            'parity': {
                'rgbBytes': selective.service_rgb_bytes == full_raster.service_rgb_bytes,
                'rgbDigest': selective.service_rgb_digest == full_raster.service_rgb_digest,
                'alpha': selective.alpha == full_raster.alpha,
                'contributorStableIds': selective_ids == full_ids,
                'contributorWeights': selective.contributor_weights == full_raster.contributor_weights,
            },
            'selectiveNonZeroAlphaPixels': sum(
                1 for image_row in selective.alpha for alpha in image_row if alpha > 0.0
            ),
            'typedAnchorContributorDigest': anchor_artifact.contributor_digest,
        }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

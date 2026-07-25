"""Versioned mask-conditioned Anchor Gaussian support probe.

The ``anchor-support-probe/v1`` policy is a cheap computability gate for
Confirm Anchor hard validation (Final Spec v1.1 §12.2). It answers only
whether any Gaussian support is observable under the exact bound
Camera/RGB/Stable-Mask identity: it is not P/N/V Evidence, not per-pixel
Contributor output, and never carries Stable Gaussian IDs or ownership
classification. The computation is pure CPU over immutable mmap planes and
deliberately never imports the locked renderer runtime (no torch, no gsplat).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


AI_SELECT_SUPPORT_PROBE_POLICY_VERSION = "anchor-support-probe/v1"
AI_SELECT_SUPPORT_PROBE_MASK_ENCODING = "bitset-lsb-v1"
# Opacity gate: alpha >= 0.5 is exactly logitOpacity >= 0.
_MIN_LOGIT_OPACITY = 0.0


@dataclass(frozen=True)
class AnchorSupportProbeCamera:
    """The OpenCV world-to-camera view derived from a validated CameraBinding."""

    world_to_camera: tuple[float, ...]
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    near: float
    far: float


def probe_camera_from_renderer_camera(
    renderer_camera: Mapping[str, object], *, width: int, height: int
) -> AnchorSupportProbeCamera:
    """Copy the validated gsplat camera seam into the probe's camera record.

    The input is the ``renderer_camera`` derived by the Anchor CameraBinding
    parser (OpenCV world-to-camera, row-major 4x4 plus pinhole intrinsics).
    """

    world_to_camera = renderer_camera.get("worldToCamera")
    intrinsics = renderer_camera.get("intrinsics")
    near = renderer_camera.get("nearPlane")
    far = renderer_camera.get("farPlane")
    if (
        not isinstance(world_to_camera, list)
        or len(world_to_camera) != 16
        or not isinstance(intrinsics, list)
        or len(intrinsics) != 9
        or not isinstance(near, (int, float))
        or not isinstance(far, (int, float))
    ):
        raise ValueError("Anchor support probe renderer camera is malformed")
    return AnchorSupportProbeCamera(
        world_to_camera=tuple(float(component) for component in world_to_camera),
        fx=float(intrinsics[0]),
        fy=float(intrinsics[4]),
        cx=float(intrinsics[2]),
        cy=float(intrinsics[5]),
        width=width,
        height=height,
        near=float(near),
        far=float(far),
    )


def count_observed_gaussians(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    camera: AnchorSupportProbeCamera,
    mask: bytes,
) -> int:
    """Count Gaussians whose mean projects onto a set Stable Mask pixel.

    Each plane pair is one chunk's (``means`` float32le x3, ``logitOpacities``
    float32le) sharing a Gaussian row order; only the count matters, so chunk
    order and Stable Gaussian IDs never enter the computation. A Gaussian is
    observed when its camera-space depth lies in [near, far], its rounded
    pinhole pixel is in bounds, its opacity is at least 0.5, and the LSB-first
    mask bit at that pixel is set.
    """

    matrix = camera.world_to_camera
    if len(matrix) != 16:
        raise ValueError("Anchor support probe camera is malformed")
    if len(mask) != (camera.width * camera.height + 7) // 8:
        raise ValueError("Anchor support probe mask does not match the camera")
    observed = 0
    for means_view, logit_view in planes:
        # Native little-endian float32 views match the packed float32le planes
        # on every supported Companion platform, exactly like the renderer's
        # torch.frombuffer validation views. No per-Gaussian Python records.
        means = means_view.cast("f")
        logits = logit_view.cast("f")
        if len(means) != 3 * len(logits):
            raise ValueError("Anchor support probe planes are inconsistent")
        for index in range(len(logits)):
            base = 3 * index
            camera_x = (
                matrix[0] * means[base]
                + matrix[1] * means[base + 1]
                + matrix[2] * means[base + 2]
                + matrix[3]
            )
            camera_y = (
                matrix[4] * means[base]
                + matrix[5] * means[base + 1]
                + matrix[6] * means[base + 2]
                + matrix[7]
            )
            camera_z = (
                matrix[8] * means[base]
                + matrix[9] * means[base + 1]
                + matrix[10] * means[base + 2]
                + matrix[11]
            )
            # Depth is gated before projection, so z is always positive here.
            if camera_z < camera.near or camera_z > camera.far:
                continue
            u = int(round(camera.fx * (camera_x / camera_z) + camera.cx))
            v = int(round(camera.fy * (camera_y / camera_z) + camera.cy))
            if u < 0 or u >= camera.width or v < 0 or v >= camera.height:
                continue
            if logits[index] < _MIN_LOGIT_OPACITY:
                continue
            pixel = v * camera.width + u
            if (mask[pixel >> 3] >> (pixel & 7)) & 1:
                observed += 1
    return observed


__all__ = [
    "AI_SELECT_SUPPORT_PROBE_MASK_ENCODING",
    "AI_SELECT_SUPPORT_PROBE_POLICY_VERSION",
    "AnchorSupportProbeCamera",
    "count_observed_gaussians",
    "probe_camera_from_renderer_camera",
]

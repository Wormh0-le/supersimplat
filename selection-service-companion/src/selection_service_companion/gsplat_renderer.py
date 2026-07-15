"""Locked gsplat RGB and complete contributor-ID rasterization.

The production boundary deliberately makes one backend call return the RGB,
alpha, and contributor stream.  Evidence never reconstructs attribution from
visibility, distance, or a bounded top-k diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Mapping, Protocol, Sequence

from .evidence import ContributorSample, RenderedContributorView
from .masking import MaskSessionError, RegisteredFrame


MASS_CONSERVATION_ATOL = 2e-6
MASS_CONSERVATION_RTOL = 1e-5
SUPPORTED_COORDINATE_CONVENTION = (
    "right-handed world coordinates; quaternion xyzw"
)
SUPPORTED_RASTERIZER = "playcanvas-gsplat-classic"
SUPPORTED_CAMERA_CONVENTION = "opencv-world-to-camera"


@dataclass(frozen=True)
class GsplatRasterization:
    """One atomic backend result from shared projection/tile preparation."""

    service_rgb_digest: str
    alpha: Sequence[Sequence[float]]
    contributor_ids: Sequence[Sequence[Sequence[int]]]
    contributor_weights: Sequence[Sequence[Sequence[float]]]


class GsplatBackend(Protocol):
    """The external CUDA boundary used by the production renderer."""

    def rasterize(
        self,
        *,
        snapshot: Mapping[str, Any],
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> GsplatRasterization:
        """Return RGB, alpha, IDs, and weights from one gsplat preparation."""


class LockedGsplatBackend:
    """Call only APIs available at the exact source revision pinned by the lock."""

    def rasterize(
        self,
        *,
        snapshot: Mapping[str, Any],
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> GsplatRasterization:
        import torch
        from gsplat.cuda._wrapper import (
            rasterize_contributing_gaussian_ids,
            rasterize_num_contributing_gaussians,
        )
        from gsplat.rendering import rasterization

        device = torch.device("cuda")
        gaussians = snapshot["gaussians"]
        render_configuration = snapshot["renderConfiguration"]
        sh_degree = render_configuration["shBands"]
        sh_basis_count = (sh_degree + 1) ** 2

        means = torch.tensor(
            [gaussian["mean"] for gaussian in gaussians],
            dtype=torch.float32,
            device=device,
        )
        # Scene Snapshot rotations are editor-owned XYZW; gsplat accepts WXYZ.
        quats = torch.tensor(
            [
                [
                    gaussian["rotation"][3],
                    gaussian["rotation"][0],
                    gaussian["rotation"][1],
                    gaussian["rotation"][2],
                ]
                for gaussian in gaussians
            ],
            dtype=torch.float32,
            device=device,
        )
        scales = torch.tensor(
            [gaussian["logScale"] for gaussian in gaussians],
            dtype=torch.float32,
            device=device,
        ).exp()
        opacities = torch.tensor(
            [gaussian["logitOpacity"] for gaussian in gaussians],
            dtype=torch.float32,
            device=device,
        ).sigmoid()
        colors = torch.empty(
            (len(gaussians), sh_basis_count, 3),
            dtype=torch.float32,
            device=device,
        )
        for tensor_index, gaussian in enumerate(gaussians):
            colors[tensor_index, 0] = torch.tensor(
                gaussian["dc"], dtype=torch.float32, device=device
            )
            active_coefficients_per_channel = sh_basis_count - 1
            available_coefficients_per_channel = len(gaussian["sh"]) // 3
            for coefficient in range(active_coefficients_per_channel):
                for channel in range(3):
                    colors[tensor_index, coefficient + 1, channel] = gaussian["sh"][
                        channel * available_coefficients_per_channel + coefficient
                    ]

        viewmats = torch.tensor(
            camera["worldToCamera"], dtype=torch.float32, device=device
        ).reshape(1, 4, 4)
        intrinsics = torch.tensor(
            camera["intrinsics"], dtype=torch.float32, device=device
        ).reshape(1, 3, 3)
        background = torch.tensor(
            [render_configuration["backgroundRgba"][:3]],
            dtype=torch.float32,
            device=device,
        )

        service_rgb, raster_alpha, meta = rasterization(
            means,
            quats,
            scales,
            opacities,
            colors,
            viewmats,
            intrinsics,
            width,
            height,
            near_plane=camera["nearPlane"],
            far_plane=camera["farPlane"],
            sh_degree=sh_degree,
            packed=False,
            tile_size=16,
            backgrounds=background,
            render_mode="RGB",
            rasterize_mode="classic",
        )
        if not bool(torch.isfinite(service_rgb).all().item()):
            raise MaskSessionError(
                "rendererFailure", "gsplat returned non-finite service RGB."
            )

        contributor_counts, contributor_alpha = (
            rasterize_num_contributing_gaussians(
                meta["means2d"],
                meta["conics"],
                meta["opacities"],
                meta["isect_offsets"],
                meta["flatten_ids"],
                width,
                height,
                meta["tile_size"],
            )
        )
        contributor_ids, contributor_weights = (
            rasterize_contributing_gaussian_ids(
                meta["means2d"],
                meta["conics"],
                meta["opacities"],
                meta["isect_offsets"],
                meta["flatten_ids"],
                width,
                height,
                meta["tile_size"],
                contributor_counts,
            )
        )
        # This check also proves that RGB's alpha and the contributor operation
        # consumed the exact same projection/tile preparation.
        if not torch.allclose(
            contributor_alpha,
            raster_alpha[..., 0],
            rtol=MASS_CONSERVATION_RTOL,
            atol=MASS_CONSERVATION_ATOL,
        ):
            raise MaskSessionError(
                "rendererMassMismatch",
                "gsplat contributor alpha does not match the corresponding RGB raster alpha.",
            )

        rgb_bytes = (
            service_rgb.detach()
            .clamp(0.0, 1.0)
            .mul(255.0)
            .round()
            .to(torch.uint8)
            .cpu()
            .contiguous()
            .numpy()
            .tobytes()
        )
        return GsplatRasterization(
            service_rgb_digest=f"sha256:{hashlib.sha256(rgb_bytes).hexdigest()}",
            alpha=raster_alpha[0, ..., 0].detach().cpu().tolist(),
            contributor_ids=contributor_ids[0].detach().cpu().tolist(),
            contributor_weights=contributor_weights[0].detach().cpu().tolist(),
        )


@dataclass(frozen=True)
class GsplatContributorRenderer:
    """Production same-rasterization renderer for Stable Gaussian Evidence."""

    backend: GsplatBackend
    renderer_id: str = "gsplat"

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
        stable_ids = validate_supported_snapshot(scene_snapshot)
        camera = _validate_camera(frame)
        rasterized = self.backend.rasterize(
            snapshot=scene_snapshot,
            camera=camera,
            width=frame.width,
            height=frame.height,
        )
        return _validated_rendered_view(
            rasterized=rasterized,
            stable_ids=stable_ids,
            frame=frame,
            renderer_id=self.renderer_id,
        )


def production_gsplat_renderer() -> GsplatContributorRenderer:
    """Construct the lazy-importing production renderer."""

    return GsplatContributorRenderer(backend=LockedGsplatBackend())


def validate_supported_snapshot(snapshot: Mapping[str, Any]) -> tuple[int, ...]:
    """Fail closed unless the snapshot has the approved SuperSplat v1 semantics."""
    if snapshot.get("protocolVersion") != "1":
        raise ValueError("The gsplat renderer supports Scene Snapshot protocol version 1 only")
    if snapshot.get("coordinateConvention") != SUPPORTED_COORDINATE_CONVENTION:
        raise ValueError("The Scene Snapshot coordinate/quaternion convention is unsupported")
    if snapshot.get("stableIdSchema") != "uint32":
        raise ValueError("The Scene Snapshot Stable Gaussian ID schema is unsupported")

    render_configuration = snapshot.get("renderConfiguration")
    if not isinstance(render_configuration, Mapping):
        raise ValueError("The Scene Snapshot render configuration is missing")
    if (
        render_configuration.get("rasterizer") != SUPPORTED_RASTERIZER
        or render_configuration.get("alphaMode") != "opaque-background"
    ):
        raise ValueError("The Scene Snapshot rasterizer or alpha semantics are unsupported")
    background = _finite_sequence(
        render_configuration.get("backgroundRgba"), 4, "backgroundRgba"
    )
    if background[3] != 1.0:
        raise ValueError("Opaque-background Scene Snapshots require background alpha 1")
    sh_bands = render_configuration.get("shBands")
    if isinstance(sh_bands, bool) or not isinstance(sh_bands, int) or sh_bands not in range(4):
        raise ValueError("The Scene Snapshot shBands must be an integer from 0 through 3")

    gaussians = snapshot.get("gaussians")
    gaussian_count = snapshot.get("gaussianCount")
    if (
        not isinstance(gaussians, Sequence)
        or isinstance(gaussians, (str, bytes))
        or isinstance(gaussian_count, bool)
        or not isinstance(gaussian_count, int)
        or gaussian_count != len(gaussians)
        or gaussian_count <= 0
    ):
        raise ValueError("The Scene Snapshot must contain its declared Gaussian records")

    sh_length: int | None = None
    stable_ids: list[int] = []
    for gaussian in gaussians:
        if not isinstance(gaussian, Mapping):
            raise ValueError("Scene Snapshot Gaussian records must be objects")
        stable_id = gaussian.get("stableId")
        if (
            isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or not 0 <= stable_id <= 0xFFFFFFFF
            or stable_id in stable_ids
        ):
            raise ValueError("Scene Snapshot Stable Gaussian IDs must be unique uint32 values")
        stable_ids.append(stable_id)
        _finite_sequence(gaussian.get("mean"), 3, "mean")
        rotation = _finite_sequence(gaussian.get("rotation"), 4, "rotation")
        if sum(value * value for value in rotation) <= 0.0:
            raise ValueError("Scene Snapshot rotations must be non-zero quaternions")
        _finite_sequence(gaussian.get("logScale"), 3, "logScale")
        _finite_number(gaussian.get("logitOpacity"), "logitOpacity")
        _finite_sequence(gaussian.get("dc"), 3, "dc")
        sh = gaussian.get("sh")
        if not isinstance(sh, Sequence) or isinstance(sh, (str, bytes)):
            raise ValueError("Scene Snapshot Gaussian sh must be a numeric array")
        for value in sh:
            _finite_number(value, "sh")
        if sh_length is None:
            sh_length = len(sh)
        elif len(sh) != sh_length:
            raise ValueError("Scene Snapshot Gaussian SH records must use one schema")

    assert sh_length is not None
    available_bands = {0: 0, 9: 1, 24: 2, 45: 3}.get(sh_length)
    if available_bands is None or sh_bands > available_bands:
        raise ValueError("Scene Snapshot SH records do not support the declared shBands")
    expected_attribute_schema = (
        "mean:f32x3;rotation:f32x4;logScale:f32x3;"
        f"logitOpacity:f32;dc:f32x3;sh:f32x{sh_length}"
    )
    if snapshot.get("attributeSchema") != expected_attribute_schema:
        raise ValueError("The Scene Snapshot attribute schema is unsupported")
    if snapshot.get("appearancePolicy") != f"effective-editor-dc-sh-bands-{available_bands}":
        raise ValueError("The Scene Snapshot appearance policy is unsupported")
    return tuple(stable_ids)


def _validate_camera(frame: RegisteredFrame) -> Mapping[str, Any]:
    camera = frame.camera
    if not isinstance(camera, Mapping):
        raise MaskSessionError(
            "rendererUnavailable",
            "The rendered Frame has no immutable pinhole camera binding.",
        )
    if (
        camera.get("model") != "pinhole"
        or camera.get("convention") != SUPPORTED_CAMERA_CONVENTION
    ):
        raise MaskSessionError(
            "rendererUnavailable", "The rendered Frame camera convention is unsupported."
        )
    world_to_camera = _finite_sequence(
        camera.get("worldToCamera"), 16, "worldToCamera"
    )
    intrinsics = _finite_sequence(camera.get("intrinsics"), 9, "intrinsics")
    near_plane = _finite_number(camera.get("nearPlane"), "nearPlane")
    far_plane = _finite_number(camera.get("farPlane"), "farPlane")
    if world_to_camera[12:] != (0.0, 0.0, 0.0, 1.0):
        raise MaskSessionError(
            "rendererUnavailable", "The rendered Frame camera transform is not affine."
        )
    if (
        intrinsics[0] <= 0
        or intrinsics[4] <= 0
        or intrinsics[8] != 1.0
        or near_plane <= 0
        or far_plane <= near_plane
    ):
        raise MaskSessionError(
            "rendererUnavailable", "The rendered Frame camera projection is invalid."
        )
    return camera


def _validated_rendered_view(
    *,
    rasterized: GsplatRasterization,
    stable_ids: tuple[int, ...],
    frame: RegisteredFrame,
    renderer_id: str,
) -> RenderedContributorView:
    if not isinstance(rasterized, GsplatRasterization):
        raise MaskSessionError("rendererFailure", "gsplat returned an invalid rasterization.")
    if (
        not isinstance(rasterized.service_rgb_digest, str)
        or not rasterized.service_rgb_digest.startswith("sha256:")
    ):
        raise MaskSessionError("rendererFailure", "gsplat returned invalid service RGB identity.")
    _validate_raster_shape(rasterized.alpha, frame.width, frame.height, "alpha")
    _validate_raster_shape(
        rasterized.contributor_ids, frame.width, frame.height, "contributor IDs"
    )
    _validate_raster_shape(
        rasterized.contributor_weights,
        frame.width,
        frame.height,
        "contributor weights",
    )

    contributors: list[ContributorSample] = []
    support_pixels: list[tuple[int, int]] = []
    maximum_error = 0.0
    for y_px in range(frame.height):
        for x_px in range(frame.width):
            alpha = _finite_number(rasterized.alpha[y_px][x_px], "raster alpha")
            if alpha < 0.0 or alpha > 1.0 + MASS_CONSERVATION_ATOL:
                raise MaskSessionError("rendererFailure", "gsplat returned invalid raster alpha.")
            ids = rasterized.contributor_ids[y_px][x_px]
            weights = rasterized.contributor_weights[y_px][x_px]
            if len(ids) != len(weights):
                raise MaskSessionError(
                    "rendererInvalidContributor",
                    "gsplat contributor IDs and weights have different lengths.",
                )
            pixel_mass = 0.0
            for tensor_id, weight_value in zip(ids, weights, strict=True):
                weight = _finite_number(weight_value, "contributor weight")
                if isinstance(tensor_id, bool) or not isinstance(tensor_id, int):
                    raise MaskSessionError(
                        "rendererInvalidContributor", "gsplat returned a non-integer contributor ID."
                    )
                if tensor_id == -1:
                    if weight != 0.0:
                        raise MaskSessionError(
                            "rendererInvalidContributor",
                            "gsplat returned mass for a padded contributor ID.",
                        )
                    continue
                if tensor_id < 0 or tensor_id >= len(stable_ids) or weight <= 0.0:
                    raise MaskSessionError(
                        "rendererInvalidContributor",
                        "gsplat returned an invalid contributor ID or weight.",
                    )
                pixel_mass += weight
                support_pixels.append((x_px, y_px))
                contributors.append(
                    ContributorSample(
                        stable_id=stable_ids[tensor_id],
                        x_px=x_px,
                        y_px=y_px,
                        mass=weight,
                    )
                )
            error = abs(pixel_mass - alpha)
            maximum_error = max(maximum_error, error)
            if error > MASS_CONSERVATION_ATOL + MASS_CONSERVATION_RTOL * abs(alpha):
                raise MaskSessionError(
                    "rendererMassMismatch",
                    "Complete gsplat contributor mass does not match raster alpha.",
                )

    if not contributors:
        raise MaskSessionError(
            "rendererUnavailable",
            "The rendered Frame has no complete gsplat contributor support.",
        )
    min_x = min(pixel[0] for pixel in support_pixels)
    min_y = min(pixel[1] for pixel in support_pixels)
    max_x = max(pixel[0] for pixel in support_pixels) + 1
    max_y = max(pixel[1] for pixel in support_pixels) + 1
    return RenderedContributorView(
        view_id=frame.view_id,
        rgb_frame_digest=frame.frame_digest,
        width=frame.width,
        height=frame.height,
        support_bounds=(min_x, min_y, max_x, max_y),
        contributors=tuple(contributors),
        service_rgb_digest=rasterized.service_rgb_digest,
        mass_conservation_max_error=maximum_error,
    )


def _validate_raster_shape(
    value: Sequence[Any], width: int, height: int, field_name: str
) -> None:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != height
        or any(
            not isinstance(row, Sequence)
            or isinstance(row, (str, bytes))
            or len(row) != width
            for row in value
        )
    ):
        raise MaskSessionError(
            "rendererFailure", f"gsplat returned an invalid {field_name} raster shape."
        )


def _finite_sequence(value: object, length: int, field_name: str) -> tuple[float, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != length
    ):
        raise ValueError(f"{field_name} must contain {length} finite numeric values")
    return tuple(_finite_number(item, field_name) for item in value)


def _finite_number(value: object, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{field_name} must contain finite numeric values")
    return float(value)

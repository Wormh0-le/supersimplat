"""Locked gsplat RGB and complete contributor-ID rasterization.

The production boundary deliberately makes one backend call return the RGB,
alpha, and contributor stream.  Evidence never reconstructs attribution from
visibility, distance, or a bounded top-k diagnostic.  When gsplat's separate
CUDA translation units disagree on a contributor exactly at a float32
validity/termination boundary, the contributor stream is reconciled against
the RGB rasterization's own alpha from the same projection/tile preparation;
any other mismatch fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from io import BytesIO
import math
import struct
from typing import Any, ClassVar, Mapping, Protocol, Sequence

from .evidence import ContributorSample, RenderedContributorView
from .generated_views import (
    CameraPreflightResult,
    GeneratedViewCameraPlan,
    PlannedGeneratedViewCandidate,
    PREFLIGHT_POLICY_ID,
    SeedRegion,
)
from .masking import MaskSessionError, RegisteredFrame


MASS_CONSERVATION_ATOL = 2e-6
MASS_CONSERVATION_RTOL = 1e-5
# gsplat's per-Gaussian validity cut (1/255), transmittance termination cut
# (1e-4), and alpha clamp mirror the pinned CUDA kernels' Common.h.
_GAUSSIAN_VALIDITY_CUT = 1.0 / 255.0
_GAUSSIAN_MAX_ALPHA = 0.99
_TRANSMITTANCE_CUT = 1e-4
# Boundary reconciliation windows. A contributor is ambiguous only when its
# exact (float64) evaluation sits within float32 evaluation noise of a kernel
# decision boundary; anything else is a real defect and fails closed. Noise
# budget at the validity cut (~21 ulps): the measured locked-build flip was
# 1.78e-9 (~4 ulps, ADR 0010); __expf's documented worst case at the cut's
# sigma (~5.5) is ~8 ulps of vis (~4e-9 in alpha), and float32 sigma
# evaluation adds a few ulps more. A wider window would let reconciliation
# mask defects that are not float evaluation noise; a genuine flip beyond it
# fails closed, which costs a preview but never silently rewrites evidence.
# The sigma-zero and termination windows stay narrow even though accumulated
# chain noise can exceed them: a missed flip there also only ever fails
# closed. At most four ambiguous contributors per pixel are enumerated, and a
# reconciled chain must reproduce the RGB raster alpha within float32
# evaluation noise, far inside mass tolerance.
_VALIDITY_BOUNDARY_WINDOW = 1e-8
_SIGMA_BOUNDARY_WINDOW = 1e-9
_TERMINATION_BOUNDARY_WINDOW = 1e-9
_MAX_BOUNDARY_CANDIDATES = 4
_BOUNDARY_MATCH_ATOL = 1e-6
# Per-contributor validation is a proof of an unchanged kernel decision chain,
# not a second mass-conservation check. The locked-build validity budget is
# eight __expf ulps plus float32 arithmetic noise, so 16 float32 ulps leaves a
# deterministic margin without accepting a material contributor rewrite.
_KERNEL_WEIGHT_PROOF_ULPS = 16
_KERNEL_WEIGHT_PROOF_ATOL = 1e-8
_MAX_RECONCILED_PIXELS = 4096
CONTRIBUTOR_RECONCILIATION_POLICY_ID = (
    "gsplat-boundary-contributor-reconciliation/v2"
)
SUPPORTED_COORDINATE_CONVENTION = (
    "right-handed world coordinates; quaternion xyzw"
)
SUPPORTED_RASTERIZER = "playcanvas-gsplat-classic"
SUPPORTED_CAMERA_CONVENTION = "opencv-world-to-camera"
SUPPORTED_RENDER_CONFIG_VERSION = "supersplat-effective-rgb-v1"
ANCHOR_PARITY_NORMAL_MAE = 2.0 / 255.0
ANCHOR_PARITY_SEVERE_MAE = 0.25


def _mass_conservation_tolerance(reference: Any) -> Any:
    """Absolute mass-conservation tolerance for one alpha or weight value."""

    return MASS_CONSERVATION_ATOL + MASS_CONSERVATION_RTOL * abs(reference)


def _f32_ulp(value: float) -> float:
    """Return the spacing of the positive float32 value nearest to ``value``."""

    value32 = _f32(abs(value))
    bits = struct.unpack("!I", struct.pack("!f", value32))[0]
    if bits >= 0x7F7FFFFF:
        return math.inf
    next_value = struct.unpack("!f", struct.pack("!I", bits + 1))[0]
    return next_value - value32


def _kernel_weight_proof_tolerance(reference: float) -> float:
    """Bound ordinary float32 evaluation noise for one contributor weight."""

    return max(
        _KERNEL_WEIGHT_PROOF_ATOL,
        _KERNEL_WEIGHT_PROOF_ULPS * _f32_ulp(reference),
    )


class _BoundaryAmbiguity(Enum):
    """The kernel decision boundary one ambiguous contributor sits at."""

    VALIDITY = "validity"
    TERMINATION = "termination"


@dataclass(frozen=True)
class GsplatRasterization:
    """One atomic backend result from shared projection/tile preparation."""

    service_rgb_digest: str
    service_rgb_bytes: bytes
    alpha: Sequence[Sequence[float]]
    contributor_ids: Sequence[Sequence[Sequence[int]]]
    contributor_weights: Sequence[Sequence[Sequence[float]]]
    peak_vram_bytes: int | None = None


@dataclass(frozen=True)
class GsplatProbe:
    """Low-resolution alpha and bounded top-contributor camera diagnostics."""

    alpha: Sequence[Sequence[float]]
    contributor_ids: Sequence[Sequence[Sequence[int]]]
    contributor_weights: Sequence[Sequence[Sequence[float]]]


@dataclass(frozen=True)
class TileGaussian:
    """One projected Gaussian in one tile's front-to-back intersection order."""

    tensor_id: int
    mean_x: float
    mean_y: float
    conic_a: float
    conic_b: float
    conic_c: float
    opacity: float


def _f32(value: float) -> float:
    """Round a Python float to the nearest IEEE-754 binary32 value."""

    return struct.unpack("f", struct.pack("f", value))[0]


def _f32_add(left: float, right: float) -> float:
    """Evaluate one non-fused binary32 addition deterministically."""

    return _f32(_f32(left) + _f32(right))


def _f32_mul(left: float, right: float) -> float:
    """Evaluate one non-fused binary32 multiplication deterministically."""

    return _f32(_f32(left) * _f32(right))


def _f32_sub(left: float, right: float) -> float:
    """Evaluate one non-fused binary32 subtraction deterministically."""

    return _f32(_f32(left) - _f32(right))


def _reference_sigma32(
    gaussian: TileGaussian, *, center_x: float, center_y: float
) -> float:
    """Use gsplat's source grouping with explicit, uncontracted binary32 steps."""

    dx = _f32_sub(gaussian.mean_x, center_x)
    dy = _f32_sub(gaussian.mean_y, center_y)
    diagonal = _f32_add(
        _f32_mul(_f32_mul(gaussian.conic_a, dx), dx),
        _f32_mul(_f32_mul(gaussian.conic_c, dy), dy),
    )
    return _f32_add(
        _f32_mul(0.5, diagonal),
        _f32_mul(_f32_mul(gaussian.conic_b, dx), dy),
    )


def _reference_alpha32(opacity: float, sigma32: float) -> float:
    """Use the binary32 alpha path apart from CUDA's intrinsic expf choice.

    Python cannot reproduce the locked CUDA translation unit's ``__expf``
    implementation. Its correctly rounded binary32 reference is used only to
    enumerate declared boundary decisions; any intrinsic-specific divergence
    that does not produce a unique boundary explanation remains fail-closed.
    """

    try:
        visibility = _f32(math.exp(-sigma32))
    except OverflowError:
        # CUDA's expf reaches infinity here and the subsequent alpha clamp
        # makes the result finite; preserve that fail-closed scalar shape.
        visibility = math.inf
    return min(_f32(_GAUSSIAN_MAX_ALPHA), _f32_mul(opacity, visibility))


def _reference_alpha64(opacity: float, sigma64: float) -> float:
    """Evaluate the high-precision boundary diagnostic without overflow."""

    try:
        visibility = math.exp(-sigma64)
    except OverflowError:
        visibility = math.inf
    return min(_GAUSSIAN_MAX_ALPHA, opacity * visibility)


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

    def probe(
        self,
        *,
        snapshot: Mapping[str, Any],
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> GsplatProbe:
        """Return low-cost alpha and bounded top contributors for preflight only."""


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
        torch.cuda.reset_peak_memory_stats(device)
        inputs = _locked_inputs(snapshot, camera, device)

        service_rgb, raster_alpha, meta = rasterization(
            inputs["means"],
            inputs["quats"],
            inputs["scales"],
            inputs["opacities"],
            inputs["colors"],
            inputs["viewmats"],
            inputs["intrinsics"],
            width,
            height,
            near_plane=camera["nearPlane"],
            far_plane=camera["farPlane"],
            sh_degree=inputs["sh_degree"],
            packed=False,
            tile_size=16,
            backgrounds=inputs["background"],
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
        # consumed the exact same projection/tile preparation. The two CUDA
        # kernels evaluate the shared per-Gaussian alpha in separate
        # translation units, so their float32 arithmetic can flip a single
        # contributor exactly at the validity/termination boundaries; reconcile
        # only those proven boundary flips against the RGB rasterization's own
        # alpha and fail closed on any other mismatch.
        difference = torch.abs(contributor_alpha - raster_alpha[..., 0])
        tolerance = _mass_conservation_tolerance(raster_alpha[..., 0])
        if bool((difference > tolerance).any().item()):
            reconciled = _reconcile_boundary_flips(
                difference=difference,
                tolerance=tolerance,
                raster_alpha=raster_alpha,
                contributor_alpha=contributor_alpha,
                contributor_ids=contributor_ids,
                contributor_weights=contributor_weights,
                meta=meta,
            )
            if reconciled is not None:
                contributor_alpha, contributor_ids, contributor_weights = reconciled
        if not torch.allclose(
            contributor_alpha,
            raster_alpha[..., 0],
            rtol=MASS_CONSERVATION_RTOL,
            atol=MASS_CONSERVATION_ATOL,
        ):
            difference = torch.abs(contributor_alpha - raster_alpha[..., 0])
            tolerance = _mass_conservation_tolerance(raster_alpha[..., 0])
            raise MaskSessionError(
                "rendererMassMismatch",
                "gsplat contributor alpha does not match the corresponding RGB raster alpha "
                f"(max absolute difference {float(difference.max().item()):.9g}; "
                f"pixels over tolerance {int((difference > tolerance).sum().item())}).",
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
            service_rgb_bytes=rgb_bytes,
            alpha=raster_alpha[0, ..., 0].detach().cpu().tolist(),
            contributor_ids=contributor_ids[0].detach().cpu().tolist(),
            contributor_weights=contributor_weights[0].detach().cpu().tolist(),
            peak_vram_bytes=int(torch.cuda.max_memory_allocated(device)),
        )

    def probe(
        self,
        *,
        snapshot: Mapping[str, Any],
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> GsplatProbe:
        import torch
        from gsplat.cuda._wrapper import rasterize_top_contributing_gaussian_ids
        from gsplat.rendering import rasterization

        device = torch.device("cuda")
        inputs = _locked_inputs(snapshot, camera, device)
        _, raster_alpha, meta = rasterization(
            inputs["means"],
            inputs["quats"],
            inputs["scales"],
            inputs["opacities"],
            inputs["colors"],
            inputs["viewmats"],
            inputs["intrinsics"],
            width,
            height,
            near_plane=camera["nearPlane"],
            far_plane=camera["farPlane"],
            sh_degree=inputs["sh_degree"],
            packed=False,
            tile_size=16,
            backgrounds=inputs["background"],
            render_mode="RGB",
            rasterize_mode="classic",
        )
        contributor_ids, contributor_weights = rasterize_top_contributing_gaussian_ids(
            meta["means2d"],
            meta["conics"],
            meta["opacities"],
            meta["isect_offsets"],
            meta["flatten_ids"],
            width,
            height,
            meta["tile_size"],
            4,
        )
        return GsplatProbe(
            alpha=raster_alpha[0, ..., 0].detach().cpu().tolist(),
            contributor_ids=contributor_ids[0].detach().cpu().tolist(),
            contributor_weights=contributor_weights[0].detach().cpu().tolist(),
        )


def _locked_inputs(
    snapshot: Mapping[str, Any], camera: Mapping[str, Any], device: Any
) -> dict[str, Any]:
    """Build the shared locked-revision projection inputs for probe or render."""

    import torch

    gaussians = snapshot["gaussians"]
    render_configuration = snapshot["renderConfiguration"]
    sh_degree = render_configuration["shBands"]
    sh_basis_count = (sh_degree + 1) ** 2
    means = torch.tensor(
        [gaussian["mean"] for gaussian in gaussians],
        dtype=torch.float32,
        device=device,
    )
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
    return {
        "means": means,
        "quats": quats,
        "scales": scales,
        "opacities": opacities,
        "colors": colors,
        "viewmats": torch.tensor(
            camera["worldToCamera"], dtype=torch.float32, device=device
        ).reshape(1, 4, 4),
        "intrinsics": torch.tensor(
            camera["intrinsics"], dtype=torch.float32, device=device
        ).reshape(1, 3, 3),
        "background": torch.tensor(
            [render_configuration["backgroundRgba"][:3]],
            dtype=torch.float32,
            device=device,
        ),
        "sh_degree": sh_degree,
    }


@dataclass(frozen=True)
class _EvaluatedGaussian:
    """One tile Gaussian's alpha evaluation shared by every replay variant."""

    tensor_id: int
    alpha32: float
    invalid32: bool


@dataclass(frozen=True)
class _ReplayedContributorChain:
    """One deterministic decision variant for one pixel's contributor chain."""

    decisions: tuple[bool, ...]
    ids: tuple[int, ...]
    weights: tuple[float, ...]
    alpha: float


def reconcile_boundary_contributors(
    *,
    ordered_gaussians: Sequence[TileGaussian],
    pixel_x: int,
    pixel_y: int,
    raster_alpha: float,
    kernel_alpha: float,
    kernel_ids: Sequence[int],
    kernel_weights: Sequence[float],
) -> tuple[tuple[int, ...], tuple[float, ...], float] | None:
    """Realign one pixel's contributor stream with the RGB rasterization.

    gsplat's RGB and contributor CUDA kernels share the per-Gaussian alpha
    source but are separate translation units, so their compiled float32
    arithmetic can disagree by a few ulps. That disagreement can flip a
    contributor decision only at the validity cut (alpha 1/255), the
    termination cut (transmittance 1e-4), or sigma zero; everywhere else the
    kernels agree far inside mass-conservation tolerance. The RGB
    rasterization is the same-rasterization authority: enumerate the
    ambiguous contributor decisions, keep the unique variant whose
    recomputed alpha matches the raster alpha, and rebuild the pixel's
    contributor IDs and weights from the matched chain.

    The repair is confined to proven boundary flips: the kernel stream must
    be internally consistent (finite weights reproducing the contributor
    kernels' own alpha), the matched variant must exercise at least one
    flip, and every kernel-chain weight must agree with its replayed value
    inside the float32 proof budget. Return None whenever the mismatch cannot
    be explained by boundary flips alone so callers keep failing closed.
    """

    threshold32 = _f32(_GAUSSIAN_VALIDITY_CUT)
    termination32 = _f32(_TRANSMITTANCE_CUT)
    center_x = pixel_x + 0.5
    center_y = pixel_y + 0.5

    kernel_id_list = [int(value) for value in kernel_ids]
    kernel_weight_list = [float(value) for value in kernel_weights]
    if (
        len(kernel_id_list) != len(kernel_weight_list)
        or len(set(kernel_id_list)) != len(kernel_id_list)
        or any(value < 0 for value in kernel_id_list)
        or any(not math.isfinite(value) for value in kernel_weight_list)
        or not math.isfinite(kernel_alpha)
        or not math.isfinite(raster_alpha)
    ):
        return None
    if abs(
        sum(kernel_weight_list) - kernel_alpha
    ) > _mass_conservation_tolerance(kernel_alpha):
        return None

    evaluations: list[_EvaluatedGaussian] = []
    ambiguous: dict[int, _BoundaryAmbiguity] = {}
    reference_transmittance32 = 1.0
    terminated = False
    for position, gaussian in enumerate(ordered_gaussians):
        dx64 = gaussian.mean_x - center_x
        dy64 = gaussian.mean_y - center_y
        sigma64 = (
            0.5
            * (
                gaussian.conic_a * dx64 * dx64
                + gaussian.conic_c * dy64 * dy64
            )
            + gaussian.conic_b * dx64 * dy64
        )
        sigma32 = _reference_sigma32(
            gaussian, center_x=center_x, center_y=center_y
        )
        alpha64 = _reference_alpha64(gaussian.opacity, sigma64)
        alpha32 = _reference_alpha32(gaussian.opacity, sigma32)
        if (
            abs(alpha64 - _GAUSSIAN_VALIDITY_CUT) <= _VALIDITY_BOUNDARY_WINDOW
            or abs(sigma64) <= _SIGMA_BOUNDARY_WINDOW
        ):
            ambiguous[position] = _BoundaryAmbiguity.VALIDITY
        evaluations.append(
            _EvaluatedGaussian(
                tensor_id=gaussian.tensor_id,
                alpha32=alpha32,
                invalid32=sigma32 < 0.0 or alpha32 < threshold32,
            )
        )
        if terminated or sigma32 < 0.0 or alpha32 < threshold32:
            continue
        next_transmittance32 = _f32_mul(
            reference_transmittance32, _f32_sub(1.0, alpha32)
        )
        if (
            abs(next_transmittance32 - termination32)
            <= _TERMINATION_BOUNDARY_WINDOW
        ):
            if position in ambiguous:
                return None
            ambiguous[position] = _BoundaryAmbiguity.TERMINATION
        if next_transmittance32 <= termination32:
            terminated = True
            continue
        reference_transmittance32 = next_transmittance32

    if not ambiguous or len(ambiguous) > _MAX_BOUNDARY_CANDIDATES:
        return None

    flags = sorted(ambiguous)
    replayed_chains: list[_ReplayedContributorChain] = []
    for mask in range(1 << len(flags)):
        forced = {
            position: bool(mask & (1 << bit)) for bit, position in enumerate(flags)
        }
        replay = _replay_boundary_chain(
            evaluations, ambiguous, forced, termination32
        )
        if replay is None:
            continue
        ids, weights, alpha = replay
        replayed_chains.append(
            _ReplayedContributorChain(
                decisions=tuple(forced[position] for position in flags),
                ids=ids,
                weights=weights,
                alpha=alpha,
            )
        )
    rgb_matches = [
        chain
        for chain in replayed_chains
        if abs(chain.alpha - raster_alpha) <= _BOUNDARY_MATCH_ATOL
    ]
    if len(rgb_matches) != 1:
        return None
    rgb_chain = rgb_matches[0]

    kernel_matches = [
        chain for chain in replayed_chains if list(chain.ids) == kernel_id_list
    ]
    if len(kernel_matches) != 1:
        return None
    kernel_chain = kernel_matches[0]
    if (
        rgb_chain.decisions == kernel_chain.decisions
        or rgb_chain.ids == kernel_chain.ids
    ):
        # The unique matching variant is the kernel stream itself: no
        # boundary flip is proven, so the mass mismatch is unexplained and
        # fails closed rather than having its weights silently rewritten.
        return None
    # Verify the entire kernel-decision chain before applying the distinct
    # RGB-matching chain. This permits the legitimate tail shift caused by a
    # boundary decision while rejecting an independent contributor defect.
    for kernel_weight, replayed_weight in zip(
        kernel_weight_list, kernel_chain.weights, strict=True
    ):
        proof_reference = max(abs(kernel_weight), abs(replayed_weight))
        if abs(kernel_weight - replayed_weight) > _kernel_weight_proof_tolerance(
            proof_reference
        ):
            return None
    return rgb_chain.ids, rgb_chain.weights, rgb_chain.alpha


def _replay_boundary_chain(
    evaluations: Sequence[_EvaluatedGaussian],
    ambiguous: Mapping[int, _BoundaryAmbiguity],
    forced: Mapping[int, bool],
    termination32: float,
) -> tuple[tuple[int, ...], tuple[float, ...], float] | None:
    """Replay one source-faithful boundary-decision variant in binary32."""

    transmittance = 1.0
    ids: list[int] = []
    weights: list[float] = []
    for position, evaluation in enumerate(evaluations):
        kind = ambiguous.get(position)
        if kind is _BoundaryAmbiguity.TERMINATION:
            if not forced[position]:
                break
        elif kind is _BoundaryAmbiguity.VALIDITY:
            if not forced[position]:
                continue
        elif evaluation.invalid32:
            continue
        next_transmittance = _f32_mul(
            transmittance, _f32_sub(1.0, evaluation.alpha32)
        )
        if next_transmittance <= termination32:
            if kind is _BoundaryAmbiguity.TERMINATION:
                # A forced "not terminated" outcome here would write a
                # Gaussian that the locked kernel excludes before on_hit.
                # Without the alternate kernel's above-cut T value, no
                # source-faithful tail can be reconstructed, so fail closed.
                return None
            if abs(next_transmittance - _TRANSMITTANCE_CUT) <= (
                _TERMINATION_BOUNDARY_WINDOW
            ):
                return None
            break
        ids.append(evaluation.tensor_id)
        weights.append(_f32_mul(evaluation.alpha32, transmittance))
        transmittance = next_transmittance
    return tuple(ids), tuple(weights), _f32(1.0 - transmittance)


def _reconcile_boundary_flips(
    *,
    difference: Any,
    tolerance: Any,
    raster_alpha: Any,
    contributor_alpha: Any,
    contributor_ids: Any,
    contributor_weights: Any,
    meta: Mapping[str, Any],
) -> tuple[Any, Any, Any] | None:
    """Realign failing pixels' contributor streams with the RGB rasterization.

    Returns updated ``(contributor_alpha, contributor_ids,
    contributor_weights)`` when every failing pixel is explained by gsplat's
    float32 boundary non-determinism; returns None when any pixel remains
    unexplained so the caller fails closed with the original error.
    """

    import torch

    failing = (difference > tolerance).nonzero().tolist()
    if not failing or len(failing) > _MAX_RECONCILED_PIXELS:
        return None
    means2d = meta["means2d"]
    conics = meta["conics"]
    opacities = meta["opacities"]
    isect_offsets = meta["isect_offsets"]
    flatten_ids = meta["flatten_ids"]
    tile_size = int(meta["tile_size"])
    tile_width = int(meta["tile_width"])
    tile_count = tile_width * int(meta["tile_height"])
    n_isects = int(flatten_ids.shape[0])
    image_count = int(means2d.shape[0])
    gaussian_count = int(means2d.shape[-2])

    new_alpha = contributor_alpha.detach().cpu().clone()
    new_ids = contributor_ids.detach().cpu().clone()
    new_weights = contributor_weights.detach().cpu().clone()
    raster_cpu = raster_alpha.detach().cpu()
    repairs: list[
        tuple[int, int, int, tuple[int, ...], tuple[float, ...], float]
    ] = []
    for image_id, y, x in failing:
        offsets = isect_offsets[image_id].reshape(-1)
        tile_id = (y // tile_size) * tile_width + (x // tile_size)
        range_start = int(offsets[tile_id].item())
        last_tile = image_id == image_count - 1 and tile_id == tile_count - 1
        range_end = n_isects if last_tile else int(offsets[tile_id + 1].item())
        rows = torch.remainder(
            flatten_ids[range_start:range_end], gaussian_count
        ).to(torch.long)
        tile_means = means2d[image_id].index_select(0, rows).cpu().tolist()
        tile_conics = conics[image_id].index_select(0, rows).cpu().tolist()
        tile_opacities = opacities[image_id].index_select(0, rows).cpu().tolist()
        ordered = [
            TileGaussian(
                tensor_id=int(row),
                mean_x=float(mean[0]),
                mean_y=float(mean[1]),
                conic_a=float(conic[0]),
                conic_b=float(conic[1]),
                conic_c=float(conic[2]),
                opacity=float(opacity),
            )
            for row, mean, conic, opacity in zip(
                rows.cpu().tolist(),
                tile_means,
                tile_conics,
                tile_opacities,
                strict=True,
            )
        ]
        ids_row = new_ids[image_id, y, x].tolist()
        kernel_ids = [int(value) for value in ids_row if value >= 0]
        weights_row = new_weights[image_id, y, x].tolist()
        kernel_weights = [
            float(weights_row[index])
            for index, value in enumerate(ids_row)
            if value >= 0
        ]
        result = reconcile_boundary_contributors(
            ordered_gaussians=ordered,
            pixel_x=x,
            pixel_y=y,
            raster_alpha=float(raster_cpu[image_id, y, x, 0]),
            kernel_alpha=float(new_alpha[image_id, y, x].item()),
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )
        if result is None:
            return None
        ids, weights, alpha = result
        repairs.append((image_id, y, x, ids, weights, alpha))

    capacity = new_ids.shape[-1]
    required = max(len(ids) for _, _, _, ids, _, _ in repairs)
    if required > capacity:
        grown_ids = torch.full(
            (*new_ids.shape[:-1], required), -1, dtype=new_ids.dtype
        )
        grown_weights = torch.zeros(
            (*new_weights.shape[:-1], required), dtype=new_weights.dtype
        )
        grown_ids[..., :capacity] = new_ids
        grown_weights[..., :capacity] = new_weights
        new_ids = grown_ids
        new_weights = grown_weights
        capacity = required
    for image_id, y, x, ids, weights, alpha in repairs:
        new_ids[image_id, y, x] = torch.tensor(
            [*ids, *([-1] * (capacity - len(ids)))], dtype=new_ids.dtype
        )
        new_weights[image_id, y, x] = torch.tensor(
            [*weights, *([0.0] * (capacity - len(weights)))],
            dtype=new_weights.dtype,
        )
        new_alpha[image_id, y, x] = alpha
    device = contributor_alpha.device
    return (
        new_alpha.to(device),
        new_ids.to(device),
        new_weights.to(device),
    )


@dataclass
class GsplatContributorRenderer:
    """Production same-rasterization renderer for Stable Gaussian Evidence."""

    backend: GsplatBackend
    renderer_id: str = "gsplat"
    requires_locked_runtime: ClassVar[bool] = True
    _generated_cache: dict[tuple[str, str], RenderedContributorView] = field(
        default_factory=dict, init=False, repr=False
    )
    last_peak_vram_bytes: int | None = field(default=None, init=False)
    peak_vram_bytes: int = field(default=0, init=False)

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
        stable_ids = validate_supported_snapshot(scene_snapshot)
        cache_key = (str(scene_snapshot["sceneVersion"]), frame.frame_digest)
        cached = self._generated_cache.get(cache_key)
        if cached is not None:
            return cached
        camera = _validate_camera(frame)
        rasterized = self.backend.rasterize(
            snapshot=scene_snapshot,
            camera=camera,
            width=frame.width,
            height=frame.height,
        )
        self.last_peak_vram_bytes = rasterized.peak_vram_bytes
        self.peak_vram_bytes = max(
            self.peak_vram_bytes, int(rasterized.peak_vram_bytes or 0)
        )
        return _validated_rendered_view(
            rasterized=rasterized,
            stable_ids=stable_ids,
            frame=frame,
            renderer_id=self.renderer_id,
        )

    def plan_views(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        anchor_frame: RegisteredFrame,
        seed_region: SeedRegion,
        initial_budget: int,
        replacement_budget: int,
        resolution: int,
    ) -> GeneratedViewCameraPlan:
        """Produce a deterministic camera orbit without rasterizing any candidate."""

        validate_supported_snapshot(scene_snapshot)
        anchor_camera = _validate_camera(anchor_frame)
        anchor_position = _camera_position(anchor_camera)
        target = seed_region.center
        distance = max(
            math.dist(anchor_position, target),
            seed_region.radius * 4.0,
            float(anchor_camera["nearPlane"]) * 4.0,
        )
        base_direction = _normalise(
            tuple(anchor_position[index] - target[index] for index in range(3))
        )
        if abs(base_direction[0]) + abs(base_direction[1]) < 1e-8:
            base_azimuth = 0.0
        else:
            base_azimuth = math.degrees(math.atan2(base_direction[1], base_direction[0]))
        base_elevation = math.degrees(math.asin(max(-1.0, min(1.0, base_direction[2]))))
        orbit_offsets = (
            (45.0, 0.0, "ring"),
            (-45.0, 0.0, "ring"),
            (90.0, 0.0, "ring"),
            (-90.0, 0.0, "ring"),
            (135.0, 0.0, "ring"),
            (-135.0, 0.0, "ring"),
            (180.0, 0.0, "ring"),
            (0.0, 30.0, "upper"),
            (90.0, 30.0, "upper"),
            (-90.0, 30.0, "upper"),
        )
        primary: list[PlannedGeneratedViewCandidate] = []
        for index, (azimuth_offset, elevation_offset, category) in enumerate(
            orbit_offsets[: max(0, initial_budget)]
        ):
            azimuth = base_azimuth + azimuth_offset
            elevation = max(-75.0, min(75.0, base_elevation + elevation_offset))
            position = _orbit_position(target, distance, azimuth, elevation)
            primary.append(
                PlannedGeneratedViewCandidate(
                    view_id=f"generated-{index:02d}",
                    camera=_generated_camera(
                        position=position,
                        target=target,
                        anchor_camera=anchor_camera,
                        anchor_frame=anchor_frame,
                        resolution=resolution,
                    ),
                    category=category,
                    azimuth_degrees=azimuth,
                    elevation_degrees=elevation,
                )
            )
        replacements: list[PlannedGeneratedViewCandidate] = []
        for index, candidate in enumerate(primary[:replacement_budget]):
            azimuth = float(candidate.azimuth_degrees or 0.0) + 10.0
            elevation = float(candidate.elevation_degrees or 0.0)
            position = _orbit_position(target, distance * 1.1, azimuth, elevation)
            replacements.append(
                PlannedGeneratedViewCandidate(
                    view_id=f"generated-replacement-{index:02d}",
                    camera=_generated_camera(
                        position=position,
                        target=target,
                        anchor_camera=anchor_camera,
                        anchor_frame=anchor_frame,
                        resolution=resolution,
                    ),
                    category="replacement",
                    azimuth_degrees=azimuth,
                    elevation_degrees=elevation,
                    replacement_of=candidate.view_id,
                )
            )
        identity = (
            f"{scene_snapshot['sceneVersion']}:{seed_region.center}:"
            f"{seed_region.radius}:{resolution}"
        ).encode("utf-8")
        return GeneratedViewCameraPlan(
            frame_set_id=f"generated-{hashlib.sha256(identity).hexdigest()[:20]}",
            primary=tuple(primary),
            replacements=tuple(replacements),
        )

    def preflight(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        seed_region: SeedRegion,
        resolution: int,
    ) -> CameraPreflightResult:
        """Run versioned geometry checks and a low-resolution alpha probe."""

        try:
            stable_ids = validate_supported_snapshot(scene_snapshot)
            camera = _validated_candidate_camera(candidate.camera, resolution)
        except (ValueError, MaskSessionError, OverflowError):
            return CameraPreflightResult(
                False,
                None,
                {"policyVersion": PREFLIGHT_POLICY_ID, "reason": "non_finite"},
            )
        attempts: list[dict[str, Any]] = []
        for adjustment in ("none", "outward"):
            adjusted = camera if adjustment == "none" else _outward_camera(camera, seed_region)
            geometry_reason, geometry_metrics = _geometry_preflight(
                adjusted, seed_region, scene_snapshot, resolution
            )
            if geometry_reason is not None:
                attempts.append(
                    {"adjustment": adjustment, "reason": geometry_reason, **geometry_metrics}
                )
                if geometry_reason not in {"inside_geometry", "near_plane_cut", "clipped"}:
                    break
                continue
            probe_size = min(64, resolution)
            probe_camera = _scaled_camera(adjusted, resolution, probe_size)
            probe = getattr(self.backend, "probe", None)
            if callable(probe):
                rasterized = probe(
                    snapshot=scene_snapshot,
                    camera=probe_camera,
                    width=probe_size,
                    height=probe_size,
                )
            else:
                # Deterministic injected test backends may reuse their complete
                # fixture; the production LockedGsplatBackend always uses the
                # bounded top-contributor probe above.
                rasterized = self.backend.rasterize(
                    snapshot=scene_snapshot,
                    camera=probe_camera,
                    width=probe_size,
                    height=probe_size,
                )
            probe_reason, probe_metrics = _probe_preflight(
                rasterized, stable_ids, seed_region
            )
            attempts.append(
                {
                    "adjustment": adjustment,
                    "reason": probe_reason,
                    **geometry_metrics,
                    **probe_metrics,
                }
            )
            if probe_reason is None:
                return CameraPreflightResult(
                    True,
                    adjusted,
                    {
                        "policyVersion": PREFLIGHT_POLICY_ID,
                        "reason": "accepted",
                        "attempts": attempts,
                    },
                )
            if probe_reason not in {"low_transmittance", "seed_unsupported"}:
                break
        return CameraPreflightResult(
            False,
            None,
            {
                "policyVersion": PREFLIGHT_POLICY_ID,
                "reason": attempts[-1]["reason"] if attempts else "invalid_camera",
                "attempts": attempts,
            },
        )

    def render_generated(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        preflight: CameraPreflightResult,
        resolution: int,
    ) -> RegisteredFrame:
        if not preflight.accepted or preflight.camera is None:
            raise MaskSessionError(
                "rendererFailure", "A rejected camera cannot be rendered as a Generated View."
            )
        stable_ids = validate_supported_snapshot(scene_snapshot)
        camera = _validated_candidate_camera(preflight.camera, resolution)
        rasterized = self.backend.rasterize(
            snapshot=scene_snapshot,
            camera=camera,
            width=resolution,
            height=resolution,
        )
        self.last_peak_vram_bytes = rasterized.peak_vram_bytes
        self.peak_vram_bytes = max(
            self.peak_vram_bytes, int(rasterized.peak_vram_bytes or 0)
        )
        image_png = _rgb_png(rasterized.service_rgb_bytes, resolution, resolution)
        frame = RegisteredFrame(
            view_id=candidate.view_id,
            frame_digest=f"sha256:{hashlib.sha256(image_png).hexdigest()}",
            width=resolution,
            height=resolution,
            image_png=image_png,
            source="generated",
            camera=camera,
        )
        rendered = _validated_rendered_view(
            rasterized=rasterized,
            stable_ids=stable_ids,
            frame=frame,
            renderer_id=self.renderer_id,
        )
        self._generated_cache[(str(scene_snapshot["sceneVersion"]), frame.frame_digest)] = rendered
        return frame

    def discard_attempt(self) -> None:
        """Dispose every generated raster retained by a failed resolution attempt."""

        self._generated_cache.clear()


def production_gsplat_renderer() -> GsplatContributorRenderer:
    """Construct the lazy-importing production renderer."""

    return GsplatContributorRenderer(backend=LockedGsplatBackend())


def _normalise(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) * float(value) for value in vector))
    if not math.isfinite(length) or length <= 1e-12:
        raise MaskSessionError("rendererUnavailable", "Generated View direction is degenerate.")
    return tuple(float(value) / length for value in vector)  # type: ignore[return-value]


def _cross(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _camera_position(camera: Mapping[str, Any]) -> tuple[float, float, float]:
    matrix = tuple(float(value) for value in camera["worldToCamera"])
    translation = (matrix[3], matrix[7], matrix[11])
    return tuple(
        -sum(matrix[row * 4 + axis] * translation[row] for row in range(3))
        for axis in range(3)
    )  # type: ignore[return-value]


def _orbit_position(
    target: Sequence[float], distance: float, azimuth: float, elevation: float
) -> tuple[float, float, float]:
    azimuth_radians = math.radians(azimuth)
    elevation_radians = math.radians(elevation)
    horizontal = distance * math.cos(elevation_radians)
    return (
        float(target[0]) + horizontal * math.cos(azimuth_radians),
        float(target[1]) + horizontal * math.sin(azimuth_radians),
        float(target[2]) + distance * math.sin(elevation_radians),
    )


def _generated_camera(
    *,
    position: Sequence[float],
    target: Sequence[float],
    anchor_camera: Mapping[str, Any],
    anchor_frame: RegisteredFrame,
    resolution: int,
) -> dict[str, Any]:
    forward = _normalise(tuple(target[index] - position[index] for index in range(3)))
    world_up = (0.0, 0.0, 1.0)
    if abs(_dot(forward, world_up)) > 0.98:
        world_up = (0.0, 1.0, 0.0)
    right = _normalise(_cross(forward, world_up))
    down = _normalise(_cross(forward, right))
    rows = (right, down, forward)
    world_to_camera = [
        rows[0][0], rows[0][1], rows[0][2], -_dot(rows[0], position),
        rows[1][0], rows[1][1], rows[1][2], -_dot(rows[1], position),
        rows[2][0], rows[2][1], rows[2][2], -_dot(rows[2], position),
        0.0, 0.0, 0.0, 1.0,
    ]
    intrinsics = tuple(float(value) for value in anchor_camera["intrinsics"])
    scale_x = resolution / anchor_frame.width
    scale_y = resolution / anchor_frame.height
    return {
        "model": "pinhole",
        "convention": SUPPORTED_CAMERA_CONVENTION,
        "worldToCamera": world_to_camera,
        "intrinsics": [
            intrinsics[0] * scale_x, 0.0, resolution / 2.0,
            0.0, intrinsics[4] * scale_y, resolution / 2.0,
            0.0, 0.0, 1.0,
        ],
        "nearPlane": float(anchor_camera["nearPlane"]),
        "farPlane": float(anchor_camera["farPlane"]),
    }


def _validated_candidate_camera(
    camera: Mapping[str, Any], resolution: int
) -> Mapping[str, Any]:
    if not isinstance(resolution, int) or isinstance(resolution, bool) or resolution <= 0:
        raise MaskSessionError("rendererUnavailable", "Generated View resolution is invalid.")
    return _validate_camera(
        RegisteredFrame(
            view_id="preflight",
            frame_digest="sha256:preflight",
            width=resolution,
            height=resolution,
            source="generated",
            camera=camera,
        )
    )


def _scaled_camera(
    camera: Mapping[str, Any], source_resolution: int, target_resolution: int
) -> dict[str, Any]:
    scaled = dict(camera)
    intrinsics = [float(value) for value in camera["intrinsics"]]
    scale = target_resolution / source_resolution
    intrinsics[0] *= scale
    intrinsics[2] *= scale
    intrinsics[4] *= scale
    intrinsics[5] *= scale
    scaled["intrinsics"] = intrinsics
    return scaled


def _outward_camera(
    camera: Mapping[str, Any], seed_region: SeedRegion
) -> Mapping[str, Any]:
    position = _camera_position(camera)
    offset = tuple(position[index] - seed_region.center[index] for index in range(3))
    outward_position = tuple(
        seed_region.center[index] + offset[index] * 1.25 for index in range(3)
    )
    matrix = tuple(float(value) for value in camera["worldToCamera"])
    rows = tuple(tuple(matrix[row * 4 + axis] for axis in range(3)) for row in range(3))
    adjusted = dict(camera)
    adjusted["worldToCamera"] = [
        rows[0][0], rows[0][1], rows[0][2], -_dot(rows[0], outward_position),
        rows[1][0], rows[1][1], rows[1][2], -_dot(rows[1], outward_position),
        rows[2][0], rows[2][1], rows[2][2], -_dot(rows[2], outward_position),
        0.0, 0.0, 0.0, 1.0,
    ]
    return adjusted


def _geometry_preflight(
    camera: Mapping[str, Any],
    seed_region: SeedRegion,
    scene_snapshot: Mapping[str, Any],
    resolution: int,
) -> tuple[str | None, dict[str, float]]:
    position = _camera_position(camera)
    camera_distance = math.dist(position, seed_region.center)
    means = [gaussian["mean"] for gaussian in scene_snapshot["gaussians"]]
    nearest_geometry = min(math.dist(position, mean) for mean in means)
    metrics = {
        "cameraDistance": camera_distance,
        "nearestGeometryDistance": nearest_geometry,
    }
    if nearest_geometry <= max(seed_region.radius * 0.5, float(camera["nearPlane"]) * 2.0):
        return "inside_geometry", metrics
    matrix = tuple(float(value) for value in camera["worldToCamera"])
    center = seed_region.center
    camera_x = _dot(matrix[0:3], center) + matrix[3]
    camera_y = _dot(matrix[4:7], center) + matrix[7]
    camera_z = _dot(matrix[8:11], center) + matrix[11]
    metrics["seedDepth"] = camera_z
    if camera_z - seed_region.radius <= float(camera["nearPlane"]):
        return "near_plane_cut", metrics
    if camera_z + seed_region.radius >= float(camera["farPlane"]):
        return "clipped", metrics
    intrinsics = tuple(float(value) for value in camera["intrinsics"])
    projected_x = intrinsics[0] * camera_x / camera_z + intrinsics[2]
    projected_y = intrinsics[4] * camera_y / camera_z + intrinsics[5]
    projected_radius = max(intrinsics[0], intrinsics[4]) * seed_region.radius / camera_z
    metrics.update(
        projectedCenterX=projected_x,
        projectedCenterY=projected_y,
        projectedRadius=projected_radius,
    )
    margin = resolution * 0.1
    if (
        projected_x + projected_radius < -margin
        or projected_y + projected_radius < -margin
        or projected_x - projected_radius > resolution + margin
        or projected_y - projected_radius > resolution + margin
        or projected_x - projected_radius < -margin
        or projected_y - projected_radius < -margin
        or projected_x + projected_radius > resolution + margin
        or projected_y + projected_radius > resolution + margin
    ):
        return "clipped", metrics
    return None, metrics


def _probe_preflight(
    rasterized: GsplatRasterization | GsplatProbe,
    stable_ids: Sequence[int],
    seed_region: SeedRegion,
) -> tuple[str | None, dict[str, float]]:
    if not isinstance(rasterized, (GsplatRasterization, GsplatProbe)):
        return "invalid_probe", {}
    seed_tensor_ids = {
        index for index, stable_id in enumerate(stable_ids) if stable_id in seed_region.stable_ids
    }
    total_alpha = 0.0
    seed_mass = 0.0
    total_mass = 0.0
    for alpha_row, id_row, weight_row in zip(
        rasterized.alpha,
        rasterized.contributor_ids,
        rasterized.contributor_weights,
        strict=True,
    ):
        for alpha, ids, weights in zip(alpha_row, id_row, weight_row, strict=True):
            alpha_value = float(alpha)
            if not math.isfinite(alpha_value):
                return "non_finite", {}
            total_alpha += max(0.0, alpha_value)
            for tensor_id, weight in zip(ids, weights, strict=True):
                weight_value = float(weight)
                if tensor_id < 0 or weight_value <= 0.0:
                    continue
                total_mass += weight_value
                if tensor_id in seed_tensor_ids:
                    seed_mass += weight_value
    metrics = {
        "probeAlpha": total_alpha,
        "seedContributorMass": seed_mass,
        "seedMassRatio": seed_mass / max(total_mass, 1e-12),
    }
    if total_alpha <= 1e-4:
        return "low_transmittance", metrics
    if seed_region.stable_ids and seed_mass <= 1e-6:
        return "seed_unsupported", metrics
    if seed_region.stable_ids and seed_mass / max(total_mass, 1e-12) < 0.05:
        return "low_transmittance", metrics
    return None, metrics


def _rgb_png(rgb_bytes: bytes, width: int, height: int) -> bytes:
    if len(rgb_bytes) != width * height * 3:
        raise MaskSessionError("rendererFailure", "gsplat returned invalid service RGB bytes.")
    try:
        from PIL import Image

        image = Image.frombytes("RGB", (width, height), rgb_bytes)
        encoded = BytesIO()
        image.save(encoded, format="PNG")
        return encoded.getvalue()
    except Exception as error:
        raise MaskSessionError(
            "rendererFailure", "Generated View RGB could not be encoded as PNG."
        ) from error


def validate_supported_snapshot(snapshot: Mapping[str, Any]) -> tuple[int, ...]:
    """Fail closed unless the snapshot has the approved SuperSplat v1 semantics."""
    for field_name in (
        "sceneId",
        "sceneVersion",
        "attributeSchema",
        "appearancePolicy",
    ):
        value = snapshot.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Scene Snapshot {field_name} must be a non-empty string")
    if snapshot.get("protocolVersion") != "1":
        raise ValueError("The gsplat renderer supports Scene Snapshot protocol version 1 only")
    if snapshot.get("coordinateConvention") != SUPPORTED_COORDINATE_CONVENTION:
        raise ValueError("The Scene Snapshot coordinate/quaternion convention is unsupported")
    if snapshot.get("stableIdSchema") != "uint32":
        raise ValueError("The Scene Snapshot Stable Gaussian ID schema is unsupported")

    render_configuration = snapshot.get("renderConfiguration")
    if not isinstance(render_configuration, Mapping):
        raise ValueError("The Scene Snapshot render configuration is missing")
    if render_configuration.get("version") != SUPPORTED_RENDER_CONFIG_VERSION:
        raise ValueError("The Scene Snapshot render configuration version is unsupported")
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
    seen_stable_ids: set[int] = set()
    for gaussian in gaussians:
        if not isinstance(gaussian, Mapping):
            raise ValueError("Scene Snapshot Gaussian records must be objects")
        stable_id = gaussian.get("stableId")
        if (
            isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or not 0 <= stable_id <= 0xFFFFFFFF
            or stable_id in seen_stable_ids
        ):
            raise ValueError("Scene Snapshot Stable Gaussian IDs must be unique uint32 values")
        stable_ids.append(stable_id)
        seen_stable_ids.add(stable_id)
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
        or not isinstance(rasterized.service_rgb_bytes, bytes)
        or len(rasterized.service_rgb_bytes) != frame.width * frame.height * 3
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
            if error > _mass_conservation_tolerance(alpha):
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
        anchor_parity=_anchor_parity(rasterized, frame),
    )


def _anchor_parity(
    rasterized: GsplatRasterization, frame: RegisteredFrame
) -> str:
    """Compare service RGB with the exact editor Anchor while failing safely.

    Exact/small 8-bit differences are normal. Material appearance differences
    are moderate and therefore cannot create Anchor negative evidence. A major
    whole-frame displacement is severe and is rejected by Evidence Policy.
    """

    if frame.source != "anchor":
        return "normal"
    if frame.image_png is None:
        return "severe"
    try:
        from PIL import Image

        with Image.open(BytesIO(frame.image_png)) as image:
            if image.size != (frame.width, frame.height):
                return "severe"
            editor_rgb = image.convert("RGB").tobytes()
    except Exception:
        return "severe"
    mean_absolute_error = sum(
        abs(service - editor)
        for service, editor in zip(
            rasterized.service_rgb_bytes, editor_rgb, strict=True
        )
    ) / (len(editor_rgb) * 255.0)
    if mean_absolute_error <= ANCHOR_PARITY_NORMAL_MAE:
        return "normal"
    if mean_absolute_error <= ANCHOR_PARITY_SEVERE_MAE:
        return "moderate"
    return "severe"


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

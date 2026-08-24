"""Project-owned same-decision RGB and production Direct Evidence raster.

The CUDA kernel consumes gsplat's pinned projection/intersection products but
owns the authoritative front-to-back pixel decision chain. Each accepted
``alpha * incoming T`` weight feeds RGB and, when the pixel is in the declared
ROI, independent P/N/V/boundary atomics. Complete per-pixel Contributor data
is neither produced nor consumed by this path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from threading import Lock
from typing import Any, Final, Iterable, Sequence

from .masking import MaskSessionError
from .renderer_runtime import (
    EXPECTED_CUDA_VERSION,
    EXPECTED_GSPLAT_SOURCE_COMMIT,
    EXPECTED_RENDERER_LOCK_DIGEST,
    EXPECTED_TORCH_VERSION,
)


DIRECT_EVIDENCE_ABI_VERSION: Final = "supersimplat-direct-evidence-abi/v2"
DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID: Final = (
    "supersimplat-gsplat-direct-evidence/v1"
)
DIRECT_EVIDENCE_BACKEND_ID: Final = "global-atomic/direct-v1"
DIRECT_EVIDENCE_BUILD_FLAGS: Final = (
    "-O3",
    "--use_fast_math",
    "--generate-line-info",
    "--ptxas-options=-v",
)
# Updated only when the checked-in CUDA source changes. The loader verifies it
# before compilation so a dirty or mismatched source fails readiness closed.
DIRECT_EVIDENCE_SOURCE_REVISION: Final = (
    "sha256:3c14ab06a3f60c893de9e86d7242269e0eb43b253b1808ebbec8e60b59fae917"
)
DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES: Final = ((8, 9),)
_CUDA_SOURCE = Path(__file__).with_name("cuda") / "direct_evidence.cu"
_EXTENSION_LOCK = Lock()
_EXTENSION: Any | None = None


def _runtime_build_id() -> str:
    payload = "|".join((
        DIRECT_EVIDENCE_ABI_VERSION,
        DIRECT_EVIDENCE_SOURCE_REVISION,
        EXPECTED_RENDERER_LOCK_DIGEST,
        EXPECTED_TORCH_VERSION,
        EXPECTED_CUDA_VERSION,
        EXPECTED_GSPLAT_SOURCE_COMMIT,
        "cc=8.9",
        ",".join(DIRECT_EVIDENCE_BUILD_FLAGS),
    ))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


DIRECT_EVIDENCE_RUNTIME_BUILD_ID: Final = _runtime_build_id()


@dataclass(frozen=True)
class DirectEvidenceTelemetry:
    """Per-view buffers and observed allocator peak for the Direct operation."""

    evidence_buffer_bytes: int
    pixel_weight_buffer_bytes: int
    boundary_buffer_bytes: int
    peak_vram_bytes: int


@dataclass(frozen=True)
class DirectEvidenceRasterization:
    """One all-or-nothing authoritative RGB plus compact per-view P/N/V result."""

    service_rgb_digest: str
    service_rgb_bytes: bytes
    rgb: Any
    alpha: Any
    positive_mass: Any
    negative_mass: Any
    visible_mass: Any
    boundary_mass: Any
    stable_gaussian_ids: tuple[int, ...]
    boundary_contact_stable_gaussian_ids: tuple[int, ...]
    telemetry: DirectEvidenceTelemetry


def _expected_extension_name() -> str:
    return (
        "supersimplat_direct_evidence_"
        + DIRECT_EVIDENCE_RUNTIME_BUILD_ID.removeprefix("sha256:")[:16]
    )


def _extension_has_current_identity(extension: Any) -> bool:
    return (
        getattr(extension, "__name__", None) == _expected_extension_name()
        and getattr(extension, "abi_version", None) == DIRECT_EVIDENCE_ABI_VERSION
    )


def direct_evidence_source_revision() -> str:
    try:
        source = _CUDA_SOURCE.read_bytes()
    except OSError as error:
        raise MaskSessionError(
            "rendererUnavailable",
            "The Direct Evidence CUDA source is unavailable.",
        ) from error
    return f"sha256:{hashlib.sha256(source).hexdigest()}"


def direct_evidence_capability() -> dict[str, object]:
    """Return the complete source/build/runtime identity advertised at readiness."""

    source_revision = direct_evidence_source_revision()
    status = (
        "ready"
        if source_revision == DIRECT_EVIDENCE_SOURCE_REVISION
        and (
            _EXTENSION is None
            or _extension_has_current_identity(_EXTENSION)
        )
        else "unavailable"
    )
    detected_compute_capability: str | None = None
    try:
        import torch

        if torch.cuda.is_available():
            compute_capability = torch.cuda.get_device_capability()
            detected_compute_capability = (
                f"{compute_capability[0]}.{compute_capability[1]}"
            )
            if compute_capability not in DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES:
                status = "unavailable"
        else:
            status = "unavailable"
    except Exception:
        status = "unavailable"
    return {
        "status": status,
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
        "sourceRevision": source_revision,
        "expectedSourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
        "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        "torchVersion": EXPECTED_TORCH_VERSION,
        "cudaVersion": EXPECTED_CUDA_VERSION,
        "gsplatSourceCommit": EXPECTED_GSPLAT_SOURCE_COMMIT,
        "supportedComputeCapabilities": [
            f"{major}.{minor}"
            for major, minor in DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES
        ],
        "accumulation": "global-atomic-baseline",
        "buildFlags": list(DIRECT_EVIDENCE_BUILD_FLAGS),
        **(
            {}
            if detected_compute_capability is None
            else {"detectedComputeCapability": detected_compute_capability}
        ),
    }


def _load_extension() -> Any:
    global _EXTENSION
    if _EXTENSION is not None:
        if not _extension_has_current_identity(_EXTENSION):
            raise MaskSessionError(
                "rendererUnavailable",
                "The loaded Direct Evidence CUDA extension identity is stale.",
            )
        return _EXTENSION
    with _EXTENSION_LOCK:
        if _EXTENSION is not None:
            if not _extension_has_current_identity(_EXTENSION):
                raise MaskSessionError(
                    "rendererUnavailable",
                    "The loaded Direct Evidence CUDA extension identity is stale.",
                )
            return _EXTENSION
        if direct_evidence_source_revision() != DIRECT_EVIDENCE_SOURCE_REVISION:
            raise MaskSessionError(
                "rendererUnavailable",
                "The Direct Evidence CUDA source revision does not match this build.",
            )
        try:
            import torch
            from torch.utils.cpp_extension import load

            capability = torch.cuda.get_device_capability()
            if capability not in DIRECT_EVIDENCE_SUPPORTED_COMPUTE_CAPABILITIES:
                raise MaskSessionError(
                    "rendererUnavailable",
                    "Direct Evidence does not support this GPU compute capability.",
                )
            extension_name = _expected_extension_name()
            extension = load(
                name=extension_name,
                sources=[str(_CUDA_SOURCE)],
                extra_cuda_cflags=list(DIRECT_EVIDENCE_BUILD_FLAGS),
                with_cuda=True,
                verbose=False,
            )
            if not _extension_has_current_identity(extension):
                raise MaskSessionError(
                    "rendererUnavailable",
                    "The compiled Direct Evidence CUDA extension identity is stale.",
                )
            _EXTENSION = extension
        except MaskSessionError:
            raise
        except Exception as error:
            raise MaskSessionError(
                "rendererUnavailable",
                "The pinned Direct Evidence CUDA extension could not be loaded.",
            ) from error
        return _EXTENSION


def _validated_uint32_ids(
    values: Iterable[int],
    *,
    name: str,
    require_sorted: bool,
) -> tuple[int, ...]:
    result = tuple(values)
    if (
        not result
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > 0xFFFFFFFF
            for value in result
        )
        or len(set(result)) != len(result)
        or (require_sorted and any(
            result[index - 1] >= result[index]
            for index in range(1, len(result))
        ))
    ):
        raise MaskSessionError(
            "rendererInvalidEvidenceMapping",
            f"Direct Evidence {name} must contain unique uint32 identities"
            + (" in ascending order." if require_sorted else "."),
        )
    return result


def build_local_evidence_mapping(
    render_stable_gaussian_ids: Iterable[int],
    evidence_stable_gaussian_ids: Iterable[int],
    target_stable_gaussian_ids: Iterable[int],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Map render row -> Evidence-local row while retaining all occluders.

    ``-1`` marks a non-target/out-of-scope occluder and ``-2`` marks target
    support outside the current expandable Evidence Working Set.
    """

    render_ids = _validated_uint32_ids(
        render_stable_gaussian_ids,
        name="render row mapping",
        require_sorted=False,
    )
    evidence_ids = _validated_uint32_ids(
        evidence_stable_gaussian_ids,
        name="Working Set mapping",
        require_sorted=True,
    )
    target_ids = _validated_uint32_ids(
        target_stable_gaussian_ids,
        name="target mapping",
        require_sorted=True,
    )
    target_set = set(target_ids)
    if any(stable_id not in target_set for stable_id in evidence_ids):
        raise MaskSessionError(
            "rendererInvalidEvidenceMapping",
            "Direct Evidence Working Set contains a non-target identity.",
        )
    evidence_lookup = {
        stable_id: local_id for local_id, stable_id in enumerate(evidence_ids)
    }
    mapping = tuple(
        evidence_lookup.get(
            stable_id,
            -2 if stable_id in target_set else -1,
        )
        for stable_id in render_ids
    )
    return mapping, evidence_ids, render_ids


def _validated_projected_depth(
    meta: dict[str, Any],
    *,
    gaussian_count: int,
    expected_device: Any,
    failure_code: str,
    failure_message: str,
) -> Any:
    """Return the exact pinned gsplat depth rows or fail before CUDA dispatch."""

    import torch

    depths = meta.get("depths")
    if (
        not isinstance(depths, torch.Tensor)
        or not depths.is_cuda
        or depths.dtype != torch.float32
        or not depths.is_contiguous()
        or tuple(depths.shape) != (1, gaussian_count)
        or depths.device != expected_device
        or not bool(torch.isfinite(depths).all().item())
    ):
        raise MaskSessionError(failure_code, failure_message)
    return depths


def _pixel_weight_tensor(pixel_weights: object, *, device: Any) -> Any:
    import torch

    if (
        isinstance(pixel_weights, tuple)
        and len(pixel_weights) == 3
        and isinstance(pixel_weights[0], int)
        and isinstance(pixel_weights[1], int)
        and isinstance(pixel_weights[2], tuple)
        and len(pixel_weights[2]) == 4
        and all(
            isinstance(channel, torch.Tensor) for channel in pixel_weights[2]
        )
    ):
        width = pixel_weights[0]
        height = pixel_weights[1]
        channels = pixel_weights[2]
        if any(channel.numel() != width * height for channel in channels):
            raise MaskSessionError(
                "invalidDirectEvidence",
                "Direct Evidence tensor weights are incomplete.",
            )
        tensor = torch.stack(channels, dim=-1).to(
            device=device, dtype=torch.float32
        )
        if not bool(torch.isfinite(tensor).all().item()) or bool(
            (tensor < 0).any().item()
        ):
            raise MaskSessionError(
                "invalidDirectEvidence",
                "Direct Evidence tensor weights must be finite and non-negative.",
            )
        return tensor.reshape(height, width, 4).contiguous()

    width = getattr(pixel_weights, "width", None)
    height = getattr(pixel_weights, "height", None)
    values = getattr(pixel_weights, "values", None)
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or not isinstance(values, Sequence)
        or len(values) != width * height
    ):
        raise MaskSessionError(
            "invalidDirectEvidence",
            "Direct Evidence pixel weights are incomplete.",
        )
    flattened: list[tuple[float, float, float, float]] = []
    for value in values:
        channels = tuple(
            float(getattr(value, name))
            for name in ("positive", "negative", "visible", "boundary")
        )
        if any(channel < 0.0 for channel in channels):
            raise MaskSessionError(
                "invalidDirectEvidence",
                "Direct Evidence pixel weights must be finite and non-negative.",
            )
        flattened.append(channels)
    tensor = torch.tensor(flattened, dtype=torch.float32, device=device)
    if not bool(torch.isfinite(tensor).all().item()):
        raise MaskSessionError(
            "invalidDirectEvidence",
            "Direct Evidence pixel weights must be finite and non-negative.",
        )
    return tensor.reshape(height, width, 4).contiguous()


def _run_projected_kernel(
    *,
    meta: dict[str, Any],
    projected_depths: Any,
    evaluated_colors: Any,
    background: Any,
    local_ids: Any,
    weights: Any,
    width: int,
    height: int,
    evidence_count: int,
    evidence_enabled: bool,
    boundary_capacity: int,
) -> tuple[Any, Any, Any, Any, int, bool, int]:
    """Invoke the extension once and return GPU outputs plus diagnostics."""

    import torch

    extension = _load_extension()
    device = meta["means2d"].device
    torch.cuda.reset_peak_memory_stats(device)
    (
        rgb,
        alpha,
        masses,
        boundary_rows,
        boundary_count,
        boundary_overflow,
    ) = extension.rasterize_direct_evidence(
        meta["means2d"].contiguous(),
        projected_depths,
        meta["conics"].contiguous(),
        evaluated_colors.contiguous(),
        meta["opacities"].contiguous(),
        background.reshape(-1).contiguous(),
        meta["isect_offsets"].contiguous(),
        meta["flatten_ids"].to(dtype=torch.int32).contiguous(),
        local_ids,
        weights,
        width,
        height,
        evidence_count,
        evidence_enabled,
        boundary_capacity,
    )
    return (
        rgb,
        alpha,
        masses,
        boundary_rows,
        int(boundary_count.item()),
        bool(boundary_overflow.item()),
        int(torch.cuda.max_memory_allocated(device)),
    )


def rasterize_projected_authoritative_rgb(
    *,
    meta: dict[str, Any],
    evaluated_colors: Any,
    background: Any,
    width: int,
    height: int,
) -> DirectEvidenceRasterization:
    """Run the Direct-Evidence-capable raster with all Evidence writes disabled."""

    import torch

    means2d = meta["means2d"]
    if (
        means2d.ndim != 3
        or means2d.shape[0] != 1
        or tuple(evaluated_colors.shape) != (1, means2d.shape[1], 3)
    ):
        raise MaskSessionError(
            "rendererFailure",
            "Direct Evidence authoritative RGB projected rows are invalid.",
        )
    device = means2d.device
    projected_depths = _validated_projected_depth(
        meta,
        gaussian_count=means2d.shape[1],
        expected_device=device,
        failure_code="rendererFailure",
        failure_message=(
            "Direct Evidence authoritative RGB projected depth is invalid."
        ),
    )
    local_ids = torch.full(
        (means2d.shape[1],), -1, dtype=torch.int32, device=device
    )
    disabled_weights = torch.empty((0,), dtype=torch.float32, device=device)
    try:
        rgb, alpha, masses, _, _, _, peak = _run_projected_kernel(
            meta=meta,
            projected_depths=projected_depths,
            evaluated_colors=evaluated_colors,
            background=background,
            local_ids=local_ids,
            weights=disabled_weights,
            width=width,
            height=height,
            evidence_count=0,
            evidence_enabled=False,
            boundary_capacity=1,
        )
        rgb_bytes = (
            rgb.detach()
            .clamp(0.0, 1.0)
            .mul(255.0)
            .round()
            .to(torch.uint8)
            .cpu()
            .contiguous()
            .numpy()
            .tobytes()
        )
        if not bool(torch.isfinite(rgb).all().item()):
            raise MaskSessionError(
                "rendererFailure", "Direct Evidence authoritative RGB is non-finite."
            )
    except MaskSessionError:
        raise
    except Exception as error:
        raise MaskSessionError(
            "rendererFailure", "Direct Evidence authoritative RGB failed."
        ) from error
    return DirectEvidenceRasterization(
        service_rgb_digest=f"sha256:{hashlib.sha256(rgb_bytes).hexdigest()}",
        service_rgb_bytes=rgb_bytes,
        rgb=rgb,
        alpha=alpha,
        positive_mass=masses[:, 0],
        negative_mass=masses[:, 1],
        visible_mass=masses[:, 2],
        boundary_mass=masses[:, 3],
        stable_gaussian_ids=(),
        boundary_contact_stable_gaussian_ids=(),
        telemetry=DirectEvidenceTelemetry(
            evidence_buffer_bytes=0,
            pixel_weight_buffer_bytes=0,
            boundary_buffer_bytes=12,
            peak_vram_bytes=peak,
        ),
    )


def rasterize_projected_direct_evidence(
    *,
    meta: dict[str, Any],
    evaluated_colors: Any,
    background: Any,
    render_stable_gaussian_ids: Iterable[int],
    evidence_stable_gaussian_ids: Iterable[int],
    target_stable_gaussian_ids: Iterable[int],
    pixel_weights: object,
    width: int,
    height: int,
) -> DirectEvidenceRasterization:
    """Run the pinned global-atomic baseline and publish only complete output."""

    import torch

    mapping, evidence_ids, render_ids = build_local_evidence_mapping(
        render_stable_gaussian_ids,
        evidence_stable_gaussian_ids,
        target_stable_gaussian_ids,
    )
    means2d = meta["means2d"].contiguous()
    device = means2d.device
    if (
        means2d.ndim != 3
        or means2d.shape[0] != 1
        or means2d.shape[1] != len(render_ids)
        or tuple(evaluated_colors.shape) != (1, len(render_ids), 3)
    ):
        raise MaskSessionError(
            "rendererInvalidEvidenceMapping",
            "Direct Evidence projected rows do not match Stable Gaussian identity.",
        )
    projected_depths = _validated_projected_depth(
        meta,
        gaussian_count=len(render_ids),
        expected_device=device,
        failure_code="rendererInvalidEvidenceMapping",
        failure_message=(
            "Direct Evidence projected depth does not match the render rows."
        ),
    )
    weights = _pixel_weight_tensor(pixel_weights, device=device)
    if tuple(weights.shape[:2]) != (height, width):
        raise MaskSessionError(
            "invalidDirectEvidence",
            "Direct Evidence weights do not match the authoritative RGB dimensions.",
        )
    local_ids = torch.tensor(mapping, dtype=torch.int32, device=device)
    boundary_capacity = max(4096, len(evidence_ids) * 8)
    try:
        (
            rgb,
            alpha,
            masses,
            boundary_rows,
            boundary_count,
            boundary_overflow,
            peak,
        ) = _run_projected_kernel(
            meta=meta,
            projected_depths=projected_depths,
            evaluated_colors=evaluated_colors,
            background=background,
            local_ids=local_ids,
            weights=weights,
            width=width,
            height=height,
            evidence_count=len(evidence_ids),
            evidence_enabled=True,
            boundary_capacity=boundary_capacity,
        )
        if boundary_overflow:
            raise MaskSessionError(
                "evidenceWorkingSetBoundaryOverflow",
                "Direct Evidence Working Set boundary diagnostics overflowed; no artifact was published.",
            )
        contact_count = min(boundary_count, boundary_capacity)
        boundary_render_rows = (
            boundary_rows[:contact_count].detach().cpu().tolist()
            if contact_count
            else []
        )
        boundary_ids = tuple(sorted({render_ids[row] for row in boundary_render_rows}))
        rgb_bytes = (
            rgb.detach()
            .clamp(0.0, 1.0)
            .mul(255.0)
            .round()
            .to(torch.uint8)
            .cpu()
            .contiguous()
            .numpy()
            .tobytes()
        )
        if not bool(torch.isfinite(rgb).all().item()) or not bool(
            torch.isfinite(masses).all().item()
        ):
            raise MaskSessionError(
                "rendererFailure",
                "Direct Evidence returned non-finite output; no artifact was published.",
            )
    except MaskSessionError:
        raise
    except Exception as error:
        raise MaskSessionError(
            "rendererFailure",
            "Direct Evidence failed; no partial artifact was published.",
        ) from error
    return DirectEvidenceRasterization(
        service_rgb_digest=f"sha256:{hashlib.sha256(rgb_bytes).hexdigest()}",
        service_rgb_bytes=rgb_bytes,
        rgb=rgb,
        alpha=alpha,
        positive_mass=masses[:, 0],
        negative_mass=masses[:, 1],
        visible_mass=masses[:, 2],
        boundary_mass=masses[:, 3],
        stable_gaussian_ids=evidence_ids,
        boundary_contact_stable_gaussian_ids=boundary_ids,
        telemetry=DirectEvidenceTelemetry(
            evidence_buffer_bytes=len(evidence_ids) * 4 * 4,
            pixel_weight_buffer_bytes=height * width * 4 * 4,
            boundary_buffer_bytes=boundary_capacity * 4 + 8,
            peak_vram_bytes=peak,
        ),
    )


__all__ = [
    "DIRECT_EVIDENCE_ABI_VERSION",
    "DIRECT_EVIDENCE_BACKEND_ID",
    "DIRECT_EVIDENCE_BUILD_FLAGS",
    "DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID",
    "DIRECT_EVIDENCE_RUNTIME_BUILD_ID",
    "DIRECT_EVIDENCE_SOURCE_REVISION",
    "DirectEvidenceRasterization",
    "DirectEvidenceTelemetry",
    "build_local_evidence_mapping",
    "direct_evidence_capability",
    "direct_evidence_source_revision",
    "rasterize_projected_authoritative_rgb",
    "rasterize_projected_direct_evidence",
]

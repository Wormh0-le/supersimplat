"""Companion-internal scalar reference and CWED depth-moment readout."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Final, Iterable


_ALPHA_THRESHOLD: Final = 1.0 / 255.0
_MAXIMUM_ALPHA: Final = 0.99
_TRANSMITTANCE_THRESHOLD: Final = 1.0e-4
_VARIANCE_ROUNDOFF_ULPS: Final = 8


@dataclass(frozen=True)
class ScalarDepthContributor:
    """One projected contributor in front-to-back raster order."""

    sigma: float
    opacity: float
    projected_depth: float


@dataclass(frozen=True)
class ScalarDepthMoments:
    """Scalar M0/M1/M2 reference output for one pixel."""

    m0: float
    m1: float
    m2: float


@dataclass(frozen=True)
class DepthMomentValidityPolicy:
    """Explicit versioned minimum-mass policy supplied by a shadow consumer."""

    policy_id: str
    minimum_m0: float

    def __post_init__(self) -> None:
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise ValueError("Depth-moment policy_id must be a non-empty string.")
        if (
            isinstance(self.minimum_m0, bool)
            or not isinstance(self.minimum_m0, (int, float))
            or not math.isfinite(float(self.minimum_m0))
            or self.minimum_m0 <= 0.0
        ):
            raise ValueError("Depth-moment minimum_m0 must be finite and positive.")


@dataclass(frozen=True)
class DepthMomentReadout:
    """Derived validity, CWED, and variance for one raw moment image."""

    policy: DepthMomentValidityPolicy
    valid: Any
    cwed: Any
    variance: Any


def rasterize_scalar_depth_moments(
    contributors: Iterable[ScalarDepthContributor],
) -> ScalarDepthMoments:
    """Apply the Direct Evidence acceptance chain to one scalar pixel."""

    transmittance = 1.0
    m0 = 0.0
    m1 = 0.0
    m2 = 0.0
    for contributor in contributors:
        if not all((
            math.isfinite(contributor.sigma),
            math.isfinite(contributor.opacity),
            math.isfinite(contributor.projected_depth),
        )):
            raise ValueError("Scalar depth contributors must be finite.")
        if contributor.sigma < 0.0:
            continue
        visibility = math.exp(-contributor.sigma)
        alpha = min(_MAXIMUM_ALPHA, contributor.opacity * visibility)
        if alpha < _ALPHA_THRESHOLD:
            continue
        next_transmittance = transmittance * (1.0 - alpha)
        if next_transmittance <= _TRANSMITTANCE_THRESHOLD:
            break
        accepted_weight = alpha * transmittance
        depth = contributor.projected_depth
        m0 += accepted_weight
        m1 += accepted_weight * depth
        m2 += accepted_weight * depth * depth
        transmittance = next_transmittance
    return ScalarDepthMoments(m0=m0, m1=m1, m2=m2)


def derive_depth_moment_readout(
    depth_moments: Any,
    *,
    policy: DepthMomentValidityPolicy,
) -> DepthMomentReadout:
    """Derive CWED without converting invalid pixels into background depth."""

    import torch

    if (
        not isinstance(depth_moments, torch.Tensor)
        or depth_moments.dtype != torch.float32
        or not depth_moments.is_contiguous()
        or depth_moments.ndim != 3
        or depth_moments.shape[2] != 3
    ):
        raise ValueError("Depth moments must be contiguous float32 [H,W,3].")

    m0, m1, m2 = depth_moments.unbind(dim=2)
    finite_moments = torch.isfinite(depth_moments).all(dim=2)
    mass_valid = finite_moments & (m0 >= float(policy.minimum_m0))
    safe_m0 = torch.where(mass_valid, m0, torch.ones_like(m0))
    candidate_cwed = m1 / safe_m0
    candidate_second_moment = m2 / safe_m0
    candidate_variance = candidate_second_moment - candidate_cwed.square()
    variance_scale = torch.maximum(
        torch.maximum(
            candidate_second_moment.abs(),
            candidate_cwed.square().abs(),
        ),
        torch.ones_like(candidate_variance),
    )
    roundoff_bound = (
        _VARIANCE_ROUNDOFF_ULPS
        * torch.finfo(depth_moments.dtype).eps
        * variance_scale
    )
    valid = (
        mass_valid
        & torch.isfinite(candidate_cwed)
        & torch.isfinite(candidate_variance)
        & (candidate_variance >= -roundoff_bound)
    )
    invalid = torch.full_like(m0, float("nan"))
    cwed = torch.where(valid, candidate_cwed, invalid)
    variance = torch.where(valid, candidate_variance.clamp_min(0.0), invalid)
    return DepthMomentReadout(
        policy=policy,
        valid=valid,
        cwed=cwed,
        variance=variance,
    )


__all__ = [
    "DepthMomentReadout",
    "DepthMomentValidityPolicy",
    "ScalarDepthContributor",
    "ScalarDepthMoments",
    "derive_depth_moment_readout",
    "rasterize_scalar_depth_moments",
]

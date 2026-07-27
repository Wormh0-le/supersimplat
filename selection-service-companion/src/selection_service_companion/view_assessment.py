"""Versioned P0 local View Assessment for AI Select.

The policy consumes only measurable Mask geometry, propagation metadata, and
an optional declared Gaussian support diagnostic. It does not consume complete
Contributor publication, infer semantic causes from missing diagnostics, or
produce a unified confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION = "local-view-assessment/v1"
AI_SELECT_LOCAL_VIEW_SUPPORT_POLICY_VERSION = "local-view-support-probe/v1"

_WEAK_GAUSSIAN_SUPPORT_COUNT = 25
_FRAGMENTED_LARGEST_COMPONENT_RATIO = 0.9
_MIN_PROPAGATED_SUPPORT_COUNT = 4
_MIN_PROPAGATED_PROMPT_COUNT = 2
_MAX_ACTIONABLE_REASONS = 2

ReviewReason = Literal[
    "target-at-boundary",
    "fragmented-mask",
    "weak-gaussian-support",
    "propagation-uncertain",
]
AssessmentStatus = Literal["good", "review", "failed"]

_REASON_ORDER: tuple[ReviewReason, ...] = (
    "target-at-boundary",
    "fragmented-mask",
    "weak-gaussian-support",
    "propagation-uncertain",
)


@dataclass(frozen=True)
class PropagationDiagnostic:
    policy_version: str
    projected_support_count: int
    prompt_count: int


@dataclass(frozen=True)
class SupportDiagnostic:
    policy_version: str
    observed_gaussian_count: int


@dataclass(frozen=True)
class LocalViewAssessmentDiagnostics:
    foreground_pixels: int
    boundary_contact_ratio: float
    connected_components: int
    largest_component_ratio: float
    observed_gaussian_count: int | None
    projected_support_count: int | None
    prompt_count: int | None


@dataclass(frozen=True)
class LocalViewAssessment:
    status: AssessmentStatus
    primary_reason: ReviewReason | None
    reasons: tuple[ReviewReason, ...]
    actionable_reasons: tuple[ReviewReason, ...]
    diagnostics: LocalViewAssessmentDiagnostics
    policy_version: str
    support_policy_version: str | None
    propagation_policy_version: str | None


def _is_foreground(mask: bytes, pixel: int) -> bool:
    return ((mask[pixel >> 3] >> (pixel & 7)) & 1) == 1


def _measure_mask(
    *, width: int, height: int, mask: bytes
) -> tuple[int, int, int, int]:
    visited = bytearray(width * height)
    foreground_pixels = 0
    boundary_pixels = 0
    components = 0
    largest_component = 0

    for pixel in range(width * height):
        if not _is_foreground(mask, pixel):
            continue
        foreground_pixels += 1
        x = pixel % width
        y = pixel // width
        if x == 0 or y == 0 or x == width - 1 or y == height - 1:
            boundary_pixels += 1
        if visited[pixel]:
            continue

        components += 1
        component_size = 0
        pending = [pixel]
        visited[pixel] = 1
        while pending:
            current = pending.pop()
            component_size += 1
            current_x = current % width
            current_y = current // width
            neighbours = (
                (current_x - 1, current_y),
                (current_x + 1, current_y),
                (current_x, current_y - 1),
                (current_x, current_y + 1),
            )
            for neighbour_x, neighbour_y in neighbours:
                if (
                    neighbour_x < 0
                    or neighbour_x >= width
                    or neighbour_y < 0
                    or neighbour_y >= height
                ):
                    continue
                neighbour = neighbour_y * width + neighbour_x
                if visited[neighbour] or not _is_foreground(mask, neighbour):
                    continue
                visited[neighbour] = 1
                pending.append(neighbour)
        largest_component = max(largest_component, component_size)

    return foreground_pixels, boundary_pixels, components, largest_component


def assess_local_view(
    *,
    width: int,
    height: int,
    mask: bytes,
    propagation: PropagationDiagnostic | None,
    support: SupportDiagnostic | None,
) -> LocalViewAssessment:
    """Assess one exact Mask revision from version-bound local diagnostics."""

    if width <= 0 or height <= 0:
        raise ValueError("View Assessment dimensions must be positive")
    if len(mask) != (width * height + 7) // 8:
        raise ValueError("View Assessment mask does not match its dimensions")
    if propagation is not None and (
        not propagation.policy_version
        or propagation.projected_support_count < 0
        or propagation.prompt_count < 0
    ):
        raise ValueError("View Assessment propagation diagnostic is invalid")
    if support is not None and (
        not support.policy_version or support.observed_gaussian_count < 0
    ):
        raise ValueError("View Assessment support diagnostic is invalid")

    foreground, boundary, components, largest = _measure_mask(
        width=width,
        height=height,
        mask=mask,
    )
    boundary_ratio = 0.0 if foreground == 0 else boundary / foreground
    largest_ratio = 0.0 if foreground == 0 else largest / foreground
    diagnostics = LocalViewAssessmentDiagnostics(
        foreground_pixels=foreground,
        boundary_contact_ratio=boundary_ratio,
        connected_components=components,
        largest_component_ratio=largest_ratio,
        observed_gaussian_count=(
            None if support is None else support.observed_gaussian_count
        ),
        projected_support_count=(
            None
            if propagation is None
            else propagation.projected_support_count
        ),
        prompt_count=None if propagation is None else propagation.prompt_count,
    )
    if foreground == 0:
        return LocalViewAssessment(
            status="failed",
            primary_reason=None,
            reasons=(),
            actionable_reasons=(),
            diagnostics=diagnostics,
            policy_version=AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
            support_policy_version=(
                None if support is None else support.policy_version
            ),
            propagation_policy_version=(
                None if propagation is None else propagation.policy_version
            ),
        )

    detected: set[ReviewReason] = set()
    if boundary > 0:
        detected.add("target-at-boundary")
    if (
        components > 1
        and largest_ratio < _FRAGMENTED_LARGEST_COMPONENT_RATIO
    ):
        detected.add("fragmented-mask")
    if (
        support is not None
        and support.observed_gaussian_count < _WEAK_GAUSSIAN_SUPPORT_COUNT
    ):
        detected.add("weak-gaussian-support")
    if propagation is not None and (
        propagation.projected_support_count < _MIN_PROPAGATED_SUPPORT_COUNT
        or propagation.prompt_count < _MIN_PROPAGATED_PROMPT_COUNT
    ):
        detected.add("propagation-uncertain")

    reasons = tuple(reason for reason in _REASON_ORDER if reason in detected)
    return LocalViewAssessment(
        status="review" if reasons else "good",
        primary_reason=reasons[0] if reasons else None,
        reasons=reasons,
        actionable_reasons=reasons[:_MAX_ACTIONABLE_REASONS],
        diagnostics=diagnostics,
        policy_version=AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        support_policy_version=(
            None if support is None else support.policy_version
        ),
        propagation_policy_version=(
            None if propagation is None else propagation.policy_version
        ),
    )


__all__ = [
    "AI_SELECT_LOCAL_VIEW_SUPPORT_POLICY_VERSION",
    "AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION",
    "LocalViewAssessment",
    "LocalViewAssessmentDiagnostics",
    "PropagationDiagnostic",
    "ReviewReason",
    "SupportDiagnostic",
    "assess_local_view",
]

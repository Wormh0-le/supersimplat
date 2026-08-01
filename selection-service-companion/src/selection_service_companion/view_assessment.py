"""Versioned local per-View Mask Review for AI Select (Final Spec v1.3 §14).

The policy consumes only the exact current Mask geometry and, when the Prompt
family exists, the instance Prompt that produced the Mask. It never consumes
tracker propagation or Gaussian visibility/support: ``propagation-uncertain``
is deleted because no tracker propagation exists, and ``weak-gaussian-support``
belongs to Ticket 13 Lift Readiness, not Mask quality. Missing optional
diagnostics never fabricate a reason, and no unified confidence score exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION = "local-view-assessment/v2"

# A Mask below this many foreground pixels cannot support a meaningful object
# decision; empty and degenerate Masks fail instead of entering Review.
_MIN_FOREGROUND_PIXELS = 4
# A Mask covering (nearly) the whole frame is not an object Mask.
_FULL_FRAME_RATIO = 0.98
# Boundary Review requires a meaningful contact margin and ratio, never any
# one-pixel contact (a thin object merely touching the edge stays Good).
_CLIPPED_MIN_BOUNDARY_PIXELS = 8
_CLIPPED_MIN_BOUNDARY_RATIO = 0.2
# Fragmentation requires material disconnected mass, not merely multiple tiny
# components: speckles next to one dominant component stay Good.
_FRAGMENT_MIN_DISCONNECTED_PIXELS = 16
_FRAGMENT_MIN_DISCONNECTED_RATIO = 0.1
# Box spill is measured outside the Box expanded by a small margin; only gross
# spill (neighbour-leak scale) is flagged.
_BOX_SPILL_MARGIN_PIXELS = 2
_BOX_SPILL_MIN_PIXELS = 16
_BOX_SPILL_MIN_RATIO = 0.2
_MAX_ACTIONABLE_REASONS = 2

ReviewReason = Literal[
    "prompt-inconsistent",
    "target-materially-clipped",
    "severely-fragmented",
    "box-spill-or-neighbour-leak",
    "empty-or-degenerate-mask",
]
AssessmentStatus = Literal["good", "review", "failed"]

_REASON_ORDER: tuple[ReviewReason, ...] = (
    "prompt-inconsistent",
    "target-materially-clipped",
    "severely-fragmented",
    "box-spill-or-neighbour-leak",
    "empty-or-degenerate-mask",
)


@dataclass(frozen=True)
class MaskReviewPrompt:
    """The instance Prompt family that produced the Mask, when one exists.

    Point/Box consistency is evaluated only when the corresponding family
    exists; an absent family contributes no reason.
    """

    positive_points: tuple[tuple[int, int], ...] = ()
    negative_points: tuple[tuple[int, int], ...] = ()
    box_xyxy: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class LocalViewAssessmentDiagnostics:
    frame_pixels: int
    foreground_pixels: int
    boundary_pixels: int
    boundary_contact_ratio: float
    connected_components: int
    largest_component_ratio: float
    prompt_point_count: int | None
    prompt_violation_count: int | None
    box_spill_pixels: int | None
    box_spill_ratio: float | None


@dataclass(frozen=True)
class LocalViewAssessment:
    status: AssessmentStatus
    primary_reason: ReviewReason | None
    reasons: tuple[ReviewReason, ...]
    actionable_reasons: tuple[ReviewReason, ...]
    diagnostics: LocalViewAssessmentDiagnostics
    policy_version: str


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


def _count_box_spill(
    *,
    width: int,
    height: int,
    mask: bytes,
    box_xyxy: tuple[int, int, int, int],
) -> int:
    x0, y0, x1, y1 = box_xyxy
    left = max(0, x0 - _BOX_SPILL_MARGIN_PIXELS)
    top = max(0, y0 - _BOX_SPILL_MARGIN_PIXELS)
    right = min(width - 1, x1 + _BOX_SPILL_MARGIN_PIXELS)
    bottom = min(height - 1, y1 + _BOX_SPILL_MARGIN_PIXELS)
    spill = 0
    for y in range(height):
        for x in range(width):
            if left <= x <= right and top <= y <= bottom:
                continue
            if _is_foreground(mask, y * width + x):
                spill += 1
    return spill


def assess_local_view(
    *,
    width: int,
    height: int,
    mask: bytes,
    prompt: MaskReviewPrompt | None = None,
) -> LocalViewAssessment:
    """Review one exact Mask revision from version-bound local geometry."""

    if width <= 0 or height <= 0:
        raise ValueError("Mask Review dimensions must be positive")
    if len(mask) != (width * height + 7) // 8:
        raise ValueError("Mask Review mask does not match its dimensions")
    if prompt is not None:
        for point in (*prompt.positive_points, *prompt.negative_points):
            x, y = point
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Mask Review Prompt point is outside the View")
        if prompt.box_xyxy is not None:
            x0, y0, x1, y1 = prompt.box_xyxy
            if not (0 <= x0 < x1 < width and 0 <= y0 < y1 < height):
                raise ValueError("Mask Review Prompt Box is invalid")

    foreground, boundary, components, largest = _measure_mask(
        width=width,
        height=height,
        mask=mask,
    )
    boundary_ratio = 0.0 if foreground == 0 else boundary / foreground
    largest_ratio = 0.0 if foreground == 0 else largest / foreground

    prompt_point_count: int | None = None
    prompt_violation_count: int | None = None
    box_spill_pixels: int | None = None
    box_spill_ratio: float | None = None
    if prompt is not None:
        violations = 0
        for x, y in prompt.positive_points:
            if not _is_foreground(mask, y * width + x):
                violations += 1
        for x, y in prompt.negative_points:
            if _is_foreground(mask, y * width + x):
                violations += 1
        prompt_point_count = len(prompt.positive_points) + len(
            prompt.negative_points
        )
        prompt_violation_count = violations
        if prompt.box_xyxy is not None:
            box_spill_pixels = _count_box_spill(
                width=width,
                height=height,
                mask=mask,
                box_xyxy=prompt.box_xyxy,
            )
            box_spill_ratio = (
                0.0 if foreground == 0 else box_spill_pixels / foreground
            )

    diagnostics = LocalViewAssessmentDiagnostics(
        frame_pixels=width * height,
        foreground_pixels=foreground,
        boundary_pixels=boundary,
        boundary_contact_ratio=boundary_ratio,
        connected_components=components,
        largest_component_ratio=largest_ratio,
        prompt_point_count=prompt_point_count,
        prompt_violation_count=prompt_violation_count,
        box_spill_pixels=box_spill_pixels,
        box_spill_ratio=box_spill_ratio,
    )

    # Empty, degenerate, and full-frame Masks fail closed with one structured
    # reason; they never enter Review and never invent geometry semantics.
    if (
        foreground < _MIN_FOREGROUND_PIXELS
        or foreground >= _FULL_FRAME_RATIO * width * height
    ):
        return LocalViewAssessment(
            status="failed",
            primary_reason="empty-or-degenerate-mask",
            reasons=("empty-or-degenerate-mask",),
            actionable_reasons=(),
            diagnostics=diagnostics,
            policy_version=AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        )

    detected: set[ReviewReason] = set()
    if prompt_violation_count:
        detected.add("prompt-inconsistent")
    if (
        boundary >= _CLIPPED_MIN_BOUNDARY_PIXELS
        and boundary_ratio >= _CLIPPED_MIN_BOUNDARY_RATIO
    ):
        detected.add("target-materially-clipped")
    disconnected = foreground - largest
    if (
        disconnected >= _FRAGMENT_MIN_DISCONNECTED_PIXELS
        and disconnected >= _FRAGMENT_MIN_DISCONNECTED_RATIO * foreground
    ):
        detected.add("severely-fragmented")
    if (
        box_spill_pixels is not None
        and box_spill_pixels >= _BOX_SPILL_MIN_PIXELS
        and box_spill_ratio is not None
        and box_spill_ratio >= _BOX_SPILL_MIN_RATIO
    ):
        detected.add("box-spill-or-neighbour-leak")

    reasons = tuple(reason for reason in _REASON_ORDER if reason in detected)
    return LocalViewAssessment(
        status="review" if reasons else "good",
        primary_reason=reasons[0] if reasons else None,
        reasons=reasons,
        actionable_reasons=reasons[:_MAX_ACTIONABLE_REASONS],
        diagnostics=diagnostics,
        policy_version=AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
    )


__all__ = [
    "AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION",
    "AssessmentStatus",
    "LocalViewAssessment",
    "LocalViewAssessmentDiagnostics",
    "MaskReviewPrompt",
    "ReviewReason",
    "assess_local_view",
]

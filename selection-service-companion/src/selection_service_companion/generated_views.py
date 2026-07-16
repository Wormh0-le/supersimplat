"""Bounded Generated View planning for complete Object Selection previews.

The module deliberately contains policy and validation rather than renderer
code.  A renderer supplies service-owned RGB frames and contributor support;
this module derives a Seed Region from the accepted Anchor mask, keeps the
candidate budget finite, and exposes only a safe public Frame Set shape to the
editor.  It never classifies Stable Gaussian IDs.
"""

from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Mapping, Protocol, Sequence

from .evidence import ContributorRenderer, RenderedContributorView, validate_rendered_view
from .masking import MaskSessionError, RegisteredFrame, RegisteredFrameSet


POLICY_ID = "generated-view-policy/v1"
PREFLIGHT_POLICY_ID = "gsplat-camera-preflight/v1"
NEIGHBOR_ANOMALY_POLICY_ID = "generated-view-neighbor-anomaly/v1"
GENERATED_VIEW_RESOLUTIONS = (1008, 768, 512)
INITIAL_VIEW_BUDGET = 16
REPLACEMENT_BUDGET = 8
TOTAL_VIEW_BUDGET = INITIAL_VIEW_BUDGET + REPLACEMENT_BUDGET
NEIGHBOR_ANOMALY_THRESHOLDS = {
    "minimumAreaRatio": 0.05,
    "maximumAreaRatio": 20.0,
    "minimumExtentRatio": 0.1,
    "maximumExtentRatio": 10.0,
    "maximumCenterDisplacement": 0.8,
    "minimumProjectedSeedOverlap": 0.05,
    "minimumProjectedSeedOverlapRatio": 0.1,
    "maximumProjectedSeedOverlapRatio": 10.0,
    "minimumContributorCountRatio": 0.1,
    "maximumContributorCountRatio": 10.0,
    "minimumTrackingConfidenceRatio": 0.5,
}


def generated_render_config_version(base_version: str, resolution: int) -> str:
    """Bind one full attempt to a unique immutable square render configuration."""

    return f"{base_version}+generated-{resolution}x{resolution}-v1"


@dataclass(frozen=True)
class SeedRegion:
    """A robust framing hint, never a Gaussian Selection or object boundary."""

    center: tuple[float, float, float]
    radius: float
    source: str
    stable_ids: tuple[int, ...]


@dataclass(frozen=True)
class GeneratedViewCandidate:
    """One service-rendered candidate plus its policy-facing camera facts."""

    frame: RegisteredFrame
    category: str
    azimuth_degrees: float | None = None
    elevation_degrees: float | None = None
    replacement_of: str | None = None


@dataclass(frozen=True)
class PlannedGeneratedViewCandidate:
    """An unrendered camera candidate produced before any RGB/SAM work."""

    view_id: str
    camera: Mapping[str, Any]
    category: str
    azimuth_degrees: float | None = None
    elevation_degrees: float | None = None
    replacement_of: str | None = None


@dataclass(frozen=True)
class GeneratedViewCameraPlan:
    """A bounded camera-only plan that is safe to preflight as one batch."""

    frame_set_id: str
    primary: tuple[PlannedGeneratedViewCandidate, ...]
    replacements: tuple[PlannedGeneratedViewCandidate, ...]


@dataclass(frozen=True)
class CameraPreflightResult:
    """Internal measured camera outcome; diagnostics never enter public payloads."""

    accepted: bool
    camera: Mapping[str, Any] | None
    diagnostics: Mapping[str, Any]


class GeneratedViewRenderer(ContributorRenderer, Protocol):
    """Contributor renderer capability needed for service-owned hidden views."""

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
        """Return bounded camera candidates without rendering RGB or contributors."""

    def preflight(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        seed_region: SeedRegion,
        resolution: int,
    ) -> CameraPreflightResult:
        """Probe one camera before full-resolution rendering or SAM work."""

    def render_generated(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        candidate: PlannedGeneratedViewCandidate,
        preflight: CameraPreflightResult,
        resolution: int,
    ) -> RegisteredFrame:
        """Render immutable RGB and cache its same-rasterization contributors."""


@dataclass(frozen=True)
class PreparedGeneratedViews:
    """A camera-only Generated View plan with no unpublished RGB or masks."""

    seed_region: SeedRegion
    frame_set_id: str
    render_config_version: str
    anchor_frame_set: RegisteredFrameSet
    primary: tuple[PlannedGeneratedViewCandidate, ...]
    replacements: tuple[PlannedGeneratedViewCandidate, ...]


@dataclass(frozen=True)
class SelectedGeneratedViews:
    """The final immutable Frame Set selected from temporary prefix replays."""

    frame_set: RegisteredFrameSet
    rejected_views: tuple[dict[str, object], ...]
    attempted_view_ids: tuple[str, ...]
    quality_diagnostics: Mapping[str, object]


@dataclass(frozen=True)
class CandidateQualityMeasurement:
    """Comparable mask and contributor facts retained only before publication."""

    contributor_ids: frozenset[int]
    frame_width: int
    frame_height: int
    mask_area_fraction: float
    extent_fraction: float
    bounding_width_fraction: float
    bounding_height_fraction: float
    center_x_fraction: float
    center_y_fraction: float


@dataclass(frozen=True)
class AcceptedNeighbor:
    """The immediately preceding accepted view used for anomaly comparison."""

    view_id: str
    measurement: CandidateQualityMeasurement
    projected_seed_overlap: float


@dataclass(frozen=True)
class CandidateAttempt:
    """One temporary candidate result, never a public Frame Set member by itself."""

    candidate: GeneratedViewCandidate | None
    measurement: CandidateQualityMeasurement | None
    projected_seed_overlap: float | None
    diagnostic: Mapping[str, object]
    rejection_stage: str | None
    rejection_reason: str | None


class GeneratedViewPolicy:
    """Policy boundary for Seed Region framing and bounded candidate planning."""

    def prepare(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        anchor_frame_set: RegisteredFrameSet,
        anchor_mask_set: Mapping[str, Any],
        renderer: GeneratedViewRenderer,
        resolution: int = GENERATED_VIEW_RESOLUTIONS[0],
    ) -> PreparedGeneratedViews:
        if not _dimension(resolution):
            raise MaskSessionError(
                "renderConfigMismatch",
                "Generated View resolution must be a positive pixel dimension.",
            )
        anchor_frame = _anchor_frame(anchor_frame_set)
        seed_region = derive_seed_region(
            scene_snapshot=scene_snapshot,
            anchor_frame=anchor_frame,
            anchor_mask_set=anchor_mask_set,
            renderer=renderer,
        )
        camera_plan = renderer.plan_views(
            scene_snapshot=scene_snapshot,
            anchor_frame=anchor_frame,
            seed_region=seed_region,
            initial_budget=INITIAL_VIEW_BUDGET,
            replacement_budget=REPLACEMENT_BUDGET,
            resolution=resolution,
        )
        _validate_camera_plan(camera_plan, anchor_frame)
        render_configuration = scene_snapshot.get("renderConfiguration")
        base_render_config_version = (
            render_configuration.get("version")
            if isinstance(render_configuration, Mapping)
            else getattr(renderer, "render_config_version", "generated-view-render-v1")
        )
        return PreparedGeneratedViews(
            seed_region=seed_region,
            frame_set_id=camera_plan.frame_set_id,
            render_config_version=generated_render_config_version(
                str(base_render_config_version), resolution
            ),
            anchor_frame_set=anchor_frame_set,
            primary=camera_plan.primary,
            replacements=camera_plan.replacements,
        )

    def select_incrementally(
        self,
        *,
        prepared: PreparedGeneratedViews,
        scene_snapshot: Mapping[str, Any],
        anchor_mask_set: Mapping[str, Any],
        renderer: GeneratedViewRenderer,
        resolution: int,
        track_prefix: Callable[
            [RegisteredFrameSet],
            tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None],
        ],
        prompt_log: Sequence[Mapping[str, Any]] = (),
    ) -> SelectedGeneratedViews:
        """Render and track one candidate prefix at a time before final replay."""

        anchor = _anchor_frame(prepared.anchor_frame_set)
        anchor_outcome = _primary_frame_outcomes(anchor_mask_set).get(anchor.view_id)
        anchor_valid, _, anchor_measurement = _quality_measurement(
            frame=anchor,
            outcome=anchor_outcome,
            scene_snapshot=scene_snapshot,
            renderer=renderer,
            prompt_log=prompt_log,
        )
        if not anchor_valid or anchor_measurement is None:
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View failed Generated View quality gating; adjust the prompt and retry.",
            )

        stable_ids = set(_scene_means(scene_snapshot))
        accepted_ids = set(anchor_measurement.contributor_ids)
        low_increment_streak = 0
        replacement_by_failed = {
            candidate.replacement_of: candidate
            for candidate in prepared.replacements
        }
        selected = [anchor]
        # The Seed Region is derived from the accepted Anchor mask, making its
        # own overlap the calibrated 1.0 baseline for the first hidden view.
        accepted_neighbors = {
            anchor.view_id: AcceptedNeighbor(
                view_id=anchor.view_id,
                measurement=anchor_measurement,
                projected_seed_overlap=1.0,
            )
        }
        rejected: list[dict[str, object]] = []
        attempted_view_ids = [anchor.view_id]
        diagnostics: dict[str, object] = {
            "policyId": NEIGHBOR_ANOMALY_POLICY_ID,
            "thresholds": dict(NEIGHBOR_ANOMALY_THRESHOLDS),
            "attempts": [],
            "rejections": [],
        }

        def attempt(candidate: PlannedGeneratedViewCandidate) -> CandidateAttempt:
            attempted_view_ids.append(candidate.view_id)
            rendered, preflight = _render_candidate(
                scene_snapshot=scene_snapshot,
                candidate=candidate,
                renderer=renderer,
                seed_region=prepared.seed_region,
                resolution=resolution,
            )
            diagnostic: dict[str, object] = {
                "viewId": candidate.view_id,
                "preflight": preflight,
            }
            if rendered is None:
                result = CandidateAttempt(
                    candidate=None,
                    measurement=None,
                    projected_seed_overlap=None,
                    diagnostic=diagnostic,
                    rejection_stage="preflight",
                    rejection_reason=_preflight_reason(preflight),
                )
                diagnostics["attempts"].append(result.diagnostic)
                return result

            prefix = _temporary_frame_set(prepared, (*selected, rendered.frame))
            tracks, tracking_diagnostics = track_prefix(prefix)
            outcome = _primary_frame_outcomes({"tracks": tracks}).get(
                rendered.frame.view_id
            )
            valid, reason, measurement = _quality_measurement(
                frame=rendered.frame,
                outcome=outcome,
                scene_snapshot=scene_snapshot,
                renderer=renderer,
                prompt_log=prompt_log,
            )
            tracking_confidence = _tracking_confidence(
                tracking_diagnostics, rendered.frame.view_id
            )
            diagnostic["trackingConfidence"] = tracking_confidence
            if not valid or measurement is None:
                result = CandidateAttempt(
                    candidate=None,
                    measurement=None,
                    projected_seed_overlap=None,
                    diagnostic=diagnostic,
                    rejection_stage="structural_quality",
                    rejection_reason=reason,
                )
                diagnostics["attempts"].append(result.diagnostic)
                return result

            neighbor_frame = selected[-1]
            neighbor = accepted_neighbors[neighbor_frame.view_id]
            neighbor_tracking_confidence = _tracking_confidence(
                tracking_diagnostics, neighbor.view_id
            )
            projected_seed_overlap = _projected_seed_overlap(measurement, preflight)
            accepted, reason, neighbor_metrics = _neighbor_anomaly_outcome(
                measurement=measurement,
                neighbor=neighbor,
                projected_seed_overlap=projected_seed_overlap,
                tracking_confidence=tracking_confidence,
                neighbor_tracking_confidence=neighbor_tracking_confidence,
            )
            diagnostic["metrics"] = neighbor_metrics
            if not accepted:
                result = CandidateAttempt(
                    candidate=None,
                    measurement=None,
                    projected_seed_overlap=projected_seed_overlap,
                    diagnostic=diagnostic,
                    rejection_stage="neighbor_anomaly",
                    rejection_reason=reason,
                )
                diagnostics["attempts"].append(result.diagnostic)
                return result

            result = CandidateAttempt(
                candidate=rendered,
                measurement=measurement,
                projected_seed_overlap=projected_seed_overlap,
                diagnostic=diagnostic,
                rejection_stage=None,
                rejection_reason=None,
            )
            diagnostics["attempts"].append(result.diagnostic)
            return result

        def reject(
            candidate: PlannedGeneratedViewCandidate,
            candidate_attempt: CandidateAttempt,
            replacement: PlannedGeneratedViewCandidate | None,
        ) -> None:
            rejection = {
                "viewId": candidate.view_id,
                "stage": candidate_attempt.rejection_stage,
                "reason": candidate_attempt.rejection_reason,
                "replacementOf": candidate.view_id if replacement is not None else None,
            }
            rejected.append(rejection)
            diagnostics["rejections"].append(
                {**rejection, "diagnostic": candidate_attempt.diagnostic}
            )

        def accept(candidate_attempt: CandidateAttempt) -> bool:
            nonlocal low_increment_streak
            assert candidate_attempt.candidate is not None
            assert candidate_attempt.measurement is not None
            assert candidate_attempt.projected_seed_overlap is not None
            incremental = len(
                candidate_attempt.measurement.contributor_ids - accepted_ids
            ) / max(1, len(stable_ids))
            accepted_ids.update(candidate_attempt.measurement.contributor_ids)
            selected.append(candidate_attempt.candidate.frame)
            accepted_neighbors[candidate_attempt.candidate.frame.view_id] = (
                AcceptedNeighbor(
                    view_id=candidate_attempt.candidate.frame.view_id,
                    measurement=candidate_attempt.measurement,
                    projected_seed_overlap=candidate_attempt.projected_seed_overlap,
                )
            )
            low_increment_streak = (
                low_increment_streak + 1 if incremental < 0.02 else 0
            )
            return low_increment_streak >= 3

        stopped_after: str | None = None
        for candidate in prepared.primary:
            candidate_attempt = attempt(candidate)
            if candidate_attempt.candidate is not None:
                if accept(candidate_attempt):
                    stopped_after = candidate.view_id
                    break
                continue
            replacement = replacement_by_failed.get(candidate.view_id)
            reject(candidate, candidate_attempt, replacement)
            if replacement is None:
                continue
            replacement_attempt = attempt(replacement)
            if replacement_attempt.candidate is None:
                reject(replacement, replacement_attempt, None)
                continue
            if accept(replacement_attempt):
                stopped_after = replacement.view_id
                break

        if len(selected) - 1 > INITIAL_VIEW_BUDGET:
            raise MaskSessionError(
                "generatedViewBudgetExceeded",
                "Generated View replacement exceeded the immutable 16-candidate Frame Set budget.",
            )
        if stopped_after is not None:
            diagnostics["earlyStop"] = {
                "afterViewId": stopped_after,
                "lowIncrementStreak": low_increment_streak,
                "minimumIncrementalCoverage": 0.02,
            }
        return SelectedGeneratedViews(
            frame_set=_temporary_frame_set(prepared, selected),
            rejected_views=tuple(rejected),
            attempted_view_ids=tuple(dict.fromkeys(attempted_view_ids)),
            quality_diagnostics=diagnostics,
        )

    def coverage_report(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame_set: RegisteredFrameSet,
        mask_set: Mapping[str, Any],
        renderer: ContributorRenderer,
        render_config_version: str,
        preliminary_rejections: Sequence[Mapping[str, object]] = (),
        attempted_view_ids: Sequence[str] | None = None,
        quality_diagnostics: Mapping[str, object] | None = None,
        prompt_log: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, object]:
        """Report reliable contributor visibility without classifying IDs.

        Full rejection details remain an internal artifact.  The separate
        ``public_coverage_report`` intentionally exposes only user-actionable
        counts and status for the editor UI.
        """

        outcomes = _primary_frame_outcomes(mask_set)
        known_ids = set(_scene_means(scene_snapshot))
        covered: set[int] = set()
        accepted = 0
        rejections = [dict(rejection) for rejection in preliminary_rejections]
        increments: list[dict[str, object]] = []
        accepted_frames: list[RegisteredFrame] = []
        for frame in frame_set.ordered_views:
            valid, reason, contributor_ids = _quality_outcome(
                frame=frame,
                outcome=outcomes.get(frame.view_id),
                scene_snapshot=scene_snapshot,
                renderer=renderer,
                prompt_log=prompt_log,
            )
            if not valid:
                rejections.append(
                    {
                        "viewId": frame.view_id,
                        "stage": "quality_gate",
                        "reason": reason,
                        "replacementOf": None,
                    }
                )
                continue
            new_ids = contributor_ids - covered
            covered.update(contributor_ids)
            accepted += 1
            accepted_frames.append(frame)
            increments.append(
                {
                    "viewId": frame.view_id,
                    "newContributorCount": len(new_ids),
                    "newContributorFraction": len(new_ids) / max(1, len(known_ids)),
                }
            )
        unseen = sorted(known_ids - covered)
        hidden_accepted = sum(frame.source == "generated" for frame in accepted_frames)
        status = (
            "sufficient"
            if hidden_accepted > 0 and not unseen
            else "insufficient_coverage"
        )
        attempted = (
            len(set(attempted_view_ids))
            if attempted_view_ids is not None
            else len(frame_set.ordered_views) + len(preliminary_rejections)
        )
        return {
            "policyId": POLICY_ID,
            "frameSetVersion": frame_set.frame_set_version,
            "renderConfigVersion": render_config_version,
            "attemptedViews": attempted,
            "acceptedViews": accepted,
            "rejectedViews": rejections,
            "coveredContributorIds": sorted(covered),
            "unseenCandidateIds": unseen,
            "incrementalCoverageByView": increments,
            "effectiveAzimuthElevationCoverage": _angular_coverage(accepted_frames),
            "qualityDiagnostics": dict(quality_diagnostics or {}),
            "status": status,
        }

    @staticmethod
    def public_coverage_report(report: Mapping[str, object]) -> dict[str, object]:
        """The beginner-facing contract: no camera, mask, or model diagnostics."""

        rejected = report.get("rejectedViews")
        if not isinstance(rejected, Sequence):
            raise MaskSessionError(
                "invalidCoverageReport", "Coverage Report rejection details are incomplete."
            )
        return {
            "frameSetVersion": report.get("frameSetVersion"),
            "renderConfigVersion": report.get("renderConfigVersion"),
            "attemptedViews": report.get("attemptedViews"),
            "acceptedViews": report.get("acceptedViews"),
            "rejectedViewCount": len(rejected),
            "status": report.get("status"),
        }


def quality_gate_tracks(
    *,
    scene_snapshot: Mapping[str, Any],
    frame_set: RegisteredFrameSet,
    tracks: Sequence[Mapping[str, Any]],
    renderer: ContributorRenderer,
    prompt_log: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], tuple[dict[str, object], ...]]:
    """Turn structurally unsafe primary outcomes into neutral rejections.

    This runs before a Mask Set is published, so a rejected hidden view cannot
    become all-zero negative evidence.  The Anchor remains required: its
    rejection fails the update rather than silently changing the prompt's
    semantic frame.
    """

    gated = copy.deepcopy(list(tracks))
    primary = next(
        (
            track
            for track in gated
            if isinstance(track, dict)
            and track.get("trackId") == "primary"
            and track.get("role") == "include"
        ),
        None,
    )
    if primary is None or not isinstance(primary.get("frames"), list):
        raise MaskSessionError(
            "incompleteMaskSet", "Generated View quality gating needs a primary include Mask Track."
        )
    if len(primary["frames"]) != len(frame_set.ordered_views):
        raise MaskSessionError(
            "incompleteMaskSet", "Generated View quality gating received an incomplete Frame Set."
        )
    rejections: list[dict[str, object]] = []
    for index, frame in enumerate(frame_set.ordered_views):
        outcome = primary["frames"][index]
        if not isinstance(outcome, dict):
            raise MaskSessionError(
                "incompleteMaskSet", "Generated View quality gating received an invalid frame outcome."
            )
        valid, reason, _ = _quality_outcome(
            frame=frame,
            outcome=outcome,
            scene_snapshot=scene_snapshot,
            renderer=renderer,
            prompt_log=prompt_log,
        )
        if valid:
            continue
        if frame.source == "anchor":
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View failed quality gating; adjust the point prompt and retry.",
            )
        if outcome.get("status") == "accepted":
            primary["frames"][index] = {
                "viewId": frame.view_id,
                "status": "rejected",
                "rejectionReason": reason,
            }
        rejections.append(
            {
                "viewId": frame.view_id,
                "stage": "quality_gate",
                "reason": reason,
                "replacementOf": None,
            }
        )
    return gated, tuple(rejections)


def frame_set_payload(frame_set: RegisteredFrameSet) -> dict[str, object]:
    """Serialize one service-owned immutable Frame Set for cache registration."""

    return {
        "frameSetId": frame_set.frame_set_id,
        "frameSetVersion": frame_set.frame_set_version,
        "orderedViews": [_frame_payload(frame) for frame in frame_set.ordered_views],
    }


def public_frame_set_payload(frame_set: RegisteredFrameSet) -> dict[str, object]:
    """Return Frame Set bindings without hidden service-rendered image data."""

    return {
        "frameSetId": frame_set.frame_set_id,
        "frameSetVersion": frame_set.frame_set_version,
        "orderedViews": [
            {
                "viewId": frame.view_id,
                "frameDigest": frame.frame_digest,
                "width": frame.width,
                "height": frame.height,
            }
            for frame in frame_set.ordered_views
        ],
    }


def derive_seed_region(
    *,
    scene_snapshot: Mapping[str, Any],
    anchor_frame: RegisteredFrame,
    anchor_mask_set: Mapping[str, Any],
    renderer: ContributorRenderer,
) -> SeedRegion:
    """Estimate a robust Seed Region from accepted Anchor contributors.

    Contributors outside the accepted Anchor mask never enter the region.  If
    there are no usable contributors, an explicit prompt-ray fallback carried
    with the Anchor metadata is used; otherwise planning fails safely.
    """

    mask = _accepted_primary_mask(anchor_mask_set, anchor_frame.view_id)
    rendered = renderer.render(scene_snapshot=scene_snapshot, frame=anchor_frame)
    means = _scene_means(scene_snapshot)
    _validate_anchor_render(rendered, anchor_frame, tuple(means))
    weighted: list[tuple[int, tuple[float, float, float], float]] = []
    for contribution in rendered.contributors:
        if (
            contribution.stable_id in means
            and _finite_positive(contribution.mass)
            and mask.contains(contribution.x_px, contribution.y_px)
        ):
            weighted.append(
                (contribution.stable_id, means[contribution.stable_id], contribution.mass)
            )
    if weighted:
        return _contributor_seed_region(weighted)
    return _prompt_ray_fallback(anchor_frame)


@dataclass(frozen=True)
class _BinaryMask:
    width: int
    height: int
    sparse_pixels: frozenset[tuple[int, int]] | None = None
    bitset: bytes | None = None

    def contains(self, x_px: int, y_px: int) -> bool:
        if not (0 <= x_px < self.width and 0 <= y_px < self.height):
            return False
        if self.sparse_pixels is not None:
            return (x_px, y_px) in self.sparse_pixels
        if self.bitset is None:
            return False
        index = y_px * self.width + x_px
        return (self.bitset[index // 8] & (1 << (index % 8))) != 0

    @property
    def pixel_count(self) -> int:
        if self.sparse_pixels is not None:
            return len(self.sparse_pixels)
        return sum(byte.bit_count() for byte in self.bitset or b"")


def _accepted_primary_mask(mask_set: Mapping[str, Any], view_id: str) -> _BinaryMask:
    tracks = mask_set.get("tracks")
    if not isinstance(tracks, Sequence):
        raise MaskSessionError("invalidSeedRegion", "The Anchor Mask Set has no Mask Tracks.")
    for track in tracks:
        if not isinstance(track, Mapping) or track.get("trackId") != "primary":
            continue
        if track.get("role") != "include" or not isinstance(track.get("frames"), Sequence):
            break
        for frame in track["frames"]:
            if not isinstance(frame, Mapping) or frame.get("viewId") != view_id:
                continue
            if frame.get("status") != "accepted":
                break
            return _decode_mask(frame.get("binaryMask"))
    raise MaskSessionError(
        "anchorMaskUnavailable",
        "The Anchor View needs an accepted Mask Set before Generated Views can be planned.",
    )


def _decode_mask(value: object) -> _BinaryMask:
    if not isinstance(value, Mapping):
        raise MaskSessionError("invalidSeedRegion", "The Anchor mask is missing binary pixels.")
    width = value.get("width")
    height = value.get("height")
    if not _dimension(width) or not _dimension(height):
        raise MaskSessionError("invalidSeedRegion", "The Anchor mask dimensions are invalid.")
    if value.get("encoding") == "sparse-points-v1":
        pixels = value.get("foregroundPixels")
        if not isinstance(pixels, Sequence):
            raise MaskSessionError("invalidSeedRegion", "The Anchor sparse mask has no pixels.")
        parsed: set[tuple[int, int]] = set()
        for pixel in pixels:
            if (
                not isinstance(pixel, Sequence)
                or len(pixel) != 2
                or not _integer(pixel[0])
                or not _integer(pixel[1])
                or not (0 <= pixel[0] < width and 0 <= pixel[1] < height)
            ):
                raise MaskSessionError("invalidSeedRegion", "The Anchor sparse mask has an invalid pixel.")
            parsed.add((pixel[0], pixel[1]))
        if not parsed:
            raise MaskSessionError("invalidSeedRegion", "The Anchor sparse mask has no pixels.")
        return _BinaryMask(width=width, height=height, sparse_pixels=frozenset(parsed))
    if value.get("encoding") == "bitset-lsb-v1" and isinstance(value.get("data"), str):
        try:
            data = base64.b64decode(value["data"], validate=True)
        except ValueError as error:
            raise MaskSessionError("invalidSeedRegion", "The Anchor bitset mask is invalid.") from error
        if len(data) != math.ceil(width * height / 8):
            raise MaskSessionError("invalidSeedRegion", "The Anchor bitset mask has invalid dimensions.")
        return _BinaryMask(width=width, height=height, bitset=data)
    raise MaskSessionError("invalidSeedRegion", "The Anchor mask uses an unsupported encoding.")


def _contributor_seed_region(
    weighted: Sequence[tuple[int, tuple[float, float, float], float]],
) -> SeedRegion:
    # A point selected through the Anchor mask can still be a background
    # contributor through a transparent/overlapping splat. Start with a
    # mass-weighted coordinate median, discard only clearly separated support,
    # then compute the framing center from the retained contributor region.
    provisional_center = tuple(
        _weighted_median(
            [(point[axis], mass) for _, point, mass in weighted]
        )
        for axis in range(3)
    )
    provisional_distances = [
        math.dist(point, provisional_center)
        for _, point, _ in weighted
    ]
    robust_distance = _weighted_median(
        [
            (distance, mass)
            for distance, (_, _, mass) in zip(provisional_distances, weighted, strict=True)
        ]
    )
    # A conservative floor preserves the single-Gaussian framing case. A
    # broad, coherently observed object keeps all of its support because its
    # weighted median distance scales with the object rather than one outlier.
    outlier_limit = max(0.05, robust_distance * 3.0)
    retained = [
        item
        for item, distance in zip(weighted, provisional_distances, strict=True)
        if distance <= outlier_limit
    ]
    if not retained:
        retained = list(weighted)
    total_mass = sum(mass for _, _, mass in retained)
    center = tuple(
        sum(point[axis] * mass for _, point, mass in retained) / total_mass
        for axis in range(3)
    )
    distances = [
        math.dist(point, center)
        for _, point, _ in retained
    ]
    # The contributor cloud can collapse to one Gaussian. Keep a conservative
    # radius so generated cameras do not frame an individual splat as an object.
    radius = max(0.05, _median(distances) * 2.5)
    return SeedRegion(
        center=(float(center[0]), float(center[1]), float(center[2])),
        radius=radius,
        source="anchor_contributors",
        stable_ids=tuple(sorted({stable_id for stable_id, _, _ in retained})),
    )


def _prompt_ray_fallback(anchor_frame: RegisteredFrame) -> SeedRegion:
    camera = anchor_frame.camera
    if not isinstance(camera, Mapping):
        raise MaskSessionError(
            "seedUnavailable",
            "The Anchor has no contributor seed or prompt-ray fallback for Generated View framing.",
        )
    origin = _vector(camera.get("rayOrigin"))
    direction = _vector(camera.get("rayDirection"))
    distance = camera.get("seedDistance")
    if origin is None or direction is None or not _finite_positive(distance):
        raise MaskSessionError(
            "seedUnavailable",
            "The Anchor prompt-ray fallback is incomplete for Generated View framing.",
        )
    length = math.sqrt(sum(value * value for value in direction))
    if length <= 1e-12:
        raise MaskSessionError(
            "seedUnavailable",
            "The Anchor prompt ray has no usable direction for Generated View framing.",
        )
    center = tuple(origin[index] + direction[index] * distance / length for index in range(3))
    return SeedRegion(
        center=(float(center[0]), float(center[1]), float(center[2])),
        radius=max(0.05, float(camera.get("minimumSeedRadius", 0.1))),
        source="prompt_ray_fallback",
        stable_ids=(),
    )


def _anchor_frame(frame_set: RegisteredFrameSet) -> RegisteredFrame:
    anchors = [frame for frame in frame_set.ordered_views if frame.source == "anchor"]
    if len(anchors) == 1:
        return anchors[0]
    if len(frame_set.ordered_views) == 1:
        return frame_set.ordered_views[0]
    raise MaskSessionError(
        "invalidFrameSet", "Generated View planning needs exactly one Anchor View.")


def _validate_anchor_render(
    rendered: RenderedContributorView,
    frame: RegisteredFrame,
    stable_ids: Sequence[int],
) -> None:
    """Preserve the planning-stage error context around shared evidence checks."""

    try:
        validate_rendered_view(rendered, frame, stable_ids)
    except MaskSessionError as error:
        raise MaskSessionError("anchorParityFailure", str(error)) from error


def _scene_means(scene_snapshot: Mapping[str, Any]) -> dict[int, tuple[float, float, float]]:
    gaussians = scene_snapshot.get("gaussians")
    if not isinstance(gaussians, Sequence):
        raise MaskSessionError("invalidSeedRegion", "The Scene Snapshot has no Gaussian means.")
    result: dict[int, tuple[float, float, float]] = {}
    for gaussian in gaussians:
        if not isinstance(gaussian, Mapping) or not _integer(gaussian.get("stableId")):
            raise MaskSessionError("invalidSeedRegion", "The Scene Snapshot has an invalid Stable Gaussian ID.")
        mean = _vector(gaussian.get("mean"))
        if mean is None:
            raise MaskSessionError("invalidSeedRegion", "The Scene Snapshot has an invalid Gaussian mean.")
        result[gaussian["stableId"]] = mean
    return result


def _validate_camera_plan(
    plan: GeneratedViewCameraPlan, anchor_frame: RegisteredFrame
) -> None:
    if not isinstance(plan, GeneratedViewCameraPlan) or not plan.frame_set_id:
        raise MaskSessionError(
            "invalidGeneratedViews",
            "The Generated View planner did not return a bounded camera plan.",
        )
    if len(plan.primary) > INITIAL_VIEW_BUDGET:
        raise MaskSessionError(
            "generatedViewBudgetExceeded",
            "The Generated View camera plan exceeds the initial 16-candidate budget.",
        )
    if len(plan.replacements) > REPLACEMENT_BUDGET:
        raise MaskSessionError(
            "generatedViewBudgetExceeded",
            "The Generated View camera plan exceeds the eight replacement budget.",
        )
    if len(plan.primary) + len(plan.replacements) > TOTAL_VIEW_BUDGET:
        raise MaskSessionError(
            "generatedViewBudgetExceeded",
            "The Generated View camera plan exceeds the 24-view total budget.",
        )
    seen = {anchor_frame.view_id}
    primary_ids: set[str] = set()
    replacement_targets: set[str] = set()
    for candidate in plan.primary:
        if (
            not isinstance(candidate, PlannedGeneratedViewCandidate)
            or candidate.category not in {"ring", "upper"}
            or not candidate.view_id
            or candidate.view_id in seen
            or not _finite_json(candidate.camera)
        ):
            raise MaskSessionError(
                "invalidGeneratedViews",
                "A primary Generated View camera candidate is invalid.",
            )
        seen.add(candidate.view_id)
        primary_ids.add(candidate.view_id)
    for candidate in plan.replacements:
        if (
            not isinstance(candidate, PlannedGeneratedViewCandidate)
            or candidate.category != "replacement"
            or not candidate.replacement_of
            or candidate.replacement_of not in primary_ids
            or candidate.replacement_of in replacement_targets
            or not candidate.view_id
            or candidate.view_id in seen
            or not _finite_json(candidate.camera)
        ):
            raise MaskSessionError(
                "invalidGeneratedViews",
                "A replacement Generated View camera candidate is invalid.",
            )
        seen.add(candidate.view_id)
        replacement_targets.add(candidate.replacement_of)


def _validate_preflight(
    outcome: CameraPreflightResult, candidate: PlannedGeneratedViewCandidate
) -> None:
    if (
        not isinstance(outcome, CameraPreflightResult)
        or not isinstance(outcome.accepted, bool)
        or not _finite_json(outcome.diagnostics)
        or (outcome.accepted and not _finite_json(outcome.camera))
        or (outcome.accepted and outcome.camera is None)
    ):
        raise MaskSessionError(
            "invalidGeneratedViews",
            f"Generated View preflight returned an invalid outcome for {candidate.view_id}.",
        )


def _validate_rendered_candidate(
    frame: RegisteredFrame,
    candidate: PlannedGeneratedViewCandidate,
    resolution: int,
) -> None:
    if (
        not isinstance(frame, RegisteredFrame)
        or frame.view_id != candidate.view_id
        or frame.source != "generated"
        or frame.width != resolution
        or frame.height != resolution
        or frame.image_png is None
        or _digest(frame.image_png) != frame.frame_digest
    ):
        raise MaskSessionError(
            "invalidGeneratedViews",
            "Generated RGB is not an immutable frame at the active render resolution.",
        )


def _temporary_frame_set(
    prepared: PreparedGeneratedViews,
    ordered_views: Sequence[RegisteredFrame],
) -> RegisteredFrameSet:
    """Build an internal prefix identity without registering or publishing it."""

    ordered = tuple(ordered_views)
    if ordered == prepared.anchor_frame_set.ordered_views:
        return prepared.anchor_frame_set
    canonical = json.dumps(
        {
            "policy": POLICY_ID,
            "anchorVersion": prepared.anchor_frame_set.frame_set_version,
            "frameSetId": prepared.frame_set_id,
            "renderConfigVersion": prepared.render_config_version,
            "views": [
                {
                    "viewId": frame.view_id,
                    "frameDigest": frame.frame_digest,
                    "width": frame.width,
                    "height": frame.height,
                }
                for frame in ordered
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    version = (
        f"{prepared.anchor_frame_set.frame_set_version}:generated:"
        f"{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
    )
    payload = {
        "frameSetId": prepared.frame_set_id,
        "frameSetVersion": version,
        "orderedViews": [_frame_payload(frame) for frame in ordered],
    }
    return RegisteredFrameSet(
        canonical=json.dumps(payload, separators=(",", ":"), sort_keys=True),
        frame_set_id=prepared.frame_set_id,
        frame_set_version=version,
        ordered_views=ordered,
    )


def _render_candidate(
    *,
    scene_snapshot: Mapping[str, Any],
    candidate: PlannedGeneratedViewCandidate,
    renderer: GeneratedViewRenderer,
    seed_region: SeedRegion,
    resolution: int,
) -> tuple[GeneratedViewCandidate | None, Mapping[str, object]]:
    outcome = renderer.preflight(
        scene_snapshot=scene_snapshot,
        candidate=candidate,
        seed_region=seed_region,
        resolution=resolution,
    )
    _validate_preflight(outcome, candidate)
    diagnostics: dict[str, object] = {
        "accepted": outcome.accepted,
        **dict(outcome.diagnostics),
    }
    if not outcome.accepted:
        return None, diagnostics
    frame = renderer.render_generated(
        scene_snapshot=scene_snapshot,
        candidate=candidate,
        preflight=outcome,
        resolution=resolution,
    )
    _validate_rendered_candidate(frame, candidate, resolution)
    return (
        GeneratedViewCandidate(
            frame=frame,
            category=candidate.category,
            azimuth_degrees=candidate.azimuth_degrees,
            elevation_degrees=candidate.elevation_degrees,
            replacement_of=candidate.replacement_of,
        ),
        diagnostics,
    )


def _preflight_reason(preflight: Mapping[str, object]) -> str:
    reason = preflight.get("reason")
    return (
        reason
        if isinstance(reason, str) and reason.strip()
        else "The Generated View camera did not pass preflight."
    )


def _tracking_confidence(
    diagnostics: Mapping[str, Any] | None, view_id: str
) -> float | None:
    if not isinstance(diagnostics, Mapping):
        return None
    confidences = diagnostics.get("trackingConfidenceByView")
    if not isinstance(confidences, Mapping):
        return None
    value = confidences.get(view_id)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        return None
    return float(value)


def _mask_bounds(mask: _BinaryMask) -> tuple[int, int, int, int]:
    if mask.sparse_pixels is not None:
        xs, ys = zip(*mask.sparse_pixels, strict=True)
        return min(xs), min(ys), max(xs), max(ys)
    xs: list[int] = []
    ys: list[int] = []
    for y_px in range(mask.height):
        for x_px in range(mask.width):
            if mask.contains(x_px, y_px):
                xs.append(x_px)
                ys.append(y_px)
    if not xs:
        raise MaskSessionError("invalidCoverageReport", "The mask has no foreground bounds.")
    return min(xs), min(ys), max(xs), max(ys)


def _quality_measurement(
    *,
    frame: RegisteredFrame,
    outcome: Mapping[str, Any] | None,
    scene_snapshot: Mapping[str, Any],
    renderer: ContributorRenderer,
    prompt_log: Sequence[Mapping[str, Any]] = (),
) -> tuple[bool, str, CandidateQualityMeasurement | None]:
    if outcome is None:
        return False, "The view was not present in the complete Mask Set.", None
    if outcome.get("status") != "accepted":
        reason = outcome.get("rejectionReason")
        return (
            False,
            reason
            if isinstance(reason, str) and reason.strip()
            else "The mask adapter did not accept this view.",
            None,
        )
    try:
        mask = _decode_mask(outcome.get("binaryMask"))
    except MaskSessionError as error:
        return False, str(error), None
    if mask.width != frame.width or mask.height != frame.height:
        return False, "The accepted mask dimensions do not match its immutable frame.", None
    if mask.pixel_count == 0:
        return False, "The accepted mask has no foreground pixels.", None
    if mask.pixel_count / (frame.width * frame.height) >= 0.95:
        return False, "The accepted mask covers nearly the whole generated frame.", None
    prompt_reason = _prompt_mask_reason(mask, frame, prompt_log)
    if prompt_reason is not None:
        return False, prompt_reason, None
    try:
        rendered = renderer.render(scene_snapshot=scene_snapshot, frame=frame)
        known_ids = set(_scene_means(scene_snapshot))
        validate_rendered_view(rendered, frame, tuple(known_ids))
    except (MaskSessionError, ValueError) as error:
        return False, str(error), None
    contributor_ids: set[int] = set()
    contributor_under_mask = False
    for contribution in rendered.contributors:
        if (
            not _integer(contribution.stable_id)
            or contribution.stable_id not in known_ids
        ):
            return False, "The Contributor renderer returned invalid view support.", None
        contributor_ids.add(contribution.stable_id)
        contributor_under_mask = contributor_under_mask or mask.contains(
            contribution.x_px, contribution.y_px
        )
    if not contributor_ids:
        return False, "The view has no contributor support.", None
    if not contributor_under_mask:
        return False, "The accepted mask has no contributor support beneath it.", None
    left, top, right, bottom = _mask_bounds(mask)
    width = right - left + 1
    height = bottom - top + 1
    return (
        True,
        "",
        CandidateQualityMeasurement(
            contributor_ids=frozenset(contributor_ids),
            frame_width=frame.width,
            frame_height=frame.height,
            mask_area_fraction=mask.pixel_count / (frame.width * frame.height),
            extent_fraction=math.hypot(width / frame.width, height / frame.height),
            bounding_width_fraction=width / frame.width,
            bounding_height_fraction=height / frame.height,
            center_x_fraction=(left + right + 1) / (2 * frame.width),
            center_y_fraction=(top + bottom + 1) / (2 * frame.height),
        ),
    )


def _projected_seed_overlap(
    measurement: CandidateQualityMeasurement,
    preflight: Mapping[str, object],
) -> float | None:
    attempts = preflight.get("attempts")
    if not isinstance(attempts, Sequence):
        return None
    projected: Mapping[str, object] | None = None
    for attempt in reversed(attempts):
        if isinstance(attempt, Mapping):
            projected = attempt
            break
    if projected is None:
        return None
    center_x = projected.get("projectedCenterX")
    center_y = projected.get("projectedCenterY")
    radius = projected.get("projectedRadius")
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in (center_x, center_y, radius)
    ):
        return None
    left = measurement.center_x_fraction - measurement.bounding_width_fraction / 2
    right = measurement.center_x_fraction + measurement.bounding_width_fraction / 2
    top = measurement.center_y_fraction - measurement.bounding_height_fraction / 2
    bottom = measurement.center_y_fraction + measurement.bounding_height_fraction / 2
    seed_left = (float(center_x) - float(radius)) / measurement.frame_width
    seed_right = (float(center_x) + float(radius)) / measurement.frame_width
    seed_top = (float(center_y) - float(radius)) / measurement.frame_height
    seed_bottom = (float(center_y) + float(radius)) / measurement.frame_height
    intersection = max(0.0, min(right, seed_right) - max(left, seed_left)) * max(
        0.0, min(bottom, seed_bottom) - max(top, seed_top)
    )
    area = max(1e-12, (right - left) * (bottom - top))
    return min(1.0, intersection / area)


def _neighbor_anomaly_outcome(
    *,
    measurement: CandidateQualityMeasurement,
    neighbor: AcceptedNeighbor,
    projected_seed_overlap: float | None,
    tracking_confidence: float | None,
    neighbor_tracking_confidence: float | None,
) -> tuple[bool, str, dict[str, object]]:
    metrics: dict[str, object] = {
        "maskAreaFraction": measurement.mask_area_fraction,
        "boundingExtentFraction": measurement.extent_fraction,
        "center": [measurement.center_x_fraction, measurement.center_y_fraction],
        "projectedSeedRegionOverlap": projected_seed_overlap,
        "contributorSupportCount": len(measurement.contributor_ids),
        "trackingConfidence": tracking_confidence,
        "acceptedNeighborViewId": neighbor.view_id,
        "acceptedNeighborProjectedSeedRegionOverlap": neighbor.projected_seed_overlap,
        "acceptedNeighborTrackingConfidence": neighbor_tracking_confidence,
        "acceptedNeighborCount": 1,
    }
    if projected_seed_overlap is None:
        return False, "projected_seed_overlap_unavailable", metrics
    overlap_ratio = projected_seed_overlap / max(neighbor.projected_seed_overlap, 1e-12)
    metrics["projectedSeedRegionOverlapRatio"] = overlap_ratio
    if projected_seed_overlap < NEIGHBOR_ANOMALY_THRESHOLDS["minimumProjectedSeedOverlap"]:
        return False, "projected_seed_overlap", metrics
    if not (
        NEIGHBOR_ANOMALY_THRESHOLDS["minimumProjectedSeedOverlapRatio"]
        <= overlap_ratio
        <= NEIGHBOR_ANOMALY_THRESHOLDS["maximumProjectedSeedOverlapRatio"]
    ):
        return False, "projected_seed_overlap_neighbor", metrics
    if tracking_confidence is None or neighbor_tracking_confidence is None:
        return False, "tracking_confidence_unavailable", metrics

    area_ratio = measurement.mask_area_fraction / max(
        neighbor.measurement.mask_area_fraction, 1e-12
    )
    extent_ratio = measurement.extent_fraction / max(
        neighbor.measurement.extent_fraction, 1e-12
    )
    center_displacement = math.dist(
        (measurement.center_x_fraction, measurement.center_y_fraction),
        (
            neighbor.measurement.center_x_fraction,
            neighbor.measurement.center_y_fraction,
        ),
    )
    contributor_ratio = len(measurement.contributor_ids) / max(
        len(neighbor.measurement.contributor_ids), 1.0
    )
    metrics.update(
        areaRatio=area_ratio,
        extentRatio=extent_ratio,
        centerDisplacement=center_displacement,
        contributorCountRatio=contributor_ratio,
    )
    if not (
        NEIGHBOR_ANOMALY_THRESHOLDS["minimumAreaRatio"]
        <= area_ratio
        <= NEIGHBOR_ANOMALY_THRESHOLDS["maximumAreaRatio"]
    ):
        return False, "mask_area", metrics
    if not (
        NEIGHBOR_ANOMALY_THRESHOLDS["minimumExtentRatio"]
        <= extent_ratio
        <= NEIGHBOR_ANOMALY_THRESHOLDS["maximumExtentRatio"]
    ):
        return False, "bounding_extent", metrics
    if center_displacement > NEIGHBOR_ANOMALY_THRESHOLDS["maximumCenterDisplacement"]:
        return False, "center_displacement", metrics
    if not (
        NEIGHBOR_ANOMALY_THRESHOLDS["minimumContributorCountRatio"]
        <= contributor_ratio
        <= NEIGHBOR_ANOMALY_THRESHOLDS["maximumContributorCountRatio"]
    ):
        return False, "contributor_support", metrics
    confidence_ratio = tracking_confidence / max(neighbor_tracking_confidence, 1e-12)
    metrics["trackingConfidenceRatio"] = confidence_ratio
    if confidence_ratio < NEIGHBOR_ANOMALY_THRESHOLDS[
        "minimumTrackingConfidenceRatio"
    ]:
        return False, "tracking_confidence", metrics
    return True, "", metrics


def _primary_frame_outcomes(mask_set: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    tracks = mask_set.get("tracks")
    if not isinstance(tracks, Sequence):
        raise MaskSessionError("invalidCoverageReport", "The Mask Set has no primary Mask Track.")
    for track in tracks:
        if (
            isinstance(track, Mapping)
            and track.get("trackId") == "primary"
            and track.get("role") == "include"
            and isinstance(track.get("frames"), Sequence)
        ):
            return {
                frame["viewId"]: frame
                for frame in track["frames"]
                if isinstance(frame, Mapping) and isinstance(frame.get("viewId"), str)
            }
    raise MaskSessionError("invalidCoverageReport", "The Mask Set has no primary include Mask Track.")


def _quality_outcome(
    *,
    frame: RegisteredFrame,
    outcome: Mapping[str, Any] | None,
    scene_snapshot: Mapping[str, Any],
    renderer: ContributorRenderer,
    prompt_log: Sequence[Mapping[str, Any]] = (),
) -> tuple[bool, str, set[int]]:
    valid, reason, measurement = _quality_measurement(
        frame=frame,
        outcome=outcome,
        scene_snapshot=scene_snapshot,
        renderer=renderer,
        prompt_log=prompt_log,
    )
    return (
        valid,
        reason,
        set(measurement.contributor_ids) if measurement is not None else set(),
    )


def _prompt_mask_reason(
    mask: _BinaryMask,
    frame: RegisteredFrame,
    prompt_log: Sequence[Mapping[str, Any]],
) -> str | None:
    """Reject masks that contradict an explicit point on this frame.

    Prompt semantics remain owned by the mask adapter. This gate only checks
    the two universally safe invariants: an include point must stay inside its
    accepted primary mask and an exclude point must stay outside it.
    """

    for entry in prompt_log:
        if not isinstance(entry, Mapping):
            continue
        prompt = entry.get("prompt")
        if not isinstance(prompt, Mapping) or prompt.get("viewId") != frame.view_id:
            continue
        x_px = prompt.get("xPx")
        y_px = prompt.get("yPx")
        polarity = prompt.get("polarity")
        if not _integer(x_px) or not _integer(y_px):
            return "The point prompt coordinates are invalid for this accepted mask."
        if not (0 <= x_px < frame.width and 0 <= y_px < frame.height):
            return "The point prompt lies outside its immutable frame."
        if polarity == "include" and not mask.contains(x_px, y_px):
            return "The accepted mask excludes an include point prompt."
        if polarity == "exclude" and mask.contains(x_px, y_px):
            return "The accepted mask includes an exclude point prompt."
    return None


def _angular_coverage(frames: Sequence[RegisteredFrame]) -> dict[str, object]:
    azimuths: list[float] = []
    elevations: list[float] = []
    for frame in frames:
        if not isinstance(frame.camera, Mapping):
            continue
        azimuth = frame.camera.get("azimuthDegrees")
        elevation = frame.camera.get("elevationDegrees")
        if isinstance(azimuth, (int, float)) and math.isfinite(azimuth):
            azimuths.append(float(azimuth) % 360.0)
        if isinstance(elevation, (int, float)) and math.isfinite(elevation):
            elevations.append(float(elevation))
    return {
        "azimuthDegreesInFrameOrder": azimuths,
        "elevationDegreesInFrameOrder": elevations,
        "circularAzimuthSpanDegrees": _circular_span(azimuths),
        "minimumElevationDegrees": min(elevations) if elevations else None,
        "maximumElevationDegrees": max(elevations) if elevations else None,
    }


def _circular_span(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    ordered = sorted(values)
    gaps = [
        right - left
        for left, right in zip(ordered, (*ordered[1:], ordered[0] + 360.0), strict=True)
    ]
    return 360.0 - max(gaps)


def _frame_payload(frame: RegisteredFrame) -> dict[str, object]:
    payload: dict[str, object] = {
        "viewId": frame.view_id,
        "frameDigest": frame.frame_digest,
        "width": frame.width,
        "height": frame.height,
        "source": frame.source,
    }
    if frame.image_png is not None:
        payload["imagePngBase64"] = base64.b64encode(frame.image_png).decode("ascii")
    if frame.camera is not None:
        payload["camera"] = dict(frame.camera)
    return payload


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _dimension(value: object) -> bool:
    return _integer(value) and value > 0


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _finite_positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _finite_json(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return True
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _finite_json(item) for key, item in value.items())
    if isinstance(value, Sequence):
        return all(_finite_json(item) for item in value)
    return False


def _vector(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, Sequence) or len(value) != 3:
        return None
    values = tuple(float(item) for item in value if isinstance(item, (int, float)) and not isinstance(item, bool))
    if len(values) != 3 or not all(math.isfinite(item) for item in values):
        return None
    return values[0], values[1], values[2]


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _weighted_median(values: Sequence[tuple[float, float]]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values, key=lambda value: value[0])
    total = sum(weight for _, weight in ordered)
    midpoint = total / 2.0
    accumulated = 0.0
    for index, (value, weight) in enumerate(ordered):
        accumulated += weight
        if accumulated > midpoint:
            return value
        if accumulated == midpoint and index + 1 < len(ordered):
            return (value + ordered[index + 1][0]) / 2.0
    return ordered[-1][0]

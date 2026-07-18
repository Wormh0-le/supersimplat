"""Same-renderer contributor evidence for Candidate Object Selection previews.

The renderer boundary is deliberately narrow: it returns the contributor mass
from the exact RGB frame it rendered, while this module owns only immutable
Mask Set composition and Evidence Policy v1.  It never accepts editor-owned
Gaussian selection state or benchmark Ground Truth.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
import math
from typing import Any, Literal, Mapping, Protocol, Sequence

from .masking import MaskSessionError, RegisteredFrame, RegisteredFrameSet


POLICY_ID = "selection-evidence-policy/v1"
CONTRIBUTOR_SEMANTICS = "alpha-times-transmittance/v1"
EVIDENCE_SCALE = "contributor-mass/v1"
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0
MINIMUM_EFFECTIVE_OBSERVATION = 0.10
SELECTED_POSTERIOR_THRESHOLD = 0.80
REJECTED_POSTERIOR_THRESHOLD = 0.20

AnchorParity = Literal["normal", "moderate", "severe"]


@dataclass(frozen=True)
class ContributorSample:
    """One positive alpha-times-transmittance mass at one rendered pixel."""

    stable_id: int
    x_px: int
    y_px: int
    mass: float


@dataclass(frozen=True)
class RenderedContributorView:
    """The RGB identity and bounded contributor support from one rasterization."""

    view_id: str
    rgb_frame_digest: str
    width: int
    height: int
    support_bounds: tuple[int, int, int, int]
    contributors: tuple[ContributorSample, ...]
    # Internal same-rasterization diagnostics. The public Evidence Snapshot
    # continues to bind the editor-owned frame digest above.
    service_rgb_digest: str | None = None
    mass_conservation_max_error: float = 0.0
    # The service computes this only for the editor-owned Anchor camera. A
    # moderate appearance difference preserves positive support but makes
    # outside-mask samples neutral; a severe geometry/projection difference
    # fails before the editor's mask can be mapped to Stable Gaussian IDs.
    anchor_parity: AnchorParity = "normal"


class ContributorRenderer(Protocol):
    """The service-owned same-renderer RGB/contributor boundary."""

    renderer_id: str

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
        """Render the frame and return only its bounded contributor support."""


@dataclass
class StaticContributorRenderer:
    """A deterministic contributor fixture for service-contract tests only."""

    views: Mapping[str, RenderedContributorView]
    renderer_id: str = "gsplat"
    rendered_view_ids: list[str] = field(default_factory=list, init=False)

    def render(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        frame: RegisteredFrame,
    ) -> RenderedContributorView:
        del scene_snapshot
        self.rendered_view_ids.append(frame.view_id)
        try:
            return self.views[frame.view_id]
        except KeyError as error:
            raise MaskSessionError(
                "rendererUnavailable",
                "The Contributor renderer has no rendered Anchor View for this Frame Set.",
            ) from error


@dataclass(frozen=True)
class _BinaryMask:
    width: int
    height: int
    sparse_pixels: frozenset[tuple[int, int]] | None = None
    bitset: bytes | None = None

    def contains(self, x_px: int, y_px: int) -> bool:
        if self.sparse_pixels is not None:
            return (x_px, y_px) in self.sparse_pixels
        if self.bitset is None:
            return False
        index = y_px * self.width + x_px
        return (self.bitset[index // 8] & (1 << (index % 8))) != 0


@dataclass(frozen=True)
class _CompositeMask:
    # Chronological independent Mask Track claims in Mask Set order. The
    # latest track claiming a pixel decides it, so a later Add restores a
    # region an earlier Remove excluded and a later Remove excludes it again.
    claims: tuple[tuple[Literal["include", "exclude"], _BinaryMask], ...]

    def contains(self, x_px: int, y_px: int) -> bool:
        decision: str | None = None
        for role, mask in self.claims:
            if mask.contains(x_px, y_px):
                decision = role
        return decision == "include"


def evidence_policy(render_config_version: str) -> dict[str, object]:
    """Return the immutable calibration unit for Evidence Policy v1."""

    return {
        "id": POLICY_ID,
        "renderConfigVersion": render_config_version,
        "contributorSemantics": CONTRIBUTOR_SEMANTICS,
        "evidenceScale": EVIDENCE_SCALE,
        "betaPrior": {"alpha": 1, "beta": 1},
        "minimumEffectiveObservation": MINIMUM_EFFECTIVE_OBSERVATION,
        "selectedPosteriorThreshold": SELECTED_POSTERIOR_THRESHOLD,
        "rejectedPosteriorThreshold": REJECTED_POSTERIOR_THRESHOLD,
    }


def build_evidence_snapshot(
    *,
    bindings: Mapping[str, object],
    scene_snapshot: Mapping[str, Any],
    frame_set: RegisteredFrameSet,
    mask_set: Mapping[str, Any],
    renderer: ContributorRenderer,
) -> dict[str, object]:
    """Compute one complete, replayable Evidence Snapshot from a Mask Set.

    Only samples returned by a quality-accepted rendered view are accumulated.
    A Gaussian that has no returned contributor sample remains unobserved even
    if it exists in the Scene Snapshot or lies near a mask boundary.
    """

    render_config_version = _binding_string(bindings, "renderConfigVersion")
    stable_ids = _scene_stable_ids(scene_snapshot)
    positive = {stable_id: 0.0 for stable_id in stable_ids}
    negative = {stable_id: 0.0 for stable_id in stable_ids}
    view_evidence: list[dict[str, object]] = []

    for frame in frame_set.ordered_views:
        composite_mask = _composite_mask_for_view(mask_set, frame)
        if composite_mask is None:
            view_evidence.append({"viewId": frame.view_id, "status": "neutral"})
            continue

        rendered = renderer.render(scene_snapshot=scene_snapshot, frame=frame)
        validate_rendered_view(rendered, frame, stable_ids)
        negative_evidence_allowed = not (
            frame.source == "anchor" and rendered.anchor_parity == "moderate"
        )
        for contribution in rendered.contributors:
            if composite_mask.contains(contribution.x_px, contribution.y_px):
                positive[contribution.stable_id] += contribution.mass
            elif negative_evidence_allowed:
                negative[contribution.stable_id] += contribution.mass
        x0, y0, x1, y1 = rendered.support_bounds
        view_evidence.append(
            {
                "viewId": frame.view_id,
                "status": "accepted",
                "rendererId": renderer.renderer_id,
                "rgbFrameDigest": rendered.rgb_frame_digest,
                "supportBounds": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "contributorCount": len(rendered.contributors),
                "anchorParity": rendered.anchor_parity,
                "negativeEvidenceAllowed": negative_evidence_allowed,
            }
        )

    records = [
        _evidence_record(stable_id, positive[stable_id], negative[stable_id])
        for stable_id in stable_ids
    ]
    return {
        **dict(bindings),
        "frameSetId": frame_set.frame_set_id,
        "policy": evidence_policy(render_config_version),
        "records": records,
        "views": view_evidence,
    }


def selection_result_ids(
    evidence_snapshot: Mapping[str, Any],
) -> tuple[list[int], list[int], list[int]]:
    """Extract sorted, mutually exclusive Candidate Object Selection ID sets."""

    records = evidence_snapshot.get("records")
    if not isinstance(records, list):
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "The Evidence Snapshot has no complete Stable Gaussian records.",
        )
    selected: list[int] = []
    uncertain: list[int] = []
    rejected: list[int] = []
    for record in records:
        if not isinstance(record, dict) or not _stable_id(record.get("stableId")):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "The Evidence Snapshot has an invalid Stable Gaussian record.",
            )
        classification = record.get("classification")
        if classification == "selected":
            selected.append(record["stableId"])
        elif classification == "uncertain":
            uncertain.append(record["stableId"])
        elif classification == "rejected":
            rejected.append(record["stableId"])
        else:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "The Evidence Snapshot has an unknown Gaussian classification.",
            )
    return sorted(selected), sorted(uncertain), sorted(rejected)


def _binding_string(bindings: Mapping[str, object], name: str) -> str:
    value = bindings.get(name)
    if not isinstance(value, str) or not value:
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            f"Evidence Snapshot binding {name} must be a non-empty string.",
        )
    return value


def _scene_stable_ids(scene_snapshot: Mapping[str, Any]) -> list[int]:
    gaussians = scene_snapshot.get("gaussians")
    if not isinstance(gaussians, list):
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "The cached Scene Snapshot has no Gaussian records for Evidence Policy.",
        )
    stable_ids: list[int] = []
    for gaussian in gaussians:
        if not isinstance(gaussian, Mapping) or not _stable_id(gaussian.get("stableId")):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "The cached Scene Snapshot has an invalid Stable Gaussian ID.",
            )
        stable_id = gaussian["stableId"]
        if stable_id in stable_ids:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "The cached Scene Snapshot has duplicate Stable Gaussian IDs.",
            )
        stable_ids.append(stable_id)
    return sorted(stable_ids)


def _stable_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xFFFFFFFF


def _composite_mask_for_view(
    mask_set: Mapping[str, Any], frame: RegisteredFrame
) -> _CompositeMask | None:
    tracks = mask_set.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "Evidence Policy requires a complete immutable Mask Set.",
        )

    primary: Mapping[str, Any] | None = None
    claims: list[tuple[str, _BinaryMask]] = []
    for track in tracks:
        if not isinstance(track, Mapping) or track.get("role") not in {"include", "exclude"}:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "Evidence Policy received an invalid Mask Track.",
            )
        frames = track.get("frames")
        if not isinstance(frames, list):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "Evidence Policy received a Mask Track without Frame Set outcomes.",
            )
        mask_frame = next(
            (
                candidate
                for candidate in frames
                if isinstance(candidate, Mapping) and candidate.get("viewId") == frame.view_id
            ),
            None,
        )
        if mask_frame is None:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "Evidence Policy received a Mask Set that omits a registered view.",
            )
        if track.get("trackId") == "primary":
            if track.get("role") != "include" or primary is not None:
                raise MaskSessionError(
                    "invalidEvidenceSnapshot",
                    "Evidence Policy requires exactly one primary include Mask Track.",
                )
            primary = mask_frame
        if mask_frame.get("status") == "accepted":
            claims.append((track["role"], _binary_mask(mask_frame.get("binaryMask"), frame)))
        elif mask_frame.get("status") not in {"not_found", "rejected", "error"}:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "Evidence Policy received an unknown Mask Set frame outcome.",
            )

    # A missing primary include is a neutral observation, not an all-negative
    # composite.  Other accepted tracks cannot turn it into background evidence.
    if primary is None:
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "Evidence Policy requires the primary include Mask Track.",
        )
    if primary.get("status") != "accepted":
        return None
    return _CompositeMask(tuple(claims))


def _binary_mask(value: object, frame: RegisteredFrame) -> _BinaryMask:
    if not isinstance(value, Mapping):
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "An accepted Mask Set frame is missing its binary mask.",
        )
    if value.get("width") != frame.width or value.get("height") != frame.height:
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "A Mask Set binary mask does not match its rendered frame dimensions.",
        )
    encoding = value.get("encoding")
    if encoding == "sparse-points-v1":
        pixels = value.get("foregroundPixels")
        if not isinstance(pixels, list) or not pixels:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "A sparse Mask Set binary mask has no foreground pixels.",
            )
        parsed: set[tuple[int, int]] = set()
        for pixel in pixels:
            if (
                not isinstance(pixel, list)
                or len(pixel) != 2
                or not _pixel_coordinate(pixel[0], frame.width)
                or not _pixel_coordinate(pixel[1], frame.height)
            ):
                raise MaskSessionError(
                    "invalidEvidenceSnapshot",
                    "A sparse Mask Set binary mask contains an invalid pixel.",
                )
            parsed.add((pixel[0], pixel[1]))
        return _BinaryMask(frame.width, frame.height, sparse_pixels=frozenset(parsed))
    if encoding == "bitset-lsb-v1":
        encoded = value.get("data")
        if not isinstance(encoded, str):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "A bitset Mask Set binary mask has no encoded data.",
            )
        try:
            bits = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "A bitset Mask Set binary mask has invalid encoded data.",
            ) from error
        if len(bits) != math.ceil(frame.width * frame.height / 8):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "A bitset Mask Set binary mask has an invalid length.",
            )
        return _BinaryMask(frame.width, frame.height, bitset=bits)
    raise MaskSessionError(
        "invalidEvidenceSnapshot",
        "Evidence Policy received an unsupported binary Mask Set encoding.",
    )


def _pixel_coordinate(value: object, size: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < size


def validate_rendered_view(
    rendered: RenderedContributorView,
    frame: RegisteredFrame,
    stable_ids: Sequence[int],
) -> None:
    if not isinstance(rendered, RenderedContributorView):
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "The Contributor renderer returned an invalid rendered view.",
        )
    if (
        rendered.view_id != frame.view_id
        or rendered.rgb_frame_digest != frame.frame_digest
        or rendered.width != frame.width
        or rendered.height != frame.height
    ):
        raise MaskSessionError(
            "anchorParityMismatch",
            "The Contributor renderer did not return support for the exact Anchor RGB frame.",
        )
    if rendered.anchor_parity not in {"normal", "moderate", "severe"}:
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "The Contributor renderer returned an invalid Anchor parity result.",
        )
    if frame.source == "anchor" and rendered.anchor_parity == "severe":
        raise MaskSessionError(
            "anchorParityMismatch",
            "The Contributor renderer found a severe Anchor parity geometry or projection mismatch.",
        )
    x0, y0, x1, y1 = rendered.support_bounds
    if (
        not all(isinstance(value, int) and not isinstance(value, bool) for value in rendered.support_bounds)
        or x0 < 0
        or y0 < 0
        or x1 <= x0
        or y1 <= y0
        or x1 > frame.width
        or y1 > frame.height
    ):
        raise MaskSessionError(
            "invalidEvidenceSnapshot",
            "The Contributor renderer returned invalid bounded contributor support.",
        )
    known_ids = set(stable_ids)
    for sample in rendered.contributors:
        if (
            not isinstance(sample, ContributorSample)
            or sample.stable_id not in known_ids
            or not _pixel_coordinate(sample.x_px, frame.width)
            or not _pixel_coordinate(sample.y_px, frame.height)
            or not isinstance(sample.mass, (float, int))
            or isinstance(sample.mass, bool)
            or not math.isfinite(sample.mass)
            or sample.mass <= 0
            or not (x0 <= sample.x_px < x1 and y0 <= sample.y_px < y1)
        ):
            raise MaskSessionError(
                "invalidEvidenceSnapshot",
                "The Contributor renderer returned an invalid contributor sample.",
            )


def _evidence_record(stable_id: int, positive: float, negative: float) -> dict[str, object]:
    effective_observation = positive + negative
    posterior = (PRIOR_ALPHA + positive) / (
        PRIOR_ALPHA + PRIOR_BETA + positive + negative
    )
    if (
        effective_observation >= MINIMUM_EFFECTIVE_OBSERVATION
        and posterior >= SELECTED_POSTERIOR_THRESHOLD
    ):
        classification = "selected"
        uncertainty_reason: str | None = None
    elif (
        effective_observation >= MINIMUM_EFFECTIVE_OBSERVATION
        and posterior <= REJECTED_POSTERIOR_THRESHOLD
    ):
        classification = "rejected"
        uncertainty_reason = None
    elif effective_observation == 0:
        classification = "uncertain"
        uncertainty_reason = "unobserved"
    elif effective_observation < MINIMUM_EFFECTIVE_OBSERVATION:
        classification = "uncertain"
        uncertainty_reason = "insufficient_observation"
    else:
        classification = "uncertain"
        uncertainty_reason = "undecided_or_conflicting"
    return {
        "stableId": stable_id,
        "positiveEvidence": positive,
        "negativeEvidence": negative,
        "effectiveObservation": effective_observation,
        "posterior": posterior,
        "uncertaintyReason": uncertainty_reason,
        "classification": classification,
    }

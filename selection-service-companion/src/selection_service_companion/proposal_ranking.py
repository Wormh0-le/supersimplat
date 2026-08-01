"""Simplified Ticket 07A candidate assessment and default-preview ordering.

The v1 ranking machinery is removed: no pairwise containment/IoU, no
material-distinctness clustering, no Top-1 margin calibration, no compactness
features, and no Gaussian support sanity (Gaussian readiness belongs to
Ticket 13 Lift Readiness, never to Anchor candidate selection). What remains:

- per-candidate eligibility from the declared prompt facts plus the versioned
  local Mask Review (Ticket 07 policy ``local-view-assessment/v2``, reused
  unchanged — severe fragmentation, material boundary clipping, and gross Box
  spill enter Review; empty/degenerate/full-frame candidates are ineligible);
- a deterministic default preview: the highest raw model score, ties broken
  by source order. The raw score only orders the preview; it is not a
  correctness probability and never auto-confirms a candidate;
- explicit user choice resolves one-point multimask ambiguity.
"""

from __future__ import annotations

import base64
import math
from typing import Mapping, Sequence

from .view_assessment import (
    MaskReviewPrompt,
    assess_local_view,
    local_view_assessment_payload,
)


RANKING_POLICY_VERSION = 'anchor-mask-ranking/v3'

_DECLARED_FACT_KEYS = {
    'positivePointsSatisfied',
    'negativePointsSatisfied',
    'positiveBoxesSatisfied',
}


def _mask_bits(proposal: Mapping[str, object], width: int, height: int) -> bytes:
    mask = proposal['mask']
    if not isinstance(mask, Mapping):
        raise ValueError('Proposal mask must be an object')
    data = mask.get('data')
    if not isinstance(data, str):
        raise ValueError('Proposal mask data must be base64')
    bits = base64.b64decode(data, validate=True)
    if len(bits) != (width * height + 7) // 8:
        raise ValueError('Proposal mask data does not match its dimensions')
    return bits


def _is_foreground(mask: bytes, pixel: int) -> bool:
    return ((mask[pixel >> 3] >> (pixel & 7)) & 1) == 1


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def add_ranking_features(
    proposals: Sequence[dict[str, object]],
    *,
    width: int,
    height: int,
    prompt_state: Mapping[str, object],
) -> list[dict[str, object]]:
    """Attach the slim v3 feature record and Mask Review to each candidate."""

    points_value = prompt_state.get('points')
    points = [
        point
        for point in (points_value if isinstance(points_value, list) else [])
        if isinstance(point, Mapping)
        and isinstance(point.get('xPx'), int)
        and isinstance(point.get('yPx'), int)
        and 0 <= int(point['xPx']) < width
        and 0 <= int(point['yPx']) < height
    ]
    positive_points = tuple(
        (int(point['xPx']), int(point['yPx']))
        for point in points
        if point.get('polarity') == 'include'
    )
    negative_points = tuple(
        (int(point['xPx']), int(point['yPx']))
        for point in points
        if point.get('polarity') == 'exclude'
    )
    boxes_value = prompt_state.get('boxes')
    boxes = [
        box
        for box in (boxes_value if isinstance(boxes_value, list) else [])
        if isinstance(box, Mapping)
        and all(
            isinstance(box.get(key), int) and not isinstance(box.get(key), bool)
            for key in ('x0Px', 'y0Px', 'x1Px', 'y1Px')
        )
    ]
    box_xyxy: tuple[int, int, int, int] | None = None
    if boxes:
        box = boxes[0]
        candidate_box = (
            int(box['x0Px']),
            int(box['y0Px']),
            int(box['x1Px']),
            int(box['y1Px']),
        )
        # A declared Prompt family is never silently dropped: an out-of-frame
        # Box fails closed instead of evaporating from consistency evaluation.
        if not (
            0 <= candidate_box[0] < candidate_box[2] < width
            and 0 <= candidate_box[1] < candidate_box[3] < height
        ):
            raise ValueError('Prompt Box is outside the View frame')
        box_xyxy = candidate_box
    review_prompt = MaskReviewPrompt(
        positive_points=positive_points,
        negative_points=negative_points,
        box_xyxy=box_xyxy,
    )

    enriched: list[dict[str, object]] = []
    for proposal in proposals:
        mask = _mask_bits(proposal, width, height)
        assessment = assess_local_view(
            width=width, height=height, mask=mask, prompt=review_prompt
        )
        positive_satisfied = all(
            _is_foreground(mask, y * width + x) for x, y in positive_points
        )
        negative_satisfied = all(
            not _is_foreground(mask, y * width + x) for x, y in negative_points
        )
        declared = proposal.get('promptConsistency')
        if (
            isinstance(declared, Mapping)
            and set(declared) == _DECLARED_FACT_KEYS
            and all(isinstance(value, bool) for value in declared.values())
        ):
            # Candidate-local facts arrive from the adapter compiler; a
            # declared hard Prompt contradiction is never eligible, regardless
            # of model score. Only the exact three-fact record crosses the
            # boundary — a partial declaration falls back to recomputation.
            prompt_consistency = dict(declared)
            hard_facts_satisfied = all(prompt_consistency.values())
        else:
            # Recomputation emits the same exact three-fact record the editor
            # requires. Without a declared Box family the fact holds
            # vacuously; with one, meaningful overlap is required.
            box_satisfied = box_xyxy is None or any(
                _is_foreground(mask, y * width + x)
                for y in range(box_xyxy[1], box_xyxy[3] + 1)
                for x in range(box_xyxy[0], box_xyxy[2] + 1)
            )
            prompt_consistency = {
                'positivePointsSatisfied': positive_satisfied,
                'negativePointsSatisfied': negative_satisfied,
                'positiveBoxesSatisfied': box_satisfied,
            }
            hard_facts_satisfied = all(prompt_consistency.values())
        features: dict[str, object] = {
            'promptConsistency': prompt_consistency,
            'eligible': bool(
                assessment.status != 'failed'
                and positive_satisfied
                and negative_satisfied
                and hard_facts_satisfied
            ),
            'areaFraction': (
                assessment.diagnostics.foreground_pixels / (width * height)
            ),
            'connectedComponentCount': (
                assessment.diagnostics.connected_components
            ),
        }
        if _is_finite_number(proposal.get('modelScore')):
            features['modelScore'] = proposal['modelScore']
        enriched.append({
            **proposal,
            'rankingFeatures': features,
            'review': local_view_assessment_payload(assessment),
        })
    return enriched


def decide_proposals(
    proposals: Sequence[Mapping[str, object]],
    *,
    view_id: str,
    rgb_digest: str,
    prompt_state_digest: str,
    proposal_set_digest: str,
) -> dict[str, object]:
    """Classify the set and name the default preview; never auto-confirm."""

    eligible = [
        proposal
        for proposal in proposals
        if isinstance(proposal.get('rankingFeatures'), Mapping)
        and proposal['rankingFeatures'].get('eligible') is True  # type: ignore[union-attr]
    ]

    def preview_order(proposal: Mapping[str, object]) -> tuple[float, int]:
        score = proposal.get('modelScore')
        value = (
            float(score)  # type: ignore[arg-type]
            if _is_finite_number(score)
            else float('-inf')
        )
        return (-value, int(proposal['sourceIndex']))  # type: ignore[arg-type]

    ordered = sorted(eligible, key=preview_order)
    alternative_ids = [str(proposal['proposalId']) for proposal in ordered]
    base: dict[str, object] = {
        'schemaVersion': 2,
        'viewId': view_id,
        'rgbDigest': rgb_digest,
        'promptStateDigest': prompt_state_digest,
        'proposalSetDigest': proposal_set_digest,
        'rankingPolicyVersion': RANKING_POLICY_VERSION,
        'alternativeProposalIds': alternative_ids,
    }
    if not ordered:
        return {**base, 'status': 'unavailable'}
    return {
        **base,
        'status': 'selected' if len(ordered) == 1 else 'ambiguous',
        'selectedProposalId': alternative_ids[0],
    }

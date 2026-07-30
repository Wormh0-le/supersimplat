from __future__ import annotations

import base64
from collections import deque
import math
from typing import Mapping, Sequence


RANKING_POLICY_VERSION = 'anchor-mask-ranking/v1'
MATERIAL_IOU_THRESHOLD = 0.9
MATERIAL_AREA_RATIO_THRESHOLD = 1.15
NESTED_AREA_RATIO_THRESHOLD = 1.5
SIMILAR_MODEL_SCORE_DELTA = 0.1


def _mask_pixels(proposal: Mapping[str, object], width: int, height: int) -> list[bool]:
    mask = proposal['mask']
    if not isinstance(mask, Mapping):
        raise ValueError('Proposal mask must be an object')
    data = mask.get('data')
    if not isinstance(data, str):
        raise ValueError('Proposal mask data must be base64')
    bits = base64.b64decode(data, validate=True)
    return [
        bool(bits[index // 8] & (1 << (index % 8)))
        for index in range(width * height)
    ]


def _component_features(
    pixels: Sequence[bool], width: int, height: int
) -> tuple[int, list[int], int]:
    component_ids = [-1] * len(pixels)
    component_count = 0
    perimeter = 0
    for index, foreground in enumerate(pixels):
        if not foreground:
            continue
        x = index % width
        y = index // width
        for neighbour_x, neighbour_y in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            if (
                neighbour_x < 0
                or neighbour_x >= width
                or neighbour_y < 0
                or neighbour_y >= height
                or not pixels[neighbour_y * width + neighbour_x]
            ):
                perimeter += 1
        if component_ids[index] >= 0:
            continue
        queue = deque([index])
        component_ids[index] = component_count
        while queue:
            current = queue.popleft()
            current_x = current % width
            current_y = current // width
            for neighbour_x, neighbour_y in (
                (current_x - 1, current_y),
                (current_x + 1, current_y),
                (current_x, current_y - 1),
                (current_x, current_y + 1),
            ):
                if (
                    0 <= neighbour_x < width
                    and 0 <= neighbour_y < height
                    and pixels[neighbour_y * width + neighbour_x]
                ):
                    neighbour = neighbour_y * width + neighbour_x
                    if component_ids[neighbour] < 0:
                        component_ids[neighbour] = component_count
                        queue.append(neighbour)
        component_count += 1
    return component_count, component_ids, perimeter


def _point_boundary_distance(
    pixels: Sequence[bool], width: int, height: int, x: int, y: int
) -> float:
    if not pixels[y * width + x]:
        return 0.0
    distance = 1
    while distance <= max(width, height):
        for candidate_x, candidate_y in (
            (x - distance, y),
            (x + distance, y),
            (x, y - distance),
            (x, y + distance),
        ):
            if (
                candidate_x < 0
                or candidate_x >= width
                or candidate_y < 0
                or candidate_y >= height
                or not pixels[candidate_y * width + candidate_x]
            ):
                return float(distance)
        distance += 1
    return float(max(width, height))


def _box_features(
    pixels: Sequence[bool], width: int, boxes: Sequence[object]
) -> tuple[list[float], list[float]]:
    fill_ratios: list[float] = []
    spill_ratios: list[float] = []
    foreground_count = sum(pixels)
    for value in boxes:
        if not isinstance(value, Mapping):
            continue
        x0 = int(value['x0Px'])
        y0 = int(value['y0Px'])
        x1 = int(value['x1Px'])
        y1 = int(value['y1Px'])
        box_indexes = [
            y * width + x
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
        ]
        inside = sum(1 for index in box_indexes if pixels[index])
        fill_ratios.append(inside / len(box_indexes))
        spill_ratios.append(
            0.0 if foreground_count == 0 else (foreground_count - inside) / foreground_count
        )
    return fill_ratios, spill_ratios


def _base_features(
    proposal: Mapping[str, object],
    *,
    width: int,
    height: int,
    prompt_state: Mapping[str, object],
) -> tuple[dict[str, object], list[bool]]:
    pixels = _mask_pixels(proposal, width, height)
    foreground_indexes = [index for index, foreground in enumerate(pixels) if foreground]
    points_value = prompt_state.get('points')
    points = points_value if isinstance(points_value, list) else []
    positive_points = [
        point
        for point in points
        if isinstance(point, Mapping) and point.get('polarity') == 'include'
    ]
    negative_points = [
        point
        for point in points
        if isinstance(point, Mapping) and point.get('polarity') == 'exclude'
    ]
    positive_satisfied = all(
        pixels[int(point['yPx']) * width + int(point['xPx'])]
        for point in positive_points
    )
    negative_satisfied = all(
        not pixels[int(point['yPx']) * width + int(point['xPx'])]
        for point in negative_points
    )
    component_count, component_ids, perimeter = _component_features(
        pixels, width, height
    )
    if foreground_indexes:
        xs = [index % width for index in foreground_indexes]
        ys = [index // width for index in foreground_indexes]
        bounding_box: dict[str, int] = {
            'x0Px': min(xs),
            'y0Px': min(ys),
            'x1Px': max(xs),
            'y1Px': max(ys),
        }
    else:
        bounding_box = {'x0Px': 0, 'y0Px': 0, 'x1Px': 0, 'y1Px': 0}
    boundary_foreground = sum(
        1
        for index in foreground_indexes
        if index % width in (0, width - 1) or index // width in (0, height - 1)
    )
    boxes_value = prompt_state.get('boxes')
    boxes = boxes_value if isinstance(boxes_value, list) else []
    box_fill_ratios, box_spill_ratios = _box_features(pixels, width, boxes)
    positive_component_ids = [
        component_ids[int(point['yPx']) * width + int(point['xPx'])]
        for point in positive_points
    ]
    prompt_fact_count = len(positive_points) + len(negative_points)
    satisfied_fact_count = sum(
        pixels[int(point['yPx']) * width + int(point['xPx'])]
        for point in positive_points
    ) + sum(
        not pixels[int(point['yPx']) * width + int(point['xPx'])]
        for point in negative_points
    )
    area = len(foreground_indexes)
    candidate_prompt_consistency = proposal.get('promptConsistency')
    if (
        isinstance(candidate_prompt_consistency, Mapping)
        and all(
            isinstance(value, bool)
            for value in candidate_prompt_consistency.values()
        )
        and {'positivePointsSatisfied', 'negativePointsSatisfied'}
        <= set(candidate_prompt_consistency)
    ):
        prompt_consistency = dict(candidate_prompt_consistency)
    else:
        prompt_consistency = {
            'positivePointsSatisfied': positive_satisfied,
            'negativePointsSatisfied': negative_satisfied,
        }
    hard_prompts_satisfied = all(prompt_consistency.values())
    features: dict[str, object] = {
        # Candidate-local visual facts arrive from the adapter compiler. The
        # current ranking policy remains unchanged; it merely retains those
        # facts for Ticket 07A instead of overwriting them with point-only
        # diagnostics.
        'promptConsistency': prompt_consistency,
        # 04B supplies candidate-local visual facts; the retained 07A policy
        # owns the eligibility decision. A declared hard Prompt contradiction
        # is never eligible, regardless of model score.
        'eligible': bool(
            area
            and positive_satisfied
            and negative_satisfied
            and hard_prompts_satisfied
        ),
        'areaFraction': area / (width * height),
        'boundingBox': bounding_box,
        'connectedComponentCount': component_count,
        'positivePointComponentIds': positive_component_ids,
        'positivePointBoundaryDistances': [
            _point_boundary_distance(
                pixels,
                width,
                height,
                int(point['xPx']),
                int(point['yPx']),
            )
            for point in positive_points
        ],
        'pairwiseRelations': [],
        'boundaryContactFraction': (
            0.0 if perimeter == 0 else boundary_foreground / perimeter
        ),
        'compactness': (
            0.0 if perimeter == 0 else 4.0 * math.pi * area / (perimeter * perimeter)
        ),
        'boxFillRatios': box_fill_ratios,
        'boxSpillRatios': box_spill_ratios,
        'promptMaskOverlap': (
            1.0 if prompt_fact_count == 0 else satisfied_fact_count / prompt_fact_count
        ),
        'optionalSupportSanity': {
            'participated': False,
            'changedDecision': False,
        },
    }
    if isinstance(proposal.get('modelScore'), (int, float)):
        features['modelScore'] = proposal['modelScore']
    return features, pixels


def add_ranking_features(
    proposals: Sequence[dict[str, object]],
    *,
    width: int,
    height: int,
    prompt_state: Mapping[str, object],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    pixels_by_proposal: list[list[bool]] = []
    for proposal in proposals:
        features, pixels = _base_features(
            proposal, width=width, height=height, prompt_state=prompt_state
        )
        enriched.append({**proposal, 'rankingFeatures': features})
        pixels_by_proposal.append(pixels)
    for left_index, left in enumerate(enriched):
        left_pixels = pixels_by_proposal[left_index]
        left_area = sum(left_pixels)
        relations: list[dict[str, object]] = []
        for right_index, right in enumerate(enriched):
            if left_index == right_index:
                continue
            right_pixels = pixels_by_proposal[right_index]
            right_area = sum(right_pixels)
            intersection = sum(
                left_pixel and right_pixel
                for left_pixel, right_pixel in zip(left_pixels, right_pixels, strict=True)
            )
            union = left_area + right_area - intersection
            iou = 0.0 if union == 0 else intersection / union
            area_ratio = (
                1.0
                if min(left_area, right_area) == 0
                else max(left_area, right_area) / min(left_area, right_area)
            )
            containment = 'none'
            if left_area > 0 and intersection == left_area and right_area > left_area:
                containment = 'contained-by'
            elif right_area > 0 and intersection == right_area and left_area > right_area:
                containment = 'contains'
            relations.append({
                'proposalId': right['proposalId'],
                'intersectionOverUnion': iou,
                'areaRatio': area_ratio,
                'containment': containment,
                'materiallyDistinct': (
                    iou < MATERIAL_IOU_THRESHOLD
                    or area_ratio > MATERIAL_AREA_RATIO_THRESHOLD
                ),
            })
        features = left['rankingFeatures']
        if isinstance(features, dict):
            features['pairwiseRelations'] = relations
    return enriched


def decide_proposals(
    proposals: Sequence[Mapping[str, object]],
    *,
    view_id: str,
    rgb_digest: str,
    prompt_state_digest: str,
    proposal_set_digest: str,
) -> dict[str, object]:
    eligible = [
        proposal
        for proposal in proposals
        if isinstance(proposal.get('rankingFeatures'), Mapping)
        and proposal['rankingFeatures'].get('eligible') is True  # type: ignore[union-attr]
    ]
    base: dict[str, object] = {
        'schemaVersion': 1,
        'viewId': view_id,
        'rgbDigest': rgb_digest,
        'promptStateDigest': prompt_state_digest,
        'proposalSetDigest': proposal_set_digest,
        'rankingPolicyVersion': RANKING_POLICY_VERSION,
        'alternativeProposalIds': [
            str(proposal['proposalId']) for proposal in eligible
        ],
        'reasons': [],
    }
    if not eligible:
        return {
            **base,
            'status': 'unavailable',
            'reasons': [{'code': 'prompt-conflict', 'proposalIds': []}],
        }
    suggested = max(
        eligible,
        key=lambda proposal: (
            float(proposal.get('modelScore', float('-inf'))),
            -int(proposal['sourceIndex']),
        ),
    )
    if len(eligible) == 1:
        return {
            **base,
            'status': 'selected',
            'selectedProposalId': suggested['proposalId'],
        }
    material_relations = [
        relation
        for proposal in eligible
        for relation in proposal['rankingFeatures']['pairwiseRelations']  # type: ignore[index]
        if relation['materiallyDistinct']
    ]
    if not material_relations:
        return {
            **base,
            'status': 'selected',
            'selectedProposalId': suggested['proposalId'],
        }
    reason_codes: list[str] = ['insufficient-decision-margin']
    if any(
        relation['containment'] != 'none'
        and relation['areaRatio'] >= NESTED_AREA_RATIO_THRESHOLD
        for relation in material_relations
    ):
        reason_codes.append('nested-part-vs-whole')
    if any(
        relation['areaRatio'] >= 2.0
        for relation in material_relations
    ):
        reason_codes.append('neighbour-object-leak-risk')
    scores = [
        float(proposal['modelScore'])
        for proposal in eligible
        if isinstance(proposal.get('modelScore'), (int, float))
    ]
    area_fractions = [
        float(proposal['rankingFeatures']['areaFraction'])  # type: ignore[index]
        for proposal in eligible
    ]
    if (
        len(scores) == len(eligible)
        and max(scores) - min(scores) <= SIMILAR_MODEL_SCORE_DELTA
        and max(area_fractions) / max(min(area_fractions), 1e-12)
        >= NESTED_AREA_RATIO_THRESHOLD
    ):
        reason_codes.append('similar-score-different-area')
    if any(
        proposal['rankingFeatures']['connectedComponentCount'] > 1  # type: ignore[index]
        for proposal in eligible
    ):
        reason_codes.append('multiple-disconnected-targets')
    return {
        **base,
        'status': 'ambiguous',
        'selectedProposalId': suggested['proposalId'],
        'reasons': [
            {
                'code': code,
                'proposalIds': [
                    str(proposal['proposalId']) for proposal in eligible
                ],
            }
            for code in reason_codes
        ],
    }

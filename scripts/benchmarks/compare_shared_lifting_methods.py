#!/usr/bin/env python3
"""Compare 2D-to-Gaussian lifting candidates on the frozen shared fixtures.

Prediction deliberately runs before this program opens any Ground Truth file.
It writes a prediction manifest and immutable per-method Stable Gaussian ID
outputs first; only then does the scoring phase read the frozen labels.

This is a disposable Wayfinder prototype, not an editor implementation.  In
particular, ``soft_mask_fit`` is a project-owned SA3D-style linear soft-mask
fit over same-renderer alpha×transmittance contributors.  It is not SA3D code
or a claim that this reproduces any external method.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gsplat
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402
from renderers import FAR_PLANE, NEAR_PLANE  # noqa: E402


METHOD_ORDER = (
    "current_top1_visibility",
    "hard_top1_vote",
    "contributor_three_state",
    "soft_mask_fit",
)


@dataclass(frozen=True)
class Scenario:
    """All prediction inputs for one benchmark case, except Ground Truth data."""

    scenario_id: str
    role: str
    ply_path: Path
    ply_sha256: str
    frame_set_path: Path
    mask_set_path: Path
    masks_path: Path
    truth_path: Path


@dataclass(frozen=True)
class AcceptedFrame:
    frame_index: int
    view_id: str
    camera_to_world: np.ndarray
    mask: np.ndarray
    is_anchor: bool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} digest mismatch: expected {expected}, got {actual}")


def scenario_inputs(fixtures_root: Path, wanted: set[str]) -> tuple[dict[str, Scenario], dict[str, Any]]:
    """Load only manifest metadata; Ground Truth arrays stay unopened here."""

    manifest_path = fixtures_root / "shared-lifting-benchmark-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenarios: dict[str, Scenario] = {}

    if "controlled_overlap" in wanted:
        controlled_root = fixtures_root / "controlled-overlap"
        controlled = json.loads((controlled_root / "controlled_front_back_overlap.json").read_text(encoding="utf-8"))
        frame_set_path = controlled_root / "frame-set-v1" / "frame-set.json"
        mask_set_path = controlled_root / "frame-set-v1" / "mask-set-v1" / "mask-set.json"
        scenarios["controlled_overlap"] = Scenario(
            scenario_id="controlled_overlap",
            role="controlled-front-back-overlap",
            ply_path=controlled_root / "controlled_front_back_overlap.ply",
            ply_sha256=controlled["files"]["controlled_front_back_overlap.ply"]["sha256"],
            frame_set_path=frame_set_path,
            mask_set_path=mask_set_path,
            masks_path=mask_set_path.parent / "masks.npz",
            truth_path=controlled_root / "controlled_front_back_overlap_ground_truth.npz",
        )

    for target in manifest["office_targets"]:
        target_id = target["target_id"]
        if target_id not in wanted:
            continue
        frame_set_path = fixtures_root / target["frame_set"]["path"]
        mask_set_path = fixtures_root / target["mask_set"]["path"]
        truth_path = fixtures_root / target["ground_truth"]["labels"]["path"]
        scenarios[target_id] = Scenario(
            scenario_id=target_id,
            role=target["benchmark_role"],
            ply_path=Path(target["scene_snapshot"]["path"]),
            ply_sha256=target["scene_snapshot"]["sha256"],
            frame_set_path=frame_set_path,
            mask_set_path=mask_set_path,
            masks_path=fixtures_root / target["mask_set"]["mask_tensor"]["path"],
            truth_path=truth_path,
        )

    unknown = wanted - set(scenarios)
    if unknown:
        raise ValueError(f"unknown scenario(s): {', '.join(sorted(unknown))}")
    return scenarios, {"path": str(manifest_path), "sha256": sha256(manifest_path)}


def accepted_frames(scenario: Scenario) -> tuple[list[AcceptedFrame], tuple[int, int], dict[str, int]]:
    """Read Frame/Mask Sets and retain only accepted masks for prediction."""

    frame_set = json.loads(scenario.frame_set_path.read_text(encoding="utf-8"))
    mask_set = json.loads(scenario.mask_set_path.read_text(encoding="utf-8"))
    masks = np.load(scenario.masks_path)["masks"].astype(bool)
    width, height = (int(value) for value in frame_set["resolution"])
    if masks.ndim != 3 or masks.shape[1:] != (height, width):
        raise RuntimeError(f"unexpected mask shape for {scenario.scenario_id}: {masks.shape}")

    frames_by_index = {int(frame["frame_index"]): frame for frame in frame_set["frames"]}
    if "tracks" in mask_set:
        tracks = mask_set["tracks"]
        if len(tracks) != 1 or tracks[0]["role"] != "include":
            raise RuntimeError(f"{scenario.scenario_id} must have one include Mask Track")
        mask_frames = tracks[0]["frames"]
    else:
        mask_frames = mask_set["frames"]

    statuses: dict[str, int] = {}
    result: list[AcceptedFrame] = []
    for mask_frame in mask_frames:
        status = mask_frame["status"]
        statuses[status] = statuses.get(status, 0) + 1
        if status != "accepted":
            continue
        frame_index = int(mask_frame["frame_index"])
        frame = frames_by_index.get(frame_index)
        mask_view_id = mask_frame.get("view_id", mask_frame.get("candidate_id"))
        if frame is None or frame["candidate_id"] != mask_view_id:
            raise RuntimeError(f"Frame Set and Mask Set disagree for {scenario.scenario_id} frame {frame_index}")
        mask_index = int(mask_frame.get("binary_mask_index", frame_index))
        if not 0 <= mask_index < len(masks):
            raise RuntimeError(f"invalid mask index for {scenario.scenario_id} frame {frame_index}")
        result.append(
            AcceptedFrame(
                frame_index=frame_index,
                view_id=frame["candidate_id"],
                camera_to_world=np.asarray(frame["camera_to_world"], dtype=np.float32),
                mask=masks[mask_index],
                is_anchor=frame.get("category") == "anchor" or frame["candidate_id"] == "anchor" or frame["candidate_id"].startswith("anchor-"),
            )
        )
    if not result:
        raise RuntimeError(f"{scenario.scenario_id} has no accepted masks")
    if sum(frame.is_anchor for frame in result) != 1:
        raise RuntimeError(f"{scenario.scenario_id} must have exactly one accepted Anchor View")
    return result, (width, height), statuses


def support_region(mask: np.ndarray, margin: int) -> np.ndarray:
    """Use a prompt-derived local support region without consulting Ground Truth.

    A known empty controlled-fixture mask retains the complete view as negative
    observation.  Production Mask Sets normally reject empty masks instead.
    """

    if not mask.any():
        return np.ones_like(mask, dtype=bool)
    y, x = np.nonzero(mask)
    y0 = max(0, int(y.min()) - margin)
    y1 = min(mask.shape[0], int(y.max()) + margin + 1)
    x0 = max(0, int(x.min()) - margin)
    x1 = min(mask.shape[1], int(x.max()) + margin + 1)
    support = np.zeros_like(mask, dtype=bool)
    support[y0:y1, x0:x1] = True
    return support


def global_contributor_ids(packed_ids: torch.Tensor, meta: dict[str, Any]) -> torch.Tensor:
    """Map raster packing IDs to fixture Stable Gaussian IDs."""

    ids = packed_ids.long()
    gaussian_ids = meta.get("gaussian_ids")
    if gaussian_ids is None:
        return ids
    valid = ids >= 0
    result = torch.full_like(ids, -1)
    result[valid] = gaussian_ids[ids[valid]].long()
    return result


def extract_weighted(ids: torch.Tensor, weights: torch.Tensor, pixel_selector: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    selected_ids = ids[pixel_selector].reshape(-1)
    selected_weights = weights[pixel_selector].reshape(-1)
    valid = (selected_ids >= 0) & torch.isfinite(selected_weights) & (selected_weights > 0)
    return selected_ids[valid], selected_weights[valid].float()


def add_weighted(accumulator: torch.Tensor, ids: torch.Tensor, weights: torch.Tensor) -> None:
    if len(ids):
        accumulator.scatter_add_(0, ids, weights)


def id_array_from_state(state: torch.Tensor, expected: int) -> np.ndarray:
    values = torch.nonzero(state == expected, as_tuple=False).flatten().cpu().numpy()
    return values.astype(np.uint32, copy=False)


def state_for_hard_votes(
    positive: torch.Tensor,
    negative: torch.Tensor,
    observed: torch.Tensor,
    min_views: int,
) -> torch.Tensor:
    state = torch.zeros(len(observed), dtype=torch.uint8, device=observed.device)
    state[(positive >= min_views) & (positive > negative)] = 1
    state[(negative >= min_views) & (negative > positive)] = 2
    return state


def state_for_weighted_evidence(
    positive: torch.Tensor,
    negative: torch.Tensor,
    observation_weight: torch.Tensor,
    observed_frames: torch.Tensor,
    min_weight: float,
    min_views: int,
    low: float,
    high: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    state = torch.zeros(len(observation_weight), dtype=torch.uint8, device=observation_weight.device)
    total = positive + negative
    ratio = torch.full_like(total, 0.5)
    nonzero = total > 0
    ratio[nonzero] = positive[nonzero] / total[nonzero]
    eligible = (observation_weight >= min_weight) & (observed_frames >= min_views)
    state[eligible & (ratio >= high)] = 1
    state[eligible & (ratio <= low)] = 2
    return state, ratio


def optimize_soft_mask(
    *,
    initial: torch.Tensor,
    observation_weight: torch.Tensor,
    hessian_diagonal: torch.Tensor,
    records: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    iterations: int,
    step: float,
    prior_strength: float,
) -> tuple[torch.Tensor, list[float]]:
    """Projected, diagonally preconditioned fitting of a per-Gaussian soft mask."""

    observed = observation_weight > 0
    result = initial.clone()
    denominator = hessian_diagonal + prior_strength
    history: list[float] = []
    for _ in range(iterations):
        gradient = torch.zeros_like(result)
        squared_error = 0.0
        pixels = 0
        for ids, weights, target in records:
            prediction = (weights * result[ids]).sum(dim=1)
            residual = prediction - target
            gradient.scatter_add_(0, ids.reshape(-1), (weights * residual[:, None]).reshape(-1))
            squared_error += float(torch.sum(residual * residual).item())
            pixels += int(len(target))
        gradient[observed] += prior_strength * (result[observed] - initial[observed])
        result[observed] = torch.clamp(
            result[observed] - step * gradient[observed] / denominator[observed].clamp_min(1e-8),
            0.0,
            1.0,
        )
        history.append(squared_error / max(1, pixels))
    return result, history


def metrics_for_prediction(state: np.ndarray, truth_path: Path, controlled_means: np.ndarray | None) -> dict[str, Any]:
    """Open Ground Truth only after prediction artifacts have been frozen."""

    truth = np.load(truth_path)
    selected_truth = truth["selected_ids"].astype(np.uint32)
    rejected_truth = truth["rejected_ids"].astype(np.uint32)
    ambiguous_truth = truth["ambiguous_ids"].astype(np.uint32)
    if "scope_ids" in truth.files:
        scope = truth["scope_ids"].astype(np.uint32)
    else:
        scope = np.concatenate((selected_truth, rejected_truth, ambiguous_truth))
    scope_state = state[scope]
    selected_prediction = scope_state == 1
    rejected_prediction = scope_state == 2
    uncertain_prediction = scope_state == 0
    selected_truth_mask = np.isin(scope, selected_truth, assume_unique=True)
    rejected_truth_mask = np.isin(scope, rejected_truth, assume_unique=True)
    metric_scope = selected_truth_mask | rejected_truth_mask

    true_positive = int(np.count_nonzero(selected_prediction & selected_truth_mask))
    false_positive = int(np.count_nonzero(selected_prediction & rejected_truth_mask))
    false_negative = int(np.count_nonzero(~selected_prediction & selected_truth_mask))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    iou = true_positive / (true_positive + false_positive + false_negative) if true_positive + false_positive + false_negative else 0.0

    result: dict[str, Any] = {
        "metric_scope_gaussians": int(metric_scope.sum()),
        "truth": {
            "selected": int(len(selected_truth)),
            "rejected": int(len(rejected_truth)),
            "ambiguous": int(len(ambiguous_truth)),
            "scope": int(len(scope)),
        },
        "prediction_on_truth_scope": {
            "selected": int(selected_prediction.sum()),
            "rejected": int(rejected_prediction.sum()),
            "uncertain": int(uncertain_prediction.sum()),
        },
        "scores": {
            "gaussian_index_iou": iou,
            "precision": precision,
            "recall": recall,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "truth_selected_prediction_state": {
            "selected": int(np.count_nonzero(selected_truth_mask & selected_prediction)),
            "rejected": int(np.count_nonzero(selected_truth_mask & rejected_prediction)),
            "uncertain": int(np.count_nonzero(selected_truth_mask & uncertain_prediction)),
        },
        "truth_rejected_prediction_state": {
            "selected": int(np.count_nonzero(rejected_truth_mask & selected_prediction)),
            "rejected": int(np.count_nonzero(rejected_truth_mask & rejected_prediction)),
            "uncertain": int(np.count_nonzero(rejected_truth_mask & uncertain_prediction)),
        },
    }
    if controlled_means is not None:
        # The half facing away from the Anchor View is a fixture-geometry-only
        # diagnostic, evaluated after prediction just like Ground Truth.
        target_z = controlled_means[: len(selected_truth), 2]
        rear_ids = np.flatnonzero(target_z >= np.median(target_z)).astype(np.uint32)
        rear_selected = int(np.count_nonzero(state[rear_ids] == 1))
        result["anchor_opposite_half_recall"] = rear_selected / len(rear_ids)
    return result


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Shared 2D-to-Gaussian lifting comparison",
        "",
        "This is a Wayfinder prototype result. Every method consumed the same frozen Scene Snapshot, Frame Set, and Mask Set. Prediction artifacts were written before the scoring phase opened Ground Truth.",
        "",
        "## Fixed comparison policy",
        "",
        f"- Top contributors per pixel: {result['comparison_policy']['top_k']}",
        f"- Prompt-derived support margin: {result['comparison_policy']['support_margin_pixels']} px",
        f"- Evidence decisions: at least {result['comparison_policy']['minimum_observed_views']} accepted views and {result['comparison_policy']['minimum_observation_weight']} accumulated alpha×transmittance support; selected at ≥{result['comparison_policy']['selected_ratio']}, rejected at ≤{result['comparison_policy']['rejected_ratio']}, otherwise uncertain.",
        "- The thresholds are comparison-only. Product semantics remain owned by the later Selection Evidence decision.",
        "",
        "## Results",
        "",
        "| Scenario | Method | IoU | Precision | Recall | Truth-selected → uncertain | Truth-rejected → selected |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scenario in result["scenarios"]:
        for method in METHOD_ORDER:
            score = scenario["methods"][method]["score"]
            selected_state = score["truth_selected_prediction_state"]
            rejected_state = score["truth_rejected_prediction_state"]
            lines.append(
                "| {scenario} | {method} | {iou:.3f} | {precision:.3f} | {recall:.3f} | {uncertain} | {leakage} |".format(
                    scenario=scenario["scenario_id"],
                    method=method,
                    iou=score["scores"]["gaussian_index_iou"],
                    precision=score["scores"]["precision"],
                    recall=score["scores"]["recall"],
                    uncertain=selected_state["uncertain"],
                    leakage=rejected_state["selected"],
                )
            )
    lines.extend(
        [
            "",
            "## Implementation and license boundary",
            "",
            "- The top-1 and hard-vote baselines introduce no dependency but cannot represent alpha×transmittance evidence.",
            "- Contributor evidence adds service-side accumulation over the already-installed gsplat contributor API; this prototype adds no model, checkpoint, or external source dependency.",
            "- Soft fitting adds a numerical-solver/configuration/test burden, but is project-owned code over the same inputs. It does not use SA3D or FlashSplat code, weights, or licenses.",
            "",
            "## Interpretation boundary",
            "",
            "- `current_top1_visibility` is a same-renderer top-1-contributor proxy for the current ID-visibility baseline; it is not a claim that the browser ID pass is identical.",
            "- `hard_top1_vote` uses unweighted top-1 footprint votes. `contributor_three_state` uses alpha×transmittance weight; both leave non-observation uncertain.",
            "- `soft_mask_fit` is a project-owned SA3D-style linear fit with a contributor-evidence prior. It is not the official SA3D implementation and introduces no external dependency.",
            "- Frozen office Coverage Reports are insufficient by design, so none of these outputs proves a Ready Object Selection or full-object coverage.",
            "",
            "Full configuration, raw Stable Gaussian ID outputs, per-view diagnostics, timings, VRAM, and hashes are in `result.json` and `prediction-manifest.json` beside this report.",
            "",
        ]
    )
    return "\n".join(lines)


def run_scenario(
    scenario: Scenario,
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    require_hash(scenario.ply_path, scenario.ply_sha256, f"{scenario.scenario_id} Scene Snapshot")
    frames, (width, height), statuses = accepted_frames(scenario)
    arrays = _load_ply_arrays(str(scenario.ply_path))
    gaussian_count = int(len(arrays["means"]))
    device = torch.device("cuda")
    means = torch.from_numpy(arrays["means"]).to(device)
    quats = torch.from_numpy(arrays["quats"]).to(device)
    scales = torch.from_numpy(np.exp(arrays["scales"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-arrays["opacities"]))).to(device)
    colors = torch.from_numpy(arrays["sh_coeffs"]).to(device)
    focal = width / (2.0 * math.tan(math.radians(float(json.loads(scenario.frame_set_path.read_text(encoding="utf-8"))["horizontal_fov_degrees"])) / 2.0))
    intrinsics = torch.tensor(
        [[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
        device=device,
    )

    anchor_selected = torch.zeros(gaussian_count, dtype=torch.bool, device=device)
    hard_positive = torch.zeros(gaussian_count, dtype=torch.int16, device=device)
    hard_negative = torch.zeros(gaussian_count, dtype=torch.int16, device=device)
    hard_observed = torch.zeros(gaussian_count, dtype=torch.int16, device=device)
    positive = torch.zeros(gaussian_count, dtype=torch.float32, device=device)
    negative = torch.zeros(gaussian_count, dtype=torch.float32, device=device)
    observation_weight = torch.zeros(gaussian_count, dtype=torch.float32, device=device)
    observed_frames = torch.zeros(gaussian_count, dtype=torch.int16, device=device)
    hessian_diagonal = torch.zeros(gaussian_count, dtype=torch.float32, device=device)
    soft_records: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
    per_view: list[dict[str, Any]] = []

    torch.cuda.reset_peak_memory_stats(device)
    render_started = time.perf_counter()
    for frame in frames:
        support = support_region(frame.mask, args.support_margin_pixels)
        mask_t = torch.from_numpy(frame.mask).to(device=device, dtype=torch.bool)
        support_t = torch.from_numpy(support).to(device=device, dtype=torch.bool)
        viewmats = torch.linalg.inv(torch.from_numpy(frame.camera_to_world).to(device))[None]
        _, _, meta = gsplat.rasterization(
            means=means,
            quats=quats,
            scales=scales,
            opacities=opacities,
            colors=colors,
            viewmats=viewmats,
            Ks=intrinsics[None],
            width=width,
            height=height,
            sh_degree=arrays["sh_degree"],
            near_plane=NEAR_PLANE,
            far_plane=FAR_PLANE,
        )
        packed_ids, weights = gsplat.rasterize_top_contributing_gaussian_ids(
            meta["means2d"],
            meta["conics"],
            meta["opacities"],
            meta["isect_offsets"],
            meta["flatten_ids"],
            width,
            height,
            meta["tile_size"],
            args.top_k,
        )
        ids = global_contributor_ids(packed_ids[0], meta)
        weights = weights[0].float()
        top1 = ids[..., 0]
        top1_valid = top1 >= 0

        if frame.is_anchor:
            anchor_ids = top1[mask_t & top1_valid]
            if len(anchor_ids):
                anchor_selected[anchor_ids] = True

        top1_pos = top1[mask_t & support_t & top1_valid]
        top1_neg = top1[support_t & ~mask_t & top1_valid]
        pos_counts = torch.bincount(top1_pos, minlength=gaussian_count) if len(top1_pos) else torch.zeros(gaussian_count, dtype=torch.int64, device=device)
        neg_counts = torch.bincount(top1_neg, minlength=gaussian_count) if len(top1_neg) else torch.zeros(gaussian_count, dtype=torch.int64, device=device)
        hard_observed += ((pos_counts + neg_counts) > 0).to(torch.int16)
        hard_positive += (pos_counts > neg_counts).to(torch.int16)
        hard_negative += (neg_counts > pos_counts).to(torch.int16)

        support_expanded = support_t[..., None].expand_as(ids)
        mask_expanded = mask_t[..., None].expand_as(ids)
        positive_ids, positive_weights = extract_weighted(ids, weights, support_expanded & mask_expanded)
        negative_ids, negative_weights = extract_weighted(ids, weights, support_expanded & ~mask_expanded)
        all_ids, all_weights = extract_weighted(ids, weights, support_expanded)
        add_weighted(positive, positive_ids, positive_weights)
        add_weighted(negative, negative_ids, negative_weights)
        add_weighted(observation_weight, all_ids, all_weights)
        add_weighted(hessian_diagonal, all_ids, all_weights * all_weights)
        if len(all_ids):
            observed_frames[torch.unique(all_ids)] += 1

        ids_support = ids[support_t].clone()
        weights_support = weights[support_t].clone()
        valid_support = (ids_support >= 0) & torch.isfinite(weights_support) & (weights_support > 0)
        ids_support[~valid_support] = 0
        weights_support[~valid_support] = 0.0
        soft_records.append((ids_support, weights_support, mask_t[support_t].float()))
        per_view.append(
            {
                "frame_index": frame.frame_index,
                "view_id": frame.view_id,
                "anchor": frame.is_anchor,
                "mask_area_pixels": int(frame.mask.sum()),
                "support_area_pixels": int(support.sum()),
                "top1_inside_ids": int(torch.unique(top1_pos).numel()),
                "weighted_inside_ids": int(torch.unique(positive_ids).numel()),
                "weighted_support_ids": int(torch.unique(all_ids).numel()),
            }
        )
        del packed_ids, ids, weights, pos_counts, neg_counts, support_expanded, mask_expanded

    torch.cuda.synchronize(device)
    shared_render_seconds = time.perf_counter() - render_started

    hard_state = state_for_hard_votes(hard_positive, hard_negative, hard_observed, args.minimum_observed_views)
    contributor_state, contributor_ratio = state_for_weighted_evidence(
        positive,
        negative,
        observation_weight,
        observed_frames,
        args.minimum_observation_weight,
        args.minimum_observed_views,
        args.rejected_ratio,
        args.selected_ratio,
    )
    soft_started = time.perf_counter()
    soft_probability, soft_loss = optimize_soft_mask(
        initial=contributor_ratio,
        observation_weight=observation_weight,
        hessian_diagonal=hessian_diagonal,
        records=soft_records,
        iterations=args.soft_iterations,
        step=args.soft_step,
        prior_strength=args.soft_prior_strength,
    )
    torch.cuda.synchronize(device)
    soft_seconds = time.perf_counter() - soft_started
    soft_state, _ = state_for_weighted_evidence(
        soft_probability,
        1.0 - soft_probability,
        observation_weight,
        observed_frames,
        args.minimum_observation_weight,
        args.minimum_observed_views,
        args.rejected_ratio,
        args.selected_ratio,
    )
    current_state = torch.zeros(gaussian_count, dtype=torch.uint8, device=device)
    current_state[anchor_selected] = 1

    scenario_dir = output_dir / scenario.scenario_id
    scenario_dir.mkdir(parents=True)
    methods = {
        "current_top1_visibility": current_state,
        "hard_top1_vote": hard_state,
        "contributor_three_state": contributor_state,
        "soft_mask_fit": soft_state,
    }
    prediction_artifacts: dict[str, dict[str, Any]] = {}
    # This is the end of the prediction phase.  Do not load truth above here.
    for method, state in methods.items():
        artifact = scenario_dir / f"{method}.npz"
        np.savez_compressed(
            artifact,
            selected_stable_gaussian_ids=id_array_from_state(state, 1),
            rejected_stable_gaussian_ids=id_array_from_state(state, 2),
            # Everything else in the fixed Scene Snapshot is uncertain.
            gaussian_count=np.asarray([gaussian_count], dtype=np.uint32),
        )
        prediction_artifacts[method] = {
            "path": str(artifact.relative_to(output_dir)),
            "sha256": sha256(artifact),
            "selected_count": int(torch.count_nonzero(state == 1).item()),
            "rejected_count": int(torch.count_nonzero(state == 2).item()),
            "uncertain_count": int(torch.count_nonzero(state == 0).item()),
        }

    # Persist the complete prediction inventory before opening the score-only
    # Ground Truth file.  A scorer can independently re-evaluate these exact
    # ID outputs later without rerunning any lifting method.
    scenario_prediction_manifest = {
        "schema_version": 1,
        "prediction_before_ground_truth_scoring": True,
        "scenario_id": scenario.scenario_id,
        "scene_snapshot": {"path": str(scenario.ply_path), "sha256": scenario.ply_sha256, "gaussian_count": gaussian_count},
        "frame_set": {"path": str(scenario.frame_set_path), "sha256": sha256(scenario.frame_set_path)},
        "mask_set": {"path": str(scenario.mask_set_path), "sha256": sha256(scenario.mask_set_path)},
        "methods": prediction_artifacts,
    }
    write_json(scenario_dir / "prediction-manifest.json", scenario_prediction_manifest)

    controlled_means = arrays["means"] if scenario.scenario_id == "controlled_overlap" else None
    scores = {
        method: metrics_for_prediction(state.cpu().numpy(), scenario.truth_path, controlled_means)
        for method, state in methods.items()
    }
    peak_vram = int(torch.cuda.max_memory_allocated(device))
    result = {
        "scenario_id": scenario.scenario_id,
        "role": scenario.role,
        "scene_snapshot": {"path": str(scenario.ply_path), "sha256": scenario.ply_sha256, "gaussian_count": gaussian_count},
        "frame_set": {"path": str(scenario.frame_set_path), "sha256": sha256(scenario.frame_set_path)},
        "mask_set": {"path": str(scenario.mask_set_path), "sha256": sha256(scenario.mask_set_path), "statuses": statuses},
        "accepted_views": len(frames),
        "per_view_diagnostics": per_view,
        "timing": {
            "shared_rasterization_and_attribution_seconds": shared_render_seconds,
            "soft_mask_fit_seconds": soft_seconds,
            "soft_mask_fit_mean_squared_error_history": soft_loss,
            "combined_four_method_prototype_peak_gpu_vram_bytes": peak_vram,
        },
        "methods": {
            method: {"prediction": prediction_artifacts[method], "score": scores[method]}
            for method in METHOD_ORDER
        },
    }

    del soft_records, methods, means, quats, scales, opacities, colors
    torch.cuda.empty_cache()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", type=Path, default=REPO_ROOT / "docs" / "benchmarks" / "fixtures")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["controlled_overlap", "gift_box", "microwave", "clothes_rack"],
        choices=("controlled_overlap", "gift_box", "microwave", "clothes_rack"),
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--support-margin-pixels", type=int, default=24)
    parser.add_argument("--minimum-observed-views", type=int, default=2)
    parser.add_argument("--minimum-observation-weight", type=float, default=0.10)
    parser.add_argument("--selected-ratio", type=float, default=0.80)
    parser.add_argument("--rejected-ratio", type=float, default=0.20)
    parser.add_argument("--soft-iterations", type=int, default=24)
    parser.add_argument("--soft-step", type=float, default=0.35)
    parser.add_argument("--soft-prior-strength", type=float, default=0.05)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {args.output_dir}")
    if args.top_k < 1 or args.minimum_observed_views < 1 or args.support_margin_pixels < 0:
        raise ValueError("top-k, minimum observed views, and support margin must be positive")
    if not 0.0 <= args.rejected_ratio < args.selected_ratio <= 1.0:
        raise ValueError("require 0 <= rejected ratio < selected ratio <= 1")

    scenarios, shared_manifest = scenario_inputs(args.fixtures_root, set(args.scenarios))
    args.output_dir.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "prototype-result-not-product-selection-semantics",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "shared_input_manifest": shared_manifest,
        "prediction_before_ground_truth_scoring": True,
        "comparison_policy": {
            "top_k": args.top_k,
            "support_margin_pixels": args.support_margin_pixels,
            "minimum_observed_views": args.minimum_observed_views,
            "minimum_observation_weight": args.minimum_observation_weight,
            "selected_ratio": args.selected_ratio,
            "rejected_ratio": args.rejected_ratio,
            "soft_mask_fit": {
                "kind": "project-owned-SA3D-style-linear-soft-mask-fit",
                "iterations": args.soft_iterations,
                "step": args.soft_step,
                "contributor_evidence_prior_strength": args.soft_prior_strength,
            },
            "methods": {
                "current_top1_visibility": "Anchor View only; same-renderer top-1 contributor under the mask; selected versus uncertain only.",
                "hard_top1_vote": "Accepted views; unweighted top-1 footprint vote inside versus outside the shared mask within a prompt-derived support region.",
                "contributor_three_state": "Accepted views; alpha×transmittance top-K positive and negative evidence within the same support region.",
                "soft_mask_fit": "Contributor-weighted linear soft-mask fit over the same support and Mask Set, initialized by contributor evidence.",
            },
            "implementation_and_license_risk": {
                "current_top1_visibility": "Lowest implementation effort; intentionally incomplete visible-surface baseline.",
                "hard_top1_vote": "Low effort; no new dependency, but discards alpha×transmittance information.",
                "contributor_three_state": "Moderate service-side accumulation work; uses the already-installed gsplat contributor API and adds no model or code dependency.",
                "soft_mask_fit": "Additional numerical solver, configuration, and test burden; project-owned code over the same gsplat inputs, with no SA3D, FlashSplat, or new model dependency.",
            },
        },
        "runtime": {
            "torch": torch.__version__,
            "gsplat": getattr(gsplat, "__version__", "unknown"),
            "gpu": torch.cuda.get_device_name(torch.device("cuda")),
        },
        "scenarios": [],
    }
    for scenario in scenarios.values():
        result["scenarios"].append(run_scenario(scenario, args.output_dir, args))

    # The raw per-method files were persisted before this aggregate file holds
    # any Ground Truth score.  This manifest makes that boundary inspectable.
    prediction_manifest = {
        "schema_version": 1,
        "prediction_before_ground_truth_scoring": True,
        "shared_input_manifest": shared_manifest,
        "scenarios": [
            {
                "scenario_id": scenario["scenario_id"],
                "methods": {method: scenario["methods"][method]["prediction"] for method in METHOD_ORDER},
            }
            for scenario in result["scenarios"]
        ],
    }
    write_json(args.output_dir / "prediction-manifest.json", prediction_manifest)
    write_json(args.output_dir / "result.json", result)
    (args.output_dir / "report.md").write_text(markdown_report(result), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "result": str(args.output_dir / "result.json")}, indent=2))


if __name__ == "__main__":
    main()

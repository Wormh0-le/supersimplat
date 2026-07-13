#!/usr/bin/env python3
"""Derive contributor-visibility facts from one frozen Frame Set and Mask Set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import gsplat
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402
from renderers import FAR_PLANE, NEAR_PLANE  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def circular_azimuth_span(azimuth_degrees: list[float]) -> float:
    """The smallest circular arc containing the observed camera bearings."""
    if len(azimuth_degrees) < 2:
        return 0.0
    values = np.sort(np.asarray(azimuth_degrees, dtype=np.float64) % 360.0)
    gaps = np.diff(np.concatenate([values, values[:1] + 360.0]))
    return float(360.0 - gaps.max())


def camera_coverage(c2w: np.ndarray, center: np.ndarray) -> tuple[float, float]:
    offset = c2w[:3, 3] - center
    horizontal = float(np.linalg.norm(offset[:2]))
    azimuth = math.degrees(math.atan2(float(offset[1]), float(offset[0]))) % 360.0
    elevation = math.degrees(math.atan2(float(offset[2]), max(horizontal, 1e-8)))
    return azimuth, elevation


def per_mask_contributors(
    *,
    means: torch.Tensor,
    quats: torch.Tensor,
    scales: torch.Tensor,
    opacities: torch.Tensor,
    colors: torch.Tensor,
    sh_degree: int,
    c2w: np.ndarray,
    intrinsics: torch.Tensor,
    width: int,
    height: int,
    mask: np.ndarray,
    top_k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return global Stable IDs and alpha×T weights inside one accepted mask."""
    viewmats = torch.linalg.inv(torch.from_numpy(c2w).to(device=means.device))[None]
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
        sh_degree=sh_degree,
        near_plane=NEAR_PLANE,
        far_plane=FAR_PLANE,
    )
    ids, weights = gsplat.rasterize_top_contributing_gaussian_ids(
        meta["means2d"],
        meta["conics"],
        meta["opacities"],
        meta["isect_offsets"],
        meta["flatten_ids"],
        width,
        height,
        meta["tile_size"],
        top_k,
    )
    mask_t = torch.from_numpy(mask).to(device=means.device, dtype=torch.bool)
    selected_ids = ids[0][mask_t].reshape(-1)
    selected_weights = weights[0][mask_t].reshape(-1)
    valid = (selected_ids >= 0) & torch.isfinite(selected_weights) & (selected_weights > 0)
    selected_ids = selected_ids[valid].long()
    selected_weights = selected_weights[valid].float()
    # The contributor utility reports packed projected IDs; map those back to
    # immutable PLY-row Stable Gaussian IDs before anything is persisted.
    if meta["gaussian_ids"] is not None:
        selected_ids = meta["gaussian_ids"][selected_ids].long()
    return selected_ids.cpu().numpy().astype(np.int64), selected_weights.cpu().numpy().astype(np.float64)


def aggregate(ids: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(ids) == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    unique_ids, inverse = np.unique(ids, return_inverse=True)
    return unique_ids, np.bincount(inverse, weights=weights, minlength=len(unique_ids))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--frame-set-dir", type=Path, required=True)
    parser.add_argument("--mask-set-dir", type=Path, required=True)
    parser.add_argument("--selection-file", type=Path, required=True)
    parser.add_argument("--coverage-version", default="coverage-report-v1")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive")

    targets = json.loads((args.targets_root / "targets.json").read_text(encoding="utf-8"))
    target = next(item for item in targets["targets"] if item["id"] == args.target)
    frame_set_path = args.frame_set_dir / "frame-set.json"
    mask_set_path = args.mask_set_dir / "mask-set.json"
    frame_set = json.loads(frame_set_path.read_text(encoding="utf-8"))
    mask_set = json.loads(mask_set_path.read_text(encoding="utf-8"))
    selection = json.loads(args.selection_file.read_text(encoding="utf-8"))
    if frame_set["target_id"] != args.target or mask_set["target_id"] != args.target:
        raise RuntimeError("target does not match Frame Set and Mask Set")
    if mask_set["status"] != "frozen":
        raise RuntimeError("coverage requires a frozen Mask Set")
    if mask_set["frame_set"]["sha256"] != sha256(frame_set_path):
        raise RuntimeError("Mask Set does not bind to the supplied Frame Set")
    if selection["target_id"] != args.target:
        raise RuntimeError("selection file target does not match")
    if selection.get("expected_coverage_status") != "insufficient_coverage":
        raise RuntimeError("this coverage script expects an explicitly insufficient-coverage selection")
    source_ply_sha256 = sha256(args.ply)
    if source_ply_sha256 != targets["scene"]["ply_sha256"]:
        raise RuntimeError("source PLY digest does not match the frozen target manifest")

    track = mask_set["tracks"]
    if len(track) != 1 or track[0]["role"] != "include":
        raise RuntimeError("coverage fixture currently requires one primary include track")
    mask_frames = track[0]["frames"]
    frame_records = frame_set["frames"]
    if len(mask_frames) != len(frame_records):
        raise RuntimeError("Mask Set does not cover every Frame Set view")
    accepted_frame_indexes: set[int] = set()
    not_found_views: list[dict] = []
    for mask_frame, frame in zip(mask_frames, frame_records, strict=True):
        if mask_frame["status"] not in {"accepted", "not_found"}:
            raise RuntimeError("coverage fixture supports only accepted and not_found Mask Set outcomes")
        if mask_frame["frame_index"] != frame["frame_index"] or mask_frame["view_id"] != frame["candidate_id"]:
            raise RuntimeError("Mask Set and Frame Set view order do not match")
        if mask_frame["status"] == "accepted":
            accepted_frame_indexes.add(frame["frame_index"])
        else:
            not_found_views.append(
                {
                    "view_id": frame["candidate_id"],
                    "frame_index": frame["frame_index"],
                    "reason": mask_frame.get("reason", "no reliable target mask"),
                }
            )
    if not accepted_frame_indexes:
        raise RuntimeError("coverage requires at least one accepted Mask Set frame")

    masks_path = args.mask_set_dir / "masks.npz"
    masks = np.load(masks_path)["masks"].astype(bool)
    width, height = frame_set["resolution"]
    if masks.shape != (len(frame_records), height, width):
        raise RuntimeError(f"unexpected Mask Set tensor shape: {masks.shape}")

    output_dir = args.frame_set_dir / args.coverage_version
    if output_dir.exists():
        raise RuntimeError(f"coverage output already exists: {output_dir}")

    arrays = _load_ply_arrays(str(args.ply))
    device = torch.device("cuda")
    means = torch.from_numpy(arrays["means"]).to(device)
    quats = torch.from_numpy(arrays["quats"]).to(device)
    scales = torch.from_numpy(np.exp(arrays["scales"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-arrays["opacities"]))).to(device)
    colors = torch.from_numpy(arrays["sh_coeffs"]).to(device)
    fov_degrees = float(frame_set["horizontal_fov_degrees"])
    focal = width / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))
    intrinsics = torch.tensor(
        [[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
        device=device,
    )
    seed_path = args.targets_root / args.target / "seed-region.npz"
    seed_ids = np.load(seed_path)["stable_gaussian_ids"].astype(np.int64)
    seed_set = set(seed_ids.tolist())

    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    total_weights: dict[int, float] = {}
    visible_frame_counts: dict[int, int] = {}
    seen_ids: set[int] = set()
    per_view: list[dict] = []
    azimuths: list[float] = []
    elevations: list[float] = []
    seed_center = np.asarray(json.loads((args.targets_root / "seed-regions.json").read_text())["targets"][args.target]["center"])
    for frame, mask in zip(frame_records, masks, strict=True):
        if frame["frame_index"] not in accepted_frame_indexes:
            continue
        ids, weights = per_mask_contributors(
            means=means,
            quats=quats,
            scales=scales,
            opacities=opacities,
            colors=colors,
            sh_degree=arrays["sh_degree"],
            c2w=np.asarray(frame["camera_to_world"], dtype=np.float32),
            intrinsics=intrinsics,
            width=width,
            height=height,
            mask=mask,
            top_k=args.top_k,
        )
        unique_ids, unique_weights = aggregate(ids, weights)
        view_id_set = set(unique_ids.tolist())
        new_ids = view_id_set - seen_ids
        new_weight = float(sum(weight for stable_id, weight in zip(unique_ids.tolist(), unique_weights.tolist(), strict=True) if stable_id in new_ids))
        for stable_id, weight in zip(unique_ids.tolist(), unique_weights.tolist(), strict=True):
            total_weights[stable_id] = total_weights.get(stable_id, 0.0) + weight
            visible_frame_counts[stable_id] = visible_frame_counts.get(stable_id, 0) + 1
        seen_ids.update(view_id_set)
        azimuth, elevation = camera_coverage(np.asarray(frame["camera_to_world"], dtype=np.float32), seed_center)
        azimuths.append(azimuth)
        elevations.append(elevation)
        per_view.append(
            {
                "view_id": frame["candidate_id"],
                "frame_index": frame["frame_index"],
                "mask_area_pixels": int(mask.sum()),
                "contributing_stable_gaussians": int(len(unique_ids)),
                "new_stable_gaussians": int(len(new_ids)),
                "new_contribution_weight": new_weight,
                "cumulative_stable_gaussians": int(len(seen_ids)),
                "observed_seed_gaussians": int(len(view_id_set & seed_set)),
                "azimuth_degrees": azimuth,
                "elevation_degrees": elevation,
            }
        )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started

    observed_ids = np.asarray(sorted(total_weights), dtype=np.int64)
    observed_weights = np.asarray([total_weights[int(stable_id)] for stable_id in observed_ids], dtype=np.float64)
    observed_frame_counts = np.asarray([visible_frame_counts[int(stable_id)] for stable_id in observed_ids], dtype=np.int16)
    observed_seed_ids = np.intersect1d(observed_ids, seed_ids, assume_unique=True)
    unseen_seed_ids = np.setdiff1d(seed_ids, observed_ids, assume_unique=False)
    output_dir.mkdir(parents=True)
    artifact_path = output_dir / "observed-contributors.npz"
    np.savez_compressed(
        artifact_path,
        stable_gaussian_ids=observed_ids,
        contribution_weights=observed_weights.astype(np.float32),
        visible_frame_counts=observed_frame_counts,
        seed_region_observed_stable_gaussian_ids=observed_seed_ids,
        seed_region_unobserved_stable_gaussian_ids=unseen_seed_ids,
    )

    candidate_manifest_path = (
        args.targets_root
        / args.target
        / f"generated-view-candidates-{selection['source_candidate_config']}"
        / "candidates.json"
    )
    candidate_manifest = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    rejections = [
        {"view_id": view_id, "stage": "quality_review", "reason": reason}
        for view_id, reason in selection.get("preliminary_rejections", {}).items()
    ]
    report = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "reliable contributor-visibility facts; not Gaussian selection labels",
        "coverage_report_version": args.coverage_version,
        "target_id": args.target,
        "source_ply": {
            "path": str(args.ply),
            "sha256": source_ply_sha256,
            "gaussian_count": int(len(arrays["means"])),
        },
        "frame_set": {
            "path": relative_to_or_absolute(frame_set_path, args.targets_root),
            "sha256": sha256(frame_set_path),
            "version": frame_set["frame_set_version"],
        },
        "mask_set": {
            "path": relative_to_or_absolute(mask_set_path, args.targets_root),
            "sha256": sha256(mask_set_path),
            "masks_sha256": sha256(masks_path),
            "version": mask_set["mask_set_version"],
        },
        "contributor_rasterization": {
            "backend": "gsplat",
            "top_k": args.top_k,
            "near_plane": NEAR_PLANE,
            "far_plane": FAR_PLANE,
            "stable_id_mapping": "packed projection IDs are mapped through meta.gaussian_ids to immutable PLY-row Stable Gaussian IDs",
        },
        "attempted_views": len(candidate_manifest["candidates"]),
        "accepted_views": len(accepted_frame_indexes),
        "not_found_views": not_found_views,
        "rejected_views": rejections,
        "candidate_selection": {
            "path": relative_to_or_absolute(args.selection_file, args.targets_root),
            "sha256": sha256(args.selection_file),
            "candidate_manifest": relative_to_or_absolute(candidate_manifest_path, args.targets_root),
            "candidate_manifest_sha256": sha256(candidate_manifest_path),
        },
        "contributor_observation": {
            "artifact": artifact_path.name,
            "artifact_sha256": sha256(artifact_path),
            "observed_stable_gaussians": int(len(observed_ids)),
            "total_contribution_weight": float(observed_weights.sum()),
            "seed_region_candidate_gaussians": int(len(seed_ids)),
            "observed_seed_region_gaussians": int(len(observed_seed_ids)),
            "unobserved_seed_region_gaussians": int(len(unseen_seed_ids)),
            "note": "The Seed Region is only a framing aid. Its observation fraction is reported but cannot by itself establish whole-object coverage.",
        },
        "incremental_coverage_by_view": per_view,
        "effective_azimuth_elevation_coverage": {
            "azimuth_degrees_in_frame_order": azimuths,
            "elevation_degrees_in_frame_order": elevations,
            "circular_azimuth_span_degrees": circular_azimuth_span(azimuths),
            "minimum_elevation_degrees": float(min(elevations)),
            "maximum_elevation_degrees": float(max(elevations)),
        },
        "status_value": "insufficient_coverage",
        "status_reason": (
            f"{len(accepted_frame_indexes)} accepted masks remain after quality rejection of "
            f"{len(rejections)} planned candidates and {len(not_found_views)} not-found Frame Set views. "
            "They do not provide a reliable full-orbit observation, so unobserved object regions must remain uncertain."
        ),
        "timing": {
            "contributor_analysis_seconds": elapsed,
            "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
        },
    }
    (output_dir / "coverage-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

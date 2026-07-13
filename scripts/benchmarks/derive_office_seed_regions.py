#!/usr/bin/env python3
"""Derive camera-framing Seed Regions from frozen office Anchor masks."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import gsplat
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order])
    return float(sorted_values[np.searchsorted(cumulative, q * cumulative[-1])])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    target_manifest = json.loads((args.targets_root / "targets.json").read_text())
    arrays = _load_ply_arrays(str(args.ply))
    device = torch.device("cuda")
    means = torch.from_numpy(arrays["means"]).to(device)
    quats = torch.from_numpy(arrays["quats"]).to(device)
    scales = torch.from_numpy(np.exp(arrays["scales"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-arrays["opacities"]))).to(device)
    sh_coeffs = torch.from_numpy(arrays["sh_coeffs"]).to(device)

    output = {"schema_version": 1, "top_k": args.top_k, "retained_contribution": 0.95, "targets": {}}
    for target in target_manifest["targets"]:
        target_id = target["id"]
        anchor = target["anchor_candidate"]
        camera_data = json.loads((args.targets_root / anchor["camera_manifest"]).read_text())
        c2w = np.asarray(camera_data["frames"][0]["camera_to_world"], dtype=np.float32)
        size = int(camera_data["size"])
        fov = math.radians(float(camera_data["horizontal_fov_degrees"]))
        focal = size / (2.0 * math.tan(fov / 2.0))
        K = torch.tensor(
            [[[focal, 0.0, size / 2.0], [0.0, focal, size / 2.0], [0.0, 0.0, 1.0]]],
            dtype=torch.float32,
            device=device,
        )
        view = torch.linalg.inv(torch.from_numpy(c2w).to(device))[None]
        _, _, meta = gsplat.rasterization(
            means,
            quats,
            scales,
            opacities,
            sh_coeffs,
            view,
            K,
            size,
            size,
            near_plane=0.01,
            far_plane=100.0,
            sh_degree=arrays["sh_degree"],
            render_mode="RGB",
        )
        ids, weights = gsplat.rasterize_top_contributing_gaussian_ids(
            meta["means2d"],
            meta["conics"],
            meta["opacities"],
            meta["isect_offsets"],
            meta["flatten_ids"],
            size,
            size,
            meta["tile_size"],
            args.top_k,
        )
        mask = np.load(args.targets_root / target["anchor_mask"]["mask_file"])["masks"][0]
        mask_t = torch.from_numpy(mask).to(device)
        selected_ids = ids[0][mask_t].reshape(-1)
        selected_weights = weights[0][mask_t].reshape(-1)
        valid = selected_ids >= 0
        selected_ids = selected_ids[valid].long()
        selected_weights = selected_weights[valid].float()
        # Contributor kernels return indices into packed projected Gaussians.
        # Convert them back to the immutable PLY/global Gaussian row IDs.
        if meta["gaussian_ids"] is not None:
            selected_ids = meta["gaussian_ids"][selected_ids].long()
        totals = torch.zeros(len(means), dtype=torch.float32, device=device)
        totals.scatter_add_(0, selected_ids, selected_weights)
        nonzero = torch.nonzero(totals > 0, as_tuple=False).squeeze(1)
        ranked_weights, rank_order = torch.sort(totals[nonzero], descending=True)
        ranked_ids = nonzero[rank_order]
        cumulative = torch.cumsum(ranked_weights, dim=0)
        keep_count = int(torch.searchsorted(cumulative, cumulative[-1] * 0.95).item()) + 1
        seed_ids = ranked_ids[:keep_count].cpu().numpy().astype(np.int64)
        seed_weights = ranked_weights[:keep_count].cpu().numpy().astype(np.float64)
        xyz = arrays["means"][seed_ids]
        center = np.average(xyz, axis=0, weights=seed_weights)
        q05 = [weighted_quantile(xyz[:, axis], seed_weights, 0.05) for axis in range(3)]
        q95 = [weighted_quantile(xyz[:, axis], seed_weights, 0.95) for axis in range(3)]
        extent = np.asarray(q95) - np.asarray(q05)
        np.savez_compressed(
            args.targets_root / target_id / "seed-region.npz",
            stable_gaussian_ids=seed_ids,
            contribution_weights=seed_weights.astype(np.float32),
        )
        output["targets"][target_id] = {
            "mask_pixels": int(mask.sum()),
            "contributing_gaussians": int(len(nonzero)),
            "retained_gaussians": int(len(seed_ids)),
            "center": center.tolist(),
            "weighted_q05": q05,
            "weighted_q95": q95,
            "extent": extent.tolist(),
        }
        print(target_id, output["targets"][target_id])

    (args.targets_root / "seed-regions.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

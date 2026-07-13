#!/usr/bin/env python3
"""Materialize exact shared Frame/Mask/Coverage fixtures for controlled overlap.

The controlled scene deliberately does not use SAM.  Its masks are analytical
top-contributor instance masks derived from the same fixed Gaussian fixture and
are therefore a method-independent input for lifting comparisons.
"""

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
from PIL import Image, ImageDraw

from generate_controlled_overlap import PER_OBJECT, SH_C0, make_fixture


CAMERAS = (
    {
        "candidate_id": "anchor-front",
        "category": "anchor",
        "eye": (0.0, 0.0, -3.2),
        "target": (0.0, 0.0, 0.25),
    },
    {
        "candidate_id": "side-right",
        "category": "ring",
        "eye": (3.2, 0.0, 0.31),
        "target": (0.0, 0.0, 0.31),
    },
    {
        "candidate_id": "side-left",
        "category": "ring",
        "eye": (-3.2, 0.0, 0.31),
        "target": (0.0, 0.0, 0.31),
    },
    {
        "candidate_id": "rear",
        "category": "ring",
        "eye": (0.0, 0.0, 3.2),
        "target": (0.0, 0.0, 0.25),
    },
)
TOP_K = 8
MASK_WEIGHT_THRESHOLD = 0.01


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def camera_to_world(eye: tuple[float, float, float], target: tuple[float, float, float]) -> np.ndarray:
    eye_array = np.asarray(eye, dtype=np.float32)
    forward = normalize(np.asarray(target, dtype=np.float32) - eye_array)
    world_up = np.asarray((0.0, 1.0, 0.0), dtype=np.float32)
    right = normalize(np.cross(world_up, forward))
    down = normalize(np.cross(forward, right))

    result = np.eye(4, dtype=np.float32)
    result[:3, 0] = right
    result[:3, 1] = down
    result[:3, 2] = forward
    result[:3, 3] = eye_array
    return result


def make_contact_sheet(records: list[dict], root: Path, output: Path) -> None:
    thumb = 256
    label_height = 30
    sheet = Image.new("RGB", (2 * thumb, 2 * (thumb + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        image = Image.open(root / record["overlay"]).convert("RGB")
        image.thumbnail((thumb, thumb))
        x = (index % 2) * thumb
        y = (index // 2) * (thumb + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + thumb + 6), record["candidate_id"], fill="white")
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    if args.size <= 0:
        raise ValueError("--size must be positive")

    fixture_dir = args.fixture_dir
    controlled_manifest_path = fixture_dir / "controlled_front_back_overlap.json"
    source_ply_path = fixture_dir / "controlled_front_back_overlap.ply"
    truth_path = fixture_dir / "controlled_front_back_overlap_ground_truth.npz"
    controlled = json.loads(controlled_manifest_path.read_text(encoding="utf-8"))
    if sha256(source_ply_path) != controlled["files"][source_ply_path.name]["sha256"]:
        raise RuntimeError("controlled PLY hash does not match the generator manifest")
    if sha256(truth_path) != controlled["files"][truth_path.name]["sha256"]:
        raise RuntimeError("controlled Ground Truth hash does not match the generator manifest")

    frame_set_dir = fixture_dir / "frame-set-v1"
    mask_set_dir = frame_set_dir / "mask-set-v1"
    coverage_dir = frame_set_dir / "coverage-report-v1"
    if frame_set_dir.exists():
        raise FileExistsError(f"refusing to overwrite Frame Set: {frame_set_dir}")
    (frame_set_dir / "frames").mkdir(parents=True)
    (mask_set_dir / "overlays").mkdir(parents=True)
    coverage_dir.mkdir(parents=True)

    fixture = make_fixture()
    if fixture["means"].shape[0] != controlled["gaussianCount"]:
        raise RuntimeError("generated controlled fixture count differs from the frozen manifest")
    device = torch.device("cuda")
    means = torch.from_numpy(fixture["means"]).to(device)
    quats = torch.from_numpy(fixture["rotation"]).to(device)
    scales = torch.from_numpy(np.exp(fixture["log_scale"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-fixture["opacity"]))).to(device)
    colors = torch.from_numpy(np.clip(0.5 + SH_C0 * fixture["sh_dc"], 0.0, 1.0)).to(device)
    fov = math.radians(float(controlled["initialCamera"]["verticalFovDegrees"]))
    focal = 0.5 * args.size / math.tan(0.5 * fov)
    intrinsics = torch.tensor(
        [[[focal, 0.0, args.size / 2.0], [0.0, focal, args.size / 2.0], [0.0, 0.0, 1.0]]],
        dtype=torch.float32,
        device=device,
    )
    background = torch.tensor([[0.04, 0.04, 0.04]], dtype=torch.float32, device=device)

    frames: list[dict] = []
    masks: list[np.ndarray] = []
    observed_ids: set[int] = set()
    started = time.perf_counter()
    for frame_index, spec in enumerate(CAMERAS):
        c2w = camera_to_world(spec["eye"], spec["target"])
        w2c = np.linalg.inv(c2w).astype(np.float32)
        rgb, _, meta = gsplat.rasterization(
            means,
            quats,
            scales,
            opacities,
            colors,
            torch.from_numpy(w2c)[None, ...].to(device),
            intrinsics,
            args.size,
            args.size,
            near_plane=0.01,
            far_plane=20.0,
            backgrounds=background,
            render_mode="RGB",
        )
        packed_ids, weights = gsplat.rasterize_top_contributing_gaussian_ids(
            meta["means2d"],
            meta["conics"],
            meta["opacities"],
            meta["isect_offsets"],
            meta["flatten_ids"],
            args.size,
            args.size,
            meta["tile_size"],
            TOP_K,
        )
        ids = packed_ids[0].long()
        weights = weights[0].float()
        target_weight = torch.where((ids >= 0) & (ids < PER_OBJECT), weights, 0.0).sum(dim=-1)
        distractor_weight = torch.where(ids >= PER_OBJECT, weights, 0.0).sum(dim=-1)
        mask = ((target_weight > MASK_WEIGHT_THRESHOLD) & (target_weight >= distractor_weight)).cpu().numpy()
        visible_target_ids = ids[(ids >= 0) & (ids < PER_OBJECT) & (weights > MASK_WEIGHT_THRESHOLD)]
        observed_ids.update(int(value) for value in torch.unique(visible_target_ids).cpu().tolist())

        pixels = rgb[0].clamp(0.0, 1.0).mul(255).byte().cpu().numpy()
        frame_file = f"frames/{frame_index:03d}-{spec['candidate_id']}.png"
        frame_path = frame_set_dir / frame_file
        Image.fromarray(pixels, mode="RGB").save(frame_path)
        overlay = pixels.astype(np.float32)
        overlay[mask] = overlay[mask] * 0.45 + np.asarray([30, 220, 90], dtype=np.float32) * 0.55
        overlay_file = f"overlays/{frame_index:03d}-{spec['candidate_id']}.png"
        Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8), mode="RGB").save(mask_set_dir / overlay_file)
        masks.append(mask)
        frames.append(
            {
                "frame_index": frame_index,
                "candidate_id": spec["candidate_id"],
                "category": spec["category"],
                "file": frame_file,
                "sha256": sha256(frame_path),
                "camera_to_world": c2w.tolist(),
                "eye": list(spec["eye"]),
                "target": list(spec["target"]),
                "source": "deterministic-controlled-render",
            }
        )

    elapsed = time.perf_counter() - started
    masks_array = np.stack(masks, axis=0)
    masks_path = mask_set_dir / "masks.npz"
    np.savez_compressed(masks_path, masks=masks_array)
    observed_array = np.asarray(sorted(observed_ids), dtype=np.uint32)
    observed_path = coverage_dir / "observed-target-contributors.npz"
    np.savez_compressed(observed_path, stable_gaussian_ids=observed_array)

    frame_set_path = frame_set_dir / "frame-set.json"
    frame_set = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "shared deterministic Frame Set for controlled front/back-overlap lifting",
        "frame_set_version": "frame-set-v1",
        "scene": {
            "ply": f"../{source_ply_path.name}",
            "sha256": sha256(source_ply_path),
            "gaussian_count": int(controlled["gaussianCount"]),
        },
        "resolution": [args.size, args.size],
        "horizontal_fov_degrees": float(controlled["initialCamera"]["verticalFovDegrees"]),
        "frames": frames,
    }
    frame_set_path.write_text(json.dumps(frame_set, indent=2) + "\n", encoding="utf-8")

    mask_set_path = mask_set_dir / "mask-set.json"
    mask_set = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "shared exact visible-target masks for controlled lifting comparison; not SAM output",
        "mask_set_version": "mask-set-v1",
        "frame_set": {"path": "../frame-set.json", "sha256": sha256(frame_set_path)},
        "ground_truth": {"path": f"../../{truth_path.name}", "sha256": sha256(truth_path)},
        "mask_derivation": {
            "kind": "same-renderer-top-contributor-instance-mask",
            "target_stable_id_range": [0, PER_OBJECT - 1],
            "top_k": TOP_K,
            "minimum_target_contribution_weight": MASK_WEIGHT_THRESHOLD,
            "rule": "target contribution must be at least the distractor contribution at the pixel",
        },
        "masks": {"path": masks_path.name, "sha256": sha256(masks_path), "shape": list(masks_array.shape)},
        "frames": [
            {
                "candidate_id": frame["candidate_id"],
                "frame_index": frame["frame_index"],
                "frame_sha256": frame["sha256"],
                "status": "accepted",
                "binary_mask_index": frame["frame_index"],
                "mask_area_pixels": int(mask.sum()),
                "mask_area_fraction": float(mask.mean()),
                "overlay": f"overlays/{frame['frame_index']:03d}-{frame['candidate_id']}.png",
            }
            for frame, mask in zip(frames, masks, strict=True)
        ],
        "timing": {
            "render_and_attribution_seconds": elapsed,
            "peak_vram_bytes": int(torch.cuda.max_memory_allocated(device)),
            "runtime": {"torch": torch.__version__, "gpu": torch.cuda.get_device_name(device)},
        },
    }
    mask_set_path.write_text(json.dumps(mask_set, indent=2) + "\n", encoding="utf-8")
    make_contact_sheet(mask_set["frames"], mask_set_dir, mask_set_dir / "overlay-contact-sheet.png")

    coverage_path = coverage_dir / "coverage-report.json"
    coverage = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "exact target-contributor observation facts for the controlled lifting fixture",
        "coverage_report_version": "coverage-report-v1",
        "scene": {"ply": f"../../{source_ply_path.name}", "sha256": sha256(source_ply_path)},
        "frame_set": {"path": "../frame-set.json", "sha256": sha256(frame_set_path)},
        "mask_set": {"path": "../mask-set-v1/mask-set.json", "sha256": sha256(mask_set_path)},
        "target_stable_id_range": [0, PER_OBJECT - 1],
        "observed_target_contributors": {
            "artifact": observed_path.name,
            "sha256": sha256(observed_path),
            "count": int(len(observed_array)),
            "total_target_gaussians": PER_OBJECT,
            "fraction": float(len(observed_array) / PER_OBJECT),
        },
        "status_value": "complete_target_observation" if len(observed_array) == PER_OBJECT else "insufficient_coverage",
        "timing": mask_set["timing"],
    }
    coverage_path.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "frame_set": str(frame_set_path),
                "mask_set": str(mask_set_path),
                "coverage_report": str(coverage_path),
                "observed_target_gaussians": int(len(observed_array)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

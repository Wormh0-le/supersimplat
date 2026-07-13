#!/usr/bin/env python3
"""Render deterministic low-resolution office views for benchmark target review."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER_ROOT = REPO_ROOT / "thirdparty" / "splat_analyzer"
sys.path.insert(0, str(ANALYZER_ROOT))

from config import PipelineConfig  # noqa: E402
from render_cameras import _generate_camera_positions, _load_ply_arrays  # noqa: E402
from renderers import get_renderer  # noqa: E402


def make_contact_sheet(frames: list[Path], output: Path, size: int) -> None:
    columns = 4
    label_height = 28
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * size, rows * (size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, frame_path in enumerate(frames):
        image = Image.open(frame_path).convert("RGB")
        x = (index % columns) * size
        y = (index // columns) * (size + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + size + 6), frame_path.stem, fill="white")
    sheet.save(output)


def z_up_ring_poses(position: np.ndarray) -> tuple[list[np.ndarray], list[int]]:
    poses: list[np.ndarray] = []
    for elevation_degrees in (-12.0, 8.0):
        elevation = math.radians(elevation_degrees)
        for azimuth_degrees in range(0, 360, 45):
            azimuth = math.radians(azimuth_degrees)
            forward = np.array(
                [
                    math.cos(elevation) * math.cos(azimuth),
                    math.cos(elevation) * math.sin(azimuth),
                    math.sin(elevation),
                ],
                dtype=np.float32,
            )
            right = np.cross(forward, np.array([0.0, 0.0, 1.0], dtype=np.float32))
            right /= np.linalg.norm(right)
            down = np.cross(forward, right)
            c2w = np.eye(4, dtype=np.float32)
            c2w[:3, 0] = right
            c2w[:3, 1] = down
            c2w[:3, 2] = forward
            c2w[:3, 3] = position
            poses.append(c2w)
    return poses, [0] * len(poses)


def z_up_pose(position: np.ndarray, forward: np.ndarray) -> np.ndarray:
    forward = forward.astype(np.float32)
    forward /= np.linalg.norm(forward)
    up_reference = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(float(np.dot(forward, up_reference))) > 0.999:
        up_reference = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    right = np.cross(forward, up_reference)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    c2w = np.eye(4, dtype=np.float32)
    c2w[:3, 0] = right
    c2w[:3, 1] = down
    c2w[:3, 2] = forward
    c2w[:3, 3] = position
    return c2w


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=384)
    parser.add_argument("--horizontal-fov", type=float, default=100.0)
    parser.add_argument(
        "--camera-position",
        type=float,
        nargs=3,
        metavar=("X", "Y", "Z"),
        help="Use an explicit Z-up camera position instead of the deterministic sample.",
    )
    parser.add_argument(
        "--forward",
        type=float,
        nargs=3,
        metavar=("X", "Y", "Z"),
        help="Render one view in this PLY-space direction instead of a ring.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = args.output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    arrays = _load_ply_arrays(str(args.ply))
    means = arrays["means"]
    cfg = PipelineConfig(
        width=args.size,
        height=args.size,
        renderer="gsplat",
        n_positions=4,
        n_azimuth=4,
        n_elevation=1,
        bbox_pct_lo=1.0,
        bbox_pct_hi=99.0,
        seed=20260712,
    )
    sampled_positions, sampled_targets = _generate_camera_positions(
        means, cfg.n_positions, cfg
    )
    # The first deterministic sample was visually verified to be inside the room;
    # callers can override it with a known-good scene coordinate.
    positions = sampled_positions[:1].copy()
    if args.camera_position is None:
        positions[0, 2] = 1.6
    else:
        positions[0] = np.asarray(args.camera_position, dtype=np.float32)
    targets = sampled_targets[:1]
    if args.forward is None:
        poses, position_indices = z_up_ring_poses(positions[0])
    else:
        poses = [z_up_pose(positions[0], np.asarray(args.forward, dtype=np.float32))]
        position_indices = [0]

    renderer = get_renderer(cfg.renderer)
    gaussians = renderer.prepare(arrays)
    fov_x = math.radians(args.horizontal_fov)
    focal = args.size / (2.0 * math.tan(fov_x / 2.0))
    intrinsics = torch.tensor(
        [[focal, 0.0, args.size / 2.0], [0.0, focal, args.size / 2.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
        device=renderer.device,
    )
    w2c = torch.linalg.inv(
        torch.tensor(np.stack(poses), dtype=torch.float32, device=renderer.device)
    )
    frame_paths: list[Path] = []
    frames_metadata = []
    for start in range(0, len(poses), 2):
        batch = renderer.render_rgb(
            gaussians, w2c[start : start + 2], intrinsics, args.size, args.size
        )
        for offset, pixels in enumerate(batch):
            index = start + offset
            path = frames_dir / f"office_overview_{index:02d}.png"
            Image.fromarray(pixels, mode="RGB").save(path)
            frame_paths.append(path)
            frames_metadata.append(
                {
                    "file": str(path.relative_to(args.output_dir)),
                    "position_index": int(position_indices[index]),
                    "camera_to_world": poses[index].tolist(),
                }
            )

    make_contact_sheet(frame_paths, args.output_dir / "contact-sheet.png", args.size)
    metadata = {
        "source": str(args.ply),
        "seed": cfg.seed,
        "size": args.size,
        "horizontal_fov_degrees": args.horizontal_fov,
        "robust_bounds_percentiles": [cfg.bbox_pct_lo, cfg.bbox_pct_hi],
        "camera_positions": positions.tolist(),
        "look_targets": targets.tolist(),
        "frames": frames_metadata,
    }
    (args.output_dir / "cameras.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output_dir / "contact-sheet.png")


if __name__ == "__main__":
    main()

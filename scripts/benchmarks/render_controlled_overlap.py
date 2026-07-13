#!/usr/bin/env python3
"""Render diagnostic front and side views of the controlled overlap fixture."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import gsplat

from generate_controlled_overlap import SH_C0, make_fixture


def normalize(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def world_to_camera(eye: tuple[float, float, float], target: tuple[float, float, float]) -> np.ndarray:
    eye_array = np.asarray(eye, dtype=np.float32)
    forward = normalize(np.asarray(target, dtype=np.float32) - eye_array)
    world_up = np.asarray((0.0, 1.0, 0.0), dtype=np.float32)
    right = normalize(np.cross(world_up, forward))
    down = normalize(np.cross(forward, right))

    camera_to_world = np.eye(4, dtype=np.float32)
    camera_to_world[:3, 0] = right
    camera_to_world[:3, 1] = down
    camera_to_world[:3, 2] = forward
    camera_to_world[:3, 3] = eye_array
    return np.linalg.inv(camera_to_world).astype(np.float32)


def render(output: Path, eye: tuple[float, float, float], target: tuple[float, float, float], size: int) -> None:
    fixture = make_fixture()
    device = torch.device("cuda")
    means = torch.from_numpy(fixture["means"]).to(device)
    quats = torch.from_numpy(fixture["rotation"]).to(device)
    scales = torch.from_numpy(np.exp(fixture["log_scale"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-fixture["opacity"]))).to(device)
    colors = torch.from_numpy(np.clip(0.5 + SH_C0 * fixture["sh_dc"], 0.0, 1.0)).to(device)

    fov = math.radians(42.0)
    focal = 0.5 * size / math.tan(0.5 * fov)
    intrinsics = torch.tensor(
        [[[focal, 0.0, size / 2.0], [0.0, focal, size / 2.0], [0.0, 0.0, 1.0]]],
        dtype=torch.float32,
        device=device,
    )
    view = torch.from_numpy(world_to_camera(eye, target))[None, ...].to(device)
    background = torch.tensor([[0.04, 0.04, 0.04]], dtype=torch.float32, device=device)

    rgb, _, _ = gsplat.rasterization(
        means,
        quats,
        scales,
        opacities,
        colors,
        view,
        intrinsics,
        size,
        size,
        near_plane=0.01,
        far_plane=20.0,
        backgrounds=background,
        render_mode="RGB",
    )
    pixels = (rgb[0].clamp(0.0, 1.0).mul(255).byte().cpu().numpy())
    Image.fromarray(pixels, mode="RGB").save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    render(args.output_dir / "front.png", (0.0, 0.0, -3.2), (0.0, 0.0, 0.25), args.size)
    render(args.output_dir / "side.png", (3.2, 0.0, 0.31), (0.0, 0.0, 0.31), args.size)


if __name__ == "__main__":
    main()

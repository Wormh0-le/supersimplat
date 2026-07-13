#!/usr/bin/env python3
"""Render policy-shaped Generated View candidates around frozen Seed Regions.

This creates review artifacts only.  It does not accept views, run SAM3.1, or
change the immutable Anchor Mask; those decisions happen in the quality-gate
step after reviewing the candidates.
"""

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
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402
from renderers import get_renderer  # noqa: E402


POLICY_VERSION = "generated-view-policy-v1"
PREVIEW_CONFIG_VERSION = "preview-512-v2-anchor-radius"


def normalize(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length < 1e-8:
        raise ValueError("camera forward vector has zero length")
    return vector / length


def look_at_c2w(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return OpenCV-convention c2w: X right, Y down, Z forward."""
    forward = normalize(target - eye)
    world_up = np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(float(np.dot(forward, world_up))) > 0.999:
        world_up = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    right = normalize(np.cross(forward, world_up))
    down = np.cross(forward, right)
    c2w = np.eye(4, dtype=np.float32)
    c2w[:3, 0] = right
    c2w[:3, 1] = down
    c2w[:3, 2] = forward
    c2w[:3, 3] = eye
    return c2w


def preflight_seed_projection(
    seed_xyz: np.ndarray, c2w: np.ndarray, focal: float, size: int, seed_radius: float
) -> dict:
    w2c = np.linalg.inv(c2w)
    homogeneous = np.concatenate(
        [seed_xyz, np.ones((len(seed_xyz), 1), dtype=np.float32)], axis=1
    )
    camera_xyz = homogeneous @ w2c.T
    depth = camera_xyz[:, 2]
    in_front = depth > 0.01
    u = focal * camera_xyz[:, 0] / np.maximum(depth, 1e-8) + size / 2.0
    v = focal * camera_xyz[:, 1] / np.maximum(depth, 1e-8) + size / 2.0
    margin = size * 0.03
    in_frame = (
        in_front
        & (u >= margin)
        & (u < size - margin)
        & (v >= margin)
        & (v < size - margin)
    )
    visible_fraction = float(in_frame.mean())
    center_depth = float((w2c @ np.append(seed_xyz.mean(axis=0), 1.0))[2])
    camera_distance = float(np.linalg.norm(c2w[:3, 3] - seed_xyz.mean(axis=0)))
    return {
        "finite": bool(np.isfinite(c2w).all()),
        "visible_seed_fraction": visible_fraction,
        "center_depth": center_depth,
        "camera_distance": camera_distance,
        "inside_seed_sphere": bool(camera_distance <= seed_radius * 1.05),
        "status": "pass"
        if np.isfinite(c2w).all()
        and visible_fraction >= 0.90
        and center_depth > 0.01
        and camera_distance > seed_radius * 1.05
        else "reject",
    }


def add_candidate(
    candidates: list[dict],
    candidate_id: str,
    category: str,
    eye: np.ndarray,
    target: np.ndarray,
    focal: float,
    size: int,
    seed_xyz: np.ndarray,
    seed_radius: float,
    azimuth_degrees: float | None,
) -> None:
    c2w = look_at_c2w(eye, target)
    candidates.append(
        {
            "id": candidate_id,
            "category": category,
            "camera_to_world": c2w.tolist(),
            "azimuth_degrees": azimuth_degrees,
            "preflight": preflight_seed_projection(seed_xyz, c2w, focal, size, seed_radius),
        }
    )


def make_contact_sheet(frame_records: list[dict], output: Path, size: int) -> None:
    columns = 4
    label_height = 34
    rows = math.ceil(len(frame_records) / columns)
    sheet = Image.new("RGB", (columns * size, rows * (size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(frame_records):
        x = (index % columns) * size
        y = (index // columns) * (size + label_height)
        if record.get("file"):
            image = Image.open(output.parent / record["file"]).convert("RGB")
            sheet.paste(image, (x, y))
        else:
            draw.rectangle((x, y, x + size, y + size), fill="#4b2020")
        label = f"{record['id']} · {record['category']}"
        if record["render_status"] != "rendered":
            label += " · rejected"
        draw.text((x + 6, y + size + 8), label, fill="white")
    sheet.save(output)


def plan_candidates(target: dict, seed_info: dict, seed_xyz: np.ndarray, size: int) -> tuple[list[dict], float]:
    anchor = target["anchor_candidate"]
    camera_data = json.loads((Path(target["_root"]) / anchor["camera_manifest"]).read_text())
    anchor_c2w = np.asarray(camera_data["frames"][0]["camera_to_world"], dtype=np.float32)
    anchor_eye = anchor_c2w[:3, 3]
    center = np.asarray(seed_info["center"], dtype=np.float32)
    extent = np.asarray(seed_info["extent"], dtype=np.float32)
    fov_degrees = float(anchor["horizontal_fov_degrees"])
    focal = size / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))
    seed_radius = max(0.12, float(np.linalg.norm(extent) / 2.0))
    anchor_offset = anchor_eye - center
    anchor_azimuth = math.atan2(float(anchor_offset[1]), float(anchor_offset[0]))
    anchor_radius_xy = max(0.01, float(np.linalg.norm(anchor_offset[:2])))
    target_diameter = max(float(np.max(extent)) * 1.20, seed_radius * 2.0)
    desired_radius = target_diameter / (2.0 * math.tan(math.radians(fov_degrees) / 2.0) * 0.60)
    # The initial path must stay close to the Anchor's projection family so a
    # tracker sees small, approximately 30-degree camera changes.  A closer
    # distance that would frame the target at 60% is reserved for replacements
    # after the stable orbit has been evaluated.
    orbit_radius = anchor_radius_xy
    ring_z = float(anchor_eye[2])

    candidates: list[dict] = [
        {
            "id": "anchor",
            "category": "anchor",
            "camera_to_world": anchor_c2w.tolist(),
            "azimuth_degrees": None,
            "preflight": preflight_seed_projection(seed_xyz, anchor_c2w, focal, size, seed_radius),
        }
    ]
    # Eleven hidden views plus the Anchor approximate a 30-degree full orbit.
    for step in range(1, 12):
        angle = anchor_azimuth + step * math.radians(30.0)
        eye = np.asarray(
            [
                center[0] + orbit_radius * math.cos(angle),
                center[1] + orbit_radius * math.sin(angle),
                ring_z,
            ],
            dtype=np.float32,
        )
        add_candidate(
            candidates,
            f"ring-{step:02d}",
            "ring",
            eye,
            center,
            focal,
            size,
            seed_xyz,
            seed_radius,
            math.degrees(angle) % 360.0,
        )
    # Four upper-oblique candidates near cardinal bearings.
    upper_z = float(center[2] + max(0.40, orbit_radius * math.tan(math.radians(30.0))))
    for index, offset_degrees in enumerate((0.0, 90.0, 180.0, 270.0)):
        angle = anchor_azimuth + math.radians(offset_degrees)
        eye = np.asarray(
            [
                center[0] + orbit_radius * math.cos(angle),
                center[1] + orbit_radius * math.sin(angle),
                upper_z,
            ],
            dtype=np.float32,
        )
        add_candidate(
            candidates,
            f"upper-{index:02d}",
            "upper",
            eye,
            center,
            focal,
            size,
            seed_xyz,
            seed_radius,
            math.degrees(angle) % 360.0,
        )
    # Eight replacements use interleaved bearings and a modest outward offset.
    for index in range(8):
        angle = anchor_azimuth + math.radians(15.0 + index * 45.0)
        eye = np.asarray(
            [
                center[0] + max(seed_radius * 2.2, desired_radius) * math.cos(angle),
                center[1] + max(seed_radius * 2.2, desired_radius) * math.sin(angle),
                ring_z + 0.15,
            ],
            dtype=np.float32,
        )
        add_candidate(
            candidates,
            f"replacement-{index:02d}",
            "replacement",
            eye,
            center,
            focal,
            size,
            seed_xyz,
            seed_radius,
            math.degrees(angle) % 360.0,
        )
    return candidates, fov_degrees


def render_target(args: argparse.Namespace, target: dict, seed_info: dict) -> None:
    target_id = target["id"]
    output_dir = args.targets_root / target_id / f"generated-view-candidates-{PREVIEW_CONFIG_VERSION}"
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    seed_ids = np.load(args.targets_root / target_id / "seed-region.npz")["stable_gaussian_ids"]
    arrays = _load_ply_arrays(str(args.ply))
    seed_xyz = arrays["means"][seed_ids]
    target["_root"] = str(args.targets_root)
    candidates, fov_degrees = plan_candidates(target, seed_info, seed_xyz, args.size)
    target.pop("_root", None)

    renderer = get_renderer("gsplat")
    gaussians = renderer.prepare(arrays)
    focal = args.size / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))
    intrinsics = torch.tensor(
        [[focal, 0.0, args.size / 2.0], [0.0, focal, args.size / 2.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
        device=renderer.device,
    )
    render_indices = [i for i, candidate in enumerate(candidates) if candidate["preflight"]["status"] == "pass"]
    for start in range(0, len(render_indices), 2):
        batch_indices = render_indices[start : start + 2]
        c2w = torch.tensor(
            np.stack([candidates[i]["camera_to_world"] for i in batch_indices]),
            dtype=torch.float32,
            device=renderer.device,
        )
        pixels_batch = renderer.render_rgb(
            gaussians, torch.linalg.inv(c2w), intrinsics, args.size, args.size
        )
        for candidate_index, pixels in zip(batch_indices, pixels_batch, strict=True):
            candidate = candidates[candidate_index]
            relative = Path("frames") / f"{candidate['id']}.png"
            Image.fromarray(pixels, mode="RGB").save(output_dir / relative)
            candidate["file"] = str(relative)
            candidate["render_status"] = "rendered"
    for candidate in candidates:
        if "render_status" not in candidate:
            candidate["render_status"] = "rejected_preflight"

    manifest = {
        "schema_version": 1,
        "purpose": "preview candidates; not an accepted Frame Set",
        "policy_version": POLICY_VERSION,
        "render_config_version": PREVIEW_CONFIG_VERSION,
        "source_ply": str(args.ply),
        "target_id": target_id,
        "resolution": [args.size, args.size],
        "horizontal_fov_degrees": fov_degrees,
        "seed_region": seed_info,
        "candidates": candidates,
    }
    (output_dir / "candidates.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    make_contact_sheet(candidates, output_dir / "contact-sheet.png", args.size)
    print(output_dir / "contact-sheet.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    if args.size not in (512, 768, 1008):
        raise ValueError("preview size must be one of 512, 768, or 1008")
    target_manifest = json.loads((args.targets_root / "targets.json").read_text())
    seed_manifest = json.loads((args.targets_root / "seed-regions.json").read_text())
    target = next(item for item in target_manifest["targets"] if item["id"] == args.target)
    render_target(args, target, seed_manifest["targets"][args.target])


if __name__ == "__main__":
    main()

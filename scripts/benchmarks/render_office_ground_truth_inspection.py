#!/usr/bin/env python3
"""Render RGB-only inspection views for independent office Ground Truth review.

The output is deliberately separate from a Frame Set or Mask Set.  It uses a
frozen Seed Region only to frame cameras around a user-confirmed target; it
does not load SAM masks, tracked masks, or lifting results.  A later human
annotation pass must classify Stable Gaussian IDs from these inspection views.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402
from renderers import get_renderer  # noqa: E402


INSPECTION_LAYOUT_VERSION = "office-ground-truth-inspection-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length < 1e-8:
        raise ValueError("camera direction has zero length")
    return vector / length


def look_at_c2w(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return an OpenCV-convention camera-to-world transform (X right, Y down, Z forward)."""
    forward = normalize(target - eye)
    up_reference = np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(float(np.dot(forward, up_reference))) > 0.999:
        up_reference = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    right = normalize(np.cross(forward, up_reference))
    down = np.cross(forward, right)
    c2w = np.eye(4, dtype=np.float32)
    c2w[:3, 0] = right
    c2w[:3, 1] = down
    c2w[:3, 2] = forward
    c2w[:3, 3] = eye
    return c2w


def seed_projection_preflight(seed_xyz: np.ndarray, c2w: np.ndarray, focal: float, size: int) -> dict:
    w2c = np.linalg.inv(c2w)
    homogeneous = np.concatenate(
        (seed_xyz, np.ones((len(seed_xyz), 1), dtype=np.float32)), axis=1
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
    return {
        "finite": bool(np.isfinite(c2w).all()),
        "visible_seed_fraction": float(in_frame.mean()),
        "seed_center_depth": float(camera_xyz[:, 2].mean()),
    }


def make_contact_sheet(records: list[dict], root: Path, output: Path) -> None:
    thumbnail_size = 252
    label_height = 30
    columns = 4
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGB", (columns * thumbnail_size, rows * (thumbnail_size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        image = Image.open(root / record["file"]).convert("RGB")
        image.thumbnail((thumbnail_size, thumbnail_size))
        x = (index % columns) * thumbnail_size
        y = (index // columns) * (thumbnail_size + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + thumbnail_size + 6), record["view_id"], fill="white")
    sheet.save(output)


def ring_eye(center: np.ndarray, horizontal_direction: np.ndarray, radius: float, z: float) -> np.ndarray:
    return np.asarray(
        [
            center[0] + horizontal_direction[0] * radius,
            center[1] + horizontal_direction[1] * radius,
            z,
        ],
        dtype=np.float32,
    )


def plan_inspection_views(
    anchor_c2w: np.ndarray,
    center: np.ndarray,
    extent: np.ndarray,
) -> list[dict]:
    """Create Anchor/opposite/left/right/top/bottom/oblique review cameras."""
    anchor_eye = anchor_c2w[:3, 3]
    horizontal_offset = anchor_eye[:2] - center[:2]
    radius = float(np.linalg.norm(horizontal_offset))
    minimum_radius = max(0.35, float(np.max(extent)) * 1.25)
    if radius < minimum_radius:
        horizontal_direction = np.asarray([1.0, 0.0], dtype=np.float32)
        radius = minimum_radius
    else:
        horizontal_direction = (horizontal_offset / radius).astype(np.float32)

    left_direction = np.asarray([-horizontal_direction[1], horizontal_direction[0]], dtype=np.float32)
    right_direction = -left_direction
    opposite_direction = -horizontal_direction
    diagonal_direction = normalize(horizontal_direction + left_direction)
    ring_z = float(anchor_eye[2])
    vertical_clearance = max(radius, float(np.max(extent)) * 1.50, 0.50)

    return [
        {
            "view_id": "anchor",
            "inspection_role": "anchor",
            "camera_to_world": anchor_c2w,
            "source": "frozen-anchor-image",
        },
        {
            "view_id": "opposite",
            "inspection_role": "opposite",
            "camera_to_world": look_at_c2w(ring_eye(center, opposite_direction, radius, ring_z), center),
            "source": "service-rendered-inspection-view",
        },
        {
            "view_id": "left_orbit",
            "inspection_role": "left",
            "camera_to_world": look_at_c2w(ring_eye(center, left_direction, radius, ring_z), center),
            "source": "service-rendered-inspection-view",
        },
        {
            "view_id": "right_orbit",
            "inspection_role": "right",
            "camera_to_world": look_at_c2w(ring_eye(center, right_direction, radius, ring_z), center),
            "source": "service-rendered-inspection-view",
        },
        {
            "view_id": "top",
            "inspection_role": "top",
            "camera_to_world": look_at_c2w(
                center + np.asarray([0.0, 0.0, vertical_clearance], dtype=np.float32), center
            ),
            "source": "service-rendered-inspection-view",
        },
        {
            "view_id": "bottom",
            "inspection_role": "bottom",
            "camera_to_world": look_at_c2w(
                center - np.asarray([0.0, 0.0, vertical_clearance], dtype=np.float32), center
            ),
            "source": "service-rendered-inspection-view",
        },
        {
            "view_id": "oblique",
            "inspection_role": "oblique",
            "camera_to_world": look_at_c2w(
                ring_eye(center, diagonal_direction, radius, ring_z + vertical_clearance * 0.45), center
            ),
            "source": "service-rendered-inspection-view",
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--inspection-version", default="ground-truth-inspection-v1")
    parser.add_argument("--size", type=int, default=1008)
    parser.add_argument(
        "--supplemental-frame-set-dir",
        type=Path,
        help="Optional immutable Frame Set whose RGB/camera metadata is copied only as an additional inspection view.",
    )
    parser.add_argument(
        "--supplemental-candidate-id",
        action="append",
        default=[],
        help="Candidate ID from --supplemental-frame-set-dir to add; may be supplied more than once.",
    )
    args = parser.parse_args()

    if args.size not in (512, 768, 1008):
        raise ValueError("inspection size must be one of 512, 768, or 1008")
    if args.supplemental_candidate_id and args.supplemental_frame_set_dir is None:
        raise ValueError("--supplemental-candidate-id requires --supplemental-frame-set-dir")
    output_dir = args.targets_root / args.target / args.inspection_version
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing inspection set: {output_dir}")
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True)

    targets_manifest_path = args.targets_root / "targets.json"
    seed_manifest_path = args.targets_root / "seed-regions.json"
    targets_manifest = json.loads(targets_manifest_path.read_text(encoding="utf-8"))
    target = next(item for item in targets_manifest["targets"] if item["id"] == args.target)
    seed_info = json.loads(seed_manifest_path.read_text(encoding="utf-8"))["targets"][args.target]

    anchor = target["anchor_candidate"]
    anchor_camera_path = args.targets_root / anchor["camera_manifest"]
    anchor_camera = json.loads(anchor_camera_path.read_text(encoding="utf-8"))
    anchor_c2w = np.asarray(anchor_camera["frames"][0]["camera_to_world"], dtype=np.float32)
    center = np.asarray(seed_info["center"], dtype=np.float32)
    extent = np.asarray(seed_info["extent"], dtype=np.float32)
    seed_ids = np.load(args.targets_root / args.target / "seed-region.npz")["stable_gaussian_ids"].astype(np.int64)

    fov_degrees = float(anchor["horizontal_fov_degrees"])
    focal = args.size / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))
    views = plan_inspection_views(anchor_c2w, center, extent)

    anchor_source = args.targets_root / anchor["image"]
    views[0]["rgb_source_path"] = anchor_source
    if args.supplemental_frame_set_dir is not None:
        frame_set_path = args.supplemental_frame_set_dir / "frame-set.json"
        frame_set = json.loads(frame_set_path.read_text(encoding="utf-8"))
        if frame_set["target_id"] != args.target:
            raise ValueError("supplemental Frame Set target does not match inspection target")
        if frame_set["resolution"] != [args.size, args.size]:
            raise ValueError("supplemental Frame Set resolution must equal the inspection resolution")
        available = {item["candidate_id"]: item for item in frame_set["frames"]}
        if len(set(args.supplemental_candidate_id)) != len(args.supplemental_candidate_id):
            raise ValueError("supplemental candidate IDs must be unique")
        for candidate_id in args.supplemental_candidate_id:
            if candidate_id not in available:
                raise ValueError(f"unknown supplemental candidate ID: {candidate_id}")
            if candidate_id == "anchor":
                raise ValueError("the Anchor is already present in every inspection set")
            source_frame = available[candidate_id]
            view_id = f"supplemental-{candidate_id}"
            views.append(
                {
                    "view_id": view_id,
                    "inspection_role": "supplemental",
                    "camera_to_world": np.asarray(source_frame["camera_to_world"], dtype=np.float32),
                    "source": "frozen-frame-set-rgb-for-inspection-only",
                    "rgb_source_path": args.supplemental_frame_set_dir / source_frame["file"],
                    "source_frame_set": {
                        "path": str(frame_set_path),
                        "sha256": sha256(frame_set_path),
                        "candidate_id": candidate_id,
                        "frame_sha256": source_frame["sha256"],
                    },
                }
            )

    arrays = _load_ply_arrays(str(args.ply))
    seed_xyz = arrays["means"][seed_ids]
    renderer = get_renderer("gsplat")
    gaussians = renderer.prepare(arrays)
    intrinsics = torch.tensor(
        [[focal, 0.0, args.size / 2.0], [0.0, focal, args.size / 2.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
        device=renderer.device,
    )

    records: list[dict] = []
    generated_views = [
        (index, view) for index, view in enumerate(views) if "rgb_source_path" not in view
    ]
    for index, view in enumerate(views):
        if "rgb_source_path" not in view:
            continue
        destination = frames_dir / f"{index:02d}-{view['view_id']}.png"
        shutil.copy2(view["rgb_source_path"], destination)
        record = {
            "frame_index": index,
            "view_id": view["view_id"],
            "inspection_role": view["inspection_role"],
            "file": str(destination.relative_to(output_dir)),
            "sha256": sha256(destination),
            "camera_to_world": view["camera_to_world"].tolist(),
            "source": view["source"],
            "seed_projection_preflight": seed_projection_preflight(seed_xyz, view["camera_to_world"], focal, args.size),
        }
        if "source_frame_set" in view:
            record["source_frame_set"] = view["source_frame_set"]
        records.append(record)

    for start in range(0, len(generated_views), 2):
        batch = generated_views[start : start + 2]
        c2w = torch.tensor(
            np.stack([view["camera_to_world"] for _, view in batch]),
            dtype=torch.float32,
            device=renderer.device,
        )
        pixels_batch = renderer.render_rgb(
            gaussians, torch.linalg.inv(c2w), intrinsics, args.size, args.size
        )
        for (index, view), pixels in zip(batch, pixels_batch, strict=True):
            destination = frames_dir / f"{index:02d}-{view['view_id']}.png"
            Image.fromarray(pixels, mode="RGB").save(destination)
            records.append(
                {
                    "frame_index": index,
                    "view_id": view["view_id"],
                    "inspection_role": view["inspection_role"],
                    "file": str(destination.relative_to(output_dir)),
                    "sha256": sha256(destination),
                    "camera_to_world": view["camera_to_world"].tolist(),
                    "source": view["source"],
                    "seed_projection_preflight": seed_projection_preflight(seed_xyz, view["camera_to_world"], focal, args.size),
                }
            )

    records.sort(key=lambda record: record["frame_index"])
    contact_sheet_path = output_dir / "contact-sheet.png"
    make_contact_sheet(records, output_dir, contact_sheet_path)
    manifest = {
        "schema_version": 1,
        "status": "rendered-pending-independent-ground-truth-annotation",
        "purpose": "RGB-only multi-direction inspection set for Benchmark Ground Truth annotation",
        "inspection_layout_version": INSPECTION_LAYOUT_VERSION,
        "target_id": args.target,
        "source_ply": {
            "path": str(args.ply),
            "sha256": sha256(args.ply),
            "gaussian_count": int(len(arrays["means"])),
        },
        "resolution": [args.size, args.size],
        "horizontal_fov_degrees": fov_degrees,
        "seed_region_framing": {
            "seed_regions_manifest": "seed-regions.json",
            "seed_regions_manifest_sha256": sha256(seed_manifest_path),
            "stable_gaussian_id_count": int(len(seed_ids)),
            "center": center.tolist(),
            "extent": extent.tolist(),
            "scope_note": "Used only to frame inspection cameras. It is not a Benchmark Ground Truth label, candidate selection, or lifting result.",
        },
        "independence": {
            "sam_masks_loaded": False,
            "lifting_results_loaded": False,
            "required_next_step": "An independent annotation pass must classify relevant Stable Gaussian IDs as selected, rejected, or ambiguous before lifting outputs are evaluated.",
        },
        "inspection_requirements": {
            "required_roles": ["anchor", "opposite", "left", "right", "top", "bottom"],
            "additional_roles": ["oblique"],
        },
        "frames": records,
        "contact_sheet": {
            "file": contact_sheet_path.name,
            "sha256": sha256(contact_sheet_path),
        },
    }
    (output_dir / "inspection-set.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(contact_sheet_path)


if __name__ == "__main__":
    main()

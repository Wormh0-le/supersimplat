#!/usr/bin/env python3
"""Materialize an immutable 1008px Frame Set from accepted preview candidates."""

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


RENDER_CONFIG_VERSION = "frame-set-1008-v1"
DEFAULT_CANDIDATE_CONFIG_VERSION = "preview-512-v2-anchor-radius"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contact_sheet(records: list[dict], root: Path, output: Path) -> None:
    thumbnail_size = 252
    label_height = 26
    columns = 4
    rows = math.ceil(len(records) / columns)
    result = Image.new("RGB", (columns * thumbnail_size, rows * (thumbnail_size + label_height)), "#202020")
    draw = ImageDraw.Draw(result)
    for index, record in enumerate(records):
        image = Image.open(root / record["file"]).convert("RGB")
        image.thumbnail((thumbnail_size, thumbnail_size))
        x = (index % columns) * thumbnail_size
        y = (index // columns) * (thumbnail_size + label_height)
        result.paste(image, (x, y))
        draw.text((x + 5, y + thumbnail_size + 5), record["candidate_id"], fill="white")
    result.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--candidate-id", action="append", required=True)
    parser.add_argument("--frame-set-version", default="frame-set-v1")
    parser.add_argument("--candidate-config-version", default=DEFAULT_CANDIDATE_CONFIG_VERSION)
    args = parser.parse_args()

    targets = json.loads((args.targets_root / "targets.json").read_text())
    target = next(item for item in targets["targets"] if item["id"] == args.target)
    candidates_dir = args.targets_root / args.target / f"generated-view-candidates-{args.candidate_config_version}"
    candidate_manifest = json.loads((candidates_dir / "candidates.json").read_text())
    candidates = {candidate["id"]: candidate for candidate in candidate_manifest["candidates"]}
    requested_ids = list(args.candidate_id)
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("candidate IDs must be unique")
    if requested_ids.count("anchor") != 1:
        raise ValueError("candidate IDs must contain anchor exactly once")
    missing = [candidate_id for candidate_id in requested_ids if candidate_id not in candidates]
    if missing:
        raise ValueError(f"unknown candidate IDs: {missing}")
    if any(candidates[candidate_id]["render_status"] != "rendered" for candidate_id in requested_ids):
        raise ValueError("all selected candidates must have rendered preview frames")

    output_dir = args.targets_root / args.target / args.frame_set_version
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    selected = [candidates[candidate_id] for candidate_id in requested_ids]
    resolution = 1008
    fov_degrees = float(target["anchor_candidate"]["horizontal_fov_degrees"])
    focal = resolution / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))

    records: list[dict] = []
    anchor_source = args.targets_root / target["anchor_candidate"]["image"]
    generated = [(index, candidate) for index, candidate in enumerate(selected) if candidate["id"] != "anchor"]
    for frame_index, candidate in enumerate(selected):
        if candidate["id"] != "anchor":
            continue
        anchor_destination = frames_dir / f"{frame_index:03d}-anchor.png"
        shutil.copy2(anchor_source, anchor_destination)
        records.append(
            {
                "frame_index": frame_index,
                "candidate_id": "anchor",
                "category": "anchor",
                "file": str(anchor_destination.relative_to(output_dir)),
                "camera_to_world": candidate["camera_to_world"],
                "sha256": sha256(anchor_destination),
                "source": "frozen-anchor-image",
            }
        )
    if generated:
        arrays = _load_ply_arrays(str(args.ply))
        renderer = get_renderer("gsplat")
        gaussians = renderer.prepare(arrays)
        intrinsics = torch.tensor(
            [[focal, 0.0, resolution / 2.0], [0.0, focal, resolution / 2.0], [0.0, 0.0, 1.0]],
            dtype=torch.float32,
            device=renderer.device,
        )
        for start in range(0, len(generated), 2):
            batch = generated[start : start + 2]
            c2w = torch.tensor(
                np.stack([candidate["camera_to_world"] for _, candidate in batch]),
                dtype=torch.float32,
                device=renderer.device,
            )
            rgb = renderer.render_rgb(gaussians, torch.linalg.inv(c2w), intrinsics, resolution, resolution)
            for (frame_index, candidate), pixels in zip(batch, rgb, strict=True):
                destination = frames_dir / f"{frame_index:03d}-{candidate['id']}.png"
                Image.fromarray(pixels, mode="RGB").save(destination)
                records.append(
                    {
                        "frame_index": frame_index,
                        "candidate_id": candidate["id"],
                        "category": candidate["category"],
                        "file": str(destination.relative_to(output_dir)),
                        "camera_to_world": candidate["camera_to_world"],
                        "sha256": sha256(destination),
                        "source": "service-rendered-generated-view",
                    }
                )

    records.sort(key=lambda record: record["frame_index"])
    manifest = {
        "schema_version": 1,
        "status": "candidate-frame-set-mask-validation-pending",
        "frame_set_version": args.frame_set_version,
        "render_config_version": RENDER_CONFIG_VERSION,
        "target_id": args.target,
        "source_ply": str(args.ply),
        "resolution": [resolution, resolution],
        "horizontal_fov_degrees": fov_degrees,
        "anchor_frame_index": next(record["frame_index"] for record in records if record["candidate_id"] == "anchor"),
        "frames": records,
    }
    (output_dir / "frame-set.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    contact_sheet(records, output_dir, output_dir / "contact-sheet.png")
    print(output_dir / "contact-sheet.png")


if __name__ == "__main__":
    main()

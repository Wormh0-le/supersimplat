#!/usr/bin/env python3
"""Freeze one complete, reviewed Mask Set from a SAM3.1 tracking run."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np


MIN_MASK_AREA_FRACTION = 0.001
MAX_MASK_AREA_FRACTION = 0.8


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


def mask_metrics(mask: np.ndarray) -> tuple[int, list[int] | None, bool]:
    area = int(mask.sum())
    if area == 0:
        return 0, None, False
    ys, xs = np.where(mask)
    bbox_xyxy = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    border_touch = bool(
        xs.min() == 0
        or ys.min() == 0
        or xs.max() == mask.shape[1] - 1
        or ys.max() == mask.shape[0] - 1
    )
    return area, bbox_xyxy, border_touch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--frame-set-dir", type=Path, required=True)
    parser.add_argument("--tracking-dir", type=Path, required=True)
    parser.add_argument("--mask-set-version", required=True)
    parser.add_argument("--accept-candidate-id", action="append", default=[])
    parser.add_argument("--not-found-candidate-id", action="append", default=[])
    parser.add_argument("--visual-review-note", required=True)
    args = parser.parse_args()

    frame_set_path = args.frame_set_dir / "frame-set.json"
    tracking_path = args.tracking_dir / "tracking.json"
    frame_set = json.loads(frame_set_path.read_text(encoding="utf-8"))
    tracking = json.loads(tracking_path.read_text(encoding="utf-8"))
    if frame_set["target_id"] != args.target or tracking["target_id"] != args.target:
        raise RuntimeError("target does not match the Frame Set and tracking run")
    if tracking.get("execution_kind") != "prompt-script" or not tracking.get("prompt_script"):
        raise RuntimeError("only a replayable --prompt-script tracking run can become a frozen Mask Set")
    if tracking["resolution"] != frame_set["resolution"]:
        raise RuntimeError("tracking resolution does not match the Frame Set")

    input_manifest = tracking.get("input_manifest", {})
    if input_manifest.get("kind") != "frame_set":
        raise RuntimeError("tracking run was not performed against an immutable Frame Set")
    if input_manifest.get("frame_set_version") != frame_set["frame_set_version"]:
        raise RuntimeError("tracking Frame Set version does not match")
    if input_manifest.get("sha256") != sha256(frame_set_path):
        raise RuntimeError("tracking Frame Set digest does not match the current Frame Set")

    frame_records = frame_set["frames"]
    tracking_records = tracking["frames"]
    if len(frame_records) != len(tracking_records):
        raise RuntimeError("tracking result does not cover every Frame Set frame")
    for frame, result in zip(frame_records, tracking_records, strict=True):
        if frame["frame_index"] != result["frame_index"] or frame["candidate_id"] != result["candidate_id"]:
            raise RuntimeError("tracking frame order or candidate identity does not match the Frame Set")

    accepted_ids = list(args.accept_candidate_id)
    not_found_ids = list(args.not_found_candidate_id)
    if not accepted_ids:
        raise RuntimeError("a frozen Mask Set requires at least one accepted frame")
    declared_ids = accepted_ids + not_found_ids
    if len(set(declared_ids)) != len(declared_ids):
        raise RuntimeError("each Frame Set candidate must have exactly one declared outcome")
    expected_ids = [frame["candidate_id"] for frame in frame_records]
    if set(declared_ids) != set(expected_ids):
        raise RuntimeError("declared accepted/not-found candidates must exactly cover the Frame Set")
    outcome_by_id = {candidate_id: "accepted" for candidate_id in accepted_ids}
    outcome_by_id.update({candidate_id: "not_found" for candidate_id in not_found_ids})

    masks_path = args.tracking_dir / "tracked-masks.npz"
    masks = np.load(masks_path)["masks"].astype(bool)
    width, height = frame_set["resolution"]
    if masks.shape != (len(frame_records), height, width):
        raise RuntimeError(f"unexpected mask tensor shape: {masks.shape}")

    validated_frames: list[dict] = []
    for frame, result, mask in zip(frame_records, tracking_records, masks, strict=True):
        area, bbox_xyxy, border_touch = mask_metrics(mask)
        fraction = area / mask.size
        if area != result["mask_area_pixels"] or bbox_xyxy != result["bbox_xyxy"] or border_touch != result["border_touch"]:
            raise RuntimeError(f"tracking manifest does not match binary mask for {frame['candidate_id']}")
        status = outcome_by_id[frame["candidate_id"]]
        record = {
            "view_id": frame["candidate_id"],
            "frame_index": frame["frame_index"],
            "frame_sha256": frame["sha256"],
            "status": status,
            "mask_area_pixels": area,
            "mask_area_fraction": fraction,
            "bbox_xyxy": bbox_xyxy,
            "border_touch": border_touch,
            "overlay": result["overlay"],
        }
        if status == "accepted":
            if not MIN_MASK_AREA_FRACTION <= fraction <= MAX_MASK_AREA_FRACTION:
                raise RuntimeError(f"mask area fails hard gate for {frame['candidate_id']}: {fraction:.6f}")
            if border_touch:
                raise RuntimeError(f"mask touches the image border for {frame['candidate_id']}")
            record["binary_mask_ref"] = "masks.npz"
            record["binary_mask_index"] = frame["frame_index"]
        else:
            if area != 0:
                raise RuntimeError(f"not_found frame must not retain a binary mask: {frame['candidate_id']}")
            record["reason"] = "SAM3.1 produced no reliable target mask; this view contributes neutral evidence."
        validated_frames.append(record)

    output_dir = args.frame_set_dir / args.mask_set_version
    if output_dir.exists():
        raise RuntimeError(f"Mask Set output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    shutil.copy2(masks_path, output_dir / "masks.npz")
    shutil.copy2(tracking_path, output_dir / "tracking.json")
    shutil.copy2(args.tracking_dir / tracking["overlay_contact_sheet"], output_dir / "overlay-contact-sheet.png")
    shutil.copytree(args.tracking_dir / "overlays", output_dir / "overlays")

    model_manifest = {
        "adapter": "SAM3.1 visual prompt/video propagation",
        "model": tracking["model"],
        "checkpoint_sha256": tracking["checkpoint_sha256"],
        "sam3_source_commit": tracking["sam3_source_commit"],
        "license": tracking["license"],
        "runtime": tracking["runtime"],
    }
    model_manifest_sha256 = hashlib.sha256(
        json.dumps(model_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "complete reviewed Mask Set for generated-view lifting benchmark",
        "mask_set_version": args.mask_set_version,
        "target_id": args.target,
        "frame_set": {
            "path": relative_to_or_absolute(frame_set_path, args.targets_root),
            "frame_set_version": frame_set["frame_set_version"],
            "sha256": sha256(frame_set_path),
            "resolution": frame_set["resolution"],
        },
        "model_manifest": model_manifest,
        "model_manifest_sha256": model_manifest_sha256,
        "prompt_script": tracking["prompt_script"],
        "acceptance_gate": {
            "minimum_mask_area_fraction": MIN_MASK_AREA_FRACTION,
            "maximum_mask_area_fraction": MAX_MASK_AREA_FRACTION,
            "border_touch": "rejected",
            "visual_review": {
                "artifact": "overlay-contact-sheet.png",
                "note": args.visual_review_note,
            },
        },
        "source_tracking": {
            "path": relative_to_or_absolute(tracking_path, args.targets_root),
            "sha256": sha256(tracking_path),
            "masks_sha256": sha256(masks_path),
        },
        "outcome_counts": {
            "accepted": len(accepted_ids),
            "not_found": len(not_found_ids),
        },
        "tracks": [
            {
                "track_id": tracking["prompt_script"]["content"]["track_id"],
                "role": tracking["prompt_script"]["content"]["role"],
                "frames": validated_frames,
            }
        ],
    }
    (output_dir / "mask-set.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

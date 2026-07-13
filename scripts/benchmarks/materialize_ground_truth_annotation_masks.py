#!/usr/bin/env python3
"""Materialize reviewable RGB-only 2D annotations for office Ground Truth.

This script intentionally has no SAM or lifting dependency.  It turns a
versioned, human-readable region specification into positive and rejected
pixel masks, so those raw annotations can be reviewed before they are lifted
to Stable Gaussian IDs by a later, separate step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_box(region: dict, width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (int(value) for value in region["xyxy"])
    x0, x1 = sorted((max(0, x0), min(width, x1)))
    y0, y1 = sorted((max(0, y0), min(height, y1)))
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"region has an empty image-space box: {region}")
    return x0, y0, x1, y1


def rasterize_region(region: dict, image: np.ndarray) -> np.ndarray:
    """Return one boolean mask for a documented manual or color-assisted region."""
    height, width = image.shape[:2]
    kind = region["kind"]
    if kind in {"box", "polygon", "stroke"}:
        canvas = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(canvas)
        if kind == "box":
            x0, y0, x1, y1 = bounded_box(region, width, height)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
        elif kind == "polygon":
            points = [tuple(point) for point in region["points"]]
            if len(points) < 3:
                raise ValueError("polygon requires at least three points")
            draw.polygon(points, fill=255)
        else:
            points = [tuple(point) for point in region["points"]]
            if len(points) < 2:
                raise ValueError("stroke requires at least two points")
            width_px = int(region["width_px"])
            if width_px <= 0:
                raise ValueError("stroke width must be positive")
            draw.line(points, fill=255, width=width_px, joint="curve")
        return np.asarray(canvas, dtype=np.uint8) > 0

    if kind == "green_threshold":
        x0, y0, x1, y1 = bounded_box(region, width, height)
        crop = image[y0:y1, x0:x1].astype(np.float32) / 255.0
        red, green, blue = crop[..., 0], crop[..., 1], crop[..., 2]
        condition = (
            (green >= float(region["green_min"]))
            & (green >= red * float(region["green_over_red"]))
            & (green >= blue * float(region["green_over_blue"]))
        )
        result = np.zeros((height, width), dtype=bool)
        result[y0:y1, x0:x1] = condition
        return result

    raise ValueError(f"unsupported annotation region kind: {kind}")


def make_contact_sheet(records: list[dict], root: Path, output: Path) -> None:
    thumbnail_size = 252
    label_height = 30
    columns = 4
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGB", (columns * thumbnail_size, rows * (thumbnail_size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        image = Image.open(root / record["overlay"]).convert("RGB")
        image.thumbnail((thumbnail_size, thumbnail_size))
        x = (index % columns) * thumbnail_size
        y = (index // columns) * (thumbnail_size + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + thumbnail_size + 6), record["view_id"], fill="white")
    sheet.save(output)


def overlay(image: np.ndarray, positive: np.ndarray, negative: np.ndarray) -> np.ndarray:
    rendered = image.astype(np.float32).copy()
    only_positive = positive & ~negative
    only_negative = negative & ~positive
    conflict = positive & negative
    rendered[only_positive] = rendered[only_positive] * 0.45 + np.asarray([30, 220, 90], dtype=np.float32) * 0.55
    rendered[only_negative] = rendered[only_negative] * 0.45 + np.asarray([235, 55, 55], dtype=np.float32) * 0.55
    rendered[conflict] = rendered[conflict] * 0.35 + np.asarray([230, 80, 230], dtype=np.float32) * 0.65
    return np.clip(rendered, 0, 255).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspection-dir", type=Path, required=True)
    parser.add_argument("--annotation-spec", type=Path, required=True)
    parser.add_argument("--output-name", default="annotation-masks-draft-v1")
    args = parser.parse_args()

    inspection_path = args.inspection_dir / "inspection-set.json"
    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    spec = json.loads(args.annotation_spec.read_text(encoding="utf-8"))
    if spec["target_id"] != inspection["target_id"]:
        raise ValueError("annotation spec and inspection set target IDs differ")
    expected_inspection_hash = spec["inspection_set"]["sha256"]
    actual_inspection_hash = sha256(inspection_path)
    if expected_inspection_hash != actual_inspection_hash:
        raise RuntimeError("annotation spec does not bind to this exact inspection set")

    output_dir = args.inspection_dir / args.output_name
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing annotation masks: {output_dir}")
    (output_dir / "positive").mkdir(parents=True)
    (output_dir / "negative").mkdir()
    (output_dir / "overlays").mkdir()

    annotation_by_view = {item["view_id"]: item for item in spec["views"]}
    records: list[dict] = []
    for frame in inspection["frames"]:
        view_id = frame["view_id"]
        frame_path = args.inspection_dir / frame["file"]
        image = np.asarray(Image.open(frame_path).convert("RGB"))
        annotation = annotation_by_view.get(view_id, {})
        positive = np.zeros(image.shape[:2], dtype=bool)
        negative = np.zeros(image.shape[:2], dtype=bool)
        for region in annotation.get("positive_regions", []):
            positive |= rasterize_region(region, image)
        for region in annotation.get("negative_regions", []):
            negative |= rasterize_region(region, image)

        positive_path = output_dir / "positive" / f"{frame['frame_index']:02d}-{view_id}.png"
        negative_path = output_dir / "negative" / f"{frame['frame_index']:02d}-{view_id}.png"
        overlay_path = output_dir / "overlays" / f"{frame['frame_index']:02d}-{view_id}.png"
        Image.fromarray(positive.astype(np.uint8) * 255, mode="L").save(positive_path)
        Image.fromarray(negative.astype(np.uint8) * 255, mode="L").save(negative_path)
        Image.fromarray(overlay(image, positive, negative), mode="RGB").save(overlay_path)
        records.append(
            {
                "frame_index": frame["frame_index"],
                "view_id": view_id,
                "source_frame_sha256": frame["sha256"],
                "positive": str(positive_path.relative_to(output_dir)),
                "positive_sha256": sha256(positive_path),
                "positive_area_pixels": int(positive.sum()),
                "negative": str(negative_path.relative_to(output_dir)),
                "negative_sha256": sha256(negative_path),
                "negative_area_pixels": int(negative.sum()),
                "overlap_area_pixels": int((positive & negative).sum()),
                "overlay": str(overlay_path.relative_to(output_dir)),
            }
        )

    contact_sheet_path = output_dir / "overlay-contact-sheet.png"
    make_contact_sheet(records, output_dir, contact_sheet_path)
    manifest = {
        "schema_version": 1,
        "status": "draft-2d-annotations-materialized-not-ground-truth",
        "purpose": "Reviewable manual and color-assisted pixel annotations before Stable Gaussian ID Ground Truth lifting",
        "target_id": spec["target_id"],
        "annotation_spec": {
            "path": str(args.annotation_spec),
            "sha256": sha256(args.annotation_spec),
        },
        "inspection_set": {
            "path": str(inspection_path),
            "sha256": actual_inspection_hash,
        },
        "review_required": "A reviewer must inspect the overlay contact sheet and either revise this spec or explicitly accept it before any Ground Truth freeze.",
        "frames": records,
        "overlay_contact_sheet": {
            "file": contact_sheet_path.name,
            "sha256": sha256(contact_sheet_path),
        },
    }
    (output_dir / "annotation-masks.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(contact_sheet_path)


if __name__ == "__main__":
    main()

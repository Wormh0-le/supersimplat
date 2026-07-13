#!/usr/bin/env python3
"""Lift reviewed manual 2D annotations into a conservative Stable-ID GT draft.

This is intentionally not a lifting candidate.  It consumes only RGB-only
annotation masks, contributor attribution, and an explicit local candidate
region.  It emits a *draft* three-way classification; a separate review and
freeze step is required before it may be used for benchmark scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import gsplat
import numpy as np
import torch
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "thirdparty" / "splat_analyzer"))
from render_cameras import _load_ply_arrays  # noqa: E402


LABEL_NONE = 0
LABEL_SELECTED = 1
LABEL_REJECTED = 2
LABEL_AMBIGUOUS = 3
LABEL_COLORS = {
    LABEL_SELECTED: np.asarray([30, 220, 90], dtype=np.float32),
    LABEL_REJECTED: np.asarray([235, 55, 55], dtype=np.float32),
    LABEL_AMBIGUOUS: np.asarray([235, 190, 35], dtype=np.float32),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mask_from_png(path: Path, width: int, height: int) -> np.ndarray:
    mask = np.asarray(Image.open(path).convert("L")) > 0
    if mask.shape != (height, width):
        raise RuntimeError(f"annotation mask has wrong dimensions: {path}")
    return mask


def contributor_ids_and_weights(
    *,
    means: torch.Tensor,
    quats: torch.Tensor,
    scales: torch.Tensor,
    opacities: torch.Tensor,
    sh_coeffs: torch.Tensor,
    sh_degree: int,
    c2w: np.ndarray,
    intrinsics: torch.Tensor,
    width: int,
    height: int,
    top_k: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return global Stable IDs and alpha×T weights, shaped [H, W, K]."""
    view = torch.linalg.inv(torch.from_numpy(c2w).to(means.device))[None]
    _, _, meta = gsplat.rasterization(
        means,
        quats,
        scales,
        opacities,
        sh_coeffs,
        view,
        intrinsics,
        width,
        height,
        near_plane=0.01,
        far_plane=100.0,
        sh_degree=sh_degree,
        render_mode="RGB",
    )
    packed_ids, weights = gsplat.rasterize_top_contributing_gaussian_ids(
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
    packed_ids = packed_ids[0].long()
    weights = weights[0].float()
    valid = packed_ids >= 0
    stable_ids = torch.zeros_like(packed_ids)
    if meta["gaussian_ids"] is None:
        stable_ids[valid] = packed_ids[valid]
    else:
        stable_ids[valid] = meta["gaussian_ids"][packed_ids[valid]].long()
    return stable_ids, weights


def aggregate_view_evidence(
    stable_ids: torch.Tensor,
    weights: torch.Tensor,
    mask: np.ndarray,
    min_weight: float,
) -> tuple[np.ndarray, np.ndarray]:
    mask_t = torch.from_numpy(mask).to(device=stable_ids.device, dtype=torch.bool)
    ids = stable_ids[mask_t].reshape(-1)
    values = weights[mask_t].reshape(-1)
    valid = (ids >= 0) & (values > 0)
    ids = ids[valid]
    values = values[valid]
    if len(ids) == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    unique_ids, inverse = torch.unique(ids, return_inverse=True)
    totals = torch.zeros(len(unique_ids), device=values.device, dtype=torch.float32)
    totals.scatter_add_(0, inverse, values)
    keep = totals >= min_weight
    return (
        unique_ids[keep].cpu().numpy().astype(np.int64),
        totals[keep].cpu().numpy().astype(np.float64),
    )


def add_evidence(
    ids: np.ndarray,
    weights: np.ndarray,
    view_id: str,
    totals: dict[int, float],
    views: dict[int, set[str]],
) -> None:
    for stable_id, weight in zip(ids.tolist(), weights.tolist(), strict=True):
        totals[stable_id] += weight
        views[stable_id].add(view_id)


def make_projection_overlay(
    image: np.ndarray,
    stable_ids: torch.Tensor,
    weights: torch.Tensor,
    label_lookup: torch.Tensor,
) -> np.ndarray:
    labels = label_lookup[stable_ids]
    class_weights = []
    for label in (LABEL_SELECTED, LABEL_REJECTED, LABEL_AMBIGUOUS):
        class_weights.append(torch.where(labels == label, weights, 0.0).sum(dim=-1))
    stacked = torch.stack(class_weights, dim=-1)
    best_weight, best_index = stacked.max(dim=-1)
    best_label = best_index + LABEL_SELECTED
    best_weight = best_weight.cpu().numpy()
    best_label = best_label.cpu().numpy()

    result = image.astype(np.float32).copy()
    for label, color in LABEL_COLORS.items():
        where = (best_label == label) & (best_weight > 0.01)
        if not np.any(where):
            continue
        alpha = np.clip(best_weight[where] * 0.70, 0.25, 0.70)[:, None]
        result[where] = result[where] * (1.0 - alpha) + color * alpha
    return np.clip(result, 0, 255).astype(np.uint8)


def make_contact_sheet(records: list[dict], root: Path, output: Path) -> None:
    thumbnail_size = 252
    label_height = 30
    columns = 4
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGB", (columns * thumbnail_size, rows * (thumbnail_size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        x = (index % columns) * thumbnail_size
        y = (index // columns) * (thumbnail_size + label_height)
        if record["projection_status"] == "rendered":
            image = Image.open(root / record["overlay"]).convert("RGB")
            image.thumbnail((thumbnail_size, thumbnail_size))
            sheet.paste(image, (x, y))
            label = record["view_id"]
        else:
            draw.rectangle((x, y, x + thumbnail_size, y + thumbnail_size), fill="#3a2525")
            draw.text((x + 12, y + thumbnail_size // 2 - 12), "excluded", fill="#f3c0c0")
            label = f"{record['view_id']} · neutral"
        draw.text((x + 5, y + thumbnail_size + 6), label, fill="white")
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--inspection-dir", type=Path, required=True)
    parser.add_argument("--annotation-spec", type=Path, required=True)
    parser.add_argument("--annotation-mask-dir", type=Path, required=True)
    parser.add_argument("--draft-version", default="ground-truth-draft-v1")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--minimum-evidence-weight", type=float, default=0.01)
    parser.add_argument("--minimum-selected-positive-views", type=int, default=2)
    parser.add_argument("--minimum-rejected-negative-views", type=int, default=1)
    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError("top-k must be positive")
    if args.minimum_evidence_weight <= 0:
        raise ValueError("minimum evidence weight must be positive")
    if args.minimum_selected_positive_views <= 0 or args.minimum_rejected_negative_views <= 0:
        raise ValueError("minimum evidence view counts must be positive")

    inspection_path = args.inspection_dir / "inspection-set.json"
    review_path = args.inspection_dir / "visual-review.json"
    annotation_manifest_path = args.annotation_mask_dir / "annotation-masks.json"
    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    spec = json.loads(args.annotation_spec.read_text(encoding="utf-8"))
    annotation_manifest = json.loads(annotation_manifest_path.read_text(encoding="utf-8"))
    target_id = inspection["target_id"]
    if any(document["target_id"] != target_id for document in (review, spec, annotation_manifest)):
        raise ValueError("Ground Truth draft inputs target different objects")
    if spec["inspection_set"]["sha256"] != sha256(inspection_path):
        raise RuntimeError("annotation spec does not bind to this inspection set")
    if annotation_manifest["annotation_spec"]["sha256"] != sha256(args.annotation_spec):
        raise RuntimeError("annotation masks do not bind to this annotation spec")
    if annotation_manifest["inspection_set"]["sha256"] != sha256(inspection_path):
        raise RuntimeError("annotation masks do not bind to this inspection set")
    if annotation_manifest["status"] != "draft-2d-annotations-materialized-not-ground-truth":
        raise RuntimeError("annotation masks must be an explicit draft artifact")

    output_dir = args.target_dir / args.draft_version
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing Ground Truth draft: {output_dir}")

    review_by_view = {item["view_id"]: item for item in review["views"]}
    annotations_by_view = {item["view_id"]: item for item in annotation_manifest["frames"]}
    width, height = (int(value) for value in inspection["resolution"])
    if width != height:
        raise RuntimeError("current draft fixture expects square inspection frames")
    fov = math.radians(float(inspection["horizontal_fov_degrees"]))
    focal = width / (2.0 * math.tan(fov / 2.0))

    # Validate all source masks before creating any output directory.  A bad
    # annotation should leave no partial Ground Truth artifact behind.
    for frame in inspection["frames"]:
        view_id = frame["view_id"]
        annotation = annotations_by_view[view_id]
        positive = mask_from_png(args.annotation_mask_dir / annotation["positive"], width, height)
        negative = mask_from_png(args.annotation_mask_dir / annotation["negative"], width, height)
        if (positive & negative).any():
            raise RuntimeError(f"annotation masks overlap in {view_id}")
        if positive.any() or negative.any():
            review_status = review_by_view[view_id]["status"]
            if review_status not in {"usable", "partial"}:
                raise RuntimeError(f"annotation exists on a non-usable inspection view: {view_id}")

    (output_dir / "projection-overlays").mkdir(parents=True)

    arrays = _load_ply_arrays(str(args.ply))
    gaussian_count = len(arrays["means"])
    device = torch.device("cuda")
    means = torch.from_numpy(arrays["means"]).to(device)
    quats = torch.from_numpy(arrays["quats"]).to(device)
    scales = torch.from_numpy(np.exp(arrays["scales"])).to(device)
    opacities = torch.from_numpy(1.0 / (1.0 + np.exp(-arrays["opacities"]))).to(device)
    sh_coeffs = torch.from_numpy(arrays["sh_coeffs"]).to(device)
    intrinsics = torch.tensor(
        [[[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]]],
        dtype=torch.float32,
        device=device,
    )

    positive_totals: dict[int, float] = defaultdict(float)
    negative_totals: dict[int, float] = defaultdict(float)
    positive_views: dict[int, set[str]] = defaultdict(set)
    negative_views: dict[int, set[str]] = defaultdict(set)
    evidence_records: list[dict] = []
    started = time.perf_counter()

    for frame in inspection["frames"]:
        view_id = frame["view_id"]
        annotation = annotations_by_view[view_id]
        positive = mask_from_png(args.annotation_mask_dir / annotation["positive"], width, height)
        negative = mask_from_png(args.annotation_mask_dir / annotation["negative"], width, height)
        if not positive.any() and not negative.any():
            continue

        stable_ids, weights = contributor_ids_and_weights(
            means=means,
            quats=quats,
            scales=scales,
            opacities=opacities,
            sh_coeffs=sh_coeffs,
            sh_degree=arrays["sh_degree"],
            c2w=np.asarray(frame["camera_to_world"], dtype=np.float32),
            intrinsics=intrinsics,
            width=width,
            height=height,
            top_k=args.top_k,
        )
        positive_ids, positive_weights = aggregate_view_evidence(
            stable_ids, weights, positive, args.minimum_evidence_weight
        )
        negative_ids, negative_weights = aggregate_view_evidence(
            stable_ids, weights, negative, args.minimum_evidence_weight
        )
        add_evidence(positive_ids, positive_weights, view_id, positive_totals, positive_views)
        add_evidence(negative_ids, negative_weights, view_id, negative_totals, negative_views)
        evidence_records.append(
            {
                "view_id": view_id,
                "positive_stable_gaussians": int(len(positive_ids)),
                "negative_stable_gaussians": int(len(negative_ids)),
                "positive_total_contribution_weight": float(positive_weights.sum()),
                "negative_total_contribution_weight": float(negative_weights.sum()),
            }
        )

    seed_path = args.target_dir / "seed-region.npz"
    seed_ids = np.load(seed_path)["stable_gaussian_ids"].astype(np.int64)
    bounds = spec["local_candidate_region"]
    if bounds["kind"] != "aabb":
        raise ValueError("only an axis-aligned local candidate region is currently supported")
    lower = np.asarray(bounds["min"], dtype=np.float32)
    upper = np.asarray(bounds["max"], dtype=np.float32)
    if lower.shape != (3,) or upper.shape != (3,) or np.any(lower >= upper):
        raise ValueError("local candidate AABB must have ordered three-dimensional min/max values")
    local_ids = np.flatnonzero(
        np.all((arrays["means"] >= lower) & (arrays["means"] <= upper), axis=1)
    ).astype(np.int64)

    all_ids = set(local_ids.tolist()) | set(seed_ids.tolist()) | set(positive_totals) | set(negative_totals)
    selected_ids = {
        stable_id
        for stable_id, observed_views in positive_views.items()
        if len(observed_views) >= args.minimum_selected_positive_views
        and stable_id not in negative_views
    }
    rejected_ids = {
        stable_id
        for stable_id, observed_views in negative_views.items()
        if len(observed_views) >= args.minimum_rejected_negative_views
        and stable_id not in positive_views
    }
    ambiguous_ids = all_ids - selected_ids - rejected_ids
    if not selected_ids:
        raise RuntimeError("draft contains no selected Stable Gaussian IDs")
    if not rejected_ids:
        raise RuntimeError("draft contains no rejected Stable Gaussian IDs")
    if selected_ids & rejected_ids or selected_ids & ambiguous_ids or rejected_ids & ambiguous_ids:
        raise RuntimeError("draft labels are not disjoint")

    selected_array = np.asarray(sorted(selected_ids), dtype=np.uint32)
    rejected_array = np.asarray(sorted(rejected_ids), dtype=np.uint32)
    ambiguous_array = np.asarray(sorted(ambiguous_ids), dtype=np.uint32)
    scope_array = np.asarray(sorted(all_ids), dtype=np.uint32)
    truth_path = output_dir / "ground-truth-draft.npz"
    np.savez_compressed(
        truth_path,
        selected_ids=selected_array,
        rejected_ids=rejected_array,
        ambiguous_ids=ambiguous_array,
        scope_ids=scope_array,
    )

    label_lookup = np.zeros(gaussian_count, dtype=np.uint8)
    label_lookup[selected_array] = LABEL_SELECTED
    label_lookup[rejected_array] = LABEL_REJECTED
    label_lookup[ambiguous_array] = LABEL_AMBIGUOUS
    provenance_path = output_dir / "evidence-provenance.npz"
    np.savez_compressed(
        provenance_path,
        stable_gaussian_ids=scope_array,
        label=label_lookup[scope_array],
        positive_view_count=np.asarray(
            [len(positive_views[int(stable_id)]) for stable_id in scope_array], dtype=np.uint8
        ),
        negative_view_count=np.asarray(
            [len(negative_views[int(stable_id)]) for stable_id in scope_array], dtype=np.uint8
        ),
        positive_total_weight=np.asarray(
            [positive_totals[int(stable_id)] for stable_id in scope_array], dtype=np.float32
        ),
        negative_total_weight=np.asarray(
            [negative_totals[int(stable_id)] for stable_id in scope_array], dtype=np.float32
        ),
    )
    label_lookup_gpu = torch.from_numpy(label_lookup).to(device)
    projection_records: list[dict] = []
    for frame in inspection["frames"]:
        review_status = review_by_view[frame["view_id"]]["status"]
        if review_status == "insufficient":
            projection_records.append(
                {
                    "frame_index": frame["frame_index"],
                    "view_id": frame["view_id"],
                    "visual_review_status": review_status,
                    "projection_status": "excluded_insufficient_view",
                    "reason": "This view is not reliable enough to visually validate Ground Truth and did not contribute annotation evidence.",
                }
            )
            continue
        stable_ids, weights = contributor_ids_and_weights(
            means=means,
            quats=quats,
            scales=scales,
            opacities=opacities,
            sh_coeffs=sh_coeffs,
            sh_degree=arrays["sh_degree"],
            c2w=np.asarray(frame["camera_to_world"], dtype=np.float32),
            intrinsics=intrinsics,
            width=width,
            height=height,
            top_k=args.top_k,
        )
        source = np.asarray(Image.open(args.inspection_dir / frame["file"]).convert("RGB"))
        rendered = make_projection_overlay(source, stable_ids, weights, label_lookup_gpu)
        overlay_path = output_dir / "projection-overlays" / f"{frame['frame_index']:02d}-{frame['view_id']}.png"
        Image.fromarray(rendered, mode="RGB").save(overlay_path)
        projection_records.append(
            {
                "frame_index": frame["frame_index"],
                "view_id": frame["view_id"],
                "visual_review_status": review_status,
                "projection_status": "rendered",
                "overlay": str(overlay_path.relative_to(output_dir)),
                "sha256": sha256(overlay_path),
            }
        )
    projection_sheet = output_dir / "projection-overlay-contact-sheet.png"
    make_contact_sheet(projection_records, output_dir, projection_sheet)

    elapsed = time.perf_counter() - started
    manifest = {
        "schema_version": 1,
        "status": "draft-derived-from-reviewed-2d-annotations-not-frozen",
        "purpose": "Conservative three-way Benchmark Ground Truth draft; not eligible for scoring until human review freezes a new revision.",
        "target_id": target_id,
        "source_ply": {
            "path": str(args.ply),
            "sha256": sha256(args.ply),
            "gaussian_count": gaussian_count,
        },
        "inspection_set": {"path": str(inspection_path), "sha256": sha256(inspection_path)},
        "visual_review": {"path": str(review_path), "sha256": sha256(review_path)},
        "annotation_spec": {"path": str(args.annotation_spec), "sha256": sha256(args.annotation_spec)},
        "annotation_masks": {"path": str(annotation_manifest_path), "sha256": sha256(annotation_manifest_path)},
        "seed_region_context": {
            "path": str(seed_path),
            "sha256": sha256(seed_path),
            "role": "framing/candidate context only; no Seed Region ID is automatically selected or rejected",
        },
        "local_candidate_region": bounds,
        "contributor_rasterization": {
            "backend": "gsplat",
            "top_k": args.top_k,
            "minimum_evidence_weight_per_view": args.minimum_evidence_weight,
            "stable_id_mapping": "packed projection IDs are mapped through meta.gaussian_ids to immutable PLY-row Stable Gaussian IDs",
        },
        "classification_policy": {
            "selected": "positive manual/color-assisted evidence in at least the configured number of independent inspection views, with no negative evidence",
            "rejected": "negative manual evidence in at least the configured number of inspection views, with no positive evidence",
            "ambiguous": "all conflicts, single-view positive evidence, and all unlabeled IDs in the explicit local candidate region or Seed Region context",
            "minimum_selected_positive_views": args.minimum_selected_positive_views,
            "minimum_rejected_negative_views": args.minimum_rejected_negative_views,
        },
        "evidence_by_view": evidence_records,
        "labels": {
            "artifact": truth_path.name,
            "artifact_sha256": sha256(truth_path),
            "scope_stable_gaussians": int(len(scope_array)),
            "selected_stable_gaussians": int(len(selected_array)),
            "rejected_stable_gaussians": int(len(rejected_array)),
            "ambiguous_stable_gaussians": int(len(ambiguous_array)),
        },
        "evidence_provenance": {
            "artifact": provenance_path.name,
            "artifact_sha256": sha256(provenance_path),
            "description": "Per-scope Stable Gaussian positive/negative view counts and contribution totals; used to audit why a label is selected, rejected, or ambiguous.",
        },
        "projection_review": {
            "contact_sheet": projection_sheet.name,
            "contact_sheet_sha256": sha256(projection_sheet),
            "frames": projection_records,
        },
        "freeze_requirement": "A reviewer must inspect the RGB annotation and projected Stable-ID overlays, then explicitly accept or revise this draft. A frozen revision must preserve this draft artifact rather than overwrite it.",
        "timing": {
            "contributor_analysis_and_projection_seconds": elapsed,
            "peak_vram_bytes": int(torch.cuda.max_memory_allocated(device)),
        },
    }
    (output_dir / "ground-truth-draft.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

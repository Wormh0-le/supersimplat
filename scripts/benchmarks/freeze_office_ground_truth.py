#!/usr/bin/env python3
"""Freeze one reviewed office Ground Truth draft without overwriting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sorted_unique(values: np.ndarray, name: str) -> np.ndarray:
    if values.ndim != 1:
        raise RuntimeError(f"{name} must be one-dimensional")
    values = values.astype(np.uint32, copy=False)
    if len(values) and np.any(values[1:] <= values[:-1]):
        raise RuntimeError(f"{name} must be strictly sorted and unique")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--draft-dir", type=Path, required=True)
    parser.add_argument("--ground-truth-version", default="ground-truth-v1")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--acceptance-note", required=True)
    args = parser.parse_args()

    draft_manifest_path = args.draft_dir / "ground-truth-draft.json"
    draft_labels_path = args.draft_dir / "ground-truth-draft.npz"
    draft = json.loads(draft_manifest_path.read_text(encoding="utf-8"))
    if draft["status"] != "draft-derived-from-reviewed-2d-annotations-not-frozen":
        raise RuntimeError("only an explicit reviewed 2D annotation draft may be frozen")
    if sha256(draft_labels_path) != draft["labels"]["artifact_sha256"]:
        raise RuntimeError("draft label artifact hash does not match its manifest")

    labels = np.load(draft_labels_path)
    selected = sorted_unique(labels["selected_ids"], "selected_ids")
    rejected = sorted_unique(labels["rejected_ids"], "rejected_ids")
    ambiguous = sorted_unique(labels["ambiguous_ids"], "ambiguous_ids")
    scope = sorted_unique(labels["scope_ids"], "scope_ids")
    if np.intersect1d(selected, rejected).size or np.intersect1d(selected, ambiguous).size or np.intersect1d(rejected, ambiguous).size:
        raise RuntimeError("draft Stable Gaussian label sets overlap")
    if not np.array_equal(np.union1d(np.union1d(selected, rejected), ambiguous), scope):
        raise RuntimeError("draft scope does not equal the union of its three label sets")
    if len(scope) and int(scope[-1]) >= int(draft["source_ply"]["gaussian_count"]):
        raise RuntimeError("draft contains Stable Gaussian IDs outside its source scene")
    expected_counts = draft["labels"]
    if (
        len(selected) != expected_counts["selected_stable_gaussians"]
        or len(rejected) != expected_counts["rejected_stable_gaussians"]
        or len(ambiguous) != expected_counts["ambiguous_stable_gaussians"]
        or len(scope) != expected_counts["scope_stable_gaussians"]
    ):
        raise RuntimeError("draft label counts do not match its manifest")

    output_dir = args.target_dir / args.ground_truth_version
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing frozen Ground Truth: {output_dir}")
    output_dir.mkdir(parents=True)
    frozen_labels_path = output_dir / "ground-truth.npz"
    frozen_draft_path = output_dir / "source-ground-truth-draft.json"
    shutil.copy2(draft_labels_path, frozen_labels_path)
    shutil.copy2(draft_manifest_path, frozen_draft_path)

    frozen_manifest = {
        "schema_version": 1,
        "status": "frozen",
        "purpose": "Method-independent Benchmark Ground Truth for a fixed office target and Scene Snapshot",
        "ground_truth_version": args.ground_truth_version,
        "target_id": draft["target_id"],
        "source_ply": draft["source_ply"],
        "labels": {
            "artifact": frozen_labels_path.name,
            "artifact_sha256": sha256(frozen_labels_path),
            "scope_stable_gaussians": int(len(scope)),
            "selected_stable_gaussians": int(len(selected)),
            "rejected_stable_gaussians": int(len(rejected)),
            "ambiguous_stable_gaussians": int(len(ambiguous)),
            "metric_rule": "Compute accuracy only within scope_ids and exclude ambiguous_ids. Candidate uncertainty counts as not selected for selected truth IDs.",
        },
        "source_draft": {
            "path": str(args.draft_dir),
            "manifest": frozen_draft_path.name,
            "manifest_sha256": sha256(frozen_draft_path),
            "labels_sha256": sha256(draft_labels_path),
            "annotation_spec": draft["annotation_spec"],
            "annotation_masks": draft["annotation_masks"],
            "inspection_set": draft["inspection_set"],
            "visual_review": draft["visual_review"],
            "projection_review": draft["projection_review"],
        },
        "review_acceptance": {
            "reviewer": args.reviewer,
            "note": args.acceptance_note,
            "frozen_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
        "immutability": "Later corrections require a new Ground Truth version. This artifact and the source draft are preserved unchanged for prior benchmark results.",
    }
    manifest_path = output_dir / "ground-truth.json"
    manifest_path.write_text(json.dumps(frozen_manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(frozen_manifest, indent=2))


if __name__ == "__main__":
    main()

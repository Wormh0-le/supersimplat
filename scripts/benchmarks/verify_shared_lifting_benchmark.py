#!/usr/bin/env python3
"""Verify the frozen shared lifting benchmark input manifest and its index."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from materialize_shared_lifting_benchmark_manifest import collect_manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    fixtures_root = args.fixtures_root.resolve()
    manifest_path = args.manifest or fixtures_root / "shared-lifting-benchmark-v2.json"
    actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmark_version = actual.get("benchmark_version")
    expected = collect_manifest(fixtures_root, benchmark_version=benchmark_version)
    violations: list[str] = []
    if actual != expected:
        violations.append("shared manifest content does not match the hash-validated fixture graph")

    targets_index_path = fixtures_root / "office" / "targets" / "targets.json"
    targets_index = json.loads(targets_index_path.read_text(encoding="utf-8"))
    if targets_index.get("status") != "shared-lifting-fixtures-frozen":
        violations.append("office target index is not marked shared-lifting-fixtures-frozen")
    manifest_ref = targets_index.get("shared_lifting_benchmark_manifest")
    if manifest_ref != {
        "path": f"../../{manifest_path.name}",
        "sha256": sha256(manifest_path),
        "version": benchmark_version,
    }:
        violations.append("office target index does not hash-bind the shared benchmark manifest")

    expected_targets = {target["target_id"]: target for target in actual.get("office_targets", [])}
    indexed_targets = {target["id"]: target for target in targets_index.get("targets", [])}
    if set(expected_targets) != set(indexed_targets):
        violations.append("office target index and shared manifest target IDs differ")
    for target_id, target in expected_targets.items():
        indexed = indexed_targets[target_id]
        expected_ground_truth = target["ground_truth"]
        expected_ref = {
            "status": "frozen",
            "version": expected_ground_truth["version"],
            "manifest": f"{target_id}/ground-truth-v1/ground-truth.json",
            "manifest_sha256": expected_ground_truth["sha256"],
            "labels": f"{target_id}/ground-truth-v1/ground-truth.npz",
            "labels_sha256": expected_ground_truth["labels"]["sha256"],
            "scope_stable_gaussians": expected_ground_truth["labels"]["scope_stable_gaussians"],
            "selected_stable_gaussians": expected_ground_truth["labels"]["selected_stable_gaussians"],
            "rejected_stable_gaussians": expected_ground_truth["labels"]["rejected_stable_gaussians"],
            "ambiguous_stable_gaussians": expected_ground_truth["labels"]["ambiguous_stable_gaussians"],
        }
        if indexed.get("ground_truth") != expected_ref:
            violations.append(f"{target_id} target index does not bind its frozen Ground Truth")

    payload = {
        "status": "pass" if not violations else "fail",
        "manifest": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "office_target_ids": sorted(expected_targets),
        "violations": violations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()

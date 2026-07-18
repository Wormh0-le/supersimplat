#!/usr/bin/env python3
"""Build the immutable entry point for the shared lifting benchmark inputs.

The manifest deliberately contains only inputs shared by every lifting
candidate.  It does not contain a candidate's implementation, predicted IDs,
or scores.  Its references are hash-pinned so a later candidate cannot
silently consume a different scene, frame set, mask set, or Ground Truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RuntimeError(f"cannot read {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def require_hash(path: Path, expected: str, role: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{role} hash mismatch: {path} has {actual}, expected {expected}")


def require_frozen(manifest: dict[str, Any], path: Path, role: str) -> None:
    if manifest.get("status") != "frozen":
        raise RuntimeError(f"{role} is not frozen: {path}")


def require_sorted_unique(values: np.ndarray, role: str) -> np.ndarray:
    if values.ndim != 1:
        raise RuntimeError(f"{role} must be one-dimensional")
    values = values.astype(np.uint32, copy=False)
    if len(values) and np.any(values[1:] <= values[:-1]):
        raise RuntimeError(f"{role} must be strictly sorted and unique")
    return values


def relative_to(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def artifact(root: Path, path: Path, **details: Any) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing artifact: {path}")
    result: dict[str, Any] = {"path": relative_to(root, path), "sha256": sha256(path)}
    result.update(details)
    return result


def require_relative_reference(base: Path, recorded: str, expected: Path, role: str) -> None:
    resolved = (base / recorded).resolve()
    if resolved != expected.resolve():
        raise RuntimeError(f"{role} path resolves to {resolved}, expected {expected}")


def resolve_project_reference(fixtures_root: Path, recorded: str) -> Path:
    path = Path(recorded)
    if path.is_absolute():
        return path
    # Frozen Ground Truth provenance records project-relative paths so that its
    # review artifacts remain readable without coupling them to a target path.
    return (fixtures_root.parents[2] / path).resolve()


def check_label_sets(labels_path: Path, labels: dict[str, Any], source_count: int, role: str) -> dict[str, int]:
    require_hash(labels_path, labels["artifact_sha256"], f"{role} labels")
    source = np.load(labels_path)
    selected = require_sorted_unique(source["selected_ids"], f"{role} selected_ids")
    rejected = require_sorted_unique(source["rejected_ids"], f"{role} rejected_ids")
    ambiguous = require_sorted_unique(source["ambiguous_ids"], f"{role} ambiguous_ids")
    scope = require_sorted_unique(source["scope_ids"], f"{role} scope_ids")
    if np.intersect1d(selected, rejected).size or np.intersect1d(selected, ambiguous).size or np.intersect1d(rejected, ambiguous).size:
        raise RuntimeError(f"{role} Ground Truth label sets overlap")
    if not np.array_equal(np.union1d(np.union1d(selected, rejected), ambiguous), scope):
        raise RuntimeError(f"{role} scope is not the union of its labels")
    if len(scope) and int(scope[-1]) >= source_count:
        raise RuntimeError(f"{role} Ground Truth contains an ID outside its Scene Snapshot")
    counts = {
        "scope_stable_gaussians": int(len(scope)),
        "selected_stable_gaussians": int(len(selected)),
        "rejected_stable_gaussians": int(len(rejected)),
        "ambiguous_stable_gaussians": int(len(ambiguous)),
    }
    for key, value in counts.items():
        if labels.get(key) != value:
            raise RuntimeError(f"{role} {key} disagrees with its NPZ")
    return counts


def controlled_fixture(fixtures_root: Path) -> dict[str, Any]:
    fixture_dir = fixtures_root / "controlled-overlap"
    source_manifest_path = fixture_dir / "controlled_front_back_overlap.json"
    source_manifest = load_json(source_manifest_path)
    ply_path = fixture_dir / "controlled_front_back_overlap.ply"
    truth_path = fixture_dir / "controlled_front_back_overlap_ground_truth.npz"
    require_hash(ply_path, source_manifest["files"][ply_path.name]["sha256"], "controlled Scene Snapshot")
    require_hash(truth_path, source_manifest["files"][truth_path.name]["sha256"], "controlled Ground Truth")

    truth = np.load(truth_path)
    selected = require_sorted_unique(truth["selected_ids"], "controlled selected_ids")
    rejected = require_sorted_unique(truth["rejected_ids"], "controlled rejected_ids")
    ambiguous = require_sorted_unique(truth["ambiguous_ids"], "controlled ambiguous_ids")
    total = int(source_manifest["gaussianCount"])
    if np.intersect1d(selected, rejected).size or np.intersect1d(selected, ambiguous).size or np.intersect1d(rejected, ambiguous).size:
        raise RuntimeError("controlled Ground Truth label sets overlap")
    if len(selected) + len(rejected) + len(ambiguous) != total:
        raise RuntimeError("controlled Ground Truth does not classify every Gaussian")
    # ADR 0011: the distractor-enclosed cap moved from selected to ambiguous;
    # selected and ambiguous now partition the exact target range.
    target_range = np.arange(int(source_manifest["targetCount"]), dtype=np.uint32)
    if not np.array_equal(np.sort(np.concatenate((selected, ambiguous))), target_range):
        raise RuntimeError(
            "controlled selected and ambiguous Stable Gaussian IDs do not partition the exact target range"
        )
    if not np.array_equal(
        rejected,
        np.arange(int(source_manifest["targetCount"]), total, dtype=np.uint32),
    ):
        raise RuntimeError("controlled rejected Stable Gaussian IDs are not the exact distractor range")

    frame_set_path = fixture_dir / "frame-set-v1" / "frame-set.json"
    mask_set_path = fixture_dir / "frame-set-v1" / "mask-set-v1" / "mask-set.json"
    coverage_path = fixture_dir / "frame-set-v1" / "coverage-report-v1" / "coverage-report.json"
    frame_set = load_json(frame_set_path)
    mask_set = load_json(mask_set_path)
    coverage = load_json(coverage_path)
    require_frozen(frame_set, frame_set_path, "controlled Frame Set")
    require_frozen(mask_set, mask_set_path, "controlled Mask Set")
    require_frozen(coverage, coverage_path, "controlled Coverage Report")
    if frame_set["scene"]["sha256"] != sha256(ply_path):
        raise RuntimeError("controlled Frame Set points at a different Scene Snapshot")
    require_relative_reference(frame_set_path.parent, frame_set["scene"]["ply"], ply_path, "controlled Frame Set Scene Snapshot")
    require_hash(frame_set_path, mask_set["frame_set"]["sha256"], "controlled Mask Set Frame Set")
    require_hash(truth_path, mask_set["ground_truth"]["sha256"], "controlled Mask Set Ground Truth")
    require_relative_reference(mask_set_path.parent, mask_set["frame_set"]["path"], frame_set_path, "controlled Mask Set Frame Set")
    require_relative_reference(mask_set_path.parent, mask_set["ground_truth"]["path"], truth_path, "controlled Mask Set Ground Truth")
    require_hash(frame_set_path, coverage["frame_set"]["sha256"], "controlled Coverage Frame Set")
    require_hash(mask_set_path, coverage["mask_set"]["sha256"], "controlled Coverage Mask Set")
    require_hash(ply_path, coverage["scene"]["sha256"], "controlled Coverage Scene Snapshot")
    require_relative_reference(coverage_path.parent, coverage["scene"]["ply"], ply_path, "controlled Coverage Scene Snapshot")
    require_relative_reference(coverage_path.parent, coverage["frame_set"]["path"], frame_set_path, "controlled Coverage Frame Set")
    require_relative_reference(coverage_path.parent, coverage["mask_set"]["path"], mask_set_path, "controlled Coverage Mask Set")

    masks_path = mask_set_path.parent / mask_set["masks"]["path"]
    require_hash(masks_path, mask_set["masks"]["sha256"], "controlled mask tensor")
    masks = np.load(masks_path)["masks"]
    if masks.ndim != 3 or tuple(masks.shape) != tuple(mask_set["masks"]["shape"]):
        raise RuntimeError("controlled mask tensor shape disagrees with its manifest")
    if masks.shape[0] != len(frame_set["frames"]) or masks.shape[0] != len(mask_set["frames"]):
        raise RuntimeError("controlled Frame Set and Mask Set frame counts differ")
    for frame, track in zip(frame_set["frames"], mask_set["frames"], strict=True):
        frame_path = frame_set_path.parent / frame["file"]
        require_hash(frame_path, frame["sha256"], f"controlled frame {frame['candidate_id']}")
        if track["frame_sha256"] != frame["sha256"]:
            raise RuntimeError(f"controlled mask record is bound to another frame: {frame['candidate_id']}")
        if int(masks[track["binary_mask_index"]].sum()) != track["mask_area_pixels"]:
            raise RuntimeError(f"controlled mask area disagrees for {frame['candidate_id']}")

    observed_path = coverage_path.parent / coverage["observed_target_contributors"]["artifact"]
    require_hash(observed_path, coverage["observed_target_contributors"]["sha256"], "controlled observed contributor IDs")
    observed = require_sorted_unique(np.load(observed_path)["stable_gaussian_ids"], "controlled observed contributor IDs")
    if len(observed) != coverage["observed_target_contributors"]["count"]:
        raise RuntimeError("controlled observed contributor count disagrees with its NPZ")
    if len(observed) and int(observed[-1]) >= int(source_manifest["targetCount"]):
        raise RuntimeError("controlled observed contributors include distractor IDs")
    mask_overlay_sheet_path = mask_set_path.parent / "overlay-contact-sheet.png"

    return {
        "scene_id": "controlled_front_back_overlap",
        "kind": "synthetic-controlled-overlap",
        "purpose": "Exact Stable Gaussian ID evaluation with deliberate front/back distractor overlap.",
        "scene_snapshot": artifact(
            fixtures_root,
            ply_path,
            gaussian_count=total,
            stable_id_dtype=source_manifest["stableId"]["dtype"],
        ),
        "ground_truth": artifact(
            fixtures_root,
            truth_path,
            label_counts={
                "selected_stable_gaussians": int(len(selected)),
                "rejected_stable_gaussians": int(len(rejected)),
                "ambiguous_stable_gaussians": int(len(ambiguous)),
            },
            semantics="Exact target/distractor Stable Gaussian IDs supplied by the deterministic generator.",
        ),
        "frame_set": artifact(
            fixtures_root,
            frame_set_path,
            version=frame_set["frame_set_version"],
            frames=len(frame_set["frames"]),
            resolution=frame_set["resolution"],
        ),
        "mask_set": artifact(
            fixtures_root,
            mask_set_path,
            version=mask_set["mask_set_version"],
            mask_tensor=artifact(fixtures_root, masks_path, shape=list(masks.shape)),
            derivation=mask_set["mask_derivation"],
            timing=mask_set["timing"],
        ),
        "coverage_report": artifact(
            fixtures_root,
            coverage_path,
            status_value=coverage["status_value"],
            observed_target_contributors=coverage["observed_target_contributors"],
        ),
        "diagnostics": {
            "mask_overlay_contact_sheet": artifact(fixtures_root, mask_overlay_sheet_path),
            "camera_specification": "camera_to_world matrices are embedded in the hash-pinned Frame Set.",
        },
    }


def office_target(fixtures_root: Path, targets_root: Path, target: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    target_id = target["id"]
    target_dir = targets_root / target_id
    frame_info = target["frame_set"]
    frame_set_path = targets_root / frame_info["manifest"]
    mask_set_path = targets_root / frame_info["mask_set"]
    coverage_path = targets_root / frame_info["coverage_report"]
    ground_truth_path = target_dir / "ground-truth-v1" / "ground-truth.json"
    labels_path = ground_truth_path.parent / "ground-truth.npz"
    frame_set = load_json(frame_set_path)
    mask_set = load_json(mask_set_path)
    coverage = load_json(coverage_path)
    ground_truth = load_json(ground_truth_path)
    if not str(frame_info["status"]).startswith("accepted"):
        raise RuntimeError(f"{target_id} Frame Set is not accepted by the target index")
    if frame_set.get("status") not in {"candidate-frame-set-mask-validation-pending", "accepted", "frozen"}:
        raise RuntimeError(f"{target_id} has an unsupported Frame Set status: {frame_set.get('status')}")
    for manifest, path, role in (
        (mask_set, mask_set_path, "office Mask Set"),
        (coverage, coverage_path, "office Coverage Report"),
        (ground_truth, ground_truth_path, "office Ground Truth"),
    ):
        require_frozen(manifest, path, f"{role} for {target_id}")
    if ground_truth["target_id"] != target_id or mask_set["target_id"] != target_id or coverage["target_id"] != target_id:
        raise RuntimeError(f"{target_id} has cross-target benchmark artifacts")
    if frame_set["source_ply"] != scene["ply"]:
        raise RuntimeError(f"{target_id} Frame Set uses a different office Scene Snapshot")
    if ground_truth["source_ply"]["sha256"] != scene["ply_sha256"]:
        raise RuntimeError(f"{target_id} Ground Truth uses a different office Scene Snapshot")
    if coverage["source_ply"]["sha256"] != scene["ply_sha256"]:
        raise RuntimeError(f"{target_id} Coverage Report uses a different office Scene Snapshot")
    require_hash(frame_set_path, frame_info["manifest_sha256"], f"{target_id} Frame Set")
    require_hash(mask_set_path, frame_info["mask_set_sha256"], f"{target_id} Mask Set")
    require_hash(coverage_path, frame_info["coverage_report_sha256"], f"{target_id} Coverage Report")
    require_hash(frame_set_path, mask_set["frame_set"]["sha256"], f"{target_id} Mask Set Frame Set")
    require_hash(frame_set_path, coverage["frame_set"]["sha256"], f"{target_id} Coverage Frame Set")
    require_hash(mask_set_path, coverage["mask_set"]["sha256"], f"{target_id} Coverage Mask Set")
    require_hash(labels_path, ground_truth["labels"]["artifact_sha256"], f"{target_id} Ground Truth labels")
    if ground_truth["labels"]["artifact_sha256"] != sha256(labels_path):
        raise RuntimeError(f"{target_id} Ground Truth label hash is stale")
    label_counts = check_label_sets(labels_path, ground_truth["labels"], int(scene["gaussian_count"]), target_id)

    masks_path = mask_set_path.parent / "masks.npz"
    expected_masks_hash = mask_set["source_tracking"]["masks_sha256"]
    require_hash(masks_path, expected_masks_hash, f"{target_id} mask tensor")
    if frame_info["mask_tensor_sha256"] != expected_masks_hash:
        raise RuntimeError(f"{target_id} target index points at a different mask tensor")
    masks = np.load(masks_path)["masks"]
    track_frames = [frame for track in mask_set["tracks"] for frame in track["frames"]]
    if masks.ndim != 3 or masks.shape[0] != len(track_frames):
        raise RuntimeError(f"{target_id} mask tensor does not align with its tracks")
    frame_records = {frame["frame_index"]: frame for frame in frame_set["frames"]}
    for frame in track_frames:
        source_frame = frame_records.get(frame["frame_index"])
        if source_frame is None:
            raise RuntimeError(f"{target_id} track refers to a missing Frame Set frame")
        if source_frame["sha256"] != frame["frame_sha256"]:
            raise RuntimeError(f"{target_id} track is bound to a different frame hash")
        require_hash(frame_set_path.parent / source_frame["file"], source_frame["sha256"], f"{target_id} frame {frame['frame_index']}")
        index = frame.get("binary_mask_index")
        if frame["status"] == "not_found":
            if index is not None or frame["mask_area_pixels"] != 0:
                raise RuntimeError(f"{target_id} not-found view has a materialized foreground mask")
            continue
        if index is None or index < 0 or index >= masks.shape[0]:
            raise RuntimeError(f"{target_id} has an invalid binary mask index")
        if int(masks[index].sum()) != frame["mask_area_pixels"]:
            raise RuntimeError(f"{target_id} mask area differs from the frozen track record")
    accepted_frames = [frame for frame in track_frames if frame["status"] == "accepted"]
    if len(accepted_frames) != frame_info["accepted_views"]:
        raise RuntimeError(f"{target_id} accepted view count disagrees with its Mask Set")
    if frame_info.get("not_found_views", 0) != sum(frame["status"] == "not_found" for frame in track_frames):
        raise RuntimeError(f"{target_id} not-found view count disagrees with its Mask Set")

    prompt_path = targets_root / target["tracking_prompt"]["prompt_script"]
    require_hash(prompt_path, target["tracking_prompt"]["prompt_script_sha256"], f"{target_id} prompt script")
    anchor_image_path = targets_root / target["anchor_candidate"]["image"]
    anchor_camera_path = targets_root / target["anchor_candidate"]["camera_manifest"]
    require_hash(anchor_image_path, target["anchor_candidate"]["image_sha256"], f"{target_id} anchor image")
    require_hash(anchor_camera_path, target["anchor_candidate"]["camera_manifest_sha256"], f"{target_id} anchor camera manifest")
    tracking_path = targets_root / mask_set["source_tracking"]["path"]
    require_hash(tracking_path, mask_set["source_tracking"]["sha256"], f"{target_id} source tracking")
    tracking = load_json(tracking_path)
    observed_path = coverage_path.parent / coverage["contributor_observation"]["artifact"]
    require_hash(observed_path, coverage["contributor_observation"]["artifact_sha256"], f"{target_id} observed contributors")
    observed = require_sorted_unique(np.load(observed_path)["stable_gaussian_ids"], f"{target_id} observed contributors")
    if len(observed) != coverage["contributor_observation"]["observed_stable_gaussians"]:
        raise RuntimeError(f"{target_id} observed contributor count disagrees with its report")
    source_draft = ground_truth["source_draft"]
    source_draft_path = resolve_project_reference(fixtures_root, source_draft["path"])
    projection_sheet_path = source_draft_path / source_draft["projection_review"]["contact_sheet"]
    require_hash(
        projection_sheet_path,
        source_draft["projection_review"]["contact_sheet_sha256"],
        f"{target_id} Ground Truth projection diagnostic",
    )
    annotation_masks_path = resolve_project_reference(fixtures_root, source_draft["annotation_masks"]["path"])
    visual_review_path = resolve_project_reference(fixtures_root, source_draft["visual_review"]["path"])
    require_hash(annotation_masks_path, source_draft["annotation_masks"]["sha256"], f"{target_id} annotation mask manifest")
    require_hash(visual_review_path, source_draft["visual_review"]["sha256"], f"{target_id} visual review")
    frame_contact_sheet_path = frame_set_path.parent / "contact-sheet.png"
    mask_overlay_sheet_path = mask_set_path.parent / "overlay-contact-sheet.png"

    return {
        "target_id": target_id,
        "display_name_zh": target["display_name_zh"],
        "benchmark_role": target["benchmark_role"],
        "identity": target["identity"],
        "scene_snapshot": {
            "path": scene["ply"],
            "sha256": scene["ply_sha256"],
            "gaussian_count": scene["gaussian_count"],
        },
        "anchor": {
            "image": target["anchor_candidate"]["image"],
            "image_sha256": target["anchor_candidate"]["image_sha256"],
            "camera_manifest": target["anchor_candidate"]["camera_manifest"],
            "camera_manifest_sha256": target["anchor_candidate"]["camera_manifest_sha256"],
        },
        "prompt_replay": artifact(
            fixtures_root,
            prompt_path,
            adapter=target["tracking_prompt"]["adapter"],
            prompt_type=target["tracking_prompt"]["prompt_type"],
        ),
        "frame_set": artifact(
            fixtures_root,
            frame_set_path,
            version=frame_info["version"],
            source_status=frame_set["status"],
            acceptance_status=frame_info["status"],
            accepted_views=len(accepted_frames),
            not_found_views=frame_info.get("not_found_views", 0),
        ),
        "mask_set": artifact(
            fixtures_root,
            mask_set_path,
            version=mask_set["mask_set_version"],
            mask_tensor=artifact(fixtures_root, masks_path, shape=list(masks.shape)),
            model_manifest=mask_set["model_manifest"],
            tracking=artifact(
                fixtures_root,
                tracking_path,
                model_build_seconds=tracking["model_build_seconds"],
                tracking_seconds=tracking["tracking_seconds"],
                peak_vram_bytes=tracking["peak_vram_bytes"],
            ),
        ),
        "coverage_report": artifact(
            fixtures_root,
            coverage_path,
            status_value=coverage["status_value"],
            observed_contributors=artifact(fixtures_root, observed_path, count=int(len(observed))),
            timing=coverage["timing"],
        ),
        "ground_truth": artifact(
            fixtures_root,
            ground_truth_path,
            version=ground_truth["ground_truth_version"],
            labels=artifact(fixtures_root, labels_path, **label_counts),
            metric_rule=ground_truth["labels"]["metric_rule"],
            review_acceptance=ground_truth["review_acceptance"],
        ),
        "diagnostics": {
            "frame_set_contact_sheet": artifact(fixtures_root, frame_contact_sheet_path),
            "mask_overlay_contact_sheet": artifact(fixtures_root, mask_overlay_sheet_path),
            "ground_truth_projection_overlay_contact_sheet": artifact(fixtures_root, projection_sheet_path),
            "ground_truth_annotation_masks": artifact(fixtures_root, annotation_masks_path),
            "ground_truth_visual_review": artifact(fixtures_root, visual_review_path),
            "camera_specification": "camera_to_world matrices are embedded in the hash-pinned Frame Set; the anchor camera manifest is separately hash-pinned above.",
        },
    }


def collect_manifest(fixtures_root: Path, benchmark_version: str = "shared-lifting-benchmark-v1") -> dict[str, Any]:
    fixtures_root = fixtures_root.resolve()
    targets_root = fixtures_root / "office" / "targets"
    targets_index_path = targets_root / "targets.json"
    targets_index = load_json(targets_index_path)
    scene = dict(targets_index["scene"])
    office_ply = Path(scene["ply"])
    if not office_ply.is_file():
        raise RuntimeError(f"office Scene Snapshot is unavailable: {office_ply}")
    require_hash(office_ply, scene["ply_sha256"], "office Scene Snapshot")
    # The frozen per-target Ground Truth is the authoritative source for the PLY count.
    first_ground_truth = load_json(targets_root / targets_index["targets"][0]["id"] / "ground-truth-v1" / "ground-truth.json")
    scene["gaussian_count"] = int(first_ground_truth["source_ply"]["gaussian_count"])
    if len(targets_index["targets"]) != 3:
        raise RuntimeError("shared office benchmark must contain exactly simple/contact/difficult targets")
    roles = {target["benchmark_role"] for target in targets_index["targets"]}
    if roles != {"simple", "contact", "difficult"}:
        raise RuntimeError("office targets must provide exactly simple, contact, and difficult roles")

    office_targets = [office_target(fixtures_root, targets_root, target, scene) for target in targets_index["targets"]]
    return {
        "schema_version": 1,
        "status": "frozen",
        "benchmark_version": benchmark_version,
        "purpose": "Byte-identical shared Scene Snapshots, Frame Sets, Mask Sets, Coverage Reports, and method-independent Ground Truth for lifting-method comparison.",
        "candidate_input_contract": {
            "required": [
                "Consume the referenced Scene Snapshot, Frame Set, and Mask Set byte-for-byte for a named fixture.",
                "Do not use the Ground Truth or its projection/annotation artifacts during prediction.",
                "Report selected Stable Gaussian IDs, any uncertain IDs, implementation version, configuration, seed, timing, and peak VRAM separately from this frozen input manifest.",
            ],
            "coverage_interpretation": "Coverage Reports are observation facts, not selection labels. An insufficient_coverage status requires unobserved regions to remain distinguishable in a candidate result; it does not invalidate the shared fixture.",
            "office_metric": "Evaluate only scope_ids, exclude ambiguous_ids, and score a candidate uncertainty as not selected for selected truth IDs.",
        },
        "controlled_fixture": controlled_fixture(fixtures_root),
        "office_scene_snapshot": {
            "path": scene["ply"],
            "sha256": scene["ply_sha256"],
            "gaussian_count": scene["gaussian_count"],
        },
        "office_targets": office_targets,
        "candidate_result_contract": {
            "required_fields": [
                "benchmark_version",
                "target_or_fixture_id",
                "shared_input_hashes",
                "candidate_name",
                "candidate_version_or_commit",
                "configuration",
                "seed",
                "selected_stable_gaussian_ids",
                "uncertain_stable_gaussian_ids",
                "runtime_seconds",
                "peak_vram_bytes",
            ],
            "note": "Candidate outputs and scores are intentionally absent from this shared-input freeze.",
        },
        "immutability": "Any correction to a shared input requires a new versioned artifact and a new shared-lifting-benchmark manifest; existing results remain bound to this manifest hash.",
        "verification": {
            "command": "thirdparty/sam3/.venv/bin/python scripts/benchmarks/verify_shared_lifting_benchmark.py --fixtures-root docs/benchmarks/fixtures",
            "scope": "hash bindings, label-set integrity, frame/mask alignment, target roles, and references to one Scene Snapshot per fixture",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--benchmark-version",
        default="shared-lifting-benchmark-v1",
        help=(
            "benchmark version recorded in the manifest and used for the "
            "default output filename; a corrected shared input requires a "
            "new version (ADR 0011 re-binds the graph as v2)"
        ),
    )
    args = parser.parse_args()
    output = args.output or args.fixtures_root / f"{args.benchmark_version}.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing shared benchmark manifest: {output}")
    manifest = collect_manifest(args.fixtures_root, benchmark_version=args.benchmark_version)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "sha256": sha256(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

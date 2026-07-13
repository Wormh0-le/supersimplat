#!/usr/bin/env python3
"""Track a replayable SAM3.1 prompt through an ordered candidate Frame Set."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from sam3 import build_sam3_predictor


PREVIEW_CONFIG_VERSION = "preview-512-v2-anchor-radius"
REPO_ROOT = Path(__file__).resolve().parents[2]


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


def sam3_source_commit() -> str:
    """Pin the adapter source that interpreted the checkpoint and prompt."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT / "thirdparty" / "sam3"), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def install_init_state_signature_adapter(predictor) -> None:
    """Bridge the SAM3.1 wrapper/model init_state signature mismatch locally."""
    original = predictor.model.init_state
    accepted = set(inspect.signature(original).parameters)

    def compatible_init_state(**kwargs):
        return original(**{key: value for key, value in kwargs.items() if key in accepted})

    predictor.model.init_state = compatible_init_state


def tracking_order(candidates: list[dict], allowed_ids: set[str] | None = None) -> list[dict]:
    by_id = {candidate["id"]: candidate for candidate in candidates}
    ids = ["anchor", "upper-00"]
    for ring in range(1, 12):
        ids.append(f"ring-{ring:02d}")
        if ring in (3, 6, 9):
            ids.append(f"upper-{ring // 3:02d}")
    # Replacements are inserted after the planned path in this preview.  Final
    # Frame Set ordering will be rebuilt by nearest accepted camera distance.
    ids.extend(
        candidate["id"]
        for candidate in candidates
        if candidate["category"] == "replacement"
    )
    # Invalid preflight views remain recorded but do not destabilize tracking.
    return [
        by_id[candidate_id]
        for candidate_id in ids
        if candidate_id in by_id
        and by_id[candidate_id]["render_status"] == "rendered"
        and (allowed_ids is None or candidate_id in allowed_ids)
    ]


def to_numpy(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def write_overlay(image_path: Path, mask: np.ndarray, output_path: Path) -> None:
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.float32)
    output = image.copy()
    output[mask] = 0.55 * output[mask] + 0.45 * np.asarray([30, 220, 80], dtype=np.float32)
    Image.fromarray(np.clip(output, 0, 255).astype(np.uint8)).save(output_path)


def write_overlay_contact_sheet(records: list[dict], overlay_dir: Path, output_path: Path) -> None:
    """Make the visual acceptance review an explicit, replayable artifact."""
    thumbnail_size = 252
    label_height = 30
    columns = 4
    rows = max(1, (len(records) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * thumbnail_size, rows * (thumbnail_size + label_height)), "#202020")
    draw = ImageDraw.Draw(sheet)
    for record in records:
        image = Image.open(overlay_dir.parent / record["overlay"]).convert("RGB")
        image.thumbnail((thumbnail_size, thumbnail_size))
        index = record["frame_index"]
        x = (index % columns) * thumbnail_size
        y = (index // columns) * (thumbnail_size + label_height)
        sheet.paste(image, (x, y))
        draw.text(
            (x + 4, y + thumbnail_size + 5),
            f"{record['candidate_id']} · {record['mask_area_pixels']} px",
            fill="white",
        )
    sheet.save(output_path)


def effective_prompt(
    *,
    prompt_script_path: Path | None,
    diagnostic_text_prompt: str | None,
    anchor_mask_prompt: dict,
    target_id: str,
    frame_set: dict | None,
    targets_root: Path,
) -> tuple[dict, dict | None, str | None]:
    """Return the exact adapter prompt and optional provenance-bearing script."""
    if prompt_script_path is None:
        prompt = dict(anchor_mask_prompt)
        if diagnostic_text_prompt:
            prompt["prompt_type"] = "positive_box_and_text"
            prompt["text"] = diagnostic_text_prompt
        return prompt, None, None

    script = json.loads(prompt_script_path.read_text(encoding="utf-8"))
    if script.get("target_id") != target_id:
        raise RuntimeError("prompt script target_id does not match --target")
    if frame_set is not None:
        expected_version = script.get("frame_set_version")
        if expected_version and expected_version != frame_set["frame_set_version"]:
            raise RuntimeError("prompt script frame_set_version does not match the input Frame Set")
        expected_manifest_sha256 = script.get("frame_set_manifest_sha256")
        if expected_manifest_sha256 and expected_manifest_sha256 != sha256(targets_root / target_id / frame_set["frame_set_version"] / "frame-set.json"):
            raise RuntimeError("prompt script Frame Set digest does not match the input Frame Set")
    prompt = script.get("adapter_prompt")
    if not isinstance(prompt, dict):
        raise RuntimeError("prompt script must contain an adapter_prompt object")
    return prompt, script, sha256(prompt_script_path)


def validate_prompt(prompt: dict) -> None:
    if prompt.get("prompt_type") not in {"positive_box", "positive_box_and_text"}:
        raise RuntimeError("tracking requires a positive_box or positive_box_and_text adapter prompt")
    if prompt.get("box_format") != "relative_xywh":
        raise RuntimeError("tracking requires a relative_xywh positive box")
    box = prompt.get("box")
    if not isinstance(box, list) or len(box) != 4 or not all(isinstance(value, (int, float)) for value in box):
        raise RuntimeError("tracking prompt box must contain four finite numeric values")
    if not all(np.isfinite(box)):
        raise RuntimeError("tracking prompt box must be finite")
    if prompt.get("prompt_type") == "positive_box_and_text" and not isinstance(prompt.get("text"), str):
        raise RuntimeError("positive_box_and_text requires a text string")
    if not isinstance(prompt.get("output_prob_threshold", 0.5), (int, float)):
        raise RuntimeError("tracking prompt output_prob_threshold must be numeric")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=("gift_box", "microwave", "clothes_rack"), required=True)
    parser.add_argument("--candidate-id", action="append", default=[])
    parser.add_argument("--run-name", default="selected-preview")
    parser.add_argument("--frame-set-dir", type=Path)
    parser.add_argument("--offload-video-to-cpu", action="store_true")
    parser.add_argument("--candidate-config-version", default=PREVIEW_CONFIG_VERSION)
    prompt_source = parser.add_mutually_exclusive_group()
    prompt_source.add_argument(
        "--prompt-script",
        type=Path,
        help="Replayable accepted adapter prompt script. Required for a non-diagnostic Mask Set.",
    )
    prompt_source.add_argument(
        "--text-prompt",
        help="Diagnostic-only text combined with the frozen positive box; use --prompt-script to freeze it.",
    )
    args = parser.parse_args()

    targets = json.loads((args.targets_root / "targets.json").read_text())
    target = next(item for item in targets["targets"] if item["id"] == args.target)
    if args.frame_set_dir:
        candidate_dir = args.frame_set_dir
        frame_set_path = candidate_dir / "frame-set.json"
        frame_set = json.loads(frame_set_path.read_text())
        if frame_set["target_id"] != args.target:
            raise RuntimeError("frame set target does not match --target")
        ordered = [
            {
                "id": frame["candidate_id"],
                "category": frame["category"],
                "file": frame["file"],
                "sha256": frame["sha256"],
                "render_status": "rendered",
            }
            for frame in frame_set["frames"]
        ]
        resolution = frame_set["resolution"]
        input_manifest = {
            "kind": "frame_set",
            "path": relative_to_or_absolute(frame_set_path, args.targets_root),
            "sha256": sha256(frame_set_path),
            "frame_set_version": frame_set["frame_set_version"],
        }
    else:
        candidate_dir = args.targets_root / args.target / f"generated-view-candidates-{args.candidate_config_version}"
        candidate_manifest = json.loads((candidate_dir / "candidates.json").read_text())
        allowed_ids = set(args.candidate_id) if args.candidate_id else None
        if allowed_ids is not None:
            allowed_ids.add("anchor")
        ordered = tracking_order(candidate_manifest["candidates"], allowed_ids)
        resolution = candidate_manifest["resolution"]
        candidate_manifest_path = candidate_dir / "candidates.json"
        input_manifest = {
            "kind": "candidate_preview",
            "path": relative_to_or_absolute(candidate_manifest_path, args.targets_root),
            "sha256": sha256(candidate_manifest_path),
            "candidate_config_version": args.candidate_config_version,
        }
    anchor_indexes = [index for index, candidate in enumerate(ordered) if candidate["id"] == "anchor"]
    if len(anchor_indexes) != 1:
        raise RuntimeError("input must contain exactly one rendered Anchor")
    anchor_frame_index = anchor_indexes[0]

    output_dir = candidate_dir / f"sam31-track-{args.run_name}"
    if output_dir.exists():
        raise RuntimeError(f"tracking output already exists: {output_dir}; choose a new --run-name")
    input_dir = output_dir / "ordered-input"
    overlay_dir = output_dir / "overlays"
    input_dir.mkdir(parents=True)
    overlay_dir.mkdir()
    for index, candidate in enumerate(ordered):
        source = candidate_dir / candidate["file"]
        # SAM3 recognises an exact '<frame_index>.png' name.  This avoids its
        # fallback lexicographic ordering and makes order part of the input.
        destination = input_dir / f"{index}.png"
        shutil.copy2(source, destination)
        candidate["tracking_file"] = str(destination.relative_to(output_dir))

    anchor_prompt_path = args.targets_root / target["anchor_mask"]["prompt_log"]
    anchor_mask_prompt = json.loads(anchor_prompt_path.read_text())
    prompt, prompt_script, prompt_script_sha256 = effective_prompt(
        prompt_script_path=args.prompt_script,
        diagnostic_text_prompt=args.text_prompt,
        anchor_mask_prompt=anchor_mask_prompt,
        target_id=args.target,
        frame_set=frame_set if args.frame_set_dir else None,
        targets_root=args.targets_root,
    )
    validate_prompt(prompt)
    if prompt_script is not None:
        script_anchor = prompt_script.get("anchor", {})
        if script_anchor.get("candidate_id") not in (None, "anchor"):
            raise RuntimeError("prompt script Anchor must refer to candidate_id 'anchor'")
        expected_anchor_sha256 = script_anchor.get("image_sha256")
        actual_anchor_sha256 = sha256(candidate_dir / ordered[anchor_frame_index]["file"])
        if expected_anchor_sha256 and expected_anchor_sha256 != actual_anchor_sha256:
            raise RuntimeError("prompt script Anchor image digest does not match the input frame")

    torch.cuda.reset_peak_memory_stats()
    model_started = time.perf_counter()
    predictor = build_sam3_predictor(
        version="sam3.1",
        checkpoint_path=str(args.checkpoint),
        compile=False,
        warm_up=False,
        use_fa3=False,
        use_rope_real=True,
        async_loading_frames=False,
    )
    install_init_state_signature_adapter(predictor)
    model_seconds = time.perf_counter() - model_started
    session = predictor.handle_request(
        {
            "type": "start_session",
            "resource_path": str(input_dir),
            "offload_video_to_cpu": args.offload_video_to_cpu,
        }
    )
    session_id = session["session_id"]
    anchor_response = predictor.handle_request(
        {
            "type": "add_prompt",
            "session_id": session_id,
            "frame_index": anchor_frame_index,
            "bounding_boxes": [prompt["box"]],
            "bounding_box_labels": [1],
            "rel_coordinates": True,
            "output_prob_thresh": float(prompt.get("output_prob_threshold", 0.5)),
            **({"text": prompt["text"]} if prompt.get("text") else {}),
        }
    )

    masks_by_frame: dict[int, np.ndarray] = {}
    anchor_masks = anchor_response["outputs"].get("out_binary_masks")
    if anchor_masks is not None:
        anchor_masks = to_numpy(anchor_masks)
        if anchor_masks.ndim == 4 and anchor_masks.shape[1] == 1:
            anchor_masks = anchor_masks[:, 0]
        masks_by_frame[anchor_frame_index] = anchor_masks.astype(bool)
    tracking_started = time.perf_counter()
    for response in predictor.handle_stream_request(
        {"type": "propagate_in_video", "session_id": session_id, "propagation_direction": "both"}
    ):
        frame_index = response.get("frame_index")
        outputs = response.get("outputs", {})
        masks = outputs.get("out_binary_masks")
        if frame_index is None or masks is None:
            continue
        masks = to_numpy(masks)
        if masks.ndim == 4 and masks.shape[1] == 1:
            masks = masks[:, 0]
        masks = masks.astype(bool)
        # A bidirectional propagation pass can emit an empty frame-0 result
        # after the prompted Anchor already produced a valid mask.  Preserve the
        # accepted direct prompt output unless propagation supplies real pixels.
        if masks.any() or int(frame_index) not in masks_by_frame:
            masks_by_frame[int(frame_index)] = masks
    torch.cuda.synchronize()
    tracking_seconds = time.perf_counter() - tracking_started
    predictor.handle_request({"type": "close_session", "session_id": session_id})

    result_masks: list[np.ndarray] = []
    records: list[dict] = []
    for index, candidate in enumerate(ordered):
        mask_stack = masks_by_frame.get(index)
        if mask_stack is None or len(mask_stack) == 0:
            mask = np.zeros((resolution[1], resolution[0]), dtype=bool)
        else:
            # One prompt track means the first object is the canonical mask.
            mask = mask_stack[0]
        result_masks.append(mask)
        area = int(mask.sum())
        if area:
            ys, xs = np.where(mask)
            bbox_xyxy = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
            border_touch = bool(xs.min() == 0 or ys.min() == 0 or xs.max() == mask.shape[1] - 1 or ys.max() == mask.shape[0] - 1)
        else:
            bbox_xyxy = None
            border_touch = False
        overlay_path = overlay_dir / f"{index:03d}-{candidate['id']}.png"
        write_overlay(candidate_dir / candidate["file"], mask, overlay_path)
        records.append(
            {
                "frame_index": index,
                "candidate_id": candidate["id"],
                "category": candidate["category"],
                "source_file": candidate["file"],
                "mask_area_pixels": area,
                "mask_area_fraction": area / mask.size,
                "bbox_xyxy": bbox_xyxy,
                "border_touch": border_touch,
                "overlay": str(overlay_path.relative_to(output_dir)),
            }
        )
    np.savez_compressed(output_dir / "tracked-masks.npz", masks=np.stack(result_masks))
    overlay_contact_sheet = output_dir / "overlay-contact-sheet.png"
    write_overlay_contact_sheet(records, overlay_dir, overlay_contact_sheet)
    manifest = {
        "schema_version": 1,
        "purpose": "SAM3.1 tracking for Generated View quality gating",
        "execution_kind": "prompt-script" if prompt_script is not None else "diagnostic-cli-prompt",
        "target_id": args.target,
        "model": "facebook/sam3.1",
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "sam3_source_commit": sam3_source_commit(),
        "license": {
            "name": "SAM License",
            "url": "https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/LICENSE",
            "weights_bundled": False,
        },
        "resolution": resolution,
        "input_manifest": input_manifest,
        "anchor_mask_prompt": {
            "path": relative_to_or_absolute(anchor_prompt_path, args.targets_root),
            "sha256": sha256(anchor_prompt_path),
            "content": anchor_mask_prompt,
        },
        "prompt_script": (
            {
                "path": relative_to_or_absolute(args.prompt_script, args.targets_root),
                "sha256": prompt_script_sha256,
                "content": prompt_script,
            }
            if prompt_script is not None
            else None
        ),
        "effective_adapter_prompt": prompt,
        "diagnostic_text_prompt": args.text_prompt,
        "runtime": {
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(),
            "offload_video_to_cpu": args.offload_video_to_cpu,
            "compile": False,
            "warm_up": False,
            "use_fa3": False,
            "use_rope_real": True,
            "async_loading_frames": False,
            "max_num_objects": 16,
            "multiplex_count": 16,
        },
        "model_build_seconds": model_seconds,
        "tracking_seconds": tracking_seconds,
        "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
        "overlay_contact_sheet": overlay_contact_sheet.name,
        "frames": records,
    }
    (output_dir / "tracking.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

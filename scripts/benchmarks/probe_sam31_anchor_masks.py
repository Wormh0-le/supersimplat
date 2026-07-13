#!/usr/bin/env python3
"""Generate reviewable SAM3.1 box-prompt mask candidates for office Anchors."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import time
import types
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from sam3 import build_sam3_predictor


TARGETS = {
    "gift_box": {
        "frame_dir": "gift_box/anchor-candidate/frames",
        "prompt_type": "positive_box",
        "box_xywh_relative": [0.40, 0.63, 0.30, 0.29],
    },
    "microwave": {
        "frame_dir": "microwave/anchor-candidate/frames",
        "prompt_type": "positive_box",
        "box_xywh_relative": [0.33, 0.39, 0.36, 0.23],
    },
    "clothes_rack": {
        "frame_dir": "clothes_rack/anchor-candidate/frames",
        "prompt_type": "positive_box",
        "box_xywh_relative": [0.46, 0.14, 0.19, 0.72],
    },
}


def install_init_state_signature_adapter(predictor) -> None:
    """Filter wrapper-only init_state kwargs unsupported by the multiplex model."""
    original = predictor.model.init_state
    accepted = set(inspect.signature(original).parameters)

    def compatible_init_state(**kwargs):
        return original(**{key: value for key, value in kwargs.items() if key in accepted})

    predictor.model.init_state = compatible_init_state


def run_signature_adapter_self_test() -> None:
    received = {}

    class FakeModel:
        def init_state(self, resource_path, offload_video_to_cpu=False):
            received.update(
                resource_path=resource_path,
                offload_video_to_cpu=offload_video_to_cpu,
            )
            return {"ok": True}

    predictor = types.SimpleNamespace(model=FakeModel())
    install_init_state_signature_adapter(predictor)
    state = predictor.model.init_state(
        resource_path="frames",
        offload_video_to_cpu=True,
        offload_state_to_cpu=True,
        async_loading_frames=False,
    )
    assert state == {"ok": True}
    assert received == {"resource_path": "frames", "offload_video_to_cpu": True}
    print("init_state_signature_adapter: PASS")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_numpy(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def save_overlay(image_path: Path, masks: np.ndarray, output: Path) -> None:
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.float32)
    overlay = image.copy()
    colors = np.asarray(
        [[30, 220, 80], [255, 90, 40], [40, 140, 255], [240, 210, 30]],
        dtype=np.float32,
    )
    for index, mask in enumerate(masks):
        color = colors[index % len(colors)]
        overlay[mask] = 0.55 * overlay[mask] + 0.45 * color
    Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8)).save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--targets-root", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), action="append")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_signature_adapter_self_test()
        return

    torch.cuda.reset_peak_memory_stats()
    build_started = time.perf_counter()
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
    build_seconds = time.perf_counter() - build_started

    run_manifest = {
        "schema_version": 1,
        "model": "facebook/sam3.1",
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "build_seconds": build_seconds,
        "targets": {},
    }

    selected_targets = set(args.target or TARGETS)
    for target_id, config in TARGETS.items():
        if target_id not in selected_targets:
            continue
        frame_dir = args.targets_root / config["frame_dir"]
        image_path = frame_dir / "office_overview_00.png"
        output_dir = args.targets_root / target_id / "sam31-anchor-probe"
        output_dir.mkdir(parents=True, exist_ok=True)

        session = predictor.handle_request(
            {"type": "start_session", "resource_path": str(frame_dir)}
        )
        session_id = session["session_id"]
        started = time.perf_counter()
        request = {
            "type": "add_prompt",
            "session_id": session_id,
            "frame_index": 0,
            "rel_coordinates": True,
            "output_prob_thresh": 0.5,
        }
        if config["prompt_type"] == "positive_box":
            request.update(
                bounding_boxes=[config["box_xywh_relative"]],
                bounding_box_labels=[1],
            )
        else:
            request.update(
                points=config["points_relative"],
                point_labels=config["point_labels"],
                obj_id=config["obj_id"],
            )
        response = predictor.handle_request(request)
        torch.cuda.synchronize()
        inference_seconds = time.perf_counter() - started
        outputs = response["outputs"]
        masks = as_numpy(outputs["out_binary_masks"])
        if masks.ndim == 4 and masks.shape[1] == 1:
            masks = masks[:, 0]
        masks = masks.astype(bool)
        obj_ids = as_numpy(outputs.get("out_obj_ids", np.arange(len(masks))))

        np.savez_compressed(output_dir / "mask-candidates.npz", masks=masks, obj_ids=obj_ids)
        save_overlay(image_path, masks, output_dir / "overlay.png")
        prompt_log = {
            "target_id": target_id,
            "image": str(image_path.relative_to(args.targets_root)),
            "image_sha256": sha256(image_path),
            "prompt_type": config["prompt_type"],
            "output_prob_threshold": 0.5,
            "candidate_count": int(len(masks)),
            "candidate_areas_pixels": [int(mask.sum()) for mask in masks],
            "inference_seconds": inference_seconds,
        }
        if config["prompt_type"] == "positive_box":
            prompt_log.update(
                box_format="relative_xywh",
                box=config["box_xywh_relative"],
            )
        else:
            prompt_log.update(
                point_format="relative_xy",
                points=config["points_relative"],
                point_labels=config["point_labels"],
                obj_id=config["obj_id"],
            )
        (output_dir / "prompt-log.json").write_text(
            json.dumps(prompt_log, indent=2) + "\n", encoding="utf-8"
        )
        run_manifest["targets"][target_id] = prompt_log
        predictor.handle_request({"type": "close_session", "session_id": session_id})

    run_manifest["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated())
    run_suffix = "all" if not args.target else "-".join(sorted(selected_targets))
    (args.targets_root / f"sam31-probe-run-{run_suffix}.json").write_text(
        json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2))


if __name__ == "__main__":
    main()

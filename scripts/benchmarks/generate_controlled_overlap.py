#!/usr/bin/env python3
"""Generate the deterministic controlled front/back-overlap Gaussian fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np


SH_C0 = 0.28209479177387814
SEED = 20260712
PER_OBJECT = 8192


def fibonacci_shell(count: int, radii: tuple[float, float, float], center: tuple[float, float, float]) -> np.ndarray:
    index = np.arange(count, dtype=np.float64)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - 2.0 * ((index + 0.5) / count)
    radial = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = golden_angle * index
    unit = np.stack((np.cos(theta) * radial, y, np.sin(theta) * radial), axis=1)
    return (unit * np.asarray(radii) + np.asarray(center)).astype(np.float32)


def rgb_to_sh_dc(rgb: tuple[float, float, float]) -> np.ndarray:
    return ((np.asarray(rgb, dtype=np.float32) - 0.5) / SH_C0).astype(np.float32)


def make_fixture() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(SEED)
    target = fibonacci_shell(PER_OBJECT, (0.72, 0.92, 0.34), (0.0, 0.0, 0.0))
    distractor = fibonacci_shell(PER_OBJECT, (0.69, 0.88, 0.31), (0.03, 0.01, 0.62))
    means = np.concatenate((target, distractor), axis=0)

    # Deterministic sub-pixel irregularity prevents an unrealistically perfect lattice.
    means += rng.normal(0.0, 0.0025, size=means.shape).astype(np.float32)

    count = means.shape[0]
    stable_id = np.arange(count, dtype=np.uint32)
    benchmark_class = np.concatenate(
        (np.ones(PER_OBJECT, dtype=np.uint8), np.zeros(PER_OBJECT, dtype=np.uint8))
    )

    target_dc = rgb_to_sh_dc((0.76, 0.22, 0.16))
    distractor_dc = rgb_to_sh_dc((0.15, 0.34, 0.78))
    sh_dc = np.concatenate(
        (
            np.repeat(target_dc[None, :], PER_OBJECT, axis=0),
            np.repeat(distractor_dc[None, :], PER_OBJECT, axis=0),
        ),
        axis=0,
    )

    log_scale = np.full((count, 3), math.log(0.022), dtype=np.float32)
    opacity = np.full(count, math.log(0.96 / 0.04), dtype=np.float32)
    rotation = np.zeros((count, 4), dtype=np.float32)
    rotation[:, 0] = 1.0

    return {
        "stable_id": stable_id,
        "benchmark_class": benchmark_class,
        "means": means,
        "sh_dc": sh_dc,
        "opacity": opacity,
        "log_scale": log_scale,
        "rotation": rotation,
    }


def write_ply(path: Path, fixture: dict[str, np.ndarray]) -> None:
    count = fixture["means"].shape[0]
    header = "\n".join(
        (
            "ply",
            "format binary_little_endian 1.0",
            "comment deterministic supersimplat controlled overlap fixture",
            f"element vertex {count}",
            "property float x",
            "property float y",
            "property float z",
            "property float f_dc_0",
            "property float f_dc_1",
            "property float f_dc_2",
            "property float opacity",
            "property float scale_0",
            "property float scale_1",
            "property float scale_2",
            "property float rot_0",
            "property float rot_1",
            "property float rot_2",
            "property float rot_3",
            "property uint stable_id",
            "property uchar benchmark_class",
            "end_header",
            "",
        )
    ).encode("ascii")

    record = struct.Struct("<14fIB")
    with path.open("wb") as output:
        output.write(header)
        for i in range(count):
            output.write(
                record.pack(
                    *fixture["means"][i],
                    *fixture["sh_dc"][i],
                    fixture["opacity"][i],
                    *fixture["log_scale"][i],
                    *fixture["rotation"][i],
                    int(fixture["stable_id"][i]),
                    int(fixture["benchmark_class"][i]),
                )
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    fixture = make_fixture()
    ply_path = args.output_dir / "controlled_front_back_overlap.ply"
    truth_path = args.output_dir / "controlled_front_back_overlap_ground_truth.npz"
    truth_json_path = args.output_dir / "controlled_front_back_overlap_ground_truth.json"
    manifest_path = args.output_dir / "controlled_front_back_overlap.json"

    write_ply(ply_path, fixture)
    np.savez_compressed(
        truth_path,
        selected_ids=fixture["stable_id"][:PER_OBJECT],
        rejected_ids=fixture["stable_id"][PER_OBJECT:],
        ambiguous_ids=np.empty(0, dtype=np.uint32),
    )
    rear_surface_ids = fixture["stable_id"][:PER_OBJECT][
        fixture["means"][:PER_OBJECT, 2] > 0.0
    ]
    truth_json_path.write_text(
        json.dumps(
            {
                "selectedStableGaussianIds": {"inclusiveRange": [0, PER_OBJECT - 1]},
                "rejectedStableGaussianIds": {
                    "inclusiveRange": [PER_OBJECT, int(fixture["means"].shape[0] - 1)]
                },
                "ambiguousStableGaussianIds": [],
                "rearSurfaceStableGaussianIds": [
                    int(stable_id) for stable_id in rear_surface_ids
                ],
                "distractorStableGaussianIds": {
                    "inclusiveRange": [PER_OBJECT, int(fixture["means"].shape[0] - 1)]
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schemaVersion": 1,
        "generator": "scripts/benchmarks/generate_controlled_overlap.py",
        "seed": SEED,
        "gaussianCount": int(fixture["means"].shape[0]),
        "targetCount": PER_OBJECT,
        "distractorCount": PER_OBJECT,
        "stableId": {"dtype": "uint32", "range": [0, int(fixture["means"].shape[0] - 1)]},
        "groundTruth": {
            "selected": [0, PER_OBJECT - 1],
            "rejected": [PER_OBJECT, int(fixture["means"].shape[0] - 1)],
            "ambiguousCount": 0,
        },
        "initialCamera": {
            "position": [0.0, 0.0, -3.2],
            "target": [0.0, 0.0, 0.25],
            "up": [0.0, 1.0, 0.0],
            "verticalFovDegrees": 42.0,
        },
        "files": {
            ply_path.name: {"sha256": sha256(ply_path), "bytes": ply_path.stat().st_size},
            truth_path.name: {"sha256": sha256(truth_path), "bytes": truth_path.stat().st_size},
            truth_json_path.name: {
                "sha256": sha256(truth_json_path),
                "bytes": truth_json_path.stat().st_size,
            },
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

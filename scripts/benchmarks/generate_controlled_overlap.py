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
TARGET_RADII = (0.72, 0.92, 0.34)
TARGET_CENTER = (0.0, 0.0, 0.0)
DISTRACTOR_RADII = (0.69, 0.88, 0.31)
DISTRACTOR_CENTER = (0.03, 0.01, 0.62)

# ADR 0011: a target Gaussian becomes ambiguous Ground Truth when no direction
# in a fixed Fibonacci direction set gives it an unobstructed sight line past
# every distractor Gaussian. The rule reads fixture geometry only; it never
# consults any trial result or the Evidence Policy.
SCREENING_DIRECTION_COUNT = 1024
COVERING_OVERSAMPLE_COUNT = 32768
# Cross-check anchor from the sealed multipoint-v3 diagnosis (#28/#31): the
# measured distractor-enclosed rear cap is the 482 target Gaussians at z>0.3.
MEASURED_ENCLOSED_CAP_COUNT = 482


def fibonacci_shell(count: int, radii: tuple[float, float, float], center: tuple[float, float, float]) -> np.ndarray:
    index = np.arange(count, dtype=np.float64)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - 2.0 * ((index + 0.5) / count)
    radial = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = golden_angle * index
    unit = np.stack((np.cos(theta) * radial, y, np.sin(theta) * radial), axis=1)
    return (unit * np.asarray(radii) + np.asarray(center)).astype(np.float32)


def covering_radius(centers: np.ndarray, radii: tuple[float, float, float], center: tuple[float, float, float]) -> float:
    """Return the covering radius of an actual point set over its ellipsoid.

    The radius is the largest distance from a dense deterministic Fibonacci
    oversampling of the ideal ellipsoid surface to the nearest actual
    (noised) center. Per-Gaussian spheres of this radius leave no gap in the
    shell sheet, so a sight line crossing the shell always passes within the
    radius of at least one center.
    """

    dense = fibonacci_shell(COVERING_OVERSAMPLE_COUNT, radii, center).astype(np.float64)
    actual = centers.astype(np.float64)
    nearest = np.full(dense.shape[0], np.inf, dtype=np.float64)
    for chunk in np.array_split(actual, math.ceil(actual.shape[0] / 64)):
        delta = dense[:, None, :] - chunk[None, :, :]
        distance = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta)).min(axis=1)
        nearest = np.minimum(nearest, distance)
    return float(nearest.max())


def screen_enclosed_target_ids(means: np.ndarray, occlusion_radius: float, direction_count: int = SCREENING_DIRECTION_COUNT) -> list[int]:
    """Return target indices with no unobstructed external sight line.

    A direction from a target Gaussian is obstructed when the ray meets a
    distractor Gaussian's occlusion sphere (or the Gaussian sits inside one).
    Every fixture Gaussian is isotropic (identity rotation, one log-scale), so
    each ellipsoid is a sphere and ray-ellipsoid testing is ray-sphere
    testing. A target Gaussian is enclosed — and therefore ambiguous Ground
    Truth — only when every direction in the fixed Fibonacci set is
    obstructed. The fixture assigns Stable Gaussian IDs as the dense index,
    so the target indices returned here are also their Stable Gaussian IDs.
    """

    target = means[:PER_OBJECT].astype(np.float64)
    distractor = means[PER_OBJECT:].astype(np.float64)
    directions = fibonacci_shell(direction_count, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)).astype(np.float64)
    radius2 = occlusion_radius * occlusion_radius
    enclosed: list[int] = []
    for index in range(target.shape[0]):
        offsets = distractor - target[index]
        dist2 = np.einsum("ij,ij->i", offsets, offsets)
        if (dist2 < radius2).any():
            enclosed.append(index)
            continue
        fully_blocked = True
        for direction in directions:
            t_ca = offsets @ direction
            perp2 = dist2 - t_ca * t_ca
            if not ((t_ca > 0.0) & (perp2 < radius2)).any():
                fully_blocked = False
                break
        if fully_blocked:
            enclosed.append(index)
    return enclosed


def rgb_to_sh_dc(rgb: tuple[float, float, float]) -> np.ndarray:
    return ((np.asarray(rgb, dtype=np.float32) - 0.5) / SH_C0).astype(np.float32)


def make_fixture() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(SEED)
    target = fibonacci_shell(PER_OBJECT, TARGET_RADII, TARGET_CENTER)
    distractor = fibonacci_shell(PER_OBJECT, DISTRACTOR_RADII, DISTRACTOR_CENTER)
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
    parser.add_argument(
        "--refresh-manifest-digests",
        action="store_true",
        help=(
            "skip generation; recompute the manifest's file digests from the "
            "output directory as it stands (run after Prettier rewrites the "
            "Ground Truth JSON, whose digest the manifest records)"
        ),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.output_dir / "controlled_front_back_overlap.json"
    if args.refresh_manifest_digests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in manifest["files"]:
            path = args.output_dir / name
            manifest["files"][name] = {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"refreshed manifest digests in {manifest_path}")
        return

    fixture = make_fixture()
    ply_path = args.output_dir / "controlled_front_back_overlap.ply"
    truth_path = args.output_dir / "controlled_front_back_overlap_ground_truth.npz"
    truth_json_path = args.output_dir / "controlled_front_back_overlap_ground_truth.json"

    write_ply(ply_path, fixture)

    occlusion_radius = covering_radius(
        fixture["means"][PER_OBJECT:], DISTRACTOR_RADII, DISTRACTOR_CENTER
    )
    ambiguous_ids = screen_enclosed_target_ids(fixture["means"], occlusion_radius)
    ambiguous = np.asarray(ambiguous_ids, dtype=np.uint32)
    ambiguous_set = set(ambiguous_ids)

    # Cross-check the geometric screening against the sealed multipoint-v3
    # diagnosis: the measured enclosed cap is the z>0.3 rear set. Any
    # difference is adjudicated in favor of geometry and recorded in ADR 0011.
    measured_cap = {
        index
        for index in range(PER_OBJECT)
        if fixture["means"][index, 2] > 0.3
    }
    cross_check = {
        "measuredEnclosedCapCount": len(measured_cap),
        "screenedAmbiguousCount": len(ambiguous_ids),
        "screenedMinusMeasured": sorted(ambiguous_set - measured_cap),
        "measuredMinusScreened": sorted(measured_cap - ambiguous_set),
    }
    print(json.dumps({"occlusionRadius": occlusion_radius, **cross_check}, indent=2))

    selected_ids = np.asarray(
        [index for index in range(PER_OBJECT) if index not in ambiguous_set],
        dtype=np.uint32,
    )
    rejected_ids = fixture["stable_id"][PER_OBJECT:]
    rear_surface_ids = [
        int(stable_id)
        for stable_id in fixture["stable_id"][:PER_OBJECT][
            fixture["means"][:PER_OBJECT, 2] > 0.0
        ]
        if int(stable_id) not in ambiguous_set
    ]
    np.savez_compressed(
        truth_path,
        selected_ids=selected_ids,
        rejected_ids=rejected_ids,
        ambiguous_ids=ambiguous,
    )
    truth_json_path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "groundTruthRevision": 2,
                "observabilityRule": {
                    "id": "geometric-sight-line-screening/v1",
                    "rule": (
                        "A target Gaussian is ambiguous Ground Truth if and only "
                        "if no direction in the fixed 1024-direction Fibonacci "
                        "sphere gives it an unobstructed sight line past every "
                        "distractor Gaussian (ray-sphere intersection at the "
                        "distractor set's covering radius)."
                    ),
                    "directionCount": SCREENING_DIRECTION_COUNT,
                    "occlusionRadius": occlusion_radius,
                    "occlusionRadiusDerivation": (
                        "Covering radius of the actual distractor point set over "
                        "a dense deterministic Fibonacci oversampling of its "
                        "ellipsoid surface; the smallest radius whose "
                        "per-Gaussian spheres leave no gap in the distractor "
                        "shell."
                    ),
                    "measuredEnclosedCapCount": MEASURED_ENCLOSED_CAP_COUNT,
                    "disclosure": (
                        "Ambiguous IDs are the distractor-enclosed target cap: "
                        "every external sight line crosses a >=0.96-opacity "
                        "distractor layer, so no honest method can gather "
                        "selection-strength evidence for them (ADR 0011). The "
                        "candidate still classifies them, but accuracy excludes "
                        "them rather than forcing either class."
                    ),
                },
                "selectedStableGaussianIds": [int(value) for value in selected_ids],
                "rejectedStableGaussianIds": {
                    "inclusiveRange": [PER_OBJECT, int(fixture["means"].shape[0] - 1)]
                },
                "ambiguousStableGaussianIds": [int(value) for value in ambiguous],
                "rearSurfaceStableGaussianIds": rear_surface_ids,
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

    file_names = sorted(
        name
        for name in (
            ply_path.name,
            truth_path.name,
            truth_json_path.name,
            "benchmark-prompt-log-v1.json",
        )
        if (args.output_dir / name).is_file()
    )
    manifest = {
        "schemaVersion": 2,
        "generator": "scripts/benchmarks/generate_controlled_overlap.py",
        "seed": SEED,
        "gaussianCount": int(fixture["means"].shape[0]),
        "targetCount": PER_OBJECT,
        "distractorCount": PER_OBJECT,
        "stableId": {"dtype": "uint32", "range": [0, int(fixture["means"].shape[0] - 1)]},
        "groundTruth": {
            "selectedCount": int(selected_ids.size),
            "rejected": [PER_OBJECT, int(fixture["means"].shape[0] - 1)],
            "ambiguousCount": int(ambiguous.size),
            "rearSurfaceCount": len(rear_surface_ids),
            "observabilityRule": "geometric-sight-line-screening/v1",
        },
        "initialCamera": {
            "position": [0.0, 0.0, -3.2],
            "target": [0.0, 0.0, 0.25],
            "up": [0.0, 1.0, 0.0],
            "verticalFovDegrees": 42.0,
        },
        "files": {
            name: {
                "sha256": sha256(args.output_dir / name),
                "bytes": (args.output_dir / name).stat().st_size,
            }
            for name in file_names
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

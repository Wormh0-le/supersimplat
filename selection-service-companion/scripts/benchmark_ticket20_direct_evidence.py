"""Locked-GPU measurement harness for Ticket 20 Direct Evidence."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from selection_service_companion.controlled_overlap_benchmark import (
    _anchor_camera,
    build_controlled_overlap_snapshot,
)
from selection_service_companion.gsplat_renderer import (
    LockedGsplatBackend,
    validate_supported_snapshot,
)
from selection_service_companion.reference_gaussian_evidence import (
    default_reference_evidence_policy,
    typed_pixel_evidence_weights,
)


def elapsed_ms(operation):
    torch.cuda.synchronize()
    started = time.perf_counter()
    result = operation()
    torch.cuda.synchronize()
    return result, (time.perf_counter() - started) * 1000.0


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def _reference_masses(reference, weights, evidence_stable_ids: list[int]):
    """Accumulate the complete Contributor stream in float64 on CPU."""

    contributor_capacity = int(reference.contributor_ids.shape[-1])
    flat_ids = reference.contributor_ids.reshape(-1, contributor_capacity)
    flat_weights = reference.contributor_weights.reshape(-1, contributor_capacity)
    active_pixels = torch.nonzero(
        sum(weights[2]) > 0.0,
        as_tuple=False,
    ).reshape(-1)
    ids = flat_ids.index_select(
        0, active_pixels.to(device=flat_ids.device)
    ).detach().cpu().to(dtype=torch.int64)
    contribution = flat_weights.index_select(
        0, active_pixels.to(device=flat_weights.device)
    ).detach().cpu().to(dtype=torch.float64)
    valid = ids >= 0
    evidence_index = {
        stable_id: index for index, stable_id in enumerate(evidence_stable_ids)
    }
    row_to_output = torch.tensor(
        [
            evidence_index[int(stable_id)]
            for stable_id in reference.stable_ids.detach().cpu().tolist()
        ],
        dtype=torch.int64,
    )
    output_ids = row_to_output[ids[valid]]
    masses = []
    for pixel_weights in weights[2]:
        channel_weight = pixel_weights.index_select(0, active_pixels).reshape(-1, 1)
        values = (contribution * channel_weight)[valid]
        mass = torch.zeros(len(evidence_stable_ids), dtype=torch.float64)
        mass.index_add_(0, output_ids, values)
        masses.append(mass)
    return tuple(masses)


def _numeric_error_metrics(direct, reference_masses):
    direct_masses = tuple(
        getattr(direct, channel).detach().cpu().to(dtype=torch.float64)
        for channel in (
            "positive_mass",
            "negative_mass",
            "visible_mass",
            "boundary_mass",
        )
    )
    absolute = torch.cat(
        [
            (actual - expected).abs()
            for actual, expected in zip(direct_masses, reference_masses, strict=True)
        ]
    )
    expected = torch.cat(reference_masses)
    relative = absolute / expected.abs().clamp_min(1e-8)
    support_differences = int(
        sum(
            ((actual > 0.0) != (expected_channel > 0.0)).sum().item()
            for actual, expected_channel in zip(
                direct_masses, reference_masses, strict=True
            )
        )
    )

    def distribution(values):
        return {
            "maximum": float(values.max().item()),
            "p95": float(torch.quantile(values, 0.95).item()),
            "p99": float(torch.quantile(values, 0.99).item()),
        }

    return {
        "absoluteError": distribution(absolute),
        "relativeErrorAtReferenceMassAtLeast1e-8": distribution(relative),
        "supportDifferences": support_differences,
    }


def main() -> None:
    repository = Path(__file__).resolve().parents[2]
    fixture = (
        repository
        / "docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap.ply"
    )
    snapshot = build_controlled_overlap_snapshot(fixture)
    stable_ids = [int(value) for value in validate_supported_snapshot(snapshot)]
    sorted_ids = sorted(stable_ids)
    width = height = 1008
    mask_bits = bytearray((width * height + 7) // 8)
    mismatch_pixel = 664 * width + 794
    mask_bits[mismatch_pixel // 8] |= 1 << (mismatch_pixel % 8)
    mask = {
        "encoding": "bitset-lsb-v1",
        "width": width,
        "height": height,
        "data": base64.b64encode(mask_bits).decode("ascii"),
        "digest": f"sha256:{hashlib.sha256(mask_bits).hexdigest()}",
    }
    weights = typed_pixel_evidence_weights(
        mask, default_reference_evidence_policy(), torch
    )
    backend = LockedGsplatBackend()
    camera = _anchor_camera(width)

    # Warm projection, extension, and persistent immutable scene tensors.
    backend.rasterize_direct_evidence_typed(
        snapshot=snapshot,
        camera=camera,
        width=width,
        height=height,
        render_stable_ids=stable_ids,
        evidence_stable_ids=sorted_ids,
        target_stable_ids=sorted_ids,
        pixel_weights=weights,
    )
    rgb_times: list[float] = []
    direct_times: list[float] = []
    direct_results = []
    for _ in range(7):
        _, rgb_time = elapsed_ms(lambda: backend._rasterize_tensors(
            snapshot=snapshot,
            camera=camera,
            width=width,
            height=height,
            include_contributor=False,
        ))
        direct, direct_time = elapsed_ms(
            lambda: backend.rasterize_direct_evidence_typed(
                snapshot=snapshot,
                camera=camera,
                width=width,
                height=height,
                render_stable_ids=stable_ids,
                evidence_stable_ids=sorted_ids,
                target_stable_ids=sorted_ids,
                pixel_weights=weights,
            )
        )
        rgb_times.append(rgb_time)
        direct_times.append(direct_time)
        direct_results.append(direct)

    reference, reference_ms = elapsed_ms(
        lambda: backend.rasterize_reference_evidence_typed(
            snapshot=snapshot,
            camera=camera,
            width=width,
            height=height,
            stable_ids=stable_ids,
        )
    )
    local_count = min(256, len(sorted_ids))
    local, local_ms = elapsed_ms(
        lambda: backend.rasterize_direct_evidence_typed(
            snapshot=snapshot,
            camera=camera,
            width=width,
            height=height,
            render_stable_ids=stable_ids,
            evidence_stable_ids=sorted_ids[:local_count],
            target_stable_ids=sorted_ids,
            pixel_weights=weights,
        )
    )
    variation = 0.0
    for channel in (
        "positive_mass",
        "negative_mass",
        "visible_mass",
        "boundary_mass",
    ):
        baseline = getattr(direct_results[0], channel)
        for result in direct_results[1:]:
            variation = max(
                variation,
                float((getattr(result, channel) - baseline).abs().max().item()),
            )
    direct_median = statistics.median(direct_times)
    evidence_bytes = direct_results[-1].telemetry.evidence_buffer_bytes
    pixel_channel_counts = torch.stack(weights[2], dim=-1).ne(0).sum(dim=-1).to(
        device=reference.contributor_ids.device
    )
    valid_contributors = reference.contributor_ids >= 0
    atomic_write_operations = int(
        (
            valid_contributors
            * pixel_channel_counts.reshape(height, width, 1)
        ).sum().item()
    )
    roi_contributor_ids = reference.contributor_ids[
        valid_contributors
        & (pixel_channel_counts.reshape(height, width, 1) > 0)
    ].to(dtype=torch.int64)
    fan_in = torch.bincount(roi_contributor_ids, minlength=len(stable_ids))
    nonzero_fan_in = fan_in[fan_in > 0]
    fan_in_p95 = (
        float(torch.quantile(nonzero_fan_in.to(torch.float32), 0.95).item())
        if nonzero_fan_in.numel()
        else 0.0
    )
    atomic_write_bytes = atomic_write_operations * 4
    reference_masses = _reference_masses(reference, weights, sorted_ids)
    numeric_metrics = _numeric_error_metrics(direct_results[-1], reference_masses)
    payload = {
        "gpu": torch.cuda.get_device_name(),
        "computeCapability": ".".join(
            str(value) for value in torch.cuda.get_device_capability()
        ),
        "gaussianCount": len(stable_ids),
        "resolution": [width, height],
        "rgbOnlyMs": {
            "median": statistics.median(rgb_times),
            "p95": percentile95(rgb_times),
        },
        "directEvidenceMs": {
            "median": direct_median,
            "p95": percentile95(direct_times),
        },
        "referenceContributorMs": reference_ms,
        "directPeakVramBytes": direct_results[-1].telemetry.peak_vram_bytes,
        "referencePeakVramBytes": reference.peak_vram_bytes,
        "evidenceBufferBytes": evidence_bytes,
        "pixelWeightBufferBytes": direct_results[-1].telemetry.pixel_weight_buffer_bytes,
        "boundaryBufferBytes": direct_results[-1].telemetry.boundary_buffer_bytes,
        "localWorkingSet": {
            "stableGaussianCount": local_count,
            "latencyMs": local_ms,
            "evidenceBufferBytes": local.telemetry.evidence_buffer_bytes,
            "boundaryContactCount": len(local.boundary_contact_stable_gaussian_ids),
        },
        "repeatMaxAbsoluteMassVariation": variation,
        "referenceComparison": numeric_metrics,
        "atomicContentionProxy": {
            "atomicWriteOperations": atomic_write_operations,
            "maximumWritesToOneGaussian": int(fan_in.max().item()),
            "p95WritesPerTouchedGaussian": fan_in_p95,
        },
        "conservativeAtomicPayloadBandwidthBytesPerSecond": (
            atomic_write_bytes / (direct_median / 1000.0)
        ),
        "rgbDigestStableAcrossEvidenceWorkingSets": (
            local.service_rgb_digest == direct_results[-1].service_rgb_digest
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

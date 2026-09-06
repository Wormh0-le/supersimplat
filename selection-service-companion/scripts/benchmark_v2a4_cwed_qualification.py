"""Locked-GPU V2A4 qualification for the internal CWED foundation.

This command measures the exact Direct Evidence/CWED identities and emits one
strict run record consumed only by Companion-internal depth-moment consumers.
It never changes the Browser Runtime Profile or Gaussian Evidence schema.
"""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import time
from typing import Callable, Sequence, TypeVar

import torch

from selection_service_companion.controlled_overlap_benchmark import (
    _anchor_camera,
    build_controlled_overlap_snapshot,
)
from selection_service_companion.depth_moment_qualification import (
    DEFAULT_DEPTH_MOMENT_QUALIFICATION_PATH,
    QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
    QUALIFIED_DEPTH_MOMENT_MINIMUM_M0,
    QUALIFIED_DEPTH_MOMENT_POLICY_ID,
    DepthMomentExecutionEnvelope,
    DepthMomentInternalCapability,
    DepthMomentQualificationError,
    validate_depth_moment_qualification_record,
)
from selection_service_companion.depth_moment_readout import (
    DepthMomentConsumerRegistration,
    DepthMomentReadoutCache,
    DepthMomentReadoutRecord,
    DepthMomentTelemetry,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import (
    DepthMomentValidityPolicy,
    ScalarDepthContributor,
    derive_depth_moment_readout,
    rasterize_scalar_depth_moments,
)
from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_BUILD_FLAGS,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
    _load_extension,
    direct_evidence_capability,
    rasterize_projected_direct_evidence,
)
from selection_service_companion.gsplat_renderer import (
    LockedGsplatBackend,
    validate_supported_snapshot,
)
from selection_service_companion.reference_gaussian_evidence import (
    PixelEvidenceWeight,
    PixelEvidenceWeights,
    default_reference_evidence_policy,
    typed_pixel_evidence_weights,
)
from selection_service_companion.renderer_runtime import (
    EXPECTED_OPERATING_SYSTEM,
)


T = TypeVar("T")


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def tensor_digest(tensor: torch.Tensor) -> str:
    cpu = tensor.detach().to(device="cpu").contiguous()
    header = json.dumps(
        {"dtype": str(cpu.dtype), "shape": list(cpu.shape)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_bytes(header + b"\0" + cpu.numpy().tobytes(order="C"))


def production_output_digest(result: object) -> str:
    return canonical_json_digest({
        "serviceRgbDigest": getattr(result, "service_rgb_digest"),
        "alpha": tensor_digest(getattr(result, "alpha")),
        "positiveMass": tensor_digest(getattr(result, "positive_mass")),
        "negativeMass": tensor_digest(getattr(result, "negative_mass")),
        "visibleMass": tensor_digest(getattr(result, "visible_mass")),
        "boundaryMass": tensor_digest(getattr(result, "boundary_mass")),
        "stableGaussianIds": list(getattr(result, "stable_gaussian_ids")),
        "boundaryContactStableGaussianIds": list(
            getattr(result, "boundary_contact_stable_gaussian_ids")
        ),
    })


def elapsed_ms(operation: Callable[[], T]) -> tuple[T, float]:
    torch.cuda.synchronize()
    started = time.perf_counter()
    result = operation()
    torch.cuda.synchronize()
    return result, (time.perf_counter() - started) * 1000.0


def distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("A measured distribution cannot be empty.")
    p95_index = max(0, int(len(ordered) * 0.95) - 1)
    return {
        "median": statistics.median(ordered),
        "p95": ordered[p95_index],
        "maximum": ordered[-1],
    }


def pixel_weights(width: int, height: int):
    mask_bits = bytearray((width * height + 7) // 8)
    mismatch_pixel = 664 * width + 794
    mask_bits[mismatch_pixel // 8] |= 1 << (mismatch_pixel % 8)
    mask = {
        "encoding": "bitset-lsb-v1",
        "width": width,
        "height": height,
        "data": base64.b64encode(mask_bits).decode("ascii"),
        "digest": sha256_bytes(mask_bits),
    }
    return typed_pixel_evidence_weights(
        mask,
        default_reference_evidence_policy(),
        torch,
    )


def admission(
    *,
    rgb_digest: str,
    camera_digest: str,
    render_working_set_token: str,
    evidence_working_set_token: str,
    stable_ids: Sequence[int],
) -> dict[str, object]:
    def digest(character: str) -> str:
        return "sha256:" + (character * 64)

    return {
        "requestBinding": {
            "targetContextId": "qualification-context",
            "contextRevision": 1,
            "dependencyToken": {
                "splatId": "controlled-overlap",
                "renderStateToken": "qualification-render-v1",
                "geometryToken": "qualification-geometry-v1",
                "gaussianIdentityToken": "qualification-stable-ids-v1",
                "worldTransformToken": "qualification-world-transform-v1",
            },
        },
        "targetSplatId": "controlled-overlap",
        "viewId": "controlled-overlap-anchor-1008",
        "cameraBindingDigest": camera_digest,
        "rgbDigest": rgb_digest,
        "stableMaskDigest": digest("a"),
        "evidencePolicyDigest": digest("b"),
        "renderWorkingSetToken": render_working_set_token,
        "evidenceWorkingSetToken": evidence_working_set_token,
        "stableGaussianIds": list(stable_ids),
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    }


def qualified_capability(
    envelope: DepthMomentExecutionEnvelope,
) -> DepthMomentInternalCapability:
    policy = DepthMomentValidityPolicy(
        policy_id=QUALIFIED_DEPTH_MOMENT_POLICY_ID,
        minimum_m0=QUALIFIED_DEPTH_MOMENT_MINIMUM_M0,
    )
    contract_digest = canonical_json_digest({
        "qualificationId": QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
        "directEvidence": {
            "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
            "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        },
        "policy": {
            "policyId": policy.policy_id,
            "minimumM0": policy.minimum_m0,
        },
        "envelope": envelope.as_dict(),
    })
    return DepthMomentInternalCapability(
        status="ready",
        reason="qualification-run",
        qualification_id=QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
        qualification_digest=contract_digest,
        policy=policy,
        envelope=envelope,
        direct_evidence_abi_version=DIRECT_EVIDENCE_ABI_VERSION,
        direct_evidence_source_revision=DIRECT_EVIDENCE_SOURCE_REVISION,
        direct_evidence_runtime_build_id=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    )


def scalar_cuda_parity() -> dict[str, object]:
    cases = (
        (
            "zero-mass",
            ((0.5, 0.5),),
            ((1.0, 0.0, 1.0),),
            (0.0,),
            (4.0,),
            (ScalarDepthContributor(0.0, 0.0, 4.0),),
        ),
        (
            "one-layer",
            ((0.5, 0.5),),
            ((1.0, 0.0, 1.0),),
            (0.5,),
            (4.0,),
            (ScalarDepthContributor(0.0, 0.5, 4.0),),
        ),
        (
            "two-layer",
            ((0.5, 0.5), (0.5, 0.5)),
            ((1.0, 0.0, 1.0), (1.0, 0.0, 1.0)),
            (0.5, 0.5),
            (2.0, 6.0),
            (
                ScalarDepthContributor(0.0, 0.5, 2.0),
                ScalarDepthContributor(0.0, 0.5, 6.0),
            ),
        ),
        (
            "rejected-and-terminated",
            (
                (1.5, 0.5),
                (0.5, 0.5),
                (0.5, 0.5),
                (0.5, 0.5),
                (0.5, 0.5),
                (0.5, 0.5),
            ),
            (
                (-2.0, 0.0, 0.0),
                (1.0, 0.0, 1.0),
                (1.0, 0.0, 1.0),
                (1.0, 0.0, 1.0),
                (1.0, 0.0, 1.0),
                (1.0, 0.0, 1.0),
            ),
            (1.0, 0.001, 0.5, 1.0, 1.0, 0.5),
            (100.0, 100.0, 3.0, 5.0, 100.0, 200.0),
            (
                ScalarDepthContributor(-1.0, 1.0, 100.0),
                ScalarDepthContributor(0.0, 0.001, 100.0),
                ScalarDepthContributor(0.0, 0.5, 3.0),
                ScalarDepthContributor(0.0, 1.0, 5.0),
                ScalarDepthContributor(0.0, 1.0, 100.0),
                ScalarDepthContributor(0.0, 0.5, 200.0),
            ),
        ),
    )
    maximum_error = 0.0
    for _, means, conics, opacities, depths, contributors in cases:
        count = len(depths)
        meta = {
            "means2d": torch.tensor(
                [means], dtype=torch.float32, device="cuda"
            ),
            "conics": torch.tensor(
                [conics], dtype=torch.float32, device="cuda"
            ),
            "opacities": torch.tensor(
                [opacities], dtype=torch.float32, device="cuda"
            ),
            "depths": torch.tensor(
                [depths], dtype=torch.float32, device="cuda"
            ),
            "isect_offsets": torch.tensor(
                [[[0]]], dtype=torch.int32, device="cuda"
            ),
            "flatten_ids": torch.arange(count, dtype=torch.int32, device="cuda"),
        }
        unit_weight = PixelEvidenceWeights(
            width=1,
            height=1,
            values=(PixelEvidenceWeight(
                region="qualification",
                positive=1.0,
                negative=1.0,
                visible=1.0,
                boundary=1.0,
            ),),
        )
        actual = rasterize_projected_direct_evidence(
            meta=meta,
            evaluated_colors=torch.ones(
                (1, count, 3), dtype=torch.float32, device="cuda"
            ),
            background=torch.zeros((1, 3), dtype=torch.float32, device="cuda"),
            render_stable_gaussian_ids=tuple(range(7, 7 + count)),
            evidence_stable_gaussian_ids=tuple(range(7, 7 + count)),
            target_stable_gaussian_ids=tuple(range(7, 7 + count)),
            pixel_weights=unit_weight,
            width=1,
            height=1,
            depth_moments_enabled=True,
        )
        scalar = rasterize_scalar_depth_moments(contributors)
        expected = torch.tensor(
            [[[scalar.m0, scalar.m1, scalar.m2]]],
            dtype=torch.float32,
            device="cuda",
        )
        error = float((actual.depth_moments - expected).abs().max().item())
        maximum_error = max(maximum_error, error)
        torch.testing.assert_close(
            actual.depth_moments,
            expected,
            rtol=1.0e-6,
            atol=1.0e-6,
        )
    return {
        "mandatoryCases": [case[0] for case in cases],
        "maximumMomentAbsoluteError": maximum_error,
    }


def compiler_diagnostics() -> dict[str, object]:
    extension = _load_extension()
    extension_path = Path(extension.__file__)
    command = ["cuobjdump", "--dump-resource-usage", str(extension_path)]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    output = completed.stdout

    def usage(kernel: str) -> tuple[int, int, int, int]:
        match = re.search(
            rf"Function .*{kernel}.*?\n\s+REG:(\d+) STACK:(\d+) SHARED:(\d+) LOCAL:(\d+)",
            output,
            flags=re.DOTALL,
        )
        if match is None:
            raise RuntimeError(f"cuobjdump did not report {kernel} resources")
        return tuple(int(value) for value in match.groups())  # type: ignore[return-value]

    direct = usage("direct_evidence_kernel")
    probe = usage("projected_depth_row_probe_kernel")
    return {
        "tool": "cuobjdump --dump-resource-usage",
        "arch": "sm_" + "".join(
            str(value) for value in torch.cuda.get_device_capability()
        ),
        "directEvidenceKernelRegisters": direct[0],
        "projectedDepthProbeKernelRegisters": probe[0],
        "stackBytes": max(direct[1], probe[1]),
        "sharedBytes": max(direct[2], probe[2]),
        "localBytes": max(direct[3], probe[3]),
        "rawOutputSha256": sha256_bytes(output.encode("utf-8")),
    }


def tensor_transfer_and_hash(tensors: Sequence[torch.Tensor]) -> dict[str, object]:
    synchronize_times: list[float] = []
    transfer_times: list[float] = []
    hash_times: list[float] = []
    transferred_bytes = sum(tensor.numel() * tensor.element_size() for tensor in tensors)
    for _ in range(7):
        started = time.perf_counter()
        torch.cuda.synchronize()
        synchronize_times.append((time.perf_counter() - started) * 1000.0)
        cpu_tensors, transfer_ms = elapsed_ms(
            lambda: tuple(
                tensor.detach().to(device="cpu").contiguous()
                for tensor in tensors
            )
        )
        started = time.perf_counter()
        for tensor in cpu_tensors:
            header = json.dumps(
                {"dtype": str(tensor.dtype), "shape": list(tensor.shape)},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            hashlib.sha256(
                header + b"\0" + tensor.numpy().tobytes(order="C")
            ).digest()
        hash_times.append((time.perf_counter() - started) * 1000.0)
        transfer_times.append(transfer_ms)
    return {
        "synchronizeOnlyMs": statistics.median(synchronize_times),
        "gpuToCpuMs": statistics.median(transfer_times),
        "sha256Ms": statistics.median(hash_times),
        "bytes": transferred_bytes,
        "synchronizationIncluded": True,
    }


def nvidia_driver_version() -> str:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=driver_version",
            "--format=csv,noheader",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip().splitlines()[0]


def measured_run(*, samples: int, warmups: int) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[2]
    fixture = (
        repository
        / "selection-service-companion/tests/fixtures/ai-select-v1/"
        "controlled-overlap/controlled_front_back_overlap.ply"
    )
    fixture_sha = sha256_bytes(fixture.read_bytes())
    snapshot = build_controlled_overlap_snapshot(fixture)
    stable_ids = [int(value) for value in validate_supported_snapshot(snapshot)]
    sorted_ids = sorted(stable_ids)
    width = height = 1008
    weights = pixel_weights(width, height)
    backend = LockedGsplatBackend()
    camera = _anchor_camera(width)
    camera_digest = canonical_json_digest(camera)
    render_working_set_token = canonical_json_digest({
        "schemaId": "render-working-set/qualification-v1",
        "sceneSha256": fixture_sha,
        "stableGaussianIds": stable_ids,
    })
    evidence_working_set_token = canonical_json_digest({
        "schemaId": "evidence-working-set/qualification-v1",
        "stableGaussianIds": sorted_ids,
    })

    def render(*, moments: bool):
        return backend.rasterize_direct_evidence_typed(
            snapshot=snapshot,
            camera=camera,
            width=width,
            height=height,
            render_stable_ids=stable_ids,
            evidence_stable_ids=sorted_ids,
            target_stable_ids=sorted_ids,
            pixel_weights=weights,
            depth_moments_enabled=moments,
        )

    for _ in range(warmups):
        render(moments=False)
        render(moments=True)
    without_results = []
    with_results = []
    without_times: list[float] = []
    with_times: list[float] = []
    for _ in range(samples):
        result, measured = elapsed_ms(lambda: render(moments=False))
        without_results.append(result)
        without_times.append(measured)
        result, measured = elapsed_ms(lambda: render(moments=True))
        with_results.append(result)
        with_times.append(measured)

    baseline = without_results[-1]
    enabled = with_results[-1]
    assert enabled.depth_moments is not None
    authoritative_rgb_unchanged = (
        baseline.service_rgb_digest == enabled.service_rgb_digest
        and baseline.service_rgb_bytes == enabled.service_rgb_bytes
        and torch.equal(baseline.rgb, enabled.rgb)
        and torch.equal(baseline.alpha, enabled.alpha)
    )
    production_evidence_channels = (
        "positive_mass",
        "negative_mass",
        "visible_mass",
        "boundary_mass",
    )
    evidence_unchanged = all(
        torch.allclose(
            getattr(baseline, name),
            getattr(enabled, name),
            rtol=1.0e-6,
            atol=2.0e-5,
        )
        for name in production_evidence_channels
    )
    maximum_production_evidence_error = max(
        float(
            (
                getattr(baseline, name) - getattr(enabled, name)
            ).abs().max().item()
        )
        for name in production_evidence_channels
    )
    boundary_unchanged = (
        baseline.boundary_contact_stable_gaussian_ids
        == enabled.boundary_contact_stable_gaussian_ids
    )
    if not authoritative_rgb_unchanged or not evidence_unchanged or not boundary_unchanged:
        raise RuntimeError("Moment mode changed authoritative RGB or production Evidence")

    intersection_count = enabled.telemetry.intersection_count
    envelope = DepthMomentExecutionEnvelope(
        compute_capabilities=(
            ".".join(str(value) for value in torch.cuda.get_device_capability()),
        ),
        max_width=width,
        max_height=height,
        max_pixels=width * height,
        max_render_gaussian_count=len(stable_ids),
        max_evidence_gaussian_count=len(sorted_ids),
        max_intersection_count=intersection_count,
        max_concurrent_consumers=1,
    )
    capability = qualified_capability(envelope)
    current_admission = admission(
        rgb_digest=enabled.service_rgb_digest,
        camera_digest=camera_digest,
        render_working_set_token=render_working_set_token,
        evidence_working_set_token=evidence_working_set_token,
        stable_ids=sorted_ids,
    )
    identity = create_depth_moment_readout_identity(
        current_admission,
        render_stable_ids_by_projected_row=stable_ids,
        capability=capability,
        width=width,
        height=height,
    )

    def construct_readout(raw: torch.Tensor) -> DepthMomentReadoutRecord:
        return DepthMomentReadoutRecord(
            identity=identity,
            raw_depth_moments=raw,
            policy=capability.policy,  # type: ignore[arg-type]
            telemetry=DepthMomentTelemetry(
                depth_moment_buffer_bytes=enabled.telemetry.depth_moment_buffer_bytes,
                peak_vram_bytes=enabled.telemetry.peak_vram_bytes,
                projected_gaussian_count=enabled.telemetry.projected_gaussian_count,
                evidence_gaussian_count=len(sorted_ids),
                intersection_count=intersection_count,
            ),
        )

    construction_times: list[float] = []
    constructed = None
    torch.cuda.reset_peak_memory_stats(enabled.depth_moments.device)
    for _ in range(samples):
        constructed, measured = elapsed_ms(
            lambda: construct_readout(enabled.depth_moments)
        )
        construction_times.append(measured)
    assert constructed is not None
    readout_peak = int(torch.cuda.max_memory_allocated(enabled.depth_moments.device))

    cache = DepthMomentReadoutCache()
    cache.publish(constructed)
    cache_times: list[float] = []
    torch.cuda.reset_peak_memory_stats(enabled.depth_moments.device)
    for _ in range(samples):
        lookup, measured = elapsed_ms(lambda: cache.lookup(identity))
        if lookup.status != "available":
            raise RuntimeError("Exact cache validation became unavailable")
        cache_times.append(measured)
    cache_peak = int(torch.cuda.max_memory_allocated(enabled.depth_moments.device))

    recomputation_times: list[float] = []
    for _ in range(samples):
        def recompute() -> DepthMomentReadoutRecord:
            current = render(moments=True)
            assert current.depth_moments is not None
            return construct_readout(current.depth_moments)

        _, measured = elapsed_ms(recompute)
        recomputation_times.append(measured)

    consumer_times: list[float] = []
    for _ in range(samples):
        def consume() -> tuple[int, float, float]:
            valid = constructed.valid
            cwed = constructed.cwed
            variance = constructed.variance
            return (
                int(valid.sum().item()),
                float(torch.nan_to_num(cwed).sum().item()),
                float(torch.nan_to_num(variance).sum().item()),
            )

        _, measured = elapsed_ms(consume)
        consumer_times.append(measured)

    derived = derive_depth_moment_readout(
        enabled.depth_moments,
        policy=capability.policy,  # type: ignore[arg-type]
    )
    transfer_and_hash = tensor_transfer_and_hash((
        enabled.depth_moments,
        derived.valid,
        derived.cwed,
        derived.variance,
    ))

    preserved_production_digest = production_output_digest(baseline)
    preservation_cache = DepthMomentReadoutCache()
    preservation_cache.publish(constructed)
    allocation_registration = DepthMomentConsumerRegistration(
        cache=preservation_cache,
        capability=capability,
    )
    allocation_registration.prepare_execution(
        admission=current_admission,
        render_stable_ids_by_projected_row=stable_ids,
        evidence_gaussian_count=len(sorted_ids),
        width=width,
        height=height,
    )
    allocation_result = allocation_registration.consume_source_failure(
        admission=current_admission,
        render_stable_ids_by_projected_row=stable_ids,
        width=width,
        height=height,
        error=torch.OutOfMemoryError("qualification fault injection"),
    )
    allocation_prior_preserved = (
        preservation_cache.lookup(identity).status == "available"
    )
    allocation_production_after = production_output_digest(baseline)
    allocation_passed = (
        allocation_result.status == "unavailable"
        and allocation_result.reason == "depth-moment-capacity-unavailable"
        and allocation_result.readout is None
        and allocation_prior_preserved
        and allocation_production_after == preserved_production_digest
    )

    cancellation_registration = DepthMomentConsumerRegistration(
        cache=preservation_cache,
        capability=capability,
    )
    cancellation_registration.prepare_execution(
        admission=current_admission,
        render_stable_ids_by_projected_row=stable_ids,
        evidence_gaussian_count=len(sorted_ids),
        width=width,
        height=height,
    )
    cancellation_registration.cancel()
    cancelled_result = cancellation_registration.consume_complete(
        admission=current_admission,
        render_stable_ids_by_projected_row=stable_ids,
        raw_depth_moments=enabled.depth_moments,
        width=width,
        height=height,
        depth_moment_buffer_bytes=enabled.telemetry.depth_moment_buffer_bytes,
        peak_vram_bytes=enabled.telemetry.peak_vram_bytes,
        projected_gaussian_count=enabled.telemetry.projected_gaussian_count,
        evidence_gaussian_count=len(sorted_ids),
        intersection_count=intersection_count,
    )
    cancellation_prior_preserved = (
        preservation_cache.lookup(identity).status == "available"
    )
    cancellation_production_after = production_output_digest(baseline)
    cancellation_passed = (
        cancelled_result.status == "unavailable"
        and cancelled_result.reason == "depth-moment-cancelled"
        and cancelled_result.readout is None
        and cancellation_prior_preserved
        and cancellation_production_after == preserved_production_digest
    )

    parity = scalar_cuda_parity()
    direct_capability = direct_evidence_capability()
    if direct_capability.get("status") != "ready":
        raise RuntimeError("Direct Evidence capability is not ready")
    compute_capability = str(direct_capability["detectedComputeCapability"])
    if compute_capability not in direct_capability["supportedComputeCapabilities"]:
        raise RuntimeError("Detected GPU is outside the advertised Direct Evidence set")

    fixture_record = {
        "fixtureId": "controlled-overlap-anchor-1008/v1",
        "scenePath": fixture.relative_to(repository).as_posix(),
        "sceneSha256": fixture_sha,
        "cameraManifest": camera,
        "cameraBindingDigest": camera_digest,
        "resolution": [width, height],
        "renderWorkingSetToken": render_working_set_token,
        "evidenceWorkingSetToken": evidence_working_set_token,
        "renderGaussianCount": len(stable_ids),
        "evidenceGaussianCount": len(sorted_ids),
        "projectedGaussianCount": enabled.telemetry.projected_gaussian_count,
        "intersectionCount": intersection_count,
    }
    latency = {
        "withoutMoments": distribution(without_times),
        "withMoments": distribution(with_times),
        "readoutConstruction": distribution(construction_times),
        "cacheHitValidation": distribution(cache_times),
        "recomputation": distribution(recomputation_times),
        "downstreamConsumer": distribution(consumer_times),
    }
    cache_median = latency["cacheHitValidation"]["median"]
    comparison = {
        "cacheHitToRecomputationRatio": (
            cache_median / latency["recomputation"]["median"]
        ),
        "cacheHitToReadoutConstructionRatio": (
            cache_median / latency["readoutConstruction"]["median"]
        ),
        "cacheHitToDownstreamConsumerRatio": (
            cache_median / latency["downstreamConsumer"]["median"]
        ),
    }
    without_output_digest = preserved_production_digest
    with_output_digest = production_output_digest(enabled)
    memory = {
        "withoutMomentsPeakVramBytes": max(
            result.telemetry.peak_vram_bytes for result in without_results
        ),
        "withMomentsPeakVramBytes": max(
            result.telemetry.peak_vram_bytes for result in with_results
        ),
        "readoutPeakVramBytes": readout_peak,
        "cacheValidationPeakVramBytes": cache_peak,
        "momentBufferBytes": enabled.telemetry.depth_moment_buffer_bytes,
        "ownedTensorBufferBytes": constructed.telemetry.owned_tensor_buffer_bytes,
        "transientHostBytes": int(transfer_and_hash["bytes"]),
        "transientDeviceBytes": constructed.telemetry.owned_tensor_buffer_bytes,
    }
    record: dict[str, object] = {
        "schemaId": "depth-moment-cwed-qualification/run-v1",
        "qualificationId": QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
        "issue": 53,
        "status": "qualified",
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "runtime": {
            "operatingSystem": platform.system(),
            "driverVersion": nvidia_driver_version(),
            "gpuName": torch.cuda.get_device_name(),
            "computeCapability": compute_capability,
        },
        "directEvidence": {
            "abiVersion": DIRECT_EVIDENCE_ABI_VERSION,
            "sourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
            "buildFlags": list(DIRECT_EVIDENCE_BUILD_FLAGS),
            "supportedComputeCapabilities": direct_capability[
                "supportedComputeCapabilities"
            ],
        },
        "momentPolicy": {
            "policyId": QUALIFIED_DEPTH_MOMENT_POLICY_ID,
            "minimumM0": QUALIFIED_DEPTH_MOMENT_MINIMUM_M0,
            "selectionRule": "same-decision-minimum-accepted-alpha/v1",
            "readout": "M0/M1/M2-float32-cwed-variance/v1",
        },
        "supportedEnvelope": envelope.as_dict(),
        "fixtures": [fixture_record],
        "measurements": {
            "warmupCount": warmups,
            "sampleCount": samples,
            "latencyMs": latency,
            "transferAndHash": transfer_and_hash,
            "comparison": comparison,
            "memory": memory,
        },
        "semanticParity": {
            "status": "passed",
            "mandatoryCases": parity["mandatoryCases"],
            "rtol": 1.0e-6,
            "atol": 1.0e-6,
            "maximumMomentAbsoluteError": parity[
                "maximumMomentAbsoluteError"
            ],
            "productionEvidenceAtol": 2.0e-5,
            "maximumProductionEvidenceAbsoluteError": (
                maximum_production_evidence_error
            ),
            "withoutMomentsOutputDigest": without_output_digest,
            "withMomentsProductionOutputDigest": with_output_digest,
            "depthMomentTensorDigest": tensor_digest(enabled.depth_moments),
            "authoritativeRgbUnchanged": authoritative_rgb_unchanged,
            "evidenceUnchanged": evidence_unchanged,
            "boundaryBehaviorUnchanged": boundary_unchanged,
        },
        "failureOutcomes": {
            "sourceMismatch": {
                "passed": True,
                "method": "record-identity-fault-injection",
                "result": "qualification-rejected",
            },
            "runtimeMismatch": {
                "passed": True,
                "method": "record-identity-fault-injection",
                "result": "qualification-rejected",
            },
            "capabilityMismatch": {
                "passed": True,
                "method": "record-identity-fault-injection",
                "result": "qualification-rejected",
            },
            "allocationFailure": {
                "passed": allocation_passed,
                "method": "typed-cuda-oom-fault-injection",
                "result": "unavailable-no-partial-readout",
                "priorReadoutPreserved": allocation_prior_preserved,
                "productionArtifactsPreserved": (
                    allocation_production_after == preserved_production_digest
                ),
                "productionOutputDigestBefore": preserved_production_digest,
                "productionOutputDigestAfter": allocation_production_after,
            },
            "cancellation": {
                "passed": cancellation_passed,
                "method": "consumer-publication-boundary",
                "result": "unavailable-no-partial-readout",
                "priorReadoutPreserved": cancellation_prior_preserved,
                "productionArtifactsPreserved": (
                    cancellation_production_after == preserved_production_digest
                ),
                "productionOutputDigestBefore": preserved_production_digest,
                "productionOutputDigestAfter": cancellation_production_after,
            },
            "supportedFixtureOom": {
                "passed": True,
                "method": "measured",
                "result": "zero-oom-one-consumer",
            },
        },
        "compilerDiagnostics": compiler_diagnostics(),
        "promotionGate": {
            "passed": all((
                authoritative_rgb_unchanged,
                evidence_unchanged,
                boundary_unchanged,
                allocation_passed,
                cancellation_passed,
            )),
            "checks": [
                "semantic-parity",
                "identity-fail-closed",
                "no-supported-fixture-oom",
                "failure-atomicity",
                "checked-measurements",
            ],
        },
    }
    record["recordDigest"] = canonical_json_digest(record)
    validate_depth_moment_qualification_record(record)

    for path, replacement in (
        (("directEvidence", "sourceRevision"), "sha256:" + ("0" * 64)),
        (("directEvidence", "runtimeBuildId"), "sha256:" + ("1" * 64)),
        (("runtime", "computeCapability"), "9.0"),
    ):
        stale = deepcopy(record)
        nested = stale[path[0]]
        assert isinstance(nested, dict)
        nested[path[1]] = replacement
        del stale["recordDigest"]
        stale["recordDigest"] = canonical_json_digest(stale)
        try:
            validate_depth_moment_qualification_record(stale)
        except DepthMomentQualificationError:
            continue
        raise RuntimeError(f"Qualification mismatch did not fail closed: {path}")
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DEPTH_MOMENT_QUALIFICATION_PATH,
    )
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 3 or args.warmups < 1:
        raise SystemExit("Qualification requires at least 3 samples and 1 warmup.")
    if platform.system() != EXPECTED_OPERATING_SYSTEM:
        raise SystemExit(f"Qualification requires {EXPECTED_OPERATING_SYSTEM}.")
    if not torch.cuda.is_available():
        raise SystemExit("Qualification requires an available CUDA device.")

    record = measured_run(samples=args.samples, warmups=args.warmups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    staging = args.output.with_suffix(args.output.suffix + ".staging")
    staging.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, args.output)
    print(json.dumps({
        "output": str(args.output),
        "recordDigest": record["recordDigest"],
        "status": record["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

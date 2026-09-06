"""Input-package and locked-GPU runner for the issue #115 shadow slice.

This module is intentionally an operator-run harness, not a browser route.
It validates the captured A/B/C package, reuses the production Direct Evidence
and existing S0/Scope/EWS seams, and writes no Candidate or editor state.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import resource
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .binary_scene_snapshot import (
    BinarySceneSnapshotUploadStore,
    PackedBinarySceneSnapshot,
    parse_binary_scene_snapshot_manifest,
)
from .camera_binding import camera_binding_digest, parse_camera_binding
from .conservative_seed import (
    create_conservative_seed_policy,
    create_conservative_seed_target_geometry,
    evaluate_conservative_seed_shadow,
)
from .digests import canonical_json_digest, route_b_artifact_digest
from .direct_gaussian_evidence import (
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)
from .gaussian_evidence_contract import (
    create_evidence_working_set,
    resolve_evidence_working_set_boundary,
)
from .gsplat_renderer import GsplatContributorRenderer, LockedGsplatBackend
from .issue_115_bonsai_diagnostics import (
    ISSUE_115_RAW_AGGREGATION_MODE,
    aggregate_issue_115_diagnostics,
)
from .masking import find_sam3_image_checkpoint
from .reference_gaussian_evidence import (
    default_reference_evidence_policy,
    validate_stable_mask_artifact,
)
from .reference_gaussian_evidence_aggregation import reference_aggregation_policy
from .renderer_runtime import CurrentProcessGsplatInspection, current_renderer_runtime

DEFAULT_S0_COMPARISON_BUDGET = 50_000_000


class Issue115BonsaiRunBlocked(RuntimeError):
    """A real input or environment prevented a truthful #115 run."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.details = dict(details or {})


@dataclass(frozen=True)
class BonsaiInputPackage:
    """One validated immutable A, B, or C input archive."""

    archive_path: Path
    archive_sha256: str
    input_json: dict[str, Any]
    scene_manifest: Any
    camera_binding: dict[str, object]
    renderer_camera: dict[str, object]
    width: int
    height: int
    rgb_png: bytes
    mask_artifact: dict[str, object] | None

    @property
    def role(self) -> str:
        value = self.input_json["role"]
        assert isinstance(value, str)
        return value

    @property
    def target_splat_id(self) -> str:
        request_binding = self.input_json["requestBinding"]
        assert isinstance(request_binding, dict)
        dependency = request_binding["dependencyToken"]
        assert isinstance(dependency, dict)
        target = dependency["splatId"]
        assert isinstance(target, str)
        return target


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Issue115BonsaiRunBlocked(
            f"{label} must be an object.", stage="input-validation"
        )
    return value


def _non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Issue115BonsaiRunBlocked(
            f"{label} must be a non-empty string.", stage="input-validation"
        )
    return value


def _digest(value: object, label: str) -> str:
    result = _non_empty_string(value, label)
    if (
        len(result) != 71
        or not result.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in result[7:])
    ):
        raise Issue115BonsaiRunBlocked(
            f"{label} must be a canonical SHA-256 digest.",
            stage="input-validation",
        )
    return result


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _validate_ids(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(
            isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or stable_id < 0
            for stable_id in value
        )
        or any(value[index - 1] >= value[index] for index in range(1, len(value)))
    ):
        raise Issue115BonsaiRunBlocked(
            f"{label} must be sorted, unique Stable Gaussian IDs.",
            stage="input-validation",
        )
    return list(value)


def _read_png_dimensions(payload: bytes, label: str) -> tuple[int, int]:
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(payload)) as image:
            image.load()
            if image.format != "PNG" or image.mode != "RGB":
                raise ValueError("PNG must decode as RGB")
            return image.size
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            f"{label} is not a valid RGB PNG.", stage="input-validation"
        ) from error


def _read_mask_artifact(
    archive: ZipFile, input_json: Mapping[str, Any]
) -> dict[str, object] | None:
    masks = input_json.get("masks")
    if not isinstance(masks, list):
        raise Issue115BonsaiRunBlocked(
            "Input masks must be an array.", stage="input-validation"
        )
    role = input_json.get("role")
    if role == "C":
        if masks:
            raise Issue115BonsaiRunBlocked(
                "C inspection input must not contain a mask.", stage="input-validation"
            )
        return None
    if len(masks) != 1 or not isinstance(masks[0], dict):
        raise Issue115BonsaiRunBlocked(
            "A/B input must contain exactly one confirmed mask.",
            stage="input-validation",
        )
    record = masks[0]
    if record.get("status") != "user-confirmed" or record.get("source") != "hybrid":
        raise Issue115BonsaiRunBlocked(
            "A/B mask is not the exported user-confirmed hybrid mask.",
            stage="human-review",
        )
    raw_file = record.get("rawFile")
    artifact = record.get("artifact")
    if not isinstance(raw_file, str) or not raw_file or not isinstance(artifact, dict):
        raise Issue115BonsaiRunBlocked(
            "A/B mask artifact or raw file is missing.", stage="input-validation"
        )
    try:
        raw_bytes = archive.read(raw_file)
        encoded = artifact.get("data")
        if not isinstance(encoded, str):
            raise TypeError("mask data is absent")
        decoded = base64.b64decode(encoded, validate=True)
        if decoded != raw_bytes:
            raise ValueError("embedded and exported mask bytes differ")
        validate_stable_mask_artifact(artifact)
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            "A/B Stable Mask bytes or digest are invalid.",
            stage="input-validation",
        ) from error
    return dict(artifact)


def load_bonsai_input_package(
    archive_path: Path, *, expected_role: str | None = None
) -> BonsaiInputPackage:
    """Validate one real input ZIP without changing its captured contents."""

    if not archive_path.is_file():
        raise Issue115BonsaiRunBlocked(
            f"Input archive is missing: {archive_path}", stage="input-validation"
        )
    try:
        with ZipFile(archive_path) as archive:
            input_json_value = json.loads(archive.read("input.json"))
            input_json = _mapping(input_json_value, "input.json")
            _non_empty_string(input_json.get("schema"), "input schema")
            if input_json.get("schema") != "ai-select-input-export/v1":
                raise ValueError("unsupported input schema")
            role = _non_empty_string(input_json.get("role"), "input role")
            if expected_role is not None and role != expected_role:
                raise ValueError(f"expected role {expected_role}, got {role}")
            expected_participation = (
                "inspection-only" if role == "C" else "fusion-input"
            )
            if input_json.get("participation") != expected_participation:
                raise ValueError("input participation does not match its role")
            expected_confirmation = "not-applicable" if role == "C" else "confirmed"
            if input_json.get("humanConfirmation") != expected_confirmation:
                raise ValueError("input human confirmation is incomplete")
            if input_json.get("rendererId") != "gsplat":
                raise ValueError("input renderer identity is not gsplat")
            _non_empty_string(
                input_json.get("targetDefinition"), "target definition"
            )
            request_binding = _mapping(
                input_json.get("requestBinding"), "request binding"
            )
            dependency = _mapping(
                request_binding.get("dependencyToken"), "dependency token"
            )
            _non_empty_string(dependency.get("splatId"), "target splat ID")
            _digest(
                input_json.get("renderWorkingSetToken"),
                "captured Render Working Set token",
            )
            scene_manifest = parse_binary_scene_snapshot_manifest(
                input_json.get("sceneSnapshot")
            )
            camera_binding_value = _mapping(
                input_json.get("cameraBinding"), "CameraBinding"
            )
            camera_binding, renderer_camera, width, height = parse_camera_binding(
                camera_binding_value
            )
            rgb_metadata = _mapping(input_json.get("rgb"), "RGB metadata")
            rgb_digest = _non_empty_string(rgb_metadata.get("digest"), "RGB digest")
            if rgb_metadata.get("width") != width or rgb_metadata.get("height") != height:
                raise ValueError("RGB and CameraBinding dimensions differ")
            rgb_png = archive.read("rgb.png")
            if _sha256_bytes(rgb_png) != rgb_digest:
                raise ValueError("RGB bytes do not match the exported digest")
            if _read_png_dimensions(rgb_png, "rgb.png") != (width, height):
                raise ValueError("RGB PNG dimensions differ from CameraBinding")
            mask_artifact = _read_mask_artifact(archive, input_json)
            rendered_ids = _validate_ids(
                input_json.get("renderStableGaussianIds"),
                "render Stable Gaussian IDs",
            )
            if len(rendered_ids) != int(scene_manifest.content["gaussianCount"]):
                raise ValueError("render Stable Gaussian ID count differs from snapshot")
    except Issue115BonsaiRunBlocked:
        raise
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            f"Input archive validation failed: {archive_path.name}: {error}",
            stage="input-validation",
        ) from error
    return BonsaiInputPackage(
        archive_path=archive_path,
        archive_sha256=_archive_sha256(archive_path),
        input_json=input_json,
        scene_manifest=scene_manifest,
        camera_binding=camera_binding,
        renderer_camera=renderer_camera,
        width=width,
        height=height,
        rgb_png=rgb_png,
        mask_artifact=mask_artifact,
    )


def _read_snapshot_chunk(package: BonsaiInputPackage, index: int) -> bytes:
    try:
        with ZipFile(package.archive_path) as archive:
            return archive.read(f"snapshot/{index}.bin")
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            f"{package.role} snapshot chunk {index} is unavailable.",
            stage="snapshot-validation",
        ) from error


def _snapshot_manifest_equal(left: Any, right: Any) -> bool:
    return (
        left.format == right.format
        and left.format_version == right.format_version
        and left.scene_id == right.scene_id
        and left.scene_version == right.scene_version
        and left.content_digest == right.content_digest
        and left.content == right.content
        and left.chunk_byte_length == right.chunk_byte_length
        and left.chunks == right.chunks
    )


def _commit_snapshot(
    package: BonsaiInputPackage, store: BinarySceneSnapshotUploadStore
) -> PackedBinarySceneSnapshot:
    admission = store.begin(package.scene_manifest)
    if admission.upload_id is None:
        snapshot = store.committed_snapshot(
            package.scene_manifest.scene_id, package.scene_manifest.scene_version
        )
        if snapshot is None:
            raise Issue115BonsaiRunBlocked(
                "The immutable Scene Snapshot commit acknowledgement has no snapshot.",
                stage="snapshot-validation",
            )
        return snapshot
    try:
        for chunk in package.scene_manifest.chunks:
            payload = _read_snapshot_chunk(package, chunk.index)
            store.accept_chunk(
                admission.upload_id,
                chunk.index,
                payload,
                chunk.digest,
            )
        return store.commit(admission.upload_id)
    except Issue115BonsaiRunBlocked:
        store.abort(admission.upload_id)
        raise
    except Exception as error:
        store.abort(admission.upload_id)
        raise Issue115BonsaiRunBlocked(
            "The immutable Scene Snapshot chunks failed validation.",
            stage="snapshot-validation",
        ) from error


def _verify_shared_snapshot(
    base: BonsaiInputPackage,
    package: BonsaiInputPackage,
) -> None:
    if not _snapshot_manifest_equal(base.scene_manifest, package.scene_manifest):
        raise Issue115BonsaiRunBlocked(
            f"{package.role} does not share A's immutable Scene Snapshot.",
            stage="snapshot-validation",
        )
    for chunk in package.scene_manifest.chunks:
        payload = _read_snapshot_chunk(package, chunk.index)
        if (
            len(payload) != chunk.byte_length
            or _sha256_bytes(payload) != chunk.digest
        ):
            raise Issue115BonsaiRunBlocked(
                f"{package.role} snapshot chunk {chunk.index} digest is invalid.",
                stage="snapshot-validation",
            )


def _target_ids(
    snapshot: PackedBinarySceneSnapshot, target_splat_id: str
) -> tuple[int, int, list[int]]:
    scope = snapshot.authoritative_render_scope
    if not isinstance(scope, Mapping) or scope.get("targetSplatId") != target_splat_id:
        raise Issue115BonsaiRunBlocked(
            "The authoritative render scope does not bind the target.",
            stage="snapshot-validation",
        )
    entries = scope.get("entries")
    if not isinstance(entries, list):
        raise Issue115BonsaiRunBlocked(
            "The authoritative render scope entries are missing.",
            stage="snapshot-validation",
        )
    targets = [
        entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("role") == "target"
    ]
    if len(targets) != 1:
        raise Issue115BonsaiRunBlocked(
            "The authoritative render scope target is ambiguous.",
            stage="snapshot-validation",
        )
    entry = targets[0]
    row_offset = entry.get("rowOffset")
    row_count = entry.get("rowCount")
    if (
        isinstance(row_offset, bool)
        or not isinstance(row_offset, int)
        or isinstance(row_count, bool)
        or not isinstance(row_count, int)
        or row_offset < 0
        or row_count <= 0
        or row_offset + row_count > snapshot.gaussian_count
    ):
        raise Issue115BonsaiRunBlocked(
            "The authoritative render scope target row range is invalid.",
            stage="snapshot-validation",
        )
    stable_ids = list(snapshot.stable_ids())
    target_ids = stable_ids[row_offset : row_offset + row_count]
    if not target_ids or target_ids != sorted(target_ids) or len(set(target_ids)) != len(target_ids):
        raise Issue115BonsaiRunBlocked(
            "The target Stable Gaussian rows are not sorted and unique.",
            stage="snapshot-validation",
        )
    return row_offset, row_count, target_ids


def _target_geometry(
    snapshot: PackedBinarySceneSnapshot,
    *,
    row_offset: int,
    target_ids: Sequence[int],
) -> dict[str, object]:
    try:
        means = snapshot.field("means").cast("f")
        log_scales = snapshot.field("logScales").cast("f")
        rows = [
            {
                "stableGaussianId": int(stable_id),
                "center": [
                    float(means[index * 3 + component])
                    for component in range(3)
                ],
                "logScales": [
                    float(log_scales[index * 3 + component])
                    for component in range(3)
                ],
            }
            for index, stable_id in enumerate(target_ids, start=row_offset)
        ]
        return create_conservative_seed_target_geometry(
            target_splat_id=snapshot.authoritative_render_scope["targetSplatId"],
            rows=rows,
        )
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            "The packed Scene Snapshot geometry could not be prepared for S0.",
            stage="geometry-validation",
        ) from error


def _s0_policy() -> dict[str, object]:
    return create_conservative_seed_policy(
        {
            "schemaVersion": 1,
            "policyId": "conservative-seed-s0/experimental-shadow-v1",
            "minimumVisibleMass": 0.10,
            "minimumPositiveRatio": 0.80,
            "maximumNegativeMass": 0.05,
            "maximumConflictRatio": 0.10,
            "connectivityScaleMultiplier": 4.0,
            "minimumSatelliteGaussianCount": 1,
            "minimumSatellitePositiveMass": 0.25,
            "grossOutlierScaleMultiplier": 40.0,
        }
    )


def _candidate_count(artifact: Mapping[str, object], policy: Mapping[str, object]) -> int:
    positive = artifact.get("positiveMass")
    negative = artifact.get("negativeMass")
    visible = artifact.get("visibleMass")
    if not all(isinstance(value, list) for value in (positive, negative, visible)):
        raise Issue115BonsaiRunBlocked(
            "Anchor Direct Evidence mass arrays are incomplete.", stage="s0"
        )
    assert isinstance(positive, list)
    assert isinstance(negative, list)
    assert isinstance(visible, list)
    if not len(positive) == len(negative) == len(visible):
        raise Issue115BonsaiRunBlocked(
            "Anchor Direct Evidence mass arrays have different lengths.", stage="s0"
        )
    count = 0
    for p_value, n_value, v_value in zip(positive, negative, visible, strict=True):
        p = float(p_value)
        n = float(n_value)
        v = float(v_value)
        if not all(math.isfinite(value) for value in (p, n, v)):
            raise Issue115BonsaiRunBlocked(
                "Anchor Direct Evidence contains a non-finite mass.", stage="s0"
            )
        if (
            v >= float(policy["minimumVisibleMass"])
            and n <= float(policy["maximumNegativeMass"])
            and n / v <= float(policy["maximumConflictRatio"])
            and p / v >= float(policy["minimumPositiveRatio"])
        ):
            count += 1
    return count


def _current_input(
    package: BonsaiInputPackage,
    *,
    snapshot: PackedBinarySceneSnapshot,
    evidence_working_set: Mapping[str, object],
    view_id: str,
    render_stable_ids: Sequence[int],
) -> dict[str, object]:
    request_binding = package.input_json.get("requestBinding")
    if not isinstance(request_binding, dict):
        raise Issue115BonsaiRunBlocked(
            "The input request binding is invalid.", stage="input-validation"
        )
    if package.mask_artifact is None:
        raise Issue115BonsaiRunBlocked(
            "A/B Direct Evidence requires an exported Stable Mask.", stage="human-review"
        )
    # The exported token is retained in inputIdentity. This derived admission
    # token is the packed snapshot identity that Direct Evidence validates
    # against the bytes being rasterized.
    policy = default_reference_evidence_policy()
    dependency = request_binding.get("dependencyToken")
    if not isinstance(dependency, dict):
        raise Issue115BonsaiRunBlocked(
            "The input dependency token is invalid.", stage="input-validation"
        )
    return {
        "requestBinding": json.loads(json.dumps(request_binding)),
        "targetSplatId": package.target_splat_id,
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": "included",
            "cameraBindingDigest": camera_binding_digest(package.camera_binding),
            "rgbDigest": package.input_json["rgb"]["digest"],
            "stableMaskDigest": package.mask_artifact["digest"],
        },
        "evidencePolicyDigest": policy["evidencePolicyDigest"],
        "renderWorkingSet": {
            "targetSplatId": package.target_splat_id,
            "dependencyToken": json.loads(json.dumps(dependency)),
            "cameraBindingDigest": camera_binding_digest(package.camera_binding),
            "renderWorkingSetToken": snapshot.content_digest,
            "stableGaussianIds": list(render_stable_ids),
            "completeness": "complete",
        },
        "evidenceWorkingSet": dict(evidence_working_set),
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    }


def _direct_evidence(
    renderer: GsplatContributorRenderer,
    package: BonsaiInputPackage,
    *,
    snapshot: PackedBinarySceneSnapshot,
    evidence_working_set: Mapping[str, object],
    view_id: str,
    target_ids: Sequence[int],
    render_stable_ids: Sequence[int],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    current_input = _current_input(
        package,
        snapshot=snapshot,
        evidence_working_set=evidence_working_set,
        view_id=view_id,
        render_stable_ids=render_stable_ids,
    )
    started = time.perf_counter_ns()
    try:
        artifact = renderer.compute_direct_evidence(
            admission_input=current_input,
            stable_mask_artifact=package.mask_artifact,
            policy=default_reference_evidence_policy(),
            scene_snapshot=snapshot,
            camera_binding=package.camera_binding,
            target_stable_ids=target_ids,
        )
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            f"{view_id} Direct Evidence did not complete: {error}",
            stage=f"direct-evidence-{view_id}",
        ) from error
    elapsed = time.perf_counter_ns() - started
    telemetry = {
        "elapsedNanoseconds": elapsed,
        "gaussianCount": len(artifact["stableGaussianIds"]),
        "peakVramBytes": renderer.last_peak_vram_bytes,
        "kernel": dict(renderer.last_direct_evidence_telemetry or {}),
    }
    return current_input, artifact, telemetry


def _support_ids(
    artifact: Mapping[str, object], *, policy: Mapping[str, object]
) -> list[int]:
    stable_ids = artifact.get("stableGaussianIds")
    positive = artifact.get("positiveMass")
    negative = artifact.get("negativeMass")
    visible = artifact.get("visibleMass")
    if not all(isinstance(value, list) for value in (stable_ids, positive, negative, visible)):
        raise Issue115BonsaiRunBlocked(
            "Direct Evidence support arrays are incomplete.", stage="scope"
        )
    assert isinstance(stable_ids, list)
    assert isinstance(positive, list)
    assert isinstance(negative, list)
    assert isinstance(visible, list)
    minimum_visible = float(policy["minimumPerViewVisibleMass"])
    minimum_evidence = float(policy["minimumPerViewEvidenceMass"])
    minimum_ratio = float(policy["selectedPositiveRatioThreshold"])
    return sorted(
        int(stable_id)
        for stable_id, p_value, n_value, v_value in zip(
            stable_ids, positive, negative, visible, strict=True
        )
        if float(v_value) >= minimum_visible
        and float(p_value) + float(n_value) >= minimum_evidence
        and float(p_value) / (float(p_value) + float(n_value)) >= minimum_ratio
    )


def _scope_setup(
    *,
    seed_record: Mapping[str, object],
    target_ids: Sequence[int],
    secondary_artifact: Mapping[str, object],
    support_policy: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], list[int]]:
    """Project S0 and B support onto the existing EWS role boundary.

    The full TargetScopeState record is an immutable historical shadow object
    containing one geometry row and several ledgers per target Gaussian. It
    is not the #115 diagnostic's product. Rebuilding that object for the
    1.24M-row real scene consumed several GiB before any B/C result existed.
    Keep this slice on the existing Scope-facing Core/Context and boundary
    interfaces, and expose the omitted TargetScopeState validation explicitly
    instead of claiming that a non-scalable state transition ran.
    """
    core_ids_value = seed_record.get("admittedStableGaussianIds")
    if not isinstance(core_ids_value, list) or not core_ids_value:
        raise Issue115BonsaiRunBlocked(
            "S0 produced no admitted core; Scope cannot be initialized.", stage="scope"
        )
    core_ids = sorted(int(value) for value in core_ids_value)
    b_support = set(_support_ids(secondary_artifact, policy=support_policy))
    new_support = sorted(b_support - set(core_ids))
    target_set = {int(value) for value in target_ids}
    if not set(core_ids).issubset(target_set) or not set(new_support).issubset(target_set):
        raise Issue115BonsaiRunBlocked(
            "The Scope role projection contains an ID outside the target universe.",
            stage="scope",
        )
    source_payload = {
        "schemaVersion": 1,
        "sourceKind": "direct-evidence-positive-support",
        "viewId": secondary_artifact["viewId"],
        "artifactDigest": secondary_artifact["artifactDigest"],
        "stableMaskDigest": secondary_artifact["stableMaskDigest"],
        "supportedStableGaussianIds": new_support,
        "reason": "confirmed B view supplies positive support outside the S0 core",
    }
    source_projection_digest = route_b_artifact_digest(source_payload)
    context_ids = sorted(target_set - set(core_ids))
    scope_summary = {
        "status": "shadow-role-projection",
        "targetScopeStateExecuted": False,
        "targetScopeStateReason": (
            "The existing full TargetScopeState ledger is not scalable for this "
            "1.24M-row diagnostic; Core/Context and boundary contracts are used."
        ),
        "seedRecordDigest": seed_record["recordDigest"],
        "sourceProjectionDigest": source_projection_digest,
        "supportPolicy": dict(support_policy),
        "coreCount": len(core_ids),
        "activeFrontierCount": len(new_support),
        "requiredContextCount": len(context_ids),
        "coreStableGaussianIdsDigest": route_b_artifact_digest({"ids": core_ids}),
        "activeFrontierStableGaussianIdsDigest": route_b_artifact_digest(
            {"ids": new_support}
        ),
        "requiredContextStableGaussianIdsDigest": route_b_artifact_digest(
            {"ids": context_ids}
        ),
        "source": source_payload,
    }
    role_binding_payload = {
        "adapterId": "issue-115-scope-roles-to-ews-shadow/v2",
        "scopeStatus": "shadow-role-projection",
        "targetScopeStateExecuted": False,
        "seedRecordDigest": seed_record["recordDigest"],
        "sourceProjectionDigest": source_projection_digest,
        "coreStableGaussianIds": core_ids,
        "activeFrontierStableGaussianIds": new_support,
        "rejectedFrontierStableGaussianIds": [],
        "requiredContextStableGaussianIds": context_ids,
    }
    return scope_summary, {
        **role_binding_payload,
        "bindingDigest": canonical_json_digest(role_binding_payload),
    }, core_ids


def _scope_evidence_working_set(
    *, target_splat_id: str, target_ids: Sequence[int], core_ids: Sequence[int], seed_digest: str
) -> dict[str, object]:
    core = sorted(int(value) for value in core_ids)
    target = sorted(int(value) for value in target_ids)
    context = sorted(set(target) - set(core))
    return create_evidence_working_set(
        {
            "targetSplatId": target_splat_id,
            "coreTargetStableIds": core,
            "contextStableGaussianIds": context,
            "targetGeometryHintSeedDigest": seed_digest,
        }
    )


def _scope_role_binding_with_ews(
    role_binding: Mapping[str, object], evidence_working_set: Mapping[str, object]
) -> dict[str, object]:
    payload = {
        **dict(role_binding),
        "evidenceWorkingSetToken": evidence_working_set["evidenceWorkingSetToken"],
    }
    return {
        **payload,
        "bindingDigest": canonical_json_digest(payload),
    }


def _boundary_clear(
    current_input: Mapping[str, object], evidence_working_set: Mapping[str, object]
) -> dict[str, object]:
    result = resolve_evidence_working_set_boundary(
        {
            "renderWorkingSet": current_input["renderWorkingSet"],
            "evidenceWorkingSet": evidence_working_set,
            "boundaryStableGaussianIds": [],
            "resolution": "fail-closed",
        }
    )
    if result.get("status") != "clear":
        raise Issue115BonsaiRunBlocked(
            "The explicit Evidence Working Set boundary did not resolve clear.",
            stage="scope/boundary",
            details=result,
        )
    return result


def _c_inspection(
    renderer: GsplatContributorRenderer,
    package: BonsaiInputPackage,
    *,
    snapshot: PackedBinarySceneSnapshot,
    render_stable_ids: Sequence[int],
) -> tuple[dict[str, object], dict[str, object]]:
    started = time.perf_counter_ns()
    try:
        rasterized = renderer.backend.rasterize_reference_evidence_typed(
            snapshot=snapshot,
            camera=package.renderer_camera,
            width=package.width,
            height=package.height,
            stable_ids=render_stable_ids,
        )
        import torch

        ids = rasterized.contributor_ids
        weights = rasterized.contributor_weights
        valid = (ids >= 0) & (weights > 0)
        row_ids = ids[valid].to(dtype=torch.long)
        visible_ids = torch.unique(
            rasterized.stable_ids[row_ids]
        ).detach().cpu().tolist()
        visible_ids = sorted(int(value) for value in visible_ids)
        rgb_png = _encode_rgb_png(
            rasterized.service_rgb_bytes, package.width, package.height
        )
        rgb_digest = _sha256_bytes(rgb_png)
        if rgb_digest != package.input_json["rgb"]["digest"]:
            raise ValueError("C authoritative RGB digest does not match")
        peak_vram = rasterized.peak_vram_bytes
        del row_ids, ids, weights, valid, rasterized
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as error:
        raise Issue115BonsaiRunBlocked(
            f"C inspection-only projection did not complete: {error}",
            stage="c-inspection",
        ) from error
    elapsed = time.perf_counter_ns() - started
    return (
        {
            "viewId": "view-c",
            "cameraBindingDigest": camera_binding_digest(package.camera_binding),
            "rgbDigest": package.input_json["rgb"]["digest"],
            "visibleStableGaussianIds": visible_ids,
        },
        {
            "elapsedNanoseconds": elapsed,
            "gaussianCount": len(render_stable_ids),
            "visibleStableGaussianCount": len(visible_ids),
            "peakVramBytes": peak_vram,
        },
    )


def _encode_rgb_png(rgb_bytes: bytes, width: int, height: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    encoded = BytesIO()
    Image.frombytes("RGB", (width, height), rgb_bytes).save(encoded, format="PNG")
    return encoded.getvalue()


def _runtime_record() -> dict[str, object]:
    facts = CurrentProcessGsplatInspection().facts()
    status = current_renderer_runtime().status()
    checkpoint = find_sam3_image_checkpoint()
    if status.status != "ready":
        raise Issue115BonsaiRunBlocked(
            f"The current Companion renderer is unavailable: {status.message}",
            stage="environment",
        )
    if checkpoint is None:
        raise Issue115BonsaiRunBlocked(
            "The SAM 3 checkpoint is absent from ~/.cache/modelscope/models.",
            stage="environment/model-cache",
        )
    return {
        "rendererStatus": status.status,
        "operatingSystem": facts.operating_system,
        "environmentPrefix": str(facts.environment_prefix),
        "cudaAvailable": facts.cuda_available,
        "gpuName": facts.gpu_name,
        "computeCapability": facts.compute_capability,
        "driverVersion": facts.driver_version,
        "torchPackagePath": (
            None if facts.torch_package_path is None else str(facts.torch_package_path)
        ),
        "gsplatPackagePath": (
            None if facts.gsplat_package_path is None else str(facts.gsplat_package_path)
        ),
        "modelCacheCheckpointPath": str(checkpoint),
        "modelCacheCheckpointPresent": True,
    }


def _package_identity(
    package: BonsaiInputPackage, *, derived_render_working_set_token: str
) -> dict[str, object]:
    rgb = package.input_json["rgb"]
    assert isinstance(rgb, dict)
    mask_digest = (
        None
        if package.mask_artifact is None
        else package.mask_artifact["digest"]
    )
    return {
        "role": package.role,
        "archive": str(package.archive_path),
        "archiveSha256": package.archive_sha256,
        "sceneId": package.scene_manifest.scene_id,
        "sceneVersion": package.scene_manifest.scene_version,
        "capturedRenderWorkingSetToken": package.input_json["renderWorkingSetToken"],
        "derivedRenderWorkingSetToken": derived_render_working_set_token,
        "cameraBindingDigest": camera_binding_digest(package.camera_binding),
        "rgbDigest": rgb["digest"],
        "maskDigest": mask_digest,
        "width": package.width,
        "height": package.height,
    }


def _summary_record(
    record: Mapping[str, object], timing: Mapping[str, object]
) -> dict[str, object]:
    return {
        "recordDigest": record["recordDigest"],
        "seedPolicy": record["seedPolicy"],
        "targetGaussianCount": len(record["targetStableGaussianIds"]),
        "admittedCount": len(record["admittedStableGaussianIds"]),
        "coreCandidateCount": len(record["coreCandidateStableGaussianIds"]),
        "satelliteCount": len(record["satelliteStableGaussianIds"]),
        "filteredCount": len(record["filteredStableGaussianIds"]),
        "unevaluatedCount": len(record["unevaluatedStableGaussianIds"]),
        "coreStableGaussianIds": list(record["coreCandidateStableGaussianIds"]),
        "satelliteStableGaussianIds": list(record["satelliteStableGaussianIds"]),
        "timing": dict(timing),
    }


def _resource_record() -> dict[str, object]:
    return {"hostMaxRssBytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024}


def run_issue_115_bonsai_diagnostics(
    *,
    input_directory: Path,
    max_s0_comparisons: int = DEFAULT_S0_COMPARISON_BUDGET,
) -> dict[str, object]:
    """Run the real A/B Direct Evidence + S0/Scope + C inspection slice."""

    started = time.perf_counter_ns()
    runtime = _runtime_record()
    packages = {
        role: load_bonsai_input_package(
            input_directory / filename, expected_role=role
        )
        for role, filename in (
            ("A", "bonsai-A-input.zip"),
            ("B", "bonsai-B-input.zip"),
            ("C", "bonsai-C-inspection.zip"),
        )
    }
    anchor = packages["A"]
    secondary = packages["B"]
    inspection = packages["C"]
    if not anchor.input_json["requestBinding"] == secondary.input_json["requestBinding"]:
        raise Issue115BonsaiRunBlocked(
            "A and B request bindings differ.", stage="input-validation"
        )
    if not anchor.input_json["targetDefinition"] == secondary.input_json["targetDefinition"]:
        raise Issue115BonsaiRunBlocked(
            "A and B target definitions differ.", stage="input-validation"
        )
    if anchor.target_splat_id != secondary.target_splat_id or anchor.target_splat_id != inspection.target_splat_id:
        raise Issue115BonsaiRunBlocked(
            "A/B/C target identities differ.", stage="input-validation"
        )

    with tempfile.TemporaryDirectory(prefix="issue-115-bonsai-") as staging:
        store = BinarySceneSnapshotUploadStore(Path(staging) / "snapshot-store")
        snapshot = _commit_snapshot(anchor, store)
        try:
            for package in (secondary, inspection):
                _verify_shared_snapshot(anchor, package)
            render_stable_ids = list(snapshot.stable_ids())
            for package in packages.values():
                exported_ids = _validate_ids(
                    package.input_json["renderStableGaussianIds"],
                    f"{package.role} render Stable Gaussian IDs",
                )
                if exported_ids != render_stable_ids:
                    raise Issue115BonsaiRunBlocked(
                        f"{package.role} Stable-ID mapping differs from the snapshot.",
                        stage="snapshot-validation",
                    )
            row_offset, row_count, target_ids = _target_ids(
                snapshot, anchor.target_splat_id
            )
            geometry = _target_geometry(
                snapshot,
                row_offset=row_offset,
                target_ids=target_ids,
            )
            initial_ews = create_evidence_working_set(
                {
                    "targetSplatId": anchor.target_splat_id,
                    "coreTargetStableIds": target_ids,
                    "contextStableGaussianIds": [],
                }
            )
            renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
            evidence_policy = default_reference_evidence_policy()
            aggregation_policy = reference_aggregation_policy(
                aggregation_mode=ISSUE_115_RAW_AGGREGATION_MODE
            )
            initial_a_input, initial_a, initial_a_timing = _direct_evidence(
                renderer,
                anchor,
                snapshot=snapshot,
                evidence_working_set=initial_ews,
                view_id="anchor-view",
                target_ids=target_ids,
                render_stable_ids=render_stable_ids,
            )
            _initial_b_input, initial_b, initial_b_timing = _direct_evidence(
                renderer,
                secondary,
                snapshot=snapshot,
                evidence_working_set=initial_ews,
                view_id="view-b",
                target_ids=target_ids,
                render_stable_ids=render_stable_ids,
            )
            candidate_count = _candidate_count(initial_a, _s0_policy())
            estimated_comparisons = candidate_count * max(0, candidate_count - 1) // 2
            s0_started = time.perf_counter_ns()
            s0_evaluation = evaluate_conservative_seed_shadow(
                evidence_artifact=initial_a,
                target_geometry=geometry,
                policy=_s0_policy(),
            )
            s0_elapsed = time.perf_counter_ns() - s0_started
            s0_record = s0_evaluation["record"]
            assert isinstance(s0_record, dict)
            s0_timing = dict(s0_evaluation["timingTelemetry"])
            s0_timing["wallNanoseconds"] = s0_elapsed
            actual_s0_comparisons = int(
                s0_timing["connectivityComparisonCount"]
            )
            if (
                max_s0_comparisons
                and actual_s0_comparisons > max_s0_comparisons
            ):
                raise Issue115BonsaiRunBlocked(
                    "The exact S0 spatial componentization exceeded the configured comparison budget.",
                    stage="s0",
                    details={
                        "candidateCount": candidate_count,
                        "estimatedQuadraticPairs": estimated_comparisons,
                        "actualConnectivityComparisons": actual_s0_comparisons,
                        "comparisonBudget": max_s0_comparisons,
                    },
                )
            scope_started = time.perf_counter_ns()
            scope_summary, scope_role_binding, scope_core_ids = _scope_setup(
                seed_record=s0_record,
                target_ids=target_ids,
                secondary_artifact=initial_b,
                support_policy=aggregation_policy,
            )
            scope_summary["wallNanoseconds"] = time.perf_counter_ns() - scope_started
            final_ews = _scope_evidence_working_set(
                target_splat_id=anchor.target_splat_id,
                target_ids=target_ids,
                core_ids=scope_core_ids,
                seed_digest=str(s0_record["recordDigest"]),
            )
            scope_role_binding = _scope_role_binding_with_ews(
                scope_role_binding, final_ews
            )
            _boundary_clear(initial_a_input, final_ews)
            final_a_input, final_a, final_a_timing = _direct_evidence(
                renderer,
                anchor,
                snapshot=snapshot,
                evidence_working_set=final_ews,
                view_id="anchor-view",
                target_ids=target_ids,
                render_stable_ids=render_stable_ids,
            )
            final_b_input, final_b, final_b_timing = _direct_evidence(
                renderer,
                secondary,
                snapshot=snapshot,
                evidence_working_set=final_ews,
                view_id="view-b",
                target_ids=target_ids,
                render_stable_ids=render_stable_ids,
            )
            _boundary_clear(final_a_input, final_ews)
            _boundary_clear(final_b_input, final_ews)
            c_input, c_timing = _c_inspection(
                renderer,
                inspection,
                snapshot=snapshot,
                render_stable_ids=render_stable_ids,
            )
            aggregation_started = time.perf_counter_ns()
            diagnostic = aggregate_issue_115_diagnostics(
                aggregation_input={
                    "requestBinding": anchor.input_json["requestBinding"],
                    "targetSplatId": anchor.target_splat_id,
                    "classificationUniverseStableGaussianIds": list(target_ids),
                    "classificationScopeStableGaussianIds": list(target_ids),
                    "evidenceWorkingSet": final_ews,
                    "views": [
                        {"currentInput": final_a_input, "artifact": final_a},
                        {"currentInput": final_b_input, "artifact": final_b},
                    ],
                },
                c_inspection=c_input,
            )
            aggregation_elapsed = time.perf_counter_ns() - aggregation_started
            total_elapsed = time.perf_counter_ns() - started
            result = {
                "status": "complete",
                "acceptance": {
                    "diagnosticComputation": "complete",
                    "realInput": True,
                    "realGpu": True,
                    "targetScopeDomain": "not-executed",
                    "productionCandidate": "not-produced",
                },
                "diagnostic": diagnostic,
                "inputIdentity": {
                    "targetDefinition": anchor.input_json["targetDefinition"],
                    "packages": [
                        _package_identity(
                            packages[role],
                            derived_render_working_set_token=snapshot.content_digest,
                        )
                        for role in ("A", "B", "C")
                    ],
                    "sceneSnapshot": {
                        "sceneId": snapshot.scene_id,
                        "sceneVersion": snapshot.scene_version,
                        "contentDigest": snapshot.content_digest,
                        "gaussianCount": snapshot.gaussian_count,
                        "targetRowOffset": row_offset,
                        "targetRowCount": row_count,
                    },
                },
                "configuration": {
                    "s0": _s0_policy(),
                    "perViewEvidence": evidence_policy,
                    "aggregation": diagnostic["aggregationPolicy"],
                    "prior": diagnostic["prior"],
                    "maxS0Comparisons": max_s0_comparisons,
                },
                "runtime": runtime,
                "s0": _summary_record(s0_record, s0_timing),
                "scope": scope_summary,
                "scopeRoleBinding": scope_role_binding,
                "execution": {
                    "recomputedFromOriginalMasks": True,
                    "previousResultAddedAsEvidence": False,
                    "initialDirectEvidence": {
                        "A": initial_a_timing,
                        "B": initial_b_timing,
                    },
                    "finalDirectEvidence": {
                        "A": final_a_timing,
                        "B": final_b_timing,
                    },
                    "cInspection": c_timing,
                    "aggregationElapsedNanoseconds": aggregation_elapsed,
                    "totalElapsedNanoseconds": total_elapsed,
                    "targetGaussianCount": len(target_ids),
                    "renderGaussianCount": len(render_stable_ids),
                    "initialEvidenceWorkingSetToken": initial_ews["evidenceWorkingSetToken"],
                    "finalEvidenceWorkingSetToken": final_ews["evidenceWorkingSetToken"],
                    "s0CandidateCount": candidate_count,
                    "s0EstimatedQuadraticPairs": estimated_comparisons,
                    "s0ActualConnectivityComparisons": actual_s0_comparisons,
                    "host": _resource_record(),
                    "gpuPeakVramBytes": max(
                        value.get("peakVramBytes") or 0
                        for value in (
                            initial_a_timing,
                            initial_b_timing,
                            final_a_timing,
                            final_b_timing,
                            c_timing,
                        )
                    ),
                },
            }
            return result
        finally:
            snapshot.close()


__all__ = [
    "DEFAULT_S0_COMPARISON_BUDGET",
    "BonsaiInputPackage",
    "Issue115BonsaiRunBlocked",
    "load_bonsai_input_package",
    "run_issue_115_bonsai_diagnostics",
]

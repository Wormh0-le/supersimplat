"""Sealed benchmark-only depth-classified Negative Evidence diagnostics.

This module is deliberately outside production Evidence, readiness, Candidate,
and orchestration paths.  It consumes the process-local CWED readout from the
accepted Direct Evidence traversal and emits a separate experimental/reference
sidecar without changing the production single ``negativeMass`` artifact.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from .depth_moment_readout import (
    DepthMomentReadoutRecord,
    projected_row_mapping_digest,
)
from .digests import canonical_json_digest


EXPERIMENTAL_ARTIFACT_KIND = "depth-classified-negative-evidence/experimental-reference"
EXPERIMENTAL_SCHEMA_VERSION = 1
EXPERIMENTAL_RELATION_ID = "front-near-behind/cwed-variance-v1"
EXPERIMENTAL_REPLAY_ARTIFACT_KIND = (
    "depth-classified-negative-evidence-candidate-replay/experimental-reference"
)
_BASELINE_MASS_ATOL = 2e-6
_BASELINE_MASS_RTOL = 1e-5
_MAX_STABLE_GAUSSIAN_ID = (1 << 32) - 1
_RELATION_CONFIG_KEYS = {
    "schemaVersion",
    "relationId",
    "absoluteBand",
    "relativeCwedBand",
    "standardDeviationMultiplier",
}


class DepthClassifiedNegativeEvidenceExperimentError(ValueError):
    """An experimental/reference sidecar input is incomplete or inconsistent."""


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _validated_stable_ids(value: Sequence[int], label: str) -> tuple[int, ...]:
    result = tuple(value)
    if (
        not result
        or any(
            not isinstance(stable_id, int)
            or isinstance(stable_id, bool)
            or stable_id < 0
            or stable_id > _MAX_STABLE_GAUSSIAN_ID
            for stable_id in result
        )
        or len(set(result)) != len(result)
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            f"{label} must contain unique unsigned 32-bit Stable Gaussian IDs."
        )
    return result


def _validated_relation_config(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _RELATION_CONFIG_KEYS:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "depth relation configuration is incomplete or has unknown fields."
        )
    schema_version = value.get("schemaVersion")
    relation_id = value.get("relationId")
    if (
        schema_version != EXPERIMENTAL_SCHEMA_VERSION
        or relation_id != EXPERIMENTAL_RELATION_ID
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "depth relation configuration identity is unsupported."
        )
    coefficients: dict[str, float] = {}
    for name in (
        "absoluteBand",
        "relativeCwedBand",
        "standardDeviationMultiplier",
    ):
        raw = value.get(name)
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
            or float(raw) < 0.0
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                f"depth relation {name} must be finite and non-negative."
            )
        coefficients[name] = float(raw)
    return {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "relationId": relation_id,
        **coefficients,
    }


def projected_depth_rows_digest(value: object) -> str:
    """Digest the exact pinned gsplat projected-depth tensor by row."""

    import hashlib
    import json

    tensor = _tensor(value, label="exact projected depth rows")
    owned = tensor.detach().contiguous().cpu()
    digest = hashlib.sha256(b"exact-pinned-projected-depth-rows/v1")
    digest.update(str(owned.dtype).encode("ascii"))
    digest.update(json.dumps(list(owned.shape)).encode("ascii"))
    digest.update(owned.numpy().tobytes(order="C"))
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True, init=False)
class ProjectedDepthRowsRecord:
    """Owned exact projected depths plus their Stable-ID row identity."""

    stable_ids_by_projected_row: tuple[int, ...]
    projected_row_mapping_digest: str
    tensor_digest: str
    dtype: str
    shape: tuple[int, ...]
    device_type: str
    _rows: Any = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        rows: object,
        stable_ids_by_projected_row: Sequence[int],
    ) -> None:
        import torch

        stable_ids = _validated_stable_ids(
            stable_ids_by_projected_row, "projected-depth row mapping"
        )
        tensor = _tensor(rows, label="exact projected depth rows")
        if (
            tensor.dtype != torch.float32
            or tensor.ndim != 1
            or tensor.numel() != len(stable_ids)
            or not tensor.is_contiguous()
            or not bool(torch.isfinite(tensor).all().item())
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "exact projected depth rows must be finite contiguous float32 [N]."
            )
        owned = tensor.detach().clone().contiguous()
        object.__setattr__(self, "stable_ids_by_projected_row", stable_ids)
        object.__setattr__(
            self,
            "projected_row_mapping_digest",
            projected_row_mapping_digest(stable_ids),
        )
        object.__setattr__(self, "tensor_digest", projected_depth_rows_digest(owned))
        object.__setattr__(self, "dtype", str(owned.dtype))
        object.__setattr__(self, "shape", tuple(int(value) for value in owned.shape))
        object.__setattr__(self, "device_type", owned.device.type)
        object.__setattr__(self, "_rows", owned)

    @property
    def rows(self) -> Any:
        return self._rows.clone()

    def validate(self) -> bool:
        return (
            self.projected_row_mapping_digest
            == projected_row_mapping_digest(self.stable_ids_by_projected_row)
            and self.tensor_digest == projected_depth_rows_digest(self._rows)
            and self.dtype == str(self._rows.dtype)
            and self.shape == tuple(int(value) for value in self._rows.shape)
            and self.device_type == self._rows.device.type
        )


def exact_projected_depth_rows_equal(
    left: ProjectedDepthRowsRecord,
    right: ProjectedDepthRowsRecord,
) -> bool:
    """Return strict same-source equality for two pinned projected-row records."""

    import torch

    return (
        isinstance(left, ProjectedDepthRowsRecord)
        and isinstance(right, ProjectedDepthRowsRecord)
        and left.validate()
        and right.validate()
        and left.stable_ids_by_projected_row == right.stable_ids_by_projected_row
        and left.projected_row_mapping_digest == right.projected_row_mapping_digest
        and left.tensor_digest == right.tensor_digest
        and left.dtype == right.dtype
        and left.shape == right.shape
        and left.device_type == right.device_type
        and torch.equal(left.rows, right.rows)
    )


def _tensor(value: object, *, label: str) -> object:
    try:
        import torch
    except ImportError as error:  # pragma: no cover - locked renderer owns torch
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the depth-classified experiment requires the locked torch runtime."
        ) from error
    if not isinstance(value, torch.Tensor):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            f"{label} must be a torch tensor."
        )
    return value


def build_depth_classified_negative_evidence_sidecar(
    *,
    relation_config: object,
    depth_readout: DepthMomentReadoutRecord,
    projected_depth_rows: ProjectedDepthRowsRecord,
    evidence_stable_ids: Sequence[int],
    contributor_row_ids: object,
    contributor_weights: object,
    negative_pixel_weights: object,
    baseline_negative_mass: object,
    baseline_artifact_digest: str,
    accepted_contribution_sequence_digest: str,
) -> dict[str, object]:
    """Classify baseline Negative Evidence by CWED relation.

    The four output channels are diagnostics.  Their sum must reconstruct the
    unchanged production ``negativeMass`` input within the production mass
    tolerance or the sidecar fails closed.
    """

    import torch

    config = _validated_relation_config(relation_config)
    if (
        not isinstance(projected_depth_rows, ProjectedDepthRowsRecord)
        or not projected_depth_rows.validate()
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experiment requires an immutable exact projected-depth row record."
        )
    projected_stable_ids = projected_depth_rows.stable_ids_by_projected_row
    evidence_ids = _validated_stable_ids(evidence_stable_ids, "Evidence Working Set")
    if (
        not isinstance(depth_readout, DepthMomentReadoutRecord)
        or not depth_readout.validate()
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experiment requires a complete immutable Depth Moment Readout."
        )
    if (
        projected_depth_rows.projected_row_mapping_digest
        != depth_readout.identity.projected_row_mapping_digest
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the projected-row mapping does not match the Depth Moment Readout."
        )
    if (
        not _is_digest(baseline_artifact_digest)
        or not _is_digest(accepted_contribution_sequence_digest)
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the baseline and accepted contribution sequence require SHA-256 identities."
        )

    contributor_ids = _tensor(contributor_row_ids, label="accepted contributor row IDs")
    contribution = _tensor(contributor_weights, label="accepted contributor weights")
    projected_depths = projected_depth_rows.rows
    negative_weights = _tensor(negative_pixel_weights, label="negative pixel weights")
    baseline = _tensor(baseline_negative_mass, label="production baseline negativeMass")
    if (
        contributor_ids.ndim != 3
        or contribution.shape != contributor_ids.shape
        or contributor_ids.dtype not in (torch.int32, torch.int64)
        or not contributor_ids.is_contiguous()
        or not contribution.is_contiguous()
        or not torch.is_floating_point(contribution)
        or tuple(contributor_ids.shape[:2])
        != (depth_readout.identity.height, depth_readout.identity.width)
        or projected_depths.ndim != 1
        or projected_depths.numel() != len(projected_stable_ids)
        or not torch.is_floating_point(projected_depths)
        or negative_weights.numel()
        != depth_readout.identity.width * depth_readout.identity.height
        or not torch.is_floating_point(negative_weights)
        or baseline.ndim != 1
        or baseline.numel() != len(evidence_ids)
        or not torch.is_floating_point(baseline)
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experimental tensors do not match the bound readout dimensions."
        )
    finite_nonnegative = (
        bool(torch.isfinite(contribution).all().item())
        and bool((contribution >= 0).all().item())
        and bool(torch.isfinite(projected_depths).all().item())
        and bool(torch.isfinite(negative_weights).all().item())
        and bool((negative_weights >= 0).all().item())
        and bool(torch.isfinite(baseline).all().item())
        and bool((baseline >= 0).all().item())
    )
    if not finite_nonnegative:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experimental masses, weights, and projected depths must be finite and non-negative."
        )
    if projected_depth_rows_digest(projected_depths) != projected_depth_rows.tensor_digest:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the classified relation did not consume the bound exact pinned projected-depth rows."
        )

    device = contribution.device
    contributor_ids = contributor_ids.to(device=device, dtype=torch.int64)
    projected_depths = projected_depths.to(device=device, dtype=torch.float64)
    negative_weights = negative_weights.reshape(-1).to(
        device=device, dtype=torch.float64
    )
    baseline = baseline.to(device=device, dtype=torch.float64)
    flat_ids = contributor_ids.reshape(-1)
    flat_contribution = contribution.reshape(-1).to(dtype=torch.float64)
    contributor_capacity = int(contributor_ids.shape[-1])
    pixel_indices = torch.arange(
        depth_readout.identity.width * depth_readout.identity.height,
        device=device,
        dtype=torch.int64,
    ).repeat_interleave(contributor_capacity)

    row_to_evidence = torch.full(
        (len(projected_stable_ids),), -1, dtype=torch.int64, device=device
    )
    evidence_index = {stable_id: index for index, stable_id in enumerate(evidence_ids)}
    for row, stable_id in enumerate(projected_stable_ids):
        output_index = evidence_index.get(stable_id)
        if output_index is not None:
            row_to_evidence[row] = output_index

    valid_row = (flat_ids >= 0) & (flat_ids < len(projected_stable_ids))
    safe_rows = flat_ids.clamp(0, len(projected_stable_ids) - 1)
    output_indices = row_to_evidence.index_select(0, safe_rows)
    mass = flat_contribution * negative_weights.index_select(0, pixel_indices)
    active = valid_row & (output_indices >= 0) & (mass > 0.0)

    valid_depth = depth_readout.valid.reshape(-1).to(device=device)
    cwed = depth_readout.cwed.reshape(-1).to(device=device, dtype=torch.float64)
    variance = depth_readout.variance.reshape(-1).to(device=device, dtype=torch.float64)
    per_contribution_valid = valid_depth.index_select(0, pixel_indices)
    contributor_depth = projected_depths.index_select(0, safe_rows)
    pixel_cwed = cwed.index_select(0, pixel_indices)
    pixel_variance = variance.index_select(0, pixel_indices)
    band = torch.maximum(
        torch.full_like(pixel_cwed, float(config["absoluteBand"])),
        torch.maximum(
            pixel_cwed.abs() * float(config["relativeCwedBand"]),
            torch.sqrt(pixel_variance.clamp_min(0.0))
            * float(config["standardDeviationMultiplier"]),
        ),
    )
    delta = contributor_depth - pixel_cwed
    relation_masks = {
        "frontNegativeMass": active & per_contribution_valid & (delta < -band),
        "nearNegativeMass": active & per_contribution_valid & (delta.abs() <= band),
        "behindNegativeMass": active & per_contribution_valid & (delta > band),
        "invalidDepthNegativeMass": active & ~per_contribution_valid,
    }
    channels: dict[str, list[float]] = {}
    write_counts: dict[str, int] = {}
    reconstructed = torch.zeros(len(evidence_ids), dtype=torch.float64, device=device)
    for name, mask in relation_masks.items():
        output = torch.zeros(len(evidence_ids), dtype=torch.float64, device=device)
        output.scatter_add_(0, output_indices[mask], mass[mask])
        reconstructed += output
        channels[name] = output.detach().cpu().tolist()
        write_counts[name] = int(mask.sum().item())

    absolute_error = (reconstructed - baseline).abs()
    tolerance = _BASELINE_MASS_ATOL + _BASELINE_MASS_RTOL * baseline.abs()
    conservation_passed = bool((absolute_error <= tolerance).all().item())
    max_absolute_error = (
        float(absolute_error.max().item()) if absolute_error.numel() else 0.0
    )
    if not conservation_passed:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "classified channels do not reconstruct the unchanged production negativeMass baseline."
        )

    payload: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "artifactKind": EXPERIMENTAL_ARTIFACT_KIND,
        "relationConfig": deepcopy(config),
        "baselineArtifactDigest": baseline_artifact_digest,
        "acceptedContributionSequenceDigest": accepted_contribution_sequence_digest,
        "exactProjectedDepthRowsDigest": projected_depth_rows.tensor_digest,
        "depthMomentReadoutDigest": depth_readout.readout_digest,
        "depthMomentIdentity": depth_readout.identity.identity_payload(),
        "stableGaussianIds": list(evidence_ids),
        **channels,
        "baselineMassConservation": {
            "absoluteTolerance": _BASELINE_MASS_ATOL,
            "relativeTolerance": _BASELINE_MASS_RTOL,
            "maximumAbsoluteError": max_absolute_error,
            "passed": conservation_passed,
        },
        "classificationContributionCounts": {
            **write_counts,
            "total": sum(write_counts.values()),
        },
    }
    return {
        **payload,
        "artifactDigest": canonical_json_digest(payload),
    }


def _validated_sidecar(value: object) -> dict[str, object]:
    expected_keys = {
        "schemaVersion",
        "artifactKind",
        "relationConfig",
        "baselineArtifactDigest",
        "acceptedContributionSequenceDigest",
        "exactProjectedDepthRowsDigest",
        "depthMomentReadoutDigest",
        "depthMomentIdentity",
        "stableGaussianIds",
        "frontNegativeMass",
        "nearNegativeMass",
        "behindNegativeMass",
        "invalidDepthNegativeMass",
        "baselineMassConservation",
        "classificationContributionCounts",
        "artifactDigest",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("schemaVersion") != EXPERIMENTAL_SCHEMA_VERSION
        or value.get("artifactKind") != EXPERIMENTAL_ARTIFACT_KIND
        or not _is_digest(value.get("artifactDigest"))
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the depth-classified sidecar is incomplete or unsupported."
        )
    payload = {
        key: deepcopy(item) for key, item in value.items() if key != "artifactDigest"
    }
    if canonical_json_digest(payload) != value.get("artifactDigest"):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the depth-classified sidecar digest does not match its payload."
        )
    if any(
        not _is_digest(value.get(name))
        for name in (
            "baselineArtifactDigest",
            "acceptedContributionSequenceDigest",
            "exactProjectedDepthRowsDigest",
            "depthMomentReadoutDigest",
        )
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the depth-classified sidecar source identities are invalid."
        )
    stable_ids = _validated_stable_ids(
        value["stableGaussianIds"], "sidecar Evidence Working Set"
    )
    for channel in (
        "frontNegativeMass",
        "nearNegativeMass",
        "behindNegativeMass",
        "invalidDepthNegativeMass",
    ):
        masses = value[channel]
        if (
            not isinstance(masses, list)
            or len(masses) != len(stable_ids)
            or any(
                isinstance(mass, bool)
                or not isinstance(mass, (int, float))
                or not math.isfinite(float(mass))
                or float(mass) < 0.0
                for mass in masses
            )
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                f"the depth-classified sidecar {channel} is invalid."
            )
    conservation = value["baselineMassConservation"]
    if not isinstance(conservation, Mapping) or conservation.get("passed") is not True:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the sidecar did not conserve the production negativeMass baseline."
        )
    counts = value["classificationContributionCounts"]
    count_keys = {
        "frontNegativeMass",
        "nearNegativeMass",
        "behindNegativeMass",
        "invalidDepthNegativeMass",
    }
    if (
        not isinstance(counts, Mapping)
        or set(counts) != {*count_keys, "total"}
        or any(
            isinstance(counts[name], bool)
            or not isinstance(counts[name], int)
            or counts[name] < 0
            for name in count_keys
        )
        or counts.get("total") != sum(int(counts[name]) for name in count_keys)
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the sidecar classification contribution counts are invalid."
        )
    _validated_relation_config(value["relationConfig"])
    return deepcopy(dict(value))


def validate_depth_classified_negative_evidence_sidecar(
    value: object,
) -> dict[str, object]:
    """Validate one persisted classified sidecar before Ground Truth access."""

    return _validated_sidecar(value)


def validate_depth_classified_replay_config(value: object) -> dict[str, object]:
    expected_keys = {
        "schemaVersion",
        "methodId",
        "frontCoefficient",
        "nearCoefficient",
        "behindCoefficient",
        "invalidDepthCoefficient",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experimental replay configuration is incomplete or has unknown fields."
        )
    method_id = value.get("methodId")
    if (
        value.get("schemaVersion") != EXPERIMENTAL_SCHEMA_VERSION
        or not isinstance(method_id, str)
        or not method_id.endswith("/experimental-reference-v1")
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experimental replay method identity is unsupported."
        )
    result: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "methodId": method_id,
    }
    for name in (
        "frontCoefficient",
        "nearCoefficient",
        "behindCoefficient",
        "invalidDepthCoefficient",
    ):
        raw = value.get(name)
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
            or float(raw) < 0.0
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                f"the experimental replay {name} must be finite and non-negative."
            )
        result[name] = float(raw)
    return result


def validate_depth_classified_candidate_replay(value: object) -> dict[str, object]:
    """Validate the complete persisted Candidate replay artifact."""

    expected_keys = {
        "schemaVersion",
        "artifactKind",
        "method",
        "relationConfig",
        "aggregationPolicy",
        "sourceBaselineArtifactDigests",
        "sourceSidecarDigests",
        "aggregationResultDigest",
        "selectedStableGaussianIds",
        "rejectedStableGaussianIds",
        "uncertainStableGaussianIds",
        "candidateInputStableGaussianIds",
        "replayDigest",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("schemaVersion") != EXPERIMENTAL_SCHEMA_VERSION
        or value.get("artifactKind") != EXPERIMENTAL_REPLAY_ARTIFACT_KIND
        or not _is_digest(value.get("replayDigest"))
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the persisted Candidate replay is incomplete or unsupported."
        )
    payload = {
        key: deepcopy(item) for key, item in value.items() if key != "replayDigest"
    }
    if canonical_json_digest(payload) != value["replayDigest"]:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the persisted Candidate replay digest does not match its payload."
        )
    validate_depth_classified_replay_config(value["method"])
    _validated_relation_config(value["relationConfig"])
    if not isinstance(value["aggregationPolicy"], Mapping) or not _is_digest(
        value["aggregationResultDigest"]
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the persisted Candidate replay aggregation identity is invalid."
        )
    for name in ("sourceBaselineArtifactDigests", "sourceSidecarDigests"):
        digests = value[name]
        if (
            not isinstance(digests, list)
            or not digests
            or any(not _is_digest(digest) for digest in digests)
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the persisted Candidate replay source graph is invalid."
            )
    def candidate_ids(name: str, label: str) -> tuple[int, ...]:
        candidate = value[name]
        if candidate == []:
            return ()
        return _validated_stable_ids(candidate, label)

    selected = candidate_ids("selectedStableGaussianIds", "selected Candidate IDs")
    rejected = candidate_ids("rejectedStableGaussianIds", "rejected Candidate IDs")
    uncertain = candidate_ids("uncertainStableGaussianIds", "uncertain Candidate IDs")
    candidate_input = candidate_ids(
        "candidateInputStableGaussianIds", "Candidate input IDs"
    )
    if (
        set(selected) & set(rejected)
        or set(selected) & set(uncertain)
        or set(rejected) & set(uncertain)
        or candidate_input != selected
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the persisted Candidate replay classifications are inconsistent."
        )
    return deepcopy(dict(value))


def replay_depth_classified_negative_evidence(
    *,
    aggregation_input: object,
    sidecars_by_view_id: Mapping[str, object],
    replay_config: object,
    aggregation_policy: object,
) -> dict[str, object]:
    """Replay one coefficient set through the existing reference Candidate policy."""

    from .gaussian_evidence_contract import (
        admit_gaussian_evidence,
        create_gaussian_evidence_artifact,
        is_current_gaussian_evidence_artifact,
    )
    from .reference_gaussian_evidence_aggregation import (
        aggregate_reference_gaussian_evidence,
    )

    config = validate_depth_classified_replay_config(replay_config)
    if (
        not isinstance(aggregation_input, Mapping)
        or not isinstance(aggregation_input.get("views"), list)
        or not isinstance(sidecars_by_view_id, Mapping)
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the experimental Candidate replay input is invalid."
        )
    replay_input = deepcopy(dict(aggregation_input))
    replay_views: list[dict[str, object]] = []
    baseline_digests: list[str] = []
    sidecar_digests: list[str] = []
    relation_configs: list[dict[str, object]] = []
    used_view_ids: set[str] = set()
    for view_record in aggregation_input["views"]:
        if not isinstance(view_record, Mapping) or not isinstance(
            view_record.get("currentInput"), Mapping
        ):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the experimental Candidate replay contains an invalid View."
            )
        current_input = deepcopy(dict(view_record["currentInput"]))
        view = current_input.get("view")
        view_id = view.get("viewId") if isinstance(view, Mapping) else None
        participation = view.get("participation") if isinstance(view, Mapping) else None
        if not isinstance(view_id, str) or view_id in used_view_ids:
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the experimental Candidate replay View identity is invalid."
            )
        used_view_ids.add(view_id)
        if participation == "excluded":
            replay_views.append({"currentInput": current_input})
            continue
        baseline = view_record.get("artifact")
        if not is_current_gaussian_evidence_artifact(baseline, current_input):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the experimental Candidate replay requires current baseline Evidence."
            )
        assert isinstance(baseline, Mapping)
        sidecar = _validated_sidecar(sidecars_by_view_id.get(view_id))
        if sidecar["baselineArtifactDigest"] != baseline.get(
            "artifactDigest"
        ) or sidecar["stableGaussianIds"] != baseline.get("stableGaussianIds"):
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the sidecar does not bind the exact production baseline artifact."
            )
        baseline_digests.append(str(baseline["artifactDigest"]))
        sidecar_digests.append(str(sidecar["artifactDigest"]))
        relation_configs.append(deepcopy(sidecar["relationConfig"]))
        channel_coefficients = (
            ("frontNegativeMass", "frontCoefficient"),
            ("nearNegativeMass", "nearCoefficient"),
            ("behindNegativeMass", "behindCoefficient"),
            ("invalidDepthNegativeMass", "invalidDepthCoefficient"),
        )
        negative_mass = [0.0] * len(sidecar["stableGaussianIds"])
        for channel_name, coefficient_name in channel_coefficients:
            for index, mass in enumerate(sidecar[channel_name]):
                negative_mass[index] += float(mass) * float(config[coefficient_name])

        current_input["evidenceBackendKind"] = "reference-contributor"
        current_input["evidenceBackendId"] = config["methodId"]
        admitted = admit_gaussian_evidence(current_input)
        if admitted.get("status") != "admitted":
            raise DepthClassifiedNegativeEvidenceExperimentError(
                "the experimental replay artifact identity was not admitted."
            )
        masses: dict[str, object] = {
            "positiveMass": list(baseline["positiveMass"]),
            "negativeMass": negative_mass,
            "visibleMass": list(baseline["visibleMass"]),
        }
        if "boundaryMass" in baseline:
            masses["boundaryMass"] = list(baseline["boundaryMass"])
        replay_artifact = create_gaussian_evidence_artifact(
            admitted["admission"], masses
        )
        replay_views.append(
            {"currentInput": current_input, "artifact": replay_artifact}
        )

    included_ids = {
        str(record["currentInput"]["view"]["viewId"])
        for record in aggregation_input["views"]
        if isinstance(record, Mapping)
        and isinstance(record.get("currentInput"), Mapping)
        and isinstance(record["currentInput"].get("view"), Mapping)
        and record["currentInput"]["view"].get("participation") != "excluded"
    }
    if set(sidecars_by_view_id) != included_ids:
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "the replay requires exactly one sidecar per Included View."
        )
    if not relation_configs or any(
        relation != relation_configs[0] for relation in relation_configs[1:]
    ):
        raise DepthClassifiedNegativeEvidenceExperimentError(
            "all replayed Views must use one exact depth relation configuration."
        )
    replay_input["views"] = replay_views
    aggregation = aggregate_reference_gaussian_evidence(
        replay_input, aggregation_policy
    )
    payload: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "artifactKind": EXPERIMENTAL_REPLAY_ARTIFACT_KIND,
        "method": deepcopy(config),
        "relationConfig": relation_configs[0],
        "aggregationPolicy": deepcopy(aggregation_policy),
        "sourceBaselineArtifactDigests": baseline_digests,
        "sourceSidecarDigests": sidecar_digests,
        "aggregationResultDigest": aggregation["resultDigest"],
        "selectedStableGaussianIds": list(aggregation["selectedStableGaussianIds"]),
        "rejectedStableGaussianIds": list(aggregation["rejectedStableGaussianIds"]),
        "uncertainStableGaussianIds": list(aggregation["uncertainStableGaussianIds"]),
        "candidateInputStableGaussianIds": list(
            aggregation["candidateInputStableGaussianIds"]
        ),
    }
    return {**payload, "replayDigest": canonical_json_digest(payload)}


__all__ = [
    "DepthClassifiedNegativeEvidenceExperimentError",
    "ProjectedDepthRowsRecord",
    "EXPERIMENTAL_ARTIFACT_KIND",
    "EXPERIMENTAL_RELATION_ID",
    "EXPERIMENTAL_REPLAY_ARTIFACT_KIND",
    "EXPERIMENTAL_SCHEMA_VERSION",
    "build_depth_classified_negative_evidence_sidecar",
    "projected_depth_rows_digest",
    "replay_depth_classified_negative_evidence",
    "validate_depth_classified_replay_config",
]

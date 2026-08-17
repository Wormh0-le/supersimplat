"""Atomic reference and production Re-Lift orchestration.

The module resolves the exact Included Stable View set, reuses only current
per-view Evidence, computes missing Evidence through an injected producer, and
constructs one Candidate only after every upstream artifact is complete. The
Ticket 21 production path accepts only exact cached Direct Evidence; the
Ticket 15 complete-Contributor path remains a reference boundary.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Callable, Mapping

from .camera_binding import camera_binding_digest
from .direct_gaussian_evidence import (
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)

from .gaussian_evidence_contract import (
    is_current_gaussian_evidence_artifact,
    is_evidence_working_set,
    is_gaussian_evidence_admission_input,
    is_gaussian_evidence_artifact,
)
from .lift_readiness import (
    default_lift_readiness_policy,
    evaluate_lift_readiness,
)
from .reference_candidate_publication import (
    create_production_candidate_artifact,
    create_reference_candidate_artifact,
)
from .reference_gaussian_evidence import default_reference_evidence_policy
from .reference_gaussian_evidence_aggregation import (
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
)


class CandidateReLiftError(ValueError):
    """The bound Re-Lift failed before an atomic Candidate publication."""

    def __init__(self, message: str, *, code: str = "candidateReLiftFailure") -> None:
        super().__init__(message)
        self.code = code


EvidenceProducer = Callable[
    [Mapping[str, object], Mapping[str, object], Mapping[str, object]],
    dict[str, object],
]


def _is_sorted_ids(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(
            isinstance(stable_id, int)
            and not isinstance(stable_id, bool)
            and 0 <= stable_id <= 0xFFFFFFFF
            and (index == 0 or value[index - 1] < stable_id)
            for index, stable_id in enumerate(value)
        )
    )


def _validated_request(value: object) -> dict[str, object]:
    required = {
        "liftAttemptId",
        "sceneId",
        "sceneVersion",
        "renderConfigVersion",
        "requestBinding",
        "targetSplatId",
        "classificationUniverseStableGaussianIds",
        "classificationScopeStableGaussianIds",
        "evidenceWorkingSet",
        "views",
    }
    production = {"productionIdentityDigest", "generationState"}
    if (
        not isinstance(value, dict)
        or set(value) not in (required, required | production)
        or any(
            not isinstance(value.get(key), str) or not str(value[key]).strip()
            for key in (
                "liftAttemptId",
                "sceneId",
                "sceneVersion",
                "renderConfigVersion",
                "targetSplatId",
            )
        )
        or not isinstance(value.get("requestBinding"), dict)
        or not _is_sorted_ids(value.get("classificationUniverseStableGaussianIds"))
        or not _is_sorted_ids(value.get("classificationScopeStableGaussianIds"))
        or not is_evidence_working_set(value.get("evidenceWorkingSet"))
        or not isinstance(value.get("views"), list)
        or not value["views"]
    ):
        raise CandidateReLiftError("AI Select Candidate Re-Lift request is invalid.")
    universe = set(value["classificationUniverseStableGaussianIds"])
    scope = set(value["classificationScopeStableGaussianIds"])
    if not scope.issubset(universe):
        raise CandidateReLiftError(
            "AI Select Candidate Re-Lift classification scope is incompatible."
        )
    return deepcopy(value)


def _validated_production_request(value: object) -> dict[str, object]:
    result = _validated_request(value)
    if (
        not isinstance(result.get("productionIdentityDigest"), str)
        or not str(result["productionIdentityDigest"]).startswith("sha256:")
        or len(str(result["productionIdentityDigest"])) != 71
        or any(
            character not in "0123456789abcdef"
            for character in str(result["productionIdentityDigest"])[7:]
        )
        or result.get("generationState")
        not in {"active", "stopped", "complete", "unavailable"}
    ):
        raise CandidateReLiftError(
            "AI Select production Candidate Re-Lift identity/readiness input is invalid."
        )
    return result


def produce_reference_candidate_re_lift(
    request: object,
    produce_evidence: EvidenceProducer,
) -> dict[str, object]:
    """Resolve current per-view Evidence and return one all-or-nothing result."""

    value = _validated_request(request)
    views = value["views"]
    assert isinstance(views, list)
    seen: set[str] = set()
    aggregation_views: list[dict[str, object]] = []
    published_evidence: list[dict[str, object]] = []
    for raw_record in views:
        if (
            not isinstance(raw_record, dict)
            or set(raw_record) - {
                "currentInput",
                "cameraBinding",
                "stableMask",
                "cachedArtifact",
            }
            or set(raw_record) < {"currentInput", "cameraBinding", "stableMask"}
            or not is_gaussian_evidence_admission_input(
                raw_record.get("currentInput")
            )
            or not isinstance(raw_record.get("cameraBinding"), dict)
            or not isinstance(raw_record.get("stableMask"), dict)
        ):
            raise CandidateReLiftError(
                "AI Select Candidate Re-Lift contains an invalid View input."
            )
        current_input = raw_record["currentInput"]
        assert isinstance(current_input, dict)
        current_view = current_input["view"]
        assert isinstance(current_view, dict)
        view_id = current_view["viewId"]
        assert isinstance(view_id, str)
        if (
            view_id in seen
            or current_input["requestBinding"] != value["requestBinding"]
            or current_input["targetSplatId"] != value["targetSplatId"]
            or current_input["evidenceWorkingSet"] != value["evidenceWorkingSet"]
        ):
            raise CandidateReLiftError(
                f"AI Select Candidate Re-Lift View {view_id} has incompatible identity."
            )
        try:
            supplied_camera_digest = camera_binding_digest(
                raw_record["cameraBinding"]
            )
        except (TypeError, ValueError) as error:
            raise CandidateReLiftError(
                f"AI Select Candidate Re-Lift View {view_id} has an invalid CameraBinding."
            ) from error
        stable_mask = raw_record["stableMask"]
        assert isinstance(stable_mask, dict)
        if (
            supplied_camera_digest != current_view["cameraBindingDigest"]
            or stable_mask.get("digest") != current_view["stableMaskDigest"]
        ):
            raise CandidateReLiftError(
                f"AI Select Candidate Re-Lift View {view_id} has incompatible Camera/Mask identity."
            )
        policy = default_reference_evidence_policy()
        if (
            current_input["evidencePolicyDigest"]
            != policy["evidencePolicyDigest"]
            or current_input["rasterImplementationId"]
            != DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID
            or current_input["evidenceBackendKind"]
            != "reference-contributor"
            or current_input["evidenceBackendId"]
            != "complete-contributor/reference-v1"
            or current_input["runtimeBuildId"]
            != DIRECT_EVIDENCE_RUNTIME_BUILD_ID
        ):
            raise CandidateReLiftError(
                f"AI Select Candidate Re-Lift View {view_id} has an unsupported reference Evidence identity."
            )
        seen.add(view_id)
        if current_view["participation"] == "excluded":
            aggregation_views.append({"currentInput": current_input})
            continue

        cached = raw_record.get("cachedArtifact")
        reused = is_current_gaussian_evidence_artifact(cached, current_input)
        if reused:
            artifact = cached
        else:
            try:
                artifact = produce_evidence(
                    current_input,
                    raw_record["stableMask"],
                    raw_record["cameraBinding"],
                )
            except Exception as error:
                error_code = getattr(error, "code", None)
                cause_code = getattr(error, "cause_code", None)
                detail = str(error).strip()
                if (
                    isinstance(cause_code, str)
                    and cause_code
                    and cause_code not in detail
                ):
                    detail = f"{detail} ({cause_code})".strip()
                raise CandidateReLiftError(
                    f"AI Select Candidate Re-Lift Evidence failed for View {view_id}."
                    + (f" {detail}" if detail else ""),
                    code=(
                        error_code
                        if isinstance(error_code, str) and error_code
                        else "candidateReLiftFailure"
                    ),
                ) from error
        if (
            not is_gaussian_evidence_artifact(artifact)
            or not is_current_gaussian_evidence_artifact(artifact, current_input)
        ):
            raise CandidateReLiftError(
                f"AI Select Candidate Re-Lift Evidence for View {view_id} is incomplete or stale."
            )
        assert isinstance(artifact, dict)
        aggregation_views.append(
            {"currentInput": current_input, "artifact": artifact}
        )
        published_evidence.append(
            {"viewId": view_id, "reused": reused, "artifact": artifact}
        )

    aggregation_views.sort(
        key=lambda item: str(item["currentInput"]["view"]["viewId"]).encode("utf-8")
    )
    published_evidence.sort(key=lambda item: str(item["viewId"]).encode("utf-8"))
    if not published_evidence:
        raise CandidateReLiftError(
            "AI Select Candidate Re-Lift requires at least one Included Stable View."
        )
    aggregation_input = {
        "requestBinding": value["requestBinding"],
        "targetSplatId": value["targetSplatId"],
        "classificationUniverseStableGaussianIds": value[
            "classificationUniverseStableGaussianIds"
        ],
        "classificationScopeStableGaussianIds": value[
            "classificationScopeStableGaussianIds"
        ],
        "evidenceWorkingSet": value["evidenceWorkingSet"],
        "views": aggregation_views,
    }
    try:
        aggregation_result = aggregate_reference_gaussian_evidence(
            aggregation_input,
            default_reference_aggregation_policy(),
        )
        candidate = create_reference_candidate_artifact(
            aggregation_input,
            aggregation_result,
        )
    except Exception as error:
        raise CandidateReLiftError(
            "AI Select Candidate Re-Lift aggregation failed closed."
        ) from error
    return {
        "status": "complete",
        "liftAttemptId": value["liftAttemptId"],
        "requestBinding": value["requestBinding"],
        "targetSplatId": value["targetSplatId"],
        "evidence": published_evidence,
        "candidate": candidate,
    }


def produce_production_candidate_re_lift(
    request: object,
) -> dict[str, object]:
    """Atomically aggregate exact cached production Direct Evidence."""

    value = _validated_production_request(request)
    views = value["views"]
    assert isinstance(views, list)
    seen: set[str] = set()
    aggregation_views: list[dict[str, object]] = []
    published_evidence: list[dict[str, object]] = []
    observation_views: list[dict[str, object]] = []
    policy = default_reference_evidence_policy()
    for raw_record in views:
        if (
            not isinstance(raw_record, dict)
            or set(raw_record) - {
                "currentInput",
                "cameraBinding",
                "stableMask",
                "cachedArtifact",
            }
            or set(raw_record) < {"currentInput", "cameraBinding", "stableMask"}
            or not is_gaussian_evidence_admission_input(
                raw_record.get("currentInput")
            )
            or not isinstance(raw_record.get("cameraBinding"), dict)
            or not isinstance(raw_record.get("stableMask"), dict)
        ):
            raise CandidateReLiftError(
                "AI Select production Candidate Re-Lift contains an invalid View input."
            )
        current_input = raw_record["currentInput"]
        assert isinstance(current_input, dict)
        current_view = current_input["view"]
        assert isinstance(current_view, dict)
        view_id = current_view["viewId"]
        assert isinstance(view_id, str)
        if (
            view_id in seen
            or current_input["requestBinding"] != value["requestBinding"]
            or current_input["targetSplatId"] != value["targetSplatId"]
            or current_input["evidenceWorkingSet"] != value["evidenceWorkingSet"]
        ):
            raise CandidateReLiftError(
                f"AI Select production Candidate Re-Lift View {view_id} has incompatible identity."
            )
        try:
            supplied_camera_digest = camera_binding_digest(
                raw_record["cameraBinding"]
            )
        except (TypeError, ValueError) as error:
            raise CandidateReLiftError(
                f"AI Select production Candidate Re-Lift View {view_id} has an invalid CameraBinding."
            ) from error
        stable_mask = raw_record["stableMask"]
        assert isinstance(stable_mask, dict)
        if (
            supplied_camera_digest != current_view["cameraBindingDigest"]
            or stable_mask.get("digest") != current_view["stableMaskDigest"]
        ):
            raise CandidateReLiftError(
                f"AI Select production Candidate Re-Lift View {view_id} has incompatible Camera/Mask identity."
            )
        if (
            current_input["evidencePolicyDigest"]
            != policy["evidencePolicyDigest"]
            or current_input["rasterImplementationId"]
            != DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID
            or current_input["evidenceBackendKind"] != "production-direct"
            or current_input["evidenceBackendId"] != "global-atomic/direct-v1"
            or current_input["runtimeBuildId"] != DIRECT_EVIDENCE_RUNTIME_BUILD_ID
        ):
            raise CandidateReLiftError(
                f"AI Select production Candidate Re-Lift View {view_id} has an unsupported Direct Evidence identity."
            )
        seen.add(view_id)
        if current_view["participation"] == "excluded":
            aggregation_views.append({"currentInput": current_input})
            continue
        artifact = raw_record.get("cachedArtifact")
        if not is_current_gaussian_evidence_artifact(artifact, current_input):
            raise CandidateReLiftError(
                f"AI Select production Candidate Re-Lift Evidence for View {view_id} is incomplete or stale."
            )
        assert isinstance(artifact, dict)
        aggregation_views.append(
            {"currentInput": current_input, "artifact": artifact}
        )
        observation_views.append(
            {
                "viewId": view_id,
                "cameraBinding": deepcopy(raw_record["cameraBinding"]),
            }
        )
        published_evidence.append(
            {"viewId": view_id, "reused": True, "artifact": artifact}
        )

    aggregation_views.sort(
        key=lambda item: str(item["currentInput"]["view"]["viewId"]).encode(
            "utf-8"
        )
    )
    published_evidence.sort(key=lambda item: str(item["viewId"]).encode("utf-8"))
    if not published_evidence:
        raise CandidateReLiftError(
            "AI Select production Candidate Re-Lift requires at least one Included Stable View."
        )
    aggregation_input = {
        "requestBinding": value["requestBinding"],
        "targetSplatId": value["targetSplatId"],
        "classificationUniverseStableGaussianIds": value[
            "classificationUniverseStableGaussianIds"
        ],
        "classificationScopeStableGaussianIds": value[
            "classificationScopeStableGaussianIds"
        ],
        "evidenceWorkingSet": value["evidenceWorkingSet"],
        "views": aggregation_views,
    }
    try:
        aggregation_result = aggregate_reference_gaussian_evidence(
            aggregation_input,
            default_reference_aggregation_policy(),
        )
        lift_readiness = evaluate_lift_readiness(
            {
                "requestBinding": value["requestBinding"],
                "targetSplatId": value["targetSplatId"],
                "evidenceWorkingSet": value["evidenceWorkingSet"],
                "aggregationResult": aggregation_result,
                "observationViews": observation_views,
                "generationState": value["generationState"],
                "lowCostSupportDiagnostic": None,
            },
            default_lift_readiness_policy(),
        )
        response: dict[str, object] = {
            "status": (
                "not-ready"
                if lift_readiness["readiness"] == "not-ready"
                else "complete"
            ),
            "liftAttemptId": value["liftAttemptId"],
            "requestBinding": value["requestBinding"],
            "targetSplatId": value["targetSplatId"],
            "evidence": published_evidence,
            "liftReadiness": lift_readiness,
        }
        if lift_readiness["readiness"] == "not-ready":
            return response
        candidate = create_production_candidate_artifact(
            aggregation_input,
            aggregation_result,
            production_identity_digest=str(value["productionIdentityDigest"]),
        )
    except Exception as error:
        raise CandidateReLiftError(
            "AI Select production Candidate Re-Lift aggregation failed closed."
        ) from error
    response["candidate"] = candidate
    return response


def validate_candidate_re_lift_snapshot_binding(
    request: object,
    *,
    scene_content_digest: str,
    scene_stable_ids: list[int],
) -> None:
    """Bind every reuse and recompute path to one registered packed Scene."""

    value = _validated_request(request)
    universe = value["classificationUniverseStableGaussianIds"]
    views = value["views"]
    assert isinstance(universe, list)
    assert isinstance(views, list)
    if universe != scene_stable_ids:
        raise CandidateReLiftError(
            "AI Select Candidate Re-Lift Scene Snapshot Stable IDs are stale."
        )
    for record in views:
        if not isinstance(record, dict):
            raise CandidateReLiftError(
                "AI Select Candidate Re-Lift Scene Snapshot View is invalid."
            )
        current_input = record.get("currentInput")
        if not isinstance(current_input, dict):
            raise CandidateReLiftError(
                "AI Select Candidate Re-Lift Scene Snapshot View is invalid."
            )
        render_working_set = current_input.get("renderWorkingSet")
        request_binding = value["requestBinding"]
        assert isinstance(request_binding, dict)
        if (
            not isinstance(render_working_set, dict)
            or render_working_set.get("renderWorkingSetToken")
            != scene_content_digest
            or render_working_set.get("stableGaussianIds") != scene_stable_ids
            or render_working_set.get("completeness") != "complete"
            or render_working_set.get("targetSplatId")
            != value["targetSplatId"]
            or render_working_set.get("dependencyToken")
            != request_binding.get("dependencyToken")
        ):
            raise CandidateReLiftError(
                "AI Select Candidate Re-Lift Scene Snapshot binding is stale."
            )


def validate_production_candidate_re_lift_snapshot_binding(
    request: object,
    *,
    scene_stable_ids: list[int],
    target_stable_ids: list[int],
) -> None:
    """Verify target identity without conflating render-only occluders."""

    value = _validated_request(request)
    universe = value["classificationUniverseStableGaussianIds"]
    views = value["views"]
    assert isinstance(universe, list)
    assert isinstance(views, list)
    if universe != target_stable_ids:
        raise CandidateReLiftError(
            "AI Select production Candidate Re-Lift target Stable IDs are stale."
        )
    scene_id_set = set(scene_stable_ids)
    request_binding = value["requestBinding"]
    assert isinstance(request_binding, dict)
    for record in views:
        current_input = record.get("currentInput") if isinstance(record, dict) else None
        render_working_set = (
            current_input.get("renderWorkingSet")
            if isinstance(current_input, dict)
            else None
        )
        render_ids = (
            render_working_set.get("stableGaussianIds")
            if isinstance(render_working_set, dict)
            else None
        )
        if (
            not isinstance(render_working_set, dict)
            or not isinstance(render_ids, list)
            or not render_ids
            or not set(render_ids).issubset(scene_id_set)
            or render_working_set.get("completeness") != "complete"
            or render_working_set.get("targetSplatId")
            != value["targetSplatId"]
            or render_working_set.get("dependencyToken")
            != request_binding.get("dependencyToken")
        ):
            raise CandidateReLiftError(
                "AI Select production Candidate Re-Lift Scene Snapshot binding is stale."
            )

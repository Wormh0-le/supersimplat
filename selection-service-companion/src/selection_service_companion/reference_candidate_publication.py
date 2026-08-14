"""Atomic Ticket 14D reference Candidate construction and quality scoring.

The Companion constructs a complete, identity-bound reference artifact. The
browser remains the owner of target-local publication, visualization and any
future native application. This module never mutates editor selection state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Final, Mapping

from .digests import canonical_json_digest
from .reference_gaussian_evidence_aggregation import (
    ReferenceGaussianEvidenceAggregationError,
    aggregate_reference_gaussian_evidence,
    is_reference_gaussian_evidence_aggregation_result,
)


REFERENCE_CANDIDATE_SCHEMA_VERSION: Final = 2
REFERENCE_CANDIDATE_PUBLICATION_KIND: Final = "reference-pre-production"
_DIGEST_PREFIX: Final = "sha256:"
_DIGEST_LENGTH: Final = len(_DIGEST_PREFIX) + 64
_MAX_STABLE_GAUSSIAN_ID: Final = (1 << 32) - 1


class ReferenceCandidatePublicationError(ValueError):
    """A reference Candidate failed complete, current publication validation."""


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_LENGTH
        and value.startswith(_DIGEST_PREFIX)
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _is_non_empty_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(not 0xD800 <= ord(character) <= 0xDFFF for character in value)
    )


def _utf8_sort_key(value: str) -> bytes:
    return value.encode("utf-8")


def _is_stable_id_array(value: object, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(
            isinstance(stable_id, int)
            and not isinstance(stable_id, bool)
            and 0 <= stable_id <= _MAX_STABLE_GAUSSIAN_ID
            for stable_id in value
        )
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _stable_input_set(
    aggregation_input: Mapping[str, object],
) -> list[dict[str, object]]:
    records = aggregation_input.get("views")
    if not isinstance(records, list):
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate requires current aggregation inputs."
        )
    stable_inputs: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ReferenceCandidatePublicationError(
                "AI Select Candidate requires current aggregation inputs."
            )
        current_input = record.get("currentInput")
        view = current_input.get("view") if isinstance(current_input, dict) else None
        if not isinstance(view, dict):
            raise ReferenceCandidatePublicationError(
                "AI Select Candidate requires current aggregation inputs."
            )
        participation = view.get("participation")
        artifact = record.get("artifact")
        evidence_artifact_digest: object = None
        if participation == "included":
            evidence_artifact_digest = (
                artifact.get("artifactDigest") if isinstance(artifact, dict) else None
            )
        stable_inputs.append(
            {
                "viewId": view.get("viewId"),
                "participation": participation,
                "stableMaskDigest": view.get("stableMaskDigest"),
                "evidenceArtifactDigest": evidence_artifact_digest,
            }
        )
    stable_inputs.sort(key=lambda item: _utf8_sort_key(str(item["viewId"])))
    if not _is_stable_input_set(stable_inputs):
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate requires current aggregation inputs."
        )
    return stable_inputs


def _is_stable_input_set(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    view_ids: list[str] = []
    for record in value:
        if (
            not isinstance(record, dict)
            or set(record)
            != {
                "viewId",
                "participation",
                "stableMaskDigest",
                "evidenceArtifactDigest",
            }
            or not _is_non_empty_string(record.get("viewId"))
            or record.get("participation") not in {"included", "excluded"}
        ):
            return False
        stable_mask_digest = record.get("stableMaskDigest")
        evidence_digest = record.get("evidenceArtifactDigest")
        if record["participation"] == "included":
            if not _is_digest(stable_mask_digest) or not _is_digest(
                evidence_digest
            ):
                return False
        elif (
            stable_mask_digest is not None
            and not _is_digest(stable_mask_digest)
        ) or evidence_digest is not None:
            return False
        view_ids.append(str(record["viewId"]))
    return view_ids == sorted(set(view_ids), key=_utf8_sort_key)


def _publication_binding(
    aggregation_input: Mapping[str, object],
    aggregation_result: Mapping[str, object],
) -> dict[str, object]:
    stable_inputs = _stable_input_set(aggregation_input)
    backend_identities = aggregation_result.get("referenceBackendIdentities")
    if not isinstance(backend_identities, list) or len(backend_identities) != 1:
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate requires one compatible reference backend identity."
        )
    binding = {
        "requestBinding": deepcopy(aggregation_result["requestBinding"]),
        "targetSplatId": aggregation_result["targetSplatId"],
        "stableInputSetDigest": canonical_json_digest(
            {"stableInputs": stable_inputs}
        ),
        "aggregationPolicyDigest": aggregation_result[
            "aggregationPolicyDigest"
        ],
        "sourceEvidencePolicyDigest": aggregation_result[
            "sourceEvidencePolicyDigest"
        ],
        "evidenceWorkingSetToken": aggregation_result[
            "evidenceWorkingSetToken"
        ],
        "evidenceArtifactSetDigest": aggregation_result[
            "evidenceArtifactSetDigest"
        ],
        "referenceBackendIdentity": deepcopy(backend_identities[0]),
    }
    if not _is_publication_binding(binding):
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate publication binding is invalid."
        )
    return binding


def _is_request_binding(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "targetContextId",
        "contextRevision",
        "dependencyToken",
    }:
        return False
    dependency = value.get("dependencyToken")
    return (
        _is_non_empty_string(value.get("targetContextId"))
        and isinstance(value.get("contextRevision"), int)
        and not isinstance(value.get("contextRevision"), bool)
        and int(value["contextRevision"]) >= 0
        and isinstance(dependency, dict)
        and set(dependency)
        == {
            "splatId",
            "renderStateToken",
            "geometryToken",
            "gaussianIdentityToken",
            "worldTransformToken",
        }
        and all(_is_non_empty_string(item) for item in dependency.values())
    )


def _is_backend_identity(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "rasterImplementationId",
            "evidenceBackendKind",
            "evidenceBackendId",
            "runtimeBuildId",
        }
        and value.get("evidenceBackendKind")
        in {"reference-contributor", "reference-autograd"}
        and all(
            _is_non_empty_string(value.get(key))
            for key in (
                "rasterImplementationId",
                "evidenceBackendId",
                "runtimeBuildId",
            )
        )
    )


def _is_publication_binding(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "requestBinding",
            "targetSplatId",
            "stableInputSetDigest",
            "aggregationPolicyDigest",
            "sourceEvidencePolicyDigest",
            "evidenceWorkingSetToken",
            "evidenceArtifactSetDigest",
            "referenceBackendIdentity",
        }
        and _is_request_binding(value.get("requestBinding"))
        and _is_non_empty_string(value.get("targetSplatId"))
        and all(
            _is_digest(value.get(key))
            for key in (
                "stableInputSetDigest",
                "aggregationPolicyDigest",
                "sourceEvidencePolicyDigest",
                "evidenceWorkingSetToken",
                "evidenceArtifactSetDigest",
            )
        )
        and _is_backend_identity(value.get("referenceBackendIdentity"))
    )


def create_reference_candidate_artifact(
    aggregation_input: object,
    aggregation_result: object,
) -> dict[str, object]:
    """Build one complete reference Candidate after exact-current revalidation."""

    if (
        not isinstance(aggregation_input, dict)
        or not isinstance(aggregation_result, dict)
        or not is_reference_gaussian_evidence_aggregation_result(
            aggregation_result
        )
    ):
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate requires a complete compatible aggregation result."
        )
    try:
        expected_result = aggregate_reference_gaussian_evidence(
            aggregation_input,
            aggregation_result["aggregationPolicy"],
        )
    except (ReferenceGaussianEvidenceAggregationError, TypeError, ValueError) as error:
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate does not match current aggregation inputs."
        ) from error
    if expected_result != aggregation_result:
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate does not match current aggregation inputs."
        )

    binding = _publication_binding(aggregation_input, aggregation_result)
    payload: dict[str, object] = {
        "schemaVersion": REFERENCE_CANDIDATE_SCHEMA_VERSION,
        "publicationKind": REFERENCE_CANDIDATE_PUBLICATION_KIND,
        "productionReadiness": "reference-only",
        "publicationBinding": binding,
        "sourceAggregationResultDigest": aggregation_result["resultDigest"],
        "candidate": {
            "selectedStableGaussianIds": list(
                aggregation_result["candidateInputStableGaussianIds"]
            )
        },
        "uncertain": {
            "stableGaussianIds": list(
                aggregation_result["uncertainStableGaussianIds"]
            )
        },
    }
    result = {
        **payload,
        "candidateDigest": canonical_json_digest(payload),
    }
    if not is_reference_candidate_artifact(result):
        raise ReferenceCandidatePublicationError(
            "AI Select Candidate construction did not produce a complete artifact."
        )
    return result


def is_reference_candidate_artifact(value: object) -> bool:
    """Validate the self-contained browser publication boundary."""

    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schemaVersion",
            "publicationKind",
            "productionReadiness",
            "publicationBinding",
            "sourceAggregationResultDigest",
            "candidate",
            "uncertain",
            "candidateDigest",
        }
        or value.get("schemaVersion") != REFERENCE_CANDIDATE_SCHEMA_VERSION
        or value.get("publicationKind")
        != REFERENCE_CANDIDATE_PUBLICATION_KIND
        or value.get("productionReadiness") != "reference-only"
        or not _is_publication_binding(value.get("publicationBinding"))
        or not _is_digest(value.get("sourceAggregationResultDigest"))
        or not _is_digest(value.get("candidateDigest"))
    ):
        return False
    candidate = value.get("candidate")
    uncertain = value.get("uncertain")
    if (
        not isinstance(candidate, dict)
        or set(candidate) != {"selectedStableGaussianIds"}
        or not isinstance(uncertain, dict)
        or set(uncertain) != {"stableGaussianIds"}
        or not _is_stable_id_array(candidate["selectedStableGaussianIds"])
        or not _is_stable_id_array(uncertain["stableGaussianIds"])
        or set(candidate["selectedStableGaussianIds"])
        & set(uncertain["stableGaussianIds"])
    ):
        return False
    payload = {key: item for key, item in value.items() if key != "candidateDigest"}
    try:
        return value["candidateDigest"] == canonical_json_digest(payload)
    except (TypeError, ValueError):
        return False


__all__ = [
    "REFERENCE_CANDIDATE_PUBLICATION_KIND",
    "REFERENCE_CANDIDATE_SCHEMA_VERSION",
    "ReferenceCandidatePublicationError",
    "create_reference_candidate_artifact",
    "is_reference_candidate_artifact",
]

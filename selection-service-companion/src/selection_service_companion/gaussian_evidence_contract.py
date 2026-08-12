"""Ticket 14A fail-closed Evidence admission and Working Set contracts.

This module deliberately defines only the reference-artifact boundary. It
does not calculate P/N/V (Ticket 14B), aggregate them (14C), publish a
Candidate (14D), or represent Ticket 20's production same-decision path.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Mapping


GAUSSIAN_EVIDENCE_ARTIFACT_SCHEMA_VERSION = 1
EVIDENCE_WORKING_SET_SCHEMA_VERSION = 1
_DIGEST_PREFIX = 'sha256:'
_DIGEST_LENGTH = len(_DIGEST_PREFIX) + 64
_MAX_SAFE_INTEGER = (1 << 53) - 1
_MAX_STABLE_GAUSSIAN_ID = (1 << 32) - 1
_REFERENCE_EVIDENCE_BACKEND_KINDS = {
    'reference-contributor',
    'reference-autograd',
}
_KNOWN_EVIDENCE_BACKEND_KINDS = {
    *_REFERENCE_EVIDENCE_BACKEND_KINDS,
    'production-direct',
}


class GaussianEvidenceContractError(ValueError):
    """A Ticket 14A Evidence boundary failed structural validation."""


def _is_record(value: object) -> bool:
    return isinstance(value, dict)


def _is_non_empty_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(not 0xD800 <= ord(character) <= 0xDFFF for character in value)
    )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_LENGTH
        and value.startswith(_DIGEST_PREFIX)
        and all(character in '0123456789abcdef' for character in value[7:])
    )


def _is_nonnegative_safe_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_SAFE_INTEGER
    )


def _is_stable_gaussian_id(value: object) -> bool:
    return _is_nonnegative_safe_integer(value) and value <= _MAX_STABLE_GAUSSIAN_ID


def _is_sorted_stable_gaussian_ids(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_is_stable_gaussian_id(stable_id) for stable_id in value)
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _copy_stable_gaussian_ids(
    value: object,
    *,
    allow_empty: bool = False,
) -> list[int]:
    if not _is_sorted_stable_gaussian_ids(value, allow_empty=allow_empty):
        raise GaussianEvidenceContractError(
            'AI Select Evidence requires sorted unique uint32 Stable Gaussian IDs.'
        )
    return list(value)


def _has_exact_keys(
    value: Mapping[str, object],
    required: set[str],
    optional: set[str] | None = None,
) -> bool:
    allowed = required | (optional or set())
    return required.issubset(value) and set(value).issubset(allowed)


def _canonical_json(value: object) -> str:
    """Match browser IEEE-754 artifact-number canonicalization exactly."""

    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            raise GaussianEvidenceContractError(
                'AI Select Evidence artifact numbers must be finite.'
            )
        return f'n{struct.pack(">d", number).hex()}'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, list):
        return '[' + ','.join(_canonical_json(entry) for entry in value) + ']'
    if isinstance(value, dict):
        entries: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise GaussianEvidenceContractError(
                    'AI Select Evidence artifact keys must be strings.'
                )
            entries.append(
                f'{json.dumps(key, ensure_ascii=False)}:{_canonical_json(value[key])}'
            )
        return '{' + ','.join(entries) + '}'
    raise GaussianEvidenceContractError(
        f'AI Select Evidence artifact contains unsupported data: {type(value).__name__}.'
    )


def _canonical_digest(value: object) -> str:
    return 'sha256:' + hashlib.sha256(
        _canonical_json(value).encode('utf-8')
    ).hexdigest()


def _union_stable_gaussian_ids(
    left: list[int],
    right: list[int],
) -> list[int]:
    result: list[int] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) or right_index < len(right):
        left_value = left[left_index] if left_index < len(left) else None
        right_value = right[right_index] if right_index < len(right) else None
        if right_value is None or (
            left_value is not None and left_value < right_value
        ):
            assert left_value is not None
            result.append(left_value)
            left_index += 1
        elif left_value is None or right_value < left_value:
            result.append(right_value)
            right_index += 1
        else:
            assert left_value is not None
            result.append(left_value)
            left_index += 1
            right_index += 1
    return result


def _stable_gaussian_ids_intersect(left: list[int], right: list[int]) -> bool:
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            return True
        if left[left_index] < right[right_index]:
            left_index += 1
        else:
            right_index += 1
    return False


def _stable_gaussian_ids_are_subset_of(
    subset: list[int],
    superset: list[int],
) -> bool:
    subset_index = 0
    superset_index = 0
    while subset_index < len(subset) and superset_index < len(superset):
        if subset[subset_index] == superset[superset_index]:
            subset_index += 1
            superset_index += 1
        elif subset[subset_index] > superset[superset_index]:
            superset_index += 1
        else:
            return False
    return subset_index == len(subset)


def _is_target_dependency_token(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(
            value,
            {
                'splatId',
                'renderStateToken',
                'geometryToken',
                'gaussianIdentityToken',
                'worldTransformToken',
            },
        )
        and all(_is_non_empty_string(value[key]) for key in value)
    )


def _copy_target_dependency_token(value: Mapping[str, object]) -> dict[str, object]:
    return {
        'splatId': value['splatId'],
        'renderStateToken': value['renderStateToken'],
        'geometryToken': value['geometryToken'],
        'gaussianIdentityToken': value['gaussianIdentityToken'],
        'worldTransformToken': value['worldTransformToken'],
    }


def _are_target_dependency_tokens_equal(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> bool:
    return all(left[key] == right[key] for key in (
        'splatId',
        'renderStateToken',
        'geometryToken',
        'gaussianIdentityToken',
        'worldTransformToken',
    ))


def _is_request_binding(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {
            'targetContextId',
            'contextRevision',
            'dependencyToken',
        })
        and _is_non_empty_string(value['targetContextId'])
        and _is_nonnegative_safe_integer(value['contextRevision'])
        and _is_target_dependency_token(value['dependencyToken'])
    )


def _copy_request_binding(value: Mapping[str, object]) -> dict[str, object]:
    dependency_token = value['dependencyToken']
    assert isinstance(dependency_token, dict)
    return {
        'targetContextId': value['targetContextId'],
        'contextRevision': value['contextRevision'],
        'dependencyToken': _copy_target_dependency_token(dependency_token),
    }


def _evidence_working_set_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        'schemaVersion': EVIDENCE_WORKING_SET_SCHEMA_VERSION,
        'targetSplatId': value['targetSplatId'],
        'coreTargetStableIds': list(value['coreTargetStableIds']),
        'contextStableGaussianIds': list(value['contextStableGaussianIds']),
    }


def _evidence_working_set_token(value: Mapping[str, object]) -> str:
    return _canonical_digest(_evidence_working_set_payload(value))


def _is_evidence_working_set_input(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {'targetSplatId', 'coreTargetStableIds', 'contextStableGaussianIds'},
        {'targetGeometryHintSeedDigest'},
    ):
        return False
    if (
        not _is_non_empty_string(value['targetSplatId'])
        or not _is_sorted_stable_gaussian_ids(
            value['coreTargetStableIds'], allow_empty=True
        )
        or not _is_sorted_stable_gaussian_ids(
            value['contextStableGaussianIds'], allow_empty=True
        )
    ):
        return False
    core = list(value['coreTargetStableIds'])
    context = list(value['contextStableGaussianIds'])
    return (
        bool(core or context)
        and not _stable_gaussian_ids_intersect(core, context)
        and (
            'targetGeometryHintSeedDigest' not in value
            or _is_digest(value['targetGeometryHintSeedDigest'])
        )
    )


def create_evidence_working_set(payload: Mapping[str, object]) -> dict[str, object]:
    """Create an immutable-by-convention Core + Context write-set record."""

    candidate = dict(payload)
    if not _is_evidence_working_set_input(candidate):
        raise GaussianEvidenceContractError(
            'AI Select Evidence Working Set requires disjoint sorted Core Target and Context Stable Gaussian IDs.'
        )
    core = _copy_stable_gaussian_ids(
        candidate['coreTargetStableIds'], allow_empty=True
    )
    context = _copy_stable_gaussian_ids(
        candidate['contextStableGaussianIds'], allow_empty=True
    )
    result: dict[str, object] = {
        'schemaVersion': EVIDENCE_WORKING_SET_SCHEMA_VERSION,
        'targetSplatId': candidate['targetSplatId'],
        'coreTargetStableIds': core,
        'contextStableGaussianIds': context,
        'stableGaussianIds': _union_stable_gaussian_ids(core, context),
        'evidenceWorkingSetToken': _evidence_working_set_token({
            'targetSplatId': candidate['targetSplatId'],
            'coreTargetStableIds': core,
            'contextStableGaussianIds': context,
        }),
    }
    if 'targetGeometryHintSeedDigest' in candidate:
        result['targetGeometryHintSeedDigest'] = candidate[
            'targetGeometryHintSeedDigest'
        ]
    return result


def is_evidence_working_set(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'targetSplatId',
            'coreTargetStableIds',
            'contextStableGaussianIds',
            'stableGaussianIds',
            'evidenceWorkingSetToken',
        },
        {'targetGeometryHintSeedDigest'},
    ) or value['schemaVersion'] != EVIDENCE_WORKING_SET_SCHEMA_VERSION:
        return False
    input_payload = {
        key: value[key]
        for key in (
            'targetSplatId',
            'coreTargetStableIds',
            'contextStableGaussianIds',
        )
    }
    if 'targetGeometryHintSeedDigest' in value:
        input_payload['targetGeometryHintSeedDigest'] = value[
            'targetGeometryHintSeedDigest'
        ]
    if not _is_evidence_working_set_input(input_payload):
        return False
    core = list(value['coreTargetStableIds'])
    context = list(value['contextStableGaussianIds'])
    expected_stable_ids = _union_stable_gaussian_ids(core, context)
    return (
        value['stableGaussianIds'] == expected_stable_ids
        and _is_digest(value['evidenceWorkingSetToken'])
        and value['evidenceWorkingSetToken'] == _evidence_working_set_token({
            'targetSplatId': value['targetSplatId'],
            'coreTargetStableIds': core,
            'contextStableGaussianIds': context,
        })
    )


def _copy_evidence_working_set(value: Mapping[str, object]) -> dict[str, object]:
    if not is_evidence_working_set(value):
        raise GaussianEvidenceContractError('AI Select Evidence Working Set is invalid.')
    result: dict[str, object] = {
        'schemaVersion': value['schemaVersion'],
        'targetSplatId': value['targetSplatId'],
        'coreTargetStableIds': list(value['coreTargetStableIds']),
        'contextStableGaussianIds': list(value['contextStableGaussianIds']),
        'stableGaussianIds': list(value['stableGaussianIds']),
        'evidenceWorkingSetToken': value['evidenceWorkingSetToken'],
    }
    if 'targetGeometryHintSeedDigest' in value:
        result['targetGeometryHintSeedDigest'] = value[
            'targetGeometryHintSeedDigest'
        ]
    return result


def _is_working_set_expansion(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {'sourceView', 'coreTargetStableIds', 'contextStableGaussianIds'},
    ) or not _is_record(value['sourceView']) or not _has_exact_keys(
        value['sourceView'],
        {'viewId', 'renderStatus', 'participation', 'stableMaskDigest'},
    ):
        return False
    source_view = value['sourceView']
    if (
        not _is_non_empty_string(source_view['viewId'])
        or source_view['renderStatus'] != 'ready'
        or source_view['participation'] != 'included'
        or not _is_digest(source_view['stableMaskDigest'])
        or not _is_sorted_stable_gaussian_ids(
            value['coreTargetStableIds'], allow_empty=True
        )
        or not _is_sorted_stable_gaussian_ids(
            value['contextStableGaussianIds'], allow_empty=True
        )
    ):
        return False
    core = list(value['coreTargetStableIds'])
    context = list(value['contextStableGaussianIds'])
    return bool(core or context) and not _stable_gaussian_ids_intersect(core, context)


def expand_evidence_working_set(
    current: Mapping[str, object],
    expansion: Mapping[str, object],
) -> dict[str, object]:
    """Grow scope only from a later Included Stable View, never silently."""

    if not is_evidence_working_set(current):
        raise GaussianEvidenceContractError('AI Select Evidence Working Set is invalid.')
    if not _is_working_set_expansion(expansion):
        raise GaussianEvidenceContractError(
            'AI Select Evidence Working Set expansion requires an Included Stable View and valid Stable Gaussian IDs.'
        )
    core = _union_stable_gaussian_ids(
        list(current['coreTargetStableIds']),
        list(expansion['coreTargetStableIds']),
    )
    context = _union_stable_gaussian_ids(
        list(current['contextStableGaussianIds']),
        list(expansion['contextStableGaussianIds']),
    )
    if _stable_gaussian_ids_intersect(core, context):
        raise GaussianEvidenceContractError(
            'AI Select Evidence Working Set expansion cannot silently move a Stable Gaussian ID between Core Target and Context.'
        )
    payload: dict[str, object] = {
        'targetSplatId': current['targetSplatId'],
        'coreTargetStableIds': core,
        'contextStableGaussianIds': context,
    }
    if 'targetGeometryHintSeedDigest' in current:
        payload['targetGeometryHintSeedDigest'] = current[
            'targetGeometryHintSeedDigest'
        ]
    return create_evidence_working_set(payload)


def _is_render_working_set_binding(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {
            'targetSplatId',
            'dependencyToken',
            'cameraBindingDigest',
            'renderWorkingSetToken',
            'stableGaussianIds',
            'completeness',
        })
        and _is_non_empty_string(value['targetSplatId'])
        and _is_target_dependency_token(value['dependencyToken'])
        and _is_digest(value['cameraBindingDigest'])
        and _is_digest(value['renderWorkingSetToken'])
        and _is_sorted_stable_gaussian_ids(value['stableGaussianIds'])
        and value['completeness'] in {'complete', 'partial'}
    )


def _is_admission_view(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {'viewId', 'renderStatus', 'participation', 'cameraBindingDigest'},
        {'rgbDigest', 'stableMaskDigest'},
    ):
        return False
    return (
        _is_non_empty_string(value['viewId'])
        and value['renderStatus'] in {'pending', 'rendering', 'ready', 'failed'}
        and value['participation'] in {'included', 'excluded'}
        and _is_digest(value['cameraBindingDigest'])
        and ('rgbDigest' not in value or _is_digest(value['rgbDigest']))
        and (
            'stableMaskDigest' not in value
            or _is_digest(value['stableMaskDigest'])
        )
    )


def is_gaussian_evidence_admission_input(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(value, {
        'requestBinding',
        'targetSplatId',
        'view',
        'evidencePolicyDigest',
        'renderWorkingSet',
        'evidenceWorkingSet',
        'rasterImplementationId',
        'evidenceBackendKind',
        'evidenceBackendId',
        'runtimeBuildId',
    }):
        return False
    if (
        not _is_request_binding(value['requestBinding'])
        or not _is_non_empty_string(value['targetSplatId'])
        or not _is_admission_view(value['view'])
        or not _is_digest(value['evidencePolicyDigest'])
        or not _is_render_working_set_binding(value['renderWorkingSet'])
        or not is_evidence_working_set(value['evidenceWorkingSet'])
        or not _is_non_empty_string(value['rasterImplementationId'])
        or value['evidenceBackendKind'] not in _KNOWN_EVIDENCE_BACKEND_KINDS
        or not _is_non_empty_string(value['evidenceBackendId'])
        or not _is_non_empty_string(value['runtimeBuildId'])
    ):
        return False
    request_binding = value['requestBinding']
    dependency_token = request_binding['dependencyToken']
    return dependency_token['splatId'] == value['targetSplatId']


def _copy_admission(value: Mapping[str, object]) -> dict[str, object]:
    request_binding = value['requestBinding']
    assert isinstance(request_binding, dict)
    return {
        'requestBinding': _copy_request_binding(request_binding),
        'targetSplatId': value['targetSplatId'],
        'viewId': value['viewId'],
        'cameraBindingDigest': value['cameraBindingDigest'],
        'rgbDigest': value['rgbDigest'],
        'stableMaskDigest': value['stableMaskDigest'],
        'evidencePolicyDigest': value['evidencePolicyDigest'],
        'renderWorkingSetToken': value['renderWorkingSetToken'],
        'evidenceWorkingSetToken': value['evidenceWorkingSetToken'],
        'stableGaussianIds': list(value['stableGaussianIds']),
        'rasterImplementationId': value['rasterImplementationId'],
        'evidenceBackendKind': value['evidenceBackendKind'],
        'evidenceBackendId': value['evidenceBackendId'],
        'runtimeBuildId': value['runtimeBuildId'],
    }


def _is_admitted_evidence_input(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {
            'requestBinding',
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId',
        })
        and _is_request_binding(value['requestBinding'])
        and _is_non_empty_string(value['targetSplatId'])
        and value['requestBinding']['dependencyToken']['splatId']
        == value['targetSplatId']
        and _is_non_empty_string(value['viewId'])
        and all(_is_digest(value[key]) for key in (
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
        ))
        and _is_sorted_stable_gaussian_ids(value['stableGaussianIds'])
        and _is_non_empty_string(value['rasterImplementationId'])
        and value['evidenceBackendKind'] in _REFERENCE_EVIDENCE_BACKEND_KINDS
        and _is_non_empty_string(value['evidenceBackendId'])
        and _is_non_empty_string(value['runtimeBuildId'])
    )


def admit_gaussian_evidence(value: object) -> dict[str, object]:
    """Admit only a current Included Stable RGB Ready View for Ticket 14B."""

    if not is_gaussian_evidence_admission_input(value):
        return {'status': 'rejected', 'reason': 'invalid-input'}
    view = value['view']
    render_working_set = value['renderWorkingSet']
    evidence_working_set = value['evidenceWorkingSet']
    if view['renderStatus'] != 'ready':
        return {'status': 'rejected', 'reason': 'render-not-ready'}
    if view['participation'] != 'included':
        return {'status': 'rejected', 'reason': 'view-excluded'}
    if 'rgbDigest' not in view:
        return {'status': 'rejected', 'reason': 'rgb-unavailable'}
    if 'stableMaskDigest' not in view:
        return {'status': 'rejected', 'reason': 'stable-mask-unavailable'}
    if render_working_set['completeness'] != 'complete':
        return {'status': 'rejected', 'reason': 'render-working-set-incomplete'}
    request_binding = value['requestBinding']
    if (
        render_working_set['targetSplatId'] != value['targetSplatId']
        or not _are_target_dependency_tokens_equal(
            render_working_set['dependencyToken'],
            request_binding['dependencyToken'],
        )
        or render_working_set['cameraBindingDigest']
        != view['cameraBindingDigest']
    ):
        return {'status': 'rejected', 'reason': 'render-working-set-mismatch'}
    if evidence_working_set['targetSplatId'] != value['targetSplatId']:
        return {'status': 'rejected', 'reason': 'evidence-working-set-mismatch'}
    if not _stable_gaussian_ids_are_subset_of(
        list(evidence_working_set['stableGaussianIds']),
        list(render_working_set['stableGaussianIds']),
    ):
        return {'status': 'rejected', 'reason': 'stable-id-mapping-invalid'}
    if value['evidenceBackendKind'] not in _REFERENCE_EVIDENCE_BACKEND_KINDS:
        return {'status': 'rejected', 'reason': 'unsupported-evidence-backend'}
    return {
        'status': 'admitted',
        'admission': _copy_admission({
            'requestBinding': request_binding,
            'targetSplatId': value['targetSplatId'],
            'viewId': view['viewId'],
            'cameraBindingDigest': view['cameraBindingDigest'],
            'rgbDigest': view['rgbDigest'],
            'stableMaskDigest': view['stableMaskDigest'],
            'evidencePolicyDigest': value['evidencePolicyDigest'],
            'renderWorkingSetToken': render_working_set['renderWorkingSetToken'],
            'evidenceWorkingSetToken': evidence_working_set['evidenceWorkingSetToken'],
            'stableGaussianIds': evidence_working_set['stableGaussianIds'],
            'rasterImplementationId': value['rasterImplementationId'],
            'evidenceBackendKind': value['evidenceBackendKind'],
            'evidenceBackendId': value['evidenceBackendId'],
            'runtimeBuildId': value['runtimeBuildId'],
        }),
    }


def _is_nonnegative_finite_mass_array(value: object, expected_length: int) -> bool:
    if not isinstance(value, list) or len(value) != expected_length:
        return False
    for mass in value:
        if not isinstance(mass, (int, float)) or isinstance(mass, bool):
            return False
        try:
            number = float(mass)
        except OverflowError:
            return False
        if not math.isfinite(number) or number < 0:
            return False
    return True


def _is_gaussian_evidence_masses(value: object, expected_length: int) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {'positiveMass', 'negativeMass', 'visibleMass'},
        {'boundaryMass'},
    ):
        return False
    return (
        _is_nonnegative_finite_mass_array(value['positiveMass'], expected_length)
        and _is_nonnegative_finite_mass_array(
            value['negativeMass'], expected_length
        )
        and _is_nonnegative_finite_mass_array(value['visibleMass'], expected_length)
        and (
            'boundaryMass' not in value
            or _is_nonnegative_finite_mass_array(
                value['boundaryMass'], expected_length
            )
        )
    )


def _artifact_payload(
    admission: Mapping[str, object],
    masses: Mapping[str, object],
) -> dict[str, object]:
    result: dict[str, object] = {
        'schemaVersion': GAUSSIAN_EVIDENCE_ARTIFACT_SCHEMA_VERSION,
        'requestBinding': _copy_request_binding(admission['requestBinding']),
        'targetSplatId': admission['targetSplatId'],
        'viewId': admission['viewId'],
        'cameraBindingDigest': admission['cameraBindingDigest'],
        'rgbDigest': admission['rgbDigest'],
        'stableMaskDigest': admission['stableMaskDigest'],
        'evidencePolicyDigest': admission['evidencePolicyDigest'],
        'renderWorkingSetToken': admission['renderWorkingSetToken'],
        'evidenceWorkingSetToken': admission['evidenceWorkingSetToken'],
        'stableGaussianIds': list(admission['stableGaussianIds']),
        'positiveMass': list(masses['positiveMass']),
        'negativeMass': list(masses['negativeMass']),
        'visibleMass': list(masses['visibleMass']),
        'rasterImplementationId': admission['rasterImplementationId'],
        'evidenceBackendKind': admission['evidenceBackendKind'],
        'evidenceBackendId': admission['evidenceBackendId'],
        'runtimeBuildId': admission['runtimeBuildId'],
    }
    if 'boundaryMass' in masses:
        result['boundaryMass'] = list(masses['boundaryMass'])
    return result


def _is_gaussian_evidence_artifact_payload(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'requestBinding',
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'positiveMass',
            'negativeMass',
            'visibleMass',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId',
        },
        {'boundaryMass'},
    ) or value['schemaVersion'] != GAUSSIAN_EVIDENCE_ARTIFACT_SCHEMA_VERSION:
        return False
    admission = {
        key: value[key]
        for key in (
            'requestBinding',
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId',
        )
    }
    expected_length = len(value['stableGaussianIds']) if isinstance(
        value['stableGaussianIds'], list
    ) else -1
    return (
        _is_admitted_evidence_input(admission)
        and _is_nonnegative_finite_mass_array(value['positiveMass'], expected_length)
        and _is_nonnegative_finite_mass_array(value['negativeMass'], expected_length)
        and _is_nonnegative_finite_mass_array(value['visibleMass'], expected_length)
        and (
            'boundaryMass' not in value
            or _is_nonnegative_finite_mass_array(
                value['boundaryMass'], expected_length
            )
        )
    )


def gaussian_evidence_artifact_digest(payload: Mapping[str, object]) -> str:
    if not _is_gaussian_evidence_artifact_payload(payload):
        raise GaussianEvidenceContractError(
            'AI Select Gaussian Evidence artifact payload is invalid.'
        )
    return _canonical_digest(dict(payload))


def create_gaussian_evidence_artifact(
    admission: Mapping[str, object],
    masses: Mapping[str, object],
) -> dict[str, object]:
    """Validate and atomically construct one reference-only P/N/V artifact."""

    if not _is_admitted_evidence_input(admission):
        raise GaussianEvidenceContractError('AI Select Gaussian Evidence admission is invalid.')
    if not _is_gaussian_evidence_masses(
        masses, len(admission['stableGaussianIds'])
    ):
        raise GaussianEvidenceContractError(
            'AI Select Gaussian Evidence requires complete finite non-negative P/N/V arrays.'
        )
    payload = _artifact_payload(admission, masses)
    if not _is_gaussian_evidence_artifact_payload(payload):
        raise GaussianEvidenceContractError(
            'AI Select Gaussian Evidence requires complete finite non-negative P/N/V arrays.'
        )
    return {
        **payload,
        'artifactDigest': gaussian_evidence_artifact_digest(payload),
    }


def is_gaussian_evidence_artifact(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'requestBinding',
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'positiveMass',
            'negativeMass',
            'visibleMass',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId',
            'artifactDigest',
        },
        {'boundaryMass'},
    ) or not _is_digest(value['artifactDigest']):
        return False
    payload = {
        key: item for key, item in value.items() if key != 'artifactDigest'
    }
    try:
        return (
            _is_gaussian_evidence_artifact_payload(payload)
            and gaussian_evidence_artifact_digest(payload) == value['artifactDigest']
        )
    except GaussianEvidenceContractError:
        return False


def _are_request_bindings_equal(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> bool:
    return (
        left['targetContextId'] == right['targetContextId']
        and left['contextRevision'] == right['contextRevision']
        and _are_target_dependency_tokens_equal(
            left['dependencyToken'], right['dependencyToken']
        )
    )


def gaussian_evidence_artifact_matches_admission(
    artifact: object,
    admission: object,
) -> bool:
    if not is_gaussian_evidence_artifact(artifact) or not _is_admitted_evidence_input(admission):
        return False
    return (
        _are_request_bindings_equal(
            artifact['requestBinding'], admission['requestBinding']
        )
        and all(artifact[key] == admission[key] for key in (
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId',
        ))
    )


def is_current_gaussian_evidence_artifact(
    artifact: object,
    current_input: object,
) -> bool:
    result = admit_gaussian_evidence(current_input)
    return (
        result['status'] == 'admitted'
        and gaussian_evidence_artifact_matches_admission(
            artifact, result['admission']
        )
    )


def _failed_boundary(
    reason: str,
    contact_stable_gaussian_ids: list[int] | None = None,
) -> dict[str, object]:
    return {
        'status': 'failed-closed',
        'reason': reason,
        'contactStableGaussianIds': list(contact_stable_gaussian_ids or []),
    }


def resolve_evidence_working_set_boundary(value: object) -> dict[str, object]:
    """Require explicit scope expansion or fail closed on boundary contact."""

    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'renderWorkingSet',
            'evidenceWorkingSet',
            'boundaryStableGaussianIds',
            'resolution',
        },
        {'expansion'},
    ) or not _is_render_working_set_binding(
        value['renderWorkingSet']
    ) or not is_evidence_working_set(value['evidenceWorkingSet']) or not _is_sorted_stable_gaussian_ids(
        value['boundaryStableGaussianIds'], allow_empty=True
    ) or value['resolution'] not in {'expand', 'fail-closed'}:
        return _failed_boundary('invalid-boundary-input')
    render_working_set = value['renderWorkingSet']
    evidence_working_set = value['evidenceWorkingSet']
    if (
        render_working_set['completeness'] != 'complete'
        or render_working_set['targetSplatId']
        != evidence_working_set['targetSplatId']
    ):
        return _failed_boundary('invalid-boundary-input')
    contact = [
        stable_id
        for stable_id in value['boundaryStableGaussianIds']
        if stable_id not in evidence_working_set['stableGaussianIds']
    ]
    if not contact:
        return {'status': 'clear', 'contactStableGaussianIds': []}
    if not _stable_gaussian_ids_are_subset_of(
        contact, list(render_working_set['stableGaussianIds'])
    ):
        return _failed_boundary('stable-id-mapping-invalid', contact)
    if value['resolution'] == 'fail-closed':
        return _failed_boundary('evidence-working-set-boundary-contact', contact)
    if not _is_working_set_expansion(value.get('expansion')):
        return _failed_boundary('expansion-does-not-cover-boundary', contact)
    try:
        expanded = expand_evidence_working_set(
            evidence_working_set, value['expansion']
        )
    except GaussianEvidenceContractError:
        return _failed_boundary('expansion-does-not-cover-boundary', contact)
    if not _stable_gaussian_ids_are_subset_of(
        contact, list(expanded['stableGaussianIds'])
    ) or not _stable_gaussian_ids_are_subset_of(
        list(expanded['stableGaussianIds']),
        list(render_working_set['stableGaussianIds']),
    ):
        return _failed_boundary('expansion-does-not-cover-boundary', contact)
    return {
        'status': 'expanded',
        'contactStableGaussianIds': contact,
        'evidenceWorkingSet': _copy_evidence_working_set(expanded),
    }


__all__ = [
    'EVIDENCE_WORKING_SET_SCHEMA_VERSION',
    'GAUSSIAN_EVIDENCE_ARTIFACT_SCHEMA_VERSION',
    'GaussianEvidenceContractError',
    'admit_gaussian_evidence',
    'create_evidence_working_set',
    'create_gaussian_evidence_artifact',
    'expand_evidence_working_set',
    'gaussian_evidence_artifact_digest',
    'gaussian_evidence_artifact_matches_admission',
    'is_current_gaussian_evidence_artifact',
    'is_evidence_working_set',
    'is_gaussian_evidence_admission_input',
    'is_gaussian_evidence_artifact',
    'resolve_evidence_working_set_boundary',
]

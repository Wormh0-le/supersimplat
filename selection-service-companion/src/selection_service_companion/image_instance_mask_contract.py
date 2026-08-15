"""Compact, fail-closed contracts for SAM 3 Image instance Mask inference.

Ticket 08A owns the shared per-View request/result seam only. It does not
perform SAM inference, Mask Review, Stable publication, Participation, or
Gaussian Evidence work.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import struct
from collections.abc import Callable
from typing import Mapping


IMAGE_INSTANCE_PROMPT_ARTIFACT_SCHEMA_VERSION = 1
COMPANION_RGB_ARTIFACT_REF_SCHEMA_VERSION = 1
IMAGE_INSTANCE_MASK_REQUEST_SCHEMA_VERSION = 1
PREVIOUS_PREDICTION_LOGITS_REF_SCHEMA_VERSION = 1
IMAGE_INSTANCE_MASK_RESULT_SCHEMA_VERSION = 1

_DIGEST_PREFIX = 'sha256:'
_DIGEST_LENGTH = len(_DIGEST_PREFIX) + 64
_MAX_SAFE_INTEGER = (1 << 53) - 1


class ImageInstanceMaskContractError(ValueError):
    """A public Image Instance Mask artifact failed fail-closed validation."""


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


def _is_nonnegative_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_SAFE_INTEGER
    )


def _canonical_json_digest(payload: Mapping[str, object]) -> str:
    """Match browser JSON.stringify/TextEncoder bytes for this fixed schema."""

    encoded = json.dumps(
        dict(payload),
        separators=(',', ':'),
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=False,
    ).encode('utf-8')
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def _has_exact_keys(
    value: Mapping[str, object],
    required: set[str],
    optional: set[str] | None = None,
) -> bool:
    allowed = required | (optional or set())
    return required.issubset(value) and set(value).issubset(allowed)


def _is_pixel_point(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {'xPx', 'yPx'})
        and _is_nonnegative_integer(value['xPx'])
        and _is_nonnegative_integer(value['yPx'])
    )


def _is_pixel_box_xyxy(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {'x0Px', 'y0Px', 'x1Px', 'y1Px'})
        and _is_nonnegative_integer(value['x0Px'])
        and _is_nonnegative_integer(value['y0Px'])
        and _is_nonnegative_integer(value['x1Px'])
        and _is_nonnegative_integer(value['y1Px'])
        and value['x0Px'] < value['x1Px']
        and value['y0Px'] < value['y1Px']
    )


def _is_supported_png_encoding(bit_depth: int, color_type: int) -> bool:
    if color_type == 0:
        return bit_depth in {1, 2, 4, 8, 16}
    if color_type in {2, 4, 6}:
        return bit_depth in {8, 16}
    if color_type == 3:
        return bit_depth in {1, 2, 4, 8}
    return False


def _is_prompt_artifact_payload(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'targetContextId',
            'contextRevision',
            'viewId',
            'rgbDigest',
            'cameraBindingDigest',
            'adapterCapabilityDigest',
            'positivePoints',
            'negativePoints',
            'multimaskOutput',
        },
        {
            'targetGeometryHintDigest',
            'localKeyViewPlanDigest',
            'promptSynthesisPolicyDigest',
            'positiveBox',
            'previousLogitsRefDigest',
        },
    ):
        return False
    if (
        value['schemaVersion'] != IMAGE_INSTANCE_PROMPT_ARTIFACT_SCHEMA_VERSION
        or not _is_non_empty_string(value['targetContextId'])
        or not _is_nonnegative_integer(value['contextRevision'])
        or not _is_non_empty_string(value['viewId'])
        or not _is_digest(value['rgbDigest'])
        or not _is_digest(value['cameraBindingDigest'])
        or not _is_digest(value['adapterCapabilityDigest'])
        or not isinstance(value['positivePoints'], list)
        or not all(_is_pixel_point(point) for point in value['positivePoints'])
        or not isinstance(value['negativePoints'], list)
        or not all(_is_pixel_point(point) for point in value['negativePoints'])
        or not isinstance(value['multimaskOutput'], bool)
    ):
        return False
    return (
        ('targetGeometryHintDigest' not in value or _is_digest(value['targetGeometryHintDigest']))
        and ('localKeyViewPlanDigest' not in value or _is_digest(value['localKeyViewPlanDigest']))
        and ('promptSynthesisPolicyDigest' not in value or _is_digest(value['promptSynthesisPolicyDigest']))
        and ('positiveBox' not in value or _is_pixel_box_xyxy(value['positiveBox']))
        and ('previousLogitsRefDigest' not in value or _is_digest(value['previousLogitsRefDigest']))
    )


def _copy_prompt_artifact_payload(
    value: Mapping[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        'schemaVersion': value['schemaVersion'],
        'targetContextId': value['targetContextId'],
        'contextRevision': value['contextRevision'],
        'viewId': value['viewId'],
        'rgbDigest': value['rgbDigest'],
        'cameraBindingDigest': value['cameraBindingDigest'],
        'adapterCapabilityDigest': value['adapterCapabilityDigest'],
        'positivePoints': [dict(point) for point in value['positivePoints']],
        'negativePoints': [dict(point) for point in value['negativePoints']],
        'multimaskOutput': value['multimaskOutput'],
    }
    for key in (
        'targetGeometryHintDigest',
        'localKeyViewPlanDigest',
        'promptSynthesisPolicyDigest',
        'previousLogitsRefDigest',
    ):
        if key in value:
            payload[key] = value[key]
    if 'positiveBox' in value:
        payload['positiveBox'] = dict(value['positiveBox'])
    return payload


def image_instance_prompt_artifact_digest(payload: Mapping[str, object]) -> str:
    """Return the canonical digest over a Prompt artifact without its digest."""

    return _canonical_json_digest(payload)


def create_image_instance_prompt_artifact(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Copy, validate, and digest one immutable-by-convention Prompt artifact."""

    candidate = dict(payload)
    if not _is_prompt_artifact_payload(candidate):
        raise ImageInstanceMaskContractError('Image Instance Prompt artifact input is invalid.')
    copied = _copy_prompt_artifact_payload(candidate)
    return {
        **copied,
        'artifactDigest': image_instance_prompt_artifact_digest(copied),
    }


def is_image_instance_prompt_artifact(value: object) -> bool:
    """Validate exact keys and the canonical digest of one Prompt artifact."""

    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'targetContextId',
            'contextRevision',
            'viewId',
            'rgbDigest',
            'cameraBindingDigest',
            'adapterCapabilityDigest',
            'positivePoints',
            'negativePoints',
            'multimaskOutput',
            'artifactDigest',
        },
        {
            'targetGeometryHintDigest',
            'localKeyViewPlanDigest',
            'promptSynthesisPolicyDigest',
            'positiveBox',
            'previousLogitsRefDigest',
        },
    ) or not _is_digest(value['artifactDigest']):
        return False
    payload = {key: item for key, item in value.items() if key != 'artifactDigest'}
    return (
        _is_prompt_artifact_payload(payload)
        and image_instance_prompt_artifact_digest(payload) == value['artifactDigest']
    )


def companion_rgb_artifact_ref_digest(payload: Mapping[str, object]) -> str:
    """Return the canonical digest of an opaque Companion RGB reference."""

    return _canonical_json_digest(payload)


def _is_companion_rgb_artifact_ref_input(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(
            value,
            {
                'schemaVersion',
                'companionInstanceId',
                'stateId',
                'rgbDigest',
                'width',
                'height',
            },
        )
        and value['schemaVersion'] == COMPANION_RGB_ARTIFACT_REF_SCHEMA_VERSION
        and _is_non_empty_string(value['companionInstanceId'])
        and _is_non_empty_string(value['stateId'])
        and _is_digest(value['rgbDigest'])
        and _is_nonnegative_integer(value['width'])
        and value['width'] > 0
        and _is_nonnegative_integer(value['height'])
        and value['height'] > 0
    )


def create_companion_rgb_artifact_ref(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Copy, validate, and digest a Companion-local RGB reference."""

    candidate = dict(payload)
    if not _is_companion_rgb_artifact_ref_input(candidate):
        raise ImageInstanceMaskContractError('Companion RGB reference input is invalid.')
    return {
        **candidate,
        'refDigest': companion_rgb_artifact_ref_digest(candidate),
    }


def is_companion_rgb_artifact_ref(value: object) -> bool:
    """Validate exact opaque-reference identity without resolving its bytes."""

    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'companionInstanceId',
            'stateId',
            'rgbDigest',
            'width',
            'height',
            'refDigest',
        },
    ) or not _is_digest(value['refDigest']):
        return False
    payload = {key: item for key, item in value.items() if key != 'refDigest'}
    return (
        _is_companion_rgb_artifact_ref_input(payload)
        and companion_rgb_artifact_ref_digest(payload) == value['refDigest']
    )


def _parse_png_dimensions(png: bytes) -> tuple[int, int]:
    """Match the browser's CRC-checked authoritative PNG envelope checks."""

    if png[:8] != b'\x89PNG\r\n\x1a\n':
        raise ImageInstanceMaskContractError('Authoritative RGB bytes are not PNG.')
    offset = 8
    dimensions: tuple[int, int] | None = None
    has_image_data = False
    image_data_ended = False
    has_palette = False
    bit_depth = 0
    color_type = 0
    while offset < len(png):
        if len(png) - offset < 12:
            raise ImageInstanceMaskContractError(
                'Authoritative RGB PNG has a truncated chunk envelope.'
            )
        length = struct.unpack('>I', png[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(png):
            raise ImageInstanceMaskContractError('Authoritative RGB PNG is truncated.')
        chunk_type = png[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        data = png[data_start:data_end]
        expected_crc = struct.unpack('>I', png[data_end:chunk_end])[0]
        actual_crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ImageInstanceMaskContractError(
                'Authoritative RGB PNG has an invalid chunk checksum.'
            )
        if dimensions is None:
            if chunk_type != b'IHDR' or len(data) != 13:
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG must start with IHDR.'
                )
            width, height = struct.unpack('>II', data[:8])
            if width == 0 or height == 0:
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG dimensions must be positive.'
                )
            bit_depth = data[8]
            color_type = data[9]
            compression_method = data[10]
            filter_method = data[11]
            interlace_method = data[12]
            if (
                not _is_supported_png_encoding(bit_depth, color_type)
                or compression_method != 0
                or filter_method != 0
                or interlace_method not in {0, 1}
            ):
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG has unsupported image encoding metadata.'
                )
            dimensions = (width, height)
        elif chunk_type == b'IHDR':
            raise ImageInstanceMaskContractError(
                'Authoritative RGB PNG must not contain multiple IHDR chunks.'
            )

        if chunk_type == b'IDAT':
            if image_data_ended:
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG IDAT chunks must be contiguous.'
                )
            has_image_data = True
        elif chunk_type == b'PLTE':
            if (
                has_image_data
                or has_palette
                or length == 0
                or length % 3 != 0
                or color_type in {0, 4}
                or length // 3 > (1 << bit_depth)
            ):
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG has an invalid palette chunk.'
                )
            has_palette = True
        elif has_image_data and chunk_type != b'IEND':
            image_data_ended = True

        if chunk_type == b'IEND':
            if (
                length != 0
                or not has_image_data
                or (color_type == 3 and not has_palette)
                or chunk_end != len(png)
            ):
                raise ImageInstanceMaskContractError(
                    'Authoritative RGB PNG has an invalid IEND chunk.'
                )
            return dimensions
        offset = chunk_end
    raise ImageInstanceMaskContractError(
        'Authoritative RGB PNG is missing its terminal IEND chunk.'
    )


def _decode_authoritative_rgb_artifact(
    value: object,
) -> tuple[bytes, str, int, int] | None:
    if not _is_record(value) or not _has_exact_keys(
        value, {'pngBase64', 'digest', 'width', 'height'}
    ):
        return None
    if (
        not _is_non_empty_string(value['pngBase64'])
        or not _is_digest(value['digest'])
        or not _is_nonnegative_integer(value['width'])
        or value['width'] <= 0
        or not _is_nonnegative_integer(value['height'])
        or value['height'] <= 0
    ):
        return None
    try:
        png = base64.b64decode(value['pngBase64'], validate=True)
        width, height = _parse_png_dimensions(png)
    except (ImageInstanceMaskContractError, ValueError, binascii.Error):
        return None
    digest = f'sha256:{hashlib.sha256(png).hexdigest()}'
    if digest != value['digest'] or width != value['width'] or height != value['height']:
        return None
    return png, digest, width, height


def is_image_instance_rgb_input(value: object) -> bool:
    """Accept exactly one authoritative RGB payload or opaque Companion ref."""

    if not _is_record(value) or not _is_digest(value.get('rgbDigest')):
        return False
    if (
        not _is_nonnegative_integer(value.get('width'))
        or value['width'] <= 0
        or not _is_nonnegative_integer(value.get('height'))
        or value['height'] <= 0
    ):
        return False
    if _has_exact_keys(value, {'rgbDigest', 'width', 'height', 'artifact'}):
        decoded = _decode_authoritative_rgb_artifact(value['artifact'])
        return (
            decoded is not None
            and decoded[1] == value['rgbDigest']
            and decoded[2] == value['width']
            and decoded[3] == value['height']
        )
    if _has_exact_keys(
        value, {'rgbDigest', 'width', 'height', 'companionRgbRef'}
    ) and is_companion_rgb_artifact_ref(value['companionRgbRef']):
        reference = value['companionRgbRef']
        return (
            reference['rgbDigest'] == value['rgbDigest']
            and reference['width'] == value['width']
            and reference['height'] == value['height']
        )
    return False


def resolve_image_instance_rgb_input(
    rgb_input: object,
    resolve_companion_reference: Callable[[Mapping[str, object]], bytes],
) -> bytes:
    """Resolve exact RGB bytes before inference or raise without running SAM."""

    if not is_image_instance_rgb_input(rgb_input):
        raise ImageInstanceMaskContractError(
            'Image Instance Mask RGB input is invalid before inference.'
        )
    if 'artifact' in rgb_input:
        decoded = _decode_authoritative_rgb_artifact(rgb_input['artifact'])
        if decoded is None:
            raise ImageInstanceMaskContractError(
                'Image Instance Mask RGB artifact is invalid before inference.'
            )
        return decoded[0]
    try:
        png = resolve_companion_reference(rgb_input['companionRgbRef'])
    except Exception as error:
        raise ImageInstanceMaskContractError(
            'Companion RGB reference cannot be resolved before inference.'
        ) from error
    if not isinstance(png, bytes):
        raise ImageInstanceMaskContractError(
            'Companion RGB reference did not resolve immutable bytes.'
        )
    try:
        width, height = _parse_png_dimensions(png)
    except ImageInstanceMaskContractError:
        raise
    if (
        f'sha256:{hashlib.sha256(png).hexdigest()}' != rgb_input['rgbDigest']
        or width != rgb_input['width']
        or height != rgb_input['height']
    ):
        raise ImageInstanceMaskContractError(
            'Companion RGB reference does not reproduce its declared identity.'
        )
    return png


def image_instance_mask_request_identity_digest(
    identity: Mapping[str, object],
) -> str:
    """Return a canonical digest for a request identity component."""

    return _canonical_json_digest(identity)


def _is_image_instance_mask_request_identity(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(
            value,
            {
                'targetContextId',
                'contextRevision',
                'viewId',
                'rgbDigest',
                'promptArtifactDigest',
                'adapterId',
                'modelManifestDigest',
                'runtimeDigest',
                'companionInstanceId',
                'inferenceAttemptId',
            },
        )
        and _is_non_empty_string(value['targetContextId'])
        and _is_nonnegative_integer(value['contextRevision'])
        and _is_non_empty_string(value['viewId'])
        and _is_digest(value['rgbDigest'])
        and _is_digest(value['promptArtifactDigest'])
        and _is_non_empty_string(value['adapterId'])
        and _is_non_empty_string(value['modelManifestDigest'])
        and _is_digest(value['runtimeDigest'])
        and _is_non_empty_string(value['companionInstanceId'])
        and _is_non_empty_string(value['inferenceAttemptId'])
    )


def _points_and_box_fit_rgb(
    prompt: Mapping[str, object], rgb: Mapping[str, object]
) -> bool:
    for point in [*prompt['positivePoints'], *prompt['negativePoints']]:
        if point['xPx'] >= rgb['width'] or point['yPx'] >= rgb['height']:
            return False
    if 'positiveBox' in prompt and (
        prompt['positiveBox']['x1Px'] > rgb['width']
        or prompt['positiveBox']['y1Px'] > rgb['height']
    ):
        return False
    return True


def _prompt_matches_multimask_policy(prompt: Mapping[str, object]) -> bool:
    return prompt['multimaskOutput'] is False


def _prompt_has_positive_seed(prompt: Mapping[str, object]) -> bool:
    return bool(prompt['positivePoints']) or 'positiveBox' in prompt


def is_image_instance_mask_request(value: object) -> bool:
    """Validate a complete provider request before RGB resolution/inference."""

    if not _is_record(value) or not _has_exact_keys(
        value, {'schemaVersion', 'identity', 'rgb', 'prompt'}
    ):
        return False
    if (
        value['schemaVersion'] != IMAGE_INSTANCE_MASK_REQUEST_SCHEMA_VERSION
        or not _is_image_instance_mask_request_identity(value['identity'])
        or not is_image_instance_rgb_input(value['rgb'])
        or not is_image_instance_prompt_artifact(value['prompt'])
    ):
        return False
    identity = value['identity']
    rgb = value['rgb']
    prompt = value['prompt']
    if 'companionRgbRef' in rgb and (
        rgb['companionRgbRef']['companionInstanceId']
        != identity['companionInstanceId']
    ):
        return False
    return (
        identity['targetContextId'] == prompt['targetContextId']
        and identity['contextRevision'] == prompt['contextRevision']
        and identity['viewId'] == prompt['viewId']
        and identity['rgbDigest'] == rgb['rgbDigest']
        and identity['rgbDigest'] == prompt['rgbDigest']
        and identity['promptArtifactDigest'] == prompt['artifactDigest']
        and _prompt_has_positive_seed(prompt)
        and _points_and_box_fit_rgb(prompt, rgb)
        and _prompt_matches_multimask_policy(prompt)
    )


def previous_prediction_logits_ref_digest(payload: Mapping[str, object]) -> str:
    """Return the canonical digest of opaque Companion-local logits metadata."""

    return _canonical_json_digest(payload)


def _is_previous_prediction_logits_ref_input(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'companionInstanceId',
            'stateId',
            'targetContextId',
            'viewId',
            'rgbDigest',
            'sourceInferenceAttemptId',
            'sourceCandidateId',
            'adapterRuntimeDigest',
            'shape',
            'dtype',
            'dataDigest',
        },
    ):
        return False
    return (
        value['schemaVersion'] == PREVIOUS_PREDICTION_LOGITS_REF_SCHEMA_VERSION
        and _is_non_empty_string(value['companionInstanceId'])
        and _is_non_empty_string(value['stateId'])
        and _is_non_empty_string(value['targetContextId'])
        and _is_non_empty_string(value['viewId'])
        and _is_digest(value['rgbDigest'])
        and _is_non_empty_string(value['sourceInferenceAttemptId'])
        and _is_non_empty_string(value['sourceCandidateId'])
        and _is_digest(value['adapterRuntimeDigest'])
        and isinstance(value['shape'], list)
        and bool(value['shape'])
        and all(_is_nonnegative_integer(dimension) and dimension > 0 for dimension in value['shape'])
        and _is_non_empty_string(value['dtype'])
        and _is_digest(value['dataDigest'])
    )


def create_previous_prediction_logits_ref(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Copy and digest opaque metadata; raw logits bytes cannot enter it."""

    candidate = dict(payload)
    if not _is_previous_prediction_logits_ref_input(candidate):
        raise ImageInstanceMaskContractError(
            'Previous prediction logits reference input is invalid.'
        )
    copied = {
        **candidate,
        'shape': list(candidate['shape']),
    }
    return {
        **copied,
        'refDigest': previous_prediction_logits_ref_digest(copied),
    }


def is_previous_prediction_logits_ref(value: object) -> bool:
    """Reject raw-tensor fields and stale/tampered opaque ref metadata."""

    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'companionInstanceId',
            'stateId',
            'targetContextId',
            'viewId',
            'rgbDigest',
            'sourceInferenceAttemptId',
            'sourceCandidateId',
            'adapterRuntimeDigest',
            'shape',
            'dtype',
            'dataDigest',
            'refDigest',
        },
    ) or not _is_digest(value['refDigest']):
        return False
    payload = {key: item for key, item in value.items() if key != 'refDigest'}
    return (
        _is_previous_prediction_logits_ref_input(payload)
        and previous_prediction_logits_ref_digest(payload) == value['refDigest']
    )


def _is_mask_artifact(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value, {'encoding', 'width', 'height', 'data', 'digest'}
    ):
        return False
    if (
        value['encoding'] != 'bitset-lsb-v1'
        or not _is_nonnegative_integer(value['width'])
        or value['width'] <= 0
        or not _is_nonnegative_integer(value['height'])
        or value['height'] <= 0
        or not _is_non_empty_string(value['data'])
        or not _is_digest(value['digest'])
    ):
        return False
    try:
        bits = base64.b64decode(value['data'], validate=True)
    except (ValueError, binascii.Error):
        return False
    pixel_count = value['width'] * value['height']
    if len(bits) != (pixel_count + 7) // 8:
        return False
    remainder = pixel_count % 8
    if remainder and bits[-1] & ~((1 << remainder) - 1):
        return False
    return f'sha256:{hashlib.sha256(bits).hexdigest()}' == value['digest']


def _is_image_instance_mask_diagnostics(value: object) -> bool:
    return (
        _is_record(value)
        and _has_exact_keys(value, {'outcome'}, {'refinementFallback'})
        and value['outcome'] in {'available', 'unavailable'}
        and (
            'refinementFallback' not in value
            or isinstance(value['refinementFallback'], bool)
        )
    )


def _is_image_instance_mask_result_input(value: object) -> bool:
    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'requestIdentity',
            'masks',
            'modelScores',
            'diagnostics',
        },
        {'previousLogitsRefs'},
    ):
        return False
    if (
        value['schemaVersion'] != IMAGE_INSTANCE_MASK_RESULT_SCHEMA_VERSION
        or not _is_image_instance_mask_request_identity(value['requestIdentity'])
        or not isinstance(value['masks'], list)
        or len(value['masks']) > 1
        or not all(_is_mask_artifact(mask) for mask in value['masks'])
        or not isinstance(value['modelScores'], list)
        or len(value['modelScores']) != len(value['masks'])
        or not all(
            isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(score)
            for score in value['modelScores']
        )
        or not _is_image_instance_mask_diagnostics(value['diagnostics'])
    ):
        return False
    if 'previousLogitsRefs' in value and (
        not isinstance(value['previousLogitsRefs'], list)
        or len(value['previousLogitsRefs']) != len(value['masks'])
        or not all(
            is_previous_prediction_logits_ref(reference)
            for reference in value['previousLogitsRefs']
        )
    ):
        return False
    return (
        value['diagnostics']['outcome'] == 'unavailable'
        if not value['masks']
        else value['diagnostics']['outcome'] == 'available'
    )


def _copy_image_instance_mask_result_input(
    value: Mapping[str, object],
) -> dict[str, object]:
    copied: dict[str, object] = {
        'schemaVersion': value['schemaVersion'],
        'requestIdentity': dict(value['requestIdentity']),
        'masks': [dict(mask) for mask in value['masks']],
        'modelScores': list(value['modelScores']),
        'diagnostics': dict(value['diagnostics']),
    }
    if 'previousLogitsRefs' in value:
        copied['previousLogitsRefs'] = [
            {**reference, 'shape': list(reference['shape'])}
            for reference in value['previousLogitsRefs']
        ]
    return copied


def _image_instance_result_canonical_json(value: object) -> str:
    """Canonicalize result numbers by IEEE-754 bits across both runtimes."""

    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            raise ImageInstanceMaskContractError(
                'Image Instance Mask result numbers must be finite.'
            )
        return f'n{struct.pack(">d", number).hex()}'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, list):
        return '[' + ','.join(
            _image_instance_result_canonical_json(entry) for entry in value
        ) + ']'
    if isinstance(value, dict):
        entries: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise ImageInstanceMaskContractError(
                    'Image Instance Mask result keys must be strings.'
                )
            entries.append(
                f'{json.dumps(key, ensure_ascii=False)}:'
                f'{_image_instance_result_canonical_json(value[key])}'
            )
        return '{' + ','.join(entries) + '}'
    raise ImageInstanceMaskContractError(
        f'Image Instance Mask result has unsupported data: {type(value).__name__}.'
    )


def image_instance_mask_result_digest(payload: Mapping[str, object]) -> str:
    """Return the canonical digest of an inference-only completed result."""

    encoded = _image_instance_result_canonical_json(dict(payload)).encode('utf-8')
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def create_image_instance_mask_result(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Copy, validate, and digest a complete result or semantic unavailable."""

    candidate = dict(payload)
    if not _is_image_instance_mask_result_input(candidate):
        raise ImageInstanceMaskContractError('Image Instance Mask result input is invalid.')
    copied = _copy_image_instance_mask_result_input(candidate)
    return {
        **copied,
        'resultDigest': image_instance_mask_result_digest(copied),
    }


def is_image_instance_mask_result(value: object) -> bool:
    """Reject partial technical results and all non-inference output fields."""

    if not _is_record(value) or not _has_exact_keys(
        value,
        {
            'schemaVersion',
            'requestIdentity',
            'masks',
            'modelScores',
            'diagnostics',
            'resultDigest',
        },
        {'previousLogitsRefs'},
    ) or not _is_digest(value['resultDigest']):
        return False
    payload = {key: item for key, item in value.items() if key != 'resultDigest'}
    return (
        _is_image_instance_mask_result_input(payload)
        and image_instance_mask_result_digest(payload) == value['resultDigest']
    )


def _identities_match(
    left: Mapping[str, object], right: Mapping[str, object]
) -> bool:
    return all(
        left[key] == right[key]
        for key in (
            'targetContextId',
            'contextRevision',
            'viewId',
            'rgbDigest',
            'promptArtifactDigest',
            'adapterId',
            'modelManifestDigest',
            'runtimeDigest',
            'companionInstanceId',
            'inferenceAttemptId',
        )
    )


def _ref_matches_identity(
    reference: Mapping[str, object], identity: Mapping[str, object]
) -> bool:
    return (
        reference['companionInstanceId'] == identity['companionInstanceId']
        and reference['targetContextId'] == identity['targetContextId']
        and reference['viewId'] == identity['viewId']
        and reference['rgbDigest'] == identity['rgbDigest']
        and reference['adapterRuntimeDigest'] == identity['runtimeDigest']
    )


def previous_logits_ref_matches_image_instance_mask_request(
    reference: object, request: object
) -> bool:
    """Reject cross-View, stale-RGB, or Companion-replacement refinement refs."""

    return (
        is_previous_prediction_logits_ref(reference)
        and is_image_instance_mask_request(request)
        and request['prompt'].get('previousLogitsRefDigest') == reference['refDigest']
        and not request['prompt']['multimaskOutput']
        and _ref_matches_identity(reference, request['identity'])
    )


def resolve_previous_logits_ref_for_image_instance_mask_request(
    request: object,
    current_companion_instance_id: str,
    resolve: Callable[[str], Mapping[str, object] | None],
) -> dict[str, object] | None:
    """Resolve only a digest to current-Companion opaque logits metadata.

    A missing or incompatible local ref is the declared fresh-inference
    fallback. A resolver exception remains a technical failure; no partial
    logits state is returned or published.
    """

    if (
        not is_image_instance_mask_request(request)
        or not _is_non_empty_string(current_companion_instance_id)
    ):
        raise ImageInstanceMaskContractError(
            'Image Instance Mask request is invalid before refinement resolution.'
        )
    if request['identity']['companionInstanceId'] != current_companion_instance_id:
        raise ImageInstanceMaskContractError(
            'Image Instance Mask request is not bound to the current Companion Instance.'
        )
    ref_digest = request['prompt'].get('previousLogitsRefDigest')
    if ref_digest is None:
        return None
    reference = resolve(ref_digest)
    if reference is None or not previous_logits_ref_matches_image_instance_mask_request(
        reference, request
    ):
        return None
    return {**reference, 'shape': list(reference['shape'])}


def image_instance_mask_result_matches_request(result: object, request: object) -> bool:
    """Verify exact request echoes, dimensions, cardinality, and returned refs."""

    if not is_image_instance_mask_result(result) or not is_image_instance_mask_request(request):
        return False
    if not _identities_match(result['requestIdentity'], request['identity']):
        return False
    if any(
        mask['width'] != request['rgb']['width']
        or mask['height'] != request['rgb']['height']
        for mask in result['masks']
    ):
        return False
    if len(result['masks']) > 1:
        return False
    return all(
        _ref_matches_identity(reference, request['identity'])
        for reference in result.get('previousLogitsRefs', [])
    )


__all__ = [
    'COMPANION_RGB_ARTIFACT_REF_SCHEMA_VERSION',
    'IMAGE_INSTANCE_MASK_RESULT_SCHEMA_VERSION',
    'IMAGE_INSTANCE_PROMPT_ARTIFACT_SCHEMA_VERSION',
    'IMAGE_INSTANCE_MASK_REQUEST_SCHEMA_VERSION',
    'PREVIOUS_PREDICTION_LOGITS_REF_SCHEMA_VERSION',
    'ImageInstanceMaskContractError',
    'companion_rgb_artifact_ref_digest',
    'create_companion_rgb_artifact_ref',
    'create_image_instance_prompt_artifact',
    'create_image_instance_mask_result',
    'create_previous_prediction_logits_ref',
    'image_instance_mask_request_identity_digest',
    'image_instance_mask_result_digest',
    'image_instance_prompt_artifact_digest',
    'is_companion_rgb_artifact_ref',
    'is_image_instance_mask_request',
    'is_image_instance_mask_result',
    'is_image_instance_prompt_artifact',
    'is_image_instance_rgb_input',
    'is_previous_prediction_logits_ref',
    'image_instance_mask_result_matches_request',
    'previous_logits_ref_matches_image_instance_mask_request',
    'previous_prediction_logits_ref_digest',
    'resolve_previous_logits_ref_for_image_instance_mask_request',
    'resolve_image_instance_rgb_input',
]

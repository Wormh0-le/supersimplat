"""Persistent, operator-owned release and model-installation state."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import secrets
import struct
from threading import Event, Lock
import time
from typing import Any, Callable, Mapping, Sequence
import uuid

from . import PACKAGE_VERSION, PROTOCOL_VERSION
from .anchor_timing import AnchorServerTiming
from .binary_scene_snapshot import (
    BinarySceneSnapshotManifest,
    BinarySceneSnapshotUploadStore,
    ImmutableSnapshotConflict,
    PackedBinarySceneSnapshot,
    SnapshotUploadError,
    SnapshotUploadAdmission,
    SnapshotUploadCommit,
)
from .evidence import ContributorRenderer, build_evidence_snapshot
from .generated_views import (
    GENERATED_VIEW_RESOLUTIONS,
    GeneratedViewPolicy,
    frame_set_payload,
    generated_render_config_version,
    public_frame_set_payload,
    quality_gate_tracks,
)
from .gsplat_renderer import (
    AnchorRenderArtifact,
    GsplatContributorRenderer,
    production_gsplat_renderer,
    validate_supported_snapshot,
)
from .masking import (
    CompiledImagePromptProgram,
    MaskProduction,
    MaskSessionError,
    POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
    PromptableMaskAdapter,
    RegisteredFrameSet,
    SAM3_IMAGE_INSTANCE_ADAPTER_ID,
    SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
    SAM3_IMAGE_RUNTIME_CONFIG,
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3ImageCandidate,
    Sam3ImageInstanceAdapter,
    Sam3ImageProposalBatch,
    Sam3ImageRefinementInput,
    Sam3PointMaskAdapter,
    compile_point_mask_prompt_program,
    compile_sam3_image_prompt_program,
    register_frame_set,
    sam3_image_instance_capabilities,
)
from .proposal_ranking import (
    RANKING_POLICY_VERSION,
    add_ranking_features,
    decide_proposals,
)
from .renderer_runtime import (
    EXPECTED_RENDERER_LOCK_DIGEST,
    RendererRuntime,
    current_renderer_runtime,
)
from .spatial_scene_working_set import (
    SpatialChunkUploadAdmission,
    SpatialChunkUploadCommit,
    SpatialManifestRegistration,
    SpatialSceneManifest,
    SpatialSceneStore,
    SpatialWorkingSet,
)
from .support_probe import (
    AI_SELECT_SUPPORT_PROBE_MASK_ENCODING,
    AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
    AnchorSupportProbeCamera,
    count_observed_gaussians,
    probe_camera_from_renderer_camera,
)
from .view_assessment import (
    AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
    MaskReviewPrompt,
    assess_local_view,
    local_view_assessment_payload,
)
from .digests import canonical_json_digest as _canonical_json_digest
from .generated_view_planning import (
    AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION,
    synthesize_view_prompts,
)
from .target_geometry import (
    AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
    AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
    LOCAL_KEY_VIEW_PLAN_SCHEMA_VERSION,
    TARGET_GEOMETRY_HINT_SCHEMA_VERSION,
    GeometryUnavailableError,
    PlanExhaustedError,
    PlannerFailureError,
    derive_target_geometry_hint,
    local_key_view_policy_digest,
    plan_local_key_views,
    target_geometry_policy_digest,
)


DEFAULT_STATE_DIRECTORY = Path.home() / ".local" / "state" / "supersplat-selection-service"
AI_SELECT_RUNTIME_PROFILE_ID = "ai-select-static-image-instance/v1"
AI_SELECT_READINESS_PROTOCOL_VERSION = "2"
AI_SELECT_MASK_PROPOSAL_POLICY_VERSION = "auto-mask-proposals/bounded-source-order-v2"
AI_SELECT_RGB_CACHE_LIMIT = 16
AI_SELECT_LOGITS_STORE_LIMIT = 8
# A planned Key View whose authoritative raster alpha covers less than this
# fraction of the frame is blank and fails closed (view-renders only).
_BLANK_RENDER_MIN_ALPHA_COVERAGE = 0.001

# Operator-facing diagnostics: the wire carries distinguishable generic
# failure codes, while the underlying model/runtime cause stays in the
# Companion log where the operator can act on it.
_logger = logging.getLogger(__name__)


def _proposal_identity_json(value: object) -> str:
    """Canonicalize proposal identity with explicit IEEE-754 number tokens."""
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Proposal identity numbers must be finite')
        return f'n{struct.pack(">d", number).hex()}'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, list):
        return '[' + ','.join(
            _proposal_identity_json(entry) for entry in value
        ) + ']'
    if isinstance(value, dict):
        entries: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError('Proposal identity object keys must be strings')
            entries.append(
                f'{json.dumps(key, ensure_ascii=False)}:'
                f'{_proposal_identity_json(value[key])}'
            )
        return f'{{{",".join(entries)}}}'
    raise TypeError(f'Unsupported proposal identity value: {type(value).__name__}')


def _proposal_identity_digest(value: object) -> str:
    encoded = _proposal_identity_json(value).encode('utf-8')
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def _local_view_assessment_payload(
    *,
    rgb_digest: str,
    stable_mask_digest: str,
    width: int,
    height: int,
    mask: bytes,
    positive_points: tuple[tuple[int, int], ...],
) -> dict[str, object]:
    # The current Generated View Prompt family is synthesized include points
    # only; Negative Point and Box consistency stay unevaluated (never
    # fabricated) until the instance Prompt contract supplies them.
    assessment = assess_local_view(
        width=width,
        height=height,
        mask=mask,
        prompt=MaskReviewPrompt(positive_points=positive_points),
    )
    payload = local_view_assessment_payload(assessment)
    payload['inputIdentity'] = {
        'rgbDigest': rgb_digest,
        'stableMaskDigest': stable_mask_digest,
        'assessmentPolicyVersion': assessment.policy_version,
    }
    return payload


def _failed_local_view_assessment_payload(
    *,
    rgb_digest: str,
    stable_mask_digest: str,
) -> dict[str, object]:
    return {
        'status': 'failed',
        'reasons': [],
        'actionableReasons': [],
        'policyVersion': AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        'inputIdentity': {
            'rgbDigest': rgb_digest,
            'stableMaskDigest': stable_mask_digest,
            'assessmentPolicyVersion': AI_SELECT_VIEW_ASSESSMENT_POLICY_VERSION,
        },
    }


def _is_torch_out_of_memory(error: BaseException) -> bool:
    """Recognize only PyTorch's measured CUDA OOM signal."""

    try:
        import torch
    except ImportError:
        return False
    return isinstance(error, torch.OutOfMemoryError)

MODEL_MANIFEST_IDENTITY_FIELDS = (
    "digest",
    "adapterId",
    "modelName",
    "checkpointDigest",
    "sourceCommit",
    "licenseName",
    "licenseUrl",
    "runtimeConfigDigest",
)

# The versioned identity of the authoritative RGB implementation. Ticket 20
# replaces this seam with the FlashSplat-style same-decision kernel; the
# browser fails closed on any version it does not explicitly support.
AI_SELECT_RGB_RENDERER_VERSION = 'gsplat-rgb/v1'


@dataclass(frozen=True)
class RegisteredSceneSnapshot:
    """Immutable Scene Snapshot payload cached by its editor-owned version."""

    scene: Mapping[str, Any] | PackedBinarySceneSnapshot
    stable_ids: tuple[int, ...] | memoryview
    render_config_version: str
    identity: str


@dataclass(frozen=True)
class AISelectAnchorRequest:
    """Validated browser binding plus the derived locked-renderer camera."""

    request_binding: dict[str, object]
    target_splat_id: str
    scene_id: str
    scene_version: str
    render_config_version: str
    render_attempt_id: str
    camera_binding: dict[str, object]
    renderer_camera: dict[str, object]
    width: int
    height: int
    view_id: str = 'anchor-view'
    scene_transport: str = 'packed-v1'
    reference_contributor: bool = False

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'sceneId': self.scene_id,
            'sceneVersion': self.scene_version,
            'renderConfigVersion': self.render_config_version,
            'renderAttemptId': self.render_attempt_id,
            'viewId': self.view_id,
            'cameraBinding': self.camera_binding,
        }


@dataclass
class AnchorRenderAdmission:
    """One private, replayable Anchor publication reserved by request binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class AISelectTargetGeometryHintRequest:
    """Validated browser binding for one Target Geometry Hint attempt."""

    request_binding: dict[str, object]
    target_splat_id: str
    scene_id: str
    scene_version: str
    render_config_version: str
    geometry_attempt_id: str
    camera_binding: dict[str, object]
    probe_camera: AnchorSupportProbeCamera
    anchor_camera_binding_digest: str
    anchor_rgb_digest: str
    stable_mask: bytes
    stable_mask_digest: str
    scene_transport: str = 'packed-v1'

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'sceneId': self.scene_id,
            'sceneVersion': self.scene_version,
            'renderConfigVersion': self.render_config_version,
            'geometryAttemptId': self.geometry_attempt_id,
            'geometryPolicyVersion': AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
        }

    def identity_fields(self) -> dict[str, object]:
        return {
            **self.response_fields(),
            'cameraBinding': self.camera_binding,
            'anchorCameraBindingDigest': self.anchor_camera_binding_digest,
            'anchorRgbDigest': self.anchor_rgb_digest,
            'stableMaskDigest': self.stable_mask_digest,
            'sceneTransport': self.scene_transport,
        }


@dataclass
class TargetGeometryHintAdmission:
    """One private, replayable hint publication reserved by request binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class AISelectLocalKeyViewPlanRequest:
    """Validated browser binding for one bounded local Key-View plan attempt."""

    request_binding: dict[str, object]
    target_splat_id: str
    plan_attempt_id: str
    batch_ordinal: int
    camera_binding: dict[str, object]
    anchor_camera_binding_digest: str
    anchor_rgb_digest: str
    stable_mask_digest: str
    target_geometry_hint: dict[str, object]

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'planAttemptId': self.plan_attempt_id,
            'batchOrdinal': self.batch_ordinal,
            'localViewPolicyVersion': AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
        }

    def identity_fields(self) -> dict[str, object]:
        return {
            **self.response_fields(),
            'cameraBinding': self.camera_binding,
            'anchorCameraBindingDigest': self.anchor_camera_binding_digest,
            'anchorRgbDigest': self.anchor_rgb_digest,
            'stableMaskDigest': self.stable_mask_digest,
            'targetGeometryHint': self.target_geometry_hint,
        }


@dataclass
class LocalKeyViewPlanAdmission:
    """One private, replayable plan publication reserved by request binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class AISelectGeneratedViewMaskRequest:
    """Validated browser binding for one cross-view automatic Mask attempt."""

    request_binding: dict[str, object]
    target_splat_id: str
    scene_id: str
    scene_version: str
    render_config_version: str
    view_id: str
    view_camera_binding: dict[str, object]
    view_probe_camera: AnchorSupportProbeCamera
    mask_attempt_id: str
    rgb_png: bytes
    rgb_digest: str
    width: int
    height: int
    anchor_camera_binding: dict[str, object]
    anchor_probe_camera: AnchorSupportProbeCamera
    anchor_rgb_digest: str
    stable_mask: bytes
    stable_mask_digest: str
    model_manifest_digest: str
    scene_transport: str = 'packed-v1'

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'sceneId': self.scene_id,
            'sceneVersion': self.scene_version,
            'renderConfigVersion': self.render_config_version,
            'viewId': self.view_id,
            'maskAttemptId': self.mask_attempt_id,
        }

    def identity_fields(self) -> dict[str, object]:
        return {
            **self.response_fields(),
            'viewCameraBinding': self.view_camera_binding,
            'rgbDigest': self.rgb_digest,
            'anchorCameraBinding': self.anchor_camera_binding,
            'anchorRgbDigest': self.anchor_rgb_digest,
            'stableMaskDigest': self.stable_mask_digest,
            'modelManifestDigest': self.model_manifest_digest,
            'sceneTransport': self.scene_transport,
        }


@dataclass
class GeneratedViewMaskAdmission:
    """One private, replayable automatic Mask reserved by request binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class AISelectMaskPrompt:
    """One validated point prompt on the single authoritative RGB frame."""

    prompt_id: str
    x_px: int
    y_px: int
    polarity: str

    def response_fields(self) -> dict[str, object]:
        return {
            'promptId': self.prompt_id,
            'xPx': self.x_px,
            'yPx': self.y_px,
            'polarity': self.polarity,
        }


@dataclass(frozen=True)
class AISelectMaskRequest:
    """Validated binding for one prompt-conditioned proposal attempt."""

    request_binding: dict[str, object]
    target_splat_id: str
    scene_id: str
    scene_version: str
    view_id: str
    camera_binding_digest: str
    rgb_png: bytes
    rgb_digest: str
    width: int
    height: int
    prompts: tuple[AISelectMaskPrompt, ...]
    prompt_program: CompiledImagePromptProgram
    prompt_state: dict[str, object]
    prompt_state_digest: str
    model_manifest_digest: str
    adapter_capability_digest: str
    proposal_policy_version: str
    ranking_policy_version: str
    proposal_attempt_id: str
    previous_logits_ref: dict[str, object] | None = None

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'sceneId': self.scene_id,
            'sceneVersion': self.scene_version,
            'viewId': self.view_id,
            'cameraBindingDigest': self.camera_binding_digest,
            'rgbDigest': self.rgb_digest,
            'promptStateDigest': self.prompt_state_digest,
            'modelManifestDigest': self.model_manifest_digest,
            'adapterCapabilityDigest': self.adapter_capability_digest,
            'proposalPolicyVersion': self.proposal_policy_version,
            'rankingPolicyVersion': self.ranking_policy_version,
            'proposalAttemptId': self.proposal_attempt_id,
        }

    def identity_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            **self.response_fields(),
            'promptState': self.prompt_state,
        }
        if self.previous_logits_ref is not None:
            fields['previousLogitsRef'] = self.previous_logits_ref
        return fields


@dataclass
class MaskRequestAdmission:
    """One private, replayable single-frame mask reserved by request binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class AISelectSupportProbeRequest:
    """Validated browser binding for one Anchor support probe attempt."""

    request_binding: dict[str, object]
    target_splat_id: str
    scene_id: str
    scene_version: str
    render_config_version: str
    support_probe_attempt_id: str
    camera_binding: dict[str, object]
    probe_camera: AnchorSupportProbeCamera
    rgb_digest: str
    stable_mask: bytes
    stable_mask_digest: str
    scene_transport: str = 'packed-v1'

    def response_fields(self) -> dict[str, object]:
        return {
            'requestBinding': self.request_binding,
            'targetSplatId': self.target_splat_id,
            'sceneId': self.scene_id,
            'sceneVersion': self.scene_version,
            'renderConfigVersion': self.render_config_version,
            'supportProbeAttemptId': self.support_probe_attempt_id,
            'viewId': 'anchor-view',
            'cameraBinding': self.camera_binding,
        }

    def identity_fields(self) -> dict[str, object]:
        return {
            **self.response_fields(),
            'rgbDigest': self.rgb_digest,
            'stableMaskDigest': self.stable_mask_digest,
            'supportProbePolicyVersion': AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
            'sceneTransport': self.scene_transport,
        }


@dataclass
class SupportProbeAdmission:
    """One private, replayable support probe publication reserved by binding."""

    completed: Event = field(default_factory=Event)
    publication: str | None = None
    failure: tuple[str, str] | None = None


@dataclass(frozen=True)
class GeneratedFrameSetResolution:
    """The cached one-rebuild result for a Generated View preview session."""

    source_frame_set_version: str
    frame_set_version: str
    render_config_version: str
    preliminary_rejections: tuple[dict[str, object], ...]
    attempted_view_ids: tuple[str, ...]
    quality_diagnostics: dict[str, object]


@dataclass(frozen=True)
class StagedGeneratedPreview:
    """Unpublished Generated View state that can be committed or rolled back."""

    token: str
    resolution: GeneratedFrameSetResolution
    prior_frame_set_version: str | None
    prior_generated_resolution: GeneratedFrameSetResolution | None
    prior_prompt_log_canonical: str
    prior_prompt_log_revision: int
    prior_completed_update: str | None
    prior_completed_update_fingerprint: str | None
    prior_completed_evidence_snapshot: str | None
    prior_completed_preview_publication: str | None


@dataclass
class ActiveMaskSession:
    """The rollback-safe, service-owned state for one mask-session lifetime."""

    frame_set_version: str | None = None
    model_manifest_digest: str | None = None
    open_request_id: str | None = None
    prompt_log_canonical: str = "[]"
    prompt_log_revision: int = 0
    completed_updates: dict[str, str] = field(default_factory=dict)
    completed_update_fingerprints: dict[str, str] = field(default_factory=dict)
    completed_evidence_snapshots: dict[str, str] = field(default_factory=dict)
    completed_preview_publications: dict[str, str] = field(default_factory=dict)
    cancelled_request_ids: set[str] = field(default_factory=set)
    in_flight_request_ids: set[str] = field(default_factory=set)
    generated_resolution: GeneratedFrameSetResolution | None = None
    staged_generated_preview_token: str | None = None
    staged_generated_preview_request_id: str | None = None
    closing: bool = False


@dataclass(frozen=True)
class PreviewPublication:
    """The sole atomically published preview result for one request."""

    bindings: dict[str, Any]
    frame_set: dict[str, object]
    mask_set: dict[str, Any]
    evidence_snapshot: dict[str, Any]
    coverage_report: dict[str, object]


@dataclass(frozen=True)
class ResolvedPreviewFrameSet:
    """The version-bound inputs used for one atomic preview publication."""

    bindings: dict[str, Any]
    frame_set: RegisteredFrameSet
    preliminary_rejections: tuple[dict[str, object], ...]
    attempted_view_ids: tuple[str, ...]
    quality_diagnostics: dict[str, object]
    staged_generated_preview: StagedGeneratedPreview | None = None


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_sha256(value: str, field_name: str = "checkpointDigest") -> str:
    prefix = "sha256:"
    digest = value[len(prefix):] if value.startswith(prefix) else value
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return digest.lower()


def _anchor_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'AI Select Anchor {field_name} must be a non-empty string')
    return value


def _anchor_sha256_digest(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != len('sha256:') + 64
        or not value.startswith('sha256:')
        or any(character not in '0123456789abcdef' for character in value[7:])
    ):
        raise ValueError(
            f'AI Select Anchor {field_name} must be a sha256:<64 hex> digest'
        )
    return value


def _anchor_nonnegative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f'AI Select Anchor {field_name} must be a non-negative integer'
        )
    return value


def _anchor_positive_integer(value: object, field_name: str) -> int:
    integer = _anchor_nonnegative_integer(value, field_name)
    if integer <= 0:
        raise ValueError(f'AI Select Anchor {field_name} must be greater than zero')
    return integer


def _anchor_finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'AI Select Anchor {field_name} must be a finite number')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'AI Select Anchor {field_name} must be a finite number')
    return number


def _anchor_number_sequence(
    value: object, length: int, field_name: str
) -> tuple[float, ...]:
    if (
        not isinstance(value, list)
        or len(value) != length
    ):
        raise ValueError(
            f'AI Select Anchor {field_name} must contain {length} finite numbers'
        )
    return tuple(
        _anchor_finite_number(item, f'{field_name}[{index}]')
        for index, item in enumerate(value)
    )


def _anchor_digest(value: str, field_name: str) -> str:
    if (
        len(value) != len('sha256:') + 64
        or not value.startswith('sha256:')
        or any(character not in '0123456789abcdef' for character in value[7:].lower())
    ):
        raise MaskSessionError(
            'rendererFailure', f'gsplat Anchor {field_name} is invalid.'
        )
    return value


def _mask_request_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'AI Select Mask {field_name} must be a non-empty string')
    return value


def _mask_request_nonnegative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f'AI Select Mask {field_name} must be a non-negative integer'
        )
    return value


def _mask_request_positive_integer(value: object, field_name: str) -> int:
    integer = _mask_request_nonnegative_integer(value, field_name)
    if integer <= 0:
        raise ValueError(f'AI Select Mask {field_name} must be greater than zero')
    return integer


def _point_prompt_capabilities() -> dict[str, object]:
    payload: dict[str, object] = {
        'points': True,
        'negativePoints': True,
        'boxes': False,
        'negativeBoxes': False,
        'maskInput': False,
        'negativeMaskConstraints': False,
        'text': False,
        'negativeText': False,
        'multiCandidateOutput': True,
        'compilerPolicyVersion': POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
        'unsupportedPromptReasons': {
            'positive-box': 'The deterministic Point Mask adapter supports Points only.',
            'negative-box': 'The deterministic Point Mask adapter supports Points only.',
            'positive-mask-constraint': (
                'The deterministic Point Mask adapter supports Points only.'
            ),
            'negative-mask-constraint': (
                'The deterministic Point Mask adapter supports Points only.'
            ),
            'positive-text': 'The deterministic Point Mask adapter supports Points only.',
            'negative-text': 'The deterministic Point Mask adapter supports Points only.',
        },
    }
    encoded = json.dumps(
        payload, separators=(',', ':'), sort_keys=True, allow_nan=False
    ).encode('utf-8')
    return {
        **payload,
        'capabilityDigest': f'sha256:{hashlib.sha256(encoded).hexdigest()}',
    }


def _prompt_capabilities_for_adapter(adapter_id: object) -> dict[str, object]:
    if adapter_id == SAM3_IMAGE_INSTANCE_ADAPTER_ID:
        return sam3_image_instance_capabilities()
    if adapter_id == 'point-mask-v1':
        return _point_prompt_capabilities()
    # The legacy sam3.1 Multiplex fixture has no current Prompt capability
    # contract; its manifest fails closed on the mask-proposals route here.
    raise MaskSessionError(
        'incompatibleManifest',
        'The selected Model Manifest has no supported Prompt capability contract.',
    )


@dataclass
class CompanionState:
    directory: Path
    requested_active_model_manifest_digest: str | None = None
    _readiness_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _session_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _scene_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _frame_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _mask_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _active_object_selection_session: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _active_anchor_render: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _anchor_render_admissions: dict[str, AnchorRenderAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active_mask_request: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _mask_admissions: dict[str, MaskRequestAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active_support_probe: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _support_probe_admissions: dict[str, SupportProbeAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active_target_geometry_hint: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _target_geometry_hint_admissions: dict[str, TargetGeometryHintAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active_local_key_view_plan: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _local_key_view_plan_admissions: dict[str, LocalKeyViewPlanAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active_generated_view_mask: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _generated_view_mask_admissions: dict[str, GeneratedViewMaskAdmission] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _scene_snapshots: dict[tuple[str, str], RegisteredSceneSnapshot] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _binary_scene_snapshot_uploads: BinarySceneSnapshotUploadStore = field(
        init=False,
        repr=False,
    )
    _spatial_scene_store: SpatialSceneStore = field(
        init=False,
        repr=False,
    )
    _frame_sets: dict[str, RegisteredFrameSet] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _mask_sessions: dict[str, ActiveMaskSession] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    # Immutable authoritative RGB reference cache: digest -> (png, width,
    # height). Populated by anchor-render output and artifact-carrying
    # proposal requests; digest-only requests resolve against it. Guarded by
    # _session_lock; never held across model work.
    _rgb_cache: dict[str, tuple[bytes, int, int]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    # Companion-local previous-prediction logits store keyed by opaque
    # stateId. Entries mint only on a successful proposal publication path
    # and are cleared with the other transient caches. Guarded by
    # _session_lock; never held across model work.
    _logits_store: dict[str, dict[str, Any]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _adapter_runtime_digests: dict[str, str] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    mask_adapters: dict[str, PromptableMaskAdapter] = field(
        default_factory=lambda: {
            "sam3.1": Sam3PointMaskAdapter(),
            SAM3_IMAGE_INSTANCE_ADAPTER_ID: Sam3ImageInstanceAdapter(),
        },
        repr=False,
    )
    contributor_renderer: ContributorRenderer | None = field(
        default_factory=production_gsplat_renderer,
        repr=False,
    )
    renderer_runtime: RendererRuntime = field(
        default_factory=current_renderer_runtime,
        repr=False,
    )
    generated_view_policy: GeneratedViewPolicy = field(
        default_factory=GeneratedViewPolicy,
        repr=False,
    )
    _companion_instance_id: str = field(init=False, repr=False)
    _process_release_identity: dict[str, str] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _active_model_manifest: dict[str, Any] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._companion_instance_id = secrets.token_urlsafe(24)
        self._binary_scene_snapshot_uploads = BinarySceneSnapshotUploadStore(
            self.directory / "runtime-scene-snapshots"
        )
        self._spatial_scene_store = SpatialSceneStore(
            self.directory / "runtime-spatial-scene-snapshots"
        )

    @property
    def release_path(self) -> Path:
        return self.directory / "release.json"

    @property
    def models_path(self) -> Path:
        return self.directory / "models.json"

    def install_release(self, release: str, lock_file: Path) -> None:
        if not release.strip():
            raise ValueError("release must not be empty")
        if not lock_file.is_file():
            raise ValueError(f"locked dependency file does not exist: {lock_file}")

        lock_digest = _sha256(lock_file)
        _write_json(
            self.release_path,
            {
                "release": release,
                "lockDigest": f"sha256:{lock_digest}",
                "lockFile": str(lock_file.resolve()),
                "installedAt": datetime.now(UTC).isoformat(),
            },
        )

    def require_release(self) -> dict[str, str]:
        release = _read_json(self.release_path, None)
        if (
            not isinstance(release, dict)
            or not isinstance(release.get("release"), str)
            or not isinstance(release.get("lockDigest"), str)
            or not isinstance(release.get("lockFile"), str)
        ):
            raise ValueError("no locked Companion release is installed; run selection-service install first")

        lock_file = Path(release["lockFile"])
        try:
            expected_digest = _normalise_sha256(release["lockDigest"], "lockDigest")
            actual_digest = _sha256(lock_file)
        except (OSError, ValueError) as error:
            raise ValueError(
                "the installed Companion release lock cannot be verified; run selection-service install again"
            ) from error
        if actual_digest != expected_digest:
            raise ValueError(
                "the installed Companion release lock changed; run selection-service install again"
            )
        return {
            "release": release["release"],
            "lockDigest": f"sha256:{expected_digest}",
            "lockFile": str(lock_file),
        }

    def install_model(self, manifest_path: Path, weights_path: Path) -> dict[str, Any]:
        if not weights_path.is_file():
            raise ValueError(f"model weights do not exist: {weights_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"model manifest does not exist: {manifest_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"model manifest is not valid JSON: {manifest_path}") from error

        if not isinstance(manifest, dict):
            raise ValueError("model manifest must be a JSON object")

        required = (
            "digest",
            "adapterId",
            "modelName",
            "checkpointDigest",
            "sourceCommit",
            "licenseName",
            "licenseUrl",
            "runtimeConfigDigest",
        )
        missing = [key for key in required if not isinstance(manifest.get(key), str) or not manifest[key].strip()]
        if missing:
            raise ValueError(f"model manifest is missing required fields: {', '.join(missing)}")
        if (
            manifest["adapterId"] == "sam3.1"
            and manifest["runtimeConfigDigest"] != SAM31_RUNTIME_CONFIG_DIGEST
        ):
            raise ValueError(
                "the SAM 3.1 Model Manifest runtimeConfigDigest does not match the pinned Companion runtime configuration"
            )
        if (
            manifest["adapterId"] == SAM3_IMAGE_INSTANCE_ADAPTER_ID
            and manifest["runtimeConfigDigest"] != SAM3_IMAGE_RUNTIME_CONFIG_DIGEST
        ):
            raise ValueError(
                "the SAM 3 Image Model Manifest runtimeConfigDigest does not match the pinned Companion runtime configuration"
            )

        expected_digest = _normalise_sha256(manifest["checkpointDigest"])
        actual_digest = _sha256(weights_path)
        if actual_digest != expected_digest:
            raise ValueError("model checkpoint digest does not match the supplied Model Manifest")

        model = {
            "digest": manifest["digest"],
            "adapterId": manifest["adapterId"],
            "modelName": manifest["modelName"],
            "checkpointDigest": f"sha256:{actual_digest}",
            "sourceCommit": manifest["sourceCommit"],
            "licenseName": manifest["licenseName"],
            "licenseUrl": manifest["licenseUrl"],
            "runtimeConfigDigest": manifest["runtimeConfigDigest"],
            "weightsPath": str(weights_path.resolve()),
            "weightsBundled": False,
            "installedAt": datetime.now(UTC).isoformat(),
        }
        models = self.models()
        existing = next(
            (available for available in models if available.get("digest") == model["digest"]),
            None,
        )
        if existing is not None:
            if any(
                existing.get(field) != model[field]
                for field in MODEL_MANIFEST_IDENTITY_FIELDS
            ):
                raise ValueError(
                    "a Model Manifest digest is immutable and cannot be reinstalled with different content"
                )
            # A second verified copy of the same checkpoint may restore a
            # missing artifact at a new path, but cannot alter the manifest
            # identity pinned by active sessions.
            model = {
                **existing,
                "weightsPath": model["weightsPath"],
                "weightsBundled": False,
                "installedAt": model["installedAt"],
            }
            models = [
                model if available.get("digest") == model["digest"] else available
                for available in models
            ]
        else:
            models.append(model)
        _write_json(self.models_path, models)
        return model

    def models(self) -> list[dict[str, Any]]:
        models = _read_json(self.models_path, [])
        if not isinstance(models, list):
            return []
        return [model for model in models if isinstance(model, dict)]

    def available_models(self) -> list[dict[str, Any]]:
        return [
            model
            for model in self.models()
            if (
                self._model_artifact_is_current(model)
                and self._model_runtime_configuration_is_current(model)
            )
        ]

    def configure_active_model_manifest(self, digest: str | None) -> None:
        if digest is not None and not digest.strip():
            raise ValueError("active Model Manifest digest must not be empty")
        with self._readiness_lock:
            if self._active_model_manifest is not None:
                raise ValueError(
                    "the process-lifetime Active Model Manifest is already resolved"
                )
            self.requested_active_model_manifest_digest = digest

    def _process_release(self) -> dict[str, str]:
        with self._readiness_lock:
            cached = self._process_release_identity
        if cached is not None:
            return dict(cached)
        release = self.require_release()
        with self._readiness_lock:
            if self._process_release_identity is None:
                self._process_release_identity = dict(release)
            return dict(self._process_release_identity)

    def health(self) -> dict[str, str]:
        release = self._process_release()
        return {
            "status": "ok",
            "serviceBuild": (
                f"selection-service-companion/{PACKAGE_VERSION}"
                f"+{release['release']}"
            ),
            "companionInstanceId": self._companion_instance_id,
        }

    def resolve_active_model_manifest(self) -> dict[str, Any]:
        with self._readiness_lock:
            active = self._active_model_manifest
            requested_digest = self.requested_active_model_manifest_digest
        if active is not None:
            if (
                self._model_artifact_is_current(active)
                and self._model_runtime_configuration_is_current(active)
            ):
                return dict(active)
            raise ValueError(
                "the process-lifetime Active Model Manifest is no longer available"
            )

        available = self.available_models()
        if requested_digest is None:
            if len(available) == 0:
                raise ValueError(
                    "no compatible installed Model Manifest is available"
                )
            if len(available) != 1:
                raise ValueError(
                    "multiple compatible Model Manifests are installed; "
                    "the operator must choose one at Companion startup"
                )
            selected = available[0]
        else:
            selected = next(
                (
                    model
                    for model in available
                    if model.get("digest") == requested_digest
                ),
                None,
            )
            if selected is None:
                raise ValueError(
                    "the operator-selected Active Model Manifest is unavailable"
                )

        with self._readiness_lock:
            if self._active_model_manifest is None:
                self._active_model_manifest = dict(selected)
            return dict(self._active_model_manifest)

    def runtime_profile_capabilities(
        self,
        allowed_editor_origins: list[str],
    ) -> dict[str, Any]:
        release = self._process_release()
        model = self.resolve_active_model_manifest()
        provider = self._image_instance_provider_capability(model)
        return {
            "protocolVersion": AI_SELECT_READINESS_PROTOCOL_VERSION,
            "serviceBuild": (
                f"selection-service-companion/{PACKAGE_VERSION}"
                f"+{release['release']}"
            ),
            "companionInstanceId": self._companion_instance_id,
            "runtimeProfileId": AI_SELECT_RUNTIME_PROFILE_ID,
            "renderer": self._renderer_capability(release),
            "imageInstanceProvider": provider,
            "supportedOperations": [
                "aiSelectAnchorRender",
                "aiSelectAnchorReferenceContributor",
                "aiSelectAnchorSupportProbe",
                "aiSelectMaskProposals",
                "autoMaskProposalSetSchemaV3",
                "aiSelectTargetGeometryHint",
                "aiSelectLocalKeyViewPlanning",
                "binarySceneSnapshotRegistrationV1",
                "cameraAwareSpatialWorkingSetV1",
            ],
            "activeModelManifest": {
                "digest": model["digest"],
                "adapterId": model["adapterId"],
                "modelName": model["modelName"],
                "checkpointDigest": model["checkpointDigest"],
                "sourceCommit": model["sourceCommit"],
                "runtimeConfigDigest": model["runtimeConfigDigest"],
                "weightsBundled": False,
                "initialized": provider["status"] == "ready",
            },
            "allowedEditorOrigins": allowed_editor_origins,
        }

    def _image_instance_provider_capability(
        self,
        model: Mapping[str, Any],
    ) -> dict[str, Any]:
        adapter_id = str(model.get("adapterId", ""))
        adapter = self.mask_adapters.get(adapter_id)
        capability_factory = getattr(
            adapter,
            "runtime_profile_capability",
            None,
        )
        if (
            adapter_id == SAM3_IMAGE_INSTANCE_ADAPTER_ID
            and callable(capability_factory)
        ):
            capability = capability_factory(model)
            if not isinstance(capability, Mapping):
                raise ValueError(
                    "the SAM 3 Image adapter returned an invalid Runtime Profile capability"
                )
            authoritative_rgb = capability.get("authoritativeRgb")
            prompt_capabilities = capability.get("promptCapabilities")
            prompt_keys = (
                "positivePoints",
                "negativePoints",
                "positiveInstanceBox",
                "previousLogitsRefinement",
                "singlePointMultimask",
                "negativeBox",
                "promptBrush",
                "maskConstraints",
                "text",
            )
            if (
                capability.get("status") not in ("ready", "unavailable")
                or not isinstance(authoritative_rgb, Mapping)
                or not all(
                    isinstance(authoritative_rgb.get(key), bool)
                    for key in ("artifact", "companionReference")
                )
                or not isinstance(prompt_capabilities, Mapping)
                or not all(
                    isinstance(prompt_capabilities.get(key), bool)
                    for key in prompt_keys
                )
            ):
                raise ValueError(
                    "the SAM 3 Image adapter returned an incomplete Runtime Profile capability"
                )
            result = {
                "status": capability["status"],
                "adapterId": adapter_id,
                "authoritativeRgb": {
                    "artifact": authoritative_rgb["artifact"],
                    "companionReference": authoritative_rgb[
                        "companionReference"
                    ],
                },
                "promptCapabilities": {
                    key: prompt_capabilities[key]
                    for key in prompt_keys
                },
            }
            if capability["status"] == "ready":
                # The editor rebuilds its Prompt adapter capability record from
                # these pass-through identities; a ready provider must bind the
                # exact compiler policy and capability digest.
                compiler_policy_version = capability.get("compilerPolicyVersion")
                adapter_capability_digest = capability.get(
                    "adapterCapabilityDigest"
                )
                if (
                    not isinstance(compiler_policy_version, str)
                    or not compiler_policy_version.strip()
                    or not isinstance(adapter_capability_digest, str)
                    or not adapter_capability_digest.startswith("sha256:")
                ):
                    raise ValueError(
                        "the SAM 3 Image adapter returned an incomplete Runtime Profile capability"
                    )
                result["compilerPolicyVersion"] = compiler_policy_version
                result["adapterCapabilityDigest"] = adapter_capability_digest
            message = capability.get("message")
            if isinstance(message, str):
                result["message"] = message
            return result

        # Any non-current adapter (including the legacy sam3.1 Multiplex
        # benchmark fixture) remains truthfully unavailable for the current
        # static instance-segmentation profile.
        return {
            "status": "unavailable",
            "adapterId": adapter_id,
            "authoritativeRgb": {
                "artifact": True,
                "companionReference": False,
            },
            "promptCapabilities": {
                "positivePoints": True,
                "negativePoints": True,
                "positiveInstanceBox": True,
                "previousLogitsRefinement": False,
                "singlePointMultimask": False,
                "negativeBox": False,
                "promptBrush": False,
                "maskConstraints": False,
                "text": False,
            },
            "message": (
                "The installed static adapter is not the current "
                f"{SAM3_IMAGE_INSTANCE_ADAPTER_ID} provider."
            ),
        }

    def open_object_selection_session(
        self,
        *,
        frame_set_version: str | None = None,
        model_manifest_digest: str | None = None,
        open_request_id: str | None = None,
    ) -> str | None:
        if (frame_set_version is None) != (model_manifest_digest is None):
            raise MaskSessionError(
                "invalidMaskSession",
                "Object Selection mask sessions require both Frame Set and Model Manifest bindings.",
            )
        if open_request_id is not None and (
            not isinstance(open_request_id, str) or not open_request_id.strip()
        ):
            raise MaskSessionError(
                "invalidMaskSession",
                "Object Selection session openRequestId must be a non-empty string.",
            )
        with self._session_lock:
            if self._active_object_selection_session is not None:
                session_id = self._active_object_selection_session
                with self._mask_lock:
                    session = self._mask_sessions.get(session_id)
                    if (
                        session is not None
                        and not session.closing
                        and open_request_id is not None
                        and session.open_request_id == open_request_id
                    ):
                        if (
                            session.frame_set_version != frame_set_version
                            or session.model_manifest_digest != model_manifest_digest
                        ):
                            raise MaskSessionError(
                                "openRequestIdConflict",
                                "A repeated Object Selection openRequestId must replay its original Frame Set and Model Manifest bindings.",
                            )
                        return session_id
                self._discard_unclaimed_frame_set(frame_set_version)
                return None
            if self._active_anchor_render is not None:
                self._discard_unclaimed_frame_set(frame_set_version)
                return None
            if self._active_mask_request is not None:
                self._discard_unclaimed_frame_set(frame_set_version)
                return None
            try:
                if frame_set_version is not None:
                    self._require_frame_set(frame_set_version)
                    self._require_mask_adapter(model_manifest_digest)
            except MaskSessionError:
                self._discard_unclaimed_frame_set(frame_set_version)
                raise
            session_id = secrets.token_urlsafe(24)
            self._active_object_selection_session = session_id
            with self._mask_lock:
                self._mask_sessions[session_id] = ActiveMaskSession(
                    frame_set_version=frame_set_version,
                    model_manifest_digest=model_manifest_digest,
                    open_request_id=open_request_id,
                )
        return session_id

    def close_object_selection_session(self, session_id: str) -> bool:
        with self._session_lock:
            return self._close_active_session_locked(session_id)

    def close_object_selection_session_for_open_request(self, open_request_id: str) -> bool:
        """Idempotently close the active session claimed by an open request.

        The browser uses this recovery path when a successful admission response
        is lost before it learns the generated session ID.
        """

        with self._session_lock:
            session_id = self._active_object_selection_session
            if session_id is None:
                return False
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if session is None or session.open_request_id != open_request_id:
                    return False
            return self._close_active_session_locked(session_id)

    def has_object_selection_session(self, session_id: str) -> bool:
        with self._session_lock:
            return self._active_object_selection_session == session_id

    def register_scene_snapshot(self, snapshot: dict[str, Any]) -> None:
        scene_id, scene_version, stable_ids, render_config_version = self._validate_scene_snapshot(snapshot)
        canonical = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
        key = (scene_id, scene_version)
        with self._scene_lock:
            existing = self._scene_snapshots.get(key)
            if existing is not None and existing.identity != canonical:
                raise ValueError(
                    "a Scene Snapshot version is immutable and cannot be registered with different content"
                )
            self._scene_snapshots[key] = RegisteredSceneSnapshot(
                # Legacy JSON fixture compatibility retains an isolated parsed
                # copy. Binary AI Select registrations never take this path.
                scene=json.loads(canonical),
                stable_ids=tuple(sorted(stable_ids)),
                render_config_version=render_config_version,
                identity=canonical,
            )

    def begin_binary_scene_snapshot_upload(
        self, manifest: BinarySceneSnapshotManifest
    ) -> SnapshotUploadAdmission:
        key = (manifest.scene_id, manifest.scene_version)
        expected_identity = f"binary:{manifest.content_digest}"
        with self._scene_lock:
            existing = self._scene_snapshots.get(key)
            if existing is not None and existing.identity != expected_identity:
                raise ImmutableSnapshotConflict(
                    "a Scene Snapshot version is immutable and cannot be registered with different content"
                )
        return self._binary_scene_snapshot_uploads.begin(manifest)

    def accept_binary_scene_snapshot_chunk(
        self, upload_id: str, index: int, payload: bytes, digest: str
    ) -> str:
        return self._binary_scene_snapshot_uploads.accept_chunk(
            upload_id, index, payload, digest
        )

    def commit_binary_scene_snapshot_upload(
        self, upload_id: str
    ) -> SnapshotUploadCommit:
        commit = self._binary_scene_snapshot_uploads.commit_result(upload_id)
        packed = commit.snapshot
        key = (packed.scene_id, packed.scene_version)
        identity = f"binary:{packed.content_digest}"
        with self._scene_lock:
            existing = self._scene_snapshots.get(key)
            if existing is not None and existing.identity != identity:
                raise ValueError(
                    "a Scene Snapshot version is immutable and cannot be registered with different content"
                )
            self._scene_snapshots[key] = RegisteredSceneSnapshot(
                scene=packed,
                stable_ids=packed.stable_ids(),
                render_config_version=packed.render_config_version,
                identity=identity,
            )
        return commit

    def abort_binary_scene_snapshot_upload(self, upload_id: str) -> None:
        self._binary_scene_snapshot_uploads.abort(upload_id)

    def cleanup_expired_binary_scene_snapshot_uploads(self) -> int:
        return self._binary_scene_snapshot_uploads.cleanup_expired()

    def register_spatial_scene_manifest(
        self, manifest: SpatialSceneManifest
    ) -> SpatialManifestRegistration:
        key = (manifest.scene_id, manifest.scene_version)
        expected_binary_identity = f"binary:{manifest.content_digest}"
        with self._scene_lock:
            existing = self._scene_snapshots.get(key)
            if existing is not None and existing.identity != expected_binary_identity:
                raise ImmutableSnapshotConflict(
                    "a Spatial Scene manifest cannot reinterpret an existing Scene Snapshot version"
                )
        return self._spatial_scene_store.register_manifest(manifest)

    def begin_spatial_scene_chunk_upload(
        self,
        scene_id: str,
        scene_version: str,
        chunk_ids: tuple[str, ...],
    ) -> SpatialChunkUploadAdmission:
        return self._spatial_scene_store.begin_chunk_upload(
            scene_id, scene_version, chunk_ids
        )

    def accept_spatial_scene_chunk(
        self, upload_id: str, chunk_id: str, payload: bytes, digest: str
    ) -> str:
        return self._spatial_scene_store.accept_chunk(
            upload_id, chunk_id, payload, digest
        )

    def commit_spatial_scene_chunk_upload(
        self, upload_id: str
    ) -> SpatialChunkUploadCommit:
        return self._spatial_scene_store.commit_chunk_upload(upload_id)

    def abort_spatial_scene_chunk_upload(self, upload_id: str) -> None:
        self._spatial_scene_store.abort_chunk_upload(upload_id)

    def cleanup_expired_spatial_scene_chunk_uploads(self) -> int:
        return self._spatial_scene_store.cleanup_expired()

    def release_spatial_scene_manifest(self, registration_id: str) -> None:
        self._spatial_scene_store.release_manifest(registration_id)

    def scene_snapshot(
        self, scene_id: str, scene_version: str
    ) -> RegisteredSceneSnapshot | None:
        with self._scene_lock:
            return self._scene_snapshots.get((scene_id, scene_version))

    def scene_snapshot_stable_ids(
        self, scene_id: str, scene_version: str
    ) -> tuple[int, ...] | memoryview | None:
        snapshot = self.scene_snapshot(scene_id, scene_version)
        return snapshot.stable_ids if snapshot is not None else None

    def render_ai_select_anchor(
        self,
        request: Mapping[str, object],
        *,
        timing: AnchorServerTiming | None = None,
    ) -> dict[str, object]:
        """Publish the authoritative Anchor RGB product or a bound cache miss."""

        return self._render_ai_select_view(
            request, expected_view_id='anchor-view', timing=timing
        )

    def render_ai_select_view(
        self,
        request: Mapping[str, object],
        *,
        timing: AnchorServerTiming | None = None,
    ) -> dict[str, object]:
        """Publish one planner-owned Generated View RGB or a bound cache miss.

        This is the Anchor render contract with a planner-owned viewId; the
        Anchor route keeps its strict ``anchor-view`` reservation.
        """

        return self._render_ai_select_view(
            request, expected_view_id=None, timing=timing
        )

    def _render_ai_select_view(
        self,
        request: Mapping[str, object],
        *,
        expected_view_id: str | None,
        timing: AnchorServerTiming | None = None,
    ) -> dict[str, object]:
        """Publish one authoritative AI View RGB product or a bound cache miss.

        The browser owns target and Scene Snapshot identity. This state method
        validates those untrusted bindings, copies the camera into gsplat's
        explicit convention, then releases all state locks before GPU work.
        """

        anchor_timing = timing or AnchorServerTiming()
        anchor_request = self._parse_ai_select_anchor_request(
            request, expected_view_id
        )
        scene_snapshot: Mapping[str, Any] | PackedBinarySceneSnapshot | SpatialWorkingSet
        with anchor_timing.measure('working-set'):
            if anchor_request.scene_transport == 'spatial-v1':
                try:
                    resolution = self._spatial_scene_store.resolve_working_set(
                        anchor_request.scene_id,
                        anchor_request.scene_version,
                        anchor_request.camera_binding,
                    )
                except SnapshotUploadError:
                    return {
                        'status': 'sceneCacheMiss',
                        **anchor_request.response_fields(),
                    }
                if resolution.missing_chunk_ids:
                    return {
                        'status': 'sceneChunkMiss',
                        **anchor_request.response_fields(),
                        'workingSetToken': resolution.working_set_token,
                        'missingChunkIds': list(resolution.missing_chunk_ids),
                    }
                if resolution.working_set is None:
                    raise ValueError(
                        'AI Select Anchor Spatial Scene working set is incomplete'
                    )
                render_configuration = resolution.working_set.manifest.render_configuration
                if (
                    render_configuration.get('version')
                    != anchor_request.render_config_version
                ):
                    raise ValueError(
                        'AI Select Anchor render configuration does not match the registered Spatial Scene manifest'
                    )
                scene_snapshot = resolution.working_set
            else:
                snapshot = self.scene_snapshot(
                    anchor_request.scene_id, anchor_request.scene_version
                )
                if snapshot is None:
                    return {
                        'status': 'sceneCacheMiss',
                        **anchor_request.response_fields(),
                    }
                if snapshot.render_config_version != anchor_request.render_config_version:
                    raise ValueError(
                        'AI Select Anchor render configuration does not match the registered Scene Snapshot'
                    )
                scene_snapshot = snapshot.scene

        renderer = self._require_contributor_renderer()
        if getattr(renderer, 'renderer_id', None) != 'gsplat':
            raise MaskSessionError(
                'rendererUnavailable',
                'The configured Contributor renderer is not the gsplat Anchor renderer.',
            )
        render_anchor = getattr(renderer, 'render_anchor', None)
        if not callable(render_anchor):
            raise MaskSessionError(
                'rendererUnavailable',
                'The gsplat/CUDA Contributor renderer cannot render an AI Select Anchor.',
            )

        with anchor_timing.measure('gpu-queue'):
            anchor_key, admission, owns_admission = self._admit_anchor_render(
                anchor_request
            )
            if not owns_admission:
                return self._replay_anchor_render(admission)

        try:
            try:
                if isinstance(renderer, GsplatContributorRenderer):
                    artifact = render_anchor(
                        scene_snapshot=scene_snapshot,
                        view_id=anchor_request.view_id,
                        camera=anchor_request.renderer_camera,
                        width=anchor_request.width,
                        height=anchor_request.height,
                        timing=anchor_timing,
                        include_reference_contributor=(
                            anchor_request.reference_contributor
                        ),
                    )
                else:
                    # Contract fixtures and compatibility renderers preserve
                    # the old narrow method signature. They still report the
                    # total renderer interval, while the locked production
                    # renderer exposes its PNG and digest subphases itself.
                    with anchor_timing.measure('gsplat'):
                        artifact = render_anchor(
                            scene_snapshot=scene_snapshot,
                            view_id=anchor_request.view_id,
                            camera=anchor_request.renderer_camera,
                            width=anchor_request.width,
                            height=anchor_request.height,
                        )
            except MaskSessionError:
                raise
            except Exception as error:
                raise MaskSessionError(
                    'rendererFailure',
                    'The gsplat/CUDA renderer failed while producing the AI Select Anchor.',
                ) from error
            if not isinstance(artifact, AnchorRenderArtifact):
                raise MaskSessionError(
                    'rendererFailure',
                    'The gsplat/CUDA renderer returned an invalid AI Select Anchor artifact.',
                )
            # Authoritative nonblank gate (view-renders only): a planned Key
            # View whose raster alpha covers nothing fails closed before any
            # RGB publishes. The Anchor route never takes this branch.
            if (
                expected_view_id is None
                and artifact.alpha_coverage is not None
                and artifact.alpha_coverage < _BLANK_RENDER_MIN_ALPHA_COVERAGE
            ):
                raise MaskSessionError(
                    'blankRender',
                    'The authoritative gsplat render is blank for the planned Key View.',
                )
            with anchor_timing.measure('json-base64'):
                response = {
                    'status': 'complete',
                    **anchor_request.response_fields(),
                    'rgb': {
                        'pngBase64': base64.b64encode(artifact.image_png).decode('ascii'),
                        'digest': _anchor_digest(artifact.rgb_digest, 'RGB digest'),
                        'width': anchor_request.width,
                        'height': anchor_request.height,
                    },
                    'rgbRendererVersion': AI_SELECT_RGB_RENDERER_VERSION,
                    'rendererId': 'gsplat',
                }
                if anchor_request.reference_contributor:
                    # The explicit debug/reference capability reports its own
                    # outcome beside the RGB; its failure never converts the
                    # successful authoritative render into a Preview Failure.
                    if artifact.reference_contributor_error is not None:
                        response['referenceContributorError'] = (
                            artifact.reference_contributor_error
                        )
                    elif artifact.contributor_digest is not None:
                        response['referenceContributorDigest'] = _anchor_digest(
                            artifact.contributor_digest,
                            'reference contributor digest',
                        )
                    else:
                        response['referenceContributorError'] = (
                            'rendererUnavailable: The renderer did not produce a reference Contributor artifact.'
                        )
        except MaskSessionError as error:
            self._complete_anchor_render(
                anchor_key, admission, failure=error, timing=anchor_timing
            )
            raise
        except Exception as error:
            failure = MaskSessionError(
                'rendererFailure',
                'The gsplat/CUDA renderer failed while publishing the AI Select Anchor.',
            )
            self._complete_anchor_render(
                anchor_key, admission, failure=failure, timing=anchor_timing
            )
            raise failure from error

        self._cache_rgb(
            _anchor_digest(artifact.rgb_digest, 'RGB digest'),
            artifact.image_png,
            anchor_request.width,
            anchor_request.height,
        )
        self._complete_anchor_render(
            anchor_key, admission, response=response, timing=anchor_timing
        )
        return response

    def _parse_ai_select_anchor_request(
        self,
        request: Mapping[str, object],
        expected_view_id: str | None = 'anchor-view',
    ) -> AISelectAnchorRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select Anchor requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select Anchor requestBinding dependencyToken must be an object'
            )
        target_splat_id = _anchor_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _anchor_string(dependency_value.get('splatId'), 'dependency splatId'),
            'renderStateToken': _anchor_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _anchor_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _anchor_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _anchor_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select Anchor targetSplatId must match its dependency splatId'
            )
        request_binding: dict[str, object] = {
            'targetContextId': _anchor_string(
                request_binding_value.get('targetContextId'), 'targetContextId'
            ),
            'contextRevision': _anchor_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        scene_id = _anchor_string(request.get('sceneId'), 'sceneId')
        scene_version = _anchor_string(request.get('sceneVersion'), 'sceneVersion')
        if scene_id != target_splat_id:
            raise ValueError(
                'AI Select Anchor sceneId must match its targetSplatId'
            )
        render_config_version = _anchor_string(
            request.get('renderConfigVersion'), 'renderConfigVersion'
        )
        render_attempt_id = _anchor_string(
            request.get('renderAttemptId'), 'renderAttemptId'
        )
        view_id_value = request.get('viewId')
        if expected_view_id is not None:
            if view_id_value != expected_view_id:
                raise ValueError(
                    f'AI Select Anchor viewId must be {expected_view_id}'
                )
            view_id = expected_view_id
        else:
            if not isinstance(view_id_value, str) or not view_id_value:
                raise ValueError('AI Select View viewId must be a non-empty string')
            if view_id_value == 'anchor-view':
                raise ValueError(
                    'AI Select View viewId anchor-view is reserved for the Anchor route'
                )
            view_id = view_id_value
        scene_transport = request.get('sceneTransport', 'packed-v1')
        if scene_transport not in ('packed-v1', 'spatial-v1'):
            raise ValueError('AI Select Anchor sceneTransport is unsupported')
        reference_contributor = request.get('referenceContributor', False)
        if not isinstance(reference_contributor, bool):
            raise ValueError(
                'AI Select Anchor referenceContributor must be an explicit boolean'
            )

        camera_binding, renderer_camera, width, height = (
            self._parse_ai_select_anchor_camera(request.get('cameraBinding'))
        )
        return AISelectAnchorRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            scene_id=scene_id,
            scene_version=scene_version,
            render_config_version=render_config_version,
            render_attempt_id=render_attempt_id,
            camera_binding=camera_binding,
            renderer_camera=renderer_camera,
            width=width,
            height=height,
            view_id=view_id,
            scene_transport=scene_transport,
            reference_contributor=reference_contributor,
        )

    @staticmethod
    def _parse_ai_select_anchor_camera(
        value: object,
    ) -> tuple[dict[str, object], dict[str, object], int, int]:
        if not isinstance(value, dict):
            raise ValueError('AI Select Anchor cameraBinding must be an object')
        if value.get('conventionVersion') != 'opencv-camera-to-world/v1':
            raise ValueError(
                'AI Select Anchor cameraBinding conventionVersion is unsupported'
            )
        revision = _anchor_nonnegative_integer(value.get('revision'), 'camera revision')
        camera_to_world = _anchor_number_sequence(
            value.get('cameraToWorld'), 16, 'cameraToWorld'
        )
        if camera_to_world[12:] != (0.0, 0.0, 0.0, 1.0):
            raise ValueError('AI Select Anchor cameraToWorld must be affine')
        rotation_rows = (
            camera_to_world[0:3],
            camera_to_world[4:7],
            camera_to_world[8:11],
        )
        for row in rotation_rows:
            if abs(sum(component * component for component in row) - 1.0) > 1e-5:
                raise ValueError('AI Select Anchor cameraToWorld rotation must be unit length')
        for first, second in ((0, 1), (0, 2), (1, 2)):
            if abs(
                sum(
                    rotation_rows[first][axis] * rotation_rows[second][axis]
                    for axis in range(3)
                )
            ) > 1e-5:
                raise ValueError('AI Select Anchor cameraToWorld rotation must be orthogonal')
        determinant = (
            rotation_rows[0][0]
            * (rotation_rows[1][1] * rotation_rows[2][2] - rotation_rows[1][2] * rotation_rows[2][1])
            - rotation_rows[0][1]
            * (rotation_rows[1][0] * rotation_rows[2][2] - rotation_rows[1][2] * rotation_rows[2][0])
            + rotation_rows[0][2]
            * (rotation_rows[1][0] * rotation_rows[2][1] - rotation_rows[1][1] * rotation_rows[2][0])
        )
        if abs(determinant - 1.0) > 1e-5:
            raise ValueError(
                'AI Select Anchor cameraToWorld rotation must be right-handed'
            )

        projection_value = value.get('projection')
        if not isinstance(projection_value, dict) or projection_value.get('model') != 'pinhole':
            raise ValueError('AI Select Anchor projection must be a pinhole object')
        fx = _anchor_finite_number(projection_value.get('fx'), 'projection fx')
        fy = _anchor_finite_number(projection_value.get('fy'), 'projection fy')
        cx = _anchor_finite_number(projection_value.get('cx'), 'projection cx')
        cy = _anchor_finite_number(projection_value.get('cy'), 'projection cy')
        width = _anchor_positive_integer(projection_value.get('width'), 'projection width')
        height = _anchor_positive_integer(projection_value.get('height'), 'projection height')
        near = _anchor_finite_number(projection_value.get('near'), 'projection near')
        far = _anchor_finite_number(projection_value.get('far'), 'projection far')
        if fx <= 0 or fy <= 0 or near <= 0 or far <= near:
            raise ValueError('AI Select Anchor projection is invalid')

        tx, ty, tz = camera_to_world[3], camera_to_world[7], camera_to_world[11]
        world_to_camera = [
            camera_to_world[0], camera_to_world[4], camera_to_world[8],
            -(camera_to_world[0] * tx + camera_to_world[4] * ty + camera_to_world[8] * tz),
            camera_to_world[1], camera_to_world[5], camera_to_world[9],
            -(camera_to_world[1] * tx + camera_to_world[5] * ty + camera_to_world[9] * tz),
            camera_to_world[2], camera_to_world[6], camera_to_world[10],
            -(camera_to_world[2] * tx + camera_to_world[6] * ty + camera_to_world[10] * tz),
            0.0, 0.0, 0.0, 1.0,
        ]
        camera_binding: dict[str, object] = {
            'revision': revision,
            'cameraToWorld': list(camera_to_world),
            'projection': {
                'model': 'pinhole',
                'fx': fx,
                'fy': fy,
                'cx': cx,
                'cy': cy,
                'width': width,
                'height': height,
                'near': near,
                'far': far,
            },
            'conventionVersion': 'opencv-camera-to-world/v1',
        }
        renderer_camera: dict[str, object] = {
            'model': 'pinhole',
            'convention': 'opencv-world-to-camera',
            'worldToCamera': world_to_camera,
            'intrinsics': [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0],
            'nearPlane': near,
            'farPlane': far,
        }
        return camera_binding, renderer_camera, width, height

    def probe_ai_select_anchor_support(
        self, request: Mapping[str, object]
    ) -> dict[str, object]:
        """Publish one mask-conditioned Gaussian support computability verdict.

        The probe is the cheap Confirm Anchor gate, not Evidence and not a
        Contributor artifact: it reuses the Anchor scene resolution seam,
        reserves the single Companion operation slot, then runs the pure-CPU
        projection loop outside every state lock. The published answer is only
        ``computable`` plus its diagnostic count — never Stable Gaussian IDs.
        """

        probe_request = self._parse_ai_select_support_probe_request(request)
        planes: list[tuple[memoryview, memoryview]] = []
        if probe_request.scene_transport == 'spatial-v1':
            try:
                resolution = self._spatial_scene_store.resolve_working_set(
                    probe_request.scene_id,
                    probe_request.scene_version,
                    probe_request.camera_binding,
                )
            except SnapshotUploadError:
                return {
                    'status': 'sceneCacheMiss',
                    **probe_request.response_fields(),
                }
            if resolution.missing_chunk_ids:
                return {
                    'status': 'sceneChunkMiss',
                    **probe_request.response_fields(),
                    'workingSetToken': resolution.working_set_token,
                    'missingChunkIds': list(resolution.missing_chunk_ids),
                }
            if resolution.working_set is None:
                raise ValueError(
                    'AI Select Anchor support probe Spatial Scene working set is incomplete'
                )
            render_configuration = (
                resolution.working_set.manifest.render_configuration
            )
            if (
                render_configuration.get('version')
                != probe_request.render_config_version
            ):
                raise ValueError(
                    'AI Select Anchor support probe render configuration does not match the registered Spatial Scene manifest'
                )
            # Resident chunks expose their immutable mmap planes directly; the
            # probe never materializes the renderer's torch tensor views.
            planes.extend(
                (chunk.field('means'), chunk.field('logitOpacities'))
                for chunk in resolution.working_set.chunks
            )
        else:
            snapshot = self.scene_snapshot(
                probe_request.scene_id, probe_request.scene_version
            )
            if snapshot is None:
                return {
                    'status': 'sceneCacheMiss',
                    **probe_request.response_fields(),
                }
            if snapshot.render_config_version != probe_request.render_config_version:
                raise ValueError(
                    'AI Select Anchor support probe render configuration does not match the registered Scene Snapshot'
                )
            if not isinstance(snapshot.scene, PackedBinarySceneSnapshot):
                raise MaskSessionError(
                    'supportProbeFailure',
                    'AI Select Anchor support probes require a packed binary Scene Snapshot.',
                )
            planes.append(
                (snapshot.scene.field('means'), snapshot.scene.field('logitOpacities'))
            )

        probe_key, admission, owns_admission = self._admit_support_probe(
            probe_request
        )
        if not owns_admission:
            return self._replay_support_probe(admission)

        try:
            try:
                observed_gaussian_count = count_observed_gaussians(
                    planes=planes,
                    camera=probe_request.probe_camera,
                    mask=probe_request.stable_mask,
                )
            except Exception as error:
                raise MaskSessionError(
                    'supportProbeFailure',
                    'The Companion failed while computing the AI Select Anchor support probe.',
                ) from error
            response = {
                'status': 'complete',
                **probe_request.response_fields(),
                'rgbDigest': probe_request.rgb_digest,
                'stableMaskDigest': probe_request.stable_mask_digest,
                'supportProbePolicyVersion': AI_SELECT_SUPPORT_PROBE_POLICY_VERSION,
                'support': {
                    'computable': observed_gaussian_count > 0,
                    'observedGaussianCount': observed_gaussian_count,
                },
            }
        except MaskSessionError as error:
            self._complete_support_probe(probe_key, admission, failure=error)
            raise
        except Exception as error:
            failure = MaskSessionError(
                'supportProbeFailure',
                'The Companion failed while publishing the AI Select Anchor support probe.',
            )
            self._complete_support_probe(probe_key, admission, failure=failure)
            raise failure from error

        self._complete_support_probe(probe_key, admission, response=response)
        return response

    def _parse_ai_select_support_probe_request(
        self, request: Mapping[str, object]
    ) -> AISelectSupportProbeRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select Anchor support probe requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select Anchor support probe requestBinding dependencyToken must be an object'
            )
        target_splat_id = _anchor_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _anchor_string(dependency_value.get('splatId'), 'dependency splatId'),
            'renderStateToken': _anchor_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _anchor_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _anchor_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _anchor_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select Anchor support probe targetSplatId must match its dependency splatId'
            )
        request_binding: dict[str, object] = {
            'targetContextId': _anchor_string(
                request_binding_value.get('targetContextId'), 'targetContextId'
            ),
            'contextRevision': _anchor_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        scene_id = _anchor_string(request.get('sceneId'), 'sceneId')
        scene_version = _anchor_string(request.get('sceneVersion'), 'sceneVersion')
        if scene_id != target_splat_id:
            raise ValueError(
                'AI Select Anchor support probe sceneId must match its targetSplatId'
            )
        render_config_version = _anchor_string(
            request.get('renderConfigVersion'), 'renderConfigVersion'
        )
        support_probe_attempt_id = _anchor_string(
            request.get('supportProbeAttemptId'), 'supportProbeAttemptId'
        )
        if request.get('viewId') != 'anchor-view':
            raise ValueError('AI Select Anchor support probe viewId must be anchor-view')
        rgb_digest = _anchor_sha256_digest(request.get('rgbDigest'), 'support probe rgbDigest')
        if (
            request.get('supportProbePolicyVersion')
            != AI_SELECT_SUPPORT_PROBE_POLICY_VERSION
        ):
            raise ValueError(
                'AI Select Anchor support probe supportProbePolicyVersion is unsupported'
            )
        scene_transport = request.get('sceneTransport', 'packed-v1')
        if scene_transport not in ('packed-v1', 'spatial-v1'):
            raise ValueError('AI Select Anchor support probe sceneTransport is unsupported')

        camera_binding, renderer_camera, width, height = (
            self._parse_ai_select_anchor_camera(request.get('cameraBinding'))
        )
        probe_camera = probe_camera_from_renderer_camera(
            renderer_camera, width=width, height=height
        )
        stable_mask, stable_mask_digest = self._parse_ai_select_support_probe_mask(
            request.get('stableMask'), width=width, height=height
        )
        return AISelectSupportProbeRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            scene_id=scene_id,
            scene_version=scene_version,
            render_config_version=render_config_version,
            support_probe_attempt_id=support_probe_attempt_id,
            camera_binding=camera_binding,
            probe_camera=probe_camera,
            rgb_digest=rgb_digest,
            stable_mask=stable_mask,
            stable_mask_digest=stable_mask_digest,
            scene_transport=scene_transport,
        )

    @staticmethod
    def _parse_ai_select_support_probe_mask(
        value: object, *, width: int, height: int
    ) -> tuple[bytes, str]:
        if not isinstance(value, dict):
            raise ValueError('AI Select Anchor support probe stableMask must be an object')
        if value.get('encoding') != AI_SELECT_SUPPORT_PROBE_MASK_ENCODING:
            raise ValueError(
                'AI Select Anchor support probe stableMask encoding is unsupported'
            )
        mask_width = _anchor_positive_integer(value.get('width'), 'stableMask width')
        mask_height = _anchor_positive_integer(value.get('height'), 'stableMask height')
        if mask_width != width or mask_height != height:
            raise ValueError(
                'AI Select Anchor support probe stableMask dimensions must match the cameraBinding projection'
            )
        data = value.get('data')
        if not isinstance(data, str) or not data:
            raise ValueError(
                'AI Select Anchor support probe stableMask data must be a non-empty string'
            )
        try:
            mask = base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError(
                'AI Select Anchor support probe stableMask data must be valid base64'
            ) from error
        pixel_count = width * height
        if len(mask) != (pixel_count + 7) // 8:
            raise ValueError(
                'AI Select Anchor support probe stableMask data does not match its dimensions'
            )
        used_bits = pixel_count % 8
        if used_bits and mask[-1] >> used_bits:
            raise ValueError(
                'AI Select Anchor support probe stableMask sets bits beyond its dimensions'
            )
        digest = _anchor_sha256_digest(value.get('digest'), 'support probe stableMask digest')
        if f'sha256:{hashlib.sha256(mask).hexdigest()}' != digest:
            raise ValueError(
                'AI Select Anchor support probe stableMask digest does not match its data bytes'
            )
        return mask, digest

    def produce_ai_select_mask(self, request: Mapping[str, object]) -> dict[str, object]:
        """Publish one bound single-frame proposal set or replay its outcome.

        The browser owns target identity, authoritative Anchor RGB, and
        PromptState. This method validates those untrusted bindings and the
        negotiated adapter capability identity, resolves the RGB artifact or
        Companion-held reference and any previous-logits refinement before
        inference, reserves the single Companion operation slot, then runs the
        SAM 3 Image instance adapter outside every state lock before
        atomically publishing the immutable bounded result. Point-only
        requests through the deterministic reference adapter retain the
        synthetic single-view Frame Set compatibility path with no video
        propagation.
        """

        model_manifest_digest = _mask_request_string(
            request.get('modelManifestDigest'), 'modelManifestDigest'
        )
        model, adapter = self._require_mask_adapter(model_manifest_digest)
        prompt_capabilities = _prompt_capabilities_for_adapter(
            model.get('adapterId')
        )
        mask_request = self._parse_ai_select_mask_request(
            request, prompt_capabilities=prompt_capabilities
        )
        mask_key, admission, owns_admission = self._admit_mask_request(mask_request)
        if not owns_admission:
            return self._replay_mask_request(admission)

        def proposal_response(
            proposals: list[dict[str, object]],
            *,
            refinement_fallback: bool = False,
        ) -> dict[str, object]:
            original_count = len(proposals)
            candidate_bound = int(
                SAM3_IMAGE_RUNTIME_CONFIG['max_multimask_candidates']
            )
            proposals = proposals[:candidate_bound]
            ranked_proposals = add_ranking_features(
                proposals,
                width=mask_request.width,
                height=mask_request.height,
                prompt_state=mask_request.prompt_state,
            )
            proposal_set: dict[str, object] = {
                # v4 (Ticket 07A) removes the v1 ranking machinery from every
                # retained candidate and binds the per-candidate Mask Review
                # record, the opaque logits references, and the refinement
                # fallback diagnostic into the identity digest.
                'schemaVersion': 4,
                'viewId': mask_request.view_id,
                'rgbDigest': mask_request.rgb_digest,
                'promptStateDigest': mask_request.prompt_state_digest,
                'modelManifestDigest': mask_request.model_manifest_digest,
                'adapterCapabilityDigest': mask_request.adapter_capability_digest,
                'proposalPolicyVersion': mask_request.proposal_policy_version,
                'proposalAttemptId': mask_request.proposal_attempt_id,
                'proposals': ranked_proposals,
            }
            if original_count > len(ranked_proposals):
                proposal_set['truncation'] = {
                    'originalCount': original_count,
                    'retainedCount': len(ranked_proposals),
                    'policy': AI_SELECT_MASK_PROPOSAL_POLICY_VERSION,
                }
            if refinement_fallback:
                proposal_set['diagnostics'] = {'refinementFallback': True}
            proposal_set['digest'] = _proposal_identity_digest(proposal_set)
            return {
                'status': 'complete',
                **mask_request.response_fields(),
                'proposalSet': proposal_set,
                'proposalDecision': decide_proposals(
                    ranked_proposals,
                    view_id=mask_request.view_id,
                    rgb_digest=mask_request.rgb_digest,
                    prompt_state_digest=mask_request.prompt_state_digest,
                    proposal_set_digest=str(proposal_set['digest']),
                ),
            }

        try:
            try:
                if isinstance(adapter, Sam3ImageInstanceAdapter):
                    refinement, refinement_fallback, source_attempt_id = (
                        self._resolve_logits_refinement(model, mask_request)
                    )
                    batch = adapter.produce_proposals(
                        model=model,
                        rgb_png=mask_request.rgb_png,
                        width=mask_request.width,
                        height=mask_request.height,
                        program=mask_request.prompt_program,
                        refinement=refinement,
                        cancelled=lambda: False,
                    )
                    proposals = self._proposals_from_sam3_image_candidates(
                        batch.candidates, mask_request
                    )
                    # Refs mint only here, on the success path, atomically
                    # with the proposal publication below. Any adapter failure
                    # or cancellation above leaves the logits store untouched.
                    self._mint_logits_refs(
                        model=model,
                        mask_request=mask_request,
                        batch=batch,
                        proposals=proposals,
                        source_attempt_id=(
                            source_attempt_id
                            if refinement is not None
                            and source_attempt_id is not None
                            else mask_request.proposal_attempt_id
                        ),
                    )
                    response = proposal_response(
                        proposals, refinement_fallback=refinement_fallback
                    )
                    self._complete_mask_request(
                        mask_key, admission, response=response
                    )
                    return response
                if mask_request.prompt_program.boxes:
                    raise MaskSessionError(
                        'unsupportedPromptType',
                        'The selected Prompt Adapter does not implement instance Prompt inference.',
                    )
                frame_set = register_frame_set({
                    'frameSetId': f'ai-select-mask-{mask_request.view_id}',
                    'frameSetVersion': (
                        f'{mask_request.view_id}-{mask_request.rgb_digest}'
                    ),
                    'orderedViews': [{
                        'viewId': mask_request.view_id,
                        'frameDigest': mask_request.rgb_digest,
                        'width': mask_request.width,
                        'height': mask_request.height,
                        'imagePngBase64': base64.b64encode(
                            mask_request.rgb_png
                        ).decode('ascii'),
                        'source': 'anchor',
                    }],
                })
                prompt_log: list[dict[str, object]] = [
                    {
                        'operation': 'New',
                        'prompt': {
                            'promptId': prompt.prompt_id,
                            'viewId': mask_request.view_id,
                            'frameDigest': mask_request.rgb_digest,
                            'frameWidth': mask_request.width,
                            'frameHeight': mask_request.height,
                            'xPx': prompt.x_px,
                            'yPx': prompt.y_px,
                            'polarity': prompt.polarity,
                        },
                    }
                    for prompt in mask_request.prompts
                ]
                production = adapter.produce_tracks(
                    model=model,
                    frame_set=frame_set,
                    prompt_log=prompt_log,
                    cancelled=lambda: False,
                )
            except MaskSessionError as error:
                if error.code != 'anchorMaskUnavailable':
                    raise
                response = proposal_response([])
                self._complete_mask_request(
                    mask_key, admission, response=response
                )
                return response
            except Exception as error:
                _logger.exception(
                    "promptable-mask adapter failed during instance inference"
                )
                raise MaskSessionError(
                    'modelFailure',
                    'The promptable-mask adapter failed; verify the installed model runtime and retry.',
                ) from error
            tracks, diagnostics, _threshold = self._normalise_mask_production(
                production
            )
            primary_track = next(
                track for track in tracks if track['trackId'] == 'primary'
            )
            anchor_frame = next(
                frame
                for frame in primary_track['frames']
                if frame['viewId'] == mask_request.view_id
            )
            if anchor_frame.get('status') in ('not_found', 'rejected'):
                response = proposal_response([])
                self._complete_mask_request(
                    mask_key, admission, response=response
                )
                return response
            self._validate_complete_tracks(frame_set, prompt_log, tracks)
            proposals: list[dict[str, object]] = []
            score_semantics: str | None = None
            alternatives: list[object] = []
            if isinstance(diagnostics, dict):
                candidate_selection = diagnostics.get('candidateSelection')
                if isinstance(candidate_selection, dict):
                    semantics = candidate_selection.get('scoreSemantics')
                    if isinstance(semantics, str) and semantics.strip():
                        score_semantics = semantics
                    candidate_alternatives = candidate_selection.get('alternatives')
                    if isinstance(candidate_alternatives, list):
                        alternatives = candidate_alternatives
            for alternative in alternatives:
                if (
                    not isinstance(alternative, dict)
                    or alternative.get('areaValid') is not True
                    or alternative.get('pointConsistent') is not True
                ):
                    continue
                source_index = alternative.get('candidateIndex')
                binary_mask = alternative.get('binaryMask')
                if (
                    not isinstance(source_index, int)
                    or isinstance(source_index, bool)
                    or source_index < 0
                    or not isinstance(binary_mask, dict)
                    or binary_mask.get('encoding') != 'bitset-lsb-v1'
                    or binary_mask.get('width') != mask_request.width
                    or binary_mask.get('height') != mask_request.height
                    or not isinstance(binary_mask.get('data'), str)
                ):
                    continue
                try:
                    mask_bytes = base64.b64decode(
                        binary_mask['data'], validate=True
                    )
                except (ValueError, binascii.Error):
                    continue
                expected_length = (mask_request.width * mask_request.height + 7) // 8
                if len(mask_bytes) != expected_length:
                    continue
                mask_digest = f'sha256:{hashlib.sha256(mask_bytes).hexdigest()}'
                proposal: dict[str, object] = {
                    'proposalId': f'proposal-{source_index}',
                    'mask': {
                        'encoding': 'bitset-lsb-v1',
                        'width': mask_request.width,
                        'height': mask_request.height,
                        'data': binary_mask['data'],
                        'digest': mask_digest,
                    },
                    'sourceIndex': source_index,
                    'promptConsistency': {
                        'positivePointsSatisfied': True,
                        'negativePointsSatisfied': True,
                    },
                }
                score = alternative.get('qualityScore')
                if (
                    isinstance(score, (int, float))
                    and not isinstance(score, bool)
                    and math.isfinite(score)
                ):
                    proposal['modelScore'] = float(score)
                if score_semantics is not None:
                    proposal['modelScoreSemantics'] = score_semantics
                proposals.append(proposal)
            if not proposals:
                raise MaskSessionError(
                    'incompleteMaskSet',
                    'The multi-candidate Prompt Adapter returned no valid bounded alternatives.',
                )
            response = proposal_response(proposals)
        except MaskSessionError as error:
            self._complete_mask_request(mask_key, admission, failure=error)
            raise
        except Exception as error:
            _logger.exception(
                "promptable-mask adapter failed while publishing the single-frame mask"
            )
            failure = MaskSessionError(
                'modelFailure',
                'The promptable-mask adapter failed while publishing the single-frame mask.',
            )
            self._complete_mask_request(mask_key, admission, failure=failure)
            raise failure from error

        self._complete_mask_request(mask_key, admission, response=response)
        return response

    def _parse_ai_select_mask_request(
        self,
        request: Mapping[str, object],
        *,
        prompt_capabilities: Mapping[str, object],
    ) -> AISelectMaskRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select Mask requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select Mask requestBinding dependencyToken must be an object'
            )
        target_splat_id = _mask_request_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _mask_request_string(
                dependency_value.get('splatId'), 'dependency splatId'
            ),
            'renderStateToken': _mask_request_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _mask_request_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _mask_request_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _mask_request_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select Mask targetSplatId must match its dependency splatId'
            )
        request_binding: dict[str, object] = {
            'targetContextId': _mask_request_string(
                request_binding_value.get('targetContextId'), 'targetContextId'
            ),
            'contextRevision': _mask_request_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        scene_id = _mask_request_string(request.get('sceneId'), 'sceneId')
        scene_version = _mask_request_string(request.get('sceneVersion'), 'sceneVersion')
        view_id = _mask_request_string(request.get('viewId'), 'viewId')
        camera_binding_digest = _anchor_sha256_digest(
            request.get('cameraBindingDigest'), 'Mask cameraBindingDigest'
        )
        model_manifest_digest = _mask_request_string(
            request.get('modelManifestDigest'), 'modelManifestDigest'
        )
        adapter_capability_digest = _anchor_sha256_digest(
            request.get('adapterCapabilityDigest'),
            'Mask adapterCapabilityDigest',
        )
        expected_capability_digest = prompt_capabilities['capabilityDigest']
        if adapter_capability_digest != expected_capability_digest:
            raise MaskSessionError(
                'capabilityMismatch',
                'The selected Prompt Adapter capability identity does not match the proposal request.',
            )
        proposal_policy_version = _mask_request_string(
            request.get('proposalPolicyVersion'), 'proposalPolicyVersion'
        )
        if proposal_policy_version != AI_SELECT_MASK_PROPOSAL_POLICY_VERSION:
            raise MaskSessionError(
                'capabilityMismatch',
                'The Companion does not support this Mask proposal policy.',
            )
        ranking_policy_version = _mask_request_string(
            request.get('rankingPolicyVersion'), 'rankingPolicyVersion'
        )
        if ranking_policy_version != RANKING_POLICY_VERSION:
            raise MaskSessionError(
                'capabilityMismatch',
                'The Companion does not support this Anchor Mask ranking policy.',
            )
        proposal_attempt_id = _mask_request_string(
            request.get('proposalAttemptId'), 'proposalAttemptId'
        )
        rgb_digest = _anchor_sha256_digest(
            request.get('rgbDigest'), 'Mask rgbDigest'
        )
        width = _mask_request_positive_integer(request.get('rgbWidth'), 'rgbWidth')
        height = _mask_request_positive_integer(
            request.get('rgbHeight'), 'rgbHeight'
        )
        rgb_value = request.get('rgb')
        if rgb_value is not None:
            artifact_png, artifact_digest, artifact_width, artifact_height = (
                self._parse_ai_select_mask_rgb(rgb_value)
            )
            if (
                artifact_digest != rgb_digest
                or artifact_width != width
                or artifact_height != height
            ):
                raise ValueError(
                    'AI Select Mask rgb artifact must match the request rgbDigest, rgbWidth, and rgbHeight'
                )
            rgb_png = artifact_png
            self._cache_rgb(rgb_digest, rgb_png, width, height)
        else:
            # A digest-only request is valid only while this Companion still
            # holds the exact immutable bytes; it fails before any inference.
            rgb_png = self._resolve_rgb(rgb_digest, width, height)
        previous_logits_ref_value = request.get('previousLogitsRef')
        if previous_logits_ref_value is not None and not isinstance(
            previous_logits_ref_value, dict
        ):
            raise ValueError('AI Select Mask previousLogitsRef must be an object')
        previous_logits_ref = (
            None
            if previous_logits_ref_value is None
            else dict(previous_logits_ref_value)
        )
        prompt_state, prompts, prompt_state_digest, prompt_program = (
            self._parse_ai_select_prompt_state(
                request.get('promptState'),
                view_id=view_id,
                rgb_digest=rgb_digest,
                width=width,
                height=height,
                prompt_capabilities=prompt_capabilities,
            )
        )
        return AISelectMaskRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            scene_id=scene_id,
            scene_version=scene_version,
            view_id=view_id,
            camera_binding_digest=camera_binding_digest,
            rgb_png=rgb_png,
            rgb_digest=rgb_digest,
            width=width,
            height=height,
            prompts=prompts,
            prompt_program=prompt_program,
            prompt_state=prompt_state,
            prompt_state_digest=prompt_state_digest,
            model_manifest_digest=model_manifest_digest,
            adapter_capability_digest=adapter_capability_digest,
            proposal_policy_version=proposal_policy_version,
            ranking_policy_version=ranking_policy_version,
            proposal_attempt_id=proposal_attempt_id,
            previous_logits_ref=previous_logits_ref,
        )

    @staticmethod
    def _proposals_from_sam3_image_candidates(
        candidates: Sequence[Sam3ImageCandidate],
        request: AISelectMaskRequest,
    ) -> list[dict[str, object]]:
        """Wrap independently validated adapter candidates without comparing them."""

        proposals: list[dict[str, object]] = []
        for candidate in candidates:
            mask_digest = f'sha256:{hashlib.sha256(candidate.mask_bits).hexdigest()}'
            proposal: dict[str, object] = {
                'proposalId': f'proposal-{candidate.source_index}',
                'mask': {
                    'encoding': 'bitset-lsb-v1',
                    'width': request.width,
                    'height': request.height,
                    'data': base64.b64encode(candidate.mask_bits).decode('ascii'),
                    'digest': mask_digest,
                },
                'sourceIndex': candidate.source_index,
                'promptConsistency': dict(candidate.prompt_consistency),
                'promptDiagnostics': [
                    dict(diagnostic) for diagnostic in candidate.prompt_diagnostics
                ],
            }
            if candidate.model_score is not None:
                proposal['modelScore'] = candidate.model_score
                proposal['modelScoreSemantics'] = (
                    'SAM 3 Image instance IoU prediction; adapter-local preview '
                    'ordering score, not a correctness probability.'
                )
            proposals.append(proposal)
        return proposals

    def _cache_rgb(self, digest: str, png: bytes, width: int, height: int) -> None:
        """Retain immutable authoritative RGB bytes for digest-only requests."""

        with self._session_lock:
            if digest in self._rgb_cache:
                return
            self._rgb_cache[digest] = (png, width, height)
            while len(self._rgb_cache) > AI_SELECT_RGB_CACHE_LIMIT:
                # dict preserves insertion order; evict the oldest entry.
                del self._rgb_cache[next(iter(self._rgb_cache))]

    def _resolve_rgb(self, digest: str, width: int, height: int) -> bytes:
        with self._session_lock:
            entry = self._rgb_cache.get(digest)
        if entry is None or entry[1] != width or entry[2] != height:
            raise MaskSessionError(
                'rgbUnresolvable',
                'The authoritative RGB reference cannot be resolved by this Companion; resend the RGB artifact.',
            )
        return entry[0]

    def _adapter_runtime_digest(self, model: Mapping[str, Any]) -> str:
        """Bind adapter, compiler, runtime, checkpoint, and source identity."""

        cache_key = str(model.get('digest', ''))
        with self._session_lock:
            cached = self._adapter_runtime_digests.get(cache_key)
        if cached is not None:
            return cached
        digest = _canonical_json_digest({
            'adapterId': model.get('adapterId'),
            'compilerPolicyVersion': SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
            'runtimeConfigDigest': model.get('runtimeConfigDigest'),
            'checkpointDigest': model.get('checkpointDigest'),
            'sourceCommit': model.get('sourceCommit'),
        })
        with self._session_lock:
            self._adapter_runtime_digests[cache_key] = digest
        return digest

    def _resolve_logits_refinement(
        self, model: Mapping[str, Any], mask_request: AISelectMaskRequest
    ) -> tuple[Sam3ImageRefinementInput | None, bool, str | None]:
        """Resolve an opaque logits ref to Companion-local refinement state.

        Any resolution failure falls back to a fresh no-mask_input inference
        with a refinementFallback diagnostic; it never errors the request and
        never converts browser data into model input.
        """

        ref = mask_request.previous_logits_ref
        if ref is None:
            return None, False, None
        entry = self._resolve_logits_ref_entry(model, mask_request, ref)
        if entry is None:
            return None, True, None
        return (
            Sam3ImageRefinementInput(
                inference_state=entry['inferenceState'],
                mask_input=entry['logits'],
            ),
            False,
            str(entry['sourceAttemptId']),
        )

    def _resolve_logits_ref_entry(
        self,
        model: Mapping[str, Any],
        mask_request: AISelectMaskRequest,
        ref: Mapping[str, object],
    ) -> dict[str, Any] | None:
        required = {
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
        }
        if set(ref) != required or ref.get('schemaVersion') != 1:
            return None
        payload = {key: value for key, value in ref.items() if key != 'refDigest'}
        try:
            recomputed = _canonical_json_digest(payload)
        except (TypeError, ValueError):
            return None
        if ref.get('refDigest') != recomputed:
            return None
        if ref.get('companionInstanceId') != self._companion_instance_id:
            return None
        logits_size = int(SAM3_IMAGE_RUNTIME_CONFIG['low_res_logits_size'])
        if (
            ref.get('shape') != [1, logits_size, logits_size]
            or ref.get('dtype') != 'float32'
        ):
            return None
        state_id = ref.get('stateId')
        if not isinstance(state_id, str):
            return None
        with self._session_lock:
            entry = self._logits_store.get(state_id)
        if entry is None:
            return None
        if (
            entry['targetContextId']
            != mask_request.request_binding.get('targetContextId')
            or entry['viewId'] != mask_request.view_id
            or entry['rgbDigest'] != mask_request.rgb_digest
            or entry['sourceCandidateId'] != ref.get('sourceCandidateId')
            or entry['dataDigest'] != ref.get('dataDigest')
            or entry['adapterRuntimeDigest'] != ref.get('adapterRuntimeDigest')
        ):
            return None
        if entry['adapterRuntimeDigest'] != self._adapter_runtime_digest(model):
            return None
        logits_bytes = entry['logits'].tobytes()
        if (
            f'sha256:{hashlib.sha256(logits_bytes).hexdigest()}'
            != entry['dataDigest']
        ):
            return None
        return entry

    def _mint_logits_refs(
        self,
        *,
        model: Mapping[str, Any],
        mask_request: AISelectMaskRequest,
        batch: Sam3ImageProposalBatch,
        proposals: list[dict[str, object]],
        source_attempt_id: str,
    ) -> None:
        """Mint one opaque digest-bound logits reference per retained candidate.

        The raw logits and inference state stay in the Companion-local store;
        only the reference crosses the boundary. Refinement attempts link back
        to their source inference attempt through ``source_attempt_id``.
        """

        adapter_runtime_digest = self._adapter_runtime_digest(model)
        target_context_id = str(
            mask_request.request_binding['targetContextId']
        )
        logits_size = int(SAM3_IMAGE_RUNTIME_CONFIG['low_res_logits_size'])
        for proposal, candidate in zip(proposals, batch.candidates, strict=True):
            logits = candidate.low_res_logits
            if (
                tuple(logits.shape) != (1, logits_size, logits_size)
                or str(logits.dtype) != 'float32'
            ):
                raise MaskSessionError(
                    'modelFailure',
                    'SAM 3 Image returned low-resolution logits outside the pinned refinement contract.',
                )
            logits_bytes = logits.tobytes()
            data_digest = f'sha256:{hashlib.sha256(logits_bytes).hexdigest()}'
            state_id = f'logits-{uuid.uuid4().hex}'
            proposal_id = str(proposal['proposalId'])
            ref_fields: dict[str, object] = {
                'schemaVersion': 1,
                'companionInstanceId': self._companion_instance_id,
                'stateId': state_id,
                'targetContextId': target_context_id,
                'viewId': mask_request.view_id,
                'rgbDigest': mask_request.rgb_digest,
                'sourceInferenceAttemptId': source_attempt_id,
                'sourceCandidateId': proposal_id,
                'adapterRuntimeDigest': adapter_runtime_digest,
                'shape': [1, logits_size, logits_size],
                'dtype': 'float32',
                'dataDigest': data_digest,
            }
            proposal['logitsRef'] = {
                **ref_fields,
                'refDigest': _canonical_json_digest(ref_fields),
            }
            entry = {
                'logits': logits,
                'inferenceState': batch.inference_state,
                'targetContextId': target_context_id,
                'viewId': mask_request.view_id,
                'rgbDigest': mask_request.rgb_digest,
                'sourceAttemptId': source_attempt_id,
                'sourceCandidateId': proposal_id,
                'adapterRuntimeDigest': adapter_runtime_digest,
                'dataDigest': data_digest,
            }
            with self._session_lock:
                self._logits_store[state_id] = entry
                while len(self._logits_store) > AI_SELECT_LOGITS_STORE_LIMIT:
                    # dict preserves insertion order; evict the oldest entry.
                    del self._logits_store[next(iter(self._logits_store))]

    @staticmethod
    def _parse_ai_select_mask_rgb(value: object) -> tuple[bytes, str, int, int]:
        if not isinstance(value, dict):
            raise ValueError('AI Select Mask rgb must be an object')
        png_base64 = value.get('pngBase64')
        if not isinstance(png_base64, str) or not png_base64:
            raise ValueError('AI Select Mask rgb pngBase64 must be a non-empty string')
        try:
            png = base64.b64decode(png_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError(
                'AI Select Mask rgb pngBase64 must be valid base64'
            ) from error
        digest = value.get('digest')
        if (
            not isinstance(digest, str)
            or len(digest) != len('sha256:') + 64
            or not digest.startswith('sha256:')
            or any(character not in '0123456789abcdef' for character in digest[7:])
        ):
            raise ValueError(
                'AI Select Mask rgb digest must be a sha256:<64 hex> digest'
            )
        if f'sha256:{hashlib.sha256(png).hexdigest()}' != digest:
            raise ValueError(
                'AI Select Mask rgb digest does not match its pngBase64 bytes'
            )
        width = _mask_request_positive_integer(value.get('width'), 'rgb width')
        height = _mask_request_positive_integer(value.get('height'), 'rgb height')
        return png, digest, width, height

    @staticmethod
    def _parse_ai_select_prompt_state(
        value: object,
        *,
        view_id: str,
        rgb_digest: str,
        width: int,
        height: int,
        prompt_capabilities: Mapping[str, object],
    ) -> tuple[
        dict[str, object],
        tuple[AISelectMaskPrompt, ...],
        str,
        CompiledImagePromptProgram,
    ]:
        if not isinstance(value, dict):
            raise ValueError('AI Select Mask promptState must be an object')
        required = {
            'schemaVersion',
            'viewId',
            'rgbDigest',
            'revision',
            'points',
            'boxes',
            'digest',
        }
        if set(value) != required:
            raise ValueError(
                'AI Select Mask promptState must contain exactly the versioned PromptState fields'
            )
        if value.get('schemaVersion') != 2:
            raise ValueError('AI Select Mask promptState schemaVersion must be 2')
        if value.get('viewId') != view_id or value.get('rgbDigest') != rgb_digest:
            raise ValueError(
                'AI Select Mask promptState must bind the exact View and authoritative RGB'
            )
        _mask_request_nonnegative_integer(
            value.get('revision'), 'promptState revision'
        )
        digest = _anchor_sha256_digest(
            value.get('digest'), 'Mask promptState digest'
        )
        payload = {key: item for key, item in value.items() if key != 'digest'}
        encoded = json.dumps(
            payload, separators=(',', ':'), sort_keys=True, allow_nan=False
        ).encode('utf-8')
        if f'sha256:{hashlib.sha256(encoded).hexdigest()}' != digest:
            raise ValueError(
                'AI Select Mask promptState digest does not match its exact payload'
            )
        compiler_policy = prompt_capabilities.get('compilerPolicyVersion')
        try:
            if compiler_policy == POINT_MASK_PROMPT_COMPILER_POLICY_VERSION:
                program = compile_point_mask_prompt_program(
                    value,
                    width=width,
                    height=height,
                    capabilities=prompt_capabilities,
                )
            else:
                program = compile_sam3_image_prompt_program(
                    value,
                    width=width,
                    height=height,
                    capabilities=prompt_capabilities,
                )
        except MaskSessionError as error:
            if error.code == 'invalidPromptState':
                raise ValueError(str(error)) from error
            raise
        if not (program.points or program.boxes):
            raise ValueError(
                'AI Select Mask promptState must contain at least one supported prompt'
            )
        prompts = tuple(
            AISelectMaskPrompt(
                prompt_id=point.prompt_id,
                x_px=point.x_px,
                y_px=point.y_px,
                polarity=point.polarity,
            )
            for point in program.points
        )
        return dict(value), prompts, digest, program

    def register_frame_set(self, payload: dict[str, Any]) -> RegisteredFrameSet:
        """Cache one immutable Frame Set without exposing model-private handles."""

        frame_set = register_frame_set(payload)
        with self._frame_lock:
            existing = self._frame_sets.get(frame_set.frame_set_version)
            if existing is not None and existing.canonical != frame_set.canonical:
                raise MaskSessionError(
                    "immutableFrameSet",
                    "A Frame Set version cannot be registered with different content.",
                )
            self._frame_sets[frame_set.frame_set_version] = frame_set
        return frame_set

    def release_frame_set(self, frame_set_version: str) -> bool:
        """Idempotently release a Frame Set that no session has claimed."""

        with self._session_lock:
            with self._mask_lock:
                if any(
                    session.frame_set_version == frame_set_version
                    for session in self._mask_sessions.values()
                ):
                    return False
            with self._frame_lock:
                self._frame_sets.pop(frame_set_version, None)
        return True

    def update_mask_session(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> dict[str, Any]:
        """Atomically produce or replay one complete Mask Set."""

        mask_set, _ = self._update_mask_session(
            bindings=bindings,
            prompt_log=prompt_log,
            retain_evidence_lease=False,
        )
        return mask_set

    def update_preview(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compatibility view of one complete preview publication."""

        publication = self.update_preview_publication(
            bindings=bindings,
            prompt_log=prompt_log,
        )
        return publication.mask_set, publication.evidence_snapshot

    def update_preview_publication(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
        stage_observer: Callable[[str, float], None] | None = None,
    ) -> PreviewPublication:
        """Atomically publish Frame Set, Mask Set, Evidence, and coverage.

        Generated View planning is an internal pre-publication step.  The
        editor sees only the final immutable Frame Set and one complete
        Candidate Object Selection result; an Anchor-only intermediate mask is
        never exposed as a candidate.
        """

        requested_request_id = self._mask_binding(bindings, "requestId")
        requested_session_id = self._mask_binding(bindings, "sessionId")
        with self._mask_lock:
            session = self._mask_sessions.get(requested_session_id)
            if session is not None:
                completed = session.completed_preview_publications.get(
                    requested_request_id
                )
                if completed is not None:
                    return self._preview_publication_from_canonical(completed)

        stage_started = time.perf_counter()
        resolved = self._effective_preview_frame_set(
            bindings=bindings,
            prompt_log=prompt_log,
        )
        if stage_observer is not None:
            stage_observer(
                "generatedViewPlanningSeconds", time.perf_counter() - stage_started
            )
        effective_bindings = resolved.bindings
        request_id = self._mask_binding(effective_bindings, "requestId")
        session_id = self._mask_binding(effective_bindings, "sessionId")
        staged_generated_preview = resolved.staged_generated_preview
        completed_after_resolution: str | None = None
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is not None:
                completed = session.completed_preview_publications.get(request_id)
                if completed is not None:
                    if (
                        staged_generated_preview is not None
                        and session.staged_generated_preview_token
                        == staged_generated_preview.token
                    ):
                        session.staged_generated_preview_token = None
                        session.staged_generated_preview_request_id = None
                    completed_after_resolution = completed
        if completed_after_resolution is not None:
            self._finish_closing_session_if_drained(session_id)
            return self._preview_publication_from_canonical(completed_after_resolution)

        staged_generated_resolution = (
            staged_generated_preview.resolution
            if staged_generated_preview is not None
            else None
        )
        try:
            stage_started = time.perf_counter()
            mask_set, evidence_lease_claimed = self._update_mask_session(
                bindings=effective_bindings,
                prompt_log=prompt_log,
                retain_evidence_lease=True,
                quality_gate=True,
                staged_frame_set_version=(
                    staged_generated_resolution.frame_set_version
                    if staged_generated_resolution is not None
                    else None
                ),
                staged_generated_preview_token=(
                    staged_generated_preview.token
                    if staged_generated_preview is not None
                    else None
                ),
            )
            if stage_observer is not None:
                stage_observer(
                    "maskProductionSeconds", time.perf_counter() - stage_started
                )
            stage_started = time.perf_counter()
            evidence_snapshot = self._build_evidence_snapshot(
                bindings=effective_bindings,
                mask_set=mask_set,
                evidence_lease_claimed=evidence_lease_claimed,
            )
            if stage_observer is not None:
                stage_observer(
                    "evidenceConstructionSeconds", time.perf_counter() - stage_started
                )
            renderer = self.contributor_renderer
            if renderer is None:
                # _build_evidence_snapshot has already returned rendererUnavailable,
                # but keep this explicit for future alternate evidence providers.
                raise MaskSessionError(
                    "rendererUnavailable",
                    "The gsplat/CUDA Contributor renderer is unavailable for Generated View coverage.",
                )
            snapshot = self.scene_snapshot(
                self._mask_binding(effective_bindings, "sceneId"),
                self._mask_binding(effective_bindings, "sceneVersion"),
            )
            if snapshot is None:
                raise MaskSessionError(
                    "sceneCacheMiss",
                    "The Scene Snapshot is unavailable for Generated View coverage.",
                )
            stage_started = time.perf_counter()
            coverage_report = self.generated_view_policy.coverage_report(
                scene_snapshot=snapshot.scene,
                frame_set=resolved.frame_set,
                mask_set=mask_set,
                renderer=renderer,
                render_config_version=self._mask_binding(
                    effective_bindings, "renderConfigVersion"
                ),
                preliminary_rejections=resolved.preliminary_rejections,
                attempted_view_ids=resolved.attempted_view_ids,
                quality_diagnostics=resolved.quality_diagnostics,
                prompt_log=prompt_log if isinstance(prompt_log, list) else (),
            )
            if stage_observer is not None:
                stage_observer(
                    "coverageReportSeconds", time.perf_counter() - stage_started
                )
            publication = PreviewPublication(
                bindings=dict(effective_bindings),
                frame_set=public_frame_set_payload(resolved.frame_set),
                mask_set=mask_set,
                evidence_snapshot=evidence_snapshot,
                coverage_report=coverage_report,
            )
            canonical = json.dumps(
                {
                    "bindings": publication.bindings,
                    "frameSet": publication.frame_set,
                    "maskSet": publication.mask_set,
                    "evidenceSnapshot": publication.evidence_snapshot,
                    "coverageReport": publication.coverage_report,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            with self._mask_lock:
                current = self._mask_sessions.get(session_id)
                if (
                    current is None
                    or current.closing
                    or request_id in current.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled",
                        "The Object Selection session closed before preview publication.",
                    )
                existing = current.completed_preview_publications.get(request_id)
                if existing is not None:
                    return self._preview_publication_from_canonical(existing)
                if staged_generated_preview is not None:
                    if (
                        current.staged_generated_preview_token
                        != staged_generated_preview.token
                    ):
                        raise MaskSessionError(
                            "updateInProgress",
                            "The Generated View preview transaction was superseded.",
                        )
                    current.frame_set_version = (
                        staged_generated_preview.resolution.frame_set_version
                    )
                    current.generated_resolution = staged_generated_preview.resolution
                    current.staged_generated_preview_token = None
                    current.staged_generated_preview_request_id = None
                current.completed_preview_publications[request_id] = canonical
            return publication
        except Exception:
            self._discard_staged_generated_preview(
                session_id=session_id,
                request_id=request_id,
                staged_generated_preview=staged_generated_preview,
            )
            raise

    def _effective_preview_frame_set(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> ResolvedPreviewFrameSet:
        """Resolve an existing or newly planned Generated View Frame Set.

        The initial Anchor Frame Set remains a cache key for retry recovery.
        Once a generated version has been prepared, a retry may still carry the
        original version and is deterministically upgraded to the cached final
        version before mask publication.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        requested_frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        model_manifest_digest = self._mask_binding(bindings, "modelManifestDigest")
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                raise MaskSessionError(
                    "unknownSession", "The Object Selection mask session is no longer active."
                )
            if session.closing or request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The Object Selection session is closing."
                )
            if session.model_manifest_digest != model_manifest_digest:
                raise MaskSessionError(
                    "staleManifest", "The Model Manifest does not match this Object Selection session."
                )
            if session.staged_generated_preview_token is not None:
                raise MaskSessionError(
                    "updateInProgress",
                    "A Generated View preview is finalizing before another update can begin.",
                )
            generated_resolution = session.generated_resolution
            current_version = session.frame_set_version
        if generated_resolution is not None:
            if requested_frame_set_version not in {
                generated_resolution.frame_set_version,
                generated_resolution.source_frame_set_version,
            }:
                raise MaskSessionError(
                    "staleFrameSet", "The preview request does not match this Generated View Frame Set."
                )
            frame_set = self._require_frame_set(generated_resolution.frame_set_version)
            staged_generated_preview = self._stage_generated_preview(
                session_id=session_id,
                request_id=request_id,
                resolution=generated_resolution,
            )
            return ResolvedPreviewFrameSet(
                bindings={
                    **bindings,
                    "frameSetVersion": generated_resolution.frame_set_version,
                    "renderConfigVersion": generated_resolution.render_config_version,
                },
                frame_set=frame_set,
                preliminary_rejections=generated_resolution.preliminary_rejections,
                attempted_view_ids=generated_resolution.attempted_view_ids or tuple(
                    frame.view_id for frame in frame_set.ordered_views
                ),
                quality_diagnostics=dict(generated_resolution.quality_diagnostics),
                staged_generated_preview=staged_generated_preview,
            )
        if current_version != requested_frame_set_version:
            raise MaskSessionError(
                "staleFrameSet", "The preview request Frame Set version does not match this Object Selection session."
            )
        anchor_frame_set = self._require_frame_set(requested_frame_set_version)
        renderer = self.contributor_renderer
        if (
            renderer is None
            or not callable(getattr(renderer, "plan_views", None))
            or not callable(getattr(renderer, "preflight", None))
            or not callable(getattr(renderer, "render_generated", None))
            or len(anchor_frame_set.ordered_views) != 1
        ):
            return ResolvedPreviewFrameSet(
                bindings=dict(bindings),
                frame_set=anchor_frame_set,
                preliminary_rejections=(),
                attempted_view_ids=tuple(
                    frame.view_id for frame in anchor_frame_set.ordered_views
                ),
                quality_diagnostics={},
            )

        planning_id = f"{request_id}:generated-view-plan"
        retry_resolution = False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None or session.closing or request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The Object Selection session is closing."
                )
            if session.staged_generated_preview_token is not None:
                raise MaskSessionError(
                    "updateInProgress",
                    "A Generated View preview is finalizing before another update can begin.",
                )
            if (
                session.generated_resolution is not None
                or session.frame_set_version != current_version
            ):
                retry_resolution = True
            elif session.in_flight_request_ids:
                raise MaskSessionError(
                    "updateInProgress", "Another Object Selection preview update is still in progress."
                )
            else:
                session.in_flight_request_ids.add(planning_id)
        if retry_resolution:
            return self._effective_preview_frame_set(
                bindings=bindings,
                prompt_log=prompt_log,
            )
        try:
            model, adapter = self._require_mask_adapter(model_manifest_digest)
            cancelled = lambda: self._preview_work_cancelled(session_id, request_id)
            production = adapter.produce_tracks(
                model=model,
                frame_set=anchor_frame_set,
                prompt_log=prompt_log,
                cancelled=cancelled,
            )
            preliminary_tracks, _anchor_tracking_diagnostics, _ = (
                self._normalise_mask_production(production)
            )
            self._validate_complete_tracks(
                anchor_frame_set,
                prompt_log if isinstance(prompt_log, list) else [],
                preliminary_tracks,
            )
            scene_id = self._mask_binding(bindings, "sceneId")
            scene_version = self._mask_binding(bindings, "sceneVersion")
            snapshot = self.scene_snapshot(scene_id, scene_version)
            if snapshot is None:
                raise MaskSessionError(
                    "sceneCacheMiss", "The Scene Snapshot is unavailable for Generated View planning."
                )
            anchor_mask_set = {"tracks": preliminary_tracks}
            scene_snapshot = snapshot.scene
            selected = None
            selected_render_config_version = None
            base_render_config_version = self._mask_binding(
                bindings, "renderConfigVersion"
            )
            oom_retries: list[dict[str, int]] = []
            for resolution_index, resolution in enumerate(GENERATED_VIEW_RESOLUTIONS):
                try:
                    prepared = self.generated_view_policy.prepare(
                        scene_snapshot=scene_snapshot,
                        anchor_frame_set=anchor_frame_set,
                        anchor_mask_set=anchor_mask_set,
                        renderer=renderer,
                        resolution=resolution,
                    )
                    attempt_render_config_version = generated_render_config_version(
                        base_render_config_version, resolution
                    )
                    if prepared.render_config_version != attempt_render_config_version:
                        raise MaskSessionError(
                            "renderConfigMismatch",
                            "Generated Views must use the immutable render configuration bound to this preview trial.",
                        )

                    def track_prefix(
                        frame_set: RegisteredFrameSet,
                    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
                        prefix_production = adapter.produce_tracks(
                            model=model,
                            frame_set=frame_set,
                            prompt_log=prompt_log,
                            cancelled=cancelled,
                        )
                        tracks, diagnostics, _ = self._normalise_mask_production(
                            prefix_production
                        )
                        self._validate_complete_tracks(
                            frame_set,
                            prompt_log if isinstance(prompt_log, list) else [],
                            tracks,
                        )
                        return tracks, diagnostics

                    selected = self.generated_view_policy.select_incrementally(
                        prepared=prepared,
                        scene_snapshot=scene_snapshot,
                        anchor_mask_set=anchor_mask_set,
                        renderer=renderer,
                        resolution=resolution,
                        track_prefix=track_prefix,
                        prompt_log=prompt_log if isinstance(prompt_log, list) else (),
                    )
                    selected_render_config_version = attempt_render_config_version
                    break
                except Exception as error:
                    if not _is_torch_out_of_memory(error):
                        raise
                    discard_attempt = getattr(renderer, "discard_attempt", None)
                    if callable(discard_attempt):
                        discard_attempt()
                    discard_tracking_attempt = getattr(adapter, "discard_attempt", None)
                    if callable(discard_tracking_attempt):
                        discard_tracking_attempt()
                    if resolution == GENERATED_VIEW_RESOLUTIONS[-1]:
                        raise MaskSessionError(
                            "rendererOutOfMemory",
                            "The Generated View attempt exhausted CUDA memory at the minimum resolution.",
                        ) from error
                    oom_retries.append(
                        {
                            "resolution": resolution,
                            "nextResolution": GENERATED_VIEW_RESOLUTIONS[
                                resolution_index + 1
                            ],
                        }
                    )
            assert selected is not None
            assert selected_render_config_version is not None
            staged_generated_resolution = GeneratedFrameSetResolution(
                source_frame_set_version=requested_frame_set_version,
                frame_set_version=selected.frame_set.frame_set_version,
                render_config_version=selected_render_config_version,
                preliminary_rejections=selected.rejected_views,
                attempted_view_ids=selected.attempted_view_ids,
                quality_diagnostics={
                    **dict(selected.quality_diagnostics),
                    "oomRetries": oom_retries,
                },
            )
            # Cache the selected immutable Frame Set only so the final replay
            # can consume it. Session ownership is promoted with the complete
            # Frame Set/Mask Set/Evidence/Coverage publication below.
            self.register_frame_set(frame_set_payload(selected.frame_set))
            staged_generated_preview: StagedGeneratedPreview | None = None
            try:
                staged_generated_preview = self._stage_generated_preview(
                    session_id=session_id,
                    request_id=request_id,
                    resolution=staged_generated_resolution,
                    allowed_in_flight_request_ids=frozenset({planning_id}),
                    cancellation_message=(
                        "The Object Selection session closed during Generated View planning."
                    ),
                )
                return ResolvedPreviewFrameSet(
                    bindings={
                        **bindings,
                        "frameSetVersion": selected.frame_set.frame_set_version,
                        "renderConfigVersion": selected_render_config_version,
                    },
                    frame_set=selected.frame_set,
                    preliminary_rejections=selected.rejected_views,
                    attempted_view_ids=selected.attempted_view_ids,
                    quality_diagnostics=dict(
                        staged_generated_resolution.quality_diagnostics
                    ),
                    staged_generated_preview=staged_generated_preview,
                )
            except Exception:
                if staged_generated_preview is not None:
                    self._discard_staged_generated_preview(
                        session_id=session_id,
                        request_id=request_id,
                        staged_generated_preview=staged_generated_preview,
                    )
                elif staged_generated_resolution.frame_set_version != requested_frame_set_version:
                    self.release_frame_set(
                        staged_generated_resolution.frame_set_version
                    )
                raise
        finally:
            self._finish_preview_work(session_id, planning_id)

    def _stage_generated_preview(
        self,
        *,
        session_id: str,
        request_id: str,
        resolution: GeneratedFrameSetResolution,
        allowed_in_flight_request_ids: frozenset[str] = frozenset(),
        cancellation_message: str = "The Object Selection session is closing.",
    ) -> StagedGeneratedPreview:
        """Reserve a Generated View replay until publication or rollback."""

        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if (
                session is None
                or session.closing
                or request_id in session.cancelled_request_ids
            ):
                raise MaskSessionError("cancelled", cancellation_message)
            if session.in_flight_request_ids - allowed_in_flight_request_ids:
                raise MaskSessionError(
                    "updateInProgress",
                    "Another Object Selection preview update is still in progress.",
                )
            if session.staged_generated_preview_token is not None:
                raise MaskSessionError(
                    "updateInProgress",
                    "A Generated View preview is already finalizing.",
                )
            token = secrets.token_urlsafe(18)
            session.staged_generated_preview_token = token
            session.staged_generated_preview_request_id = request_id
            return StagedGeneratedPreview(
                token=token,
                resolution=resolution,
                prior_frame_set_version=session.frame_set_version,
                prior_generated_resolution=session.generated_resolution,
                prior_prompt_log_canonical=session.prompt_log_canonical,
                prior_prompt_log_revision=session.prompt_log_revision,
                prior_completed_update=session.completed_updates.get(request_id),
                prior_completed_update_fingerprint=(
                    session.completed_update_fingerprints.get(request_id)
                ),
                prior_completed_evidence_snapshot=(
                    session.completed_evidence_snapshots.get(request_id)
                ),
                prior_completed_preview_publication=(
                    session.completed_preview_publications.get(request_id)
                ),
            )

    def _discard_staged_generated_preview(
        self,
        *,
        session_id: str,
        request_id: str,
        staged_generated_preview: StagedGeneratedPreview | None,
    ) -> None:
        """Undo unpublished final-replay state after a staged Generated View fails."""

        if staged_generated_preview is None:
            return

        def restore_cached_request(
            cache: dict[str, str], prior_value: str | None
        ) -> None:
            if prior_value is None:
                cache.pop(request_id, None)
            else:
                cache[request_id] = prior_value

        release_cached_frame_set = False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is not None:
                if (
                    session.staged_generated_preview_token
                    != staged_generated_preview.token
                ):
                    return
                session.frame_set_version = staged_generated_preview.prior_frame_set_version
                session.generated_resolution = (
                    staged_generated_preview.prior_generated_resolution
                )
                session.prompt_log_canonical = (
                    staged_generated_preview.prior_prompt_log_canonical
                )
                session.prompt_log_revision = (
                    staged_generated_preview.prior_prompt_log_revision
                )
                restore_cached_request(
                    session.completed_updates,
                    staged_generated_preview.prior_completed_update,
                )
                restore_cached_request(
                    session.completed_update_fingerprints,
                    staged_generated_preview.prior_completed_update_fingerprint,
                )
                restore_cached_request(
                    session.completed_evidence_snapshots,
                    staged_generated_preview.prior_completed_evidence_snapshot,
                )
                restore_cached_request(
                    session.completed_preview_publications,
                    staged_generated_preview.prior_completed_preview_publication,
                )
            release_cached_frame_set = (
                staged_generated_preview.resolution.frame_set_version
                != staged_generated_preview.prior_frame_set_version
            )
        # The selected Frame Set was cache-only until the commit above. Once
        # final replay fails, it must not remain available to a later request.
        # Keep the token while releasing it so no retry can re-register and
        # stage the same deterministic version between rollback and eviction.
        try:
            if release_cached_frame_set:
                self.release_frame_set(
                    staged_generated_preview.resolution.frame_set_version
                )
        finally:
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    session is not None
                    and session.staged_generated_preview_token
                    == staged_generated_preview.token
                ):
                    session.staged_generated_preview_token = None
                    session.staged_generated_preview_request_id = None
        self._finish_closing_session_if_drained(session_id)

    def _preview_work_cancelled(self, session_id: str, request_id: str) -> bool:
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            return (
                current is None
                or current.closing
                or request_id in current.cancelled_request_ids
            )

    @staticmethod
    def _preview_publication_from_canonical(canonical: str) -> PreviewPublication:
        try:
            value = json.loads(canonical)
            return PreviewPublication(
                bindings=value["bindings"],
                frame_set=value["frameSet"],
                mask_set=value["maskSet"],
                evidence_snapshot=value["evidenceSnapshot"],
                coverage_report=value["coverageReport"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidPreviewPublication", "The cached preview publication is invalid."
            ) from error

    def _update_mask_session(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
        retain_evidence_lease: bool,
        quality_gate: bool = False,
        staged_frame_set_version: str | None = None,
        staged_generated_preview_token: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically produce or replay one complete Mask Set.

        Adapter work happens outside the state lock.  No accepted Prompt Log or
        Mask Set is advanced until the adapter has produced every track/view
        outcome and the request is still current.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        model_manifest_digest = self._mask_binding(bindings, "modelManifestDigest")
        prompt_log_revision = self._mask_binding_revision(bindings)
        if not isinstance(prompt_log, list):
            raise MaskSessionError(
                "invalidPromptLog", "The Mask Set update must contain an ordered Prompt Log."
            )
        try:
            prompt_log_canonical = json.dumps(
                prompt_log, separators=(",", ":"), sort_keys=True
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidPromptLog", "The Prompt Log must be JSON-compatible."
            ) from error
        try:
            request_fingerprint = json.dumps(
                {"bindings": bindings, "promptLog": prompt_log},
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidMaskSession", "The Mask Set request bindings must be JSON-compatible."
            ) from error

        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                raise MaskSessionError(
                    "unknownSession", "The Object Selection mask session is no longer active."
                )
            if (
                session.staged_generated_preview_token is not None
                and (
                    session.staged_generated_preview_token
                    != staged_generated_preview_token
                    or session.staged_generated_preview_request_id != request_id
                )
            ):
                raise MaskSessionError(
                    "updateInProgress",
                    "A Generated View preview is finalizing before another update can begin.",
                )
            completed = session.completed_updates.get(request_id)
            if completed is not None:
                if session.completed_update_fingerprints.get(request_id) != request_fingerprint:
                    raise MaskSessionError(
                        "requestIdConflict",
                        "A repeated Mask Set request ID must replay its original bindings and Prompt Log.",
                    )
                if retain_evidence_lease:
                    if session.closing or request_id in session.cancelled_request_ids:
                        raise MaskSessionError(
                            "cancelled",
                            "The Object Selection mask session is closing.",
                        )
                    if request_id not in session.completed_evidence_snapshots:
                        if session.in_flight_request_ids:
                            raise MaskSessionError(
                                "updateInProgress",
                                "Another Object Selection preview update is still in progress.",
                            )
                        session.in_flight_request_ids.add(request_id)
                        return json.loads(completed), True
                return json.loads(completed), False
            if session.closing:
                raise MaskSessionError(
                    "cancelled", "The Object Selection mask session is closing."
                )
            if request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The promptable-mask update was cancelled."
                )
            if session.in_flight_request_ids:
                raise MaskSessionError(
                    "updateInProgress", "Another promptable-mask update is still in progress."
                )
            self._validate_mask_session_bindings(
                session,
                frame_set_version=frame_set_version,
                model_manifest_digest=model_manifest_digest,
                staged_frame_set_version=staged_frame_set_version,
            )
            self._validate_prompt_log_revision(
                session,
                prompt_log=prompt_log,
                prompt_log_canonical=prompt_log_canonical,
                prompt_log_revision=prompt_log_revision,
            )
            # Claim the singleton preview pipeline before resolving model/frame
            # assets. A concurrent close then retains its lease and cancels
            # this pending work instead of clearing caches beneath a future
            # model or contributor-renderer call or admitting another update.
            session.in_flight_request_ids.add(request_id)

        try:
            frame_set = self._require_frame_set(frame_set_version)
            model, adapter = self._require_mask_adapter(model_manifest_digest)
        except MaskSessionError:
            self._finish_preview_work(session_id, request_id)
            raise

        cancelled_before_inference = False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None or request_id in session.cancelled_request_ids:
                cancelled_before_inference = True
        if cancelled_before_inference:
            self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )

        def cancelled() -> bool:
            with self._mask_lock:
                current = self._mask_sessions.get(session_id)
                return current is None or request_id in current.cancelled_request_ids

        try:
            production = adapter.produce_tracks(
                model=model,
                frame_set=frame_set,
                prompt_log=prompt_log,
                cancelled=cancelled,
            )
            tracks, diagnostics, threshold = self._normalise_mask_production(production)
            self._validate_complete_tracks(frame_set, prompt_log, tracks)
            if quality_gate and self.contributor_renderer is not None:
                scene_id = self._mask_binding(bindings, "sceneId")
                scene_version = self._mask_binding(bindings, "sceneVersion")
                snapshot = self.scene_snapshot(scene_id, scene_version)
                if snapshot is None:
                    raise MaskSessionError(
                        "sceneCacheMiss",
                        "The Scene Snapshot is unavailable for Generated View quality gating.",
                    )
                tracks, quality_rejections = quality_gate_tracks(
                    scene_snapshot=snapshot.scene,
                    frame_set=frame_set,
                    tracks=tracks,
                    renderer=self.contributor_renderer,
                    prompt_log=prompt_log,
                )
                if quality_rejections:
                    diagnostics = {
                        **(diagnostics or {}),
                        "generatedViewQualityRejections": list(quality_rejections),
                    }
            mask_set = {
                "status": "complete",
                "requestId": request_id,
                "sessionId": session_id,
                "promptLogRevision": prompt_log_revision,
                "frameSetVersion": frame_set_version,
                "modelManifestDigest": model_manifest_digest,
                "tracks": tracks,
            }
            # Preview-quality diagnostics are internal policy artifacts, never
            # editor-facing Mask Set fields.
            if diagnostics is not None and not quality_gate:
                mask_set["diagnostics"] = diagnostics
            mask_set["threshold"] = threshold
            mask_set_canonical = json.dumps(
                mask_set, separators=(",", ":"), sort_keys=True
            )
        except MaskSessionError:
            self._finish_preview_work(session_id, request_id)
            raise
        except Exception as error:
            self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "modelFailure",
                "The promptable-mask adapter failed; verify the installed model runtime and retry.",
            ) from error

        cancelled_after_inference = False
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if current is None or request_id in current.cancelled_request_ids:
                if current is not None:
                    current.in_flight_request_ids.discard(request_id)
                cancelled_after_inference = True
            else:
                if not retain_evidence_lease:
                    current.in_flight_request_ids.discard(request_id)
                current.completed_updates[request_id] = mask_set_canonical
                current.completed_update_fingerprints[request_id] = request_fingerprint
                if prompt_log_revision > current.prompt_log_revision:
                    current.prompt_log_canonical = prompt_log_canonical
                    current.prompt_log_revision = prompt_log_revision
                if current.frame_set_version is None:
                    current.frame_set_version = frame_set_version
                if current.model_manifest_digest is None:
                    current.model_manifest_digest = model_manifest_digest
        if cancelled_after_inference:
            self._finish_closing_session_if_drained(session_id)
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )
        self._finish_closing_session_if_drained(session_id)
        return json.loads(mask_set_canonical), retain_evidence_lease

    def build_evidence_snapshot(
        self,
        *,
        bindings: dict[str, Any],
        mask_set: dict[str, Any],
    ) -> dict[str, Any]:
        """Lift a complete Mask Set into its immutable Evidence Snapshot."""

        return self._build_evidence_snapshot(
            bindings=bindings,
            mask_set=mask_set,
            evidence_lease_claimed=False,
        )

    def _build_evidence_snapshot(
        self,
        *,
        bindings: dict[str, Any],
        mask_set: dict[str, Any],
        evidence_lease_claimed: bool,
    ) -> dict[str, Any]:
        """Lift one complete Mask Set into its immutable Evidence Snapshot.

        The completed Mask Set remains the only input accepted from the mask
        stage.  The renderer is invoked outside service locks, while a
        canonical snapshot is cached under the request ID so retries cannot
        reinterpret the same request with a later renderer result.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        scene_id = self._mask_binding(bindings, "sceneId")
        scene_version = self._mask_binding(bindings, "sceneVersion")
        frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        lease_owned = False
        try:
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    evidence_lease_claimed
                    and session is not None
                    and request_id in session.in_flight_request_ids
                ):
                    lease_owned = True
                if (
                    session is None
                    or session.closing
                    or request_id in session.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled",
                        "The Object Selection session closed before Evidence Snapshot publication.",
                    )
                completed = session.completed_evidence_snapshots.get(request_id)
                if completed is not None:
                    if lease_owned:
                        session.in_flight_request_ids.discard(request_id)
                    return json.loads(completed)
                completed_mask_set = session.completed_updates.get(request_id)
                canonical_mask_set = json.dumps(
                    mask_set, separators=(",", ":"), sort_keys=True
                )
                if completed_mask_set != canonical_mask_set:
                    raise MaskSessionError(
                        "invalidEvidenceSnapshot",
                        "Evidence Policy must lift the complete immutable Mask Set for this request.",
                    )
                if evidence_lease_claimed:
                    if session.in_flight_request_ids != {request_id}:
                        raise MaskSessionError(
                            "updateInProgress",
                            "Another Object Selection preview update is still in progress.",
                        )
                else:
                    if session.in_flight_request_ids:
                        raise MaskSessionError(
                            "updateInProgress",
                            "Another Object Selection preview update is still in progress.",
                        )
                    # Rendering contributor support is part of the same preview
                    # transaction as mask production. Keep capacity and cancellation
                    # ownership until the immutable Evidence Snapshot is published.
                    session.in_flight_request_ids.add(request_id)
                    lease_owned = True
        except MaskSessionError:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise

        try:
            snapshot = self.scene_snapshot(scene_id, scene_version)
            if snapshot is None:
                raise MaskSessionError(
                    "sceneCacheMiss",
                    "The Scene Snapshot is unavailable for Evidence Policy lifting.",
                )
            frame_set = self._require_frame_set(frame_set_version)
            renderer = self._require_contributor_renderer()
            with self._mask_lock:
                current = self._mask_sessions.get(session_id)
                if (
                    current is None
                    or current.closing
                    or request_id in current.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled",
                        "The Object Selection session closed before Evidence Snapshot publication.",
                    )

            evidence_snapshot = build_evidence_snapshot(
                bindings=bindings,
                scene_snapshot=snapshot.scene,
                frame_set=frame_set,
                mask_set=mask_set,
                renderer=renderer,
            )
            canonical_evidence_snapshot = json.dumps(
                evidence_snapshot, separators=(",", ":"), sort_keys=True
            )
        except MaskSessionError:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise
        except Exception as error:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "rendererFailure",
                "The Contributor renderer failed; verify the gsplat/CUDA runtime and retry.",
            ) from error

        cancelled_after_lifting = False
        completed_evidence_snapshot: str | None = None
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if (
                current is None
                or current.closing
                or request_id in current.cancelled_request_ids
            ):
                if current is not None:
                    current.in_flight_request_ids.discard(request_id)
                cancelled_after_lifting = True
            else:
                completed_evidence_snapshot = current.completed_evidence_snapshots.get(
                    request_id
                )
                if completed_evidence_snapshot is None:
                    completed_evidence_snapshot = canonical_evidence_snapshot
                    current.completed_evidence_snapshots[request_id] = (
                        completed_evidence_snapshot
                    )
                current.in_flight_request_ids.discard(request_id)
        if cancelled_after_lifting:
            self._finish_closing_session_if_drained(session_id)
            raise MaskSessionError(
                "cancelled",
                "The Object Selection session closed before Evidence Snapshot publication.",
            )
        self._finish_closing_session_if_drained(session_id)
        assert completed_evidence_snapshot is not None
        return json.loads(completed_evidence_snapshot)

    def cancel_mask_update(self, session_id: str, request_id: str) -> bool:
        """Mark a pending update cancelled without changing the last usable Mask Set."""

        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                return False
            if request_id in session.completed_preview_publications:
                return False
            if (
                request_id in session.completed_evidence_snapshots
                and session.staged_generated_preview_request_id != request_id
            ):
                return False
            session.cancelled_request_ids.add(request_id)
            return True

    def release_object_selection_sessions(self) -> None:
        with self._session_lock:
            session_id = self._active_object_selection_session
            if session_id is None:
                if self._active_anchor_render is not None:
                    return
                with self._mask_lock:
                    self._mask_sessions.clear()
                self._release_all_transient_caches_locked()
                return
            self._close_active_session_locked(session_id)

    def _finish_preview_work(self, session_id: str, request_id: str) -> None:
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if current is not None:
                current.in_flight_request_ids.discard(request_id)
        self._finish_closing_session_if_drained(session_id)

    def _finish_closing_session_if_drained(self, session_id: str) -> None:
        with self._session_lock:
            if self._active_object_selection_session != session_id:
                return
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    session is None
                    or not session.closing
                    or session.in_flight_request_ids
                    or session.staged_generated_preview_token is not None
                ):
                    return
            self._release_active_session_locked(session_id)

    def _close_active_session_locked(self, session_id: str) -> bool:
        """Close the active singleton while holding `_session_lock`."""

        if self._active_object_selection_session != session_id:
            return False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is not None:
                session.closing = True
                session.cancelled_request_ids.update(session.in_flight_request_ids)
                if (
                    session.in_flight_request_ids
                    or session.staged_generated_preview_token is not None
                ):
                    # Keep the single-session lease until the adapter has
                    # observed cancellation and the staged finalization has
                    # committed or rolled back. Otherwise a second session
                    # could overlap the same transaction's GPU/cache work.
                    return True
        self._release_active_session_locked(session_id)
        return True

    def _release_active_session_locked(self, session_id: str) -> None:
        """Clear the singleton session and caches while holding `_session_lock`."""

        if self._active_object_selection_session != session_id:
            return
        with self._mask_lock:
            self._mask_sessions.pop(session_id, None)
        self._release_all_transient_caches_locked()
        self._active_object_selection_session = None

    @staticmethod
    def _anchor_render_request_key(request: AISelectAnchorRequest) -> str:
        """Canonicalize every immutable input that can affect one Anchor RGB."""

        return json.dumps(
            request.response_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_anchor_render(
        self, request: AISelectAnchorRequest
    ) -> tuple[str, AnchorRenderAdmission, bool]:
        """Reserve or join one bound GPU publication without holding locks for it."""

        key = self._anchor_render_request_key(request)
        with self._session_lock:
            admission = self._anchor_render_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # A replay record can contain a full-resolution PNG. Retain only
            # the most recent completed request for lost-response recovery;
            # a different current binding makes older products stale anyway.
            self._anchor_render_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._anchor_render_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = AnchorRenderAdmission()
            self._anchor_render_admissions[key] = admission
            self._active_anchor_render = key
        return key, admission, True

    @staticmethod
    def _replay_anchor_render(admission: AnchorRenderAdmission) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'rendererFailure',
            'The Companion lost an AI Select Anchor publication before it completed.',
        )

    def _complete_anchor_render(
        self,
        key: str,
        admission: AnchorRenderAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
        timing: AnchorServerTiming | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single GPU slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select Anchor completion requires one outcome')
        if response is None:
            publication = None
        elif timing is None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        else:
            with timing.measure('json-base64'):
                publication = json.dumps(
                    response, separators=(',', ':'), sort_keys=True, allow_nan=False
                )
        with self._session_lock:
            current = self._anchor_render_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_anchor_render == key:
                self._active_anchor_render = None
            admission.completed.set()

    @staticmethod
    def _support_probe_request_key(request: AISelectSupportProbeRequest) -> str:
        """Canonicalize every immutable input that can affect one support probe."""

        return json.dumps(
            request.identity_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_support_probe(
        self, request: AISelectSupportProbeRequest
    ) -> tuple[str, SupportProbeAdmission, bool]:
        """Reserve or join one bound probe publication without holding locks for it."""

        key = self._support_probe_request_key(request)
        with self._session_lock:
            admission = self._support_probe_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # Completed admissions are dropped at the next admission: a newer
            # current binding makes older verdicts stale, so lost-response
            # recovery replays only the still-running attempt.
            self._support_probe_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._support_probe_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = SupportProbeAdmission()
            self._support_probe_admissions[key] = admission
            self._active_support_probe = key
        return key, admission, True

    @staticmethod
    def _replay_support_probe(admission: SupportProbeAdmission) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'supportProbeFailure',
            'The Companion lost an AI Select Anchor support probe publication before it completed.',
        )

    def _complete_support_probe(
        self,
        key: str,
        admission: SupportProbeAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select Anchor support probe completion requires one outcome')
        publication = None
        if response is not None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        with self._session_lock:
            current = self._support_probe_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_support_probe == key:
                self._active_support_probe = None
            admission.completed.set()

    @staticmethod
    def _mask_request_key(request: AISelectMaskRequest) -> str:
        """Canonicalize every immutable input that can affect one mask attempt."""

        return json.dumps(
            request.identity_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_mask_request(
        self, request: AISelectMaskRequest
    ) -> tuple[str, MaskRequestAdmission, bool]:
        """Reserve or join one bound mask attempt without holding locks for it."""

        key = self._mask_request_key(request)
        with self._session_lock:
            admission = self._mask_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # A replay record can contain a full-resolution mask. Retain only
            # the most recent completed request for lost-response recovery;
            # a different current binding makes older products stale anyway.
            self._mask_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._mask_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = MaskRequestAdmission()
            self._mask_admissions[key] = admission
            self._active_mask_request = key
        return key, admission, True

    @staticmethod
    def _replay_mask_request(admission: MaskRequestAdmission) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'modelFailure',
            'The Companion lost a single-frame mask publication before it completed.',
        )

    def _complete_mask_request(
        self,
        key: str,
        admission: MaskRequestAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select Mask completion requires one outcome')
        publication = None
        if response is not None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        with self._session_lock:
            current = self._mask_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_mask_request == key:
                self._active_mask_request = None
            admission.completed.set()

    def _release_all_transient_caches_locked(self) -> None:
        self._anchor_render_admissions.clear()
        self._mask_admissions.clear()
        self._support_probe_admissions.clear()
        self._target_geometry_hint_admissions.clear()
        self._local_key_view_plan_admissions.clear()
        self._generated_view_mask_admissions.clear()
        # Target disposal invalidates every Companion-held RGB reference and
        # previous-prediction logits reference with the same transaction.
        self._rgb_cache.clear()
        self._logits_store.clear()
        with self._frame_lock:
            self._frame_sets.clear()
        with self._scene_lock:
            self._scene_snapshots.clear()

    def produce_ai_select_target_geometry_hint(
        self, request: Mapping[str, object]
    ) -> dict[str, object]:
        """Publish the compact visible-surface Target Geometry Hint.

        The browser owns the confirmed Anchor identity. This state method
        validates those untrusted bindings, resolves the scene exactly like
        the support probe, reserves the single Companion operation slot, then
        derives the first-hit visible-surface hint outside every state lock.
        Derivation is pure CPU geometry: no RGB, no Contributor, no SAM, and
        no GPU work. The hint carries no Stable Gaussian IDs, no weights, and
        no ownership labels.
        """

        hint_request = self._parse_ai_select_target_geometry_hint_request(request)
        planes, miss = self._resolve_ai_select_scene_planes(
            scene_id=hint_request.scene_id,
            scene_version=hint_request.scene_version,
            render_config_version=hint_request.render_config_version,
            camera_binding=hint_request.camera_binding,
            scene_transport=hint_request.scene_transport,
            response_fields=hint_request.response_fields(),
            failure_code='geometryFailure',
            failure_label='AI Select Target Geometry Hint',
        )
        if miss is not None:
            return miss

        hint_key, admission, owns_admission = self._admit_target_geometry_hint(
            hint_request
        )
        if not owns_admission:
            return self._replay_target_geometry_hint(admission)

        try:
            try:
                derivation = derive_target_geometry_hint(
                    planes=planes,
                    camera=hint_request.probe_camera,
                    mask=hint_request.stable_mask,
                )
                if derivation is None:
                    raise MaskSessionError(
                        'geometryUnavailable',
                        'The confirmed Anchor Stable Mask has no usable first-hit visible support for the AI Select Target Geometry Hint.',
                    )
            except GeometryUnavailableError as error:
                raise MaskSessionError('geometryUnavailable', str(error)) from error
            except MaskSessionError:
                raise
            except Exception as error:
                raise MaskSessionError(
                    'geometryFailure',
                    'The Companion failed while deriving the AI Select Target Geometry Hint.',
                ) from error
            hint_payload: dict[str, object] = {
                'schemaVersion': TARGET_GEOMETRY_HINT_SCHEMA_VERSION,
                'targetContextId': hint_request.request_binding['targetContextId'],
                'anchorCameraBindingDigest': hint_request.anchor_camera_binding_digest,
                'anchorRgbDigest': hint_request.anchor_rgb_digest,
                'anchorStableMaskDigest': hint_request.stable_mask_digest,
                'geometryPolicyDigest': target_geometry_policy_digest(),
                'centerWorld': list(derivation.center),
                'extentWorld': list(derivation.extent),
                'visiblePoints': [list(point) for point in derivation.visible_points],
                'quality': derivation.quality,
                'reasons': list(derivation.reasons),
            }
            hint_payload['artifactDigest'] = _canonical_json_digest(hint_payload)
            response = {
                'status': 'complete',
                **hint_request.response_fields(),
                'hint': hint_payload,
            }
        except MaskSessionError as error:
            self._complete_target_geometry_hint(hint_key, admission, failure=error)
            raise
        except Exception as error:
            failure = MaskSessionError(
                'geometryFailure',
                'The Companion failed while publishing the AI Select Target Geometry Hint.',
            )
            self._complete_target_geometry_hint(hint_key, admission, failure=failure)
            raise failure from error

        self._complete_target_geometry_hint(hint_key, admission, response=response)
        return response

    def _parse_ai_select_target_geometry_hint_request(
        self, request: Mapping[str, object]
    ) -> AISelectTargetGeometryHintRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select Target Geometry Hint requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select Target Geometry Hint requestBinding dependencyToken must be an object'
            )
        target_splat_id = _anchor_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _anchor_string(dependency_value.get('splatId'), 'dependency splatId'),
            'renderStateToken': _anchor_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _anchor_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _anchor_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _anchor_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select Target Geometry Hint targetSplatId must match its dependency splatId'
            )
        request_binding: dict[str, object] = {
            'targetContextId': _anchor_string(
                request_binding_value.get('targetContextId'), 'targetContextId'
            ),
            'contextRevision': _anchor_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        scene_id = _anchor_string(request.get('sceneId'), 'sceneId')
        scene_version = _anchor_string(request.get('sceneVersion'), 'sceneVersion')
        if scene_id != target_splat_id:
            raise ValueError(
                'AI Select Target Geometry Hint sceneId must match its targetSplatId'
            )
        render_config_version = _anchor_string(
            request.get('renderConfigVersion'), 'renderConfigVersion'
        )
        geometry_attempt_id = _anchor_string(
            request.get('geometryAttemptId'), 'geometryAttemptId'
        )
        anchor_camera_binding_digest = _anchor_sha256_digest(
            request.get('anchorCameraBindingDigest'), 'hint anchorCameraBindingDigest'
        )
        anchor_rgb_digest = _anchor_sha256_digest(
            request.get('anchorRgbDigest'), 'hint anchorRgbDigest'
        )
        if (
            request.get('geometryPolicyVersion')
            != AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION
        ):
            raise ValueError(
                'AI Select Target Geometry Hint geometryPolicyVersion is unsupported'
            )
        scene_transport = request.get('sceneTransport', 'packed-v1')
        if scene_transport not in ('packed-v1', 'spatial-v1'):
            raise ValueError(
                'AI Select Target Geometry Hint sceneTransport is unsupported'
            )

        camera_binding, renderer_camera, width, height = (
            self._parse_ai_select_anchor_camera(request.get('anchorCameraBinding'))
        )
        probe_camera = probe_camera_from_renderer_camera(
            renderer_camera, width=width, height=height
        )
        stable_mask, stable_mask_digest = self._parse_ai_select_support_probe_mask(
            request.get('anchorStableMask'), width=width, height=height
        )
        return AISelectTargetGeometryHintRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            scene_id=scene_id,
            scene_version=scene_version,
            render_config_version=render_config_version,
            geometry_attempt_id=geometry_attempt_id,
            camera_binding=camera_binding,
            probe_camera=probe_camera,
            anchor_camera_binding_digest=anchor_camera_binding_digest,
            anchor_rgb_digest=anchor_rgb_digest,
            stable_mask=stable_mask,
            stable_mask_digest=stable_mask_digest,
            scene_transport=scene_transport,
        )

    @staticmethod
    def _target_geometry_hint_request_key(
        request: AISelectTargetGeometryHintRequest,
    ) -> str:
        """Canonicalize every immutable input that can affect one hint."""

        return json.dumps(
            request.identity_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_target_geometry_hint(
        self, request: AISelectTargetGeometryHintRequest
    ) -> tuple[str, TargetGeometryHintAdmission, bool]:
        """Reserve or join one bound hint publication without holding locks for it."""

        key = self._target_geometry_hint_request_key(request)
        with self._session_lock:
            admission = self._target_geometry_hint_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # A completed admission stays replayable for lost-response
            # recovery; a different request's admission then evicts every
            # completed record here, because a newer current binding makes
            # older hints stale anyway.
            self._target_geometry_hint_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._target_geometry_hint_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = TargetGeometryHintAdmission()
            self._target_geometry_hint_admissions[key] = admission
            self._active_target_geometry_hint = key
        return key, admission, True

    @staticmethod
    def _replay_target_geometry_hint(
        admission: TargetGeometryHintAdmission,
    ) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'geometryFailure',
            'The Companion lost an AI Select Target Geometry Hint publication before it completed.',
        )

    def _complete_target_geometry_hint(
        self,
        key: str,
        admission: TargetGeometryHintAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select Target Geometry Hint completion requires one outcome')
        publication = None
        if response is not None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        with self._session_lock:
            current = self._target_geometry_hint_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_target_geometry_hint == key:
                self._active_target_geometry_hint = None
            admission.completed.set()

    def plan_ai_select_local_key_views(
        self, request: Mapping[str, object]
    ) -> dict[str, object]:
        """Publish one bounded local Key-View batch from a verified hint.

        Planning is pure CPU over the fail-closed validated Target Geometry
        Hint: no scene resolution, no RGB, no Contributor, no SAM, and no GPU
        work. The untrusted hint must replay its own canonical artifact
        digest and bind the exact Anchor camera/RGB/Mask identities of this
        request before any candidate camera is planned.
        """

        plan_request = self._parse_ai_select_local_key_view_plan_request(request)
        plan_key, admission, owns_admission = self._admit_local_key_view_plan(
            plan_request
        )
        if not owns_admission:
            return self._replay_local_key_view_plan(admission)

        try:
            try:
                views = plan_local_key_views(
                    anchor_camera_binding=plan_request.camera_binding,
                    center=plan_request.target_geometry_hint['centerWorld'],  # type: ignore[arg-type]
                    extent=plan_request.target_geometry_hint['extentWorld'],  # type: ignore[arg-type]
                    visible_points=plan_request.target_geometry_hint['visiblePoints'],  # type: ignore[arg-type]
                    batch_ordinal=plan_request.batch_ordinal,
                )
            except PlanExhaustedError as error:
                raise MaskSessionError('planExhausted', str(error)) from error
            except PlannerFailureError as error:
                raise MaskSessionError('plannerFailure', str(error)) from error
            except MaskSessionError:
                raise
            except Exception as error:
                raise MaskSessionError(
                    'plannerFailure',
                    'The Companion failed while planning the AI Select local Key Views.',
                ) from error
            plan_payload: dict[str, object] = {
                'schemaVersion': LOCAL_KEY_VIEW_PLAN_SCHEMA_VERSION,
                'targetContextId': plan_request.request_binding['targetContextId'],
                'anchorStableMaskDigest': plan_request.stable_mask_digest,
                'targetGeometryHintDigest': (
                    plan_request.target_geometry_hint['artifactDigest']
                ),
                'localViewPolicyDigest': local_key_view_policy_digest(),
                'orderedViews': [
                    {
                        'viewId': view.view_id,
                        'cameraBinding': view.camera_binding,
                        'quality': view.quality,
                        'reasons': list(view.reasons),
                    }
                    for view in views
                ],
                'planAttemptId': plan_request.plan_attempt_id,
            }
            plan_payload['artifactDigest'] = _canonical_json_digest(plan_payload)
            response = {
                'status': 'complete',
                **plan_request.response_fields(),
                'plan': plan_payload,
            }
        except MaskSessionError as error:
            self._complete_local_key_view_plan(plan_key, admission, failure=error)
            raise
        except Exception as error:
            failure = MaskSessionError(
                'plannerFailure',
                'The Companion failed while publishing the AI Select local Key View plan.',
            )
            self._complete_local_key_view_plan(plan_key, admission, failure=failure)
            raise failure from error

        self._complete_local_key_view_plan(plan_key, admission, response=response)
        return response

    def _parse_ai_select_local_key_view_plan_request(
        self, request: Mapping[str, object]
    ) -> AISelectLocalKeyViewPlanRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select local Key View plan requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select local Key View plan requestBinding dependencyToken must be an object'
            )
        target_splat_id = _anchor_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _anchor_string(dependency_value.get('splatId'), 'dependency splatId'),
            'renderStateToken': _anchor_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _anchor_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _anchor_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _anchor_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select local Key View plan targetSplatId must match its dependency splatId'
            )
        target_context_id = _anchor_string(
            request_binding_value.get('targetContextId'), 'targetContextId'
        )
        request_binding: dict[str, object] = {
            'targetContextId': target_context_id,
            'contextRevision': _anchor_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        plan_attempt_id = _anchor_string(
            request.get('planAttemptId'), 'planAttemptId'
        )
        batch_ordinal = _anchor_nonnegative_integer(
            request.get('batchOrdinal'), 'batchOrdinal'
        )
        anchor_camera_binding_digest = _anchor_sha256_digest(
            request.get('anchorCameraBindingDigest'), 'plan anchorCameraBindingDigest'
        )
        anchor_rgb_digest = _anchor_sha256_digest(
            request.get('anchorRgbDigest'), 'plan anchorRgbDigest'
        )
        stable_mask_digest = _anchor_sha256_digest(
            request.get('anchorStableMaskDigest'), 'plan anchorStableMaskDigest'
        )
        if (
            request.get('localViewPolicyVersion')
            != AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION
        ):
            raise ValueError(
                'AI Select local Key View plan localViewPolicyVersion is unsupported'
            )

        camera_binding, _, _, _ = self._parse_ai_select_anchor_camera(
            request.get('anchorCameraBinding')
        )
        target_geometry_hint = self._parse_ai_select_target_geometry_hint(
            request.get('targetGeometryHint'),
            target_context_id=target_context_id,
            anchor_camera_binding_digest=anchor_camera_binding_digest,
            anchor_rgb_digest=anchor_rgb_digest,
            stable_mask_digest=stable_mask_digest,
        )
        return AISelectLocalKeyViewPlanRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            plan_attempt_id=plan_attempt_id,
            batch_ordinal=batch_ordinal,
            camera_binding=camera_binding,
            anchor_camera_binding_digest=anchor_camera_binding_digest,
            anchor_rgb_digest=anchor_rgb_digest,
            stable_mask_digest=stable_mask_digest,
            target_geometry_hint=target_geometry_hint,
        )

    @staticmethod
    def _parse_ai_select_target_geometry_hint(
        value: object,
        *,
        target_context_id: str,
        anchor_camera_binding_digest: str,
        anchor_rgb_digest: str,
        stable_mask_digest: str,
    ) -> dict[str, object]:
        """Fail-closed validation of the untrusted Target Geometry Hint.

        The hint is a Companion-produced artifact replayed by the browser; it
        is trusted only after its structure, identity bindings, and canonical
        artifact digest all verify. Any mismatch rejects the whole request.
        """

        if not isinstance(value, dict):
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint must be an object'
            )
        if value.get('schemaVersion') != TARGET_GEOMETRY_HINT_SCHEMA_VERSION:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint schemaVersion is unsupported'
            )
        hint_target_context_id = value.get('targetContextId')
        if not isinstance(hint_target_context_id, str) or not hint_target_context_id:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint targetContextId must be a non-empty string'
            )
        if hint_target_context_id != target_context_id:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint targetContextId must match its requestBinding'
            )
        hint_camera_digest = _anchor_sha256_digest(
            value.get('anchorCameraBindingDigest'),
            'targetGeometryHint anchorCameraBindingDigest',
        )
        hint_rgb_digest = _anchor_sha256_digest(
            value.get('anchorRgbDigest'), 'targetGeometryHint anchorRgbDigest'
        )
        hint_mask_digest = _anchor_sha256_digest(
            value.get('anchorStableMaskDigest'),
            'targetGeometryHint anchorStableMaskDigest',
        )
        _anchor_sha256_digest(
            value.get('geometryPolicyDigest'),
            'targetGeometryHint geometryPolicyDigest',
        )
        artifact_digest = _anchor_sha256_digest(
            value.get('artifactDigest'), 'targetGeometryHint artifactDigest'
        )
        if hint_camera_digest != anchor_camera_binding_digest:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint anchorCameraBindingDigest must match the request'
            )
        if hint_rgb_digest != anchor_rgb_digest:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint anchorRgbDigest must match the request'
            )
        if hint_mask_digest != stable_mask_digest:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint anchorStableMaskDigest must match the request'
            )
        _anchor_number_sequence(
            value.get('centerWorld'), 3, 'targetGeometryHint centerWorld'
        )
        _anchor_number_sequence(
            value.get('extentWorld'), 3, 'targetGeometryHint extentWorld'
        )
        visible_points = value.get('visiblePoints')
        if (
            not isinstance(visible_points, list)
            or len(visible_points) < 1
            or len(visible_points) > 64
        ):
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint visiblePoints must contain 1..64 points'
            )
        for index, point in enumerate(visible_points):
            _anchor_number_sequence(
                point, 3, f'targetGeometryHint visiblePoints[{index}]'
            )
        quality = value.get('quality')
        if quality not in ('usable', 'limited', 'unavailable'):
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint quality is unsupported'
            )
        if quality == 'unavailable':
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint quality unavailable cannot plan Key Views'
            )
        reasons = value.get('reasons')
        if not isinstance(reasons, list) or any(
            not isinstance(reason, str) for reason in reasons
        ):
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint reasons must be a list of strings'
            )
        recomputed = _canonical_json_digest(
            {key: entry for key, entry in value.items() if key != 'artifactDigest'}
        )
        if recomputed != artifact_digest:
            raise ValueError(
                'AI Select local Key View plan targetGeometryHint artifactDigest does not match its payload'
            )
        return value

    @staticmethod
    def _local_key_view_plan_request_key(
        request: AISelectLocalKeyViewPlanRequest,
    ) -> str:
        """Canonicalize every immutable input that can affect one plan."""

        return json.dumps(
            request.identity_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_local_key_view_plan(
        self, request: AISelectLocalKeyViewPlanRequest
    ) -> tuple[str, LocalKeyViewPlanAdmission, bool]:
        """Reserve or join one bound plan publication without holding locks for it."""

        key = self._local_key_view_plan_request_key(request)
        with self._session_lock:
            admission = self._local_key_view_plan_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # A completed admission stays replayable for lost-response
            # recovery; a different request's admission then evicts every
            # completed record here, because a newer current binding makes
            # older plans stale anyway.
            self._local_key_view_plan_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._local_key_view_plan_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = LocalKeyViewPlanAdmission()
            self._local_key_view_plan_admissions[key] = admission
            self._active_local_key_view_plan = key
        return key, admission, True

    @staticmethod
    def _replay_local_key_view_plan(
        admission: LocalKeyViewPlanAdmission,
    ) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'plannerFailure',
            'The Companion lost an AI Select local Key View plan publication before it completed.',
        )

    def _complete_local_key_view_plan(
        self,
        key: str,
        admission: LocalKeyViewPlanAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select local Key View plan completion requires one outcome')
        publication = None
        if response is not None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        with self._session_lock:
            current = self._local_key_view_plan_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_local_key_view_plan == key:
                self._active_local_key_view_plan = None
            admission.completed.set()

    def produce_ai_select_generated_view_mask(
        self, request: Mapping[str, object]
    ) -> dict[str, object]:
        """Publish one propagated automatic Mask for a Generated View.

        The Companion projects the confirmed Anchor's mask-conditioned
        Gaussian support into the Generated View camera, synthesizes
        deterministic include prompts, and runs exactly one single-frame SAM
        pass on the bound Generated View RGB. An Anchor support set that does
        not project into the View fails Mask production closed; it never
        demotes the RGB Ready View.
        """

        mask_request = self._parse_ai_select_generated_view_mask_request(request)
        model, adapter = self._require_mask_adapter(mask_request.model_manifest_digest)
        planes, miss = self._resolve_ai_select_scene_planes(
            scene_id=mask_request.scene_id,
            scene_version=mask_request.scene_version,
            render_config_version=mask_request.render_config_version,
            camera_binding=mask_request.anchor_camera_binding,
            scene_transport=mask_request.scene_transport,
            response_fields=mask_request.response_fields(),
            failure_code='modelFailure',
            failure_label='AI Select Generated View Mask production',
        )
        if miss is not None:
            return miss

        mask_key, admission, owns_admission = self._admit_generated_view_mask(
            mask_request
        )
        if not owns_admission:
            return self._replay_generated_view_mask(admission)

        try:
            try:
                synthesized = synthesize_view_prompts(
                    planes=planes,
                    anchor_camera=mask_request.anchor_probe_camera,
                    view_camera=mask_request.view_probe_camera,
                    mask=mask_request.stable_mask,
                )
                if synthesized is None:
                    raise MaskSessionError(
                        'propagationUnavailable',
                        'The confirmed Anchor Stable Mask support is not observable from this Generated View camera; adjust the View or draw the Mask manually.',
                    )
                frame_set = register_frame_set({
                    'frameSetId': f'ai-select-mask-{mask_request.view_id}',
                    'frameSetVersion': (
                        f'{mask_request.view_id}-{mask_request.rgb_digest}'
                    ),
                    'orderedViews': [{
                        'viewId': mask_request.view_id,
                        'frameDigest': mask_request.rgb_digest,
                        'width': mask_request.width,
                        'height': mask_request.height,
                        'imagePngBase64': base64.b64encode(
                            mask_request.rgb_png
                        ).decode('ascii'),
                        'source': 'generated',
                    }],
                })
                prompt_log: list[dict[str, object]] = [
                    {
                        'operation': 'New',
                        'prompt': {
                            'promptId': f'propagated-prompt-{index + 1}',
                            'viewId': mask_request.view_id,
                            'frameDigest': mask_request.rgb_digest,
                            'frameWidth': mask_request.width,
                            'frameHeight': mask_request.height,
                            'xPx': x_px,
                            'yPx': y_px,
                            'polarity': 'include',
                        },
                    }
                    for index, (x_px, y_px) in enumerate(synthesized.prompts)
                ]
                production = adapter.produce_tracks(
                    model=model,
                    frame_set=frame_set,
                    prompt_log=prompt_log,
                    cancelled=lambda: False,
                )
            except MaskSessionError:
                raise
            except Exception as error:
                raise MaskSessionError(
                    'modelFailure',
                    'The promptable-mask adapter failed; verify the installed model runtime and retry.',
                ) from error
            tracks, _diagnostics, _threshold = self._normalise_mask_production(
                production
            )
            self._validate_complete_tracks(frame_set, prompt_log, tracks)
            primary_track = next(
                track for track in tracks if track['trackId'] == 'primary'
            )
            view_frame = next(
                frame
                for frame in primary_track['frames']
                if frame['viewId'] == mask_request.view_id
            )
            binary_mask = view_frame['binaryMask']
            # The propagated product contract publishes bitset bytes only;
            # dimensions, payload length, and trailing bits were validated
            # with the complete tracks above.
            if binary_mask.get('encoding') != 'bitset-lsb-v1':
                raise MaskSessionError(
                    'incompleteMaskSet',
                    'A propagated Generated View mask must use the bitset-lsb-v1 encoding.',
                )
            mask_bytes = base64.b64decode(binary_mask['data'], validate=True)
            mask_digest = f'sha256:{hashlib.sha256(mask_bytes).hexdigest()}'
            try:
                # Mask Review consumes the exact produced Mask and the
                # synthesized include-point Prompt family only; Gaussian
                # visibility/support belongs to Ticket 13 Lift Readiness.
                assessment_payload = _local_view_assessment_payload(
                    rgb_digest=mask_request.rgb_digest,
                    stable_mask_digest=mask_digest,
                    width=mask_request.width,
                    height=mask_request.height,
                    mask=mask_bytes,
                    positive_points=synthesized.prompts,
                )
            except Exception:
                # Assessment is derived from an already valid automatic Mask.
                # Its failure must fail closed without discarding that Mask or
                # inventing a user-visible cause.
                assessment_payload = _failed_local_view_assessment_payload(
                    rgb_digest=mask_request.rgb_digest,
                    stable_mask_digest=mask_digest,
                )
            response = {
                'status': 'complete',
                **mask_request.response_fields(),
                'rgbDigest': mask_request.rgb_digest,
                'anchorRgbDigest': mask_request.anchor_rgb_digest,
                'mask': {
                    'encoding': 'bitset-lsb-v1',
                    'width': mask_request.width,
                    'height': mask_request.height,
                    'data': binary_mask['data'],
                    'digest': mask_digest,
                },
                'maskSource': 'propagated',
                'maskPropagation': {
                    'policyVersion': AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION,
                    'projectedSupportCount': synthesized.projected_support_count,
                    'promptCount': len(synthesized.prompts),
                },
                'assessment': assessment_payload,
                'modelManifestDigest': mask_request.model_manifest_digest,
            }
        except MaskSessionError as error:
            self._complete_generated_view_mask(mask_key, admission, failure=error)
            raise
        except Exception as error:
            failure = MaskSessionError(
                'modelFailure',
                'The promptable-mask adapter failed while publishing the propagated mask.',
            )
            self._complete_generated_view_mask(mask_key, admission, failure=failure)
            raise failure from error

        self._complete_generated_view_mask(mask_key, admission, response=response)
        return response

    def _parse_ai_select_generated_view_mask_request(
        self, request: Mapping[str, object]
    ) -> AISelectGeneratedViewMaskRequest:
        request_binding_value = request.get('requestBinding')
        if not isinstance(request_binding_value, dict):
            raise ValueError('AI Select Generated View Mask requestBinding must be an object')
        dependency_value = request_binding_value.get('dependencyToken')
        if not isinstance(dependency_value, dict):
            raise ValueError(
                'AI Select Generated View Mask requestBinding dependencyToken must be an object'
            )
        target_splat_id = _anchor_string(
            request.get('targetSplatId'), 'targetSplatId'
        )
        dependency_token = {
            'splatId': _anchor_string(dependency_value.get('splatId'), 'dependency splatId'),
            'renderStateToken': _anchor_string(
                dependency_value.get('renderStateToken'), 'dependency renderStateToken'
            ),
            'geometryToken': _anchor_string(
                dependency_value.get('geometryToken'), 'dependency geometryToken'
            ),
            'gaussianIdentityToken': _anchor_string(
                dependency_value.get('gaussianIdentityToken'),
                'dependency gaussianIdentityToken',
            ),
            'worldTransformToken': _anchor_string(
                dependency_value.get('worldTransformToken'),
                'dependency worldTransformToken',
            ),
        }
        if dependency_token['splatId'] != target_splat_id:
            raise ValueError(
                'AI Select Generated View Mask targetSplatId must match its dependency splatId'
            )
        request_binding: dict[str, object] = {
            'targetContextId': _anchor_string(
                request_binding_value.get('targetContextId'), 'targetContextId'
            ),
            'contextRevision': _anchor_nonnegative_integer(
                request_binding_value.get('contextRevision'), 'contextRevision'
            ),
            'dependencyToken': dependency_token,
        }
        scene_id = _anchor_string(request.get('sceneId'), 'sceneId')
        scene_version = _anchor_string(request.get('sceneVersion'), 'sceneVersion')
        if scene_id != target_splat_id:
            raise ValueError(
                'AI Select Generated View Mask sceneId must match its targetSplatId'
            )
        render_config_version = _anchor_string(
            request.get('renderConfigVersion'), 'renderConfigVersion'
        )
        view_id = _anchor_string(request.get('viewId'), 'viewId')
        if view_id == 'anchor-view':
            raise ValueError(
                'AI Select Generated View Mask viewId anchor-view is reserved for the Anchor route'
            )
        mask_attempt_id = _anchor_string(
            request.get('maskAttemptId'), 'maskAttemptId'
        )
        model_manifest_digest = _anchor_string(
            request.get('modelManifestDigest'), 'modelManifestDigest'
        )
        scene_transport = request.get('sceneTransport', 'packed-v1')
        if scene_transport not in ('packed-v1', 'spatial-v1'):
            raise ValueError(
                'AI Select Generated View Mask sceneTransport is unsupported'
            )

        view_camera_binding, view_renderer_camera, width, height = (
            self._parse_ai_select_anchor_camera(request.get('viewCameraBinding'))
        )
        view_probe_camera = probe_camera_from_renderer_camera(
            view_renderer_camera, width=width, height=height
        )
        rgb_png, rgb_digest, rgb_width, rgb_height = self._parse_ai_select_mask_rgb(
            request.get('rgb')
        )
        if rgb_width != width or rgb_height != height:
            raise ValueError(
                'AI Select Generated View Mask rgb dimensions must match its viewCameraBinding projection'
            )

        anchor_value = request.get('anchor')
        if not isinstance(anchor_value, dict):
            raise ValueError('AI Select Generated View Mask anchor must be an object')
        anchor_camera_binding, anchor_renderer_camera, anchor_width, anchor_height = (
            self._parse_ai_select_anchor_camera(anchor_value.get('cameraBinding'))
        )
        anchor_probe_camera = probe_camera_from_renderer_camera(
            anchor_renderer_camera, width=anchor_width, height=anchor_height
        )
        anchor_rgb_digest = _anchor_sha256_digest(
            anchor_value.get('rgbDigest'), 'anchor rgbDigest'
        )
        stable_mask, stable_mask_digest = self._parse_ai_select_support_probe_mask(
            anchor_value.get('stableMask'), width=anchor_width, height=anchor_height
        )
        return AISelectGeneratedViewMaskRequest(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            scene_id=scene_id,
            scene_version=scene_version,
            render_config_version=render_config_version,
            view_id=view_id,
            view_camera_binding=view_camera_binding,
            view_probe_camera=view_probe_camera,
            mask_attempt_id=mask_attempt_id,
            rgb_png=rgb_png,
            rgb_digest=rgb_digest,
            width=width,
            height=height,
            anchor_camera_binding=anchor_camera_binding,
            anchor_probe_camera=anchor_probe_camera,
            anchor_rgb_digest=anchor_rgb_digest,
            stable_mask=stable_mask,
            stable_mask_digest=stable_mask_digest,
            model_manifest_digest=model_manifest_digest,
            scene_transport=scene_transport,
        )

    @staticmethod
    def _generated_view_mask_request_key(
        request: AISelectGeneratedViewMaskRequest,
    ) -> str:
        """Canonicalize every immutable input that can affect one mask attempt."""

        return json.dumps(
            request.identity_fields(),
            separators=(',', ':'),
            sort_keys=True,
            allow_nan=False,
        )

    def _admit_generated_view_mask(
        self, request: AISelectGeneratedViewMaskRequest
    ) -> tuple[str, GeneratedViewMaskAdmission, bool]:
        """Reserve or join one bound mask attempt without holding locks for it."""

        key = self._generated_view_mask_request_key(request)
        with self._session_lock:
            admission = self._generated_view_mask_admissions.get(key)
            if admission is not None:
                return key, admission, False
            if self._operation_slot_in_use_locked():
                raise MaskSessionError(
                    'capacityFull',
                    'The Companion is already serving another AI or Object Selection operation.',
                )
            # A replay record can contain a full-resolution mask. A completed
            # admission stays replayable for lost-response recovery; a
            # different request's admission then evicts every completed record
            # here, because a newer current binding makes older products stale.
            self._generated_view_mask_admissions = {
                completed_key: completed_admission
                for completed_key, completed_admission
                in self._generated_view_mask_admissions.items()
                if not completed_admission.completed.is_set()
            }
            admission = GeneratedViewMaskAdmission()
            self._generated_view_mask_admissions[key] = admission
            self._active_generated_view_mask = key
        return key, admission, True

    @staticmethod
    def _replay_generated_view_mask(
        admission: GeneratedViewMaskAdmission,
    ) -> dict[str, object]:
        """Wait for a matching request, then return only its immutable outcome."""

        admission.completed.wait()
        if admission.publication is not None:
            return json.loads(admission.publication)
        if admission.failure is not None:
            raise MaskSessionError(*admission.failure)
        raise MaskSessionError(
            'modelFailure',
            'The Companion lost a propagated mask publication before it completed.',
        )

    def _complete_generated_view_mask(
        self,
        key: str,
        admission: GeneratedViewMaskAdmission,
        *,
        response: dict[str, object] | None = None,
        failure: MaskSessionError | None = None,
    ) -> None:
        """Atomically publish one replay result and release the single slot."""

        if (response is None) == (failure is None):
            raise ValueError('AI Select Generated View Mask completion requires one outcome')
        publication = None
        if response is not None:
            publication = json.dumps(
                response, separators=(',', ':'), sort_keys=True, allow_nan=False
            )
        with self._session_lock:
            current = self._generated_view_mask_admissions.get(key)
            if current is not admission:
                return
            if publication is not None:
                admission.publication = publication
            else:
                assert failure is not None
                admission.failure = (failure.code, str(failure))
            if self._active_generated_view_mask == key:
                self._active_generated_view_mask = None
            admission.completed.set()

    def _resolve_ai_select_scene_planes(
        self,
        *,
        scene_id: str,
        scene_version: str,
        render_config_version: str,
        camera_binding: Mapping[str, object],
        scene_transport: str,
        response_fields: dict[str, object],
        failure_code: str,
        failure_label: str,
    ) -> tuple[list[tuple[memoryview, memoryview]], dict[str, object] | None]:
        """Resolve immutable Gaussian planes or a bound scene miss response.

        The resolution is identical to the Anchor support probe: spatial
        working sets expose their resident chunk mmap planes, and packed
        binary snapshots expose the whole-scene planes. A cache or chunk miss
        returns bound identity echoes so the editor can re-register or upload
        exactly once before one bounded retry.
        """

        planes: list[tuple[memoryview, memoryview]] = []
        if scene_transport == 'spatial-v1':
            try:
                resolution = self._spatial_scene_store.resolve_working_set(
                    scene_id,
                    scene_version,
                    camera_binding,
                )
            except SnapshotUploadError:
                return planes, {
                    'status': 'sceneCacheMiss',
                    **response_fields,
                }
            if resolution.missing_chunk_ids:
                return planes, {
                    'status': 'sceneChunkMiss',
                    **response_fields,
                    'workingSetToken': resolution.working_set_token,
                    'missingChunkIds': list(resolution.missing_chunk_ids),
                }
            if resolution.working_set is None:
                raise ValueError(
                    f'{failure_label} Spatial Scene working set is incomplete'
                )
            render_configuration = (
                resolution.working_set.manifest.render_configuration
            )
            if (
                render_configuration.get('version')
                != render_config_version
            ):
                raise ValueError(
                    f'{failure_label} render configuration does not match the registered Spatial Scene manifest'
                )
            # Resident chunks expose their immutable mmap planes directly; the
            # policies never materialize the renderer's torch tensor views.
            planes.extend(
                (chunk.field('means'), chunk.field('logitOpacities'))
                for chunk in resolution.working_set.chunks
            )
        else:
            snapshot = self.scene_snapshot(scene_id, scene_version)
            if snapshot is None:
                return planes, {
                    'status': 'sceneCacheMiss',
                    **response_fields,
                }
            if snapshot.render_config_version != render_config_version:
                raise ValueError(
                    f'{failure_label} render configuration does not match the registered Scene Snapshot'
                )
            if not isinstance(snapshot.scene, PackedBinarySceneSnapshot):
                raise MaskSessionError(
                    failure_code,
                    f'{failure_label} requires a packed binary Scene Snapshot.',
                )
            planes.append(
                (snapshot.scene.field('means'), snapshot.scene.field('logitOpacities'))
            )
        return planes, None

    def _discard_unclaimed_frame_set(self, frame_set_version: str | None) -> None:
        if frame_set_version is None:
            return
        with self._mask_lock:
            if any(
                session.frame_set_version == frame_set_version
                for session in self._mask_sessions.values()
            ):
                return
        with self._frame_lock:
            self._frame_sets.pop(frame_set_version, None)

    @staticmethod
    def _normalise_mask_production(
        production: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, float]:
        """Freeze generic diagnostics together with the complete tracks."""

        if not isinstance(production, MaskProduction):
            raise MaskSessionError(
                "incompleteMaskSet",
                "The promptable-mask adapter must bind a threshold with its complete Mask Set.",
            )
        tracks = production.tracks
        diagnostics = production.diagnostics
        threshold = production.threshold
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or threshold < 0
            or threshold > 1
        ):
            raise MaskSessionError(
                "invalidThreshold",
                "Promptable-mask adapter threshold must be a finite probability from zero through one.",
        )
        if diagnostics is None:
            return tracks, None, float(threshold)
        if not isinstance(diagnostics, dict):
            raise MaskSessionError(
                "invalidDiagnostics",
                "Promptable-mask adapter diagnostics must be a JSON object.",
            )
        try:
            # JSON round-tripping rejects runtime handles and makes the cached
            # diagnostic payload independent of any mutable adapter object.
            return (
                tracks,
                json.loads(
                    json.dumps(
                        diagnostics,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    )
                ),
                float(threshold),
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidDiagnostics",
                "Promptable-mask adapter diagnostics must be JSON-compatible.",
            ) from error

    @staticmethod
    def _model_runtime_configuration_is_current(model: dict[str, Any]) -> bool:
        adapter_id = model.get("adapterId")
        if adapter_id == "sam3.1":
            return model.get("runtimeConfigDigest") == SAM31_RUNTIME_CONFIG_DIGEST
        if adapter_id == SAM3_IMAGE_INSTANCE_ADAPTER_ID:
            return (
                model.get("runtimeConfigDigest") == SAM3_IMAGE_RUNTIME_CONFIG_DIGEST
            )
        return True

    def _require_frame_set(self, frame_set_version: str) -> RegisteredFrameSet:
        with self._frame_lock:
            frame_set = self._frame_sets.get(frame_set_version)
        if frame_set is None:
            raise MaskSessionError(
                "frameSetUnavailable",
                "The requested Frame Set is unavailable; register the immutable Anchor Frame Set and retry.",
            )
        return frame_set

    def _require_mask_adapter(
        self, model_manifest_digest: str | None
    ) -> tuple[dict[str, Any], PromptableMaskAdapter]:
        if not isinstance(model_manifest_digest, str) or not model_manifest_digest:
            raise MaskSessionError(
                "invalidManifest", "A non-empty Model Manifest digest is required."
            )
        model = next(
            (
                available
                for available in self.available_models()
                if available.get("digest") == model_manifest_digest
            ),
            None,
        )
        if model is None:
            raise MaskSessionError(
                "modelUnavailable",
                "The requested Model Manifest is unavailable or its separately installed weights cannot be verified.",
            )
        adapter_id = model.get("adapterId")
        adapter = self.mask_adapters.get(adapter_id)
        if adapter is None:
            raise MaskSessionError(
                "incompatibleManifest",
                "The installed Model Manifest selects a promptable-mask adapter that is unavailable in this Companion runtime.",
            )
        return model, adapter

    @staticmethod
    def _mask_binding(bindings: dict[str, Any], name: str) -> str:
        value = bindings.get(name)
        if not isinstance(value, str) or not value:
            raise MaskSessionError(
                "invalidMaskSession", f"Mask Set {name} must be a non-empty string."
            )
        return value

    @staticmethod
    def _mask_binding_revision(bindings: dict[str, Any]) -> int:
        revision = bindings.get("promptLogRevision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise MaskSessionError(
                "invalidPromptLog", "Mask Set Prompt Log revision must be a non-negative integer."
            )
        return revision

    @staticmethod
    def _validate_mask_session_bindings(
        session: ActiveMaskSession,
        *,
        frame_set_version: str,
        model_manifest_digest: str,
        staged_frame_set_version: str | None = None,
    ) -> None:
        if (
            session.frame_set_version is not None
            and session.frame_set_version != frame_set_version
            and staged_frame_set_version != frame_set_version
        ):
            raise MaskSessionError(
                "staleFrameSet",
                "The Mask Set request Frame Set version does not match this Object Selection session.",
            )
        if (
            session.model_manifest_digest is not None
            and session.model_manifest_digest != model_manifest_digest
        ):
            raise MaskSessionError(
                "staleManifest",
                "The Mask Set request Model Manifest does not match this Object Selection session.",
            )

    @staticmethod
    def _validate_prompt_log_revision(
        session: ActiveMaskSession,
        *,
        prompt_log: list[Any],
        prompt_log_canonical: str,
        prompt_log_revision: int,
    ) -> None:
        if prompt_log_revision != len(prompt_log):
            raise MaskSessionError(
                "invalidPromptLog",
                "Prompt Log revision must equal the number of ordered point prompts.",
            )
        if prompt_log_revision < session.prompt_log_revision:
            raise MaskSessionError(
                "stalePromptLog", "The Mask Set request Prompt Log revision is stale."
            )
        if prompt_log_revision == session.prompt_log_revision:
            if prompt_log_canonical != session.prompt_log_canonical:
                raise MaskSessionError(
                    "stalePromptLog",
                    "The Mask Set request changes an already accepted Prompt Log revision.",
                )
            return
        accepted_prompt_log = json.loads(session.prompt_log_canonical)
        if prompt_log[: len(accepted_prompt_log)] != accepted_prompt_log:
            raise MaskSessionError(
                "stalePromptLog",
                "The Mask Set request must replay the accepted Prompt Log before adding prompts.",
            )

    @staticmethod
    def _is_nonnegative_integer(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    @staticmethod
    def _validate_binary_mask(
        binary_mask: Any,
        *,
        width: int,
        height: int,
    ) -> None:
        if (
            not isinstance(binary_mask, dict)
            or binary_mask.get("width") != width
            or binary_mask.get("height") != height
        ):
            raise MaskSessionError(
                "incompleteMaskSet",
                "Accepted Mask Set frames require a mask with the registered Frame Set dimensions.",
            )

        encoding = binary_mask.get("encoding")
        if encoding == "sparse-points-v1":
            foreground_pixels = binary_mask.get("foregroundPixels")
            if not isinstance(foreground_pixels, list) or not foreground_pixels:
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "Sparse Mask Set frames require one or more foreground pixels.",
                )
            previous_pixel = -1
            for pixel in foreground_pixels:
                if (
                    not isinstance(pixel, list)
                    or len(pixel) != 2
                    or not CompanionState._is_nonnegative_integer(pixel[0])
                    or not CompanionState._is_nonnegative_integer(pixel[1])
                ):
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be in-bounds integer coordinates.",
                    )
                x_px, y_px = pixel
                if x_px >= width or y_px >= height:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be in-bounds integer coordinates.",
                    )
                pixel_index = y_px * width + x_px
                if pixel_index <= previous_pixel:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be sorted and unique.",
                    )
                previous_pixel = pixel_index
            return

        if encoding == "bitset-lsb-v1":
            encoded_data = binary_mask.get("data")
            if not isinstance(encoded_data, str) or not encoded_data:
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set frames require base64 data."
                )
            try:
                data = base64.b64decode(encoded_data, validate=True)
            except (ValueError, binascii.Error) as error:
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set data must be valid base64."
                ) from error
            pixel_count = width * height
            if len(data) != (pixel_count + 7) // 8 or not any(data):
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "Bitset Mask Set data must contain every registered frame pixel and foreground.",
                )
            trailing_bits = pixel_count % 8
            if trailing_bits and data[-1] & ~((1 << trailing_bits) - 1):
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set data sets bits outside the registered frame."
                )
            return

        raise MaskSessionError(
            "incompleteMaskSet", "Accepted Mask Set frames use an unsupported binary mask encoding."
        )

    @staticmethod
    def _validate_complete_tracks(
        frame_set: RegisteredFrameSet,
        prompt_log: list[Any],
        tracks: Any,
    ) -> None:
        if not isinstance(tracks, list) or not tracks:
            raise MaskSessionError(
                "incompleteMaskSet", "The promptable-mask adapter did not return any Mask Tracks."
            )
        primary_frames: list[dict[str, Any]] | None = None
        track_ids: set[str] = set()
        for track in tracks:
            if (
                not isinstance(track, dict)
                or not isinstance(track.get("trackId"), str)
                or not track["trackId"]
                or track["trackId"] in track_ids
                or track.get("role") not in {"include", "exclude"}
                or not isinstance(track.get("frames"), list)
            ):
                raise MaskSessionError(
                    "incompleteMaskSet", "The promptable-mask adapter returned an invalid Mask Track."
                )
            track_ids.add(track["trackId"])
            frames = track["frames"]
            if len(frames) != len(frame_set.ordered_views):
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "The promptable-mask adapter must return every registered Frame Set view in order.",
                )
            for frame, expected_view in zip(frames, frame_set.ordered_views, strict=True):
                if not isinstance(frame, dict) or frame.get("viewId") != expected_view.view_id:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "The promptable-mask adapter must return every registered Frame Set view in order.",
                    )
                status = frame.get("status")
                if status not in {"accepted", "not_found", "rejected", "error"}:
                    raise MaskSessionError(
                        "incompleteMaskSet", "The promptable-mask adapter returned an unknown frame outcome."
                    )
                if status == "accepted":
                    CompanionState._validate_binary_mask(
                        frame.get("binaryMask"),
                        width=expected_view.width,
                        height=expected_view.height,
                    )
                elif "binaryMask" in frame or not isinstance(frame.get("rejectionReason"), str) or not frame["rejectionReason"].strip():
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Neutral Mask Set outcomes require an actionable reason and no binary mask.",
                    )
            if track["trackId"] == "primary":
                if track["role"] != "include" or primary_frames is not None:
                    raise MaskSessionError(
                        "incompleteMaskSet", "A New Mask Set requires one primary include Mask Track."
                    )
                primary_frames = frames

        if primary_frames is None:
            raise MaskSessionError(
                "incompleteMaskSet", "A New Mask Set requires its primary include Mask Track."
            )
        anchor_view_id = CompanionState._prompt_anchor_view(prompt_log)
        anchor_frame = next(
            (frame for frame in primary_frames if frame["viewId"] == anchor_view_id), None
        )
        if anchor_frame is None or anchor_frame["status"] != "accepted":
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View must have an accepted Mask Set outcome before preview can advance.",
            )

    @staticmethod
    def _prompt_anchor_view(prompt_log: list[Any]) -> str:
        for entry in prompt_log:
            if not isinstance(entry, dict) or entry.get("operation") != "New":
                continue
            prompt = entry.get("prompt")
            if isinstance(prompt, dict) and isinstance(prompt.get("viewId"), str):
                return prompt["viewId"]
        raise MaskSessionError(
            "invalidPromptLog", "A New Mask Set requires an Anchor View prompt."
        )

    def _model_artifact_is_current(self, model: dict[str, Any]) -> bool:
        try:
            weights_path = Path(model["weightsPath"])
            expected_digest = _normalise_sha256(model["checkpointDigest"])
            return weights_path.is_file() and _sha256(weights_path) == expected_digest
        except (KeyError, OSError, TypeError, ValueError):
            return False

    def _validate_scene_snapshot(
        self, snapshot: dict[str, Any]
    ) -> tuple[str, str, list[int], str]:
        # Registration is the attribution trust boundary. Reject unsupported
        # SuperSplat semantics before the immutable cache can be observed by a
        # mask/evidence request.
        stable_ids = list(validate_supported_snapshot(snapshot))
        render_configuration = snapshot["renderConfiguration"]
        return (
            snapshot["sceneId"],
            snapshot["sceneVersion"],
            stable_ids,
            render_configuration["version"],
        )

    def _operation_slot_in_use_locked(self) -> bool:
        """The single global AI/Object Selection operation slot; call under _session_lock."""
        return (
            self._active_object_selection_session is not None
            or self._active_anchor_render is not None
            or self._active_mask_request is not None
            or self._active_support_probe is not None
            or self._active_target_geometry_hint is not None
            or self._active_local_key_view_plan is not None
            or self._active_generated_view_mask is not None
        )

    def _capacity(self) -> dict[str, int]:
        with self._session_lock:
            return {
                "maximumActiveSessions": 1,
                "activeSessions": int(self._operation_slot_in_use_locked()),
            }

    def capabilities(self, allowed_editor_origins: list[str]) -> dict[str, Any]:
        release = self.require_release()
        manifests = []
        for model in self.available_models():
            if (
                not all(key in model for key in ("digest", "adapterId", "modelName"))
                or model["adapterId"] not in self.mask_adapters
            ):
                continue
            try:
                prompt_capabilities = _prompt_capabilities_for_adapter(
                    model["adapterId"]
                )
            except MaskSessionError:
                # Non-current fixtures (for example the legacy sam3.1
                # Multiplex adapter) have no current Prompt capability
                # contract and stay out of the advertised manifest list.
                continue
            manifests.append({
                "digest": model["digest"],
                "adapterId": model["adapterId"],
                "modelName": model["modelName"],
                "weightsBundled": False,
                "promptCapabilities": prompt_capabilities,
            })
        renderer_capability = self._renderer_capability(release)
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serviceBuild": f"selection-service-companion/{PACKAGE_VERSION}+{release['release']}",
            "renderer": renderer_capability,
            "supportedPromptKinds": ["point", "box"],
            "supportedOperations": [
                "aiSelectAnchorRender",
                "aiSelectAnchorReferenceContributor",
                "aiSelectAnchorSupportProbe",
                "aiSelectMaskProposals",
                "autoMaskProposalSetSchemaV3",
                "aiSelectTargetGeometryHint",
                "aiSelectLocalKeyViewPlanning",
                "binarySceneSnapshotRegistrationV1",
                "cameraAwareSpatialWorkingSetV1",
            ],
            "modelManifests": manifests,
            "capacity": self._capacity(),
            "allowedEditorOrigins": allowed_editor_origins,
        }

    def _renderer_capability(self, release: dict[str, str]) -> dict[str, Any]:
        lock_identity_matches = release["lockDigest"] == EXPECTED_RENDERER_LOCK_DIGEST
        runtime = self.renderer_runtime.status()
        renderer = self.contributor_renderer
        renderer_capability: dict[str, Any]
        if not lock_identity_matches:
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "message": "The installed release does not use the canonical Companion lock for this renderer baseline.",
            }
        elif runtime.status != "ready":
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "message": runtime.message
                or "The gsplat/CUDA runtime is unavailable in this Companion environment.",
            }
            if runtime.cuda_version is not None:
                renderer_capability["cudaVersion"] = runtime.cuda_version
        elif renderer is None:
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "cudaVersion": runtime.cuda_version,
                "message": "The locked gsplat/CUDA runtime is verified, but this Companion release has no production Contributor renderer.",
            }
        else:
            renderer_capability = {
                "id": renderer.renderer_id,
                "status": "ready",
                "cudaVersion": runtime.cuda_version,
                "rgbRendererVersion": AI_SELECT_RGB_RENDERER_VERSION,
            }
        return renderer_capability

    def _require_contributor_renderer(self) -> ContributorRenderer:
        renderer = self.contributor_renderer
        if renderer is None:
            raise MaskSessionError(
                "rendererUnavailable",
                "The gsplat/CUDA Contributor renderer is unavailable for Anchor Evidence.",
            )
        if not getattr(renderer, "requires_locked_runtime", False):
            return renderer
        try:
            release = self.require_release()
        except ValueError as error:
            raise MaskSessionError("rendererUnavailable", str(error)) from error
        capability = self._renderer_capability(release)
        if capability["status"] != "ready":
            raise MaskSessionError(
                "rendererUnavailable",
                str(capability.get("message") or "The locked gsplat/CUDA renderer is unavailable."),
            )
        return renderer

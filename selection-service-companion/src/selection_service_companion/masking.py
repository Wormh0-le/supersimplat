"""Model-independent promptable-mask contracts for the Companion."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import inspect
import json
import math
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, Sequence


# The compiler is a capability-level contract: changing prompt ordering,
# coordinate conversion, or composition changes the advertised capability
# digest so a replay artifact from the old semantics cannot be rebound.
POINT_MASK_PROMPT_COMPILER_POLICY_VERSION = 'point-mask-compiler/v1'
SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION = 'sam3-image-instance-compiler/v1'
SAM3_IMAGE_INSTANCE_ADAPTER_ID = 'sam3-image-instance/v1'


# The SAM 3 Image adapter intentionally pins every material model, processor,
# and result-cardinality option rather than inheriting upstream defaults. The digest is
# the manifest identity for this executable configuration, not an
# operator-chosen label: changing one of these values requires a new adapter
# baseline.
SAM3_IMAGE_RUNTIME_CONFIG: dict[str, Any] = {
    "anchor_prompt_adapter": SAM3_IMAGE_INSTANCE_ADAPTER_ID,
    "anchor_prompt_compiler_policy": SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
    "image_model_builder": "sam3.build_sam3_image_model",
    "enable_inst_interactivity": True,
    "processor_resolution": 1008,
    "confidence_threshold": 0.5,
    "multimask_policy": "single-result/v1",
    "max_multimask_candidates": 1,
    # The pinned upstream returns low-resolution prediction logits at its
    # backbone feature size (288x288), not SAM 2's 256x256; this guard fails
    # closed if a future model build changes that contract.
    "low_res_logits_size": 288,
    "reject_full_frame_masks": True,
    "autocast_dtype": "bfloat16",
    "compile": False,
    "load_from_hf": False,
}
SAM3_IMAGE_RUNTIME_CONFIG_DIGEST = "sha256:" + hashlib.sha256(
    json.dumps(
        SAM3_IMAGE_RUNTIME_CONFIG, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
).hexdigest()


# Reserved legacy identity (non-current): the retired SAM 3.1 visual Prompt
# compiler policy.  It remains only because the pinned legacy runtime
# configuration below binds it; nothing current may compile against it.
SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION = 'sam3.1-visual-prompt-compiler/v1'


# Legacy non-current benchmark fixture: the retired SAM 3.1 Multiplex
# configuration below remains pinned only so the historical object-selection
# PoC flow and its benchmark records stay replayable.  It is not a current
# static instance-segmentation runtime and must not be installed as the Active
# Model Manifest for AI Select mask proposals.
SAM31_RUNTIME_CONFIG: dict[str, Any] = {
    "anchor_prompt_adapter": "sam3.1-interactive-image/v1",
    "anchor_prompt_compiler_policy": SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
    "anchor_box_composition": "independent-box-branches/v1",
    "anchor_mask_input": "disabled-after-brush-only-iou-gate/v1",
    "async_loading_frames": False,
    "compile": False,
    "default_output_prob_thresh": 0.5,
    "max_num_objects": 8,
    "multiplex_count": 16,
    "offload_state_to_cpu": False,
    "offload_video_to_cpu": True,
    "reject_full_frame_masks": True,
    "session_expiration_sec": 1200,
    "use_fa3": False,
    "use_rope_real": True,
    "warm_up": False,
}
SAM31_RUNTIME_CONFIG_DIGEST = "sha256:" + hashlib.sha256(
    json.dumps(SAM31_RUNTIME_CONFIG, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
).hexdigest()


def _prompt_capability_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload, separators=(',', ':'), sort_keys=True, allow_nan=False
    ).encode('utf-8')
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def sam3_image_instance_capabilities() -> dict[str, object]:
    """Return the exact, digest-bound SAM 3 Image instance-prompt contract.

    The current static adapter supports Positive/Negative Points, one Positive
    Instance Box in authoritative pixel XYXY, Companion-local previous-logits
    refinement, with every Prompt pinned to single-result output. Negative Box,
    Prompt Brush, Mask constraints, and Text are not tools in this contract;
    removed families have no placeholder reasons because old artifacts fail
    closed on schema and capability-digest identity instead.
    """

    payload: dict[str, object] = {
        'positivePoints': True,
        'negativePoints': True,
        'positiveInstanceBox': True,
        'previousLogitsRefinement': True,
        'singlePointMultimask': False,
        'negativeBox': False,
        'promptBrush': False,
        'maskConstraints': False,
        'text': False,
        'compilerPolicyVersion': SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
    }
    return {**payload, 'capabilityDigest': _prompt_capability_digest(payload)}


@dataclass(frozen=True)
class CompiledPointPrompt:
    """One exact RGB-pixel point preserved for model input and diagnostics."""

    prompt_id: str
    polarity: str
    x_px: int
    y_px: int


@dataclass(frozen=True)
class CompiledBoxPrompt:
    """One Positive Instance Box in authoritative-image pixel XYXY."""

    prompt_id: str
    x0_px: int
    y0_px: int
    x1_px: int
    y1_px: int


@dataclass(frozen=True)
class CompiledImagePromptProgram:
    """Deterministic, RGB-bound instance constraints for one SAM invocation."""

    compiler_policy_version: str
    rgb_digest: str
    prompt_state_digest: str
    adapter_capability_digest: str
    width: int
    height: int
    points: tuple[CompiledPointPrompt, ...]
    boxes: tuple[CompiledBoxPrompt, ...]
    diagnostics: Mapping[str, object]


def _require_prompt_id(entry: Mapping[str, object], family: str) -> str:
    prompt_id = entry.get('promptId')
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise MaskSessionError(
            'invalidPromptState', f'{family} promptId must be a non-empty string.'
        )
    return prompt_id


def _require_prompt_polarity(entry: Mapping[str, object], family: str) -> str:
    polarity = entry.get('polarity')
    if polarity not in {'include', 'exclude'}:
        raise MaskSessionError(
            'invalidPromptState', f'{family} polarity must be include or exclude.'
        )
    return str(polarity)


def _require_prompt_pixel(
    entry: Mapping[str, object], name: str, *, width: int, height: int
) -> int:
    value = entry.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or (name.startswith('x') and value >= width)
        or (name.startswith('y') and value >= height)
    ):
        raise MaskSessionError(
            'invalidPromptState', f'Prompt {name} must address an in-bounds pixel.'
        )
    return value


def _require_supported_prompt(
    capabilities: Mapping[str, object], field: str, family: str
) -> None:
    if capabilities.get(field) is not True:
        raise MaskSessionError(
            'unsupportedPromptType',
            f'The selected Prompt Adapter does not support {family}.',
        )


def _is_sha256_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == len('sha256:') + 64
        and value.startswith('sha256:')
        and all(character in '0123456789abcdef' for character in value[7:])
    )


def _require_prompt_state_v2(prompt_state: Mapping[str, object]) -> tuple[str, str]:
    """Fail closed on any PromptState shape outside the exact v2 contract."""

    required = {
        'schemaVersion',
        'viewId',
        'rgbDigest',
        'revision',
        'points',
        'boxes',
        'digest',
    }
    if set(prompt_state) != required:
        raise MaskSessionError(
            'invalidPromptState',
            'PromptState must contain exactly the schema v2 fields.',
        )
    if prompt_state.get('schemaVersion') != 2:
        raise MaskSessionError(
            'invalidPromptState', 'PromptState schemaVersion must be 2.'
        )
    revision = prompt_state.get('revision')
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise MaskSessionError(
            'invalidPromptState',
            'PromptState revision must be a non-negative integer.',
        )
    rgb_digest = prompt_state.get('rgbDigest')
    prompt_state_digest = prompt_state.get('digest')
    if not _is_sha256_digest(rgb_digest) or not _is_sha256_digest(prompt_state_digest):
        raise MaskSessionError(
            'invalidPromptState',
            'PromptState requires exact sha256 RGB and PromptState digests.',
        )
    payload = {key: item for key, item in prompt_state.items() if key != 'digest'}
    try:
        encoded = json.dumps(
            payload, separators=(',', ':'), sort_keys=True, allow_nan=False
        ).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise MaskSessionError(
            'invalidPromptState', 'PromptState payload must be JSON-compatible.'
        ) from error
    if f'sha256:{hashlib.sha256(encoded).hexdigest()}' != prompt_state_digest:
        raise MaskSessionError(
            'invalidPromptState',
            'PromptState digest does not match its exact payload.',
        )
    return str(rgb_digest), str(prompt_state_digest)


def _compile_point_entries(
    entries: object,
    *,
    width: int,
    height: int,
    capabilities: Mapping[str, object],
    positive_field: str,
    negative_field: str,
    prompt_ids: set[str],
) -> list[CompiledPointPrompt]:
    if not isinstance(entries, list):
        raise MaskSessionError(
            'invalidPromptState', 'PromptState points must be an array.'
        )
    points: list[CompiledPointPrompt] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise MaskSessionError('invalidPromptState', 'Point prompts must be objects.')
        prompt_id = _require_prompt_id(entry, 'Point')
        polarity = _require_prompt_polarity(entry, 'Point')
        _require_supported_prompt(
            capabilities,
            negative_field if polarity == 'exclude' else positive_field,
            'negative Point prompts' if polarity == 'exclude' else 'Point prompts',
        )
        if prompt_id in prompt_ids:
            raise MaskSessionError('invalidPromptState', 'Prompt IDs must be unique.')
        prompt_ids.add(prompt_id)
        points.append(
            CompiledPointPrompt(
                prompt_id=prompt_id,
                polarity=polarity,
                x_px=_require_prompt_pixel(entry, 'xPx', width=width, height=height),
                y_px=_require_prompt_pixel(entry, 'yPx', width=width, height=height),
            )
        )
    points.sort(key=lambda point: point.prompt_id)
    return points


def _require_box_pixel(value: object, name: str, *, limit: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > limit
    ):
        raise MaskSessionError(
            'invalidPromptState', f'Box {name} must address an in-bounds pixel.'
        )
    return value


def _compile_instance_box(
    entries: object,
    *,
    width: int,
    height: int,
    capabilities: Mapping[str, object],
    prompt_ids: set[str],
) -> tuple[CompiledBoxPrompt, ...]:
    if not isinstance(entries, list):
        raise MaskSessionError(
            'invalidPromptState', 'PromptState boxes must be an array.'
        )
    if not entries:
        return ()
    _require_supported_prompt(
        capabilities, 'positiveInstanceBox', 'Instance Box prompts'
    )
    if len(entries) > 1:
        raise MaskSessionError(
            'invalidPromptState',
            'PromptState supports at most one positive Instance Box.',
        )
    entry = entries[0]
    if not isinstance(entry, Mapping):
        raise MaskSessionError('invalidPromptState', 'Box prompts must be objects.')
    prompt_id = _require_prompt_id(entry, 'Box')
    if entry.get('polarity') != 'include':
        raise MaskSessionError(
            'unsupportedPromptType',
            'The SAM 3 Image adapter supports a positive Instance Box only.',
        )
    if prompt_id in prompt_ids:
        raise MaskSessionError('invalidPromptState', 'Prompt IDs must be unique.')
    prompt_ids.add(prompt_id)
    x0_px = _require_box_pixel(entry.get('x0Px'), 'x0Px', limit=width)
    y0_px = _require_box_pixel(entry.get('y0Px'), 'y0Px', limit=height)
    x1_px = _require_box_pixel(entry.get('x1Px'), 'x1Px', limit=width)
    y1_px = _require_box_pixel(entry.get('y1Px'), 'y1Px', limit=height)
    if x0_px >= x1_px or y0_px >= y1_px:
        raise MaskSessionError(
            'invalidPromptState', 'Box prompts must have a non-empty pixel area.'
        )
    return (
        CompiledBoxPrompt(
            prompt_id=prompt_id,
            x0_px=x0_px,
            y0_px=y0_px,
            x1_px=x1_px,
            y1_px=y1_px,
        ),
    )


def compile_sam3_image_prompt_program(
    prompt_state: Mapping[str, object],
    *,
    width: int,
    height: int,
    capabilities: Mapping[str, object],
) -> CompiledImagePromptProgram:
    """Compile exact PromptState v2 constraints without ranking any candidates.

    The declared order is family then lexicographic Prompt ID. The Instance Box
    uses authoritative-image pixel XYXY only; there is no normalized XYWH form.
    Removed v1 families (Mask constraints, Text, negative Box polarity) fail
    closed on exact-key, schema-version, and capability identity rather than
    being converted into Points.
    """

    if width <= 0 or height <= 0:
        raise MaskSessionError(
            'invalidPromptState', 'Prompt compilation requires positive RGB dimensions.'
        )
    expected_capabilities = sam3_image_instance_capabilities()
    capability_digest = expected_capabilities['capabilityDigest']
    if (
        capabilities.get('compilerPolicyVersion')
        != SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION
        or capabilities.get('capabilityDigest') != capability_digest
    ):
        raise MaskSessionError(
            'capabilityMismatch',
            'The SAM 3 Image Prompt compiler policy is incompatible.',
        )
    rgb_digest, prompt_state_digest = _require_prompt_state_v2(prompt_state)
    prompt_ids: set[str] = set()
    points = _compile_point_entries(
        prompt_state.get('points'),
        width=width,
        height=height,
        capabilities=capabilities,
        positive_field='positivePoints',
        negative_field='negativePoints',
        prompt_ids=prompt_ids,
    )
    boxes = _compile_instance_box(
        prompt_state.get('boxes'),
        width=width,
        height=height,
        capabilities=capabilities,
        prompt_ids=prompt_ids,
    )
    compiled_prompt_ids = [
        *(point.prompt_id for point in points),
        *(box.prompt_id for box in boxes),
    ]
    return CompiledImagePromptProgram(
        compiler_policy_version=SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
        rgb_digest=rgb_digest,
        prompt_state_digest=prompt_state_digest,
        adapter_capability_digest=str(capability_digest),
        width=width,
        height=height,
        points=tuple(points),
        boxes=boxes,
        diagnostics=MappingProxyType({
            'compilerPolicyVersion': SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
            'promptOrder': 'family-then-prompt-id-lexicographic/v1',
            'boxCoordinateConvention': 'authoritative-pixel-xyxy/v1',
            'rgbDigest': rgb_digest,
            'promptStateDigest': prompt_state_digest,
            'adapterCapabilityDigest': capability_digest,
            'rgbDimensions': [width, height],
            'compiledPromptIds': compiled_prompt_ids,
        }),
    )


def compile_point_mask_prompt_program(
    prompt_state: Mapping[str, object],
    *,
    width: int,
    height: int,
    capabilities: Mapping[str, object],
) -> CompiledImagePromptProgram:
    """Validate the deterministic reference point-only program on v2 shape.

    This compiler belongs to the ``point-mask-v1`` protocol reference adapter.
    It shares the exact v2 PromptState envelope but supports Points only and
    never adopts SAM model identity.
    """

    if width <= 0 or height <= 0:
        raise MaskSessionError(
            'invalidPromptState', 'Prompt compilation requires positive RGB dimensions.'
        )
    if (
        capabilities.get('compilerPolicyVersion')
        != POINT_MASK_PROMPT_COMPILER_POLICY_VERSION
    ):
        raise MaskSessionError(
            'capabilityMismatch',
            'The Point Mask Prompt compiler policy is incompatible.',
        )
    capability_digest = capabilities.get('capabilityDigest')
    if not _is_sha256_digest(capability_digest):
        raise MaskSessionError(
            'invalidPromptState',
            'Prompt compilation requires an exact adapter capability digest.',
        )
    rgb_digest, prompt_state_digest = _require_prompt_state_v2(prompt_state)
    if prompt_state.get('boxes'):
        _require_supported_prompt(capabilities, 'boxes', 'Box prompts')
    prompt_ids: set[str] = set()
    points = _compile_point_entries(
        prompt_state.get('points'),
        width=width,
        height=height,
        capabilities=capabilities,
        positive_field='points',
        negative_field='negativePoints',
        prompt_ids=prompt_ids,
    )
    return CompiledImagePromptProgram(
        compiler_policy_version=POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
        rgb_digest=rgb_digest,
        prompt_state_digest=prompt_state_digest,
        adapter_capability_digest=str(capability_digest),
        width=width,
        height=height,
        points=tuple(points),
        boxes=(),
        diagnostics=MappingProxyType({
            'compilerPolicyVersion': POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
            'promptOrder': 'family-then-prompt-id-lexicographic/v1',
            'rgbDigest': rgb_digest,
            'promptStateDigest': prompt_state_digest,
            'adapterCapabilityDigest': capability_digest,
            'rgbDimensions': [width, height],
            'compiledPromptIds': [point.prompt_id for point in points],
        }),
    )


def resolve_multimask_output(
    program: CompiledImagePromptProgram, has_refinement: bool
) -> bool:
    """Keep every interactive Prompt on the single-result inference path."""

    del program, has_refinement
    return False


class MaskSessionError(ValueError):
    """An actionable failure that must not publish a partial Mask Set."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RegisteredFrame:
    """Immutable metadata for one model-visible frame."""

    view_id: str
    frame_digest: str
    width: int
    height: int
    image_png: bytes | None = None
    # The Anchor is editor-owned RGB; Generated Views are Companion-rendered.
    # Camera values are opaque to mask adapters and are interpreted only by a
    # service-owned Generated View renderer.
    source: str = "anchor"
    camera: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RegisteredFrameSet:
    """An immutable, ordered Frame Set keyed by its editor-owned version."""

    canonical: str
    frame_set_id: str
    frame_set_version: str
    ordered_views: tuple[RegisteredFrame, ...]

    def view(self, view_id: str) -> RegisteredFrame | None:
        return next(
            (view for view in self.ordered_views if view.view_id == view_id), None
        )


@dataclass(frozen=True)
class MaskProduction:
    """Complete tracks, a bound mask threshold, and optional diagnostics."""

    tracks: list[dict[str, Any]]
    threshold: float
    diagnostics: dict[str, Any] | None = None


@dataclass(frozen=True)
class Sam3ImageRefinementInput:
    """Resolved Companion-local refinement state; it never crosses the wire."""

    inference_state: Any
    mask_input: Any


@dataclass(frozen=True)
class Sam3ImageCandidate:
    """One validated, unranked instance candidate for the proposal seam.

    ``low_res_logits`` is the raw model-side refinement tensor. It is
    Companion-local disposable state and must never be serialized into a
    response; only opaque digest-bound references may cross the boundary.
    """

    source_index: int
    mask_bits: bytes
    model_score: float | None
    prompt_consistency: Mapping[str, bool]
    prompt_diagnostics: tuple[Mapping[str, object], ...]
    low_res_logits: Any


@dataclass(frozen=True)
class Sam3ImageProposalBatch:
    """Retained candidates plus the opaque image state used to mint refs."""

    candidates: tuple[Sam3ImageCandidate, ...]
    inference_state: Any


class PromptableMaskAdapter(Protocol):
    """A replaceable model adapter that exposes only generic Mask Set values."""

    def produce_tracks(
        self,
        *,
        model: Mapping[str, Any],
        frame_set: RegisteredFrameSet,
        prompt_log: Sequence[dict[str, Any]],
        cancelled: Callable[[], bool],
    ) -> MaskProduction:
        """Return complete tracks or raise without publishing a partial result.

        ``MaskProduction`` binds the threshold and any adapter-local audit
        diagnostics into the immutable completed Mask Set.
        """


def register_frame_set(payload: dict[str, Any]) -> RegisteredFrameSet:
    """Validate one Frame Set before it enters the immutable service cache."""

    frame_set_id = _require_string(payload, "frameSetId", "Frame Set")
    frame_set_version = _require_string(payload, "frameSetVersion", "Frame Set")
    ordered_views = payload.get("orderedViews")
    if not isinstance(ordered_views, list) or not ordered_views:
        raise MaskSessionError(
            "invalidFrameSet",
            "Frame Set orderedViews must contain the Anchor View.",
        )

    views: list[RegisteredFrame] = []
    known_view_ids: set[str] = set()
    for value in ordered_views:
        if not isinstance(value, dict):
            raise MaskSessionError(
                "invalidFrameSet", "Frame Set views must be objects."
            )
        view_id = _require_string(value, "viewId", "Frame Set view")
        if view_id in known_view_ids:
            raise MaskSessionError(
                "invalidFrameSet", "Frame Set view IDs must be unique."
            )
        known_view_ids.add(view_id)
        frame_digest = _require_string(value, "frameDigest", "Frame Set view")
        width = _require_dimension(value, "width")
        height = _require_dimension(value, "height")
        image_png = _optional_png(value)
        source = value.get("source", "anchor")
        if source not in {"anchor", "generated"}:
            raise MaskSessionError(
                "invalidFrameSet",
                "Frame Set view source must be anchor or generated.",
            )
        camera = value.get("camera")
        if camera is not None:
            if not isinstance(camera, dict):
                raise MaskSessionError(
                    "invalidFrameSet", "Frame Set view camera must be an object."
                )
            try:
                # Reject non-JSON camera metadata before it becomes part of an
                # immutable cache key. Detailed camera semantics remain owned
                # by the Generated View renderer.
                camera = json.loads(
                    json.dumps(
                        camera,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    )
                )
            except (TypeError, ValueError) as error:
                raise MaskSessionError(
                    "invalidFrameSet", "Frame Set view camera must be JSON-compatible."
                ) from error
        if image_png is not None:
            expected_digest = f"sha256:{hashlib.sha256(image_png).hexdigest()}"
            if frame_digest != expected_digest:
                raise MaskSessionError(
                    "invalidFrameSet",
                    "Frame Set imagePngBase64 does not match its Frame Set digest.",
                )
        views.append(
            RegisteredFrame(
                view_id,
                frame_digest,
                width,
                height,
                image_png,
                source,
                camera,
            )
        )

    return RegisteredFrameSet(
        canonical=json.dumps(
            payload, separators=(",", ":"), sort_keys=True, allow_nan=False
        ),
        frame_set_id=frame_set_id,
        frame_set_version=frame_set_version,
        ordered_views=tuple(views),
    )


class PointMaskAdapter:
    """A deterministic protocol reference adapter for point-mask contracts.

    It is intentionally limited to contract tests and local transport smoke
    checks.  It never claims to be image/model inference; the
    ``Sam3ImageInstanceAdapter`` below is the isolated model-backed Anchor View
    implementation.
    """

    def produce_tracks(
        self,
        *,
        model: Mapping[str, Any],
        frame_set: RegisteredFrameSet,
        prompt_log: Sequence[dict[str, Any]],
        cancelled: Callable[[], bool],
    ) -> MaskProduction:
        if model.get("adapterId") != "point-mask-v1":
            raise MaskSessionError(
                "incompatibleManifest",
                "The selected Model Manifest is incompatible with the Point Mask adapter.",
            )
        if cancelled():
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )
        if not prompt_log:
            raise MaskSessionError(
                "invalidPromptLog", "A New Mask Set requires one point prompt."
            )

        points_by_view: dict[str, list[tuple[int, int, str]]] = {
            view.view_id: [] for view in frame_set.ordered_views
        }
        anchor_view_id: str | None = None
        for entry in prompt_log:
            if cancelled():
                raise MaskSessionError(
                    "cancelled", "The promptable-mask update was cancelled."
                )
            if not isinstance(entry, dict) or entry.get("operation") != "New":
                raise MaskSessionError(
                    "unsupportedOperation",
                    "This first promptable-mask slice accepts a New point Prompt Log only.",
                )
            prompt = entry.get("prompt")
            if not isinstance(prompt, dict):
                raise MaskSessionError(
                    "invalidPromptLog", "Prompt Log entries must contain point prompts."
                )
            view = self._validate_point_prompt(prompt, frame_set)
            if anchor_view_id is None:
                anchor_view_id = view.view_id
            points_by_view[view.view_id].append(
                (prompt["xPx"], prompt["yPx"], prompt["polarity"])
            )

        if anchor_view_id is None:
            raise MaskSessionError(
                "invalidPromptLog", "A New Mask Set requires an Anchor View prompt."
            )

        tracks = [{
            "trackId": "primary",
            "role": "include",
            "frames": [
                self._frame_outcome(view, points_by_view[view.view_id])
                for view in frame_set.ordered_views
            ],
        }]
        anchor_outcome = next(
            frame
            for frame in tracks[0]["frames"]
            if frame["viewId"] == anchor_view_id
        )
        if anchor_outcome["status"] != "accepted":
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View did not produce an accepted promptable mask; adjust the point prompts and retry.",
            )
        # The reference adapter uses exact pixel membership rather than a
        # model probability. Its zero threshold is still explicit so every
        # complete Mask Set has the same versioned shape as SAM output.
        return MaskProduction(tracks=tracks, threshold=0.0)

    @staticmethod
    def _validate_point_prompt(
        prompt: dict[str, Any], frame_set: RegisteredFrameSet
    ) -> RegisteredFrame:
        if "imagePngBase64" in prompt:
            raise MaskSessionError(
                "invalidPromptLog",
                "Point Prompt Logs must reference Frame Set views without embedding frame image bytes.",
            )
        _require_string(prompt, "promptId", "Point prompt")
        view_id = _require_string(prompt, "viewId", "Point prompt")
        view = frame_set.view(view_id)
        if view is None:
            raise MaskSessionError(
                "unknownView", "The point prompt references a view outside the registered Frame Set."
            )
        if prompt.get("frameDigest") != view.frame_digest:
            raise MaskSessionError(
                "staleFrame", "The point prompt Frame Set digest is stale."
            )
        if prompt.get("frameWidth") != view.width or prompt.get("frameHeight") != view.height:
            raise MaskSessionError(
                "staleFrame", "The point prompt dimensions do not match the registered Frame Set."
            )
        x_px = prompt.get("xPx")
        y_px = prompt.get("yPx")
        if (
            isinstance(x_px, bool)
            or isinstance(y_px, bool)
            or not isinstance(x_px, int)
            or not isinstance(y_px, int)
            or x_px < 0
            or y_px < 0
            or x_px >= view.width
            or y_px >= view.height
        ):
            raise MaskSessionError(
                "invalidPoint",
                "Point prompts must address an in-bounds pixel center in the registered Frame Set.",
            )
        if prompt.get("polarity") not in {"include", "exclude"}:
            raise MaskSessionError(
                "invalidPoint", "Point prompt polarity must be include or exclude."
            )
        return view

    @staticmethod
    def _frame_outcome(
        view: RegisteredFrame, points: Sequence[tuple[int, int, str]]
    ) -> dict[str, Any]:
        include_points = {
            (x_px, y_px)
            for x_px, y_px, polarity in points
            if polarity == "include"
        }
        excluded_points = {
            (x_px, y_px)
            for x_px, y_px, polarity in points
            if polarity == "exclude"
        }
        foreground_pixels = sorted(
            include_points - excluded_points,
            key=lambda point: (point[1], point[0]),
        )
        if not foreground_pixels:
            return {
                "viewId": view.view_id,
                "status": "not_found",
                "rejectionReason": "No included point remained for this view.",
            }
        return {
            "viewId": view.view_id,
            "status": "accepted",
            "binaryMask": {
                "encoding": "sparse-points-v1",
                "width": view.width,
                "height": view.height,
                "foregroundPixels": [list(point) for point in foreground_pixels],
            },
        }


class Sam3PointMaskAdapter:
    """Legacy non-current SAM 3.1 Multiplex point tracker (benchmark fixture).

    This adapter remains only for the historical object-selection PoC flow and
    its frozen benchmark fixtures. It is not a current static
    instance-segmentation provider: a ``sam3.1`` Model Manifest fails closed on
    the AI Select mask-proposals route, and the retired private-tracker static
    path (``produce_ai_select_visual_proposals``) has been removed. The current
    static path is ``Sam3ImageInstanceAdapter`` below.
    """

    def __init__(
        self,
        *,
        build_predictor: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._build_predictor = build_predictor or _build_sam3_predictor

    def produce_tracks(
        self,
        *,
        model: Mapping[str, Any],
        frame_set: RegisteredFrameSet,
        prompt_log: Sequence[dict[str, Any]],
        cancelled: Callable[[], bool],
    ) -> MaskProduction:
        if model.get("adapterId") != "sam3.1":
            raise MaskSessionError(
                "incompatibleManifest",
                "The selected Model Manifest is incompatible with the SAM 3.1 Point Mask adapter.",
            )
        if model.get("runtimeConfigDigest") != SAM31_RUNTIME_CONFIG_DIGEST:
            raise MaskSessionError(
                "incompatibleManifest",
                "The selected SAM 3.1 Model Manifest does not bind the pinned runtime configuration.",
            )
        if cancelled():
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )
        if not prompt_log:
            raise MaskSessionError(
                "invalidPromptLog", "A New Mask Set requires one point prompt."
            )

        anchor_view: RegisteredFrame | None = None
        points: list[list[int]] = []
        point_labels: list[int] = []
        for entry in prompt_log:
            if cancelled():
                raise MaskSessionError(
                    "cancelled", "The promptable-mask update was cancelled."
                )
            if not isinstance(entry, dict) or entry.get("operation") != "New":
                raise MaskSessionError(
                    "unsupportedOperation",
                    "This first SAM 3.1 slice accepts a New point Prompt Log only.",
                )
            prompt = entry.get("prompt")
            if not isinstance(prompt, dict):
                raise MaskSessionError(
                    "invalidPromptLog", "Prompt Log entries must contain point prompts."
                )
            view = PointMaskAdapter._validate_point_prompt(prompt, frame_set)
            if anchor_view is None:
                anchor_view = view
            elif view.view_id != anchor_view.view_id:
                raise MaskSessionError(
                    "unsupportedView",
                    "This first SAM 3.1 slice accepts point prompts on the Anchor View only.",
                )
            points.append([prompt["xPx"], prompt["yPx"]])
            point_labels.append(1 if prompt["polarity"] == "include" else 0)

        if anchor_view is None:
            raise MaskSessionError(
                "invalidPromptLog", "A New Mask Set requires an Anchor View prompt."
            )
        if any(view.image_png is None for view in frame_set.ordered_views):
            raise MaskSessionError(
                "frameDataUnavailable",
                "The SAM 3.1 adapter requires PNG bytes for every Frame Set view.",
            )

        outcomes, candidate_diagnostics_by_view = self._infer_frame_set(
            model=model,
            frame_set=frame_set,
            anchor_view=anchor_view,
            points=points,
            point_labels=point_labels,
            cancelled=cancelled,
        )
        anchor_outcome = outcomes[anchor_view.view_id]
        if anchor_outcome["status"] != "accepted":
            reason = anchor_outcome.get("rejectionReason")
            detail = (
                reason
                if isinstance(reason, str) and reason.strip()
                else "The prompted view did not produce an accepted SAM 3.1 mask."
            )
            raise MaskSessionError(
                "anchorMaskUnavailable",
                f"{detail} Adjust the point prompts and retry.",
            )
        tracking_confidence_by_view = {
            view.view_id: self._tracking_confidence_from_candidate_diagnostics(
                candidate_diagnostics_by_view.get(view.view_id)
            )
            for view in frame_set.ordered_views
        }
        return MaskProduction(
            tracks=[{
                "trackId": "primary",
                "role": "include",
                "frames": [outcomes[view.view_id] for view in frame_set.ordered_views],
            }],
            threshold=float(SAM31_RUNTIME_CONFIG["default_output_prob_thresh"]),
            diagnostics={
                "adapterId": "sam3.1",
                "candidateSelection": candidate_diagnostics_by_view[anchor_view.view_id],
                "trackingConfidenceSemantics": (
                    "sigmoid-normalized selected sam3.1.out_probs candidate quality "
                    "score; unavailable when no candidate is selected."
                ),
                "trackingConfidenceByView": tracking_confidence_by_view,
            },
        )

    def discard_attempt(self) -> None:
        """Release cached CUDA allocations after the active SAM session closes."""

        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _infer_frame_set(
        self,
        *,
        model: Mapping[str, Any],
        frame_set: RegisteredFrameSet,
        anchor_view: RegisteredFrame,
        points: list[list[int]],
        point_labels: list[int],
        cancelled: Callable[[], bool],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        predictor = self._build_predictor(model)
        with tempfile.TemporaryDirectory(prefix="supersplat-sam3-") as directory:
            frame_directory = Path(directory)
            for index, view in enumerate(frame_set.ordered_views):
                (frame_directory / f"{index:06d}.png").write_bytes(
                    view.image_png or b""
                )
            # The pinned multiplex model does not accept offload_state_to_cpu;
            # the builder compatibility shim removes its false upstream default.
            started = predictor.handle_request({
                "type": "start_session",
                "resource_path": str(frame_directory),
                "offload_video_to_cpu": SAM31_RUNTIME_CONFIG["offload_video_to_cpu"],
            })
            if not isinstance(started, Mapping) or not isinstance(started.get("session_id"), str):
                raise MaskSessionError(
                    "modelFailure", "SAM 3.1 did not return an inference session ID."
                )
            session_id = started["session_id"]
            try:
                if cancelled():
                    raise MaskSessionError(
                        "cancelled", "The promptable-mask update was cancelled."
                    )
                anchor_index = frame_set.ordered_views.index(anchor_view)
                response = predictor.handle_request({
                    "type": "add_prompt",
                    "session_id": session_id,
                    "frame_index": anchor_index,
                    "points": points,
                    "point_labels": point_labels,
                    "clear_old_points": True,
                    "rel_coordinates": False,
                    "obj_id": 1,
                    "output_prob_thresh": SAM31_RUNTIME_CONFIG[
                        "default_output_prob_thresh"
                    ],
                })
                if cancelled():
                    raise MaskSessionError(
                        "cancelled", "The promptable-mask update was cancelled."
                    )
                anchor_outcome, anchor_diagnostics = (
                    self._mask_outcome_and_diagnostics_from_response(
                        response,
                        anchor_view,
                        points=points,
                        point_labels=point_labels,
                    )
                )
                outcomes = {anchor_view.view_id: anchor_outcome}
                candidate_diagnostics_by_view = {
                    anchor_view.view_id: anchor_diagnostics,
                }
                self._collect_propagated_outcomes(
                    predictor=predictor,
                    session_id=session_id,
                    frame_set=frame_set,
                    anchor_index=anchor_index,
                    outcomes=outcomes,
                    candidate_diagnostics_by_view=candidate_diagnostics_by_view,
                    cancelled=cancelled,
                )
                return outcomes, candidate_diagnostics_by_view
            finally:
                try:
                    predictor.handle_request({
                        "type": "close_session",
                        "session_id": session_id,
                        "run_gc_collect": False,
                    })
                except Exception:
                    # The completed output remains immutable; an optional runtime
                    # cleanup failure must not publish a different partial result.
                    pass

    def _collect_propagated_outcomes(
        self,
        *,
        predictor: Any,
        session_id: str,
        frame_set: RegisteredFrameSet,
        anchor_index: int,
        outcomes: dict[str, dict[str, Any]],
        candidate_diagnostics_by_view: dict[str, dict[str, Any]],
        cancelled: Callable[[], bool],
    ) -> None:
        propagation_failure = "missing frame result"
        if len(frame_set.ordered_views) > 1:
            try:
                responses = predictor.handle_stream_request({
                    "type": "propagate_in_video",
                    "session_id": session_id,
                    "propagation_direction": "both",
                    "start_frame_index": anchor_index,
                    "max_frame_num_to_track": len(frame_set.ordered_views),
                    "output_prob_thresh": SAM31_RUNTIME_CONFIG[
                        "default_output_prob_thresh"
                    ],
                })
                for tracked in responses:
                    self._cancel_propagation_if_requested(
                        predictor, session_id, cancelled
                    )
                    if not isinstance(tracked, Mapping):
                        continue
                    frame_index = tracked.get("frame_index")
                    if (
                        isinstance(frame_index, bool)
                        or not isinstance(frame_index, int)
                        or not 0 <= frame_index < len(frame_set.ordered_views)
                        or frame_index == anchor_index
                    ):
                        continue
                    view = frame_set.ordered_views[frame_index]
                    if view.view_id in outcomes:
                        continue
                    candidate_diagnostics: dict[str, Any] | None = None
                    try:
                        outcome, candidate_diagnostics = (
                            self._mask_outcome_and_diagnostics_from_response(
                                tracked,
                                view,
                                points=(),
                                point_labels=(),
                            )
                        )
                    except MaskSessionError as error:
                        outcome = {
                            "viewId": view.view_id,
                            "status": "error",
                            "rejectionReason": str(error),
                        }
                    outcomes[view.view_id] = outcome
                    if candidate_diagnostics is not None:
                        candidate_diagnostics_by_view[view.view_id] = (
                            candidate_diagnostics
                        )
                self._cancel_propagation_if_requested(
                    predictor, session_id, cancelled
                )
            except MaskSessionError:
                raise
            except Exception as error:
                propagation_failure = type(error).__name__
        for view in frame_set.ordered_views:
            outcomes.setdefault(
                view.view_id,
                {
                    "viewId": view.view_id,
                    "status": "error",
                    "rejectionReason": f"SAM 3.1 tracking did not produce this frame ({propagation_failure}).",
                },
            )

    @staticmethod
    def _cancel_propagation_if_requested(
        predictor: Any,
        session_id: str,
        cancelled: Callable[[], bool],
    ) -> None:
        if not cancelled():
            return
        try:
            predictor.handle_request({
                "type": "cancel_propagation",
                "session_id": session_id,
            })
        finally:
            raise MaskSessionError(
                "cancelled",
                "The promptable-mask update was cancelled.",
            )

    @staticmethod
    def _mask_outcome_from_response(
        response: Any,
        view: RegisteredFrame,
        *,
        points: Sequence[Sequence[int]],
        point_labels: Sequence[int],
    ) -> dict[str, Any]:
        outcome, _diagnostics = (
            Sam3PointMaskAdapter._mask_outcome_and_diagnostics_from_response(
                response,
                view,
                points=points,
                point_labels=point_labels,
            )
        )
        return outcome

    @staticmethod
    def _mask_outcome_and_diagnostics_from_response(
        response: Any,
        view: RegisteredFrame,
        *,
        points: Sequence[Sequence[int]],
        point_labels: Sequence[int],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(response, Mapping):
            raise MaskSessionError(
                "modelFailure", "SAM 3.1 returned an invalid point-inference response."
            )
        outputs = response.get("outputs")
        if not isinstance(outputs, Mapping) or "out_binary_masks" not in outputs:
            raise MaskSessionError(
                "modelFailure", "SAM 3.1 returned no binary Anchor View mask."
            )
        masks = Sam3PointMaskAdapter._mask_candidates(outputs["out_binary_masks"])
        if not masks:
            return (
                {
                    "viewId": view.view_id,
                    "status": "not_found",
                    "rejectionReason": "SAM 3.1 found no foreground mask for the Anchor View points.",
                },
                Sam3PointMaskAdapter._candidate_diagnostics([], None),
            )
        scores = Sam3PointMaskAdapter._candidate_scores(
            outputs.get("out_probs"), len(masks)
        )
        candidates: list[tuple[bytearray, bool, bool, bool]] = []
        diagnostics: list[dict[str, Any]] = []
        for index, mask in enumerate(masks):
            bits, foreground = Sam3PointMaskAdapter._encode_binary_mask(mask, view)
            foreground_pixel_count = sum(byte.bit_count() for byte in bits)
            area_valid = foreground and (
                not SAM31_RUNTIME_CONFIG["reject_full_frame_masks"]
                or foreground_pixel_count < view.width * view.height
            )
            point_consistent = foreground and Sam3PointMaskAdapter._satisfies_anchor_points(
                bits, view, points, point_labels
            )
            diagnostic: dict[str, Any] = {
                "candidateIndex": index,
                "foregroundPixelCount": foreground_pixel_count,
                "areaValid": area_valid,
                "pointConsistent": point_consistent,
                "selected": False,
                "binaryMask": {
                    "encoding": "bitset-lsb-v1",
                    "width": view.width,
                    "height": view.height,
                    "data": base64.b64encode(bits).decode("ascii"),
                },
            }
            if scores[index] is not None:
                diagnostic["qualityScore"] = scores[index]
            diagnostics.append(diagnostic)
            candidates.append((bits, foreground, area_valid, point_consistent))
        candidate_indexes = sorted(
            range(len(masks)),
            key=lambda index: (
                scores[index] if scores[index] is not None else float("-inf")
            ),
            reverse=True,
        )
        has_foreground = False
        for index in candidate_indexes:
            bits, foreground, area_valid, point_consistent = candidates[index]
            if not foreground:
                continue
            has_foreground = True
            if not area_valid or not point_consistent:
                continue
            diagnostics[index]["selected"] = True
            return (
                {
                    "viewId": view.view_id,
                    "status": "accepted",
                    "binaryMask": {
                        "encoding": "bitset-lsb-v1",
                        "width": view.width,
                        "height": view.height,
                        "data": base64.b64encode(bits).decode("ascii"),
                    },
                },
                Sam3PointMaskAdapter._candidate_diagnostics(diagnostics, index),
            )
        if not has_foreground:
            return (
                {
                    "viewId": view.view_id,
                    "status": "not_found",
                    "rejectionReason": "SAM 3.1 found no foreground mask for the Anchor View points.",
                },
                Sam3PointMaskAdapter._candidate_diagnostics(diagnostics, None),
            )
        return (
                {
                    "viewId": view.view_id,
                    "status": "rejected",
                    "rejectionReason": "SAM 3.1 did not return an Anchor View mask that satisfied the supplied point prompts and basic area validation.",
            },
            Sam3PointMaskAdapter._candidate_diagnostics(diagnostics, None),
        )

    @staticmethod
    def _candidate_diagnostics(
        alternatives: list[dict[str, Any]], selected_candidate_index: int | None
    ) -> dict[str, Any]:
        return {
            "scoreSemantics": (
                "sam3.1.out_probs is an adapter-local candidate quality score "
                "used only to order candidates that satisfy point and area validation."
            ),
            "selectedCandidateIndex": selected_candidate_index,
            "alternatives": alternatives,
        }

    @staticmethod
    def _tracking_confidence_from_candidate_diagnostics(
        diagnostics: Mapping[str, Any] | None,
    ) -> float | None:
        """Return a bounded, adapter-declared confidence for one selected mask."""

        if not isinstance(diagnostics, Mapping):
            return None
        selected_index = diagnostics.get("selectedCandidateIndex")
        alternatives = diagnostics.get("alternatives")
        if (
            isinstance(selected_index, bool)
            or not isinstance(selected_index, int)
            or not isinstance(alternatives, Sequence)
        ):
            return None
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                continue
            if alternative.get("candidateIndex") != selected_index:
                continue
            score = alternative.get("qualityScore")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                return None
            if score >= 0:
                return 1.0 / (1.0 + math.exp(-score))
            exponent = math.exp(score)
            return exponent / (1.0 + exponent)
        return None

    @staticmethod
    def _mask_candidates(value: Any) -> list[list[list[Any]]]:
        value = Sam3PointMaskAdapter._python_value(value)
        if value == []:
            return []

        def is_matrix(candidate: Any) -> bool:
            return (
                isinstance(candidate, list)
                and bool(candidate)
                and all(isinstance(row, list) and row for row in candidate)
                and all(
                    not isinstance(pixel, (list, tuple, dict))
                    for row in candidate
                    for pixel in row
                )
            )

        def collect(candidate: Any) -> list[list[list[Any]]]:
            if candidate == []:
                return []
            if is_matrix(candidate):
                return [candidate]
            if not isinstance(candidate, list):
                raise MaskSessionError(
                    "modelFailure", "SAM 3.1 returned no usable binary Anchor View mask."
                )
            masks: list[list[list[Any]]] = []
            for nested in candidate:
                masks.extend(collect(nested))
            return masks

        return collect(value)

    @staticmethod
    def _python_value(value: Any) -> Any:
        for method in ("detach", "cpu"):
            if hasattr(value, method):
                value = getattr(value, method)()
        if hasattr(value, "tolist"):
            value = value.tolist()
        return value

    @staticmethod
    def _candidate_scores(value: Any, candidate_count: int) -> list[float | None]:
        if value is None:
            return [None] * candidate_count
        values: list[Any] = []

        def flatten(item: Any) -> None:
            if isinstance(item, list):
                for nested in item:
                    flatten(nested)
                return
            values.append(item)

        flatten(Sam3PointMaskAdapter._python_value(value))
        if len(values) != candidate_count:
            raise MaskSessionError(
                "modelFailure", "SAM 3.1 returned candidate scores that do not match its masks."
            )
        scores: list[float | None] = []
        for score in values:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise MaskSessionError(
                    "modelFailure", "SAM 3.1 returned a non-numeric candidate quality score."
                )
            if not math.isfinite(score):
                raise MaskSessionError(
                    "modelFailure", "SAM 3.1 returned a non-finite candidate quality score."
                )
            scores.append(float(score))
        return scores

    @staticmethod
    def _encode_binary_mask(
        mask: list[list[Any]], view: RegisteredFrame
    ) -> tuple[bytearray, bool]:
        if len(mask) != view.height or any(len(row) != view.width for row in mask):
            raise MaskSessionError(
                "modelFailure", "SAM 3.1 returned a mask with stale Anchor View dimensions."
            )
        bits = bytearray((view.width * view.height + 7) // 8)
        foreground = False
        for y_px, row in enumerate(mask):
            for x_px, value in enumerate(row):
                if isinstance(value, bool):
                    accepted = value
                elif isinstance(value, (int, float)):
                    accepted = value > 0
                else:
                    raise MaskSessionError(
                        "modelFailure", "SAM 3.1 returned a non-binary Anchor View mask."
                    )
                if accepted:
                    foreground = True
                    pixel_index = y_px * view.width + x_px
                    bits[pixel_index // 8] |= 1 << (pixel_index % 8)
        return bits, foreground

    @staticmethod
    def _satisfies_anchor_points(
        bits: bytearray,
        view: RegisteredFrame,
        points: Sequence[Sequence[int]],
        point_labels: Sequence[int],
    ) -> bool:
        if len(points) != len(point_labels):
            raise MaskSessionError(
                "modelFailure", "SAM 3.1 returned against an invalid point-label batch."
            )
        for point, label in zip(points, point_labels, strict=True):
            if len(point) != 2 or label not in {0, 1}:
                raise MaskSessionError(
                    "modelFailure", "SAM 3.1 received an invalid point-label batch."
                )
            x_px, y_px = point
            pixel_index = y_px * view.width + x_px
            present = bool(bits[pixel_index // 8] & (1 << (pixel_index % 8)))
            if present != bool(label):
                return False
        return True


def _build_sam3_predictor(model: Mapping[str, Any]) -> Any:
    """Load the optional operator-installed SAM runtime on demand."""

    weights_path = model.get("weightsPath")
    if not isinstance(weights_path, str) or not weights_path:
        raise MaskSessionError(
            "modelUnavailable", "The SAM 3.1 Model Manifest has no verified checkpoint path."
        )
    try:
        from sam3.model_builder import build_sam3_multiplex_video_predictor
    except ImportError as error:
        raise MaskSessionError(
            "modelRuntimeUnavailable",
            "SAM 3.1 is not installed in this Companion environment; install the matching runtime and retry.",
        ) from error
    predictor = build_sam3_multiplex_video_predictor(
        checkpoint_path=weights_path,
        max_num_objects=SAM31_RUNTIME_CONFIG["max_num_objects"],
        multiplex_count=SAM31_RUNTIME_CONFIG["multiplex_count"],
        use_fa3=SAM31_RUNTIME_CONFIG["use_fa3"],
        use_rope_real=SAM31_RUNTIME_CONFIG["use_rope_real"],
        compile=SAM31_RUNTIME_CONFIG["compile"],
        warm_up=SAM31_RUNTIME_CONFIG["warm_up"],
        session_expiration_sec=SAM31_RUNTIME_CONFIG["session_expiration_sec"],
        default_output_prob_thresh=SAM31_RUNTIME_CONFIG[
            "default_output_prob_thresh"
        ],
        async_loading_frames=SAM31_RUNTIME_CONFIG["async_loading_frames"],
    )
    multiplex_model = getattr(predictor, "model", None)
    init_state = getattr(multiplex_model, "init_state", None)
    if callable(init_state) and "offload_state_to_cpu" not in inspect.signature(
        init_state
    ).parameters:
        # The pinned base predictor always forwards this SAM2-era option, while
        # the pinned multiplex model removed it. Its configured false value is
        # equivalent to omitting it and retaining GPU-backed tracker state.
        def compatible_init_state(
            *args: Any,
            offload_state_to_cpu: bool = False,
            **kwargs: Any,
        ) -> Any:
            if offload_state_to_cpu:
                raise MaskSessionError(
                    "incompatibleRuntime",
                    "The pinned SAM 3.1 multiplex model cannot offload tracker state to CPU.",
                )
            return init_state(*args, **kwargs)

        multiplex_model.init_state = compatible_init_state
    build_sam2_output = getattr(multiplex_model, "_build_sam2_output", None)
    if callable(build_sam2_output):
        # The pinned multiplex implementation returns before merging the first
        # point mask when the frame cache is still empty. Preserve the upstream
        # merge semantics so a fresh point prompt can initialize its object.
        def compatible_build_sam2_output(
            inference_state: Mapping[str, Any],
            frame_idx: int,
            refined_obj_id_to_mask: Mapping[int, Any] | None = None,
        ) -> dict[int, Any]:
            output = dict(
                build_sam2_output(
                    inference_state,
                    frame_idx,
                    refined_obj_id_to_mask,
                )
            )
            if refined_obj_id_to_mask is not None:
                output.update(refined_obj_id_to_mask)
            return output

        multiplex_model._build_sam2_output = compatible_build_sam2_output
    return predictor


def _encode_binary_mask_bits(
    mask: list[list[Any]], width: int, height: int
) -> tuple[bytearray, bool]:
    if len(mask) != height or any(len(row) != width for row in mask):
        raise MaskSessionError(
            'modelFailure', 'SAM 3 Image returned a mask with stale RGB dimensions.'
        )
    bits = bytearray((width * height + 7) // 8)
    foreground = False
    for y_px, row in enumerate(mask):
        for x_px, value in enumerate(row):
            if isinstance(value, bool):
                accepted = value
            elif isinstance(value, (int, float)):
                accepted = value > 0
            else:
                raise MaskSessionError(
                    'modelFailure', 'SAM 3 Image returned a non-binary instance mask.'
                )
            if accepted:
                foreground = True
                pixel_index = y_px * width + x_px
                bits[pixel_index // 8] |= 1 << (pixel_index % 8)
    return bits, foreground


def _instance_prompt_consistency_facts(
    bits: bytes,
    *,
    width: int,
    height: int,
    program: CompiledImagePromptProgram,
) -> tuple[dict[str, bool], list[dict[str, object]]]:
    """Compute exact candidate-local Point/Box facts for one instance mask."""

    def contains(x_px: int, y_px: int) -> bool:
        pixel_index = y_px * width + x_px
        return bool(bits[pixel_index // 8] & (1 << (pixel_index % 8)))

    foreground_count = sum(byte.bit_count() for byte in bits)
    diagnostics: list[dict[str, object]] = []
    point_results: list[bool] = []
    for point in program.points:
        present = contains(point.x_px, point.y_px)
        satisfied = present == (point.polarity == 'include')
        point_results.append(satisfied)
        diagnostics.append({
            'promptId': point.prompt_id,
            'family': 'point',
            'polarity': point.polarity,
            'satisfied': satisfied,
        })

    box_results: list[bool] = []
    for box in program.boxes:
        box_pixels = [
            (x_px, y_px)
            for y_px in range(box.y0_px, box.y1_px)
            for x_px in range(box.x0_px, box.x1_px)
        ]
        intersection_count = sum(
            contains(x_px, y_px) for x_px, y_px in box_pixels
        )
        # This is an exact local fact, not an acceptance threshold. Ticket
        # 07A owns how fill/spill fractions affect proposal eligibility.
        satisfied = intersection_count > 0
        box_results.append(satisfied)
        diagnostics.append({
            'promptId': box.prompt_id,
            'family': 'box',
            'polarity': 'include',
            'satisfied': satisfied,
            'constraintCoverageFraction': intersection_count / len(box_pixels),
            'candidateCoverageFraction': (
                0.0
                if foreground_count == 0
                else intersection_count / foreground_count
            ),
        })

    point_positive = [
        result
        for point, result in zip(program.points, point_results, strict=True)
        if point.polarity == 'include'
    ]
    point_negative = [
        result
        for point, result in zip(program.points, point_results, strict=True)
        if point.polarity == 'exclude'
    ]
    facts: dict[str, bool] = {
        'positivePointsSatisfied': all(point_positive),
        'negativePointsSatisfied': all(point_negative),
        'positiveBoxesSatisfied': all(box_results),
    }
    return facts, diagnostics


class _Sam3ImageModelRuntime:
    """The locked official SAM 3 Image path behind the injectable seam."""

    def __init__(self, model: Any, processor: Any) -> None:
        self._model = model
        self._processor = processor

    @staticmethod
    def _inference_scope() -> Any:
        """The pinned upstream execution scope for every model entry point.

        The upstream interactive example runs both ``set_image`` and
        ``predict_inst`` inside one inference_mode + bf16 autocast scope.
        Ambient autocast state is thread-local (and the builder leaks an
        enabled autocast state into its calling thread), so each entry point
        must establish the scope explicitly or HTTP worker threads execute a
        different dtype contract than the main thread.
        """

        import contextlib

        import torch

        stack = contextlib.ExitStack()
        try:
            import torch
        except ImportError as error:
            raise MaskSessionError(
                'modelRuntimeUnavailable',
                'SAM 3 Image requires the pinned PyTorch runtime in this Companion environment.',
            ) from error
        stack.enter_context(torch.inference_mode())
        if torch.cuda.is_available():
            stack.enter_context(torch.autocast('cuda', dtype=torch.bfloat16))
        return stack

    def set_image(self, rgb_png: bytes) -> Any:
        try:
            from PIL import Image
        except ImportError as error:
            raise MaskSessionError(
                'modelRuntimeUnavailable',
                'SAM 3 Image dependencies are unavailable in this Companion environment.',
            ) from error
        try:
            with Image.open(io.BytesIO(rgb_png)) as image:
                rgb = image.convert('RGB').copy()
        except Exception as error:
            raise MaskSessionError(
                'invalidRgb',
                'The authoritative RGB cannot be decoded for SAM 3 Image prompting.',
            ) from error
        with self._inference_scope():
            return self._processor.set_image(rgb)

    def predict_inst(self, inference_state: Any, **kwargs: Any) -> Any:
        with self._inference_scope():
            return self._model.predict_inst(inference_state, **kwargs)


def _build_sam3_image_runtime(model: Mapping[str, Any]) -> _Sam3ImageModelRuntime:
    """Load the optional operator-installed SAM 3 Image runtime on demand."""

    weights_path = model.get('weightsPath')
    if not isinstance(weights_path, str) or not weights_path:
        raise MaskSessionError(
            'modelUnavailable',
            'The SAM 3 Image Model Manifest has no verified checkpoint path.',
        )
    try:
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
    except ImportError as error:
        raise MaskSessionError(
            'modelRuntimeUnavailable',
            'SAM 3 Image is not installed in this Companion environment; install the matching runtime and retry.',
        ) from error
    try:
        built = build_sam3_image_model(
            enable_inst_interactivity=SAM3_IMAGE_RUNTIME_CONFIG[
                'enable_inst_interactivity'
            ],
            checkpoint_path=weights_path,
            load_from_HF=SAM3_IMAGE_RUNTIME_CONFIG['load_from_hf'],
            compile=SAM3_IMAGE_RUNTIME_CONFIG['compile'],
        )
    except Exception as error:
        raise MaskSessionError(
            'modelFailure',
            'The SAM 3 Image checkpoint could not be initialized from the installed Model Manifest.',
        ) from error
    return _Sam3ImageModelRuntime(built, Sam3Processor(built))


class Sam3ImageInstanceAdapter:
    """Locked SAM 3 Image instance adapter for the current static Prompt path.

    The model builder is injectable so contract tests can substitute a fake
    runtime; the default builds the pinned official upstream
    ``build_sam3_image_model(enable_inst_interactivity=True)`` model and its
    ``Sam3Processor``. The built model is cached per Model Manifest digest as
    Companion-local disposable state. Inference state and low-resolution
    logits never cross the browser boundary; only generic Mask bytes, scores,
    and opaque digest-bound references do. This adapter must never instantiate
    the Multiplex video predictor or call private tracker-head methods.
    """

    def __init__(
        self,
        *,
        build_model: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._build_model = build_model or _build_sam3_image_runtime
        self._runtime_cache_key: str | None = None
        self._runtime_cache: Any = None

    def runtime_profile_capability(
        self, model: Mapping[str, Any]
    ) -> dict[str, object]:
        capabilities = sam3_image_instance_capabilities()
        capability: dict[str, object] = {
            'status': 'ready',
            'authoritativeRgb': {
                'artifact': True,
                'companionReference': True,
            },
            'promptCapabilities': {
                key: capabilities[key]
                for key in (
                    'positivePoints',
                    'negativePoints',
                    'positiveInstanceBox',
                    'previousLogitsRefinement',
                    'singlePointMultimask',
                    'negativeBox',
                    'promptBrush',
                    'maskConstraints',
                    'text',
                )
            },
            'compilerPolicyVersion': SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
            'adapterCapabilityDigest': capabilities['capabilityDigest'],
        }
        try:
            self._require_runtime(model)
        except MaskSessionError as error:
            return {
                **capability,
                'status': 'unavailable',
                'message': str(error),
            }
        except Exception:
            return {
                **capability,
                'status': 'unavailable',
                'message': (
                    'The SAM 3 Image checkpoint could not be initialized in '
                    'this Companion environment.'
                ),
            }
        return capability

    def produce_proposals(
        self,
        *,
        model: Mapping[str, Any],
        rgb_png: bytes,
        width: int,
        height: int,
        program: CompiledImagePromptProgram,
        refinement: Sam3ImageRefinementInput | None,
        cancelled: Callable[[], bool],
        force_single_mask: bool = False,
    ) -> Sam3ImageProposalBatch:
        """Run unranked instance inference through the locked image API.

        This method owns only adapter execution, candidate-local prompt facts,
        and the pinned single-result/area candidate policy. It never publishes
        Stable authority; that remains downstream policy.
        """

        if model.get('adapterId') != SAM3_IMAGE_INSTANCE_ADAPTER_ID:
            raise MaskSessionError(
                'incompatibleManifest',
                'The selected Model Manifest is incompatible with the SAM 3 Image instance adapter.',
            )
        if model.get('runtimeConfigDigest') != SAM3_IMAGE_RUNTIME_CONFIG_DIGEST:
            raise MaskSessionError(
                'incompatibleManifest',
                'The selected SAM 3 Image Model Manifest does not bind the pinned runtime configuration.',
            )
        if (
            width != program.width
            or height != program.height
            or f'sha256:{hashlib.sha256(rgb_png).hexdigest()}' != program.rgb_digest
            or program.adapter_capability_digest
            != sam3_image_instance_capabilities()['capabilityDigest']
        ):
            raise MaskSessionError(
                'capabilityMismatch',
                'The Prompt program does not bind this RGB, dimensions, and adapter capability.',
            )
        if cancelled():
            raise MaskSessionError(
                'cancelled', 'The instance Prompt request was cancelled.'
            )

        runtime = self._require_runtime(model)
        multimask_output = (
            False
            if force_single_mask
            else resolve_multimask_output(program, refinement is not None)
        )
        if refinement is None:
            inference_state = runtime.set_image(rgb_png)
        else:
            # Refinement reuses the exact stored image state and the chosen
            # candidate's low-resolution logits as mask_input; the RGB digest
            # lineage was validated before this dispatch.
            inference_state = refinement.inference_state
        if cancelled():
            raise MaskSessionError(
                'cancelled', 'The instance Prompt request was cancelled.'
            )

        import numpy as np

        point_coords = None
        point_labels = None
        if program.points:
            point_coords = np.array(
                [[point.x_px, point.y_px] for point in program.points],
                dtype=np.float32,
            )
            point_labels = np.array(
                [
                    1 if point.polarity == 'include' else 0
                    for point in program.points
                ],
                dtype=np.int32,
            )
        box = None
        if program.boxes:
            instance_box = program.boxes[0]
            box = np.array(
                [
                    instance_box.x0_px,
                    instance_box.y0_px,
                    instance_box.x1_px,
                    instance_box.y1_px,
                ],
                dtype=np.float32,
            )
        masks, scores, low_res_logits = runtime.predict_inst(
            inference_state,
            point_coords=point_coords,
            point_labels=point_labels,
            box=box,
            mask_input=None if refinement is None else refinement.mask_input,
            multimask_output=multimask_output,
            return_logits=False,
            # The pinned SAM Image API interprets absolute authoritative-image
            # pixels correctly only when it performs its native normalization.
            normalize_coords=True,
        )
        if cancelled():
            raise MaskSessionError(
                'cancelled', 'The instance Prompt request was cancelled.'
            )

        mask_candidates = Sam3PointMaskAdapter._mask_candidates(masks)
        if not mask_candidates:
            return Sam3ImageProposalBatch(
                candidates=(), inference_state=inference_state
            )
        candidate_scores = Sam3PointMaskAdapter._candidate_scores(
            scores, len(mask_candidates)
        )
        logits_size = int(SAM3_IMAGE_RUNTIME_CONFIG['low_res_logits_size'])
        logits_array = np.asarray(low_res_logits, dtype=np.float32)
        if (
            logits_array.ndim != 3
            or logits_array.shape[0] != len(mask_candidates)
            or logits_array.shape[1] != logits_size
            or logits_array.shape[2] != logits_size
        ):
            raise MaskSessionError(
                'modelFailure',
                'SAM 3 Image returned low-resolution logits that do not match its candidates.',
            )

        candidate_cap = 1
        retained: list[Sam3ImageCandidate] = []
        seen_payloads: set[bytes] = set()
        for source_index, (mask, score) in enumerate(
            zip(mask_candidates, candidate_scores, strict=True)
        ):
            bits, foreground = _encode_binary_mask_bits(mask, width, height)
            foreground_count = sum(byte.bit_count() for byte in bits)
            if (
                not foreground
                or (
                    SAM3_IMAGE_RUNTIME_CONFIG['reject_full_frame_masks']
                    and foreground_count == width * height
                )
            ):
                continue
            payload = bytes(bits)
            if payload in seen_payloads:
                # Byte-identical duplicate masks are removed without any
                # general clustering framework.
                continue
            seen_payloads.add(payload)
            prompt_consistency, prompt_diagnostics = (
                _instance_prompt_consistency_facts(
                    payload, width=width, height=height, program=program
                )
            )
            retained.append(
                Sam3ImageCandidate(
                    source_index=source_index,
                    mask_bits=payload,
                    model_score=score,
                    prompt_consistency=MappingProxyType(prompt_consistency),
                    prompt_diagnostics=tuple(
                        MappingProxyType(diagnostic)
                        for diagnostic in prompt_diagnostics
                    ),
                    low_res_logits=np.ascontiguousarray(
                        logits_array[source_index].reshape(
                            1, logits_size, logits_size
                        )
                    ),
                )
            )
            if len(retained) >= candidate_cap:
                break
        return Sam3ImageProposalBatch(
            candidates=tuple(retained), inference_state=inference_state
        )

    def _require_runtime(self, model: Mapping[str, Any]) -> Any:
        cache_key = str(model.get('digest') or model.get('weightsPath') or '')
        if (
            self._runtime_cache_key == cache_key
            and self._runtime_cache is not None
        ):
            return self._runtime_cache
        runtime = self._build_model(model)
        # A different Active Model Manifest deterministically replaces the
        # previous built runtime; Python finalization releases its GPU state.
        self._runtime_cache_key = cache_key
        self._runtime_cache = runtime
        return runtime
def _require_string(payload: dict[str, Any], name: str, subject: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise MaskSessionError(
            "invalidFrameSet", f"{subject} {name} must be a non-empty string."
        )
    return value


def _require_dimension(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MaskSessionError(
            "invalidFrameSet", f"Frame Set view {name} must be a positive integer."
        )
    return value


def _optional_png(payload: dict[str, Any]) -> bytes | None:
    """Decode optional Anchor RGB without retaining browser-specific handles."""

    value = payload.get("imagePngBase64")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MaskSessionError(
            "invalidFrameSet", "Frame Set imagePngBase64 must be a non-empty base64 string."
        )
    try:
        image_png = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise MaskSessionError(
            "invalidFrameSet", "Frame Set imagePngBase64 is not valid base64."
        ) from error
    if not image_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MaskSessionError(
            "invalidFrameSet", "Frame Set imagePngBase64 must contain a PNG image."
        )
    return image_png

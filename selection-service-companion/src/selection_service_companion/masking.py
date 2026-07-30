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
from typing import Any, Callable, Mapping, Protocol, runtime_checkable, Sequence


# The compiler is a capability-level contract: changing prompt ordering,
# coordinate conversion, or composition changes the advertised capability
# digest so a replay artifact from the old semantics cannot be rebound.
POINT_MASK_PROMPT_COMPILER_POLICY_VERSION = 'point-mask-compiler/v1'
SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION = 'sam3.1-visual-prompt-compiler/v1'


# The initial SAM 3.1 adapter intentionally pins every material predictor and
# session option rather than inheriting upstream defaults.  The digest is the
# manifest identity for this executable configuration, not an operator-chosen
# label: changing one of these values requires a new adapter baseline.
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


def sam31_visual_prompt_capabilities() -> dict[str, object]:
    """Return the exact, digest-bound SAM 3.1 visual-prompt contract.

    Positive Box uses the pinned interactive-image API. The current SAM
    ``mask_input`` consumes previous-iteration logits rather than a partial
    positive scribble, so Prompt Brush remains off after its locked quality
    gate failed. Negative visual and Text composition are also explicitly off.
    """

    payload: dict[str, object] = {
        'points': True,
        'negativePoints': True,
        'boxes': True,
        'negativeBoxes': False,
        'maskInput': False,
        'negativeMaskConstraints': False,
        'text': False,
        'negativeText': False,
        'multiCandidateOutput': True,
        'compilerPolicyVersion': SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
        'unsupportedPromptReasons': {
            'negative-box': (
                'The locked SAM 3.1 interactive-image adapter has no validated '
                'negative Box composition.'
            ),
            'positive-mask-constraint': (
                'Prompt Brush is disabled because SAM mask_input expects '
                'previous-prediction logits; the partial-brush GPU quality '
                'gate failed.'
            ),
            'negative-mask-constraint': (
                'The locked SAM 3.1 interactive-image adapter has no validated '
                'negative Mask constraint composition.'
            ),
            'positive-text': 'Text prompts are not enabled by this adapter.',
            'negative-text': 'Text prompts are not enabled by this adapter.',
        },
    }
    return {**payload, 'capabilityDigest': _prompt_capability_digest(payload)}


@dataclass(frozen=True)
class Sam31CompiledPointPrompt:
    """One exact RGB-pixel point preserved for model input and diagnostics."""

    prompt_id: str
    polarity: str
    x_px: int
    y_px: int


@dataclass(frozen=True)
class Sam31CompiledBoxPrompt:
    """An inclusive PixelBox compiled to the native normalized XYWH contract."""

    prompt_id: str
    polarity: str
    x0_px: int
    y0_px: int
    x1_px: int
    y1_px: int
    normalized_xywh: tuple[float, float, float, float]


@dataclass(frozen=True)
class Sam31CompiledMaskConstraintPrompt:
    """One immutable Prompt Brush artifact retained for candidate diagnostics."""

    prompt_id: str
    polarity: str
    bits: bytes


@dataclass(frozen=True)
class Sam31VisualPromptProgram:
    """Deterministic, RGB-bound visual constraints for one SAM invocation."""

    compiler_policy_version: str
    rgb_digest: str
    prompt_state_digest: str
    adapter_capability_digest: str
    width: int
    height: int
    points: tuple[Sam31CompiledPointPrompt, ...]
    boxes: tuple[Sam31CompiledBoxPrompt, ...]
    mask_constraints: tuple[Sam31CompiledMaskConstraintPrompt, ...]
    positive_mask_constraint: bytes | None
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


def _decode_mask_constraint(
    entry: Mapping[str, object], *, width: int, height: int
) -> bytes:
    artifact = entry.get('artifact')
    if not isinstance(artifact, Mapping):
        raise MaskSessionError(
            'invalidPromptState', 'Mask constraint artifact must be an object.'
        )
    if (
        artifact.get('encoding') != 'bitset-lsb-v1'
        or artifact.get('width') != width
        or artifact.get('height') != height
        or not isinstance(artifact.get('data'), str)
    ):
        raise MaskSessionError(
            'invalidPromptState',
            'Mask constraint artifact must match the exact authoritative RGB.',
        )
    try:
        bits = base64.b64decode(str(artifact['data']), validate=True)
    except (ValueError, TypeError) as error:
        raise MaskSessionError(
            'invalidPromptState', 'Mask constraint artifact data is invalid.'
        ) from error
    expected_length = (width * height + 7) // 8
    if len(bits) != expected_length:
        raise MaskSessionError(
            'invalidPromptState',
            'Mask constraint artifact data does not match its dimensions.',
        )
    if bits and width * height % 8 and bits[-1] >> (width * height % 8):
        raise MaskSessionError(
            'invalidPromptState',
            'Mask constraint artifact sets bits outside its dimensions.',
        )
    digest = artifact.get('digest')
    expected_digest = f'sha256:{hashlib.sha256(bits).hexdigest()}'
    if digest != expected_digest:
        raise MaskSessionError(
            'invalidPromptState',
            'Mask constraint artifact digest does not match its bytes.',
        )
    return bits


def compile_sam31_visual_prompt_program(
    prompt_state: Mapping[str, object],
    *,
    width: int,
    height: int,
    capabilities: Mapping[str, object],
) -> Sam31VisualPromptProgram:
    """Compile exact PromptState constraints without ranking any candidates.

    The declared order is family then lexicographic Prompt ID. Boxes use
    inclusive pixel bounds and become normalized XYWH for SAM. Every family is
    capability-checked before its payload is decoded; no visual constraint is
    converted to a Point or silently discarded.
    """

    if width <= 0 or height <= 0:
        raise MaskSessionError(
            'invalidPromptState', 'Prompt compilation requires positive RGB dimensions.'
        )
    if (
        capabilities.get('compilerPolicyVersion')
        != SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION
    ):
        raise MaskSessionError(
            'capabilityMismatch',
            'The SAM 3.1 visual Prompt compiler policy is incompatible.',
        )
    rgb_digest = prompt_state.get('rgbDigest')
    prompt_state_digest = prompt_state.get('digest')
    capability_digest = capabilities.get('capabilityDigest')
    if not all(
        isinstance(value, str)
        and len(value) == len('sha256:') + 64
        and value.startswith('sha256:')
        and all(character in '0123456789abcdef' for character in value[7:])
        for value in (rgb_digest, prompt_state_digest, capability_digest)
    ):
        raise MaskSessionError(
            'invalidPromptState',
            'Prompt compilation requires exact RGB, PromptState, and capability digests.',
        )

    points_value = prompt_state.get('points')
    boxes_value = prompt_state.get('boxes')
    constraints_value = prompt_state.get('maskConstraints')
    text_value = prompt_state.get('textPrompts')
    if not all(
        isinstance(value, list)
        for value in (points_value, boxes_value, constraints_value, text_value)
    ):
        raise MaskSessionError(
            'invalidPromptState', 'PromptState families must be arrays.'
        )
    if text_value:
        _require_supported_prompt(capabilities, 'text', 'Text prompts')
        raise MaskSessionError(
            'unsupportedPromptType',
            'The locked SAM 3.1 visual adapter does not accept Text prompts.',
        )

    points: list[Sam31CompiledPointPrompt] = []
    boxes: list[Sam31CompiledBoxPrompt] = []
    mask_constraints: list[Sam31CompiledMaskConstraintPrompt] = []
    prompt_ids: set[str] = set()

    for entry in points_value:
        if not isinstance(entry, Mapping):
            raise MaskSessionError('invalidPromptState', 'Point prompts must be objects.')
        prompt_id = _require_prompt_id(entry, 'Point')
        polarity = _require_prompt_polarity(entry, 'Point')
        _require_supported_prompt(
            capabilities,
            'negativePoints' if polarity == 'exclude' else 'points',
            'negative Point prompts' if polarity == 'exclude' else 'Point prompts',
        )
        if prompt_id in prompt_ids:
            raise MaskSessionError('invalidPromptState', 'Prompt IDs must be unique.')
        prompt_ids.add(prompt_id)
        points.append(
            Sam31CompiledPointPrompt(
                prompt_id=prompt_id,
                polarity=polarity,
                x_px=_require_prompt_pixel(entry, 'xPx', width=width, height=height),
                y_px=_require_prompt_pixel(entry, 'yPx', width=width, height=height),
            )
        )

    for entry in boxes_value:
        if not isinstance(entry, Mapping):
            raise MaskSessionError('invalidPromptState', 'Box prompts must be objects.')
        prompt_id = _require_prompt_id(entry, 'Box')
        polarity = _require_prompt_polarity(entry, 'Box')
        _require_supported_prompt(
            capabilities,
            'negativeBoxes' if polarity == 'exclude' else 'boxes',
            'negative Box prompts' if polarity == 'exclude' else 'Box prompts',
        )
        if prompt_id in prompt_ids:
            raise MaskSessionError('invalidPromptState', 'Prompt IDs must be unique.')
        prompt_ids.add(prompt_id)
        x0_px = _require_prompt_pixel(entry, 'x0Px', width=width, height=height)
        y0_px = _require_prompt_pixel(entry, 'y0Px', width=width, height=height)
        x1_px = _require_prompt_pixel(entry, 'x1Px', width=width, height=height)
        y1_px = _require_prompt_pixel(entry, 'y1Px', width=width, height=height)
        if x0_px >= x1_px or y0_px >= y1_px:
            raise MaskSessionError(
                'invalidPromptState', 'Box prompts must have a non-empty pixel area.'
            )
        boxes.append(
            Sam31CompiledBoxPrompt(
                prompt_id=prompt_id,
                polarity=polarity,
                x0_px=x0_px,
                y0_px=y0_px,
                x1_px=x1_px,
                y1_px=y1_px,
                normalized_xywh=(
                    x0_px / width,
                    y0_px / height,
                    (x1_px - x0_px + 1) / width,
                    (y1_px - y0_px + 1) / height,
                ),
            )
        )

    for entry in constraints_value:
        if not isinstance(entry, Mapping):
            raise MaskSessionError(
                'invalidPromptState', 'Mask constraints must be objects.'
            )
        prompt_id = _require_prompt_id(entry, 'Mask constraint')
        polarity = _require_prompt_polarity(entry, 'Mask constraint')
        _require_supported_prompt(
            capabilities,
            'negativeMaskConstraints' if polarity == 'exclude' else 'maskInput',
            (
                'negative Mask constraints'
                if polarity == 'exclude'
                else 'Mask constraints'
            ),
        )
        if prompt_id in prompt_ids:
            raise MaskSessionError('invalidPromptState', 'Prompt IDs must be unique.')
        prompt_ids.add(prompt_id)
        mask_constraints.append(
            Sam31CompiledMaskConstraintPrompt(
                prompt_id=prompt_id,
                polarity=polarity,
                bits=_decode_mask_constraint(entry, width=width, height=height),
            )
        )

    points.sort(key=lambda point: point.prompt_id)
    boxes.sort(key=lambda box: box.prompt_id)
    mask_constraints.sort(key=lambda constraint: constraint.prompt_id)
    positive_mask_constraint: bytes | None = None
    if mask_constraints:
        composed = bytearray((width * height + 7) // 8)
        for constraint in mask_constraints:
            if constraint.polarity != 'include':
                # The capability check above means this is only reachable when
                # a future version explicitly enables negative Mask semantics.
                raise MaskSessionError(
                    'unsupportedPromptType',
                    'Negative Mask constraint composition is not available in this compiler.',
                )
            for index, value in enumerate(constraint.bits):
                composed[index] |= value
        positive_mask_constraint = bytes(composed)

    compiled_prompt_ids = [
        *(point.prompt_id for point in points),
        *(box.prompt_id for box in boxes),
        *(constraint.prompt_id for constraint in mask_constraints),
    ]
    return Sam31VisualPromptProgram(
        compiler_policy_version=SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
        rgb_digest=rgb_digest,
        prompt_state_digest=prompt_state_digest,
        adapter_capability_digest=capability_digest,
        width=width,
        height=height,
        points=tuple(points),
        boxes=tuple(boxes),
        mask_constraints=tuple(mask_constraints),
        positive_mask_constraint=positive_mask_constraint,
        diagnostics=MappingProxyType({
            'compilerPolicyVersion': SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
            'promptOrder': 'family-then-prompt-id-lexicographic/v1',
            'boxCoordinateConvention': (
                'inclusive-authoritative-pixel-xyxy-native-normalization/v1'
            ),
            'boxComposition': 'independent-box-branches/v1',
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
) -> Sam31VisualPromptProgram:
    """Validate the reference point-only program without adopting SAM identity."""

    if (
        capabilities.get('compilerPolicyVersion')
        != POINT_MASK_PROMPT_COMPILER_POLICY_VERSION
    ):
        raise MaskSessionError(
            'capabilityMismatch',
            'The Point Mask Prompt compiler policy is incompatible.',
        )
    compiler_capabilities = {
        **capabilities,
        'compilerPolicyVersion': SAM31_VISUAL_PROMPT_COMPILER_POLICY_VERSION,
    }
    program = compile_sam31_visual_prompt_program(
        prompt_state,
        width=width,
        height=height,
        capabilities=compiler_capabilities,
    )
    return Sam31VisualPromptProgram(
        compiler_policy_version=POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
        rgb_digest=program.rgb_digest,
        prompt_state_digest=program.prompt_state_digest,
        adapter_capability_digest=program.adapter_capability_digest,
        width=program.width,
        height=program.height,
        points=program.points,
        boxes=program.boxes,
        mask_constraints=program.mask_constraints,
        positive_mask_constraint=program.positive_mask_constraint,
        diagnostics=MappingProxyType({
            **program.diagnostics,
            'compilerPolicyVersion': POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
        }),
    )


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
class AISelectVisualPromptCandidate:
    """One structurally valid, unranked model candidate for the proposal seam."""

    source_index: int
    mask_bits: bytes
    model_score: float | None
    prompt_consistency: Mapping[str, bool]
    prompt_diagnostics: tuple[Mapping[str, object], ...]


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


@runtime_checkable
class AISelectVisualPromptAdapter(PromptableMaskAdapter, Protocol):
    """A prompt adapter that explicitly owns the visual inference contract."""

    def produce_ai_select_visual_proposals(
        self,
        *,
        model: Mapping[str, Any],
        rgb_png: bytes,
        width: int,
        height: int,
        program: Sam31VisualPromptProgram,
        cancelled: Callable[[], bool],
    ) -> tuple[AISelectVisualPromptCandidate, ...]:
        """Return independently validated candidates without cross-candidate policy."""


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
    checks.  It never claims to be image/model inference; the `sam3.1` adapter
    below is the isolated model-backed Anchor View implementation.
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
    """Track SAM 3.1 point prompts across an ordered Frame Set.

    SAM and its checkpoint remain separately installed by the operator.  This
    adapter imports that runtime only when selected, passes the verified
    checkpoint path to it, materializes immutable PNGs into a temporary video
    sequence, and releases the model session before returning generic mask
    bytes to the Companion state machine.
    """

    def __init__(
        self,
        *,
        build_predictor: Callable[[Mapping[str, Any]], Any] | None = None,
        build_interactive_predictor: Callable[[Mapping[str, Any], bytes], Any]
        | None = None,
    ) -> None:
        self._build_predictor = build_predictor or _build_sam3_predictor
        self._build_interactive_predictor = (
            build_interactive_predictor or _build_sam3_interactive_image_predictor
        )

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

    def produce_ai_select_visual_proposals(
        self,
        *,
        model: Mapping[str, Any],
        rgb_png: bytes,
        width: int,
        height: int,
        program: Sam31VisualPromptProgram,
        cancelled: Callable[[], bool],
    ) -> tuple[AISelectVisualPromptCandidate, ...]:
        """Run unranked visual-prompt inference through the locked image API.

        This method owns only adapter execution and candidate-local prompt
        facts. It never compares candidates, truncates them, or chooses a
        proposal; those operations remain downstream policy concerns.
        """

        if model.get('adapterId') != 'sam3.1':
            raise MaskSessionError(
                'incompatibleManifest',
                'The selected Model Manifest is incompatible with the SAM 3.1 visual Prompt adapter.',
            )
        if model.get('runtimeConfigDigest') != SAM31_RUNTIME_CONFIG_DIGEST:
            raise MaskSessionError(
                'incompatibleManifest',
                'The selected SAM 3.1 Model Manifest does not bind the pinned visual Prompt runtime.',
            )
        if (
            width != program.width
            or height != program.height
            or f'sha256:{hashlib.sha256(rgb_png).hexdigest()}' != program.rgb_digest
            or program.adapter_capability_digest
            != sam31_visual_prompt_capabilities()['capabilityDigest']
        ):
            raise MaskSessionError(
                'capabilityMismatch',
                'The visual Prompt program does not bind this RGB, dimensions, and adapter capability.',
            )
        if program.mask_constraints:
            raise MaskSessionError(
                'unsupportedPromptType',
                'Prompt Brush has no validated SAM 3.1 visual Prompt mapping.',
            )
        if cancelled():
            raise MaskSessionError('cancelled', 'The visual Prompt request was cancelled.')

        predictor = self._build_interactive_predictor(model, rgb_png)
        branches = program.boxes or (None,)
        candidates: list[AISelectVisualPromptCandidate] = []
        source_index = 0
        for box in branches:
            if cancelled():
                raise MaskSessionError(
                    'cancelled', 'The visual Prompt request was cancelled.'
                )
            masks, scores, _low_res_masks = predictor.predict(
                point_coords=[
                    [point.x_px, point.y_px] for point in program.points
                ]
                or None,
                point_labels=[
                    1 if point.polarity == 'include' else 0
                    for point in program.points
                ]
                or None,
                box=(
                    [[box.x0_px, box.y0_px, box.x1_px, box.y1_px]]
                    if box is not None
                    else None
                ),
                mask_input=None,
                multimask_output=True,
                return_logits=False,
                # Pinned SAM interprets absolute authoritative-image pixels
                # correctly only when it performs its native normalization.
                normalize_coords=True,
            )
            mask_candidates = self._mask_candidates(masks)
            candidate_scores = self._candidate_scores(scores, len(mask_candidates))
            for mask, score in zip(mask_candidates, candidate_scores, strict=True):
                bits, foreground = self._encode_binary_mask(
                    mask,
                    RegisteredFrame(
                        view_id='anchor-view',
                        frame_digest='',
                        width=width,
                        height=height,
                    ),
                )
                foreground_count = sum(byte.bit_count() for byte in bits)
                if (
                    not foreground
                    or (
                        SAM31_RUNTIME_CONFIG['reject_full_frame_masks']
                        and foreground_count == width * height
                    )
                ):
                    source_index += 1
                    continue
                prompt_consistency, prompt_diagnostics = (
                    self._visual_prompt_consistency_facts(
                        bits,
                        width=width,
                        height=height,
                        program=program,
                    )
                )
                candidates.append(
                    AISelectVisualPromptCandidate(
                        source_index=source_index,
                        mask_bits=bytes(bits),
                        model_score=score,
                        prompt_consistency=MappingProxyType(prompt_consistency),
                        prompt_diagnostics=tuple(
                            MappingProxyType(diagnostic)
                            for diagnostic in prompt_diagnostics
                        ),
                    )
                )
                source_index += 1
        return tuple(candidates)

    @staticmethod
    def _visual_prompt_consistency_facts(
        bits: bytes,
        *,
        width: int,
        height: int,
        program: Sam31VisualPromptProgram,
    ) -> tuple[dict[str, bool], list[dict[str, object]]]:
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
                for y_px in range(box.y0_px, box.y1_px + 1)
                for x_px in range(box.x0_px, box.x1_px + 1)
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
                'polarity': box.polarity,
                'satisfied': satisfied,
                'constraintCoverageFraction': intersection_count / len(box_pixels),
                'candidateCoverageFraction': (
                    0.0
                    if foreground_count == 0
                    else intersection_count / foreground_count
                ),
            })

        mask_results: list[bool] = []
        for constraint in program.mask_constraints:
            constraint_count = sum(byte.bit_count() for byte in constraint.bits)
            intersection_count = sum(
                byte.bit_count() for byte in bytes(
                    left & right for left, right in zip(bits, constraint.bits, strict=True)
                )
            )
            satisfied = intersection_count > 0
            mask_results.append(satisfied)
            diagnostics.append({
                'promptId': constraint.prompt_id,
                'family': 'mask-constraint',
                'polarity': constraint.polarity,
                'satisfied': satisfied,
                'constraintCoverageFraction': (
                    0.0 if constraint_count == 0 else intersection_count / constraint_count
                ),
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
        }
        if program.boxes:
            facts['positiveBoxesSatisfied'] = all(box_results)
        if program.mask_constraints:
            facts['maskConstraintsSatisfied'] = all(mask_results)
        return facts, diagnostics

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


@dataclass(frozen=True)
class _Sam31InteractiveImageSession:
    """One locked SAM 3.1 interactive head over shared image features."""

    runtime: Any
    tracker_model: Any
    backbone_features: Any
    high_resolution_features: tuple[Any, ...]
    multiplex_state: Any
    original_width: int
    original_height: int

    @property
    def model(self) -> Any:
        return self.tracker_model

    def predict(self, **request: object) -> tuple[object, object, object]:
        import torch
        import torch.nn.functional as functional

        if request.get('normalize_coords') is not True:
            raise ValueError(
                'SAM 3.1 visual prompts must use authoritative pixel coordinates.'
            )
        device = self.backbone_features.device
        coords: list[list[float]] = []
        labels: list[int] = []
        box = request.get('box')
        if box is not None:
            box_tensor = torch.as_tensor(box, dtype=torch.float32)
            if box_tensor.numel() != 4:
                raise ValueError('SAM 3.1 Box input must contain one XYXY box.')
            box_values = box_tensor.reshape(4).tolist()
            coords.extend([
                [float(box_values[0]), float(box_values[1])],
                [float(box_values[2]), float(box_values[3])],
            ])
            labels.extend([2, 3])
        point_coords = request.get('point_coords')
        point_labels = request.get('point_labels')
        if point_coords is not None:
            point_tensor = torch.as_tensor(point_coords, dtype=torch.float32)
            label_tensor = torch.as_tensor(point_labels, dtype=torch.int32)
            if (
                point_tensor.ndim != 2
                or point_tensor.shape[-1] != 2
                or label_tensor.ndim != 1
                or point_tensor.shape[0] != label_tensor.shape[0]
            ):
                raise ValueError('SAM 3.1 Point inputs are structurally invalid.')
            coords.extend(point_tensor.tolist())
            labels.extend(label_tensor.tolist())
        point_inputs: dict[str, Any] | None = None
        if coords:
            point_coords_tensor = torch.tensor(
                coords, dtype=torch.float32, device=device
            )
            point_coords_tensor[:, 0] *= (
                self.tracker_model.image_size / self.original_width
            )
            point_coords_tensor[:, 1] *= (
                self.tracker_model.image_size / self.original_height
            )
            point_inputs = {
                'point_coords': point_coords_tensor.unsqueeze(0),
                'point_labels': torch.tensor(
                    labels, dtype=torch.int32, device=device
                ).unsqueeze(0),
            }
        mask_input = request.get('mask_input')
        mask_tensor = None
        if mask_input is not None:
            mask_tensor = torch.as_tensor(
                mask_input, dtype=torch.float32, device=device
            )
            if mask_tensor.ndim == 3:
                mask_tensor = mask_tensor.unsqueeze(0)
            if mask_tensor.ndim != 4 or mask_tensor.shape[:2] != (1, 1):
                raise ValueError('SAM 3.1 Mask input is structurally invalid.')
        with torch.inference_mode():
            output = self.tracker_model._forward_sam_heads(
                backbone_features=self.backbone_features,
                point_inputs=point_inputs,
                mask_inputs=mask_tensor,
                interactive_high_res_features=list(
                    self.high_resolution_features
                ),
                multimask_output=bool(request.get('multimask_output', True)),
                objects_to_interact=[0],
                multiplex_state=self.multiplex_state,
            )
            masks = output['high_res_multimasks']
            if masks.shape[-2:] != (self.original_height, self.original_width):
                masks = functional.interpolate(
                    masks,
                    size=(self.original_height, self.original_width),
                    mode='bilinear',
                    align_corners=False,
                )
            if request.get('return_logits') is not True:
                masks = masks > 0
            return (
                masks.squeeze(0).float().cpu().numpy(),
                output['ious'].squeeze(0).float().cpu().numpy(),
                output['low_res_multimasks'].squeeze(0).float().cpu().numpy(),
            )


def _build_sam3_interactive_image_predictor(
    model: Mapping[str, Any], rgb_png: bytes
) -> Any:
    """Build the pinned SAM 3.1 shared-backbone image-prompt surface."""

    weights_path = model.get('weightsPath')
    if not isinstance(weights_path, str) or not weights_path:
        raise MaskSessionError(
            'modelUnavailable',
            'The SAM 3.1 Model Manifest has no verified checkpoint path.',
        )
    try:
        from PIL import Image
        from sam3.model.sam3_image_processor import Sam3Processor
    except ImportError as error:
        raise MaskSessionError(
            'modelRuntimeUnavailable',
            'SAM 3.1 interactive-image dependencies are unavailable in this Companion environment.',
        ) from error
    try:
        with Image.open(io.BytesIO(rgb_png)) as image:
            rgb = image.convert('RGB').copy()
    except Exception as error:
        raise MaskSessionError(
            'invalidRgb',
            'The authoritative RGB cannot be decoded for SAM 3.1 visual prompting.',
        ) from error
    try:
        runtime = _build_sam3_predictor(model)
        multiplex_model = getattr(runtime, 'model', None)
        detector = getattr(multiplex_model, 'detector', None)
        tracker_wrapper = getattr(multiplex_model, 'tracker', None)
        tracker_model = getattr(tracker_wrapper, 'model', None)
        if detector is None or tracker_model is None:
            raise RuntimeError(
                'SAM 3.1 multiplex runtime has no detector/tracker prompt surface'
            )
        import torch
        from torchvision.transforms import v2

        processor = Sam3Processor(detector)
        image_tensor = processor.transform(
            v2.functional.to_image(rgb).to('cuda')
        ).unsqueeze(0)
        with torch.inference_mode():
            backbone_out = detector.backbone.forward_image(
                image_tensor,
                need_sam3_out=False,
                need_interactive_out=True,
                need_propagation_out=False,
            )
            interactive = backbone_out['interactive']
            if tracker_model.use_high_res_features_in_sam:
                interactive['backbone_fpn'][
                    0
                ].tensors = tracker_model.interactive_sam_mask_decoder.conv_s0(
                    interactive['backbone_fpn'][0].tensors
                )
                interactive['backbone_fpn'][
                    1
                ].tensors = tracker_model.interactive_sam_mask_decoder.conv_s1(
                    interactive['backbone_fpn'][1].tensors
                )
            prepared = tracker_model._prepare_backbone_features(backbone_out)[
                'interactive'
            ]
            vision_features = prepared['vision_feats']
            feature_sizes = prepared['feat_sizes']
            backbone_features = tracker_model._get_interactive_pix_mem(
                vision_features, feature_sizes
            )
            high_resolution_features = tuple(
                feature.permute(1, 2, 0).view(
                    feature.size(1), feature.size(2), *size
                )
                for feature, size in zip(
                    vision_features[:-1], feature_sizes[:-1], strict=True
                )
            )
            multiplex_state = tracker_model.multiplex_controller.get_state(
                num_valid_entries=1,
                device=backbone_features.device,
                dtype=backbone_features.dtype,
                random=False,
                object_ids=[1],
            )
        return _Sam31InteractiveImageSession(
            runtime=runtime,
            tracker_model=tracker_model,
            backbone_features=backbone_features,
            high_resolution_features=high_resolution_features,
            multiplex_state=multiplex_state,
            original_width=rgb.width,
            original_height=rgb.height,
        )
    except MaskSessionError:
        raise
    except Exception as error:
        raise MaskSessionError(
            'modelFailure',
            'The locked SAM 3.1 interactive-image adapter failed to prepare the authoritative RGB.',
        ) from error


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

"""Model-independent promptable-mask contracts for the Companion."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Protocol, Sequence


# The initial SAM 3.1 adapter intentionally pins every material predictor and
# session option rather than inheriting upstream defaults.  The digest is the
# manifest identity for this executable configuration, not an operator-chosen
# label: changing one of these values requires a new adapter baseline.
SAM31_RUNTIME_CONFIG: dict[str, Any] = {
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
    """Run SAM 3.1 point inference over a registered Anchor PNG.

    SAM and its checkpoint remain separately installed by the operator.  This
    adapter imports that runtime only when selected, passes the verified
    checkpoint path to it, and releases the model's temporary session before
    returning generic, immutable mask bytes to the Companion state machine.
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
        if anchor_view.image_png is None:
            raise MaskSessionError(
                "frameDataUnavailable",
                "The SAM 3.1 adapter requires the registered Anchor View PNG bytes.",
            )

        anchor_outcome, candidate_diagnostics = self._infer_anchor_mask(
            model=model,
            view=anchor_view,
            points=points,
            point_labels=point_labels,
            cancelled=cancelled,
        )
        if anchor_outcome["status"] != "accepted":
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View did not produce an accepted SAM 3.1 mask; adjust the point prompts and retry.",
            )
        return MaskProduction(
            tracks=[{
                "trackId": "primary",
                "role": "include",
                "frames": [
                    anchor_outcome if view.view_id == anchor_view.view_id else {
                        "viewId": view.view_id,
                        "status": "error",
                        "rejectionReason": "SAM 3.1 Anchor Mask inference does not cover this Generated View.",
                    }
                    for view in frame_set.ordered_views
                ],
            }],
            threshold=float(SAM31_RUNTIME_CONFIG["default_output_prob_thresh"]),
            diagnostics={
                "adapterId": "sam3.1",
                "candidateSelection": candidate_diagnostics,
            },
        )

    def _infer_anchor_mask(
        self,
        *,
        model: Mapping[str, Any],
        view: RegisteredFrame,
        points: list[list[int]],
        point_labels: list[int],
        cancelled: Callable[[], bool],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        predictor = self._build_predictor(model)
        with tempfile.TemporaryDirectory(prefix="supersplat-sam3-") as directory:
            image_path = Path(directory) / "0.png"
            image_path.write_bytes(view.image_png or b"")
            started = predictor.handle_request({
                "type": "start_session",
                "resource_path": str(image_path),
                "offload_video_to_cpu": SAM31_RUNTIME_CONFIG["offload_video_to_cpu"],
                "offload_state_to_cpu": SAM31_RUNTIME_CONFIG["offload_state_to_cpu"],
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
                response = predictor.handle_request({
                    "type": "add_prompt",
                    "session_id": session_id,
                    "frame_index": 0,
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
                return self._mask_outcome_and_diagnostics_from_response(
                    response,
                    view,
                    points=points,
                    point_labels=point_labels,
                )
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
    return build_sam3_multiplex_video_predictor(
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

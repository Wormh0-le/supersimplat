from __future__ import annotations

import hashlib
import inspect
import io
import json
import unittest
from pathlib import Path

from PIL import Image

from selection_service_companion import masking
from selection_service_companion.masking import (
    SAM3_IMAGE_INSTANCE_ADAPTER_ID,
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    Sam3ImageInstanceAdapter,
    Sam3ImageRefinementInput,
    compile_sam3_image_prompt_program,
    find_sam3_image_checkpoint,
    sam3_image_instance_capabilities,
)


def _gpu_fixture_available() -> bool:
    if find_sam3_image_checkpoint() is None:
        return False
    repository = Path(__file__).resolve().parents[2]
    if not (
        repository
        / 'docs/benchmarks/fixtures/office/targets/clothes_rack/'
        / 'frame-set-v1/frames/001-anchor.png'
    ).is_file():
        return False
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


class Sam3ImageStaticPathAuditTests(unittest.TestCase):
    """Static proof that the current static path retired Multiplex internals."""

    def test_the_retired_private_tracker_path_is_gone(self) -> None:
        source = inspect.getsource(masking)

        self.assertNotIn('_forward_sam_heads', source)
        self.assertNotIn('def _build_sam3_interactive_image_predictor', source)
        self.assertNotIn('def produce_ai_select_visual_proposals', source)
        self.assertNotIn('def compile_sam31_visual_prompt_program', source)

    def test_the_current_static_adapter_never_touches_multiplex(self) -> None:
        adapter_source = inspect.getsource(Sam3ImageInstanceAdapter)
        builder_source = inspect.getsource(masking._build_sam3_image_runtime)

        for source in (adapter_source, builder_source):
            self.assertNotIn('build_sam3_multiplex_video_predictor', source)
            self.assertNotIn('_forward_sam_heads', source)


@unittest.skipUnless(
    _gpu_fixture_available(),
    'locked SAM 3 Image GPU fixture requires the ModelScope cache and office image fixture',
)
class Sam3ImageInstanceGpuTests(unittest.TestCase):
    """Locked-runtime proof for the official SAM 3 Image instance path."""

    def test_point_box_and_refinement_on_the_real_image_model(self) -> None:
        checkpoint = find_sam3_image_checkpoint()
        self.assertIsNotNone(checkpoint)
        assert checkpoint is not None

        repository = Path(__file__).resolve().parents[2]
        image_path = repository / (
            'docs/benchmarks/fixtures/office/targets/clothes_rack/'
            'frame-set-v1/frames/001-anchor.png'
        )
        rgb_png = image_path.read_bytes()
        with Image.open(io.BytesIO(rgb_png)) as image:
            width, height = image.size
        rgb_digest = f'sha256:{hashlib.sha256(rgb_png).hexdigest()}'
        capabilities = sam3_image_instance_capabilities()
        self.assertTrue(capabilities['positiveInstanceBox'])
        self.assertTrue(capabilities['previousLogitsRefinement'])
        self.assertNotIn('promptBrush', capabilities)
        model = {
            'adapterId': SAM3_IMAGE_INSTANCE_ADAPTER_ID,
            'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            'weightsPath': str(checkpoint),
        }
        adapter = Sam3ImageInstanceAdapter()

        try:
            point_batch = adapter.produce_proposals(
                model=model,
                rgb_png=rgb_png,
                width=width,
                height=height,
                program=self._program(
                    rgb_digest=rgb_digest,
                    width=width,
                    height=height,
                    capabilities=capabilities,
                    points=[{
                        'promptId': 'rack-positive',
                        'polarity': 'include',
                        'xPx': 548,
                        'yPx': 410,
                    }],
                    boxes=[],
                ),
                refinement=None,
                cancelled=lambda: False,
            )
            # One positive point returns one result with Companion-local
            # low-resolution logits for refinement.
            self.assertEqual(len(point_batch.candidates), 1)
            for candidate in point_batch.candidates:
                self.assertEqual(candidate.low_res_logits.shape, (1, 288, 288))
                self.assertEqual(str(candidate.low_res_logits.dtype), 'float32')

            # The HTTP server executes model work on handler threads, not
            # the main thread that built the runtime; ambient autocast state
            # is thread-local, so the pinned inference scope must hold there.
            box_result: dict[str, object] = {}

            def produce_box_in_worker_thread(
                adapter: Sam3ImageInstanceAdapter = adapter,
            ) -> None:
                try:
                    box_result['batch'] = adapter.produce_proposals(
                        model=model,
                        rgb_png=rgb_png,
                        width=width,
                        height=height,
                        program=self._program(
                            rgb_digest=rgb_digest,
                            width=width,
                            height=height,
                            capabilities=capabilities,
                            points=[{
                                'promptId': 'rack-positive',
                                'polarity': 'include',
                                'xPx': 548,
                                'yPx': 410,
                            }],
                            boxes=[{
                                'promptId': 'rack-box',
                                'polarity': 'include',
                                'x0Px': 475,
                                'y0Px': 170,
                                'x1Px': 624,
                                'y1Px': 859,
                            }],
                        ),
                        refinement=None,
                        cancelled=lambda: False,
                    )
                except Exception as error:  # noqa: BLE001
                    box_result['error'] = error

            import threading

            worker = threading.Thread(target=produce_box_in_worker_thread)
            worker.start()
            worker.join()
            if 'error' in box_result:
                raise box_result['error']  # type: ignore[misc]
            box_batch = box_result['batch']
            # A Box forces single-mask mode.
            self.assertLessEqual(len(box_batch.candidates), 1)

            refined_batch = adapter.produce_proposals(
                model=model,
                rgb_png=rgb_png,
                width=width,
                height=height,
                program=self._program(
                    rgb_digest=rgb_digest,
                    width=width,
                    height=height,
                    capabilities=capabilities,
                    points=[
                        {
                            'promptId': 'rack-positive',
                            'polarity': 'include',
                            'xPx': 548,
                            'yPx': 410,
                        },
                        {
                            'promptId': 'rack-negative',
                            'polarity': 'exclude',
                            'xPx': 700,
                            'yPx': 500,
                        },
                    ],
                    boxes=[],
                ),
                refinement=Sam3ImageRefinementInput(
                    inference_state=point_batch.inference_state,
                    mask_input=point_batch.candidates[0].low_res_logits,
                ),
                cancelled=lambda: False,
            )
            # Previous-logits refinement forces single-mask mode.
            self.assertLessEqual(len(refined_batch.candidates), 1)
        finally:
            del adapter
            import torch

            torch.cuda.empty_cache()

    def test_locked_model_oom_fault_publishes_no_candidate_batch(self) -> None:
        import torch

        checkpoint = find_sam3_image_checkpoint()
        self.assertIsNotNone(checkpoint)
        assert checkpoint is not None
        repository = Path(__file__).resolve().parents[2]
        rgb_png = (
            repository
            / 'docs/benchmarks/fixtures/office/targets/clothes_rack/frame-set-v1/frames/001-anchor.png'
        ).read_bytes()
        with Image.open(io.BytesIO(rgb_png)) as image:
            width, height = image.size
        rgb_digest = f'sha256:{hashlib.sha256(rgb_png).hexdigest()}'
        capabilities = sam3_image_instance_capabilities()
        model = {
            'adapterId': SAM3_IMAGE_INSTANCE_ADAPTER_ID,
            'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            'weightsPath': str(checkpoint),
        }
        adapter = Sam3ImageInstanceAdapter()
        runtime = adapter._require_runtime(model)

        class OomRuntime:
            def set_image(self, value: bytes) -> object:
                return runtime.set_image(value)

            def predict_inst(self, *_args: object, **_kwargs: object) -> object:
                raise torch.OutOfMemoryError('injected locked-model OOM')

        adapter._runtime_cache = OomRuntime()
        try:
            with self.assertRaises(torch.OutOfMemoryError):
                adapter.produce_proposals(
                    model=model,
                    rgb_png=rgb_png,
                    width=width,
                    height=height,
                    program=self._program(
                        rgb_digest=rgb_digest,
                        width=width,
                        height=height,
                        capabilities=capabilities,
                        points=[{
                            'promptId': 'rack-positive',
                            'polarity': 'include',
                            'xPx': 548,
                            'yPx': 410,
                        }],
                        boxes=[],
                    ),
                    refinement=None,
                    cancelled=lambda: False,
                )
        finally:
            del adapter
            torch.cuda.empty_cache()

    @staticmethod
    def _program(
        *,
        rgb_digest: str,
        width: int,
        height: int,
        capabilities: dict[str, object],
        points: list[dict[str, object]],
        boxes: list[dict[str, object]],
    ):
        prompt_state: dict[str, object] = {
            'schemaVersion': 2,
            'viewId': 'anchor-view',
            'rgbDigest': rgb_digest,
            'revision': 1,
            'points': points,
            'boxes': boxes,
        }
        prompt_state['digest'] = 'sha256:' + hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in prompt_state.items()
                    if key != 'digest'
                },
                separators=(',', ':'),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return compile_sam3_image_prompt_program(
            prompt_state,
            width=width,
            height=height,
            capabilities=capabilities,
        )


if __name__ == '__main__':
    unittest.main()

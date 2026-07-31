from __future__ import annotations

import hashlib
import json
import unittest

import numpy as np

from selection_service_companion.masking import (
    MaskSessionError,
    POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
    SAM3_IMAGE_INSTANCE_ADAPTER_ID,
    SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    Sam3ImageInstanceAdapter,
    Sam3ImageRefinementInput,
    compile_point_mask_prompt_program,
    compile_sam3_image_prompt_program,
    resolve_multimask_output,
    sam3_image_instance_capabilities,
)


RGB_DIGEST = f'sha256:{"1" * 64}'
IMAGE_WIDTH = 4
IMAGE_HEIGHT = 4


def _digest(prompt_state: dict[str, object]) -> str:
    payload = {
        key: value for key, value in prompt_state.items() if key != 'digest'
    }
    encoded = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def _prompt_state(
    *,
    points: list[dict[str, object]] | None = None,
    boxes: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    prompt_state: dict[str, object] = {
        'schemaVersion': 2,
        'viewId': 'anchor-view',
        'rgbDigest': RGB_DIGEST,
        'revision': 1,
        'points': points if points is not None else [
            {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
        ],
        'boxes': boxes if boxes is not None else [],
    }
    prompt_state['digest'] = _digest(prompt_state)
    return prompt_state


def _point_prompt_capabilities() -> dict[str, object]:
    payload: dict[str, object] = {
        'points': True,
        'negativePoints': True,
        'boxes': False,
        'compilerPolicyVersion': POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
    }
    encoded = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    return {
        **payload,
        'capabilityDigest': f'sha256:{hashlib.sha256(encoded).hexdigest()}',
    }


class Sam3ImageCapabilitiesTests(unittest.TestCase):
    def test_declares_the_exact_current_instance_contract(self) -> None:
        capabilities = sam3_image_instance_capabilities()

        self.assertEqual(
            set(capabilities),
            {
                'positivePoints',
                'negativePoints',
                'positiveInstanceBox',
                'previousLogitsRefinement',
                'singlePointMultimask',
                'negativeBox',
                'promptBrush',
                'maskConstraints',
                'text',
                'compilerPolicyVersion',
                'capabilityDigest',
            },
        )
        self.assertTrue(capabilities['positivePoints'])
        self.assertTrue(capabilities['negativePoints'])
        self.assertTrue(capabilities['positiveInstanceBox'])
        self.assertTrue(capabilities['previousLogitsRefinement'])
        self.assertTrue(capabilities['singlePointMultimask'])
        self.assertFalse(capabilities['negativeBox'])
        self.assertFalse(capabilities['promptBrush'])
        self.assertFalse(capabilities['maskConstraints'])
        self.assertFalse(capabilities['text'])
        self.assertEqual(
            capabilities['compilerPolicyVersion'],
            SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
        )

    def test_capability_digest_recomputes_over_the_ten_bound_fields(self) -> None:
        capabilities = sam3_image_instance_capabilities()
        payload = {
            key: value
            for key, value in capabilities.items()
            if key != 'capabilityDigest'
        }
        encoded = json.dumps(
            payload, separators=(',', ':'), sort_keys=True
        ).encode()

        self.assertEqual(
            capabilities['capabilityDigest'],
            f'sha256:{hashlib.sha256(encoded).hexdigest()}',
        )


class Sam3ImagePromptCompilerTests(unittest.TestCase):
    def compile(self, prompt_state: dict[str, object]):
        return compile_sam3_image_prompt_program(
            prompt_state,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            capabilities=sam3_image_instance_capabilities(),
        )

    def test_compiles_points_and_one_pixel_xyxy_box_in_a_stable_order(self) -> None:
        program = self.compile(_prompt_state(
            points=[
                {'promptId': 'point-b', 'xPx': 3, 'yPx': 2, 'polarity': 'exclude'},
                {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
            ],
            boxes=[{
                'promptId': 'box-a',
                'polarity': 'include',
                'x0Px': 0,
                'y0Px': 1,
                'x1Px': 2,
                'y1Px': 3,
            }],
        ))

        self.assertEqual(
            program.compiler_policy_version,
            SAM3_IMAGE_PROMPT_COMPILER_POLICY_VERSION,
        )
        self.assertEqual(
            [point.prompt_id for point in program.points], ['point-a', 'point-b']
        )
        self.assertEqual(len(program.boxes), 1)
        box = program.boxes[0]
        self.assertEqual((box.x0_px, box.y0_px, box.x1_px, box.y1_px), (0, 1, 2, 3))
        self.assertEqual(
            program.diagnostics['boxCoordinateConvention'],
            'authoritative-pixel-xyxy/v1',
        )
        self.assertNotIn('normalizedXywh', program.diagnostics)
        self.assertEqual(
            program.diagnostics['compiledPromptIds'],
            ['point-a', 'point-b', 'box-a'],
        )

    def test_rejects_a_v1_artifact_with_removed_families(self) -> None:
        v1_state: dict[str, object] = {
            'schemaVersion': 1,
            'viewId': 'anchor-view',
            'rgbDigest': RGB_DIGEST,
            'revision': 1,
            'points': [
                {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
            ],
            'boxes': [],
            'maskConstraints': [],
            'textPrompts': [],
        }
        v1_state['digest'] = _digest(v1_state)

        with self.assertRaises(MaskSessionError) as error:
            self.compile(v1_state)
        self.assertEqual(error.exception.code, 'invalidPromptState')

    def test_rejects_a_removed_field_even_at_schema_version_2(self) -> None:
        prompt_state = _prompt_state()
        prompt_state['maskConstraints'] = []
        prompt_state['digest'] = _digest(prompt_state)

        with self.assertRaises(MaskSessionError) as error:
            self.compile(prompt_state)
        self.assertEqual(error.exception.code, 'invalidPromptState')

    def test_rejects_a_tampered_payload_via_digest_recompute(self) -> None:
        prompt_state = _prompt_state()
        prompt_state['points'] = [
            {'promptId': 'point-a', 'xPx': 2, 'yPx': 2, 'polarity': 'include'},
        ]

        with self.assertRaises(MaskSessionError) as error:
            self.compile(prompt_state)
        self.assertEqual(error.exception.code, 'invalidPromptState')

    def test_rejects_a_stale_adapter_capability_identity(self) -> None:
        capabilities = sam3_image_instance_capabilities()
        capabilities['capabilityDigest'] = f'sha256:{"f" * 64}'

        with self.assertRaises(MaskSessionError) as error:
            compile_sam3_image_prompt_program(
                _prompt_state(),
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                capabilities=capabilities,
            )
        self.assertEqual(error.exception.code, 'capabilityMismatch')

    def test_rejects_more_than_one_instance_box(self) -> None:
        prompt_state = _prompt_state(
            boxes=[
                {
                    'promptId': 'box-a',
                    'polarity': 'include',
                    'x0Px': 0,
                    'y0Px': 0,
                    'x1Px': 1,
                    'y1Px': 1,
                },
                {
                    'promptId': 'box-b',
                    'polarity': 'include',
                    'x0Px': 1,
                    'y0Px': 1,
                    'x1Px': 2,
                    'y1Px': 2,
                },
            ],
        )

        with self.assertRaises(MaskSessionError) as error:
            self.compile(prompt_state)
        self.assertEqual(error.exception.code, 'invalidPromptState')

    def test_rejects_a_negative_box_without_conversion(self) -> None:
        prompt_state = _prompt_state(
            boxes=[{
                'promptId': 'box-a',
                'polarity': 'exclude',
                'x0Px': 0,
                'y0Px': 0,
                'x1Px': 1,
                'y1Px': 1,
            }],
        )

        with self.assertRaises(MaskSessionError) as error:
            self.compile(prompt_state)
        self.assertEqual(error.exception.code, 'unsupportedPromptType')

    def test_rejects_empty_and_out_of_bounds_boxes(self) -> None:
        for box in (
            {'promptId': 'box-a', 'polarity': 'include', 'x0Px': 1, 'y0Px': 0, 'x1Px': 1, 'y1Px': 2},
            {'promptId': 'box-a', 'polarity': 'include', 'x0Px': 0, 'y0Px': 2, 'x1Px': 2, 'y1Px': 2},
            {'promptId': 'box-a', 'polarity': 'include', 'x0Px': 0, 'y0Px': 0, 'x1Px': IMAGE_WIDTH + 1, 'y1Px': 2},
            {'promptId': 'box-a', 'polarity': 'include', 'x0Px': -1, 'y0Px': 0, 'x1Px': 2, 'y1Px': 2},
        ):
            with self.subTest(box=box):
                with self.assertRaises(MaskSessionError) as error:
                    self.compile(_prompt_state(boxes=[box]))
                self.assertEqual(error.exception.code, 'invalidPromptState')

    def test_rejects_out_of_bounds_and_duplicate_point_prompts(self) -> None:
        out_of_bounds = _prompt_state(points=[
            {'promptId': 'point-a', 'xPx': IMAGE_WIDTH, 'yPx': 0, 'polarity': 'include'},
        ])
        with self.assertRaises(MaskSessionError) as error:
            self.compile(out_of_bounds)
        self.assertEqual(error.exception.code, 'invalidPromptState')

        duplicated = _prompt_state(
            points=[
                {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
                {'promptId': 'point-a', 'xPx': 2, 'yPx': 2, 'polarity': 'exclude'},
            ],
            boxes=[{
                'promptId': 'point-a',
                'polarity': 'include',
                'x0Px': 0,
                'y0Px': 0,
                'x1Px': 1,
                'y1Px': 1,
            }],
        )
        with self.assertRaises(MaskSessionError) as error:
            self.compile(duplicated)
        self.assertEqual(error.exception.code, 'invalidPromptState')


class PointMaskPromptCompilerTests(unittest.TestCase):
    def test_compiles_a_points_only_reference_program(self) -> None:
        program = compile_point_mask_prompt_program(
            _prompt_state(),
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            capabilities=_point_prompt_capabilities(),
        )

        self.assertEqual(
            program.compiler_policy_version,
            POINT_MASK_PROMPT_COMPILER_POLICY_VERSION,
        )
        self.assertEqual(len(program.points), 1)
        self.assertEqual(program.boxes, ())

    def test_rejects_boxes_for_the_reference_adapter(self) -> None:
        with self.assertRaises(MaskSessionError) as error:
            compile_point_mask_prompt_program(
                _prompt_state(boxes=[{
                    'promptId': 'box-a',
                    'polarity': 'include',
                    'x0Px': 0,
                    'y0Px': 0,
                    'x1Px': 1,
                    'y1Px': 1,
                }]),
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                capabilities=_point_prompt_capabilities(),
            )
        self.assertEqual(error.exception.code, 'unsupportedPromptType')


class MultimaskPolicyTests(unittest.TestCase):
    def program(
        self,
        *,
        points: list[dict[str, object]] | None = None,
        boxes: list[dict[str, object]] | None = None,
    ):
        return compile_sam3_image_prompt_program(
            _prompt_state(points=points, boxes=boxes),
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            capabilities=sam3_image_instance_capabilities(),
        )

    def test_exactly_one_positive_point_enables_multimask(self) -> None:
        self.assertTrue(resolve_multimask_output(self.program(), False))

    def test_refinement_box_multi_point_and_negative_point_force_single(self) -> None:
        self.assertFalse(resolve_multimask_output(self.program(), True))
        self.assertFalse(
            resolve_multimask_output(
                self.program(boxes=[{
                    'promptId': 'box-a',
                    'polarity': 'include',
                    'x0Px': 0,
                    'y0Px': 0,
                    'x1Px': 2,
                    'y1Px': 2,
                }]),
                False,
            )
        )
        self.assertFalse(
            resolve_multimask_output(
                self.program(points=[
                    {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
                    {'promptId': 'point-b', 'xPx': 2, 'yPx': 2, 'polarity': 'exclude'},
                ]),
                False,
            )
        )
        self.assertFalse(
            resolve_multimask_output(
                self.program(points=[
                    {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'exclude'},
                ]),
                False,
            )
        )


class FakeSam3ImageRuntime:
    """Records the official image-model seam without requiring CUDA."""

    def __init__(self) -> None:
        self.set_image_calls: list[bytes] = []
        self.predict_calls: list[dict[str, object]] = []
        self.masks: list[list[list[bool]]] = [
            [[False, True, False, False]] * 4,
        ]
        self.scores: list[float] = [0.9]
        self.logits: np.ndarray | None = None

    def set_image(self, rgb_png: bytes) -> dict[str, object]:
        self.set_image_calls.append(rgb_png)
        return {'imageState': len(self.set_image_calls)}

    def predict_inst(
        self, inference_state: object, **kwargs: object
    ) -> tuple[object, object, np.ndarray]:
        self.predict_calls.append({'inferenceState': inference_state, **kwargs})
        count = len(self.masks)
        logits = (
            self.logits
            if self.logits is not None
            else np.zeros((count, 288, 288), dtype=np.float32)
        )
        return self.masks, self.scores, logits


class Sam3ImageInstanceAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = FakeSam3ImageRuntime()
        self.build_calls: list[dict[str, object]] = []

        def build_model(model: dict[str, object]) -> FakeSam3ImageRuntime:
            self.build_calls.append(dict(model))
            return self.runtime

        self.adapter = Sam3ImageInstanceAdapter(build_model=build_model)
        self.model = {
            'digest': 'sha256:manifest-v1',
            'adapterId': SAM3_IMAGE_INSTANCE_ADAPTER_ID,
            'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
            'checkpointDigest': f'sha256:{"2" * 64}',
            'sourceCommit': 'sam3-source-v1',
            'weightsPath': '/models/sam3-image.pt',
        }
        self.rgb_png = b'\x89PNG\r\n\x1a\nfake-rgb-bytes'
        self.rgb_digest = f'sha256:{hashlib.sha256(self.rgb_png).hexdigest()}'

    def program(
        self,
        *,
        points: list[dict[str, object]] | None = None,
        boxes: list[dict[str, object]] | None = None,
    ):
        prompt_state = _prompt_state(points=points, boxes=boxes)
        prompt_state['rgbDigest'] = self.rgb_digest
        prompt_state['digest'] = _digest(prompt_state)
        return compile_sam3_image_prompt_program(
            prompt_state,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            capabilities=sam3_image_instance_capabilities(),
        )

    def produce(self, program, refinement=None):
        return self.adapter.produce_proposals(
            model=self.model,
            rgb_png=self.rgb_png,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            program=program,
            refinement=refinement,
            cancelled=lambda: False,
        )

    def test_single_positive_point_runs_multimask_and_retains_three(self) -> None:
        self.runtime.masks = [
            [[False, True, False, False]] * 4,
            [[False, True, True, False]] * 4,
            [[False, True, True, True]] * 4,
        ]
        self.runtime.scores = [0.9, 0.8, 0.7]

        batch = self.produce(self.program())

        self.assertEqual(self.runtime.set_image_calls, [self.rgb_png])
        self.assertEqual(len(self.runtime.predict_calls), 1)
        predict = self.runtime.predict_calls[0]
        self.assertIs(predict['multimask_output'], True)
        self.assertIsNone(predict['box'])
        self.assertIsNone(predict['mask_input'])
        self.assertIs(predict['normalize_coords'], True)
        self.assertEqual(
            np.asarray(predict['point_coords']).tolist(), [[1.0, 1.0]]
        )
        self.assertEqual(
            np.asarray(predict['point_labels']).tolist(), [1]
        )
        self.assertEqual(len(batch.candidates), 3)
        self.assertEqual(
            [candidate.source_index for candidate in batch.candidates],
            [0, 1, 2],
        )
        for candidate in batch.candidates:
            self.assertEqual(candidate.low_res_logits.shape, (1, 288, 288))
            self.assertEqual(str(candidate.low_res_logits.dtype), 'float32')
            self.assertEqual(
                set(candidate.prompt_consistency),
                {
                    'positivePointsSatisfied',
                    'negativePointsSatisfied',
                    'positiveBoxesSatisfied',
                },
            )

    def test_multimask_retains_at_most_three_candidates(self) -> None:
        self.runtime.masks = [
            [[index == 0, True, False, False]] * 4 for index in range(4)
        ]
        # Distinct non-empty, non-full-frame masks beyond the bound.
        self.runtime.masks = [
            [[True, False, False, False]] * 4,
            [[False, True, False, False]] * 4,
            [[False, False, True, False]] * 4,
            [[False, False, False, True]] * 4,
        ]
        self.runtime.scores = [0.9, 0.8, 0.7, 0.6]

        batch = self.produce(self.program())

        self.assertEqual(
            [candidate.source_index for candidate in batch.candidates],
            [0, 1, 2],
        )

    def test_exact_duplicate_masks_are_removed(self) -> None:
        self.runtime.masks = [
            [[False, True, False, False]] * 4,
            [[False, True, False, False]] * 4,
            [[False, True, True, False]] * 4,
        ]
        self.runtime.scores = [0.9, 0.8, 0.7]

        batch = self.produce(self.program())

        self.assertEqual(
            [candidate.source_index for candidate in batch.candidates],
            [0, 2],
        )

    def test_empty_and_full_frame_masks_are_filtered(self) -> None:
        self.runtime.masks = [
            [[False, False, False, False]] * 4,
            [[True, True, True, True]] * 4,
            [[False, True, False, False]] * 4,
        ]
        self.runtime.scores = [0.9, 0.8, 0.7]

        batch = self.produce(self.program())

        self.assertEqual(
            [candidate.source_index for candidate in batch.candidates],
            [2],
        )

    def test_box_forces_single_mask_mode_in_authoritative_pixel_xyxy(self) -> None:
        batch = self.produce(self.program(
            boxes=[{
                'promptId': 'box-a',
                'polarity': 'include',
                'x0Px': 0,
                'y0Px': 0,
                'x1Px': 2,
                'y1Px': 2,
            }],
        ))

        predict = self.runtime.predict_calls[0]
        self.assertIs(predict['multimask_output'], False)
        self.assertEqual(
            np.asarray(predict['box']).tolist(), [0.0, 0.0, 2.0, 2.0]
        )
        self.assertLessEqual(len(batch.candidates), 1)
        self.assertTrue(
            batch.candidates[0].prompt_consistency['positiveBoxesSatisfied']
        )
        self.assertEqual(
            [
                (diagnostic['family'], diagnostic['promptId'])
                for diagnostic in batch.candidates[0].prompt_diagnostics
            ],
            [('point', 'point-a'), ('box', 'box-a')],
        )

    def test_refinement_reuses_stored_state_and_forces_single_mask_mode(self) -> None:
        first = self.produce(self.program())
        stored_logits = first.candidates[0].low_res_logits
        refinement = Sam3ImageRefinementInput(
            inference_state=first.inference_state,
            mask_input=stored_logits,
        )

        refined = self.produce(
            self.program(points=[
                {'promptId': 'point-a', 'xPx': 1, 'yPx': 1, 'polarity': 'include'},
                {'promptId': 'point-b', 'xPx': 3, 'yPx': 3, 'polarity': 'exclude'},
            ]),
            refinement=refinement,
        )

        # The image state is reused; no second set_image call is made.
        self.assertEqual(len(self.runtime.set_image_calls), 1)
        predict = self.runtime.predict_calls[-1]
        self.assertIs(predict['inferenceState'], first.inference_state)
        self.assertIs(predict['mask_input'], stored_logits)
        self.assertIs(predict['multimask_output'], False)
        self.assertLessEqual(len(refined.candidates), 1)

    def test_rejects_a_non_current_manifest_identity(self) -> None:
        for patch, code in (
            ({'adapterId': 'sam3.1'}, 'incompatibleManifest'),
            ({'runtimeConfigDigest': 'sha256:legacy-runtime'}, 'incompatibleManifest'),
        ):
            with self.subTest(patch=patch):
                with self.assertRaises(MaskSessionError) as error:
                    self.adapter.produce_proposals(
                        model={**self.model, **patch},
                        rgb_png=self.rgb_png,
                        width=IMAGE_WIDTH,
                        height=IMAGE_HEIGHT,
                        program=self.program(),
                        refinement=None,
                        cancelled=lambda: False,
                    )
                self.assertEqual(error.exception.code, code)
        self.assertEqual(self.build_calls, [])

    def test_cancellation_before_inference_builds_and_publishes_nothing(self) -> None:
        with self.assertRaises(MaskSessionError) as error:
            self.adapter.produce_proposals(
                model=self.model,
                rgb_png=self.rgb_png,
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                program=self.program(),
                refinement=None,
                cancelled=lambda: True,
            )
        self.assertEqual(error.exception.code, 'cancelled')
        self.assertEqual(self.build_calls, [])
        self.assertEqual(self.runtime.predict_calls, [])


if __name__ == '__main__':
    unittest.main()

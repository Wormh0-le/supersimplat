from __future__ import annotations

import contextlib
import hashlib
from importlib.metadata import distribution
import io
import json
import os
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from selection_service_companion.masking import (
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
    _build_sam3_interactive_image_predictor,
    compile_sam31_visual_prompt_program,
    sam31_visual_prompt_capabilities,
)


SAM31_SOURCE_COMMIT = '5dd401d1c5c1d5c3eedff06d41b77af824517619'
SAM31_CHECKPOINT_DIGEST = (
    '0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6'
)
SAM31_VISUAL_RUNTIME_DIGEST = (
    'sha256:6e1475abaee95d1ae97a8986494fba6ac7d3f440625f945b3ca0d258c6934c09'
)
CHECKPOINT_ENV = 'SUPERSPLAT_SAM31_VISUAL_GPU_CHECKPOINT'


def _gpu_fixture_available() -> bool:
    checkpoint = os.environ.get(CHECKPOINT_ENV)
    if not checkpoint or not Path(checkpoint).is_file():
        return False
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


@unittest.skipUnless(
    _gpu_fixture_available(),
    f'locked SAM 3.1 GPU fixture requires {CHECKPOINT_ENV}',
)
class Sam31VisualPromptGpuTests(unittest.TestCase):
    """Locked-runtime proof for enabled Point/Box and rejected Brush mapping."""

    def test_point_box_and_rejected_brush_mapping_on_real_model(self) -> None:
        checkpoint = Path(os.environ[CHECKPOINT_ENV])
        self.assertEqual(
            hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            SAM31_CHECKPOINT_DIGEST,
        )
        direct_url = distribution('sam3').read_text('direct_url.json')
        self.assertIsNotNone(direct_url)
        self.assertEqual(
            json.loads(direct_url)['vcs_info']['commit_id'],
            SAM31_SOURCE_COMMIT,
        )
        self.assertEqual(
            SAM31_RUNTIME_CONFIG_DIGEST,
            SAM31_VISUAL_RUNTIME_DIGEST,
        )

        repository = Path(__file__).resolve().parents[2]
        image_path = repository / (
            'docs/benchmarks/fixtures/office/targets/clothes_rack/'
            'frame-set-v1/frames/001-anchor.png'
        )
        rgb_png = image_path.read_bytes()
        with Image.open(io.BytesIO(rgb_png)) as image:
            width, height = image.size
        rgb_digest = f'sha256:{hashlib.sha256(rgb_png).hexdigest()}'
        ground_truth = np.load(
            repository
            / (
                'docs/benchmarks/fixtures/office/targets/clothes_rack/'
                'frame-set-v1/mask-set-v1/masks.npz'
            )
        )['masks'][1]
        brush = np.zeros_like(ground_truth)
        brush[:, 532:548] = ground_truth[:, 532:548]
        box = {
            'promptId': 'rack-box',
            'polarity': 'include',
            'x0Px': 475,
            'y0Px': 170,
            'x1Px': 624,
            'y1Px': 859,
        }
        capabilities = sam31_visual_prompt_capabilities()
        self.assertTrue(capabilities['boxes'])
        self.assertFalse(capabilities['maskInput'])
        self.assertIn(
            'previous-prediction logits',
            capabilities['unsupportedPromptReasons'][
                'positive-mask-constraint'
            ],
        )
        model = {
            'adapterId': 'sam3.1',
            'runtimeConfigDigest': SAM31_RUNTIME_CONFIG_DIGEST,
            'weightsPath': str(checkpoint),
        }

        # The pinned builder is noisy about compatibility keys even on a valid
        # load. The assertions below, not console output, are the fixture gate.
        with contextlib.redirect_stdout(io.StringIO()):
            session = _build_sam3_interactive_image_predictor(model, rgb_png)
        adapter = Sam3PointMaskAdapter(
            build_interactive_predictor=lambda _model, _rgb: session
        )
        try:
            import torch
            import torch.nn.functional as functional

            prompt_encoder = getattr(
                session.model, 'sam_prompt_encoder', None
            )
            if prompt_encoder is None:
                prompt_encoder = session.model.interactive_sam_prompt_encoder
            mask_input_size = prompt_encoder.mask_input_size
            binary_brush_input = functional.interpolate(
                torch.from_numpy(brush.astype(np.float32))[None, None],
                size=tuple(mask_input_size),
                mode='bilinear',
                align_corners=False,
                antialias=True,
            ).squeeze(0).cpu().numpy()
            brush_masks, _, _ = session.predict(
                point_coords=None,
                point_labels=None,
                box=None,
                mask_input=binary_brush_input,
                multimask_output=True,
                return_logits=False,
                normalize_coords=True,
            )
            candidate_sets = {
                name: adapter.produce_ai_select_visual_proposals(
                    model=model,
                    rgb_png=rgb_png,
                    width=width,
                    height=height,
                    program=self._program(
                        rgb_digest=rgb_digest,
                        width=width,
                        height=height,
                        capabilities=capabilities,
                        boxes=boxes,
                    ),
                    cancelled=lambda: False,
                )
                for name, boxes in (
                    ('point', []),
                    ('box', [box]),
                )
            }
        finally:
            del adapter
            del session
            import torch

            torch.cuda.empty_cache()

        for candidates in candidate_sets.values():
            self.assertEqual(
                [candidate.source_index for candidate in candidates],
                [0, 1, 2],
            )
        digests = {
            name: tuple(
                hashlib.sha256(candidate.mask_bits).hexdigest()
                for candidate in candidates
            )
            for name, candidates in candidate_sets.items()
        }
        self.assertNotEqual(digests['box'], digests['point'])
        self.assertEqual(
            [
                diagnostic['promptId']
                for diagnostic in candidate_sets['box'][0].prompt_diagnostics
            ],
            ['rack-negative', 'rack-positive', 'rack-box'],
        )
        best_brush_iou = max(
            self._iou(mask, ground_truth)
            for mask in brush_masks
        )
        self.assertLess(
            best_brush_iou,
            0.5,
            'A partial binary brush must not be advertised as valid SAM mask_input semantics.',
        )

    @staticmethod
    def _iou(candidate: np.ndarray, ground_truth: np.ndarray) -> float:
        candidate_mask = np.asarray(candidate, dtype=bool)
        ground_truth_mask = np.asarray(ground_truth, dtype=bool)
        intersection = np.logical_and(candidate_mask, ground_truth_mask).sum()
        union = np.logical_or(candidate_mask, ground_truth_mask).sum()
        return 0.0 if union == 0 else float(intersection / union)

    @staticmethod
    def _program(
        *,
        rgb_digest: str,
        width: int,
        height: int,
        capabilities: dict[str, object],
        boxes: list[dict[str, object]],
    ):
        prompt_state = {
            'rgbDigest': rgb_digest,
            'digest': f'sha256:{hashlib.sha256(
                json.dumps(
                    {
                        'boxes': boxes,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest()}',
            'points': [
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
            'boxes': boxes,
            'maskConstraints': [],
            'textPrompts': [],
        }
        return compile_sam31_visual_prompt_program(
            prompt_state,
            width=width,
            height=height,
            capabilities=capabilities,
        )

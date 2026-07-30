from __future__ import annotations

import base64
import contextlib
import hashlib
from importlib.metadata import distribution
import io
import json
import os
from pathlib import Path
import unittest

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
    'sha256:de51b91ba833a299fa2ebe512daeda439007c7fa181f375c085bf38fa46b502f'
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
    """Locked-runtime proof that Box and Prompt Brush affect real inference."""

    def test_box_mask_and_combined_prompts_change_real_candidates(self) -> None:
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
        constraint_bits = self._rectangle_mask(
            width=width,
            height=height,
            x0=475,
            y0=170,
            x1=624,
            y1=859,
        )
        box = {
            'promptId': 'rack-box',
            'polarity': 'include',
            'x0Px': 475,
            'y0Px': 170,
            'x1Px': 624,
            'y1Px': 859,
        }
        constraint = {
            'promptId': 'rack-brush',
            'polarity': 'include',
            'artifact': {
                'encoding': 'bitset-lsb-v1',
                'width': width,
                'height': height,
                'data': base64.b64encode(constraint_bits).decode('ascii'),
                'digest': (
                    f'sha256:{hashlib.sha256(constraint_bits).hexdigest()}'
                ),
            },
        }
        capabilities = sam31_visual_prompt_capabilities()
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
                        constraints=constraints,
                    ),
                    cancelled=lambda: False,
                )
                for name, boxes, constraints in (
                    ('point', [], []),
                    ('box', [box], []),
                    ('mask', [], [constraint]),
                    ('combined', [box], [constraint]),
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
        self.assertNotEqual(digests['mask'], digests['point'])
        self.assertNotEqual(digests['combined'], digests['box'])
        self.assertNotEqual(digests['combined'], digests['mask'])
        self.assertEqual(
            [
                diagnostic['promptId']
                for diagnostic in candidate_sets['combined'][0].prompt_diagnostics
            ],
            ['rack-negative', 'rack-positive', 'rack-box', 'rack-brush'],
        )

    @staticmethod
    def _rectangle_mask(
        *,
        width: int,
        height: int,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> bytes:
        bits = bytearray((width * height + 7) // 8)
        for y_px in range(y0, y1 + 1):
            for x_px in range(x0, x1 + 1):
                index = y_px * width + x_px
                bits[index // 8] |= 1 << (index % 8)
        return bytes(bits)

    @staticmethod
    def _program(
        *,
        rgb_digest: str,
        width: int,
        height: int,
        capabilities: dict[str, object],
        boxes: list[dict[str, object]],
        constraints: list[dict[str, object]],
    ):
        prompt_state = {
            'rgbDigest': rgb_digest,
            'digest': f'sha256:{hashlib.sha256(
                json.dumps(
                    {
                        'boxes': boxes,
                        'constraints': constraints,
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
            'maskConstraints': constraints,
            'textPrompts': [],
        }
        return compile_sam31_visual_prompt_program(
            prompt_state,
            width=width,
            height=height,
            capabilities=capabilities,
        )

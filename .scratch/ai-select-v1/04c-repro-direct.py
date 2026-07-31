"""Drive the real SAM 3 Image runtime directly to capture the inference traceback."""

import traceback

from selection_service_companion.masking import (
    _build_sam3_image_runtime,
    sam3_image_instance_capabilities,
    compile_sam3_image_prompt_program,
    resolve_multimask_output,
)

WEIGHTS = '/home/ubuntu/.cache/modelscope/hub/models/facebook/sam3/sam3.pt'

model = {'weightsPath': WEIGHTS, 'digest': 'repro'}

print('building runtime (real build_sam3_image_model on GPU)...')
runtime = _build_sam3_image_runtime(model)
print('runtime built ok')

# Minimal valid 64x48 PNG, same as the HTTP repro.
import base64
import hashlib
import struct
import zlib


def png_bytes(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack('>I', len(data))
            + tag
            + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b''.join(b'\x00' + b'\x80\x80\x80' * width for _ in range(height))
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw))
        + chunk(b'IEND', b'')
    )


png = png_bytes(64, 48)
rgb_digest = f'sha256:{hashlib.sha256(png).hexdigest()}'
caps = sam3_image_instance_capabilities()

prompt_state = {
    'schemaVersion': 2,
    'viewId': 'anchor-view',
    'rgbDigest': rgb_digest,
    'revision': 1,
    'points': [{'promptId': 'prompt-1', 'polarity': 'include', 'xPx': 32, 'yPx': 24}],
    'boxes': [],
}
encoded = __import__('json').dumps(
    prompt_state, separators=(',', ':'), sort_keys=True
).encode()
prompt_state['digest'] = f'sha256:{hashlib.sha256(encoded).hexdigest()}'

program = compile_sam3_image_prompt_program(
    prompt_state, width=64, height=48, capabilities=caps
)
print('program compiled, multimask =', resolve_multimask_output(program, False))

try:
    inference_state = runtime.set_image(png)
    print('set_image ok')
    import numpy as np

    masks, scores, low_res = runtime.predict_inst(
        inference_state,
        point_coords=np.array([[32, 24]], dtype=np.float32),
        point_labels=np.array([1], dtype=np.int32),
        box=None,
        mask_input=None,
        multimask_output=True,
        return_logits=False,
        normalize_coords=True,
    )
    print('predict_inst ok:', type(masks), getattr(masks, 'shape', None))
    print('scores:', scores)
    print('low_res:', getattr(low_res, 'shape', None))
except Exception:
    traceback.print_exc()

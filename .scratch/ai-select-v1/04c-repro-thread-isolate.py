"""Isolate whether set_image or predict_inst fails in a worker thread."""

import threading
import traceback

import numpy as np

from selection_service_companion.masking import _build_sam3_image_runtime

WEIGHTS = '/home/ubuntu/.cache/modelscope/hub/models/facebook/sam3/sam3.pt'

runtime = _build_sam3_image_runtime({'weightsPath': WEIGHTS, 'digest': 't'})
print('runtime built in main thread')

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


def work() -> None:
    try:
        state = runtime.set_image(png)
        print('worker set_image OK')
    except Exception:
        print('worker set_image FAILED:')
        traceback.print_exc()
        return
    try:
        masks, scores, low = runtime.predict_inst(
            state,
            point_coords=np.array([[32, 24]], dtype=np.float32),
            point_labels=np.array([1], dtype=np.int32),
            box=None,
            mask_input=None,
            multimask_output=True,
            return_logits=False,
            normalize_coords=True,
        )
        print('worker predict_inst OK', masks.shape, low.shape)
    except Exception:
        print('worker predict_inst FAILED:')
        traceback.print_exc()


thread = threading.Thread(target=work)
thread.start()
thread.join()

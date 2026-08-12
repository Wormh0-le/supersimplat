"""Instrument dtype/autocast state in main vs worker thread."""

import struct
import threading
import traceback
import zlib

import torch

from selection_service_companion.masking import _build_sam3_image_runtime

WEIGHTS = '/home/ubuntu/.cache/modelscope/hub/models/facebook/sam3/sam3.pt'


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


runtime = _build_sam3_image_runtime({'weightsPath': WEIGHTS, 'digest': 't'})
model = runtime._model

dtypes: dict[str, int] = {}
devices: dict[str, int] = {}
for param in model.parameters():
    dtypes[str(param.dtype)] = dtypes.get(str(param.dtype), 0) + 1
    devices[str(param.device)] = devices.get(str(param.device), 0) + 1
print('param dtypes:', dtypes)
print('param devices:', devices)

png = png_bytes(64, 48)


def probe(label: str) -> None:
    print(
        label,
        'autocast_cuda=',
        torch.is_autocast_enabled('cuda')
        if hasattr(torch, 'is_autocast_enabled')
        else torch.is_autocast_enabled(),
        'inference_mode=',
        torch.is_inference_mode_enabled(),
    )
    try:
        runtime.set_image(png)
        print(label, 'set_image OK')
    except Exception as error:
        print(label, 'set_image FAILED:', type(error).__name__, error)


probe('MAIN')

thread = threading.Thread(target=lambda: probe('WORKER'))
thread.start()
thread.join()

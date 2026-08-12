"""Drive state.produce_ai_select_mask with the REAL adapter and print the wrapped cause."""

import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import traceback

from selection_service_companion.state import (
    AI_SELECT_MASK_PROPOSAL_POLICY_VERSION,
    CompanionState,
)
from selection_service_companion.proposal_ranking import RANKING_POLICY_VERSION
from selection_service_companion.masking import (
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    sam3_image_instance_capabilities,
)

WEIGHTS = '/home/ubuntu/.cache/modelscope/hub/models/facebook/sam3/sam3.pt'

tmp = tempfile.TemporaryDirectory()
directory = Path(tmp.name)
state = CompanionState(directory / 'state')
lock_file = directory / 'uv.lock'
lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
state.install_release('0.1.0', lock_file)

manifest = directory / 'manifest.json'
checkpoint_digest = hashlib.sha256(Path(WEIGHTS).read_bytes()).hexdigest()
manifest.write_text(
    json.dumps({
        'digest': 'operator-sam3-image-instance-v2',
        'adapterId': 'sam3-image-instance/v1',
        'modelName': 'SAM 3 Image',
        'checkpointDigest': f'sha256:{checkpoint_digest}',
        'sourceCommit': '5dd401d1c5c1d5c3eedff06d41b77af824517619',
        'licenseName': 'SAM License',
        'licenseUrl': 'https://example.test/sam-license',
        'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    }),
    encoding='utf-8',
)
manifest_digest = state.install_model(manifest, Path(WEIGHTS))['digest']
print('manifest installed:', manifest_digest)


def png_bytes(width: int, height: int) -> bytes:
    import struct
    import zlib

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


WIDTH, HEIGHT = 64, 48
png = png_bytes(WIDTH, HEIGHT)
rgb_digest = f'sha256:{hashlib.sha256(png).hexdigest()}'

prompt_state = {
    'schemaVersion': 2,
    'viewId': 'anchor-view',
    'rgbDigest': rgb_digest,
    'revision': 1,
    'points': [{'promptId': 'prompt-1', 'polarity': 'include', 'xPx': 32, 'yPx': 24}],
    'boxes': [],
}
encoded = json.dumps(prompt_state, separators=(',', ':'), sort_keys=True).encode()
prompt_state['digest'] = f'sha256:{hashlib.sha256(encoded).hexdigest()}'

request = {
    'requestBinding': {
        'targetContextId': 'repro-context',
        'contextRevision': 0,
        'dependencyToken': {
            'splatId': 'splat-1',
            'renderStateToken': 'render-v1',
            'geometryToken': 'geometry-v1',
            'gaussianIdentityToken': 'ids-v1',
            'worldTransformToken': 'world-v1',
        },
    },
    'targetSplatId': 'splat-1',
    'sceneId': 'splat-1',
    'sceneVersion': 'snapshot-v1',
    'viewId': 'anchor-view',
    'cameraBindingDigest': f'sha256:{"1" * 64}',
    'proposalAttemptId': 'repro-attempt-1',
    'rgbDigest': rgb_digest,
    'rgbWidth': WIDTH,
    'rgbHeight': HEIGHT,
    'rgb': {
        'pngBase64': base64.b64encode(png).decode('ascii'),
        'digest': rgb_digest,
        'width': WIDTH,
        'height': HEIGHT,
    },
    'promptState': prompt_state,
    'modelManifestDigest': manifest_digest,
    'adapterCapabilityDigest': sam3_image_instance_capabilities()['capabilityDigest'],
    'proposalPolicyVersion': AI_SELECT_MASK_PROPOSAL_POLICY_VERSION,
    'rankingPolicyVersion': RANKING_POLICY_VERSION,
}

print('producing with the REAL adapter (default builder)...')
try:
    response = state.produce_ai_select_mask(request)
    print('STATUS complete, proposals:', len(response['proposalSet']['proposals']))
except Exception as error:
    traceback.print_exc()
    cause = error.__cause__
    while cause is not None:
        print('\n=== CAUSE ===')
        traceback.print_exception(type(cause), cause, cause.__traceback__)
        cause = cause.__cause__
    sys.exit(1)

# Mimic the HTTP server: model built in the main thread (capabilities),
# inference executed in a worker thread (ThreadingHTTPServer handler).
import threading

print('building runtime in main thread via capabilities...')
state.runtime_profile_capabilities(['http://localhost:3000'])

result: dict = {}


def run_in_thread() -> None:
    try:
        request['proposalAttemptId'] = 'repro-attempt-2'
        response = state.produce_ai_select_mask(request)
        result['ok'] = len(response['proposalSet']['proposals'])
    except Exception as error:  # noqa: BLE001
        result['error'] = error
        traceback.print_exc()
        cause = error.__cause__
        while cause is not None:
            print('=== CAUSE ===')
            traceback.print_exception(type(cause), cause, cause.__traceback__)
            cause = cause.__cause__


worker = threading.Thread(target=run_in_thread)
worker.start()
worker.join()
print('threaded result:', result.get('ok', result.get('error')))

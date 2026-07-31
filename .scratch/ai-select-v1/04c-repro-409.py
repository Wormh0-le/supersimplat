"""Reproduce the production 409 against the live Companion on :8787."""

import base64
import hashlib
import io
import json
import struct
import sys
import zlib
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def png_bytes(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack('>I', len(data))
            + tag
            + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b''.join(
        b'\x00' + b'\x80\x80\x80' * width for _ in range(height)
    )
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw))
        + chunk(b'IEND', b'')
    )


def digest_of(payload: dict) -> str:
    encoded = json.dumps(
        payload, separators=(',', ':'), sort_keys=True
    ).encode()
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


WIDTH, HEIGHT = 64, 48
png = png_bytes(WIDTH, HEIGHT)
rgb_digest = f'sha256:{hashlib.sha256(png).hexdigest()}'

caps = json.load(
    urlopen(Request(
        'http://127.0.0.1:8787/capabilities',
        headers={'Origin': 'http://localhost:3000'},
    ))
)
provider = caps['imageInstanceProvider']
manifest_digest = caps['activeModelManifest']['digest']

prompt_state = {
    'schemaVersion': 2,
    'viewId': 'anchor-view',
    'rgbDigest': rgb_digest,
    'revision': 1,
    'points': [
        {'promptId': 'prompt-1', 'polarity': 'include', 'xPx': 32, 'yPx': 24}
    ],
    'boxes': [],
}
prompt_state['digest'] = digest_of(prompt_state)

request_body = {
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
    'adapterCapabilityDigest': provider['adapterCapabilityDigest'],
    'proposalPolicyVersion': 'auto-mask-proposals/bounded-source-order-v2',
    'rankingPolicyVersion': 'anchor-mask-ranking/v2',
}

http_request = Request(
    'http://127.0.0.1:8787/ai-select/mask-proposals',
    data=json.dumps(request_body).encode(),
    method='POST',
    headers={'Origin': 'http://localhost:3000', 'Content-Type': 'application/json'},
)
try:
    with urlopen(http_request, timeout=300) as response:
        body = json.load(response)
        print('STATUS', response.status)
        proposals = body['proposalSet']['proposals']
        print('proposals:', len(proposals))
        for proposal in proposals:
            print(
                proposal['proposalId'],
                'score=', proposal.get('modelScore'),
                'logitsRef=', 'logitsRef' in proposal,
            )
except HTTPError as error:
    print('STATUS', error.code)
    print(error.read().decode())
    sys.exit(1)

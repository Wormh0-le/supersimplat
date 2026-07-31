"""04C cross-runtime wire-shape audit — Companion side.

Validates the editor-produced payload (/tmp/04c_ts_payload.json) with the real
Python compiler/digest code, then drives produce_ai_select_mask with a fake
SAM 3 Image runtime and dumps request/response exchanges to
/tmp/04c_py_fixtures.json for the editor validators.
"""

import base64
import copy
import json
from pathlib import Path
import sys
import tempfile

REPO = Path('/home/ubuntu/orca/workspaces/supersimplat/houndshark')
sys.path.insert(0, str(REPO / 'selection-service-companion/tests'))

from selection_service_companion.masking import (  # noqa: E402
    SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    compile_sam3_image_prompt_program,
    sam3_image_instance_capabilities,
)
from selection_service_companion.state import (  # noqa: E402
    AI_SELECT_MASK_PROPOSAL_POLICY_VERSION,
    CompanionState,
    _canonical_json_digest,
)
from selection_service_companion.proposal_ranking import (  # noqa: E402
    RANKING_POLICY_VERSION,
)
from selection_service_companion.masking import Sam3ImageInstanceAdapter  # noqa: E402
from test_ai_select_masks import (  # noqa: E402
    FakeSam3ImageRuntime,
    IMAGE_DIGEST,
    IMAGE_HEIGHT,
    IMAGE_PNG,
    IMAGE_WIDTH,
)

ADAPTER_ID = 'sam3-image-instance/v1'

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        failures.append(label)
        print('FAIL:', label)
    else:
        print('ok:', label)


# --- Part A: validate the editor-produced payload ---------------------------
ts = json.loads(Path('/tmp/04c_ts_payload.json').read_text(encoding='utf-8'))

python_caps = sam3_image_instance_capabilities()
check(
    ts['capabilities']['capabilityDigest'] == python_caps['capabilityDigest'],
    'capability digest parity (TS createPromptAdapterCapabilities == Python)',
)

for name in ('pointState', 'boxState'):
    program = compile_sam3_image_prompt_program(
        ts[name],
        width=ts['rgb']['width'],
        height=ts['rgb']['height'],
        capabilities=ts['capabilities'],
    )
    check(True, f'Python compiler accepts editor PromptState v2 ({name})')

ref = ts['ref']
ref_payload = {key: value for key, value in ref.items() if key != 'refDigest'}
check(
    _canonical_json_digest(ref_payload) == ref['refDigest'],
    'refDigest parity (editor ref recomputes under Python canonical JSON)',
)

# --- Part B: drive the route and dump exchanges ------------------------------
tmp = tempfile.TemporaryDirectory()
directory = Path(tmp.name)
state = CompanionState(directory / 'state')
lock_file = directory / 'uv.lock'
lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
state.install_release('0.1.0', lock_file)

weights = directory / 'sam3-image.pt'
weights.write_bytes(b'separately acquired sam3 image weights')
import hashlib

checkpoint_digest = hashlib.sha256(weights.read_bytes()).hexdigest()
manifest = directory / 'manifest.json'
manifest.write_text(
    json.dumps({
        'digest': 'sha256:sam3-image-v1',
        'adapterId': ADAPTER_ID,
        'modelName': 'SAM 3 Image',
        'checkpointDigest': f'sha256:{checkpoint_digest}',
        'sourceCommit': 'sam3-source-v1',
        'licenseName': 'SAM License',
        'licenseUrl': 'https://example.test/sam-license',
        'runtimeConfigDigest': SAM3_IMAGE_RUNTIME_CONFIG_DIGEST,
    }),
    encoding='utf-8',
)
model_manifest_digest = state.install_model(manifest, weights)['digest']

runtime = FakeSam3ImageRuntime()
runtime.masks = [
    [[False, True], [False, False]],
    [[True, False], [False, False]],
    [[False, False], [False, True]],
]
runtime.scores = [0.9, 0.8, 0.7]
state.mask_adapters[ADAPTER_ID] = Sam3ImageInstanceAdapter(
    build_model=lambda model: runtime
)


def make_request(prompt_state: dict, attempt: str) -> dict:
    return {
        'requestBinding': {
            'targetContextId': 'context-1',
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
        'proposalAttemptId': attempt,
        'rgbDigest': IMAGE_DIGEST,
        'rgbWidth': IMAGE_WIDTH,
        'rgbHeight': IMAGE_HEIGHT,
        'rgb': {
            'pngBase64': base64.b64encode(IMAGE_PNG).decode('ascii'),
            'digest': IMAGE_DIGEST,
            'width': IMAGE_WIDTH,
            'height': IMAGE_HEIGHT,
        },
        'promptState': prompt_state,
        'modelManifestDigest': model_manifest_digest,
        'adapterCapabilityDigest': python_caps['capabilityDigest'],
        'proposalPolicyVersion': AI_SELECT_MASK_PROPOSAL_POLICY_VERSION,
        'rankingPolicyVersion': RANKING_POLICY_VERSION,
    }


def prompt_state(points: list, revision: int) -> dict:
    value = {
        'schemaVersion': 2,
        'viewId': 'anchor-view',
        'rgbDigest': IMAGE_DIGEST,
        'revision': revision,
        'points': points,
        'boxes': [],
    }
    value['digest'] = _canonical_json_digest(value)
    return value


exchanges: dict[str, dict] = {}

fresh_request = make_request(
    prompt_state(
        [{'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'}],
        1,
    ),
    'proposal-attempt-1',
)
fresh_response = state.produce_ai_select_mask(fresh_request)
check(fresh_response['status'] == 'complete', 'fresh request completes')
check(
    len(fresh_response['proposalSet']['proposals']) == 3,
    'single positive point yields three candidates',
)
exchanges['fresh'] = {'request': fresh_request, 'response': fresh_response}

chosen_ref = fresh_response['proposalSet']['proposals'][0].get('logitsRef')
check(chosen_ref is not None, 'fresh candidates carry logits refs')

refinement_request = make_request(
    prompt_state(
        [
            {'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'},
            {'promptId': 'prompt-2', 'xPx': 0, 'yPx': 1, 'polarity': 'exclude'},
        ],
        2,
    ),
    'proposal-attempt-2',
)
refinement_request['previousLogitsRef'] = chosen_ref
del refinement_request['rgb']  # reference-only RGB resolution
refinement_response = state.produce_ai_select_mask(refinement_request)
check(
    refinement_response['status'] == 'complete',
    'reference-only refinement request completes',
)
check(
    'refinementFallback'
    not in refinement_response['proposalSet'].get('diagnostics', {}),
    'valid ref refines without fallback',
)
check(
    len(refinement_response['proposalSet']['proposals']) == 1,
    'refinement forces a single candidate',
)
new_ref = refinement_response['proposalSet']['proposals'][0]['logitsRef']
check(
    new_ref['sourceInferenceAttemptId'] == 'proposal-attempt-1',
    'refinement ref links to the source attempt',
)
exchanges['refinement'] = {
    'request': refinement_request,
    'response': refinement_response,
}

stale_ref = copy.deepcopy(chosen_ref)
stale_ref['stateId'] = 'logits-does-not-exist'
stale_payload = {
    key: value for key, value in stale_ref.items() if key != 'refDigest'
}
stale_ref['refDigest'] = _canonical_json_digest(stale_payload)
fallback_request = make_request(
    prompt_state(
        [{'promptId': 'prompt-1', 'xPx': 1, 'yPx': 0, 'polarity': 'include'}],
        3,
    ),
    'proposal-attempt-3',
)
fallback_request['previousLogitsRef'] = stale_ref
del fallback_request['rgb']
fallback_response = state.produce_ai_select_mask(fallback_request)
check(
    fallback_response['proposalSet']
    .get('diagnostics', {})
    .get('refinementFallback')
    is True,
    'unknown stateId falls back to fresh inference with diagnostic',
)
exchanges['fallback'] = {
    'request': fallback_request,
    'response': fallback_response,
}

Path('/tmp/04c_py_fixtures.json').write_text(
    json.dumps({'capabilities': python_caps, 'exchanges': exchanges}),
    encoding='utf-8',
)
print('fixtures written')

if failures:
    sys.exit(1)

from __future__ import annotations

import base64
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
from typing import Any, Mapping
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from selection_service_companion.gsplat_renderer import AnchorRenderArtifact
from selection_service_companion.masking import MaskSessionError
from selection_service_companion.server import create_server
from selection_service_companion.state import CompanionState


EDITOR_ORIGIN = 'https://editor.example'


class AnchorFixtureRenderer:
    """Records the exact camera accepted at the authoritative renderer seam."""

    renderer_id = 'gsplat'
    requires_locked_runtime = False

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render_anchor(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        view_id: str,
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        self.calls.append(
            {
                'sceneSnapshot': dict(scene_snapshot),
                'viewId': view_id,
                'camera': dict(camera),
                'width': width,
                'height': height,
            }
        )
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=='
        )
        return AnchorRenderArtifact(
            image_png=png,
            rgb_digest=f'sha256:{hashlib.sha256(png).hexdigest()}',
            contributor_digest='sha256:' + ('1' * 64),
        )


class BlockingAnchorFixtureRenderer(AnchorFixtureRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()

    def render_anchor(
        self,
        *,
        scene_snapshot: Mapping[str, Any],
        view_id: str,
        camera: Mapping[str, Any],
        width: int,
        height: int,
    ) -> AnchorRenderArtifact:
        self.started.set()
        if not self.release.wait(timeout=5):
            raise RuntimeError('test Anchor render was never released')
        return super().render_anchor(
            scene_snapshot=scene_snapshot,
            view_id=view_id,
            camera=camera,
            width=width,
            height=height,
        )


class AISelectAnchorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.state = CompanionState(self.directory / 'state')
        self.lock_file = self.directory / 'uv.lock'
        self.lock_file.write_text('locked companion dependencies\n', encoding='utf-8')
        self.state.install_release('0.1.0', self.lock_file)
        self.renderer = AnchorFixtureRenderer()
        self.state.contributor_renderer = self.renderer  # type: ignore[assignment]
        self.server = create_server(
            state=self.state,
            endpoint='http://127.0.0.1:0',
            profile='loopback',
            allowed_origins=[EDITOR_ORIGIN],
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    @staticmethod
    def snapshot() -> dict[str, object]:
        return {
            'protocolVersion': '1',
            'sceneId': 'splat-1',
            'sceneVersion': 'snapshot-v1',
            'gaussianCount': 1,
            'coordinateConvention': 'right-handed world coordinates; quaternion xyzw',
            'attributeSchema': 'mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0',
            'stableIdSchema': 'uint32',
            'appearancePolicy': 'effective-editor-dc-sh-bands-0',
            'renderConfiguration': {
                'version': 'supersplat-effective-rgb-v1',
                'backgroundRgba': [0, 0, 0, 1],
                'alphaMode': 'opaque-background',
                'shBands': 0,
                'rasterizer': 'playcanvas-gsplat-classic',
            },
            'gaussians': [{
                'stableId': 3,
                'mean': [0, 0, 0],
                'rotation': [0, 0, 0, 1],
                'logScale': [0, 0, 0],
                'logitOpacity': 0,
                'dc': [0, 0, 0],
                'sh': [],
            }],
        }

    @staticmethod
    def request_body() -> dict[str, object]:
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
            'renderConfigVersion': 'supersplat-effective-rgb-v1',
            'renderAttemptId': 'attempt-1',
            'viewId': 'anchor-view',
            'cameraBinding': {
                'revision': 0,
                'cameraToWorld': [
                    1, 0, 0, 1,
                    0, 1, 0, 2,
                    0, 0, 1, 3,
                    0, 0, 0, 1,
                ],
                'projection': {
                    'model': 'pinhole',
                    'fx': 100,
                    'fy': 100,
                    'cx': 0.5,
                    'cy': 0.5,
                    'width': 1,
                    'height': 1,
                    'near': 0.1,
                    'far': 100,
                },
                'conventionVersion': 'opencv-camera-to-world/v1',
            },
        }

    def request_json(self, path: str, method: str, body: dict[str, object]) -> dict[str, object]:
        with urlopen(Request(
            f'{self.endpoint}{path}',
            data=json.dumps(body).encode(),
            method=method,
            headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
        )) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            return json.load(response)

    def test_renders_a_registered_snapshot_from_the_bound_camera_without_editor_pixels(self) -> None:
        snapshot = self.snapshot()
        self.request_json('/scene-snapshots/splat-1/snapshot-v1', 'PUT', snapshot)
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['supportedOperations'],
            [
                'aiSelectAnchorRender',
                'aiSelectAnchorReferenceContributor',
                'binarySceneSnapshotRegistrationV1',
                'cameraAwareSpatialWorkingSetV1',
            ],
        )

        response = self.request_json(
            '/ai-select/anchor-renders', 'POST', self.request_body()
        )

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['requestBinding'], self.request_body()['requestBinding'])
        self.assertEqual(response['renderAttemptId'], 'attempt-1')
        self.assertEqual(response['cameraBinding'], self.request_body()['cameraBinding'])
        self.assertEqual(response['rgbRendererVersion'], 'gsplat-rgb/v1')
        # RGB Ready stands alone: the production response carries no complete
        # Contributor identity or mass-validation result.
        self.assertNotIn('contributorDigest', response)
        self.assertNotIn('referenceContributorDigest', response)
        self.assertNotIn('referenceContributorError', response)
        self.assertEqual(response['rgb']['width'], 1)
        self.assertEqual(response['rgb']['height'], 1)
        self.assertEqual(
            base64.b64decode(response['rgb']['pngBase64']),
            base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mNk+M/wHwAF/gL+WnQf3wAAAABJRU5ErkJggg=='
            ),
        )
        self.assertEqual(len(self.renderer.calls), 1)
        self.assertEqual(self.renderer.calls[0]['viewId'], 'anchor-view')
        self.assertEqual(
            self.renderer.calls[0]['camera'],
            {
                'model': 'pinhole',
                'convention': 'opencv-world-to-camera',
                'worldToCamera': [
                    1.0, 0.0, 0.0, -1.0,
                    0.0, 1.0, 0.0, -2.0,
                    0.0, 0.0, 1.0, -3.0,
                    0.0, 0.0, 0.0, 1.0,
                ],
                'intrinsics': [100.0, 0.0, 0.5, 0.0, 100.0, 0.5, 0.0, 0.0, 1.0],
                'nearPlane': 0.1,
                'farPlane': 100.0,
            },
        )

    def test_reports_all_anchor_server_timing_phases(self) -> None:
        """The browser can distinguish the Anchor publication stages in DevTools."""

        self.state.register_scene_snapshot(self.snapshot())
        with urlopen(Request(
            f'{self.endpoint}/ai-select/anchor-renders',
            data=json.dumps(self.request_body()).encode(),
            method='POST',
            headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
        )) as response:
            self.assertEqual(response.status, HTTPStatus.OK)
            timing_header = response.headers.get('Server-Timing')
            self.assertIsNotNone(timing_header)
            self.assertEqual(
                response.headers.get('Access-Control-Expose-Headers'),
                'Server-Timing',
            )
            json.load(response)

        metrics = {
            metric.split(';', 1)[0]
            for metric in timing_header.split(', ')
        }
        self.assertEqual(
            metrics,
            {
                'working-set',
                'gpu-queue',
                'gsplat',
                'contributor-digest',
                'png',
                'json-base64',
            },
        )
        for metric in timing_header.split(', '):
            self.assertRegex(metric, r'^[a-z0-9-]+;dur=\d+(?:\.\d+)?$')

    def test_returns_a_bound_cache_miss_without_rendering(self) -> None:
        response = self.request_json(
            '/ai-select/anchor-renders', 'POST', self.request_body()
        )

        self.assertEqual(response['status'], 'sceneCacheMiss')
        self.assertEqual(response['requestBinding'], self.request_body()['requestBinding'])
        self.assertEqual(response['cameraBinding'], self.request_body()['cameraBinding'])
        self.assertEqual(self.renderer.calls, [])

    def test_rejects_a_request_whose_target_and_dependency_bindings_disagree(self) -> None:
        request = self.request_body()
        request['requestBinding']['dependencyToken']['splatId'] = 'other-splat'  # type: ignore[index]

        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f'{self.endpoint}/ai-select/anchor-renders',
                data=json.dumps(request).encode(),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            ))

        self.assertEqual(error.exception.code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(json.load(error.exception)['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])

    def test_rejects_a_request_whose_target_and_scene_snapshot_bindings_disagree(self) -> None:
        request = self.request_body()
        request['sceneId'] = 'other-splat'

        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f'{self.endpoint}/ai-select/anchor-renders',
                data=json.dumps(request).encode(),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            ))

        self.assertEqual(error.exception.code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(json.load(error.exception)['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])

    def test_anchor_render_holds_the_single_companion_capacity_lease(self) -> None:
        self.state.register_scene_snapshot(self.snapshot())
        renderer = BlockingAnchorFixtureRenderer()
        self.state.contributor_renderer = renderer  # type: ignore[assignment]
        worker = Thread(
            target=lambda: self.state.render_ai_select_anchor(self.request_body()),
            daemon=True,
        )
        worker.start()
        self.assertTrue(renderer.started.wait(timeout=1))
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['capacity']['activeSessions'],
            1,
        )

        competing_request = self.request_body()
        competing_request['requestBinding']['contextRevision'] = 1  # type: ignore[index]
        with self.assertRaisesRegex(MaskSessionError, 'already serving another'):
            self.state.render_ai_select_anchor(competing_request)

        renderer.release.set()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(
            self.state.capabilities([EDITOR_ORIGIN])['capacity']['activeSessions'],
            0,
        )

    def test_replays_a_matching_anchor_request_without_using_a_second_gpu_slot(self) -> None:
        self.state.register_scene_snapshot(self.snapshot())
        renderer = BlockingAnchorFixtureRenderer()
        self.state.contributor_renderer = renderer  # type: ignore[assignment]
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []
        duplicate_started = Event()

        def render_into_results(notify_started: Event | None = None) -> None:
            if notify_started is not None:
                notify_started.set()
            try:
                results.append(self.state.render_ai_select_anchor(self.request_body()))
            except BaseException as error:
                errors.append(error)

        first = Thread(target=render_into_results, daemon=True)
        duplicate = Thread(
            target=lambda: render_into_results(duplicate_started),
            daemon=True,
        )
        first.start()
        self.assertTrue(renderer.started.wait(timeout=1))
        duplicate.start()
        self.assertTrue(duplicate_started.wait(timeout=1))

        renderer.release.set()
        first.join(timeout=5)
        duplicate.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(duplicate.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(renderer.calls), 1)

        replay = self.state.render_ai_select_anchor(self.request_body())
        self.assertEqual(replay, results[0])
        self.assertEqual(len(renderer.calls), 1)

    def test_keeps_only_the_latest_completed_anchor_replay_record(self) -> None:
        self.state.register_scene_snapshot(self.snapshot())

        first = self.state.render_ai_select_anchor(self.request_body())
        next_request = self.request_body()
        next_request['requestBinding']['contextRevision'] = 1  # type: ignore[index]
        second = self.state.render_ai_select_anchor(next_request)

        self.assertNotEqual(
            first['requestBinding']['contextRevision'],
            second['requestBinding']['contextRevision'],
        )
        self.assertEqual(len(self.renderer.calls), 2)
        self.assertEqual(len(self.state._anchor_render_admissions), 1)  # type: ignore[attr-defined]

    def test_rejects_a_request_without_a_render_attempt_identity(self) -> None:
        request = self.request_body()
        del request['renderAttemptId']

        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f'{self.endpoint}/ai-select/anchor-renders',
                data=json.dumps(request).encode(),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            ))

        self.assertEqual(error.exception.code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(json.load(error.exception)['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])

    def test_rejects_a_non_boolean_reference_contributor_switch(self) -> None:
        request = self.request_body()
        request['referenceContributor'] = 'true'

        with self.assertRaises(HTTPError) as error:
            urlopen(Request(
                f'{self.endpoint}/ai-select/anchor-renders',
                data=json.dumps(request).encode(),
                method='POST',
                headers={'Origin': EDITOR_ORIGIN, 'Content-Type': 'application/json'},
            ))

        self.assertEqual(error.exception.code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(json.load(error.exception)['status'], 'invalidRequest')
        self.assertEqual(self.renderer.calls, [])

    def test_reference_contributor_requires_an_explicit_opt_in(self) -> None:
        self.state.register_scene_snapshot(self.snapshot())
        request = self.request_body()
        request['referenceContributor'] = True

        response = self.state.render_ai_select_anchor(request)

        self.assertEqual(response['status'], 'complete')
        self.assertEqual(
            response['referenceContributorDigest'], 'sha256:' + ('1' * 64)
        )
        self.assertNotIn('referenceContributorError', response)
        self.assertNotIn('contributorDigest', response)

    def test_reference_contributor_failure_never_blocks_rgb_publication(self) -> None:
        class FailingReferenceRenderer(AnchorFixtureRenderer):
            def render_anchor(self, **kwargs: object) -> AnchorRenderArtifact:
                artifact = super().render_anchor(**kwargs)
                return AnchorRenderArtifact(
                    image_png=artifact.image_png,
                    rgb_digest=artifact.rgb_digest,
                    reference_contributor_error=(
                        'rendererMassMismatch: contributor alpha diverged'
                    ),
                )

        self.state.register_scene_snapshot(self.snapshot())
        self.state.contributor_renderer = FailingReferenceRenderer()  # type: ignore[assignment]
        request = self.request_body()
        request['referenceContributor'] = True

        response = self.state.render_ai_select_anchor(request)

        self.assertEqual(response['status'], 'complete')
        self.assertIn('rgb', response)
        self.assertNotIn('referenceContributorDigest', response)
        self.assertEqual(
            response['referenceContributorError'],
            'rendererMassMismatch: contributor alpha diverged',
        )

    def test_explicit_retry_creates_a_new_attempt_that_actually_rerenders(self) -> None:
        self.state.register_scene_snapshot(self.snapshot())

        first = self.state.render_ai_select_anchor(self.request_body())
        replay = self.state.render_ai_select_anchor(self.request_body())
        retry_request = self.request_body()
        retry_request['renderAttemptId'] = 'attempt-2'
        retry = self.state.render_ai_select_anchor(retry_request)

        # The same attempt replays idempotently; the explicit Retry mints a
        # new attempt identity for the same CameraBinding and really reruns.
        self.assertEqual(replay, first)
        self.assertEqual(retry['renderAttemptId'], 'attempt-2')
        self.assertEqual(retry['cameraBinding'], first['cameraBinding'])
        self.assertEqual(len(self.renderer.calls), 2)

    def test_a_new_attempt_reruns_instead_of_replaying_a_cached_failure(self) -> None:
        class FlakyAnchorFixtureRenderer(AnchorFixtureRenderer):
            def __init__(self) -> None:
                super().__init__()
                self.invocations = 0

            def render_anchor(self, **kwargs: object) -> AnchorRenderArtifact:
                self.invocations += 1
                if self.invocations == 1:
                    raise MaskSessionError('rendererFailure', 'transient gsplat failure')
                return super().render_anchor(**kwargs)

        self.state.register_scene_snapshot(self.snapshot())
        renderer = FlakyAnchorFixtureRenderer()
        self.state.contributor_renderer = renderer  # type: ignore[assignment]

        with self.assertRaisesRegex(MaskSessionError, 'transient gsplat failure'):
            self.state.render_ai_select_anchor(self.request_body())
        with self.assertRaisesRegex(MaskSessionError, 'transient gsplat failure'):
            self.state.render_ai_select_anchor(self.request_body())
        # The cached failure replays for the same attempt without GPU work.
        self.assertEqual(renderer.invocations, 1)

        retry_request = self.request_body()
        retry_request['renderAttemptId'] = 'attempt-2'
        retry = self.state.render_ai_select_anchor(retry_request)

        self.assertEqual(retry['status'], 'complete')
        self.assertEqual(retry['renderAttemptId'], 'attempt-2')
        self.assertEqual(renderer.invocations, 2)


if __name__ == '__main__':
    unittest.main()

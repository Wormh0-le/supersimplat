from __future__ import annotations

from dataclasses import replace
import base64
import hashlib
from io import BytesIO
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from PIL import Image

from selection_service_companion.anchor_timing import AnchorServerTiming
from selection_service_companion.camera_binding import camera_binding_digest
from selection_service_companion.depth_moment_qualification import (
    QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
    DepthMomentExecutionEnvelope,
    DepthMomentInternalCapability,
)
from selection_service_companion.depth_moment_readout import (
    DepthMomentConsumerRegistration,
    DepthMomentReadoutCache,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import DepthMomentValidityPolicy
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
    DepthMomentRasterUnavailableError,
)
from selection_service_companion.evidence import ContributorSample
from selection_service_companion.gsplat_renderer import (
    GsplatContributorRenderer,
    GsplatProbe,
    GsplatRasterization,
    LockedGsplatBackend,
    MASS_CONSERVATION_ATOL,
    MASS_CONSERVATION_RTOL,
    TileGaussian,
    TypedAnchorRasterization,
    reconcile_boundary_contributors,
    validate_supported_snapshot,
)
from selection_service_companion.generated_views import (
    PlannedGeneratedViewCandidate,
    SeedRegion,
)
from selection_service_companion.masking import MaskSessionError, RegisteredFrame
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
)
from selection_service_companion.reference_gaussian_evidence import (
    ReferenceGaussianEvidenceError,
    default_reference_evidence_policy,
    typed_pixel_evidence_weights,
)
from selection_service_companion.reference_gaussian_evidence_aggregation import (
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
)
from selection_service_companion.state import CompanionState


def qualified_depth_moment_capability(
    policy: DepthMomentValidityPolicy,
) -> DepthMomentInternalCapability:
    return DepthMomentInternalCapability(
        status="ready",
        reason="test-qualified",
        qualification_id=QUALIFIED_DEPTH_MOMENT_CAPABILITY_ID,
        qualification_digest="sha256:" + ("9" * 64),
        policy=policy,
        envelope=DepthMomentExecutionEnvelope(
            compute_capabilities=("8.9",),
            max_width=4096,
            max_height=4096,
            max_pixels=4096 * 4096,
            max_render_gaussian_count=65536,
            max_evidence_gaussian_count=65536,
            max_intersection_count=1_000_000,
            max_concurrent_consumers=1,
        ),
        direct_evidence_abi_version=DIRECT_EVIDENCE_ABI_VERSION,
        direct_evidence_source_revision=DIRECT_EVIDENCE_SOURCE_REVISION,
        direct_evidence_runtime_build_id=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    )


def supported_snapshot() -> dict[str, object]:
    return {
        "protocolVersion": "1",
        "sceneId": "scene-1",
        "sceneVersion": "snapshot-v1",
        "gaussianCount": 2,
        "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
        "attributeSchema": (
            "mean:f32x3;rotation:f32x4;logScale:f32x3;"
            "logitOpacity:f32;dc:f32x3;sh:f32x0"
        ),
        "stableIdSchema": "uint32",
        "appearancePolicy": "effective-editor-dc-sh-bands-0",
        "renderConfiguration": {
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        "gaussians": [
            {
                "stableId": 41,
                "mean": [0.0, 0.0, 2.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "logScale": [-1.6, -1.6, -1.6],
                "logitOpacity": 0.0,
                "dc": [0.0, 0.0, 0.0],
                "sh": [],
            },
            {
                "stableId": 99,
                "mean": [0.2, 0.0, 2.5],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "logScale": [-1.6, -1.6, -1.6],
                "logitOpacity": -0.5,
                "dc": [0.0, 0.0, 0.0],
                "sh": [],
            },
        ],
    }


def png_bytes(width: int, height: int, value: int = 0) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(value, value, value)).save(
        output, format="PNG"
    )
    return output.getvalue()


def anchor_frame(
    *, width: int = 2, height: int = 2, image_value: int = 0
) -> RegisteredFrame:
    return RegisteredFrame(
        view_id="anchor-view",
        frame_digest="sha256:editor-anchor-rgb",
        width=width,
        height=height,
        image_png=png_bytes(width, height, image_value),
        source="anchor",
        camera={
            "model": "pinhole",
            "convention": "opencv-world-to-camera",
            "worldToCamera": [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            "intrinsics": [
                20.0, 0.0, width / 2,
                0.0, 20.0, height / 2,
                0.0, 0.0, 1.0,
            ],
            "nearPlane": 0.01,
            "farPlane": 100.0,
        },
    )


class StaticGsplatBackend:
    def __init__(self, rasterization: GsplatRasterization) -> None:
        self.rasterization = rasterization
        self.calls = 0
        self.probe_calls = 0

    def rasterize(self, *, snapshot, camera, width, height):
        del snapshot, camera, width, height
        self.calls += 1
        return self.rasterization

    def probe(self, *, snapshot, camera, width, height):
        del snapshot, camera, width, height
        self.probe_calls += 1
        return GsplatProbe(
            alpha=self.rasterization.alpha,
            contributor_ids=self.rasterization.contributor_ids,
            contributor_weights=self.rasterization.contributor_weights,
        )


class StaticTypedAnchorBackend:
    """Test-only backend that forbids the legacy Python contributor path."""

    def __init__(self) -> None:
        import torch

        self.calls = 0
        self.legacy_calls = 0
        self.reference_contributor_requests: list[bool] = []
        self.rasterization = TypedAnchorRasterization(
            service_rgb_digest="sha256:service-rgb",
            service_rgb_bytes=bytes(2 * 2 * 3),
            alpha=torch.tensor(((0.5, 0.0), (0.0, 0.25)), dtype=torch.float32),
            contributor_ids=torch.tensor(
                (((0, 1), (-1, -1)), ((-1, -1), (1, -1))),
                dtype=torch.int32,
            ),
            contributor_weights=torch.tensor(
                (((0.3, 0.2), (0.0, 0.0)), ((0.0, 0.0), (0.25, 0.0))),
                dtype=torch.float32,
            ),
            stable_ids=torch.tensor((41, 99), dtype=torch.int32),
        )

    def rasterize_anchor_typed(
        self,
        *,
        snapshot,
        camera,
        width,
        height,
        stable_ids,
        include_reference_contributor=False,
    ):
        del snapshot, camera, width, height, stable_ids
        self.calls += 1
        self.reference_contributor_requests.append(include_reference_contributor)
        return self.rasterization

    def rasterize(self, *, snapshot, camera, width, height):
        del snapshot, camera, width, height
        self.legacy_calls += 1
        raise AssertionError("Anchor publication must not use the legacy list path")

    def probe(self, *, snapshot, camera, width, height):
        del snapshot, camera, width, height
        raise AssertionError("Anchor publication does not probe")


def valid_rasterization() -> GsplatRasterization:
    return GsplatRasterization(
        service_rgb_digest="sha256:service-rgb",
        service_rgb_bytes=bytes(2 * 2 * 3),
        alpha=((0.5, 0.0), (0.0, 0.25)),
        contributor_ids=(((0, 1), (-1, -1)), ((-1, -1), (1, -1))),
        contributor_weights=(((0.3, 0.2), (0.0, 0.0)), ((0.0, 0.0), (0.25, 0.0))),
    )


class GsplatContributorRendererTests(unittest.TestCase):
    def test_planning_budget_counts_hidden_camera_candidates_not_the_anchor(self) -> None:
        renderer = GsplatContributorRenderer(backend=StaticGsplatBackend(valid_rasterization()))
        seed_region = SeedRegion(
            center=(0.0, 0.0, 2.0),
            radius=0.01,
            source="anchor_contributors",
            stable_ids=(41,),
        )

        plan = renderer.plan_views(
            scene_snapshot=supported_snapshot(),
            anchor_frame=anchor_frame(),
            seed_region=seed_region,
            initial_budget=2,
            replacement_budget=0,
            resolution=2,
        )

        self.assertEqual(len(plan.primary), 2)

    @staticmethod
    def _direction_from(camera: dict[str, object], target: tuple[float, float, float]) -> tuple[float, float, float]:
        matrix = [float(value) for value in camera["worldToCamera"]]  # type: ignore[arg-type]
        translation = (matrix[3], matrix[7], matrix[11])
        position = tuple(
            -sum(matrix[row * 4 + axis] * translation[row] for row in range(3))
            for axis in range(3)
        )
        vector = tuple(position[axis] - target[axis] for axis in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        return tuple(value / length for value in vector)  # type: ignore[return-value]

    @staticmethod
    def _angle_degrees(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
        cosine = sum(left[axis] * right[axis] for axis in range(3))
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    def test_planning_orbits_the_anchor_axis_for_a_pole_aligned_anchor(self) -> None:
        # The identity test camera sits on the world z axis of the Seed Region;
        # a world-longitude ring would collapse onto that pole and plan only
        # near-duplicate views. The anchor-relative orbit must still circle.
        renderer = GsplatContributorRenderer(backend=StaticGsplatBackend(valid_rasterization()))
        target = (0.0, 0.0, 2.0)
        seed_region = SeedRegion(
            center=target,
            radius=0.2,
            source="anchor_contributors",
            stable_ids=(41,),
        )

        plan = renderer.plan_views(
            scene_snapshot=supported_snapshot(),
            anchor_frame=anchor_frame(),
            seed_region=seed_region,
            initial_budget=10,
            replacement_budget=2,
            resolution=2,
        )

        base = (0.0, 0.0, -1.0)
        expected_ring = (45.0, 45.0, 90.0, 90.0, 135.0, 135.0, 180.0)
        ring = [candidate for candidate in plan.primary if candidate.category == "ring"]
        self.assertEqual(len(ring), len(expected_ring))
        for candidate, expected in zip(ring, expected_ring, strict=True):
            direction = self._direction_from(candidate.camera, target)
            self.assertAlmostEqual(
                self._angle_degrees(direction, base), expected, places=6
            )
        upper = [candidate for candidate in plan.primary if candidate.category == "upper"]
        self.assertEqual(len(upper), 3)
        for candidate, expected in zip(upper, (30.0, 90.0, 90.0), strict=True):
            direction = self._direction_from(candidate.camera, target)
            self.assertAlmostEqual(
                self._angle_degrees(direction, base), expected, places=6
            )
        self.assertEqual(len(plan.replacements), 2)
        for replacement, primary in zip(plan.replacements, plan.primary, strict=False):
            primary_direction = self._direction_from(primary.camera, target)
            replacement_direction = self._direction_from(replacement.camera, target)
            self.assertAlmostEqual(
                self._angle_degrees(replacement_direction, primary_direction),
                10.0,
                places=6,
            )

    def test_planning_preserves_the_level_anchor_world_orbit(self) -> None:
        # A level anchor must keep the historical world-z longitude orbit:
        # the anchor-relative formulation only changes degenerate anchors.
        renderer = GsplatContributorRenderer(backend=StaticGsplatBackend(valid_rasterization()))
        target = (0.0, 0.0, 0.0)
        seed_region = SeedRegion(
            center=target,
            radius=0.2,
            source="anchor_contributors",
            stable_ids=(41,),
        )
        level_anchor = RegisteredFrame(
            view_id="anchor-view",
            frame_digest="sha256:editor-anchor-rgb",
            width=2,
            height=2,
            image_png=png_bytes(2, 2),
            source="anchor",
            camera={
                "model": "pinhole",
                "convention": "opencv-world-to-camera",
                "worldToCamera": [
                    1.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, -1.0, 0.0,
                    0.0, 1.0, 0.0, 5.0,
                    0.0, 0.0, 0.0, 1.0,
                ],
                "intrinsics": [
                    20.0, 0.0, 1.0,
                    0.0, 20.0, 1.0,
                    0.0, 0.0, 1.0,
                ],
                "nearPlane": 0.01,
                "farPlane": 100.0,
            },
        )

        plan = renderer.plan_views(
            scene_snapshot=supported_snapshot(),
            anchor_frame=level_anchor,
            seed_region=seed_region,
            initial_budget=10,
            replacement_budget=0,
            resolution=2,
        )

        distance = 5.0
        expected_offsets = (
            (45.0, 0.0), (-45.0, 0.0), (90.0, 0.0), (-90.0, 0.0),
            (135.0, 0.0), (-135.0, 0.0), (180.0, 0.0),
            (0.0, 30.0), (90.0, 30.0), (-90.0, 30.0),
        )
        base_azimuth = math.radians(-90.0)
        for candidate, (azimuth_offset, elevation_offset) in zip(
            plan.primary, expected_offsets, strict=True
        ):
            azimuth = base_azimuth + math.radians(azimuth_offset)
            elevation = math.radians(elevation_offset)
            expected = (
                distance * math.cos(elevation) * math.cos(azimuth),
                distance * math.cos(elevation) * math.sin(azimuth),
                distance * math.sin(elevation),
            )
            direction = self._direction_from(candidate.camera, target)
            actual = tuple(value * distance for value in direction)
            for axis in range(3):
                self.assertAlmostEqual(actual[axis], expected[axis], places=9)

    def test_render_generated_records_angular_diagnostics_on_the_frame(self) -> None:
        renderer = GsplatContributorRenderer(backend=StaticGsplatBackend(valid_rasterization()))
        snapshot = supported_snapshot()
        seed_region = SeedRegion(
            center=(0.0, 0.0, 2.0),
            radius=0.01,
            source="anchor_contributors",
            stable_ids=(41,),
        )
        plan = renderer.plan_views(
            scene_snapshot=snapshot,
            anchor_frame=anchor_frame(),
            seed_region=seed_region,
            initial_budget=1,
            replacement_budget=0,
            resolution=2,
        )
        candidate = plan.primary[0]
        preflight = renderer.preflight(
            scene_snapshot=snapshot,
            candidate=candidate,
            seed_region=seed_region,
            resolution=2,
        )

        frame = renderer.render_generated(
            scene_snapshot=snapshot,
            candidate=candidate,
            preflight=preflight,
            resolution=2,
        )

        self.assertIsNotNone(frame.camera)
        assert frame.camera is not None
        self.assertEqual(frame.camera["azimuthDegrees"], candidate.azimuth_degrees)
        self.assertEqual(frame.camera["elevationDegrees"], candidate.elevation_degrees)

    def test_render_anchor_publishes_png_and_contributor_digests_from_one_rasterization(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            include_reference_contributor=True,
        )

        self.assertEqual(backend.calls, 1)
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )
        self.assertIsNotNone(artifact.contributor_digest)
        assert artifact.contributor_digest is not None
        self.assertRegex(artifact.contributor_digest, r'^sha256:[0-9a-f]{64}$')
        with Image.open(BytesIO(artifact.image_png)) as image:
            self.assertEqual(image.size, (frame.width, frame.height))

    def test_production_render_anchor_never_touches_the_reference_contributor(self) -> None:
        backend = StaticTypedAnchorBackend()
        backend.rasterization = replace(
            backend.rasterization,
            contributor_ids=None,
            contributor_weights=None,
            stable_ids=None,
        )
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
        )

        # The production preview neither requests nor publishes any complete
        # Contributor artifact; RGB alone decides readiness.
        self.assertEqual(backend.reference_contributor_requests, [False])
        self.assertIsNone(artifact.contributor_digest)
        self.assertIsNone(artifact.reference_contributor_error)
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )
        with Image.open(BytesIO(artifact.image_png)) as image:
            self.assertEqual(image.size, (frame.width, frame.height))

    def test_render_anchor_accepts_a_generated_view_identity(self) -> None:
        backend = StaticTypedAnchorBackend()
        backend.rasterization = replace(
            backend.rasterization,
            contributor_ids=None,
            contributor_weights=None,
            stable_ids=None,
        )
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='generated-00',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
        )

        # Generated Views render through the same locked authoritative path;
        # the view identity is a label, never a rasterization difference.
        self.assertEqual(backend.calls, 1)
        self.assertEqual(backend.reference_contributor_requests, [False])
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )
        with Image.open(BytesIO(artifact.image_png)) as image:
            self.assertEqual(image.size, (frame.width, frame.height))

    def test_reference_contributor_failure_stays_diagnostic_beside_valid_rgb(self) -> None:
        backend = StaticTypedAnchorBackend()
        backend.rasterization = replace(
            backend.rasterization,
            contributor_ids=None,
            contributor_weights=None,
            stable_ids=None,
            contributor_error=MaskSessionError(
                'rendererMassMismatch', 'contributor alpha diverged'
            ),
        )
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            include_reference_contributor=True,
        )

        self.assertEqual(backend.reference_contributor_requests, [True])
        self.assertIsNone(artifact.contributor_digest)
        self.assertEqual(
            artifact.reference_contributor_error,
            'rendererMassMismatch: contributor alpha diverged',
        )
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )

    def test_render_anchor_hashes_complete_typed_contributors_without_legacy_lists(self) -> None:
        backend = StaticTypedAnchorBackend()
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            include_reference_contributor=True,
        )

        # The format is deliberately independent of Python object layout:
        # fixed header, alpha f32, validity bytes, Stable IDs u32, weights f32.
        stream = b''.join((
            b'SSPAICTR',
            struct.pack('<IIII', 1, 2, 2, 2),
            struct.pack('<4f', 0.5, 0.0, 0.0, 0.25),
            bytes((1, 1, 0, 0, 0, 0, 1, 0)),
            struct.pack('<8I', 41, 99, 0, 0, 0, 0, 99, 0),
            struct.pack('<8f', 0.3, 0.2, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0),
        ))
        self.assertEqual(backend.calls, 1)
        self.assertEqual(backend.legacy_calls, 0)
        self.assertEqual(
            artifact.contributor_digest,
            f'sha256:{hashlib.sha256(stream).hexdigest()}',
        )

    def test_typed_anchor_records_renderer_png_and_digest_timing_separately(self) -> None:
        backend = StaticTypedAnchorBackend()
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None
        timing = AnchorServerTiming()

        renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            timing=timing,
            include_reference_contributor=True,
        )

        self.assertGreater(timing.duration_ms('gsplat'), 0)
        self.assertGreater(timing.duration_ms('png'), 0)
        self.assertGreater(timing.duration_ms('contributor-digest'), 0)
        self.assertEqual(timing.duration_ms('working-set'), 0)
        self.assertEqual(timing.duration_ms('gpu-queue'), 0)

    def test_typed_anchor_keeps_uint32_max_stable_id_distinct_from_padding(self) -> None:
        import torch

        backend = StaticTypedAnchorBackend()
        backend.rasterization = replace(
            backend.rasterization,
            stable_ids=torch.tensor((-1, 99), dtype=torch.int32),
        )
        renderer = GsplatContributorRenderer(backend=backend)
        frame = anchor_frame()
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            include_reference_contributor=True,
        )

        stream = b''.join((
            b'SSPAICTR',
            struct.pack('<IIII', 1, 2, 2, 2),
            struct.pack('<4f', 0.5, 0.0, 0.0, 0.25),
            bytes((1, 1, 0, 0, 0, 0, 1, 0)),
            struct.pack('<8I', 0xffffffff, 99, 0, 0, 0, 0, 99, 0),
            struct.pack('<8f', 0.3, 0.2, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0),
        ))
        self.assertEqual(
            artifact.contributor_digest,
            f'sha256:{hashlib.sha256(stream).hexdigest()}',
        )

    def test_plans_and_preflights_cameras_before_coherent_generated_rendering(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        renderer = GsplatContributorRenderer(backend=backend)
        snapshot = supported_snapshot()
        seed_region = SeedRegion(
            center=(0.0, 0.0, 2.0),
            radius=0.01,
            source="anchor_contributors",
            stable_ids=(41,),
        )

        plan = renderer.plan_views(
            scene_snapshot=snapshot,
            anchor_frame=anchor_frame(),
            seed_region=seed_region,
            initial_budget=16,
            replacement_budget=8,
            resolution=2,
        )

        self.assertEqual(backend.calls, 0)
        self.assertGreater(len(plan.primary), 0)
        candidate = plan.primary[0]
        preflight = renderer.preflight(
            scene_snapshot=snapshot,
            candidate=candidate,
            seed_region=seed_region,
            resolution=2,
        )
        self.assertTrue(preflight.accepted, preflight.diagnostics)
        accepted_attempt = preflight.diagnostics["attempts"][-1]
        self.assertIn("projectedCenterX", accepted_attempt)
        self.assertIn("projectedCenterY", accepted_attempt)
        self.assertIn("projectedRadius", accepted_attempt)
        self.assertEqual(backend.calls, 0)
        self.assertEqual(backend.probe_calls, 1)

        frame = renderer.render_generated(
            scene_snapshot=snapshot,
            candidate=candidate,
            preflight=preflight,
            resolution=2,
        )
        rendered = renderer.render(scene_snapshot=snapshot, frame=frame)

        self.assertEqual(backend.calls, 1)
        self.assertEqual(rendered.service_rgb_digest, "sha256:service-rgb")
        self.assertEqual(rendered.rgb_frame_digest, frame.frame_digest)
        self.assertEqual((frame.width, frame.height), (2, 2))

    def test_preflight_rejects_non_finite_camera_without_rasterizing(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        renderer = GsplatContributorRenderer(backend=backend)
        candidate = PlannedGeneratedViewCandidate(
            view_id="bad-camera",
            camera={"worldToCamera": [float("nan")]},
            category="ring",
        )

        outcome = renderer.preflight(
            scene_snapshot=supported_snapshot(),
            candidate=candidate,
            seed_region=SeedRegion((0.0, 0.0, 2.0), 0.25, "fixture", (41,)),
            resolution=2,
        )

        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.diagnostics["reason"], "non_finite")
        self.assertEqual(backend.calls, 0)
        self.assertEqual(backend.probe_calls, 0)

    def test_preflight_rejects_unsafe_geometry_and_probe_outcomes(self) -> None:
        snapshot = supported_snapshot()
        base_camera = anchor_frame().camera
        assert base_camera is not None

        def outcome(camera, seed_region, rasterization=valid_rasterization()):
            renderer = GsplatContributorRenderer(
                backend=StaticGsplatBackend(rasterization)
            )
            return renderer.preflight(
                scene_snapshot=snapshot,
                candidate=PlannedGeneratedViewCandidate(
                    view_id="candidate", camera=camera, category="ring"
                ),
                seed_region=seed_region,
                resolution=2,
            )

        inside_camera = dict(base_camera)
        inside_camera["worldToCamera"] = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, -2.0,
            0.0, 0.0, 0.0, 1.0,
        ]
        cases = {
            "inside_geometry": outcome(
                inside_camera, SeedRegion((0.0, 0.0, 2.0), 0.01, "fixture", (41,))
            ),
            "near_plane_cut": outcome(
                base_camera, SeedRegion((0.0, 0.0, 0.02), 0.02, "fixture", ())
            ),
            "clipped": outcome(
                base_camera, SeedRegion((10.0, 0.0, 2.0), 0.01, "fixture", ())
            ),
            "seed_unsupported": outcome(
                base_camera,
                SeedRegion((0.0, 0.0, 2.0), 0.01, "fixture", (41,)),
                replace(
                    valid_rasterization(),
                    contributor_ids=(((1, -1), (-1, -1)), ((-1, -1), (1, -1))),
                    contributor_weights=(((0.5, 0.0), (0.0, 0.0)), ((0.0, 0.0), (0.25, 0.0))),
                ),
            ),
            "low_transmittance": outcome(
                base_camera,
                SeedRegion((0.0, 0.0, 2.0), 0.01, "fixture", (41,)),
                replace(
                    valid_rasterization(),
                    contributor_weights=(((0.001, 0.499), (0.0, 0.0)), ((0.0, 0.0), (0.25, 0.0))),
                ),
            ),
        }

        for reason, preflight in cases.items():
            with self.subTest(reason=reason):
                self.assertFalse(preflight.accepted)
                self.assertEqual(preflight.diagnostics["reason"], reason)

    def test_companion_rejects_unsupported_v1_semantics_before_caching(self) -> None:
        snapshot = supported_snapshot()
        snapshot["coordinateConvention"] = "left-handed"
        with tempfile.TemporaryDirectory() as directory:
            state = CompanionState(Path(directory) / "state")

            with self.assertRaisesRegex(ValueError, "coordinate"):
                state.register_scene_snapshot(snapshot)

            self.assertIsNone(state.scene_snapshot("scene-1", "snapshot-v1"))

    def test_maps_every_valid_tensor_row_to_stable_ids_and_preserves_mass(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        rendered = GsplatContributorRenderer(backend=backend).render(
            scene_snapshot=supported_snapshot(),
            frame=anchor_frame(),
        )

        self.assertEqual(backend.calls, 1)
        self.assertEqual(rendered.rgb_frame_digest, "sha256:editor-anchor-rgb")
        self.assertEqual(rendered.service_rgb_digest, "sha256:service-rgb")
        self.assertEqual(rendered.anchor_parity, "normal")
        self.assertEqual(rendered.support_bounds, (0, 0, 2, 2))
        self.assertEqual(
            rendered.contributors,
            (
                ContributorSample(stable_id=41, x_px=0, y_px=0, mass=0.3),
                ContributorSample(stable_id=99, x_px=0, y_px=0, mass=0.2),
                ContributorSample(stable_id=99, x_px=1, y_px=1, mass=0.25),
            ),
        )
        self.assertLessEqual(rendered.mass_conservation_max_error, MASS_CONSERVATION_ATOL)

    def test_rejects_mass_mismatch_without_attribution_fallback(self) -> None:
        backend = StaticGsplatBackend(
            replace(
                valid_rasterization(),
                contributor_weights=(
                    ((0.3, 0.1), (0.0, 0.0)),
                    ((0.0, 0.0), (0.25, 0.0)),
                ),
            )
        )

        with self.assertRaises(MaskSessionError) as raised:
            GsplatContributorRenderer(backend=backend).render(
                scene_snapshot=supported_snapshot(),
                frame=anchor_frame(),
            )

        self.assertEqual(raised.exception.code, "rendererMassMismatch")

    def test_rejects_invalid_contributor_ids_without_visible_or_nearest_fallback(self) -> None:
        backend = StaticGsplatBackend(
            replace(
                valid_rasterization(),
                contributor_ids=(((0, 2), (-1, -1)), ((-1, -1), (1, -1))),
            )
        )

        with self.assertRaises(MaskSessionError) as raised:
            GsplatContributorRenderer(backend=backend).render(
                scene_snapshot=supported_snapshot(),
                frame=anchor_frame(),
            )

        self.assertEqual(raised.exception.code, "rendererInvalidContributor")

    def test_rejects_unsupported_snapshot_before_calling_gsplat(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        snapshot = supported_snapshot()
        snapshot["protocolVersion"] = "2"

        with self.assertRaisesRegex(ValueError, "protocol version 1"):
            GsplatContributorRenderer(backend=backend).render(
                scene_snapshot=snapshot,
                frame=anchor_frame(),
            )

        self.assertEqual(backend.calls, 0)

    def test_rejects_unknown_render_configuration_before_calling_gsplat(self) -> None:
        backend = StaticGsplatBackend(valid_rasterization())
        snapshot = supported_snapshot()
        snapshot["renderConfiguration"]["version"] = "unknown-rgb-v2"

        with self.assertRaisesRegex(ValueError, "render configuration version"):
            GsplatContributorRenderer(backend=backend).render(
                scene_snapshot=snapshot,
                frame=anchor_frame(),
            )

        self.assertEqual(backend.calls, 0)

    def test_classifies_major_anchor_rgb_displacement_as_severe(self) -> None:
        rendered = GsplatContributorRenderer(
            backend=StaticGsplatBackend(valid_rasterization())
        ).render(
            scene_snapshot=supported_snapshot(),
            frame=anchor_frame(image_value=255),
        )

        self.assertEqual(rendered.anchor_parity, "severe")

    def test_rejects_absent_contributor_support(self) -> None:
        backend = StaticGsplatBackend(
            GsplatRasterization(
                service_rgb_digest="sha256:service-rgb",
                service_rgb_bytes=bytes(2 * 2 * 3),
                alpha=((0.0, 0.0), (0.0, 0.0)),
                contributor_ids=(((), ()), ((), ())),
                contributor_weights=(((), ()), ((), ())),
            )
        )

        with self.assertRaises(MaskSessionError) as raised:
            GsplatContributorRenderer(backend=backend).render(
                scene_snapshot=supported_snapshot(),
                frame=anchor_frame(),
            )

        self.assertEqual(raised.exception.code, "rendererUnavailable")


class BoundaryContributorReconciliationTests(unittest.TestCase):
    """Issue #30: repair gsplat's fp32 validity/termination boundary flips.

    The RGB and contributor CUDA kernels evaluate the same per-Gaussian alpha
    in separate translation units. For a Gaussian whose exact alpha sits within
    float32 rounding of gsplat's 1/255 validity cut (or whose transmittance
    update sits at the 1e-4 termination cut), the kernels can disagree on one
    contributor. The reconciler must align the contributor stream with the RGB
    rasterization's own alpha and fail closed on anything else.
    """

    @staticmethod
    def gaussian(tensor_id: int, *, sigma: float, opacity: float = 0.96) -> TileGaussian:
        # Pixel center (8.5, 8.5); dx = 1 and dy = 0 make sigma exactly the
        # conic evaluation 0.5 * conic_a * dx**2.
        return TileGaussian(
            tensor_id=tensor_id,
            mean_x=9.5,
            mean_y=8.5,
            conic_a=2.0 * sigma,
            conic_b=0.0,
            conic_c=1.0,
            opacity=opacity,
        )

    @staticmethod
    def sigma_for_alpha(alpha: float, opacity: float = 0.96) -> float:
        return math.log(opacity / alpha)

    @staticmethod
    def replay_contributor_chain(
        gaussians: list[TileGaussian], *, force_exclude: set[int] | None = None
    ) -> tuple[list[int], list[float], float]:
        """Independent float64 replay of the shared kernel semantics."""
        excluded = force_exclude or set()
        transmittance = 1.0
        ids: list[int] = []
        weights: list[float] = []
        for gaussian in gaussians:
            if gaussian.tensor_id in excluded:
                continue
            dx = gaussian.mean_x - 8.5
            dy = gaussian.mean_y - 8.5
            sigma = (
                0.5 * (gaussian.conic_a * dx * dx + gaussian.conic_c * dy * dy)
                + gaussian.conic_b * dx * dy
            )
            alpha = min(0.99, gaussian.opacity * math.exp(-sigma))
            if sigma < 0.0 or alpha < 1.0 / 255.0:
                continue
            next_transmittance = transmittance * (1.0 - alpha)
            if next_transmittance <= 1e-4:
                break
            ids.append(gaussian.tensor_id)
            weights.append(alpha * transmittance)
            transmittance = next_transmittance
        return ids, weights, 1.0 - transmittance

    def front_gaussians(self) -> list[TileGaussian]:
        return [
            self.gaussian(1, sigma=self.sigma_for_alpha(0.5)),
            self.gaussian(2, sigma=self.sigma_for_alpha(0.3)),
            self.gaussian(3, sigma=self.sigma_for_alpha(0.2)),
        ]

    def test_drops_spurious_contributor_below_validity_cut(self) -> None:
        # The exact issue #30 signature: exact alpha 1.78e-9 below 1/255, but
        # the contributor kernel's fp32 evaluation accepted the Gaussian.
        borderline = self.gaussian(4, sigma=5.50044204404077)
        gaussians = [*self.front_gaussians(), borderline]
        _, accepted_weights, _ = self.replay_contributor_chain(gaussians)
        borderline_weight = borderline.opacity * math.exp(-5.50044204404077) * 0.28
        kernel_ids = [1, 2, 3, 4]
        kernel_weights = [*accepted_weights, borderline_weight]
        _, _, raster_alpha = self.replay_contributor_chain(gaussians, force_exclude={4})

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha + borderline_weight,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, weights, alpha = repaired
        self.assertEqual(ids, (1, 2, 3))
        self.assertAlmostEqual(alpha, raster_alpha, delta=1e-6)
        self.assertAlmostEqual(sum(weights), raster_alpha, delta=1e-6)

    def test_restores_contributor_dropped_below_validity_cut(self) -> None:
        alpha_target = 1.0 / 255.0 + 1.5e-9
        borderline = self.gaussian(4, sigma=self.sigma_for_alpha(alpha_target))
        gaussians = [*self.front_gaussians(), borderline]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians, force_exclude={4}
        )
        _, _, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, weights, alpha = repaired
        self.assertEqual(ids, (1, 2, 3, 4))
        self.assertAlmostEqual(alpha, raster_alpha, delta=1e-6)
        self.assertAlmostEqual(sum(weights), raster_alpha, delta=1e-6)

    def test_restores_mid_chain_contributor_and_shifts_tail_weights(self) -> None:
        alpha_target = 1.0 / 255.0 + 1.5e-9
        borderline = self.gaussian(4, sigma=self.sigma_for_alpha(alpha_target))
        front = self.front_gaussians()
        gaussians = [front[0], borderline, front[1], front[2]]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians, force_exclude={4}
        )
        expected_ids, expected_weights, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, weights, alpha = repaired
        self.assertEqual(ids, tuple(expected_ids))
        self.assertAlmostEqual(alpha, raster_alpha, delta=1e-6)
        for actual, expected in zip(weights, expected_weights, strict=True):
            self.assertAlmostEqual(actual, expected, delta=1e-6)

    def test_drops_spurious_contributor_above_termination_cut(self) -> None:
        gaussians = [
            self.gaussian(1, sigma=self.sigma_for_alpha(0.9)),
            self.gaussian(2, sigma=0.001, opacity=1.0),
            self.gaussian(3, sigma=self.sigma_for_alpha(0.8999995)),
        ]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians
        )
        _, _, raster_alpha = self.replay_contributor_chain(gaussians, force_exclude={3})

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, _, alpha = repaired
        self.assertEqual(ids, (1, 2))
        self.assertAlmostEqual(alpha, raster_alpha, delta=1e-6)

    def test_rejects_a_synthetic_chain_below_the_termination_cut(self) -> None:
        # The locked kernels exclude the Gaussian that drops T to the cut;
        # a replay must not force it into a synthetic chain and continue.
        gaussians = [
            self.gaussian(1, sigma=self.sigma_for_alpha(0.9)),
            self.gaussian(2, sigma=0.001, opacity=1.0),
            self.gaussian(3, sigma=self.sigma_for_alpha(0.9000005)),
        ]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians
        )

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=0.9999000005,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_restores_rgb_inclusion_just_above_the_termination_cut(self) -> None:
        # The RGB translation unit can retain the boundary Gaussian with a
        # remaining transmittance a few float32 ulps above the cut while the
        # contributor kernel rounds the same update just below it. The next
        # valid Gaussian proves the RGB chain must stop immediately afterward.
        front = [
            self.gaussian(index + 1, sigma=self.sigma_for_alpha(0.89))
            for index in range(4)
        ]
        incoming_transmittance = 0.11**4
        scalar_next_transmittance = 1e-4 - 2e-10
        boundary_alpha = 1.0 - (
            scalar_next_transmittance / incoming_transmittance
        )
        boundary = self.gaussian(
            5, sigma=self.sigma_for_alpha(boundary_alpha)
        )
        tail = self.gaussian(6, sigma=self.sigma_for_alpha(0.1))
        gaussians = [*front, boundary, tail]
        kernel_ids, kernel_weights, kernel_alpha = (
            self.replay_contributor_chain(gaussians)
        )
        raster_alpha = 1.0 - (1e-4 + 1.6e-8)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, weights, alpha = repaired
        self.assertEqual(ids, (1, 2, 3, 4, 5))
        self.assertAlmostEqual(alpha, raster_alpha, delta=1e-8)
        self.assertLessEqual(
            abs(sum(weights) - raster_alpha),
            MASS_CONSERVATION_ATOL
            + MASS_CONSERVATION_RTOL * abs(raster_alpha),
        )

    def test_rejects_unexplained_missing_contributor(self) -> None:
        gaussians = self.front_gaussians()
        _, _, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=0.57,
            kernel_ids=[1, 3],
            kernel_weights=[0.5, 0.07],
        )

        self.assertIsNone(repaired)

    def test_rejects_mismatch_no_variant_explains(self) -> None:
        borderline = self.gaussian(4, sigma=5.50044204404077)
        gaussians = [*self.front_gaussians(), borderline]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians
        )

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=0.9,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_too_many_boundary_candidates(self) -> None:
        alpha_target = 1.0 / 255.0 - 1.5e-9
        gaussians = [
            self.gaussian(1, sigma=self.sigma_for_alpha(0.5)),
            *(
                self.gaussian(10 + index, sigma=self.sigma_for_alpha(alpha_target))
                for index in range(5)
            ),
        ]
        kernel_ids = [1, 10, 11, 12, 13, 14]
        kernel_weights = [0.5]
        transmittance = 0.5
        for _ in range(5):
            kernel_weights.append(alpha_target * transmittance)
            transmittance *= 1.0 - alpha_target
        _, _, raster_alpha = self.replay_contributor_chain(
            gaussians, force_exclude={10, 11, 12, 13, 14}
        )

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=sum(kernel_weights),
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_an_unflipped_kernel_chain(self) -> None:
        # The kernel stream is itself the unique matching variant: no boundary
        # flip is proven, so the mismatch stays unexplained and fails closed.
        alpha_target = 1.0 / 255.0 - 1.5e-9
        borderline = self.gaussian(4, sigma=self.sigma_for_alpha(alpha_target))
        gaussians = [*self.front_gaussians(), borderline]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians
        )

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=kernel_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_non_finite_kernel_weights(self) -> None:
        gaussians = self.front_gaussians()
        _, _, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha,
            kernel_ids=[1, 2, 3],
            kernel_weights=[0.5, float("nan"), 0.07],
        )

        self.assertIsNone(repaired)

    def test_rejects_kernel_weights_inconsistent_with_kernel_alpha(self) -> None:
        gaussians = self.front_gaussians()
        kernel_ids, kernel_weights, _ = self.replay_contributor_chain(gaussians)
        _, _, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=0.5,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_a_weight_defect_ahead_of_the_flip(self) -> None:
        # A 1e-3 error in the first contributor's weight is upstream of the
        # flipped borderline Gaussian, so it cannot be a boundary effect.
        borderline = self.gaussian(4, sigma=5.50044204404077)
        gaussians = [*self.front_gaussians(), borderline]
        _, accepted_weights, _ = self.replay_contributor_chain(gaussians)
        borderline_weight = borderline.opacity * math.exp(-5.50044204404077) * 0.28
        kernel_weights = [*accepted_weights, borderline_weight]
        kernel_weights[0] += 1e-3
        _, _, raster_alpha = self.replay_contributor_chain(gaussians, force_exclude={4})

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha + borderline_weight + 1e-3,
            kernel_ids=[1, 2, 3, 4],
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_a_balanced_tail_weight_defect_after_a_flip(self) -> None:
        # A real mid-chain flip legitimately changes tail weights, but it must
        # not authorize an unrelated pair of offsetting tail-weight defects.
        alpha_target = 1.0 / 255.0 + 1.5e-9
        borderline = self.gaussian(4, sigma=self.sigma_for_alpha(alpha_target))
        front = self.front_gaussians()
        gaussians = [front[0], borderline, front[1], front[2]]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians, force_exclude={4}
        )
        kernel_weights[1] += 1e-4
        kernel_weights[2] -= 1e-4
        _, _, raster_alpha = self.replay_contributor_chain(gaussians)

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_rejects_a_prefix_weight_defect_beyond_f32_proof(self) -> None:
        # Aggregate mass tolerance is too broad to establish that an untouched
        # prefix contributor came from the same rasterization.
        borderline = self.gaussian(4, sigma=5.50044204404077)
        gaussians = [*self.front_gaussians(), borderline]
        _, accepted_weights, _ = self.replay_contributor_chain(gaussians)
        borderline_weight = borderline.opacity * math.exp(-5.50044204404077) * 0.28
        kernel_weights = [*accepted_weights, borderline_weight]
        kernel_weights[0] += 1e-6
        _, _, raster_alpha = self.replay_contributor_chain(gaussians, force_exclude={4})

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha + borderline_weight + 1e-6,
            kernel_ids=[1, 2, 3, 4],
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)

    def test_tolerates_kernel_weight_noise_within_evaluation_tolerance(self) -> None:
        borderline = self.gaussian(4, sigma=5.50044204404077)
        gaussians = [*self.front_gaussians(), borderline]
        _, accepted_weights, _ = self.replay_contributor_chain(gaussians)
        borderline_weight = borderline.opacity * math.exp(-5.50044204404077) * 0.28
        kernel_weights = [*accepted_weights, borderline_weight]
        kernel_weights[0] += 1e-7
        _, _, raster_alpha = self.replay_contributor_chain(gaussians, force_exclude={4})

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha + borderline_weight + 1e-7,
            kernel_ids=[1, 2, 3, 4],
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, _, _ = repaired
        self.assertEqual(ids, (1, 2, 3))

    def test_tolerates_bounded_float32_noise_accumulated_through_a_prefix(self) -> None:
        # A contributor weight includes the product of every preceding
        # transmittance update. The locked CUDA kernel can therefore differ
        # from the scalar replay by more than the single-operation ULP budget
        # while still remaining inside the cumulative float32 error bound.
        front = [
            self.gaussian(index + 1, sigma=self.sigma_for_alpha(0.5))
            for index in range(7)
        ]
        borderline = self.gaussian(8, sigma=5.50044204404077)
        gaussians = [*front, borderline]
        _, accepted_weights, _ = self.replay_contributor_chain(gaussians)
        borderline_weight = (
            borderline.opacity * math.exp(-5.50044204404077) * (0.5**7)
        )
        kernel_weights = [*accepted_weights, borderline_weight]
        accumulated_noise = 3.5e-8
        kernel_weights[6] += accumulated_noise
        _, _, raster_alpha = self.replay_contributor_chain(
            gaussians, force_exclude={8}
        )

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=raster_alpha + borderline_weight + accumulated_noise,
            kernel_ids=[*range(1, 9)],
            kernel_weights=kernel_weights,
        )

        self.assertIsNotNone(repaired)
        ids, _, _ = repaired
        self.assertEqual(ids, tuple(range(1, 8)))

    def test_rejects_multiple_matching_variants(self) -> None:
        # Two identical borderline Gaussians deep in the chain: excluding
        # either one, or both, stays within match tolerance of the raster
        # alpha, so no unique variant exists and the pixel fails closed.
        front = [
            self.gaussian(index + 1, sigma=self.sigma_for_alpha(0.89))
            for index in range(4)
        ]
        alpha_target = 1.0 / 255.0 + 1.5e-9
        borderline = [
            self.gaussian(5, sigma=self.sigma_for_alpha(alpha_target)),
            self.gaussian(6, sigma=self.sigma_for_alpha(alpha_target)),
        ]
        gaussians = [*front, *borderline]
        kernel_ids, kernel_weights, kernel_alpha = self.replay_contributor_chain(
            gaussians
        )
        raster_alpha = 1.0 - 0.11**4

        repaired = reconcile_boundary_contributors(
            ordered_gaussians=gaussians,
            pixel_x=8,
            pixel_y=8,
            raster_alpha=raster_alpha,
            kernel_alpha=kernel_alpha,
            kernel_ids=kernel_ids,
            kernel_weights=kernel_weights,
        )

        self.assertIsNone(repaired)


class LockedGsplatGpuGoldenTests(unittest.TestCase):
    def require_cuda(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("locked renderer extra is not installed")
        if not torch.cuda.is_available():
            self.skipTest("CUDA is unavailable")

    def test_complete_contributor_mass_matches_same_rasterization_alpha(self) -> None:
        self.require_cuda()

        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        rendered = renderer.render(
            scene_snapshot=supported_snapshot(),
            frame=anchor_frame(width=8, height=8),
        )

        self.assertGreater(len(rendered.contributors), 0)
        self.assertEqual({sample.stable_id for sample in rendered.contributors}, {41, 99})
        self.assertLessEqual(rendered.mass_conservation_max_error, MASS_CONSERVATION_ATOL)
        self.assertIsNotNone(renderer.last_peak_vram_bytes)
        self.assertGreater(renderer.last_peak_vram_bytes or 0, 0)

    def test_production_anchor_render_never_invokes_the_contributor_kernels(self) -> None:
        self.require_cuda()

        import gsplat.cuda._wrapper as gsplat_wrapper

        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        frame = anchor_frame(width=8, height=8)
        assert frame.camera is not None

        def forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError(
                'production Anchor RGB must not run the reference Contributor kernels'
            )

        with (
            mock.patch.object(
                gsplat_wrapper,
                'rasterize_num_contributing_gaussians',
                forbidden,
            ),
            mock.patch.object(
                gsplat_wrapper,
                'rasterize_contributing_gaussian_ids',
                forbidden,
            ),
        ):
            artifact = renderer.render_anchor(
                scene_snapshot=supported_snapshot(),
                view_id='anchor-view',
                camera=frame.camera,
                width=frame.width,
                height=frame.height,
            )

        self.assertIsNone(artifact.contributor_digest)
        self.assertIsNone(artifact.reference_contributor_error)
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )
        with Image.open(BytesIO(artifact.image_png)) as image:
            self.assertEqual(image.size, (frame.width, frame.height))

    def test_direct_evidence_matches_reference_without_allocating_contributor(self) -> None:
        self.require_cuda()

        width = height = 8
        binding = {
            "revision": 1,
            "cameraToWorld": [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            "projection": {
                "model": "pinhole",
                "fx": 20.0,
                "fy": 20.0,
                "cx": width / 2,
                "cy": height / 2,
                "width": width,
                "height": height,
                "near": 0.01,
                "far": 100.0,
            },
            "conventionVersion": "opencv-camera-to-world/v1",
        }
        frame = anchor_frame(width=width, height=height)
        assert frame.camera is not None
        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        scene = supported_snapshot()
        scene["sceneVersion"] = "sha256:" + ("d" * 64)
        scene["gaussians"][0]["logScale"] = [0.0, 0.0, 0.0]
        scene["gaussianCount"] = 3
        scene["gaussians"].append({
            "stableId": 123,
            "mean": [100.0, 100.0, 2.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "logScale": [-1.6, -1.6, -1.6],
            "logitOpacity": 0.0,
            "dc": [0.0, 0.0, 0.0],
            "sh": [],
        })
        rgb = renderer.render_anchor(
            scene_snapshot=scene,
            view_id="anchor-view",
            camera=frame.camera,
            width=width,
            height=height,
        )
        mask_bits = bytes([0xFF] * ((width * height + 7) // 8))
        mask = {
            "encoding": "bitset-lsb-v1",
            "width": width,
            "height": height,
            "data": base64.b64encode(mask_bits).decode("ascii"),
            "digest": f"sha256:{hashlib.sha256(mask_bits).hexdigest()}",
        }
        dependency = {
            "splatId": "scene-1",
            "renderStateToken": "render-v1",
            "geometryToken": "geometry-v1",
            "gaussianIdentityToken": "gaussians-v1",
            "worldTransformToken": "transform-v1",
        }
        evidence_working_set = create_evidence_working_set({
            "targetSplatId": "scene-1",
            "coreTargetStableIds": [41, 99, 123],
            "contextStableGaussianIds": [],
        })
        policy = default_reference_evidence_policy()
        direct_input = {
            "requestBinding": {
                "targetContextId": "context-1",
                "contextRevision": 1,
                "dependencyToken": dependency,
            },
            "targetSplatId": "scene-1",
            "view": {
                "viewId": "anchor-view",
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": camera_binding_digest(binding),
                "rgbDigest": rgb.rgb_digest,
                "stableMaskDigest": mask["digest"],
            },
            "evidencePolicyDigest": policy["evidencePolicyDigest"],
            "renderWorkingSet": {
                "targetSplatId": "scene-1",
                "dependencyToken": dependency,
                "cameraBindingDigest": camera_binding_digest(binding),
                "renderWorkingSetToken": scene["sceneVersion"],
                "stableGaussianIds": [41, 99, 123],
                "completeness": "complete",
            },
            "evidenceWorkingSet": evidence_working_set,
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendKind": "production-direct",
            "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        }

        moment_policy = DepthMomentValidityPolicy(
            policy_id="depth-moment-minimum-m0/renderer-integration-test-v1",
            minimum_m0=0.01,
        )
        moment_capability = qualified_depth_moment_capability(moment_policy)
        moment_cache = DepthMomentReadoutCache()
        direct = renderer.compute_direct_evidence(
            admission_input=direct_input,
            stable_mask_artifact=mask,
            policy=policy,
            scene_snapshot=scene,
            camera_binding=binding,
            target_stable_ids=[41, 99, 123],
            depth_moment_consumer=DepthMomentConsumerRegistration(
                cache=moment_cache,
                capability=moment_capability,
            ),
        )
        admission_result = admit_gaussian_evidence(direct_input)
        self.assertEqual(admission_result["status"], "admitted")
        admission = admission_result["admission"]
        assert isinstance(admission, dict)
        moment_identity = create_depth_moment_readout_identity(
            admission,
            render_stable_ids_by_projected_row=validate_supported_snapshot(scene),
            capability=moment_capability,
            width=width,
            height=height,
        )
        moment_lookup = moment_cache.lookup(moment_identity)
        self.assertEqual(moment_lookup.status, "available")
        assert moment_lookup.readout is not None
        self.assertEqual(
            tuple(moment_lookup.readout.raw_depth_moments.shape),
            (height, width, 3),
        )
        self.assertEqual(
            moment_lookup.readout.telemetry.depth_moment_buffer_bytes,
            height * width * 3 * 4,
        )
        self.assertGreater(
            moment_lookup.readout.telemetry.owned_tensor_buffer_bytes,
            moment_lookup.readout.telemetry.depth_moment_buffer_bytes,
        )
        self.assertGreater(
            moment_lookup.readout.telemetry.peak_vram_bytes,
            0,
        )
        self.assertEqual(
            moment_lookup.readout.telemetry.projected_gaussian_count,
            3,
        )
        self.assertEqual(
            moment_lookup.readout.telemetry.evidence_gaussian_count,
            3,
        )
        self.assertGreater(
            moment_lookup.readout.telemetry.intersection_count,
            0,
        )
        self.assertNotIn("depthMoments", direct)
        self.assertNotIn("cwed", direct)

        rasterize_direct = renderer.backend.rasterize_direct_evidence_typed

        def without_depth_moments(**kwargs: object):
            rasterized = rasterize_direct(**kwargs)
            return replace(
                rasterized,
                depth_moments=None,
                telemetry=replace(
                    rasterized.telemetry,
                    depth_moment_buffer_bytes=0,
                ),
            )

        unavailable_cache = DepthMomentReadoutCache()
        with mock.patch.object(
            renderer.backend,
            "rasterize_direct_evidence_typed",
            side_effect=without_depth_moments,
        ):
            without_depth = renderer.compute_direct_evidence(
                admission_input=direct_input,
                stable_mask_artifact=mask,
                policy=policy,
                scene_snapshot=scene,
                camera_binding=binding,
                target_stable_ids=[41, 99, 123],
                depth_moment_consumer=DepthMomentConsumerRegistration(
                    cache=unavailable_cache,
                    capability=moment_capability,
                ),
            )
        for channel in (
            "positiveMass",
            "negativeMass",
            "visibleMass",
            "boundaryMass",
        ):
            for observed, expected in zip(
                without_depth[channel], direct[channel], strict=True
            ):
                self.assertAlmostEqual(observed, expected, delta=2e-5)
        self.assertEqual(
            unavailable_cache.lookup(moment_identity).status,
            "unavailable",
        )
        self.assertNotIn("depthMoments", without_depth)
        self.assertNotIn("cwed", without_depth)

        fallback_failures = (
            DepthMomentRasterUnavailableError(
                "depth-moment-capacity-unavailable"
            ),
            DepthMomentRasterUnavailableError(
                "depth-moment-runtime-unavailable"
            ),
        )
        for moment_error in fallback_failures:
            expected_reason = moment_error.reason
            with self.subTest(moment_error=expected_reason):
                fallback_calls: list[bool] = []

                def fail_only_with_moments(**kwargs: object):
                    enabled = bool(kwargs["depth_moments_enabled"])
                    fallback_calls.append(enabled)
                    if enabled:
                        raise moment_error
                    return rasterize_direct(**kwargs)

                fallback_cache = DepthMomentReadoutCache()
                fallback_consumer = DepthMomentConsumerRegistration(
                    cache=fallback_cache,
                    capability=moment_capability,
                )
                with mock.patch.object(
                    renderer.backend,
                    "rasterize_direct_evidence_typed",
                    side_effect=fail_only_with_moments,
                ):
                    fallback_artifact = renderer.compute_direct_evidence(
                        admission_input=direct_input,
                        stable_mask_artifact=mask,
                        policy=policy,
                        scene_snapshot=scene,
                        camera_binding=binding,
                        target_stable_ids=[41, 99, 123],
                        depth_moment_consumer=fallback_consumer,
                    )

                self.assertEqual(fallback_calls, [True, False])
                for channel in (
                    "positiveMass",
                    "negativeMass",
                    "visibleMass",
                    "boundaryMass",
                ):
                    for observed, expected in zip(
                        fallback_artifact[channel], direct[channel], strict=True
                    ):
                        self.assertAlmostEqual(observed, expected, delta=2e-5)
                self.assertEqual(fallback_consumer.result.status, "unavailable")
                self.assertEqual(fallback_consumer.result.reason, expected_reason)
                fallback_lookup = fallback_cache.lookup(moment_identity)
                self.assertEqual(fallback_lookup.status, "unavailable")
                self.assertEqual(fallback_lookup.reason, expected_reason)
                self.assertIsNone(fallback_lookup.readout)

        failed_calls: list[bool] = []

        def fail_every_direct_evidence_render(**kwargs: object):
            failed_calls.append(bool(kwargs["depth_moments_enabled"]))
            raise RuntimeError("injected production raster failure")

        failed_consumer = DepthMomentConsumerRegistration(
            cache=DepthMomentReadoutCache(),
            capability=moment_capability,
        )
        with mock.patch.object(
            renderer.backend,
            "rasterize_direct_evidence_typed",
            side_effect=fail_every_direct_evidence_render,
        ):
            with self.assertRaises(ReferenceGaussianEvidenceError) as raised:
                renderer.compute_direct_evidence(
                    admission_input=direct_input,
                    stable_mask_artifact=mask,
                    policy=policy,
                    scene_snapshot=scene,
                    camera_binding=binding,
                    target_stable_ids=[41, 99, 123],
                    depth_moment_consumer=failed_consumer,
                )
        self.assertEqual(raised.exception.code, "directEvidenceRenderFailed")
        self.assertEqual(failed_calls, [True])
        release_probe = DepthMomentConsumerRegistration(
            cache=DepthMomentReadoutCache(),
            capability=moment_capability,
        )
        self.assertTrue(
            release_probe.prepare_execution(
                admission=admission,
                render_stable_ids_by_projected_row=(41, 99, 123),
                evidence_gaussian_count=3,
                width=width,
                height=height,
            )
        )
        release_probe.cancel()

        reference_input = {
            **direct_input,
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendKind": "reference-contributor",
            "evidenceBackendId": "complete-contributor/reference-v1",
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        }
        reference = renderer.compute_reference_evidence(
            admission_input=reference_input,
            stable_mask_artifact=mask,
            policy=policy,
            scene_snapshot=scene,
            camera_binding=binding,
        )

        for channel in ("positiveMass", "negativeMass", "visibleMass", "boundaryMass"):
            for observed, expected in zip(direct[channel], reference[channel], strict=True):
                self.assertAlmostEqual(observed, expected, delta=2e-5)
        self.assertNotEqual(direct["artifactDigest"], reference["artifactDigest"])
        self.assertEqual(direct["evidenceBackendKind"], "production-direct")
        self.assertIsNotNone(renderer.last_direct_evidence_telemetry)
        assert renderer.last_direct_evidence_telemetry is not None
        self.assertEqual(
            renderer.last_direct_evidence_telemetry["evidenceBufferBytes"],
            3 * 4 * 4,
        )
        repeats = [direct]
        for _ in range(4):
            repeats.append(renderer.compute_direct_evidence(
                admission_input=direct_input,
                stable_mask_artifact=mask,
                policy=policy,
                scene_snapshot=scene,
                camera_binding=binding,
                target_stable_ids=[41, 99, 123],
            ))
        for channel in ("positiveMass", "negativeMass", "visibleMass", "boundaryMass"):
            for stable_index in range(3):
                values = [artifact[channel][stable_index] for artifact in repeats]
                self.assertLessEqual(max(values) - min(values), 2e-5)

        def classify(current_input, artifact):
            return aggregate_reference_gaussian_evidence(
                {
                    "requestBinding": current_input["requestBinding"],
                    "targetSplatId": "scene-1",
                    "classificationUniverseStableGaussianIds": [41, 99, 123],
                    "classificationScopeStableGaussianIds": [41, 99, 123],
                    "evidenceWorkingSet": evidence_working_set,
                    "views": [{"currentInput": current_input, "artifact": artifact}],
                },
                default_reference_aggregation_policy(),
            )

        reference_classification = classify(reference_input, reference)
        self.assertIn(123, reference_classification["uncertainStableGaussianIds"])
        for artifact in repeats:
            production_classification = classify(direct_input, artifact)
            for key in (
                "selectedStableGaussianIds",
                "rejectedStableGaussianIds",
                "uncertainStableGaussianIds",
            ):
                self.assertEqual(
                    production_classification[key], reference_classification[key]
                )

        mixed_bits = bytearray((width * height + 7) // 8)
        for y_px in range(2, 6):
            for x_px in range(2, 6):
                pixel = y_px * width + x_px
                mixed_bits[pixel // 8] |= 1 << (pixel % 8)
        mixed_mask = {
            "encoding": "bitset-lsb-v1",
            "width": width,
            "height": height,
            "data": base64.b64encode(mixed_bits).decode("ascii"),
            "digest": f"sha256:{hashlib.sha256(mixed_bits).hexdigest()}",
        }
        mixed_direct_input = {
            **direct_input,
            "view": {
                **direct_input["view"],
                "stableMaskDigest": mixed_mask["digest"],
            },
        }
        mixed_reference_input = {
            **mixed_direct_input,
            "evidenceBackendKind": "reference-contributor",
            "evidenceBackendId": "complete-contributor/reference-v1",
        }
        mixed_direct = renderer.compute_direct_evidence(
            admission_input=mixed_direct_input,
            stable_mask_artifact=mixed_mask,
            policy=policy,
            scene_snapshot=scene,
            camera_binding=binding,
            target_stable_ids=[41, 99, 123],
        )
        mixed_reference = renderer.compute_reference_evidence(
            admission_input=mixed_reference_input,
            stable_mask_artifact=mixed_mask,
            policy=policy,
            scene_snapshot=scene,
            camera_binding=binding,
        )
        for channel in (
            "positiveMass",
            "negativeMass",
            "visibleMass",
            "boundaryMass",
        ):
            for observed, expected in zip(
                mixed_direct[channel], mixed_reference[channel], strict=True
            ):
                self.assertAlmostEqual(observed, expected, delta=2e-5)
        mixed_reference_classification = classify(
            mixed_reference_input, mixed_reference
        )
        mixed_direct_classification = classify(mixed_direct_input, mixed_direct)
        self.assertIn(
            41,
            mixed_reference_classification["uncertainStableGaussianIds"],
            mixed_reference_classification,
        )
        for key in (
            "selectedStableGaussianIds",
            "rejectedStableGaussianIds",
            "uncertainStableGaussianIds",
        ):
            self.assertEqual(
                mixed_direct_classification[key],
                mixed_reference_classification[key],
            )

    def test_anchor_uses_the_typed_gpu_contributor_publication_path(self) -> None:
        self.require_cuda()

        class TypedOnlyLockedBackend(LockedGsplatBackend):
            def rasterize(self, *, snapshot, camera, width, height):
                del snapshot, camera, width, height
                raise AssertionError('Anchor must not materialize legacy contributor lists')

        renderer = GsplatContributorRenderer(backend=TypedOnlyLockedBackend())
        frame = anchor_frame(width=8, height=8)
        assert frame.camera is not None

        artifact = renderer.render_anchor(
            scene_snapshot=supported_snapshot(),
            view_id='anchor-view',
            camera=frame.camera,
            width=frame.width,
            height=frame.height,
            include_reference_contributor=True,
        )

        self.assertIsNotNone(artifact.contributor_digest)
        assert artifact.contributor_digest is not None
        self.assertRegex(artifact.contributor_digest, r'^sha256:[0-9a-f]{64}$')
        self.assertIsNotNone(renderer.last_peak_vram_bytes)
        self.assertGreater(renderer.last_peak_vram_bytes or 0, 0)

    def test_normal_1008_generated_view_records_measured_peak_vram(self) -> None:
        self.require_cuda()

        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        snapshot = supported_snapshot()
        seed_region = SeedRegion(
            center=(0.0, 0.0, 2.0),
            radius=0.2,
            source="anchor_contributors",
            stable_ids=(41,),
        )
        plan = renderer.plan_views(
            scene_snapshot=snapshot,
            anchor_frame=anchor_frame(width=1008, height=1008),
            seed_region=seed_region,
            initial_budget=2,
            replacement_budget=0,
            resolution=1008,
        )
        candidate = plan.primary[0]
        preflight = renderer.preflight(
            scene_snapshot=snapshot,
            candidate=candidate,
            seed_region=seed_region,
            resolution=1008,
        )
        self.assertTrue(preflight.accepted, preflight.diagnostics)

        frame = renderer.render_generated(
            scene_snapshot=snapshot,
            candidate=candidate,
            preflight=preflight,
            resolution=1008,
        )
        rendered = renderer.render(scene_snapshot=snapshot, frame=frame)

        self.assertEqual((frame.width, frame.height), (1008, 1008))
        self.assertGreater(len(rendered.contributors), 0)
        self.assertIsNotNone(renderer.last_peak_vram_bytes)
        self.assertGreater(renderer.last_peak_vram_bytes or 0, 0)

    def test_controlled_overlap_1008_anchor_conserves_contributor_mass(self) -> None:
        self.require_cuda()
        fixture = (
            Path(__file__).resolve().parents[2]
            / "docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap.ply"
        )
        if not fixture.exists():
            self.skipTest("controlled-overlap fixture is unavailable")
        from selection_service_companion.controlled_overlap_benchmark import (
            _anchor_camera,
            build_controlled_overlap_snapshot,
        )

        snapshot = build_controlled_overlap_snapshot(fixture)
        rasterized = LockedGsplatBackend().rasterize(
            snapshot=snapshot,
            camera=_anchor_camera(1008),
            width=1008,
            height=1008,
        )

        # Issue #30: at pixel (794, 664) the contributor kernels accepted
        # tensor row 2516 although its exact alpha (0.003921566848368366) sits
        # 1.78e-9 below gsplat's 1/255 validity cut. The reconciled stream
        # must match the RGB rasterization's own accepted set.
        pixel_ids = [tensor_id for tensor_id in rasterized.contributor_ids[664][794] if tensor_id >= 0]
        self.assertEqual(len(pixel_ids), 33)
        self.assertNotIn(2516, pixel_ids)
        alpha = rasterized.alpha[664][794]
        mass = sum(
            weight
            for tensor_id, weight in zip(
                rasterized.contributor_ids[664][794],
                rasterized.contributor_weights[664][794],
                strict=True,
            )
            if tensor_id >= 0
        )
        self.assertLessEqual(
            abs(mass - alpha),
            MASS_CONSERVATION_ATOL + MASS_CONSERVATION_RTOL * abs(alpha),
        )

    def test_controlled_overlap_direct_evidence_does_not_reconcile_contributors(self) -> None:
        self.require_cuda()
        import torch

        fixture = (
            Path(__file__).resolve().parents[2]
            / "docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap.ply"
        )
        if not fixture.exists():
            self.skipTest("controlled-overlap fixture is unavailable")
        from selection_service_companion.controlled_overlap_benchmark import (
            _anchor_camera,
            build_controlled_overlap_snapshot,
        )

        snapshot = build_controlled_overlap_snapshot(fixture)
        stable_ids = [int(value) for value in validate_supported_snapshot(snapshot)]
        sorted_stable_ids = sorted(stable_ids)
        mask_bits = bytearray((1008 * 1008 + 7) // 8)
        mismatch_pixel = 664 * 1008 + 794
        mask_bits[mismatch_pixel // 8] |= 1 << (mismatch_pixel % 8)
        mask = {
            "encoding": "bitset-lsb-v1",
            "width": 1008,
            "height": 1008,
            "data": base64.b64encode(mask_bits).decode("ascii"),
            "digest": f"sha256:{hashlib.sha256(mask_bits).hexdigest()}",
        }
        policy = default_reference_evidence_policy()
        pixel_weights = typed_pixel_evidence_weights(mask, policy, torch)
        backend = LockedGsplatBackend()

        with mock.patch.object(
            backend,
            "_reference_contributor_tensors",
            side_effect=AssertionError(
                "Direct Evidence must not reconcile complete Contributors"
            ),
        ):
            direct = backend.rasterize_direct_evidence_typed(
                snapshot=snapshot,
                camera=_anchor_camera(1008),
                width=1008,
                height=1008,
                render_stable_ids=stable_ids,
                evidence_stable_ids=sorted_stable_ids,
                target_stable_ids=sorted_stable_ids,
                pixel_weights=pixel_weights,
            )

        self.assertEqual(direct.boundary_contact_stable_gaussian_ids, ())
        self.assertTrue(bool(torch.isfinite(direct.positive_mass).all().item()))
        self.assertTrue(bool(torch.isfinite(direct.visible_mass).all().item()))
        self.assertEqual(
            direct.telemetry.evidence_buffer_bytes,
            len(stable_ids) * 4 * 4,
        )


if __name__ == "__main__":
    unittest.main()

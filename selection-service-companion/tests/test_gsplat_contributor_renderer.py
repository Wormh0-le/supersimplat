from __future__ import annotations

from dataclasses import replace
import hashlib
from io import BytesIO
import math
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image

from selection_service_companion.anchor_timing import AnchorServerTiming
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
)
from selection_service_companion.generated_views import (
    PlannedGeneratedViewCandidate,
    SeedRegion,
)
from selection_service_companion.masking import MaskSessionError, RegisteredFrame
from selection_service_companion.state import CompanionState


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

    def rasterize_anchor_typed(self, *, snapshot, camera, width, height, stable_ids):
        del snapshot, camera, width, height, stable_ids
        self.calls += 1
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
        )

        self.assertEqual(backend.calls, 1)
        self.assertEqual(
            artifact.rgb_digest,
            f'sha256:{hashlib.sha256(artifact.image_png).hexdigest()}',
        )
        self.assertRegex(artifact.contributor_digest, r'^sha256:[0-9a-f]{64}$')
        with Image.open(BytesIO(artifact.image_png)) as image:
            self.assertEqual(image.size, (frame.width, frame.height))

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
        )

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


if __name__ == "__main__":
    unittest.main()

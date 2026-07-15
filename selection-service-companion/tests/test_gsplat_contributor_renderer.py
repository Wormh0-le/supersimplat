from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from selection_service_companion.evidence import ContributorSample
from selection_service_companion.gsplat_renderer import (
    GsplatContributorRenderer,
    GsplatProbe,
    GsplatRasterization,
    LockedGsplatBackend,
    MASS_CONSERVATION_ATOL,
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


def valid_rasterization() -> GsplatRasterization:
    return GsplatRasterization(
        service_rgb_digest="sha256:service-rgb",
        service_rgb_bytes=bytes(2 * 2 * 3),
        alpha=((0.5, 0.0), (0.0, 0.25)),
        contributor_ids=(((0, 1), (-1, -1)), ((-1, -1), (1, -1))),
        contributor_weights=(((0.3, 0.2), (0.0, 0.0)), ((0.0, 0.0), (0.25, 0.0))),
    )


class GsplatContributorRendererTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

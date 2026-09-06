from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from PIL import Image

from selection_service_companion.camera_binding import camera_binding_digest
from selection_service_companion.reference_gaussian_evidence import (
    ReferenceGaussianEvidenceError,
    compare_available_reference_artifacts,
    compute_reference_contributor_evidence,
    default_reference_evidence_policy,
    derive_pixel_evidence_weights,
)
from selection_service_companion import reference_gaussian_evidence
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
    is_gaussian_evidence_artifact,
)
from selection_service_companion.gsplat_renderer import (
    GsplatContributorRenderer,
    GsplatRasterization,
    LockedGsplatBackend,
    REFERENCE_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    REFERENCE_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.masking import MaskSessionError
from selection_service_companion.renderer_runtime import (
    RendererRuntimeStatus,
    StaticRendererRuntime,
)


def mask_artifact(
    width: int, height: int, foreground: set[tuple[int, int]]
) -> dict[str, object]:
    bits = bytearray((width * height + 7) // 8)
    for x_px, y_px in foreground:
        pixel_index = y_px * width + x_px
        bits[pixel_index // 8] |= 1 << (pixel_index % 8)
    return {
        "encoding": "bitset-lsb-v1",
        "width": width,
        "height": height,
        "data": base64.b64encode(bits).decode("ascii"),
        "digest": f"sha256:{hashlib.sha256(bits).hexdigest()}",
    }


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def policy_digest(policy: dict[str, object]) -> str:
    payload = {
        key: value for key, value in policy.items() if key != "evidencePolicyDigest"
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def dependency() -> dict[str, object]:
    return {
        "splatId": "editor-splat:1",
        "renderStateToken": "render-v1",
        "geometryToken": "geometry-v1",
        "gaussianIdentityToken": "gaussians-v1",
        "worldTransformToken": "transform-v1",
    }


def admission_input(
    mask: dict[str, object],
    policy: dict[str, object],
) -> dict[str, object]:
    return {
        "requestBinding": {
            "targetContextId": "ai-target-context-1",
            "contextRevision": 3,
            "dependencyToken": dependency(),
        },
        "targetSplatId": "editor-splat:1",
        "view": {
            "viewId": "view-1",
            "renderStatus": "ready",
            "participation": "included",
            "cameraBindingDigest": digest("a"),
            "rgbDigest": digest("b"),
            "stableMaskDigest": mask["digest"],
        },
        "evidencePolicyDigest": policy["evidencePolicyDigest"],
        "renderWorkingSet": {
            "targetSplatId": "editor-splat:1",
            "dependencyToken": dependency(),
            "cameraBindingDigest": digest("a"),
            "renderWorkingSetToken": digest("d"),
            "stableGaussianIds": [5, 9, 11, 13, 42],
            "completeness": "complete",
        },
        "evidenceWorkingSet": create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": [5, 11, 13],
                "contextStableGaussianIds": [9],
            }
        ),
        "rasterImplementationId": "gsplat-reference-rgb/v1",
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": "complete-contributor/reference-v1",
        "runtimeBuildId": "locked-runtime-build-1",
    }


def contributor_raster(
    width: int,
    height: int,
    samples: dict[tuple[int, int], list[tuple[int, float]]],
) -> dict[str, object]:
    contributor_ids: list[list[list[int]]] = []
    contributor_weights: list[list[list[float]]] = []
    alpha: list[list[float | int]] = []
    for y_px in range(height):
        id_row: list[list[int]] = []
        weight_row: list[list[float]] = []
        alpha_row: list[float | int] = []
        for x_px in range(width):
            pixel_samples = samples.get((x_px, y_px), [])
            id_row.append([row_id for row_id, _ in pixel_samples])
            weight_row.append([weight for _, weight in pixel_samples])
            alpha_row.append(
                sum(weight for row_id, weight in pixel_samples if row_id >= 0)
            )
        contributor_ids.append(id_row)
        contributor_weights.append(weight_row)
        alpha.append(alpha_row)
    return {
        "width": width,
        "height": height,
        "rgbDigest": digest("b"),
        "stableGaussianIdsByTensorRow": [42, 9, 5, 11, 13],
        "alpha": alpha,
        "contributorIds": contributor_ids,
        "contributorWeights": contributor_weights,
        "rasterImplementationId": "gsplat-reference-rgb/v1",
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": "complete-contributor/reference-v1",
        "runtimeBuildId": "locked-runtime-build-1",
    }


def supported_snapshot(stable_ids: list[int]) -> dict[str, object]:
    return {
        "protocolVersion": "1",
        "sceneId": "scene-1",
        "sceneVersion": digest("d"),
        "gaussianCount": len(stable_ids),
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
                "stableId": stable_id,
                "mean": [float(index) * 0.01, 0.0, 2.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "logScale": [-1.6, -1.6, -1.6],
                "logitOpacity": 0.0,
                "dc": [0.0, 0.0, 0.0],
                "sh": [],
            }
            for index, stable_id in enumerate(stable_ids)
        ],
    }


def camera(width: int, height: int) -> dict[str, object]:
    return {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
        "intrinsics": [
            20.0,
            0.0,
            width / 2,
            0.0,
            20.0,
            height / 2,
            0.0,
            0.0,
            1.0,
        ],
        "nearPlane": 0.01,
        "farPlane": 100.0,
    }


def camera_binding(width: int, height: int) -> dict[str, object]:
    return {
        "revision": 1,
        "cameraToWorld": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
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


def locked_admission_input(
    mask: dict[str, object],
    policy: dict[str, object],
    binding: dict[str, object],
    rgb_digest: str,
) -> dict[str, object]:
    result = admission_input(mask, policy)
    binding_digest = camera_binding_digest(binding)
    result["rasterImplementationId"] = (
        REFERENCE_EVIDENCE_RASTER_IMPLEMENTATION_ID
    )
    result["runtimeBuildId"] = REFERENCE_EVIDENCE_RUNTIME_BUILD_ID
    result["view"] = {
        **result["view"],
        "cameraBindingDigest": binding_digest,
        "rgbDigest": rgb_digest,
    }
    result["renderWorkingSet"] = {
        **result["renderWorkingSet"],
        "cameraBindingDigest": binding_digest,
    }
    return result


def png_digest(width: int, height: int, rgb_bytes: bytes) -> str:
    output = BytesIO()
    Image.frombytes("RGB", (width, height), rgb_bytes).save(output, format="PNG")
    return f"sha256:{hashlib.sha256(output.getvalue()).hexdigest()}"


class StaticReferenceBackend:
    def __init__(self, rasterization: GsplatRasterization) -> None:
        self.rasterization = rasterization
        self.calls = 0

    def rasterize(self, *, snapshot, camera, width, height):
        del snapshot, camera, width, height
        self.calls += 1
        return self.rasterization


class ReferenceGaussianEvidenceTests(unittest.TestCase):
    def test_typed_mask_regions_match_the_scalar_reference_at_edges_and_holes(
        self,
    ) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch is unavailable")
        policy = default_reference_evidence_policy()
        cases = (
            (5, 5, {(0, 0)}),
            (7, 6, {(6, 5), (3, 2)}),
            (
                9,
                9,
                {
                    (x_px, y_px)
                    for y_px in range(1, 8)
                    for x_px in range(1, 8)
                    if (x_px, y_px) != (4, 4)
                },
            ),
        )
        for width, height, foreground in cases:
            with self.subTest(width=width, height=height, foreground=foreground):
                mask = mask_artifact(width, height, foreground)
                scalar = derive_pixel_evidence_weights(mask, policy)
                typed_width, typed_height, channels = (
                    reference_gaussian_evidence._typed_pixel_evidence_weights(
                        mask,
                        policy,
                        torch,
                    )
                )
                self.assertEqual((typed_width, typed_height), (width, height))
                for channel, attribute in zip(
                    channels,
                    ("positive", "negative", "visible", "boundary"),
                    strict=True,
                ):
                    self.assertEqual(
                        channel.tolist(),
                        [getattr(value, attribute) for value in scalar.values],
                    )

    def test_typed_contributor_accumulation_matches_the_reference_lists(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch is unavailable")
        policy = default_reference_evidence_policy()
        mask = mask_artifact(
            9,
            9,
            {(x_px, y_px) for y_px in range(3, 6) for x_px in range(3, 6)},
        )
        admission = admission_input(mask, policy)
        samples = {
            (4, 4): [(2, 0.4), (0, 0.4), (3, 0.2)],
            (1, 4): [(1, 0.5), (3, 0.3)],
            (3, 3): [(3, 0.2)],
        }
        list_artifact = compute_reference_contributor_evidence(
            admission,
            mask,
            contributor_raster(9, 9, samples),
            policy,
        )
        ids = torch.full((9, 9, 3), -1, dtype=torch.int32)
        contributions = torch.zeros((9, 9, 3), dtype=torch.float32)
        alpha = torch.zeros((9, 9), dtype=torch.float32)
        for (x_px, y_px), pixel_samples in samples.items():
            for index, (row_id, weight) in enumerate(pixel_samples):
                ids[y_px, x_px, index] = row_id
                contributions[y_px, x_px, index] = weight
                alpha[y_px, x_px] += weight

        typed_artifact = (
            reference_gaussian_evidence.compute_typed_reference_contributor_evidence(
                admission,
                mask,
                {
                    "width": 9,
                    "height": 9,
                    "rgbDigest": digest("b"),
                    "stableGaussianIdsByTensorRow": torch.tensor(
                        [42, 9, 5, 11, 13], dtype=torch.int64
                    ),
                    "alpha": alpha,
                    "contributorIds": ids,
                    "contributorWeights": contributions,
                    "rasterImplementationId": "gsplat-reference-rgb/v1",
                    "evidenceBackendKind": "reference-contributor",
                    "evidenceBackendId": "complete-contributor/reference-v1",
                    "runtimeBuildId": "locked-runtime-build-1",
                },
                policy,
            )
        )

        for channel in (
            "positiveMass",
            "negativeMass",
            "visibleMass",
            "boundaryMass",
        ):
            for typed, listed in zip(
                typed_artifact[channel], list_artifact[channel], strict=True
            ):
                self.assertAlmostEqual(typed, listed, places=7)

    def test_policy_explicitly_separates_positive_boundary_local_negative_and_far_neutral(
        self,
    ) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(
            11,
            11,
            {(x_px, y_px) for y_px in range(4, 7) for x_px in range(4, 7)},
        )

        weights = derive_pixel_evidence_weights(mask, policy)

        self.assertNotEqual(
            policy["positiveWeightPolicyVersion"],
            policy["negativeWeightPolicyVersion"],
        )
        self.assertNotEqual(
            policy["negativeWeightPolicyVersion"],
            policy["visibleWeightPolicyVersion"],
        )
        self.assertEqual(weights.at(5, 5).region, "strong-positive-interior")
        self.assertEqual(weights.at(5, 5).positive, 1.0)
        self.assertEqual(weights.at(4, 4).region, "boundary-ignore-band")
        self.assertEqual(weights.at(4, 4).positive, 0.25)
        self.assertEqual(weights.at(3, 5).region, "boundary-ignore-band")
        self.assertEqual(weights.at(3, 5).negative, 0.0)
        self.assertEqual(weights.at(2, 5).region, "local-negative-context-ring")
        self.assertEqual(weights.at(2, 5).negative, 1.0)
        self.assertEqual(weights.at(0, 0).region, "far-neutral-region")
        self.assertEqual(weights.at(0, 0).visible, 0.0)
        boundary = weights.at(4, 4)
        self.assertNotEqual(boundary.positive + boundary.negative, boundary.visible)

        invalid_far_negative = {
            **policy,
            "farNeutralNegativeWeight": 1.0,
        }
        invalid_far_negative["evidencePolicyDigest"] = policy_digest(
            invalid_far_negative
        )
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "far region must remain neutral",
        ):
            derive_pixel_evidence_weights(mask, invalid_far_negative)

    def test_contributor_weights_accumulate_raw_pnv_by_stable_id_without_writing_occluders(
        self,
    ) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(
            9,
            9,
            {(x_px, y_px) for y_px in range(3, 6) for x_px in range(3, 6)},
        )
        raster = contributor_raster(
            9,
            9,
            {
                (4, 4): [(2, 0.4), (0, 0.4), (3, 0.2)],
                (1, 4): [(1, 0.5), (3, 0.3)],
                (3, 3): [(3, 0.2)],
            },
        )

        artifact = compute_reference_contributor_evidence(
            admission_input(mask, policy),
            mask,
            raster,
            policy,
        )

        self.assertTrue(is_gaussian_evidence_artifact(artifact))
        self.assertEqual(artifact["stableGaussianIds"], [5, 9, 11, 13])
        self.assertEqual(artifact["positiveMass"], [0.4, 0.0, 0.25, 0.0])
        self.assertEqual(artifact["negativeMass"], [0.0, 0.5, 0.3, 0.0])
        self.assertEqual(artifact["visibleMass"], [0.4, 0.5, 0.7, 0.0])
        self.assertEqual(artifact["boundaryMass"], [0.0, 0.0, 0.2, 0.0])
        self.assertNotIn(42, artifact["stableGaussianIds"])

        replay = compute_reference_contributor_evidence(
            admission_input(mask, policy),
            mask,
            raster,
            policy,
        )
        self.assertEqual(replay, artifact)

    def test_available_reference_backends_report_discrepancies_without_retuning_thresholds(
        self,
    ) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(1, 1, {(0, 0)})
        contributor_input = admission_input(mask, policy)
        contributor_admission = admit_gaussian_evidence(contributor_input)
        self.assertEqual(contributor_admission["status"], "admitted")
        contributor = create_gaussian_evidence_artifact(
            contributor_admission["admission"],
            {
                "positiveMass": [0.0, 1.0, 2.0, 4.0],
                "negativeMass": [0.0, 0.5, 0.0, 0.0],
                "visibleMass": [0.0, 1.0, 2.0, 4.0],
                "boundaryMass": [0.0, 0.0, 0.25, 0.0],
            },
        )
        autograd_input = {
            **contributor_input,
            "evidenceBackendKind": "reference-autograd",
            "evidenceBackendId": "stock-gsplat-autograd/reference-v1",
        }
        autograd_admission = admit_gaussian_evidence(autograd_input)
        self.assertEqual(autograd_admission["status"], "admitted")
        autograd = create_gaussian_evidence_artifact(
            autograd_admission["admission"],
            {
                "positiveMass": [0.1, 0.9995, 1.0, 4.0],
                "negativeMass": [0.0, 0.4, 0.0, 0.0],
                "visibleMass": [0.1, 0.9995, 1.0, 4.0],
                "boundaryMass": [0.0, 0.0, 0.2, 0.0],
            },
        )

        report = compare_available_reference_artifacts(
            [contributor, autograd],
            thresholds={"positiveMass": [1.0]},
            threshold_near_absolute_tolerance=0.001,
        )

        self.assertEqual(
            report["availableBackendKinds"],
            [
                "reference-autograd",
                "reference-contributor",
            ],
        )
        self.assertEqual(len(report["comparisons"]), 1)
        positive = report["comparisons"][0]["channels"]["positiveMass"]
        self.assertEqual(positive["maxAbsoluteError"], 1.0)
        self.assertEqual(positive["p95AbsoluteError"], 1.0)
        self.assertEqual(positive["p99AbsoluteError"], 1.0)
        self.assertEqual(positive["maxRelativeError"], 1.0)
        self.assertEqual(positive["supportDifferenceStableGaussianIds"], [5])
        self.assertEqual(positive["thresholdNearDifferenceStableGaussianIds"], [9])
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "at least one trusted reference backend",
        ):
            compare_available_reference_artifacts([])

    def test_incomplete_or_non_finite_contributor_output_fails_before_replacing_an_artifact(
        self,
    ) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(1, 1, {(0, 0)})
        current = compute_reference_contributor_evidence(
            admission_input(mask, policy),
            mask,
            contributor_raster(1, 1, {(0, 0): [(2, 0.5)]}),
            policy,
        )
        incomplete = contributor_raster(1, 1, {(0, 0): [(2, 0.5)]})
        incomplete["contributorWeights"] = []
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "dimensions are incomplete",
        ):
            compute_reference_contributor_evidence(
                admission_input(mask, policy),
                mask,
                incomplete,
                policy,
            )
        non_finite = contributor_raster(
            1,
            1,
            {(0, 0): [(2, 10**10000)]},
        )
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "raster alpha is invalid",
        ):
            compute_reference_contributor_evidence(
                admission_input(mask, policy),
                mask,
                non_finite,
                policy,
            )
        mass_mismatch = contributor_raster(1, 1, {(0, 0): [(2, 0.5)]})
        mass_mismatch["alpha"] = [[0.25]]
        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "mass does not match raster alpha",
        ):
            compute_reference_contributor_evidence(
                admission_input(mask, policy),
                mask,
                mass_mismatch,
                policy,
            )
        self.assertTrue(is_gaussian_evidence_artifact(current))
        self.assertEqual(current["positiveMass"], [0.125, 0.0, 0.0, 0.0])

    def test_reference_adapter_rejects_an_injected_backend_claiming_locked_identity(
        self,
    ) -> None:
        width = 9
        height = 9
        policy = default_reference_evidence_policy()
        mask = mask_artifact(
            width,
            height,
            {(x_px, y_px) for y_px in range(3, 6) for x_px in range(3, 6)},
        )
        dense = contributor_raster(
            width,
            height,
            {
                (4, 4): [(2, 0.4), (0, 0.6)],
                (1, 4): [(1, 0.5)],
            },
        )
        rgb_bytes = bytes(width * height * 3)
        alpha = [[0.0] * width for _ in range(height)]
        alpha[4][4] = 1.0
        alpha[4][1] = 0.5
        backend = StaticReferenceBackend(
            GsplatRasterization(
                service_rgb_digest=digest("f"),
                service_rgb_bytes=rgb_bytes,
                alpha=alpha,
                contributor_ids=dense["contributorIds"],
                contributor_weights=dense["contributorWeights"],
            )
        )
        renderer = GsplatContributorRenderer(backend=backend)
        binding = camera_binding(width, height)
        admitted_input = locked_admission_input(
            mask, policy, binding, png_digest(width, height, rgb_bytes)
        )

        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "backend identity is incompatible",
        ):
            renderer.compute_reference_evidence(
                admission_input=admitted_input,
                stable_mask_artifact=mask,
                policy=policy,
                scene_snapshot=supported_snapshot([42, 9, 5, 11, 13]),
                camera_binding=binding,
            )

        self.assertEqual(backend.calls, 0)

    def test_reference_adapter_rejects_camera_mismatch_before_rasterization(
        self,
    ) -> None:
        width = 1
        height = 1
        policy = default_reference_evidence_policy()
        mask = mask_artifact(width, height, {(0, 0)})
        binding = camera_binding(width, height)
        admitted_input = locked_admission_input(mask, policy, binding, digest("b"))
        different_binding = camera_binding(width, height)
        different_binding["revision"] = 2
        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())

        with self.assertRaisesRegex(
            ReferenceGaussianEvidenceError,
            "CameraBinding digest does not match admission",
        ):
            renderer.compute_reference_evidence(
                admission_input=admitted_input,
                stable_mask_artifact=mask,
                policy=policy,
                scene_snapshot=supported_snapshot([42, 9, 5, 11, 13]),
                camera_binding=different_binding,
            )

    def test_reference_adapter_rejects_a_stale_scene_working_set_token(self) -> None:
        width = 1
        height = 1
        policy = default_reference_evidence_policy()
        mask = mask_artifact(width, height, {(0, 0)})
        binding = camera_binding(width, height)
        admitted_input = locked_admission_input(mask, policy, binding, digest("b"))
        stale_snapshot = supported_snapshot([42, 9, 5, 11, 13])
        stale_snapshot["sceneVersion"] = digest("e")
        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        ready_runtime = StaticRendererRuntime(
            RendererRuntimeStatus.ready()
        )

        with (
            patch(
                "selection_service_companion.gsplat_renderer.current_renderer_runtime",
                return_value=ready_runtime,
            ),
            self.assertRaisesRegex(
                ReferenceGaussianEvidenceError,
                "Render Working Set token does not match",
            ),
        ):
            renderer.compute_reference_evidence(
                admission_input=admitted_input,
                stable_mask_artifact=mask,
                policy=policy,
                scene_snapshot=stale_snapshot,
                camera_binding=binding,
            )

    def test_reference_backend_failure_is_classified_as_evidence_failure(self) -> None:
        width = 1
        height = 1
        policy = default_reference_evidence_policy()
        mask = mask_artifact(width, height, {(0, 0)})
        binding = camera_binding(width, height)
        admitted_input = locked_admission_input(mask, policy, binding, digest("b"))
        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        ready_runtime = StaticRendererRuntime(
            RendererRuntimeStatus.ready()
        )

        with (
            patch(
                "selection_service_companion.gsplat_renderer.current_renderer_runtime",
                return_value=ready_runtime,
            ),
            patch.object(
                LockedGsplatBackend,
                "rasterize_reference_evidence_typed",
                side_effect=MaskSessionError(
                    "rendererMassMismatch", "reference contributor failed"
                ),
            ),
        ):
            with self.assertRaisesRegex(
                ReferenceGaussianEvidenceError,
                r"Evidence rendering failed \(rendererMassMismatch\)",
            ) as raised:
                renderer.compute_reference_evidence(
                    admission_input=admitted_input,
                    stable_mask_artifact=mask,
                    policy=policy,
                    scene_snapshot=supported_snapshot([42, 9, 5, 11, 13]),
                    camera_binding=binding,
                )
        self.assertEqual(raised.exception.code, "referenceRenderFailed")
        self.assertEqual(raised.exception.cause_code, "rendererMassMismatch")

    def test_occluded_target_stays_unobserved_while_out_of_scope_occluder_composites(
        self,
    ) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(1, 1, {(0, 0)})
        artifact = compute_reference_contributor_evidence(
            admission_input(mask, policy),
            mask,
            contributor_raster(1, 1, {(0, 0): [(0, 1.0)]}),
            policy,
        )

        self.assertEqual(artifact["positiveMass"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(artifact["visibleMass"], [0.0, 0.0, 0.0, 0.0])
        self.assertNotIn(42, artifact["stableGaussianIds"])

    def test_thin_mask_structure_keeps_low_positive_boundary_evidence(self) -> None:
        policy = default_reference_evidence_policy()
        mask = mask_artifact(5, 5, {(2, y_px) for y_px in range(5)})
        artifact = compute_reference_contributor_evidence(
            admission_input(mask, policy),
            mask,
            contributor_raster(5, 5, {(2, 2): [(2, 0.8)]}),
            policy,
        )

        self.assertEqual(artifact["positiveMass"], [0.2, 0.0, 0.0, 0.0])
        self.assertEqual(artifact["negativeMass"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(artifact["visibleMass"], [0.8, 0.0, 0.0, 0.0])
        self.assertEqual(artifact["boundaryMass"], [0.8, 0.0, 0.0, 0.0])

    def test_locked_gpu_reference_backend_populates_a_bound_artifact(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("locked renderer extra is not installed")
        if not torch.cuda.is_available():
            self.skipTest("CUDA is unavailable")

        width = 8
        height = 8
        policy = default_reference_evidence_policy()
        mask = mask_artifact(
            width,
            height,
            {(x_px, y_px) for y_px in range(height) for x_px in range(width)},
        )
        snapshot = supported_snapshot([42, 9, 5, 11, 13])
        view_camera = camera(width, height)
        binding = camera_binding(width, height)
        renderer = GsplatContributorRenderer(backend=LockedGsplatBackend())
        rgb = renderer.render_anchor(
            scene_snapshot=snapshot,
            view_id="view-1",
            camera=view_camera,
            width=width,
            height=height,
        )
        admitted_input = locked_admission_input(mask, policy, binding, rgb.rgb_digest)

        artifact = renderer.compute_reference_evidence(
            admission_input=admitted_input,
            stable_mask_artifact=mask,
            policy=policy,
            scene_snapshot=snapshot,
            camera_binding=binding,
        )

        self.assertTrue(is_gaussian_evidence_artifact(artifact))
        self.assertGreater(sum(artifact["positiveMass"]), 0.0)
        self.assertGreater(sum(artifact["visibleMass"]), 0.0)
        self.assertGreater(renderer.last_peak_vram_bytes or 0, 0)


if __name__ == "__main__":
    unittest.main()

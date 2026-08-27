from __future__ import annotations

import base64
from collections.abc import Iterator
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    binary_scene_snapshot_content_digest,
)
from selection_service_companion.camera_binding import camera_binding_digest
from selection_service_companion.conservative_seed import (
    ConservativeSeedError,
    canonical_conservative_seed_shadow_bytes,
    create_conservative_seed_policy,
    create_conservative_seed_target_geometry,
    evaluate_conservative_seed_shadow,
    is_conservative_seed_shadow_record,
)
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.gsplat_renderer import GsplatContributorRenderer
from selection_service_companion.reference_gaussian_evidence import (
    default_reference_evidence_policy,
)
from selection_service_companion.state import CompanionState


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def policy(overrides: dict[str, object] | None = None) -> dict[str, object]:
    return create_conservative_seed_policy({
        "schemaVersion": 1,
        "policyId": "conservative-seed-s0/experimental-shadow-v1",
        "minimumVisibleMass": 0.1,
        "minimumPositiveRatio": 0.8,
        "maximumNegativeMass": 0.05,
        "maximumConflictRatio": 0.1,
        "connectivityScaleMultiplier": 4.0,
        "minimumSatelliteGaussianCount": 1,
        "minimumSatellitePositiveMass": 0.25,
        "grossOutlierScaleMultiplier": 40.0,
        **(overrides or {}),
    })


def artifact(
    *,
    stable_ids: list[int],
    positive: list[float],
    negative: list[float],
    visible: list[float],
) -> dict[str, object]:
    dependency = {
        "splatId": "splat-1",
        "renderStateToken": "render-1",
        "geometryToken": "geometry-1",
        "gaussianIdentityToken": "gaussians-1",
        "worldTransformToken": "world-1",
    }
    working_set = create_evidence_working_set({
        "targetSplatId": "splat-1",
        "coreTargetStableIds": stable_ids,
        "contextStableGaussianIds": [],
    })
    current_input = {
        "requestBinding": {
            "targetContextId": "target-context-1",
            "contextRevision": 2,
            "dependencyToken": dependency,
        },
        "targetSplatId": "splat-1",
        "view": {
            "viewId": "anchor-view",
            "renderStatus": "ready",
            "participation": "included",
            "cameraBindingDigest": digest("a"),
            "rgbDigest": digest("b"),
            "stableMaskDigest": digest("c"),
        },
        "evidencePolicyDigest": digest("d"),
        "renderWorkingSet": {
            "targetSplatId": "splat-1",
            "dependencyToken": dependency,
            "cameraBindingDigest": digest("a"),
            "renderWorkingSetToken": digest("e"),
            "stableGaussianIds": stable_ids,
            "completeness": "complete",
        },
        "evidenceWorkingSet": working_set,
        "rasterImplementationId": "gsplat-direct-evidence/v1",
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": "global-atomic/direct-v1",
        "runtimeBuildId": "locked-runtime-1",
    }
    admission = admit_gaussian_evidence(current_input)
    assert admission["status"] == "admitted"
    return create_gaussian_evidence_artifact(
        admission["admission"],
        {
            "positiveMass": positive,
            "negativeMass": negative,
            "visibleMass": visible,
        },
    )


def geometry(
    rows: list[tuple[int, tuple[float, float, float]]],
) -> dict[str, object]:
    return create_conservative_seed_target_geometry(
        target_splat_id="splat-1",
        rows=[
            {
                "stableGaussianId": stable_id,
                "center": list(center),
                "logScales": [0.0, 0.0, 0.0],
            }
            for stable_id, center in rows
        ],
    )


def clock(*values: int):
    readings: Iterator[int] = iter(values)
    return lambda: next(readings)


def binary_fixture() -> tuple[bytes, BinarySceneSnapshotManifest]:
    source_digest = digest("b")
    scope_identity = json.dumps(
        {
            "policyId": "visible-editor-splats-conservative/v1",
            "targetSplatId": "splat-1",
            "sources": [{
                "splatId": "splat-1",
                "sourceContentDigest": source_digest,
                "gaussianCount": 1,
            }],
        },
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload = struct.pack(
        "<I" + "f" * 14,
        7,
        1.0,
        2.0,
        3.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    content: dict[str, object] = {
        "protocolVersion": "1",
        "gaussianCount": 1,
        "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
        "stableIdSchema": "uint32",
        "attributeSchema": "mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
        "appearancePolicy": "effective-editor-dc-sh-bands-0",
        "renderConfiguration": {
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        "authoritativeRenderScope": {
            "policyId": "visible-editor-splats-conservative/v1",
            "targetSplatId": "splat-1",
            "identityDigest": "sha256:" + hashlib.sha256(scope_identity).hexdigest(),
            "entries": [{
                "splatId": "splat-1",
                "role": "target",
                "sourceContentDigest": source_digest,
                "rowOffset": 0,
                "rowCount": 1,
                "renderIdStart": 7,
            }],
        },
        "shFloatCountPerGaussian": 0,
        "payloadByteLength": len(payload),
        "fields": [
            {"name": "stableIds", "scalarType": "uint32le", "componentCount": 1, "byteOffset": 0, "byteLength": 4},
            {"name": "means", "scalarType": "float32le", "componentCount": 3, "byteOffset": 4, "byteLength": 12},
            {"name": "rotationsXyzw", "scalarType": "float32le", "componentCount": 4, "byteOffset": 16, "byteLength": 16},
            {"name": "logScales", "scalarType": "float32le", "componentCount": 3, "byteOffset": 32, "byteLength": 12},
            {"name": "logitOpacities", "scalarType": "float32le", "componentCount": 1, "byteOffset": 44, "byteLength": 4},
            {"name": "dc", "scalarType": "float32le", "componentCount": 3, "byteOffset": 48, "byteLength": 12},
            {"name": "sh", "scalarType": "float32le", "componentCount": 0, "byteOffset": 60, "byteLength": 0},
        ],
    }
    chunk_length = 32
    chunks = tuple(
        BinarySceneSnapshotChunk(
            index=index,
            offset=index * chunk_length,
            byte_length=len(payload[index * chunk_length:(index + 1) * chunk_length]),
            digest="sha256:" + hashlib.sha256(
                payload[index * chunk_length:(index + 1) * chunk_length]
            ).hexdigest(),
        )
        for index in range((len(payload) + chunk_length - 1) // chunk_length)
    )
    content_digest = binary_scene_snapshot_content_digest(
        content,
        (payload[chunk.offset:chunk.offset + chunk.byte_length] for chunk in chunks),
    )
    return payload, BinarySceneSnapshotManifest(
        scene_id="splat-1",
        scene_version=content_digest,
        content_digest=content_digest,
        content=content,
        chunk_byte_length=chunk_length,
        chunks=chunks,
    )


class DirectEvidenceFixtureRenderer(GsplatContributorRenderer):
    requires_locked_runtime = False

    def __init__(self) -> None:
        super().__init__(backend=object())  # type: ignore[arg-type]
        self.artifact: dict[str, object] | None = None

    def compute_direct_evidence(self, **_kwargs: object) -> dict[str, object]:
        assert self.artifact is not None
        return self.artifact


class ConservativeSeedEvaluatorTests(unittest.TestCase):
    def test_admits_one_high_precision_connected_core(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9],
            positive=[0.9, 0.85],
            negative=[0.01, 0.02],
            visible=[1.0, 1.0],
        )

        evaluation = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry([
                (9, (2.0, 0.0, 0.0)),
                (7, (0.0, 0.0, 0.0)),
            ]),
            policy=policy(),
            clock_ns=clock(100, 250),
        )

        record = evaluation["record"]
        self.assertTrue(is_conservative_seed_shadow_record(record))
        self.assertEqual(record["status"], "experimental-shadow")
        self.assertEqual(record["coreCandidateStableGaussianIds"], [7, 9])
        self.assertEqual(record["admittedStableGaussianIds"], [7, 9])
        self.assertEqual(record["satelliteStableGaussianIds"], [])
        self.assertEqual(record["filteredStableGaussianIds"], [])
        self.assertEqual(
            [row["outcome"] for row in record["perGaussianSupport"]],
            ["core-candidate", "core-candidate"],
        )
        self.assertEqual(
            evaluation["timingTelemetry"],
            {
                "evaluationNanoseconds": 150,
                "evaluatedGaussianCount": 2,
                "connectivityComparisonCount": 1,
            },
        )

    def test_retains_thin_disconnected_material_support_as_a_satellite(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9, 12],
            positive=[0.9, 0.85, 0.8],
            negative=[0.01, 0.02, 0.01],
            visible=[1.0, 1.0, 0.9],
        )

        record = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry([
                (7, (0.0, 0.0, 0.0)),
                (9, (2.0, 0.0, 0.0)),
                (12, (8.0, 0.0, 0.0)),
            ]),
            policy=policy(),
            clock_ns=clock(0, 1),
        )["record"]

        self.assertEqual(record["coreCandidateStableGaussianIds"], [7, 9])
        self.assertEqual(record["satelliteStableGaussianIds"], [12])
        self.assertEqual(record["admittedStableGaussianIds"], [7, 9, 12])
        self.assertEqual(record["filteredStableGaussianIds"], [])
        self.assertEqual(record["perGaussianSupport"][2]["outcome"], "satellite")
        self.assertEqual(
            [summary["classification"] for summary in record["componentSummaries"]],
            ["core", "satellite"],
        )

    def test_low_visibility_stays_unknown_while_mixed_conflict_is_filtered(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9, 12],
            positive=[0.9, 0.01, 0.9],
            negative=[0.01, 0.0, 0.2],
            visible=[1.0, 0.05, 1.0],
        )

        record = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry([
                (7, (0.0, 0.0, 0.0)),
                (9, (2.0, 0.0, 0.0)),
                (12, (3.0, 0.0, 0.0)),
            ]),
            policy=policy(),
            clock_ns=clock(0, 1),
        )["record"]

        self.assertEqual(record["admittedStableGaussianIds"], [7])
        self.assertEqual(record["filteredStableGaussianIds"], [9, 12])
        low_visibility = record["perGaussianSupport"][1]
        self.assertEqual(low_visibility["outcome"], "filtered-low-visibility")
        self.assertIn("semantic-disposition-unknown", low_visibility["reasons"])
        self.assertNotIn("rejected", low_visibility["outcome"])
        self.assertEqual(
            record["perGaussianSupport"][2]["outcome"],
            "filtered-conflict",
        )

    def test_records_a_policy_bounded_gross_outlier_reason(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9],
            positive=[0.9, 0.8],
            negative=[0.01, 0.01],
            visible=[1.0, 0.9],
        )

        record = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry([
                (7, (0.0, 0.0, 0.0)),
                (9, (100.0, 0.0, 0.0)),
            ]),
            policy=policy(),
            clock_ns=clock(0, 1),
        )["record"]

        self.assertEqual(record["coreCandidateStableGaussianIds"], [7])
        self.assertEqual(record["satelliteStableGaussianIds"], [])
        self.assertEqual(record["filteredStableGaussianIds"], [9])
        self.assertEqual(record["perGaussianSupport"][1]["outcome"], "gross-outlier")
        self.assertEqual(
            record["componentSummaries"][1]["classification"],
            "gross-outlier",
        )

    def test_nonmaterial_disconnected_support_keeps_a_named_filtered_reason(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9],
            positive=[0.9, 0.8],
            negative=[0.01, 0.01],
            visible=[1.0, 0.9],
        )

        record = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry([
                (7, (0.0, 0.0, 0.0)),
                (9, (8.0, 0.0, 0.0)),
                (42, (20.0, 0.0, 0.0)),
            ]),
            policy=policy({"minimumSatelliteGaussianCount": 2}),
            clock_ns=clock(0, 1),
        )["record"]

        self.assertEqual(record["targetStableGaussianIds"], [7, 9, 42])
        self.assertEqual(record["admittedStableGaussianIds"], [7])
        self.assertEqual(record["filteredStableGaussianIds"], [9])
        self.assertEqual(
            record["perGaussianSupport"][1]["outcome"],
            "filtered-disconnected",
        )
        self.assertEqual(
            record["componentSummaries"][1]["classification"],
            "filtered-disconnected",
        )

    def test_canonical_record_is_independent_of_geometry_row_order(self) -> None:
        evidence = artifact(
            stable_ids=[7, 9, 12],
            positive=[0.9, 0.85, 0.8],
            negative=[0.01, 0.02, 0.01],
            visible=[1.0, 1.0, 0.9],
        )
        rows = [
            (7, (0.0, 0.0, 0.0)),
            (9, (2.0, 0.0, 0.0)),
            (12, (8.0, 0.0, 0.0)),
        ]

        first = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry(rows),
            policy=policy(),
            clock_ns=clock(0, 1),
        )
        permuted = evaluate_conservative_seed_shadow(
            evidence_artifact=evidence,
            target_geometry=geometry(list(reversed(rows))),
            policy=policy(),
            clock_ns=clock(100, 500),
        )

        self.assertEqual(first["record"], permuted["record"])
        self.assertEqual(
            first["record"]["recordDigest"],
            permuted["record"]["recordDigest"],
        )
        self.assertEqual(
            canonical_conservative_seed_shadow_bytes(first["record"]),
            canonical_conservative_seed_shadow_bytes(permuted["record"]),
        )
        self.assertNotEqual(
            first["timingTelemetry"], permuted["timingTelemetry"]
        )

    def test_policy_validation_rejects_unversioned_or_tampered_values(self) -> None:
        with self.assertRaisesRegex(ConservativeSeedError, "experimental S0"):
            policy({"policyId": "conservative-seed-s0/production-v1"})
        with self.assertRaisesRegex(ConservativeSeedError, "valid ranges"):
            policy({"minimumPositiveRatio": 1.1})

        tampered = policy()
        tampered["minimumVisibleMass"] = 0.2
        with self.assertRaisesRegex(ConservativeSeedError, "digest"):
            evaluate_conservative_seed_shadow(
                evidence_artifact=artifact(
                    stable_ids=[7],
                    positive=[0.9],
                    negative=[0.01],
                    visible=[1.0],
                ),
                target_geometry=geometry([(7, (0.0, 0.0, 0.0))]),
                policy=tampered,
                clock_ns=clock(0, 1),
            )

    def test_duplicate_geometry_and_malformed_evidence_identity_fail_closed(self) -> None:
        with self.assertRaisesRegex(ConservativeSeedError, "unique uint32"):
            geometry([
                (7, (0.0, 0.0, 0.0)),
                (7, (1.0, 0.0, 0.0)),
            ])
        with self.assertRaisesRegex(ConservativeSeedError, "finite range"):
            create_conservative_seed_target_geometry(
                target_splat_id="splat-1",
                rows=[{
                    "stableGaussianId": 7,
                    "center": [0.0, 0.0, 0.0],
                    "logScales": [1000.0, 0.0, 0.0],
                }],
            )

        malformed = artifact(
            stable_ids=[7],
            positive=[0.9],
            negative=[0.01],
            visible=[1.0],
        )
        malformed["artifactDigest"] = digest("f")
        with self.assertRaisesRegex(ConservativeSeedError, "exact production"):
            evaluate_conservative_seed_shadow(
                evidence_artifact=malformed,
                target_geometry=geometry([(7, (0.0, 0.0, 0.0))]),
                policy=policy(),
                clock_ns=clock(0, 1),
            )


class ConservativeSeedIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.renderer = DirectEvidenceFixtureRenderer()
        self.state = CompanionState(
            Path(self.temporary_directory.name),
            contributor_renderer=self.renderer,
        )
        payload, self.manifest = binary_fixture()
        upload = self.state.begin_binary_scene_snapshot_upload(self.manifest)
        assert upload.upload_id is not None
        for chunk in self.manifest.chunks:
            body = payload[chunk.offset:chunk.offset + chunk.byte_length]
            self.state.accept_binary_scene_snapshot_chunk(
                upload.upload_id,
                chunk.index,
                body,
                chunk.digest,
            )
        self.state.commit_binary_scene_snapshot_upload(upload.upload_id)

        self.camera = {
            "revision": 0,
            "cameraToWorld": [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            "projection": {
                "model": "pinhole",
                "fx": 1.0,
                "fy": 1.0,
                "cx": 0.0,
                "cy": 0.0,
                "width": 1,
                "height": 1,
                "near": 0.1,
                "far": 10.0,
            },
            "conventionVersion": "opencv-camera-to-world/v1",
        }
        mask_bytes = b"\x01"
        self.stable_mask = {
            "encoding": "bitset-lsb-v1",
            "width": 1,
            "height": 1,
            "data": base64.b64encode(mask_bytes).decode("ascii"),
            "digest": "sha256:" + hashlib.sha256(mask_bytes).hexdigest(),
        }
        dependency = {
            "splatId": "splat-1",
            "renderStateToken": "render-1",
            "geometryToken": "geometry-1",
            "gaussianIdentityToken": "gaussians-1",
            "worldTransformToken": "world-1",
        }
        self.current_input = {
            "requestBinding": {
                "targetContextId": "target-context-1",
                "contextRevision": 2,
                "dependencyToken": dependency,
            },
            "targetSplatId": "splat-1",
            "view": {
                "viewId": "anchor-view",
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": camera_binding_digest(self.camera),
                "rgbDigest": digest("a"),
                "stableMaskDigest": self.stable_mask["digest"],
            },
            "evidencePolicyDigest": default_reference_evidence_policy()[
                "evidencePolicyDigest"
            ],
            "renderWorkingSet": {
                "targetSplatId": "splat-1",
                "dependencyToken": dependency,
                "cameraBindingDigest": camera_binding_digest(self.camera),
                "renderWorkingSetToken": self.manifest.content_digest,
                "stableGaussianIds": [7],
                "completeness": "complete",
            },
            "evidenceWorkingSet": create_evidence_working_set({
                "targetSplatId": "splat-1",
                "coreTargetStableIds": [7],
                "contextStableGaussianIds": [],
            }),
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendKind": "production-direct",
            "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        }
        admission = admit_gaussian_evidence(self.current_input)
        assert admission["status"] == "admitted"
        self.renderer.artifact = create_gaussian_evidence_artifact(
            admission["admission"],
            {
                "positiveMass": [0.9],
                "negativeMass": [0.01],
                "visibleMass": [1.0],
            },
        )

    def tearDown(self) -> None:
        self.state.release_runtime_state()
        self.temporary_directory.cleanup()

    def request(self) -> dict[str, object]:
        return {
            "evidenceAttemptId": "evidence-attempt-1",
            "sceneId": self.manifest.scene_id,
            "sceneVersion": self.manifest.scene_version,
            "renderConfigVersion": "supersplat-effective-rgb-v1",
            "currentInput": self.current_input,
            "cameraBinding": self.camera,
            "stableMask": self.stable_mask,
        }

    def test_opt_in_consumes_the_exact_published_anchor_artifact_only_in_shadow(self) -> None:
        enabled = self.state.opt_in_conservative_seed_shadow(
            current_anchor_input=self.current_input,
            policy=policy(),
        )

        response = self.state.produce_ai_select_direct_evidence(self.request())
        assert self.renderer.artifact is not None
        shadow = self.state.conservative_seed_shadow_result(
            self.renderer.artifact["artifactDigest"]
        )

        self.assertEqual(enabled["status"], "enabled")
        self.assertEqual(response["artifact"], self.renderer.artifact)
        self.assertFalse(response["reused"])
        self.assertNotIn("conservativeSeed", response)
        self.assertEqual(shadow["status"], "available")
        self.assertEqual(
            shadow["record"]["evidenceIdentity"]["artifactDigest"],
            self.renderer.artifact["artifactDigest"],
        )
        self.assertEqual(shadow["record"]["targetStableGaussianIds"], [7])
        self.assertEqual(
            shadow["record"]["anchorViewIdentity"]["stableMaskDigest"],
            self.stable_mask["digest"],
        )
        self.assertEqual(
            shadow["timingTelemetry"]["evaluatedGaussianCount"], 1
        )

    def test_shadow_failure_preserves_the_published_production_artifact(self) -> None:
        self.state.opt_in_conservative_seed_shadow(
            current_anchor_input=self.current_input,
            policy=policy(),
        )
        assert self.renderer.artifact is not None

        with patch(
            "selection_service_companion.state.evaluate_conservative_seed_shadow",
            side_effect=MemoryError("injected shadow failure"),
        ):
            response = self.state.produce_ai_select_direct_evidence(self.request())

        shadow = self.state.conservative_seed_shadow_result(
            self.renderer.artifact["artifactDigest"]
        )
        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["artifact"], self.renderer.artifact)
        self.assertNotIn("conservativeSeed", response)
        self.assertEqual(shadow["status"], "failed-closed")
        self.assertEqual(
            shadow["reason"], "conservative-seed-shadow-evaluation-failed"
        )
        self.assertEqual(shadow["failureType"], "MemoryError")

    def test_default_off_and_disable_keep_shadow_out_of_production_consumers(self) -> None:
        assert self.renderer.artifact is not None
        response = self.state.produce_ai_select_direct_evidence(self.request())
        artifact_digest = self.renderer.artifact["artifactDigest"]

        self.assertEqual(
            self.state.conservative_seed_shadow_result(artifact_digest),
            {"status": "unavailable"},
        )
        self.assertEqual(response["artifact"], self.renderer.artifact)
        self.assertNotIn("conservativeSeed", response)

        self.state.opt_in_conservative_seed_shadow(
            current_anchor_input=self.current_input,
            policy=policy(),
        )
        self.state.disable_conservative_seed_shadow()
        self.assertEqual(
            self.state.conservative_seed_shadow_result(artifact_digest),
            {"status": "unavailable"},
        )


if __name__ == "__main__":
    unittest.main()

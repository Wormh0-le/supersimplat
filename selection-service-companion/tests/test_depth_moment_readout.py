from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from selection_service_companion.depth_moment_readout import (
    DepthMomentConsumerRegistration,
    DepthMomentReadoutCache,
    DepthMomentReadoutError,
    DepthMomentReadoutRecord,
    DepthMomentTelemetry,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import DepthMomentValidityPolicy


def digest(character: str) -> str:
    return "sha256:" + (character * 64)


def request_binding() -> dict[str, object]:
    return {
        "targetContextId": "context-1",
        "contextRevision": 3,
        "dependencyToken": {
            "splatId": "target-1",
            "renderStateToken": "render-1",
            "geometryToken": "geometry-1",
            "gaussianIdentityToken": "gaussians-1",
            "worldTransformToken": "transform-1",
        },
    }


def admitted_input() -> dict[str, object]:
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "target-1",
        "viewId": "view-1",
        "cameraBindingDigest": digest("a"),
        "rgbDigest": digest("b"),
        "stableMaskDigest": digest("c"),
        "evidencePolicyDigest": digest("d"),
        "renderWorkingSetToken": digest("e"),
        "evidenceWorkingSetToken": digest("f"),
        "stableGaussianIds": [4, 9],
        "rasterImplementationId": "supersimplat-gsplat-direct-evidence/v1",
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": "global-atomic/direct-v1",
        "runtimeBuildId": digest("1"),
    }


def policy(
    *,
    policy_id: str = "depth-moment-minimum-m0/test-v1",
    minimum_m0: float = 0.01,
) -> DepthMomentValidityPolicy:
    return DepthMomentValidityPolicy(
        policy_id=policy_id,
        minimum_m0=minimum_m0,
    )


def identity(
    *,
    current_policy: DepthMomentValidityPolicy | None = None,
):
    return create_depth_moment_readout_identity(
        admitted_input(),
        render_stable_ids_by_projected_row=(9, 4),
        policy=current_policy or policy(),
        width=2,
        height=1,
        direct_evidence_abi_version="supersimplat-direct-evidence-abi/v3",
        direct_evidence_source_revision=digest("2"),
        direct_evidence_runtime_build_id=digest("1"),
    )


def record(
    *,
    raw_values: list[list[list[float]]] | None = None,
    peak_vram_bytes: int = 4096,
):
    import torch

    raw = torch.tensor(
        raw_values or [[[0.5, 2.0, 8.0], [0.0, 0.0, 0.0]]],
        dtype=torch.float32,
    )
    return DepthMomentReadoutRecord(
        identity=identity(),
        raw_depth_moments=raw,
        policy=policy(),
        telemetry=DepthMomentTelemetry(
            depth_moment_buffer_bytes=24,
            peak_vram_bytes=peak_vram_bytes,
        ),
    )


class DepthMomentReadoutRecordTests(unittest.TestCase):
    def test_constructor_owns_immutable_tensors_and_has_one_canonical_digest(self) -> None:
        import torch

        readout = record()
        repeated = record()
        warm_restart = record(peak_vram_bytes=8192)

        self.assertEqual(readout.readout_digest, repeated.readout_digest)
        self.assertEqual(readout.readout_digest, warm_restart.readout_digest)
        self.assertNotEqual(
            readout.telemetry.peak_vram_bytes,
            warm_restart.telemetry.peak_vram_bytes,
        )
        self.assertRegex(readout.readout_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(readout.validate())
        self.assertEqual(
            set(readout.tensor_digests.as_dict()),
            {"rawDepthMoments", "valid", "cwed", "variance"},
        )
        self.assertEqual(readout.valid.tolist(), [[True, False]])
        self.assertEqual(readout.telemetry.depth_moment_buffer_bytes, 24)
        self.assertEqual(readout.telemetry.owned_tensor_buffer_bytes, 42)
        self.assertEqual(readout.telemetry.peak_vram_bytes, 4096)
        self.assertEqual(readout.cwed[0, 0].item(), 4.0)
        self.assertTrue(torch.isnan(readout.cwed[0, 1]))

        caller_copy = readout.raw_depth_moments
        caller_copy[0, 0, 0] = 99.0
        self.assertEqual(readout.raw_depth_moments[0, 0, 0].item(), 0.5)
        self.assertTrue(readout.validate())
        with self.assertRaises(FrozenInstanceError):
            readout.readout_digest = digest("9")  # type: ignore[misc]

    def test_constructor_rejects_inexact_identity_and_tensor_shape(self) -> None:
        import torch

        missing = admitted_input()
        del missing["rgbDigest"]
        extra = {**admitted_input(), "depthMoments": "forbidden"}
        for value in (missing, extra):
            with self.subTest(keys=sorted(value)):
                with self.assertRaises(DepthMomentReadoutError):
                    create_depth_moment_readout_identity(
                        value,
                        render_stable_ids_by_projected_row=(9, 4),
                        policy=policy(),
                        width=2,
                        height=1,
                        direct_evidence_abi_version=(
                            "supersimplat-direct-evidence-abi/v3"
                        ),
                        direct_evidence_source_revision=digest("2"),
                        direct_evidence_runtime_build_id=digest("1"),
                    )

        invalid_tensors = (
            torch.zeros((1, 2), dtype=torch.float32),
            torch.zeros((1, 1, 3), dtype=torch.float32),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            torch.tensor(
                [[[0.5, float("nan"), 8.0], [0.0, 0.0, 0.0]]],
                dtype=torch.float32,
            ),
        )
        for raw in invalid_tensors:
            with self.subTest(shape=tuple(raw.shape), dtype=raw.dtype):
                with self.assertRaises(DepthMomentReadoutError):
                    DepthMomentReadoutRecord(
                        identity=identity(),
                        raw_depth_moments=raw,
                        policy=policy(),
                        telemetry=DepthMomentTelemetry(
                            depth_moment_buffer_bytes=24,
                            peak_vram_bytes=4096,
                        ),
                    )

        with self.assertRaises(DepthMomentReadoutError):
            DepthMomentReadoutRecord(
                identity=identity(),
                raw_depth_moments=torch.zeros((1, 2, 3), dtype=torch.float32),
                policy=policy(),
                telemetry=DepthMomentTelemetry(
                    depth_moment_buffer_bytes=12,
                    peak_vram_bytes=4096,
                ),
            )


class DepthMomentReadoutCacheTests(unittest.TestCase):
    def test_every_bound_identity_change_misses_or_is_explicitly_stale(self) -> None:
        base = record()
        base_identity = base.identity
        dependency = base_identity.request_binding.dependency
        changed_identities = {
            "target-context": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    target_context_id="context-2",
                ),
            ),
            "context-revision": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    context_revision=4,
                ),
            ),
            "target-splat": replace(
                base_identity,
                target_splat_id="target-2",
                request_binding=replace(
                    base_identity.request_binding,
                    dependency=replace(dependency, splat_id="target-2"),
                ),
            ),
            "render-state": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    dependency=replace(dependency, render_state_token="render-2"),
                ),
            ),
            "geometry": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    dependency=replace(dependency, geometry_token="geometry-2"),
                ),
            ),
            "gaussian-identity": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    dependency=replace(
                        dependency,
                        gaussian_identity_token="gaussians-2",
                    ),
                ),
            ),
            "world-transform": replace(
                base_identity,
                request_binding=replace(
                    base_identity.request_binding,
                    dependency=replace(
                        dependency,
                        world_transform_token="transform-2",
                    ),
                ),
            ),
            "view": replace(base_identity, view_id="view-2"),
            "camera": replace(base_identity, camera_binding_digest=digest("3")),
            "rgb": replace(base_identity, rgb_digest=digest("4")),
            "render-working-set": replace(
                base_identity,
                render_working_set_token=digest("5"),
            ),
            "projected-row-map": replace(
                base_identity,
                projected_row_mapping_digest=digest("6"),
            ),
            "abi": replace(
                base_identity,
                direct_evidence_abi_version=(
                    "supersimplat-direct-evidence-abi/future"
                ),
            ),
            "source": replace(
                base_identity,
                direct_evidence_source_revision=digest("7"),
            ),
            "runtime": replace(
                base_identity,
                direct_evidence_runtime_build_id=digest("8"),
            ),
            "policy": replace(
                base_identity,
                moment_policy_id="depth-moment-minimum-m0/test-v2",
            ),
        }

        cache = DepthMomentReadoutCache()
        cache.publish(base)
        self.assertEqual(cache.lookup(base_identity).status, "available")
        for dimension, changed in changed_identities.items():
            with self.subTest(dimension=dimension):
                self.assertIn(
                    cache.lookup(changed).status,
                    {"stale", "unavailable"},
                )
        self.assertEqual(cache.lookup(base_identity).status, "stale")

    def test_cache_hit_validates_tensor_digests_and_replacement_invalidates_old_key(self) -> None:
        cached = record()
        cache = DepthMomentReadoutCache()
        self.assertEqual(cache.publish(cached).status, "available")
        self.assertEqual(cache.lookup(cached.identity).status, "available")

        cached._raw_depth_moments[0, 0, 0] = 99.0
        corrupted = cache.lookup(cached.identity)
        self.assertEqual(corrupted.status, "stale")
        self.assertEqual(corrupted.reason, "tensor-digest-mismatch")

        replacement = record(raw_values=[[[0.75, 3.0, 12.0], [0.0, 0.0, 0.0]]])
        cache.publish(replacement)
        self.assertEqual(cache.lookup(replacement.identity).status, "available")

    def test_restart_recomputation_must_digest_match(self) -> None:
        original = record()
        restarted = DepthMomentReadoutCache()
        accepted = restarted.publish(
            record(),
            expected_recomputed_digest=original.readout_digest,
        )
        self.assertEqual(accepted.status, "available")

        changed = record(
            raw_values=[[[0.75, 3.0, 12.0], [0.0, 0.0, 0.0]]]
        )
        rejected = DepthMomentReadoutCache().publish(
            changed,
            expected_recomputed_digest=original.readout_digest,
        )
        self.assertEqual(rejected.status, "stale")
        self.assertEqual(rejected.reason, "recomputed-digest-mismatch")

    def test_registration_reports_unavailable_without_substitution(self) -> None:
        cache = DepthMomentReadoutCache()
        registration = DepthMomentConsumerRegistration(
            cache=cache,
            policy=policy(),
        )
        expected = identity()

        result = registration.consume_complete(
            admission=admitted_input(),
            render_stable_ids_by_projected_row=(9, 4),
            raw_depth_moments=None,
            width=2,
            height=1,
            depth_moment_buffer_bytes=0,
            peak_vram_bytes=4096,
            direct_evidence_abi_version="supersimplat-direct-evidence-abi/v3",
            direct_evidence_source_revision=digest("2"),
            direct_evidence_runtime_build_id=digest("1"),
        )

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason, "depth-moments-unavailable")
        self.assertIsNone(result.readout)
        self.assertEqual(registration.result, result)
        self.assertEqual(cache.lookup(expected).status, "unavailable")

    def test_registration_reports_identity_and_operational_failures_explicitly(self) -> None:
        registration = DepthMomentConsumerRegistration(
            cache=DepthMomentReadoutCache(),
            policy=policy(),
        )
        invalid_admission = {**admitted_input(), "unexpected": True}

        invalid = registration.consume_complete(
            admission=invalid_admission,
            render_stable_ids_by_projected_row=(9, 4),
            raw_depth_moments=None,
            width=2,
            height=1,
            depth_moment_buffer_bytes=0,
            peak_vram_bytes=4096,
            direct_evidence_abi_version="supersimplat-direct-evidence-abi/v3",
            direct_evidence_source_revision=digest("2"),
            direct_evidence_runtime_build_id=digest("1"),
        )
        self.assertEqual(invalid.status, "unavailable")
        self.assertEqual(invalid.reason, "depth-moment-identity-invalid")
        self.assertEqual(registration.result, invalid)

        with patch(
            "selection_service_companion.depth_moment_readout.DepthMomentReadoutRecord",
            side_effect=MemoryError("injected capacity failure"),
        ):
            capacity = registration.consume_complete(
                admission=admitted_input(),
                render_stable_ids_by_projected_row=(9, 4),
                raw_depth_moments=None,
                width=2,
                height=1,
                depth_moment_buffer_bytes=24,
                peak_vram_bytes=4096,
                direct_evidence_abi_version=(
                    "supersimplat-direct-evidence-abi/v3"
                ),
                direct_evidence_source_revision=digest("2"),
                direct_evidence_runtime_build_id=digest("1"),
            )
        self.assertEqual(capacity.status, "unavailable")
        self.assertEqual(capacity.reason, "depth-moment-capacity-unavailable")
        self.assertEqual(registration.result, capacity)


class DepthMomentPublicBoundaryTests(unittest.TestCase):
    def test_browser_and_candidate_sources_have_no_depth_moment_contract(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        browser_contracts = (
            repository_root / "src/ai-select/gaussian-evidence-contract.ts",
            repository_root / "src/ai-select/candidate-publication.ts",
            repository_root / "src/selection-service-readiness.ts",
        )
        forbidden = ("cwed", "depthmoment", "depth_moment")

        for path in browser_contracts:
            source = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=path):
                for token in forbidden:
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

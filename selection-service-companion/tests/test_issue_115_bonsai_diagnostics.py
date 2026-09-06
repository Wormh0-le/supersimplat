from __future__ import annotations

import math
import unittest
from typing import ClassVar
from unittest.mock import patch

import selection_service_companion.issue_115_bonsai_diagnostics as diagnostics
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
from selection_service_companion.issue_115_bonsai_diagnostics import (
    aggregate_issue_115_diagnostics,
)
from selection_service_companion.reference_gaussian_evidence import (
    default_reference_evidence_policy,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


class Issue115DiagnosticTests(unittest.TestCase):
    stable_ids: ClassVar[list[int]] = [1, 2, 3]
    request_binding: ClassVar[dict[str, object]] = {
        "targetContextId": "bonsai-context",
        "contextRevision": 0,
        "dependencyToken": {
            "splatId": "bonsai-splat",
            "renderStateToken": digest("a"),
            "geometryToken": digest("b"),
            "gaussianIdentityToken": digest("c"),
            "worldTransformToken": digest("d"),
        },
    }
    working_set = create_evidence_working_set({
        "targetSplatId": "bonsai-splat",
        "coreTargetStableIds": stable_ids,
        "contextStableGaussianIds": [],
    })
    policy = default_reference_evidence_policy()

    @classmethod
    def current_input(cls, view_id: str, mask_letter: str) -> dict[str, object]:
        camera_letter = "a" if view_id == "anchor-view" else "b"
        rgb_letter = "b" if view_id == "anchor-view" else "c"
        admission_input = {
            "requestBinding": cls.request_binding,
            "targetSplatId": "bonsai-splat",
            "view": {
                "viewId": view_id,
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": digest(camera_letter),
                "rgbDigest": digest(rgb_letter),
                "stableMaskDigest": digest(mask_letter),
            },
            "evidencePolicyDigest": cls.policy["evidencePolicyDigest"],
            "renderWorkingSet": {
                "targetSplatId": "bonsai-splat",
                "dependencyToken": cls.request_binding["dependencyToken"],
                "cameraBindingDigest": digest(camera_letter),
                "renderWorkingSetToken": digest("e"),
                "stableGaussianIds": cls.stable_ids,
                "completeness": "complete",
            },
            "evidenceWorkingSet": cls.working_set,
            "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
            "evidenceBackendKind": "production-direct",
            "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
            "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        }
        return admission_input

    @classmethod
    def artifact(
        cls,
        *,
        view_id: str,
        mask_letter: str,
        positive: list[float],
        negative: list[float],
        visible: list[float],
        boundary: list[float],
    ) -> tuple[dict[str, object], dict[str, object]]:
        current_input = cls.current_input(view_id, mask_letter)
        admitted = admit_gaussian_evidence(current_input)
        assert admitted["status"] == "admitted"
        admission = admitted["admission"]
        assert isinstance(admission, dict)
        return current_input, create_gaussian_evidence_artifact(
            admission,
            {
                "positiveMass": positive,
                "negativeMass": negative,
                "visibleMass": visible,
                "boundaryMass": boundary,
            },
        )

    def test_one_raw_aggregation_drives_anchor_and_pair_qs(self) -> None:
        anchor_input, anchor_artifact = self.artifact(
            view_id="anchor-view",
            mask_letter="f",
            positive=[4.0, 0.0, 0.2],
            negative=[0.0, 0.0, 0.8],
            visible=[4.0, 0.0, 1.0],
            boundary=[0.0, 0.0, 0.5],
        )
        secondary_input, secondary_artifact = self.artifact(
            view_id="view-b",
            mask_letter="0",
            positive=[0.0, 4.0, 0.0],
            negative=[0.0, 0.0, 0.0],
            visible=[0.0, 4.0, 0.0],
            boundary=[0.0, 0.0, 0.0],
        )
        with patch.object(
            diagnostics,
            "aggregate_reference_gaussian_evidence",
            wraps=diagnostics.aggregate_reference_gaussian_evidence,
        ) as aggregate:
            result = aggregate_issue_115_diagnostics(
                aggregation_input={
                    "requestBinding": self.request_binding,
                    "targetSplatId": "bonsai-splat",
                    "classificationUniverseStableGaussianIds": self.stable_ids,
                    "classificationScopeStableGaussianIds": self.stable_ids,
                    "evidenceWorkingSet": self.working_set,
                    "views": [
                        {"currentInput": anchor_input, "artifact": anchor_artifact},
                        {"currentInput": secondary_input, "artifact": secondary_artifact},
                    ],
                },
                c_inspection={
                    "viewId": "view-c",
                    "cameraBindingDigest": digest("c"),
                    "rgbDigest": digest("d"),
                    "visibleStableGaussianIds": self.stable_ids,
                },
            )
        self.assertEqual(aggregate.call_count, 1)

        self.assertEqual(result["aggregationPassCount"], 1)
        anchor = result["anchorOnly"]
        pair = result["anchorPlusB"]
        assert isinstance(anchor, dict)
        assert isinstance(pair, dict)
        self.assertEqual(anchor["selectedStableGaussianIds"], [1])
        self.assertEqual(pair["selectedStableGaussianIds"], [1, 2])
        self.assertEqual(pair["uncertainStableGaussianIds"], [3])
        pair_q = pair["q"]
        pair_s = pair["s"]
        assert isinstance(pair_q, list)
        assert isinstance(pair_s, list)
        self.assertAlmostEqual(pair_q[0], 5.0 / 6.0)
        self.assertAlmostEqual(
            pair_s[0], (1.0 - math.exp(-4.0)) * (1.0 - math.exp(-4.0))
        )

        c = result["cInspection"]
        assert isinstance(c, dict)
        self.assertEqual(c["newStableGaussianIds"], [2])
        self.assertEqual(c["contaminationStableGaussianIds"], [3])
        self.assertEqual(c["unknownStableGaussianIds"], [3])
        self.assertFalse(c["usedForFusion"])
        self.assertFalse(c["stableMaskPresent"])

    def test_c_input_cannot_be_used_as_fusion_evidence(self) -> None:
        anchor_input, anchor_artifact = self.artifact(
            view_id="anchor-view",
            mask_letter="f",
            positive=[1.0, 1.0, 1.0],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            boundary=[0.0, 0.0, 0.0],
        )
        secondary_input, secondary_artifact = self.artifact(
            view_id="view-b",
            mask_letter="0",
            positive=[1.0, 1.0, 1.0],
            negative=[0.0, 0.0, 0.0],
            visible=[1.0, 1.0, 1.0],
            boundary=[0.0, 0.0, 0.0],
        )
        with self.assertRaises(ValueError):
            aggregate_issue_115_diagnostics(
                aggregation_input={
                    "requestBinding": self.request_binding,
                    "targetSplatId": "bonsai-splat",
                    "classificationUniverseStableGaussianIds": self.stable_ids,
                    "classificationScopeStableGaussianIds": self.stable_ids,
                    "evidenceWorkingSet": self.working_set,
                    "views": [
                        {"currentInput": anchor_input, "artifact": anchor_artifact},
                        {"currentInput": secondary_input, "artifact": secondary_artifact},
                    ],
                },
                c_inspection={
                    "viewId": "view-c",
                    "cameraBindingDigest": digest("c"),
                    "rgbDigest": digest("d"),
                    "visibleStableGaussianIds": [1, 4],
                },
            )


if __name__ == "__main__":
    unittest.main()

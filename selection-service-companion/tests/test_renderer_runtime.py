from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.evidence import StaticContributorRenderer
from selection_service_companion.renderer_runtime import (
    CurrentProcessGsplatInspection,
    GsplatRuntime,
    GsplatRuntimeFacts,
    RendererRuntimeStatus,
    StaticGsplatRuntimeInspection,
    StaticRendererRuntime,
)
from selection_service_companion.state import CompanionState


class RendererRuntimeReadinessTests(unittest.TestCase):
    @staticmethod
    def locked_runtime_facts() -> GsplatRuntimeFacts:
        return GsplatRuntimeFacts(
            environment_prefix=Path("/opt/supersplat/.venv"),
            operating_system="Linux",
            cuda_available=True,
            torch_package_path=Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py"
            ),
            gsplat_package_path=Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
            ),
        )

    def test_capabilities_advertise_gsplat_only_after_runtime_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = CompanionState(
                Path(directory) / "state",
                contributor_renderer=StaticContributorRenderer({}),
                renderer_runtime=StaticRendererRuntime(
                    RendererRuntimeStatus.ready()
                ),
            )
            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {
                    "id": "gsplat",
                    "status": "ready",
                    "rgbRendererVersion": "gsplat-direct-evidence-rgb/v1",
                    "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
                    "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
                },
            )

    def test_capabilities_advertise_gsplat_after_runtime_availability_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = CompanionState(
                Path(directory) / "state",
                contributor_renderer=StaticContributorRenderer({}),
                renderer_runtime=GsplatRuntime(
                    StaticGsplatRuntimeInspection(
                        self.locked_runtime_facts()
                    )
                ),
            )
            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {
                    "id": "gsplat",
                    "status": "ready",
                    "rgbRendererVersion": "gsplat-direct-evidence-rgb/v1",
                    "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
                    "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
                },
            )

    def test_runtime_mismatches_remain_explicitly_unavailable(self) -> None:
        expected = self.locked_runtime_facts()
        cases = (
            (
                "missing CUDA",
                replace(expected, cuda_available=False),
                "CUDA",
            ),
            (
                "missing gsplat",
                replace(expected, gsplat_package_path=None),
                "gsplat must be installed",
            ),
            (
                "SAM3 reference environment",
                replace(
                    expected,
                    environment_prefix=Path("/workspace/thirdparty/sam3/.venv"),
                ),
                "must not use thirdparty/sam3/.venv",
            ),
            (
                "unverified operating system",
                replace(expected, operating_system="Windows"),
                "Linux",
            ),
            (
                "package leaked from the SAM3 reference environment",
                replace(
                    expected,
                    torch_package_path=Path(
                        "/workspace/thirdparty/sam3/.venv/lib/python3.12/site-packages/torch/__init__.py"
                    ),
                ),
                "outside it are not used",
            ),
        )

        for name, facts, expected_message in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                state = CompanionState(
                    Path(directory) / "state",
                    contributor_renderer=StaticContributorRenderer({}),
                    renderer_runtime=GsplatRuntime(
                        StaticGsplatRuntimeInspection(facts)
                    ),
                )
                capability = state.capabilities(["https://editor.example"])[
                    "renderer"
                ]
                self.assertEqual(capability["status"], "unavailable")
                self.assertIn(expected_message, capability["message"])

    def test_default_readiness_inspects_the_current_companion_process(self) -> None:
        torch_module = SimpleNamespace(
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py",
            cuda=SimpleNamespace(is_available=lambda: True),
        )
        def import_runtime_module(name: str):
            if name == "torch":
                return torch_module
            if name == "gsplat":
                return SimpleNamespace(
                    __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
                )
            raise ImportError(name)

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("sys.prefix", "/opt/supersplat/.venv"),
            patch("importlib.import_module", side_effect=import_runtime_module),
        ):
            state = CompanionState(
                Path(directory) / "state",
            )
            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {
                    "id": "gsplat",
                    "status": "ready",
                    "rgbRendererVersion": "gsplat-direct-evidence-rgb/v1",
                    "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
                    "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
                },
            )

    def test_driver_readout_falls_back_to_nvidia_smi(self) -> None:
        torch_module = SimpleNamespace(
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py",
            cuda=SimpleNamespace(is_available=lambda: False),
        )
        gsplat_module = SimpleNamespace(
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
        )
        with (
            patch(
                "importlib.import_module",
                side_effect=lambda name: torch_module
                if name == "torch"
                else gsplat_module,
            ),
            patch.object(
                Path,
                "read_text",
                side_effect=OSError("test has no procfs"),
            ),
            patch.object(
                subprocess,
                "run",
                return_value=SimpleNamespace(stdout="610.62\n"),
            ) as run,
        ):
            facts = CurrentProcessGsplatInspection().facts()

        self.assertEqual(facts.driver_version, "610.62")
        run.assert_called_once()

    def test_readiness_rejects_a_shadowed_gsplat_module(self) -> None:
        torch_module = SimpleNamespace(
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py",
            cuda=SimpleNamespace(is_available=lambda: True),
        )
        gsplat_module = SimpleNamespace(
            __file__="/workspace/thirdparty/sam3/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("platform.system", return_value="Linux"),
            patch("sys.prefix", "/opt/supersplat/.venv"),
            patch(
                "importlib.import_module",
                side_effect=lambda name: torch_module
                if name == "torch"
                else gsplat_module,
            ),
        ):
            state = CompanionState(
                Path(directory) / "state",
                contributor_renderer=StaticContributorRenderer({}),
            )
            capability = state.capabilities(["https://editor.example"])["renderer"]

            self.assertEqual(capability["status"], "unavailable")
            self.assertIn("gsplat", capability["message"])
            self.assertIn("outside it are not used", capability["message"])

    def test_broken_optional_runtime_degrades_to_unavailable(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "importlib.import_module",
                side_effect=AttributeError("broken optional CUDA extension"),
            ),
        ):
            state = CompanionState(Path(directory) / "state")
            capability = state.capabilities(["https://editor.example"])["renderer"]

            self.assertEqual(capability["status"], "unavailable")
            self.assertIn("inspection failed", capability["message"])

if __name__ == "__main__":
    unittest.main()

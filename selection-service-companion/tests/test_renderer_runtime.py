from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from selection_service_companion.evidence import StaticContributorRenderer
from selection_service_companion.renderer_runtime import (
    GsplatRuntime,
    GsplatRuntimeFacts,
    RendererRuntimeStatus,
    StaticGsplatRuntimeInspection,
    StaticRendererRuntime,
)
from selection_service_companion.state import CompanionState


class RendererRuntimeReadinessTests(unittest.TestCase):
    @staticmethod
    def install_canonical_release(state: CompanionState) -> None:
        state.install_release(
            "0.1.0",
            Path(__file__).resolve().parents[1] / "uv.lock",
        )

    @staticmethod
    def locked_runtime_facts() -> GsplatRuntimeFacts:
        return GsplatRuntimeFacts(
            environment_prefix=Path("/opt/supersplat/.venv"),
            operating_system="Linux",
            python_version="3.12.12",
            torch_version="2.11.0+cu128",
            cuda_version="12.8",
            cuda_available=True,
            gsplat_version="1.5.3",
            gsplat_source_url="https://github.com/nerfstudio-project/gsplat.git",
            gsplat_source_commit="77ab983ffe43420b2131669cb35776b883ca4c3c",
            torch_package_path=Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py"
            ),
            gsplat_package_path=Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
            ),
            gsplat_distribution_path=Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages"
            ),
        )

    def test_capabilities_advertise_gsplat_only_after_runtime_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = CompanionState(
                Path(directory) / "state",
                contributor_renderer=StaticContributorRenderer({}),
                renderer_runtime=StaticRendererRuntime(
                    RendererRuntimeStatus.ready(cuda_version="12.8")
                ),
            )
            self.install_canonical_release(state)

            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {"id": "gsplat", "status": "ready", "cudaVersion": "12.8"},
            )

    def test_capabilities_verify_the_locked_gsplat_runtime_before_ready(self) -> None:
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
            self.install_canonical_release(state)

            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {"id": "gsplat", "status": "ready", "cudaVersion": "12.8"},
            )

    def test_runtime_mismatches_remain_explicitly_unavailable(self) -> None:
        expected = self.locked_runtime_facts()
        cases = (
            (
                "missing CUDA",
                replace(expected, cuda_available=False),
                "CUDA 12.8",
            ),
            (
                "missing gsplat",
                replace(expected, gsplat_version=None),
                "gsplat 1.5.3",
            ),
            (
                "different source commit",
                replace(expected, gsplat_source_commit="different-commit"),
                "locked source commit",
            ),
            (
                "local source without immutable VCS identity",
                replace(
                    expected,
                    gsplat_source_url="file:///workspace/thirdparty/gsplat",
                    gsplat_source_commit=None,
                ),
                "locked Git source",
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
                self.install_canonical_release(state)

                capability = state.capabilities(["https://editor.example"])[
                    "renderer"
                ]
                self.assertEqual(capability["status"], "unavailable")
                self.assertIn(expected_message, capability["message"])

    def test_default_readiness_inspects_the_current_companion_process(self) -> None:
        torch_module = SimpleNamespace(
            __version__="2.11.0+cu128",
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py",
            version=SimpleNamespace(cuda="12.8"),
            cuda=SimpleNamespace(is_available=lambda: True),
        )
        gsplat_distribution = SimpleNamespace(
            version="1.5.3",
            locate_file=lambda name: Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages"
            ),
            read_text=lambda name: json.dumps(
                {
                    "url": "https://github.com/nerfstudio-project/gsplat.git",
                    "vcs_info": {
                        "vcs": "git",
                        "commit_id": "77ab983ffe43420b2131669cb35776b883ca4c3c",
                    },
                }
            )
            if name == "direct_url.json"
            else None,
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
            patch("importlib.metadata.distribution", return_value=gsplat_distribution),
            patch("platform.python_version", return_value="3.12.12"),
            patch("sys.prefix", "/opt/supersplat/.venv"),
            patch("importlib.import_module", side_effect=import_runtime_module),
        ):
            state = CompanionState(
                Path(directory) / "state",
            )
            self.install_canonical_release(state)

            self.assertEqual(
                state.capabilities(["https://editor.example"])["renderer"],
                {"id": "gsplat", "status": "ready", "cudaVersion": "12.8"},
            )

    def test_readiness_rejects_a_shadowed_gsplat_module(self) -> None:
        torch_module = SimpleNamespace(
            __version__="2.11.0+cu128",
            __file__="/opt/supersplat/.venv/lib/python3.12/site-packages/torch/__init__.py",
            version=SimpleNamespace(cuda="12.8"),
            cuda=SimpleNamespace(is_available=lambda: True),
        )
        gsplat_module = SimpleNamespace(
            __file__="/workspace/thirdparty/sam3/.venv/lib/python3.12/site-packages/gsplat/__init__.py"
        )
        gsplat_distribution = SimpleNamespace(
            version="1.5.3",
            locate_file=lambda name: Path(
                "/opt/supersplat/.venv/lib/python3.12/site-packages"
            ),
            read_text=lambda name: json.dumps(
                {
                    "url": "https://github.com/nerfstudio-project/gsplat.git",
                    "vcs_info": {
                        "vcs": "git",
                        "commit_id": "77ab983ffe43420b2131669cb35776b883ca4c3c",
                    },
                }
            ),
        )

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("importlib.metadata.distribution", return_value=gsplat_distribution),
            patch("platform.python_version", return_value="3.12.12"),
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
            self.install_canonical_release(state)

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
            self.install_canonical_release(state)

            capability = state.capabilities(["https://editor.example"])["renderer"]

            self.assertEqual(capability["status"], "unavailable")
            self.assertIn("inspection failed", capability["message"])

    def test_readiness_rejects_a_noncanonical_release_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = CompanionState(
                Path(directory) / "state",
                contributor_renderer=StaticContributorRenderer({}),
                renderer_runtime=StaticRendererRuntime(
                    RendererRuntimeStatus.ready(cuda_version="12.8")
                ),
            )
            arbitrary_lock = Path(directory) / "uv.lock"
            arbitrary_lock.write_text("not the release lock\n", encoding="utf-8")
            state.install_release("0.1.0", arbitrary_lock)

            capability = state.capabilities(["https://editor.example"])["renderer"]

            self.assertEqual(capability["status"], "unavailable")
            self.assertIn("canonical Companion lock", capability["message"])


if __name__ == "__main__":
    unittest.main()

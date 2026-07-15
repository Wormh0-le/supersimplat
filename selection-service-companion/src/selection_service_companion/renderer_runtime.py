"""Locked runtime status for the optional gsplat/CUDA Contributor renderer."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from typing import Literal, Protocol


EXPECTED_PYTHON_VERSION = "3.12.12"
EXPECTED_OPERATING_SYSTEM = "Linux"
EXPECTED_TORCH_VERSION = "2.11.0+cu128"
EXPECTED_CUDA_VERSION = "12.8"
EXPECTED_GSPLAT_VERSION = "1.5.3"
EXPECTED_GSPLAT_SOURCE_URL = "https://github.com/nerfstudio-project/gsplat"
EXPECTED_GSPLAT_SOURCE_COMMIT = "77ab983ffe43420b2131669cb35776b883ca4c3c"
EXPECTED_RENDERER_LOCK_DIGEST = (
    "sha256:db8ecc6a07d4101012697d19728a588002c0680a105b0e7283841087b4b9105c"
)


@dataclass(frozen=True)
class RendererRuntimeStatus:
    """Whether the independently installed gsplat/CUDA runtime is usable."""

    status: Literal["ready", "unavailable"]
    cuda_version: str | None = None
    message: str | None = None

    @classmethod
    def ready(cls, *, cuda_version: str) -> "RendererRuntimeStatus":
        return cls(status="ready", cuda_version=cuda_version)

    @classmethod
    def unavailable(cls, message: str) -> "RendererRuntimeStatus":
        return cls(status="unavailable", message=message)


class RendererRuntime(Protocol):
    """The operator-owned runtime check behind the public readiness response."""

    def status(self) -> RendererRuntimeStatus:
        """Return the current independently installed runtime status."""


@dataclass(frozen=True)
class GsplatRuntimeFacts:
    """The non-secret facts required to verify one gsplat/CUDA installation."""

    environment_prefix: Path
    operating_system: str
    python_version: str
    torch_version: str | None
    cuda_version: str | None
    cuda_available: bool
    gsplat_version: str | None
    gsplat_source_url: str | None
    gsplat_source_commit: str | None
    torch_package_path: Path | None = None
    gsplat_package_path: Path | None = None
    gsplat_distribution_path: Path | None = None
    torch_inspection_error: str | None = None
    gsplat_inspection_error: str | None = None


class GsplatRuntimeInspection(Protocol):
    """Read process-local runtime facts without searching other environments."""

    def facts(self) -> GsplatRuntimeFacts:
        """Return facts about the current Companion process only."""


@dataclass(frozen=True)
class StaticGsplatRuntimeInspection:
    """A deterministic process inspection for readiness-contract tests."""

    runtime_facts: GsplatRuntimeFacts

    def facts(self) -> GsplatRuntimeFacts:
        return self.runtime_facts


class CurrentProcessGsplatInspection:
    """Inspect only packages importable by the running Companion process."""

    def facts(self) -> GsplatRuntimeFacts:
        torch_version: str | None = None
        cuda_version: str | None = None
        cuda_available = False
        torch_package_path: Path | None = None
        torch_inspection_error: str | None = None
        try:
            torch = importlib.import_module("torch")
            module_path = getattr(torch, "__file__", None)
            if isinstance(module_path, str):
                torch_package_path = Path(module_path)
            version = getattr(torch, "__version__", None)
            torch_version = str(version) if version is not None else None
            torch_cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
            cuda_version = (
                str(torch_cuda_version) if torch_cuda_version is not None else None
            )
            is_available = getattr(getattr(torch, "cuda", None), "is_available", None)
            cuda_available = bool(is_available()) if callable(is_available) else False
        # Optional binary packages can fail with extension-specific exceptions.
        # Readiness must fail closed instead of taking down /capabilities.
        except Exception as error:
            torch_inspection_error = type(error).__name__

        gsplat_version: str | None = None
        gsplat_source_url: str | None = None
        gsplat_source_commit: str | None = None
        gsplat_package_path: Path | None = None
        gsplat_distribution_path: Path | None = None
        gsplat_inspection_error: str | None = None
        try:
            gsplat = importlib.import_module("gsplat")
            module_path = getattr(gsplat, "__file__", None)
            if isinstance(module_path, str):
                gsplat_package_path = Path(module_path)
            distribution = importlib.metadata.distribution("gsplat")
            gsplat_distribution_path = Path(distribution.locate_file(""))
            gsplat_version = str(distribution.version)
            direct_url_text = distribution.read_text("direct_url.json")
            if direct_url_text is not None:
                direct_url = json.loads(direct_url_text)
                if isinstance(direct_url, dict):
                    url = direct_url.get("url")
                    if isinstance(url, str):
                        gsplat_source_url = url
                    vcs_info = direct_url.get("vcs_info")
                    if (
                        isinstance(vcs_info, dict)
                        and vcs_info.get("vcs") == "git"
                        and isinstance(vcs_info.get("commit_id"), str)
                    ):
                        gsplat_source_commit = vcs_info["commit_id"]
        except Exception as error:
            gsplat_inspection_error = type(error).__name__

        return GsplatRuntimeFacts(
            environment_prefix=Path(sys.prefix),
            operating_system=platform.system(),
            python_version=platform.python_version(),
            torch_version=torch_version,
            cuda_version=cuda_version,
            cuda_available=cuda_available,
            gsplat_version=gsplat_version,
            gsplat_source_url=gsplat_source_url,
            gsplat_source_commit=gsplat_source_commit,
            torch_package_path=torch_package_path,
            gsplat_package_path=gsplat_package_path,
            gsplat_distribution_path=gsplat_distribution_path,
            torch_inspection_error=torch_inspection_error,
            gsplat_inspection_error=gsplat_inspection_error,
        )


class GsplatRuntime:
    """Validate the fixed first-release gsplat/CUDA runtime baseline."""

    def __init__(self, inspection: GsplatRuntimeInspection) -> None:
        self._inspection = inspection

    def status(self) -> RendererRuntimeStatus:
        facts = self._inspection.facts()
        prefix_parts = facts.environment_prefix.parts
        if prefix_parts[-3:] == ("thirdparty", "sam3", ".venv"):
            return RendererRuntimeStatus.unavailable(
                "The gsplat/CUDA runtime must not use thirdparty/sam3/.venv; install the locked Companion runtime."
            )
        if facts.operating_system != EXPECTED_OPERATING_SYSTEM:
            return RendererRuntimeStatus.unavailable(
                f"The locked gsplat/CUDA runtime supports {EXPECTED_OPERATING_SYSTEM} only."
            )
        if facts.python_version != EXPECTED_PYTHON_VERSION:
            return RendererRuntimeStatus.unavailable(
                f"Python {EXPECTED_PYTHON_VERSION} is required for the locked gsplat/CUDA runtime."
            )
        if facts.torch_inspection_error is not None:
            return RendererRuntimeStatus.unavailable(
                f"PyTorch runtime inspection failed ({facts.torch_inspection_error})."
            )
        if facts.torch_version != EXPECTED_TORCH_VERSION:
            return RendererRuntimeStatus.unavailable(
                f"PyTorch {EXPECTED_TORCH_VERSION} is required for the locked gsplat/CUDA runtime."
            )
        if facts.gsplat_inspection_error is not None:
            return RendererRuntimeStatus.unavailable(
                f"gsplat runtime inspection failed ({facts.gsplat_inspection_error})."
            )
        if facts.cuda_version != EXPECTED_CUDA_VERSION or not facts.cuda_available:
            return RendererRuntimeStatus.unavailable(
                f"CUDA {EXPECTED_CUDA_VERSION} must be available to the locked gsplat runtime."
            )
        if facts.gsplat_version != EXPECTED_GSPLAT_VERSION:
            return RendererRuntimeStatus.unavailable(
                f"gsplat {EXPECTED_GSPLAT_VERSION} is required for the locked Companion runtime."
            )
        if _normalise_source_url(facts.gsplat_source_url) != EXPECTED_GSPLAT_SOURCE_URL:
            return RendererRuntimeStatus.unavailable(
                "gsplat must be installed from the locked Git source, not an unpinned local source."
            )
        if facts.gsplat_source_commit != EXPECTED_GSPLAT_SOURCE_COMMIT:
            return RendererRuntimeStatus.unavailable(
                "gsplat must be installed from the locked source commit."
            )
        for package_name, package_path in (
            ("PyTorch", facts.torch_package_path),
            ("gsplat", facts.gsplat_package_path),
            ("gsplat metadata", facts.gsplat_distribution_path),
        ):
            if package_path is None or not _is_within(
                package_path, facts.environment_prefix
            ):
                return RendererRuntimeStatus.unavailable(
                    f"{package_name} must be installed inside the Companion runtime; packages outside it are not used."
                )
        return RendererRuntimeStatus.ready(cuda_version=EXPECTED_CUDA_VERSION)


@dataclass(frozen=True)
class StaticRendererRuntime:
    """A fixed runtime status for tests and an initially unavailable default."""

    runtime_status: RendererRuntimeStatus

    def status(self) -> RendererRuntimeStatus:
        return self.runtime_status


def current_renderer_runtime() -> GsplatRuntime:
    """Create the runtime verifier used by a production Companion process."""

    return GsplatRuntime(CurrentProcessGsplatInspection())


def _normalise_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    return value.removeprefix("git+").rstrip("/").removesuffix(".git")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True

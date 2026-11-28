# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Build ForeRSI's private terminal as part of its Python distribution."""

import os
import tomllib
from collections.abc import Sequence
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools_rust import Binding, RustExtension
from setuptools_rust.build import build_rust


class DataDistribution(Distribution):
    """Expose installed data to setuptools' editable-wheel command."""

    def has_data(self) -> bool:
        """Bridge editable_wheel's has_data probe to the standard data-files predicate."""
        return self.has_data_files()


class BuildTerminalData(build_rust):
    """Install the native executable as wheel data, including in editable mode."""

    def install_extension(
        self,
        ext: RustExtension,
        dylib_paths: Sequence[tuple[str, str]],
        build_artifact_dir: Path | None,
    ) -> None:
        """Give Cargo's executable to the standard installer without copying into src."""
        self.distribution.data_files.append(
            (f"libexec/{self.distribution.get_name()}", [path for _, path in dylib_paths])
        )


class PlatformWheel(bdist_wheel):
    """Keep the native platform tag without imposing a CPython ABI on the executable."""

    def get_tag(self) -> tuple[str, str, str]:
        """Return the platform-specific, Python-ABI-independent wheel tag."""
        _, _, platform = super().get_tag()
        return "py3", "none", platform


root = Path(__file__).parent
with (root / "pyproject.toml").open("rb") as source:
    project = tomllib.load(source)["project"]
with (root / "terminal/rust-toolchain.toml").open("rb") as source:
    toolchain = tomllib.load(source)["toolchain"]["channel"]

# Cargo owns compilation; wheel data installs the private executable in both
# regular and editable environments. Only project.scripts adds a PATH command.
setup(
    distclass=DataDistribution,
    data_files=[("libexec/fore-rsi", [
        "terminal/src/integration/assets/pi/herdr-agent-state.ts",
        # Saved terminal panes may still replay these extension paths from an earlier installation.
        "src/fore_rsi/rsi_workflows/agent_runtimes/pi/tool_mcp.ts",
        "src/fore_rsi/rsi_workflows/agent_runtimes/pi/ipc.ts",
        "src/fore_rsi/rsi_workflows/agent_runtimes/tool_stdio.py",
    ])],
    rust_extensions=[
        RustExtension(
            target="_terminal",
            path=str(root / "terminal/Cargo.toml"),
            binding=Binding.Exec,
            cargo_manifest_args=[
                "--locked",
                "--config", str(root / "terminal/.cargo/config.toml"),
            ],
            env={
                **os.environ,
                "RUSTUP_TOOLCHAIN": os.environ.get("RUSTUP_TOOLCHAIN") or toolchain,
                "FORE_RSI_VERSION": project["version"],
            },
        ),
    ],
    cmdclass={"bdist_wheel": PlatformWheel, "build_rust": BuildTerminalData},
)

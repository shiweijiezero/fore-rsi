#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Prepare Zig and the vendored Ghostty package cache for Cargo."""

from __future__ import annotations

import argparse
import errno
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import URLError
import urllib.request
import zipfile


def main() -> None:
    """Print the compiler and Zig global-cache paths for the Cargo build script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Cargo host triple")
    parser.add_argument("--version", required=True, help="Compiler version selected by the build script")
    parser.add_argument("--vendor-dir", required=True, type=Path, help="Vendored libghostty-vt directory")
    parser.add_argument("--zig", type=Path, help="Use an existing compiler instead of the cached one")
    args = parser.parse_args()

    architecture, system = host_platform(args.host)
    directory = f"zig-{architecture}-{system}-{args.version}"
    destination = cache_directory() / directory
    executable = args.zig or destination / ("zig.exe" if system == "windows" else "zig")
    if args.zig is None and not executable.is_file():
        archive_suffix = "zip" if system == "windows" else "tar.xz"
        url = f"https://ziglang.org/download/{args.version}/{directory}.{archive_suffix}"
        print(f"Downloading Zig {args.version} for {architecture}-{system}", file=sys.stderr)
        install_compiler(url, destination)
    if not executable.is_file():
        raise SystemExit(f"Zig executable does not exist: {executable}")

    global_cache = destination.parent / f"{directory}-global-cache"
    prepare_dependencies(executable, args.vendor_dir, global_cache)
    print(executable)
    print(global_cache)


def host_platform(host: str) -> tuple[str, str]:
    """Select an official compiler archive for the machine running Cargo."""
    architecture = host.split("-", 1)[0]
    if architecture not in {"aarch64", "x86_64"}:
        raise SystemExit(f"No Zig download configured for host {host}")
    if host.endswith("apple-darwin"):
        return architecture, "macos"
    if host.endswith(("linux-gnu", "linux-musl")):
        return architecture, "linux"
    if host.endswith(("windows-msvc", "windows-gnu")):
        return architecture, "windows"
    raise SystemExit(f"No Zig download configured for host {host}")


def cache_directory() -> Path:
    """Keep downloaded toolchains outside the source checkout."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return (base / "fore-rsi" / "zig").resolve()


def download_file(url: str, destination: Path) -> None:
    """Download a file through a temporary path so partial files are never reused."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.{attempt}")
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "ForeRSI terminal dependency bootstrap"},
            )
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
            return
        except (OSError, URLError) as error:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            print(f"download attempt {attempt + 1} failed; retrying: {error}", file=sys.stderr)


def install_compiler(url: str, destination: Path) -> None:
    """Extract an official archive and atomically publish the complete toolchain."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory(prefix="zig-", dir=destination.parent) as temporary:
                staging = Path(temporary)
                archive = staging / url.rsplit("/", 1)[-1]
                download_file(url, archive)
                extracted = staging / "extracted"
                extracted.mkdir()
                if archive.suffix == ".zip":
                    with zipfile.ZipFile(archive) as handle:
                        handle.extractall(extracted)
                else:
                    with tarfile.open(archive, "r:xz") as handle:
                        for member in handle.getmembers():
                            target = (extracted / member.name).resolve()
                            if not (member.isfile() or member.isdir()) or not target.is_relative_to(extracted):
                                raise ValueError(f"Unsupported path in Zig archive: {member.name}")
                        handle.extractall(extracted)
                installation = extracted / destination.name
                executable = installation / ("zig.exe" if os.name == "nt" else "zig")
                if not executable.is_file():
                    raise FileNotFoundError(f"Zig archive does not contain {executable.name}")
                try:
                    installation.rename(destination)
                except OSError as error:
                    if error.errno not in {errno.EEXIST, errno.ENOTEMPTY} or not (destination / executable.name).is_file():
                        raise
                return
        except (OSError, EOFError, tarfile.TarError, URLError, ValueError) as error:
            last_error = error
            if attempt == 2:
                raise
            print(f"Zig extraction attempt {attempt + 1} failed; retrying: {error}", file=sys.stderr)
    raise RuntimeError(f"Zig installation failed: {last_error}")


def archive_url(url: str) -> tuple[str, str]:
    """Map a package URL to a local-download URL and stable cache filename."""
    if url.startswith("git+https://github.com/"):
        repository, commit = url[len("git+https://github.com/") :].rsplit("#", 1)
        repository = repository.removesuffix(".git")
        name = repository.rsplit("/", 1)[-1]
        return f"https://codeload.github.com/{repository}/tar.gz/{commit}", f"{name}-{commit}.tar.gz"
    return url, url.rsplit("/", 1)[-1].split("?", 1)[0]


def dependency_urls(vendor_dir: Path) -> list[str]:
    """Collect URLs from the top-level and already materialized nested packages."""
    manifests = sorted(vendor_dir.rglob("build.zig.zon"))
    return sorted({
        url
        for manifest in manifests
        for url in re.findall(r'(?m)^(?!\s*//)\s*\.url\s*=\s*"([^"]+)"', manifest.read_text())
    })


def prepare_dependencies(zig: Path, vendor_dir: Path, global_cache: Path) -> None:
    """Recursively prefetch Ghostty packages before Zig builds the vendored source."""
    manifest = global_cache / "fore-rsi-dependencies.txt"
    downloads = global_cache / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    processed: set[str] = set()
    if manifest.is_file():
        processed.update(line for line in manifest.read_text().splitlines() if line)

    while True:
        urls = dependency_urls(vendor_dir)
        pending = [url for url in urls if url not in processed]
        if not pending:
            manifest.write_text("\n".join(urls) + "\n")
            return
        for url in pending:
            download, filename = archive_url(url)
            archive = downloads / filename
            if not archive.is_file():
                print(f"Downloading terminal dependency {filename}", file=sys.stderr)
                download_file(download, archive)
            subprocess.run(
                [str(zig), "fetch", "--global-cache-dir", str(global_cache), str(archive)],
                check=True,
                cwd=vendor_dir,
                stdout=subprocess.DEVNULL,
            )
            processed.add(url)


if __name__ == "__main__":
    main()

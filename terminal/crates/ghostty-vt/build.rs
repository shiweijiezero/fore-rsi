// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Herdr and ForeRSI projects

//! Builds the vendored terminal library, preparing its host Zig compiler when absent.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const ZIG_VERSION: &str = "0.16.0";

fn zig_target(target: &str) -> &str {
    match target {
        "x86_64-unknown-linux-gnu" => "x86_64-linux-gnu",
        "aarch64-unknown-linux-gnu" => "aarch64-linux-gnu",
        "x86_64-unknown-linux-musl" => "x86_64-linux-musl",
        "aarch64-unknown-linux-musl" => "aarch64-linux-musl",
        "x86_64-apple-darwin" => "x86_64-macos",
        "aarch64-apple-darwin" => "aarch64-macos",
        "aarch64-apple-ios" => "aarch64-ios",
        "aarch64-apple-ios-sim" => "aarch64-ios-simulator",
        "x86_64-pc-windows-msvc" => "x86_64-windows-msvc",
        "aarch64-pc-windows-msvc" => "aarch64-windows-msvc",
        other => panic!("unsupported target for libghostty-vt build: {other}"),
    }
}

fn env_bool(name: &str) -> Option<bool> {
    match env::var(name) {
        Ok(value) => match value.to_ascii_lowercase().as_str() {
            "1" | "true" | "yes" | "on" => Some(true),
            "0" | "false" | "no" | "off" => Some(false),
            other => panic!("invalid boolean value for {name}: {other}"),
        },
        Err(env::VarError::NotPresent) => None,
        Err(err) => panic!("failed to read {name}: {err}"),
    }
}

fn zig_version(command: &str) -> Option<String> {
    let output = Command::new(command).arg("version").output().ok()?;
    output
        .status
        .success()
        .then(|| String::from_utf8_lossy(&output.stdout).trim().to_owned())
}

/// Reuse or prepare the host compiler and its vendored package cache.
fn resolve_zig(manifest_dir: &Path, vendor_dir: &Path, host: &str) -> (String, PathBuf) {
    let bootstrap = manifest_dir.join("../../scripts/ensure_zig.py");
    let mut args = vec![
        "-I".to_owned(),
        bootstrap.display().to_string(),
        "--host".to_owned(),
        host.to_owned(),
        "--version".to_owned(),
        ZIG_VERSION.to_owned(),
        "--vendor-dir".to_owned(),
        vendor_dir.join("libghostty-vt").display().to_string(),
    ];
    if let Ok(explicit) = env::var("ZIG") {
        assert_eq!(
            zig_version(&explicit).as_deref(),
            Some(ZIG_VERSION),
            "ZIG must point to Zig {ZIG_VERSION}: {explicit}"
        );
        args.extend(["--zig".to_owned(), explicit]);
    } else if let Some(system) = (zig_version("zig").as_deref() == Some(ZIG_VERSION))
        .then(|| "zig".to_owned())
    {
        args.extend(["--zig".to_owned(), system]);
    }
    for python in ["python3", "python"] {
        let output = match Command::new(python)
            .args(&args)
            .stderr(Stdio::inherit())
            .output()
        {
            Ok(output) => output,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => panic!("could not start terminal toolchain preparation: {error}"),
        };
        assert!(
            output.status.success(),
            "automatic terminal toolchain preparation failed: {}",
            output.status
        );
        let stdout = String::from_utf8(output.stdout)
            .expect("terminal toolchain preparation returned non-UTF-8 output");
        let lines = stdout
            .lines()
            .map(str::trim)
            .filter(|line| !line.is_empty())
            .collect::<Vec<_>>();
        assert!(lines.len() >= 2, "terminal toolchain preparation returned incomplete paths");
        let zig = lines[0].to_owned();
        assert_eq!(
            zig_version(&zig).as_deref(),
            Some(ZIG_VERSION),
            "invalid prepared Zig compiler: {zig}"
        );
        return (zig, PathBuf::from(lines[1]));
    }
    panic!("Python 3 is required to automatically prepare Zig {ZIG_VERSION}");
}

fn main() {
    // The vendored source stays at the repository root, shared with its maintenance scripts.
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let vendor_dir = manifest_dir.join("../../vendor");
    let vendored_dir = vendor_dir.join("libghostty-vt");

    println!("cargo:rerun-if-changed=build.rs");
    for path in [
        vendor_dir.join("libghostty-vt.vendor.json"),
        vendored_dir.join("build.zig"),
        vendored_dir.join("build.zig.zon"),
        vendored_dir.join("include"),
        vendored_dir.join("pkg"),
        vendored_dir.join("src"),
        vendored_dir.join("VERSION"),
    ] {
        println!("cargo:rerun-if-changed={}", path.display());
    }
    println!("cargo:rerun-if-env-changed=LIBGHOSTTY_VT_OPTIMIZE");
    println!("cargo:rerun-if-env-changed=LIBGHOSTTY_VT_SIMD");
    println!("cargo:rerun-if-env-changed=LIBGHOSTTY_VT_ZIG_SYSTEM_DIR");
    println!("cargo:rerun-if-env-changed=ZIG");
    println!("cargo:rerun-if-changed=../../scripts/ensure_zig.py");
    println!("cargo:rerun-if-env-changed=LIBGHOSTTY_VT_WINDOWS_LIBC");

    let optimize = env::var("LIBGHOSTTY_VT_OPTIMIZE").unwrap_or_else(|_| "ReleaseFast".into());
    let simd = env_bool("LIBGHOSTTY_VT_SIMD").unwrap_or(true);
    let target = env::var("TARGET").expect("TARGET");
    let zig_target = zig_target(&target);
    let version_string = fs::read_to_string(vendored_dir.join("VERSION"))
        .expect("failed to read vendored libghostty-vt VERSION")
        .trim()
        .to_string();

    // Install into this build's OUT_DIR so concurrent builds for different targets
    // from one checkout never link each other's archive.
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    let zig_prefix = out_dir.join("zig-out");

    let host = env::var("HOST").expect("HOST");
    let (zig, zig_global_cache) = resolve_zig(&manifest_dir, &vendor_dir, &host);
    let mut command = Command::new(&zig);
    command.env("ZIG_GLOBAL_CACHE_DIR", zig_global_cache);
    command
        .arg("build")
        .arg("--prefix")
        .arg(&zig_prefix)
        .arg("-Demit-lib-vt")
        .arg(format!("-Doptimize={optimize}"))
        .arg(format!("-Dsimd={simd}"))
        .arg(format!("-Dtarget={zig_target}"))
        .arg(format!("-Dversion-string={version_string}"))
        .arg("-Demit-xcframework=false");
    if target.ends_with("windows-msvc") {
        if let Some(libc_file) = env::var_os("LIBGHOSTTY_VT_WINDOWS_LIBC") {
            println!(
                "cargo:rerun-if-changed={}",
                PathBuf::from(&libc_file).display()
            );
            command.arg("--libc").arg(libc_file);
        }
    }
    if let Ok(system_dir) = env::var("LIBGHOSTTY_VT_ZIG_SYSTEM_DIR") {
        command.arg("--system").arg(system_dir);
    }

    let status = command
        .current_dir(&vendored_dir)
        .status()
        .unwrap_or_else(|err| {
            panic!("failed to execute {zig:?} for vendored libghostty-vt: {err}")
        });
    assert!(
        status.success(),
        "Zig {ZIG_VERSION} build for vendored libghostty-vt failed: {status}"
    );

    let mut lib_dir = zig_prefix.join("lib");
    if target.contains("-apple-") {
        // Apple's linker prefers the sibling dylib for `-l`, so search a directory
        // holding only the static archive.
        let static_dir = out_dir.join("lib");
        fs::create_dir_all(&static_dir).expect("failed to create libghostty-vt link directory");
        fs::copy(
            lib_dir.join("libghostty-vt.a"),
            static_dir.join("libghostty-vt.a"),
        )
        .expect("failed to copy libghostty-vt static archive");
        lib_dir = static_dir;
    }
    println!("cargo:rustc-link-search=native={}", lib_dir.display());
    if target.contains("windows-msvc") {
        println!("cargo:rustc-link-lib=static=ghostty-vt-static");
    } else {
        println!("cargo:rustc-link-lib=static=ghostty-vt");
    }
}

#!/usr/bin/env python3
"""Provider-free qualification using a supplied octet checkout's real Rust host.

No package installation or source-tree writes: Cargo runs offline in a new private
work directory, reusing only its registry cache. See docs/native-host-check.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import tomllib
import wave


PROBE = r'''
use octet_agent::extension_process::{
    discover_extension_manifests, ExtensionCatalog, ExtensionExecutionContext,
    ExtensionHostState, ExtensionPolicy, ExtensionProcess, ExtensionRoot,
    ExtensionRuntimeConfig, ExtensionRuntimeError, ExtensionSource,
};
use serde_json::json;
use std::{path::PathBuf, time::Duration};

#[tokio::main]
async fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let package = PathBuf::from(&args[0]).canonicalize().unwrap();
    let workspace = PathBuf::from(&args[1]).canonicalize().unwrap();
    let source = workspace.join("tone.wav");
    assert_ne!(package, workspace);
    assert!(!workspace.join("extension.py").exists());
    let (inputs, _) = discover_extension_manifests(&[ExtensionRoot {
        directory: package.parent().unwrap().to_path_buf(),
        source: ExtensionSource::Explicit,
    }]);
    // Other children of the supplied parent are metadata-only; never activate them.
    let input = inputs.into_iter()
        .find(|i| i.path == package.join("extension.toml"))
        .expect("requested extension discovered by its actual parent directory");
    let mut config = ExtensionRuntimeConfig::new(&workspace);
    config.request_timeout = Duration::from_secs(10);
    config.tool_call_timeout = Duration::from_secs(30);
    config.supervise = false;
    let off = ExtensionCatalog::load_resolved(
        [input.clone()], &ExtensionPolicy::default(), 256 * 1024);
    assert!(off.diagnostics.is_empty(), "{:?}", off.diagnostics);
    let descriptor = off.extensions.into_iter().next().unwrap();
    assert_eq!(descriptor.manifest.name, "octet-ableton");
    assert!(!descriptor.activation.enabled);
    assert!(matches!(ExtensionProcess::start(descriptor, config.clone()).await,
        Err(ExtensionRuntimeError::Disabled(_))));
    println!("PASS discovery_disabled_by_default");

    let mut policy = ExtensionPolicy::default();
    policy.enable("octet-ableton"); // In-memory only; no user configuration writes.
    let on = ExtensionCatalog::load_resolved([input], &policy, 256 * 1024);
    assert!(on.diagnostics.is_empty(), "{:?}", on.diagnostics);
    let process = ExtensionProcess::start(on.extensions.into_iter().next().unwrap(), config)
        .await.expect("native host launch and initialization");
    assert_eq!(process.api_version(), "0.4");
    for feature in ["request_cancellation", "content_parts"] {
        assert!(process.negotiated_features().contains(feature));
    }
    let mut tools: Vec<_> = process.tool_definitions().iter().map(|t| t.name.clone()).collect();
    tools.sort();
    assert_eq!(tools, ["ableton_compose", "ableton_listen", "ableton_live_object_model"]);
    let commands = process.command_definitions();
    assert_eq!(commands.len(), 1);
    assert_eq!(commands[0].name, "ableton");
    let generation = process.health_snapshot().generation;
    println!("PASS native_launcher_arbitrary_cwd_api04_three_tools_one_command");

    // Deserialize the public wire context so additive optional host fields stay absent.
    let context: ExtensionExecutionContext = serde_json::from_value(json!({
        "workspace": workspace, "execution_scope": null, "resource_owner": null,
        "host": ExtensionHostState::default(),
    })).unwrap();
    let help = process.execute_command("ableton", vec!["help".into()], context.clone())
        .await.expect("help command");
    assert!(help.text.contains("Three tools"));
    println!("PASS help_command_no_bridge_contact");

    let output = process.call_tool("ableton_listen", json!({
        "file_path": source, "include_session_state": false,
        "slices": [{"start_sec": 0, "end_sec": 0.25}],
    }), context.clone()).await.expect("file audio tool response");
    assert!(!output.is_error, "{}", output.content);
    let data: serde_json::Value = serde_json::from_str(&output.content).unwrap();
    assert_eq!(data["source"], "file");
    assert_eq!(data["slice_paths"].as_array().unwrap().len(), 1);
    assert!(data["slices"][0]["telemetry"].is_object());
    let mp3 = PathBuf::from(data["slice_paths"][0].as_str().unwrap());
    assert_eq!(mp3.extension().unwrap(), "mp3");
    let bytes = std::fs::metadata(&mp3).unwrap().len();
    assert!(bytes > 0 && bytes <= 110 * 1024);
    // Retain the generated preview outside the generation-owned scratch lifecycle.
    std::fs::copy(&mp3, workspace.join("preview.mp3")).unwrap();
    std::fs::write(workspace.join("audio-result.json"),
        serde_json::to_vec_pretty(&data).unwrap()).unwrap();
    println!("PASS synthetic_wav_file_audio_mp3_and_telemetry");

    let invalid = process.call_tool("ableton_listen", json!({
        "file_path": source, "include_session_state": false, "slices": [],
    }), context.clone()).await.expect("malformed arguments return a tool error");
    assert!(invalid.is_error);
    assert!(invalid.content.contains("slices"));
    let unknown = process.call_tool("ableton_listen", json!({
        "file_path": source, "unexpected": true,
        "slices": [{"start_sec": 0, "end_sec": 0.25}],
    }), context.clone()).await.expect("unknown argument returns a tool error");
    assert!(unknown.is_error);
    println!("PASS malformed_arguments_rejected");
    let again = process.execute_command("ableton", vec!["help".into()], context)
        .await.expect("subsequent command");
    assert!(again.text.contains("Three tools"));
    assert_eq!(process.health_snapshot().generation, generation);
    assert!(process.is_running());
    println!("PASS same_generation_responsive_after_errors");
    assert!(process.shutdown().await, "shutdown must acknowledge AND exit gracefully");
    assert!(!process.is_running());
    println!("PASS shutdown_acknowledged_and_exited");
}
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, *, cwd, env, log, timeout):
    """Bound a subprocess group, retaining diagnostics without dumping environment."""
    with log.open("w") as stream:
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            stream.write(f"\nTIMEOUT after {timeout}s\n")
            return 124


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octet-source", type=Path, required=True,
                        help="reviewed octet source checkout (not the installed binary)")
    parser.add_argument("--extension-dir", type=Path, required=True,
                        help="octet-ableton source root containing extension.toml")
    parser.add_argument("--work-dir", type=Path,
                        help="new directory to retain probe, build logs and evidence")
    parser.add_argument("--build-timeout", type=int, default=600)
    parser.add_argument("--run-timeout", type=int, default=60)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("this runner currently qualifies POSIX process-group cleanup only")
    if args.build_timeout <= 0 or args.run_timeout <= 0:
        parser.error("timeouts must be positive")
    host = args.octet_source.resolve(strict=True)
    extension = args.extension_dir.resolve(strict=True)
    for path in [host / "crates/octet-agent/Cargo.toml", host / "Cargo.lock",
                 extension / "extension.toml", extension / ".venv/bin/python"]:
        if not path.is_file():
            parser.error(f"required file missing: {path}")
    for tool in ["cargo", "rustc", "ffmpeg", "ffprobe"]:
        if shutil.which(tool) is None:
            parser.error(f"required executable missing: {tool}")
    if args.work_dir:
        work = args.work_dir.absolute()
        work.mkdir(mode=0o700, parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="octet-ableton-native-"))
    work = work.resolve()
    print(f"Evidence directory: {work}", flush=True)
    for name in ["home", "tmp", "cargo-home", "probe/src", "workspace"]:
        (work / name).mkdir(parents=True, mode=0o700)
    # No Cargo config/credentials or native octet provider settings are copied.
    cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
    (work / "cargo-home/registry").symlink_to(cargo_home / "registry", target_is_directory=True)
    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(work / "home"),
           "TMPDIR": str(work / "tmp"), "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    # Resolve rustup proxies before changing HOME; consult toolchains, not auth.
    def rust_binary(name):
        binary = Path(shutil.which(name)).resolve()
        if binary.name == "rustup":
            toolchain_env = dict(env, RUSTUP_HOME=os.environ.get(
                "RUSTUP_HOME", str(Path.home() / ".rustup")))
            binary = Path(subprocess.check_output(
                [str(binary), "which", name], cwd=work, env=toolchain_env,
                timeout=10, text=True).strip())
        return str(binary)

    cargo = rust_binary("cargo")
    rustc = rust_binary("rustc")
    build_env = dict(env, CARGO_HOME=str(work / "cargo-home"), RUSTC=rustc,
                     CARGO_TARGET_DIR=str(work / "target"), CARGO_BUILD_JOBS="2")
    manifest = f'''[package]
name = "octet-ableton-native-smoke"
version = "0.0.0"
edition = "2021"
[workspace]
[profile.dev]
debug = 0
incremental = false
[dependencies]
octet-agent = {{ path = {json.dumps(str(host / "crates/octet-agent"))} }}
serde_json = "1"
tokio = {{ version = "1", features = ["macros", "rt-multi-thread", "time"] }}
'''
    (work / "probe/Cargo.toml").write_text(manifest)
    (work / "probe/src/main.rs").write_text(PROBE)
    shutil.copyfile(host / "Cargo.lock", work / "probe/Cargo.lock")
    with wave.open(str(work / "workspace/tone.wav"), "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", round(5000 * math.sin(2 * math.pi * 440 * n / 48000)))
                                 for n in range(12000)))
    report = {
        "host_version": tomllib.loads((host / "Cargo.toml").read_text())["workspace"]["package"]["version"],
        "host_source": str(host), "extension_dir": str(extension),
        "platform": platform.platform(), "started_unix": time.time(),
        "host_lock_sha256": digest(host / "Cargo.lock"),
        "extension_manifest_sha256": digest(extension / "extension.toml"),
        "probe_sha256": digest(work / "probe/src/main.rs"),
        "native_cancellation": "not exercised; see existing raw SDK cancellation test",
    }
    report["rustc"] = subprocess.check_output([rustc, "--version"], env=env, timeout=10, text=True).strip()
    report["cargo"] = subprocess.check_output([cargo, "--version"], env=env, timeout=10, text=True).strip()
    report["build_exit"] = run(
        [cargo, "build", "--offline", "--manifest-path", str(work / "probe/Cargo.toml")],
        cwd=work, env=build_env, log=work / "build.log", timeout=args.build_timeout)
    if report["build_exit"] == 0:
        report["run_exit"] = run(
            [str(work / "target/debug/octet-ableton-native-smoke"), str(extension), str(work / "workspace")],
            cwd=work / "workspace", env=env, log=work / "run.log", timeout=args.run_timeout)
        print((work / "run.log").read_text()[-8000:], end="")
    else:
        print("Build failed; last diagnostics:")
        print((work / "build.log").read_text()[-8000:])
    report["finished_unix"] = time.time()
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report.get("run_exit") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

# Native host qualification (provider-free)

## Result

**Passed on macOS arm64, 2026-11-14**, against the supplied octet working-tree
`octet-agent` **0.10.4**, using its real Rust `ExtensionProcess` (not a mock
JSON-RPC peer). This qualifies the native library boundary, not a published
release, CLI/TUI session, provider audio ingestion, or Ableton Live integration.

The runner is `scripts/host_smoke.py`. It generates a small temporary Cargo
project referencing `--octet-source/crates/octet-agent`, without adding a
production dependency or modifying either source checkout.

```sh
python3 scripts/host_smoke.py \
  --octet-source /absolute/path/to/octet \
  --extension-dir /absolute/path/to/octet-ableton \
  --work-dir /tmp/octet-ableton-native-check \
  --build-timeout 600 --run-timeout 60
```

`--extension-dir` means this extension's source root, **not its parent**. The
probe passes its parent to octet's discovery API, selects only this manifest,
and explicitly enables only `octet-ableton` in memory. `--work-dir` must not
exist; omit it to allocate a new private temporary directory. Evidence and build
outputs are retained there, not installed into octet. The script exits nonzero
on compile failure, timeout, or failed native assertions.

Prerequisites: Python 3.11+, the extension's existing `.venv` (`uv sync` separately
if needed), FFmpeg/FFprobe, Rust/Cargo, and cached dependencies for the reviewed
host checkout. Cargo builds **offline** with a separate target and Cargo home;
only the existing registry cache is linked. It copies the host lockfile into the
temporary project (Cargo updates that copy for the probe). It does not download
missing crates or change the source lockfile. Rustup proxies are resolved to the
installed toolchain before changing HOME; no default-toolchain setting is written.

## Probe assertions

The current runner expects `ableton_live_object_model` (Ableton Live Object Model).
Recorded native runs below predate this rename and used `ableton_lom`; the rename
has process-protocol regression coverage, but the Rust probe has not been rebuilt
or rerun for it. Previously compiled probes retain the old catalog assertion.

1. Native manifest discovery and catalog loading leave the extension disabled;
   attempting native startup returns `ExtensionRuntimeError::Disabled`.
2. Explicit in-memory enablement starts the actual manifest `run-extension`
   launcher with an unrelated, otherwise empty temporary workspace as cwd.
3. The native handshake admits exact API `0.4`, required cancellation/content
   features, exactly `ableton_listen`, `ableton_compose`, `ableton_live_object_model`, and the
   `ableton` command.
4. `/ableton help` succeeds without contacting any bridge.
5. `ableton_listen` processes a generated 0.25-second, 440 Hz mono PCM WAV through
   real FFmpeg and returns telemetry plus a nonempty bounded MP3. It explicitly
   sets `include_session_state: false`; no Live transport, capture device,
   composition, or LOM request is invoked.
6. Empty slices and an unknown argument produce tool errors. A subsequent help
   command succeeds in the same process generation (supervision disabled).
7. Native `shutdown()` confirms both acknowledgement **and timely process exit**;
   `is_running()` is false afterward.

The native runtime has no provider/secret service configured. Build and probe
subprocesses receive an allowlisted environment and private HOME/TMPDIR, without
provider variables, original octet configuration, Cargo credentials, or
PYTHONPATH. No setup command or audio-upload/read-to-model operation is run.

**Cancellation boundary:** the native handshake negotiates cancellation, but this
probe does not exercise a cancelled native request. The existing raw-SDK test
`tests/test_extension.py::ProcessSmoke.test_cancel_then_same_process_responds`
passed separately: an injected stalled bridge observes cancellation, returns
`-32800`, and the same extension process handles help afterward. This is not
native cancellation qualification. The check intentionally does not claim a Live
bridge port or contact an existing Live bridge to simulate a stall. OctetBridge now uses port 9878 to coexist with
Ableton MCP's port 9877.

## Recorded evidence

Successful local run directory:
`/private/tmp/octet-ableton-native-host-20261114-rerun/`

- `report.json`: host version/source path, platform, toolchain identities,
  manifest/host-lock/probe SHA-256, timestamps, build/run exit statuses (both 0).
- `build.log`: offline native compilation completed in 1m27s.
- `run.log`: seven `PASS` assertions listed above.
- `probe/{Cargo.toml,Cargo.lock,src/main.rs}`: exact generated test and resolution.
- `workspace/{tone.wav,preview.mp3,audio-result.json}`: synthetic input, copied
  preview, and returned analysis. Original generation-owned slice paths in the
  result are not promised to survive shutdown; the copied preview does.

The already-built native probe was also rerun against the final extension code
(after live capture/automation integration and the port change): all seven checks
passed again. Local evidence: `artifacts/qualification/native-final.UImxJo/run.log`.

Observed versions: Rust/Cargo 1.97.1, extension Python 3.14.4, NumPy 2.5.4,
FFmpeg 7.1.1, macOS 27.0 arm64. Independent `ffprobe` inspection of the copied
preview reported MP3, 48 kHz, one channel, 3,788 bytes, 0.288 seconds (MP3 frame
padding; the source analysis interval is 0.25 seconds).

Also passed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p test_extension.py -v
# 6 tests passed, including raw-SDK cancellation and real file-audio processing.
.venv/bin/ruff check scripts/host_smoke.py
# All checks passed.
```

An initial runner attempt in `/private/tmp/octet-ableton-native-host-20261114/`
failed before compilation because a rustup proxy lost its default toolchain under
private HOME. Resolving the installed toolchain explicitly fixed the runner;
the native extension itself required no changes. These are local working-tree
results, not cross-platform, full frontend, or live-set acceptance evidence.

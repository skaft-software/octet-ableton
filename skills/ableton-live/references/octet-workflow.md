# Execute through octet-ableton

## 1. Check the connected implementation

Use only tools actually present in the current catalog. The native extension supplies **Ableton Live Object Model** (`ableton_live_object_model`), `ableton_compose`, and `ableton_listen`. Host-qualified names may differ: use the exact registered identity and schema. `/ableton status` is a user-facing command, not a model tool; these views require bridge revision 2 or later; corrected start-before-seek playback and endpoint-checked capture require at least revision 4. Use revision 6 for capture from either playing or stopped transport. Missing tools or a revision mismatch are capability gaps: report them, not an excuse to fall back to MCP, build a harness, or install another integration.

### Compact inspection fast path

Start with `ableton_live_object_model` for transport, track/device identities and Arrangement clip counts, not a full snapshot or parameter-object dump:

```json
{"view":"session"}
```

Session defaults to the first 64 regular tracks; check `truncated` and `track_count`. To select others, supply `track_indices` (at most 64, indices 0–511). Session accepts only `view` and optional `track_indices`; it does not return clip details or return/master tracks.

After observing the actual target, discover only the needed parameter schema. The following indices/names are illustrative, not assumptions about the user's Set:

```json
{"view":"device","track_index":0,"device":"Filter","parameters":["Frequency",1],"fields":["name","min","max","is_quantized"]}
```

Device requires `track_index` (0–511) and `device` (integer 0–255 or exact unique name). `parameters` selects up to 256 exact names or integer indices (0–1023); numeric strings are names, not indices. Ambiguous names need a freshly observed index. Without selectors, use `offset` (0–1023) and `limit` (1–256, default 256), following `next_offset` until null. Never combine `parameters` with pagination.

`fields` is a unique projection from `name`, `min`, `max`, `value`, `is_enabled`, `is_quantized`, `display_value`, `automation_state`, `value_items`; defaults are `name` and `value`. Results use `columns` (always starting with `index`) and `rows`, not parameter objects. Zip columns to each row; null plus an `unavailable` entry is missing evidence, not a zero value. Narrow selectors/fields if output limits are reached.

Batch **1–16 independent reads** into one bridge call. Do not batch discovery with a query whose target depends on that discovery:

```json
{"queries":[{"view":"session","track_indices":[0]},{"view":"device","track_index":0,"device":"Filter","parameters":["Frequency",1],"fields":["value","is_enabled"]}]}
```

A batch contains only `queries`. Each query is a session/device view; inspect every `results` entry's `ok` and `result` or `error`, even if others succeeded. These are sequential reads, not an atomic snapshot. Never mix `queries`, `view`, and `expression` modes.

### Reuse schema, never stale state

When the host exposes code mode, keep the discovered columns/rows as a small schema map in its session-local store, and return only task-relevant summaries to model context. Reuse names, ranges and quantization only while the same Set/device/parameter layout is verified. Do not invent a code-mode API if none is available; ordinary native calls suffice.

Invalidate cached schema after Set changes/reloads, reconnects, device replacement/loading, preset or rack/mapping changes, or changed names/counts/ranges; rediscover when identity is uncertain. Numeric indices are locations, not persistent IDs. Refresh session indices after structural edits, and refresh selected mutable `value`, `is_enabled`, `automation_state` or display fields before edits and after verification. A schema cache must not cache current values, transport or clip state.

Use legacy `expression` only for bounded facts not exposed by these views (for example a specific clip's notes or routing labels). It permits public `song`/`app` paths and small literal containers, not calls, assignments, imports, private attributes or Python execution. Refine truncated reads; never infer that omitted data means an absent object.

## 2. Coordinate contract

- Track/device indices are zero-based. A new track's `ref` and subsequent `track_ref` last for **one batch only**. After structural edits, reconcile track order before using indices.
- Bars are one-based. Beats are zero-based **quarter notes**, not necessarily the denominator's note value. MIDI note start/duration and device envelope points are clip-relative quarter notes; clip placement is arrangement-relative.
- For a constant meter `n/d`, `q = n * 4 / d` beats per bar; `start_beat = (start_bar - 1) * q`; `length_beats = length_bars * q`.
- For a constant-tempo audio file, `seconds = origin_sec + beat * 60 / tempo`. Ends are exclusive. File `tempo` is the file's known tempo, not automatically the Set's. A pickup changes the origin; inspect it rather than guessing.
- Example: constant 7/8 has `q = 3.5`; bar 5 begins at beat 14, which is seven seconds after bar 1 at 120 BPM. Constant 6/8 has three quarter notes per bar.
- The extension's bar mapping uses the current/simulated signature; it does **not** reconstruct historical meter/tempo automation. For a variable map, first establish actual beat positions from Live. Do not treat current BPM as an exact whole-song seconds conversion.

## 3. Compose safely

`ableton_compose` accepts at most 64 sequential actions. `dry_run` defaults to `true`. Preflight can defer checks until newly created objects exist, so a valid preview is not a guarantee every write will succeed. Batches are **not transactions**, even if changes are grouped for undo.

Supported operation names:

| Operation | Inputs and checks |
| --- | --- |
| `create_midi_track`, `create_audio_track` | Optional name and batch-local ref; inspect resulting index. Choose MIDI for an instrument, audio for recorded/imported sound. |
| `duplicate_track` | Existing target; can change following indices. Use when preserving a working source matters. |
| `load_device_or_preset` | Exact `query` or `name`; optionally `root` from `instruments`, `audio_effects`, `midi_effects`, `user_library`. Recursive preset search needs a root and an unambiguous result. Check device availability/edition first. |
| `set_device_params` | `device` name/index and `params` keyed by parameter name or decimal index. Use observed min/max and actual Live units; quantized choices are not free continuous values. |
| `set_track_controls` | Name, RGB color, raw `volume` **or** `volume_db`, pan, indexed sends and exact input/output routing type/channel labels. Do not assume raw volume is a dB conversion. Check available channels after changing routing type. |
| `write_arrangement_midi_clip` | `start_bar` or `start_beat`, `length_bars` or `length_beats`; notes use `pitch`, `start_beat`, `duration_beats`, `velocity`, optional `mute` and `probability`. Probability requires the modern note API. Check clip bounds and same-track occupied destinations. |
| `place_audio_clip` | Absolute approved local `path`, start in bars or beats; optional name, gain, pitch coarse/fine and `warp_mode`. Requires Live's audio import API (12.0.5+) and an empty Session staging slot. The imported length comes from Live; do not invent an unsupported length argument. |
| `set_transport` | BPM, signature, playback, loop and playhead/loop bounds. Explicit playhead plus `playing:true` starts playback first, then seeks to that position, without moving the Arrangement Insert Marker. These are immediate state changes, not a written tempo/meter automation map. Preserve state unrelated to the task. |

A MIDI-only preview example (deliberately no assumed instrument or audio output):

```json
{
  "dry_run": true,
  "actions": [
    {"op": "create_midi_track", "name": "Sketch", "ref": "sketch"},
    {"op": "write_arrangement_midi_clip", "track_ref": "sketch",
     "start_beat": 0, "length_beats": 4,
     "notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1, "velocity": 90}]}
  ]
}
```

Keep default `detail: "summary"`: inspect compact counts, failures, deferred checks and `receipt_path`. Full receipts remain in that local file; read it only when reconciling uncertain actions or needing per-action detail. Use `detail: "full"` only when inline receipts are actually needed, never replay an applied batch merely to get more detail. Summary counts alone do not prove every requested change succeeded.

Apply with `dry_run: false` only after approval/scope and preview checks. A MIDI clip on a track without an instrument or external MIDI destination will not produce audio. Inspect the real browser/device choice before adding one; do not assume the example is an auditioned musical result.

### Device envelopes

Clip placement can take `envelopes.device_params`, each with a `device`, `param` and `points` (`beat`, `value`, optional `curve`). The first point is at beat zero; values must lie in the inspected target parameter range. `curve` describes the segment **arriving at that point**: `step` by default, or `ramp` rasterized at 96 steps per quarter note. This is not a continuous/Bezier curve API. Quantized parameters cannot use continuous ramps.

Envelopes are staged on a temporary Session clip before Arrangement duplication. This does not establish general in-place editing of existing Arrangement envelopes. MIDI pitch-bend and CC envelope writes are not exposed here; an exposed instrument parameter may be an alternative only if it preserves the user's intent. Do not equate that substitution with per-note MPE.

### Unsupported operations

The operation catalog above does not expose arbitrary Session clip launching, Warp Marker editing, freeze/flatten, bounce, comping, stem separation, export, saving Sets, arbitrary note transformations, MPE curves, browser downloads, or hardware configuration. Their UI procedures elsewhere in this skill remain useful, but require another explicitly available and authorized surface or a user-performed step. Do not infer a tool from a documented Live feature.

## 4. Listen without overclaiming

- File-duration checks allow one output sample of ffprobe metadata rounding, but decoding must still cover all requested frames; genuinely truncated previews are rejected.
- Local-file slices use seconds **or** bars, not both. File bars need a known constant tempo; default signature is 4/4 and origin is zero only when correct for that file.
- Live slices use bars and require explicit working loopback routing. Default capture input is exactly `BlackHole 2ch` on macOS or `CABLE Output (VB-Audio Virtual Cable)` on Windows. Route Live playback to **CABLE Input** on Windows. Use `/ableton devices` for renamed endpoints; never substitute a microphone. Driver/routing setup needs the user's authorization.
- At most four slices per call, each at most eight seconds **and** eight bars. A musically short passage can still exceed the seconds limit at low tempo.
- Omit `solo_tracks` to preserve current solos. An empty list temporarily clears solos; supplied indices request temporary isolation. Live recording and Session overrides must be stopped/resolved before timeline capture.
- Transport and solos are intended to be restored after capture, including cancellation. Verify after failures; capture restoration does not undo prior composition edits.
- Revision 4 starts playback before seeking, but its same-tick Stop/Continue during restoration can leave Live stopped. Revision 5 uses Stop/Play then seeks to the saved beat when resuming. Revision 6 checks the playing flag only for resume: Stop can be queued until the next Live tick. Revision 3 and later check the ending playhead against the requested origin and Live's elapsed playback time before producing a preview. Mismatches, incomplete ranges or missing timing reject it after cleanup. Inspect `capture.playback` diagnostics; this coarse check is not sample-accurate verification. Off-origin captures made by older scripts may be mislabeled and need re-capturing after update/restart.
- Optional `latency_ms` compensates a measured loopback delay. Zero means uncalibrated, not zero actual latency. Tempo/meter changes invalidate the constant map. Other applications on the loopback bus can contaminate the preview.
For a direct audition, request only the desired slices with `attach_audio: true`. After capture, Octet asks before attaching those MP3s in request order to the active model. Declining keeps them local; do not then read them without permission. Attachment requires host artifact support and an audio-capable model route for ingestion. The default returns local paths and measurements only.

- `ableton_listen` returns local `slice_paths`; it does not automatically upload audio. Keep `include_session_state` omitted/false; inspect with `view: "session"` instead unless a full snapshot is genuinely needed. Read only the selected short previews, together when independent, into an explicitly approved audio-capable model route. Do not read the whole source or all generated slices by default. Measurements are decoded-PCM levels before MP3 encoding. Pitch candidates and energy-cell transients are estimates, not proven key, fundamental, instrument identity or sample-accurate timing. Silence may be represented by null dBFS.

## 5. Recover and verify

On a failed/partial/cancelled/lost compose response: stop writes; retain receipts; inspect the actual Set; determine which objects now exist and what changed; rebuild a preview for missing/corrective work only. Don't reuse old batch refs or blindly replay track creation. Coordinate undo with the user's intervening edits rather than assuming one undo is safe.

For success, compare the actual destination, clip duration, notes/envelopes, parameter/routing values and transport with the intended plan. Listen only within the permission boundary. A fake-API test, a dry-run receipt and an actual Live audition are three different kinds of evidence.

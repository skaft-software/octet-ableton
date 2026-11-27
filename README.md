# octet-ableton

Make music with an audio-capable model in [octet](https://github.com/skaft-software/octet): hear a reference, build a part in Ableton Live, then listen back.

**Unofficial, MIT-licensed, hobby software under Skaft Software.** Not affiliated with or endorsed by Ableton. Ableton and Live are trademarks of Ableton AG. No MCP server, extra skill installation, usage tracking, or automatic audio uploads.

## Three tools

- **`ableton_listen`** — slice local audio **or record Live bar ranges through loopback**, with levels, spectral bands, pitch candidates and energy gaps. Live previews restore the previous transport/solo state, including on cancellation; a Live-side timeout guard handles a vanished client.
- **`ableton_compose`** — batch track creation, device loading, parameters, Arrangement MIDI/audio, device automation, mixer/routing and transport changes.
- **Ableton Live Object Model** (`ableton_live_object_model`) — compact session/device views, projected parameter tables, and up to 16 reads per bridge call; legacy read-only expressions remain supported.

The intended loop is **listen → read selected previews together → compose → listen back**. The audio-capable model judges timbre/groove; measurements and Live state handle coordinates and levels. No guaranteed turn count or quota claim.

## Windows: compose for a game with Kontakt / Spectres

Use native Windows Octet (extension API 0.4), Python 3.11+ on PATH, Git, uv, and Ableton Live 12. For listening, put FFmpeg 6+ (with DirectShow and `libmp3lame`) and ffprobe on PATH. You can capture short Arrangement ranges directly through VB-CABLE or listen to an exported WAV without a virtual driver.

In a **non-elevated PowerShell**, clone into a dedicated extensions directory. Start Octet from your game workspace so its project context stays there:

```powershell
$extensions = "$HOME\MusicTools\extensions"
git clone https://github.com/skaft-software/octet-ableton.git "$extensions\octet-ableton"
uv sync --locked --project "$extensions\octet-ableton"
# Run from your game workspace:
octet --extension-dir "$extensions" --enable-extension octet-ableton --skill-dir "$extensions\octet-ableton\skills"
```

1. Run `/ableton setup` and check the proposed destination against Live's **Settings → Library → Location of User Library** before confirming. For a custom library, supply its quoted absolute path. Save your Set, restart Live, select **OctetBridge** as a Control Surface with Input/Output **None**, then check `/ableton status` for revision **6**. The bridge token stays in your Windows user profile with a user-only file ACL; do not copy a token from another machine.
2. In a disposable Set, create a MIDI track, load your **locally licensed Kontakt and Spectres** patch, and name the track `Spectres`. Expose any plug-in parameters you want to automate to Live. Save the Set as a template. The extension writes MIDI to the track; it does not install the library, browse Kontakt's internal presets, or assume macro names.
3. Give Octet a bounded cue brief, for example: *Inspect the Spectres track. Preview an eight-bar exploration loop in an empty range: a low D pedal with a sparse E-flat pulse, then two bars of silence for a game transition. Show me the notes and placement before applying. Leave the tempo and other tracks alone.*
4. For direct playback previews, route the cue through **VB-CABLE** as described below. Alternatively, export a WAV in Live and pass its absolute path to `ableton_listen` with a short seconds range. Use `attach_audio: true` only if you approve sharing that preview with your model provider. No audio, Kontakt assets or game projects are included in this repository.

To update, `git -C "$extensions\octet-ableton" pull --ff-only`, repeat `uv sync --locked --project "$extensions\octet-ableton"`, and `/reload` in Octet. If the bridge revision changes, repeat setup and restart Live.

### Route Live to VB-CABLE on Windows

1. Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) separately if needed and follow its restart instructions. Leave your Windows default playback device alone so other apps are not mixed into the preview.
2. In Live's **Settings → Audio**, note your current output so you can restore it. Select **CABLE Input (VB-Audio Virtual Cable)** as the **playback/output** device. If your interface's ASIO driver doesn't expose the cable, select **MME/DirectX** and the cable output there, or keep ASIO and audition an exported WAV. Send the track through Main to that stereo output. Do not monitor the cable's recording endpoint back into the cable.
3. In Octet run `/ableton devices`. The **recording/input** endpoint to capture is **`CABLE Output (VB-Audio Virtual Cable)`** — the opposite end of the cable, not `CABLE Input`. That's the exact Windows default. If it is renamed or localized, pass the exact listed loopback `name` as `device`. An absent or duplicate name fails; no system-default or microphone fallback.
4. Put a known sounding clip at bar 1 in a disposable Arrangement. Stop recording, then call `ableton_listen` with `{"slices":[{"start_bar":1,"end_bar":2}]}` (one bar at 120 BPM). Check `capture.device`, `capture.transport_restored` and `telemetry.peak_dbfs`. Play the local MP3 to confirm it contains your clip. Silence is not a routing pass: check Live's Main meter, the Windows recording meter for **CABLE Output**, and that the chosen bars actually contain audio. Restore your original output when done.

The Windows smoke workflow exercises DirectShow discovery and the recorder/encoder with a synthetic signal. It does **not** run Live, install a virtual driver, or verify a physical machine's routing or latency.

## Setup (macOS)

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), FFmpeg with `libmp3lame`, Ableton Live (12 recommended), and an octet host with extension API 0.4. The MIT source SDK is bundled; no unpublished PyPI SDK dependency.

```sh
# Inside this checkout, named octet-ableton:
uv sync --locked
# Install FFmpeg separately if missing: brew install ffmpeg

octet --extension-dir .. --enable-extension octet-ableton --skill-dir ./skills
```

`--extension-dir` takes the **parent** containing `octet-ableton`. Enablement may persist in octet's configuration. This is source installation, not a published extension bundle.

In octet:

1. `/ableton setup` or `/extensions` → octet-ableton → Install / update.
2. Confirm copying the Remote Script into `~/Music/Ableton/User Library/Remote Scripts/OctetBridge`. Updates retain backups in `~/.config/octet-ableton/script-backups/`, outside Live's script scan. A custom absolute User Library path can follow `setup`.
3. Restart Live; select **OctetBridge** in **Settings → Tempo & MIDI → Control Surface** (older versions: Link, Tempo & MIDI). Input/Output: **None**.
4. `/ableton status` checks connection, bridge revision and FFmpeg. `/ableton devices` lists capture devices.

After updating the checkout, run `/reload` in octet to reload the extension. This does not update the Remote Script in Live. If `/ableton status` reports an old revision, run `/ableton setup`, save your Set, and restart Live. Check that `/ableton status` reports bridge revision **6** before testing capture restoration.

The inspection tool was renamed from `ableton_lom` to `ableton_live_object_model`. Run `/reload` in octet after updating; this name-only change needs no Remote Script reinstall or Live restart. Existing scripts must use the new name after reload.

The bridge uses **127.0.0.1:9878**, deliberately separate from Ableton MCP's 9877. The private token is in `~/.config/octet-ableton/bridge.json` (0600). Setup never changes a Live set or your audio routing.

### Live listening

Install BlackHole 2ch separately if needed (`brew install blackhole-2ch`), then route Live's output to it. To hear playback yourself too, create a Multi-Output Device in Audio MIDI Setup with your headphones and BlackHole, and select that as Live's output.

The extension **never falls back to a microphone**, never installs a driver silently, and never changes routing for you. On macOS capture defaults to the exact device `BlackHole 2ch`; `device` can select another explicitly named loopback input. Other audio routed to that device will also be captured.

```json
{
  "slices": [{"label": "answer", "start_bar": 6, "end_bar": 8, "solo_tracks": [3]}]
}
```

For a direct audition, request only the desired slices with `attach_audio: true`. After capture, Octet asks before attaching those MP3s in request order to the active model. Declining keeps them local; do not then read them without permission. Attachment requires host artifact support and an audio-capable model route for ingestion. The default returns local paths and measurements only.

`include_session_state` defaults to **false**: file listening makes no bridge call, and Live capture reads only transport metadata. Opt in for the full snapshot, or use the compact session view below. Omit `solo_tracks` to preserve the current solo mix; `[]` temporarily clears solos. Recording and Session overrides must be stopped before timeline capture. Returned MP3s persist for `read`; raw capture files are cleaned up. Cancellation is not rollback of prior composition edits.

Revision 4 starts playback **before** seeking to the requested capture origin, and revision 5 uses Play rather than Continue before restoring a previously playing transport's saved position. Revision 6 checks `is_playing` immediately after resuming, but not after requesting Stop: on Live 12.4.16 the stopped flag can lag by one tick. A Stop exception still fails restoration. Live can ignore seeks made while stopped when either Play or Continue is called, so capture does not rely on the Arrangement Insert Marker or cached stopped position. Before exporting a preview, it compares the ending playhead with the requested origin plus Live's actual elapsed playback time, including latency compensation and cleanup/dispatch delays. Tolerance is 250 ms of transport time, capped at half a quarter-note beat. A mismatch, incomplete range or missing endpoint timing rejects the preview after restoration instead of silently labeling audio from the wrong bars. Returned `capture.playback` contains the observed/expected endpoint and tolerance. This is a sanity check, not sample-accurate or continuous-position verification.

## Reference listening

```json
{
  "file_path": "/absolute/path/reference.mp3",
  "tempo": 155,
  "slices": [
    {"label": "A", "start_bar": 6, "end_bar": 10},
    {"label": "B", "start_bar": 32, "end_bar": 36}
  ]
}
```

Up to four slices; each at most **eight seconds and eight bars**. File slices use seconds **or** bars, never both. Bar ends are exclusive. File bar ranges require known constant `tempo`; `signature` defaults to `[4,4]`, `origin_sec` to 0. Live slices use bars and query Live's current tempo/meter. Beats mean quarter notes, including in compound meters.

File-duration preflight allows one output sample (1/48000 second) of ffprobe metadata rounding. Decoding must still produce every requested frame; previews are never padded or silently shortened to cover an overrun.

Levels are measured on decoded PCM before MP3 encoding. Transients are energy-cell estimates, not sample-accurate kick/snare detections. Pitch candidates are prominent spectral peaks, **not guaranteed f0 or key**. Unknown file tempo is not guessed. Silence uses JSON `null` dBFS. A mono-preview fallback avoids near-total opposite-phase stereo cancellation.

**Loopback alignment is approximate:** device and FFmpeg buffering are not calibrated. Optional `latency_ms` compensates a *measured* loopback delay; zero does not mean zero latency. Tempo/meter changes detected during capture reject the constant-tempo map; complex automation is not modeled. This is preview capture, not a sample-accurate render API.

Reading the returned previews sends audio to your chosen model provider and retains it in session history. Use only audio approved for that provider. The extension itself makes no audio/model API calls.

## Batch composition

[`examples/answer.json`](examples/answer.json) builds an Operator/Redux phrase on a new track. It is a technical example, not a claimed finished musical result.

- `dry_run` defaults to `true`; set `false` to apply.
- `detail` defaults to `"summary"`: counts, created tracks, arrangement span, failures and a `receipt_path`. Set `"detail":"full"` for all receipts inline. Receipt files are private and generation-owned; copy them before host cleanup if needed. Failed/possibly applied actions remain visible in compact output. Receipt-time indices can change after later insertions.
- New tracks can declare `ref`; later actions use `track_ref`. References last **only for that batch**. Otherwise `track_index` is zero-based and follows the evolving track list.
- `load_device_or_preset`: exact `query` or `name`; optional `root` (`instruments`, `audio_effects`, `midi_effects`, `user_library`). Exact top-level devices load directly; recursive presets require a root and an unambiguous bounded search.
- `set_device_params`: `device` name/index and `params` map keyed by parameter name or decimal index. Values are actual Live `min`/`max` units, **not arbitrary normalized fractions**.
- Create/duplicate tracks and `set_track_controls`: `name`, RGB `color`, raw `volume` or `volume_db`, `pan`, `sends` (`{"0": 0.2}`), exact `input_routing_type`, `input_routing_channel`, `output_routing_type`, `output_routing_channel`. dB conversion uses Live's display conversion, not an invented linear scale.
- `write_arrangement_midi_clip`: `start_bar`/`length_bars` or `start_beat`/`length_beats`; notes have `pitch`, clip-relative `start_beat`, `duration_beats`, `velocity`, optional `mute`/`probability`. Probability requires Live's modern note API.
- `place_audio_clip`: absolute `path`, `start_bar` or `start_beat`, optional `gain`, `pitch_coarse`, `pitch_fine`, `warp_mode` (`beats`, `tones`, `texture`, `repitch`, `complex`, `complex_pro`). Needs an empty Session slot and Live's audio import API (12.0.5+); temporary staging clips are cleaned up.
- `set_transport`: `bpm`, `playing`, `loop`, playhead/loop start/length in bars or beats, signature numerator/denominator. With an explicit playhead and `playing:true`, playback starts first, then seeks to that position without changing the Arrangement Insert Marker. Play-only retains Live's normal start behavior.

Both clip-placement operations accept device envelopes:

```json
{"envelopes":{"device_params":[{"device":"Auto Filter","param":"Frequency","points":[{"beat":0,"value":0.35},{"beat":2,"value":0.75,"curve":"ramp"}]}]}}
```

This example assumes the 0..1 domain observed in Live 12.4's Auto Filter; always inspect your device first. First point is at beat zero; values use the target's actual units. `curve` describes the segment **arriving** at that point: default `step`, or a ramp rasterized at 96 steps per quarter note. Envelopes are written to a temporary Session clip before Arrangement duplication. Continuous/Bezier interpolation is not claimed.

**MIDI pitch-bend/CC envelope writes are not exposed by the verified API used here.** They fail explicitly; automate an exposed synth pitch parameter instead. No arbitrary Python execution or fake internal-resampling fallback is provided.

## Fast inspection and feedback

Start with `{"view":"session"}` in `ableton_live_object_model` for track names, devices, parameter counts and Arrangement clip counts—without parameter dumps. Then use observed indices in one projected batch:

```json
{"queries":[
  {"view":"device","track_index":0,"device":0,"fields":["name","min","max","is_quantized"]},
  {"view":"device","track_index":1,"device":"Auto Filter","parameters":["Frequency","Resonance"],"fields":["name","value"]}
]}
```

Device results use `columns`/`rows`, defaulting to index/name/value. One query can discover all 195 Operator parameters; larger devices paginate with `offset`/`limit` (default/max 256). Up to 16 queries execute sequentially on Live's main thread in **one bridge call**. Batch results preserve per-query errors; unavailable parameter fields return null plus a diagnostic instead of losing the whole result. No mutable values are cached.

Retain a discovered schema in code-mode `store` for the active device/version, invalidate it after device changes, and read current values before editing. Legacy `{"expression":"song.tracks[0].devices[0].parameters"}` still works; selectors permit public attribute/index paths and small literal containers, never calls, assignments, imports or private attributes.

All three tools return `metrics.elapsed_ms`, attempted `bridge_calls`, and UTF-8 `payload_bytes` **before metrics**. These are local execution measurements, not provider tokens, billed usage or model reasoning time. Prefer readiness → batched inspection → compose → targeted verification/capture; avoid repeated full snapshots. [Efficiency changes and evidence](docs/efficiency.md).

## Bundled Live skill

[`skills/ableton-live`](skills/ableton-live/SKILL.md) provides self-contained Live 12 workflows and on-demand topic guides for production, devices, troubleshooting and delivery. It distinguishes Live UI features from this extension's supported operations. No original manual, extracted source text or downloaded-PDF dependency is included.

The source-launch command above exposes the bundled skill with `--skill-dir ./skills`; inspect it in `/skills`. A managed extension bundle discovers `skills/*/SKILL.md` automatically as skill candidates, not as automatically executed instructions. No manifest tool or permission changes are needed.

A read-only, standard-library helper can locate documentation shipped with installed Live versions without copying, downloading or opening it:

```sh
python3 skills/ableton-live/scripts/find_live_docs.py
```

Discovery may return no documents, and multiple installations require matching the version actually in use. [Coverage, evaluation evidence and maintainer notes](docs/live-skill/README.md).

## Tests and qualification

```sh
uv run python -m unittest discover -s tests -v
uv run ruff check .
```

- **Automated tests cover:** synthetic audio, fake Live operations, real FFmpeg recording/encoding, loopback orchestration, automation staging, transport restoration, cancellation, protocol behavior, bundled-skill contracts and installed-document discovery.
- **Real octet native host passed:** discovery, arbitrary-cwd launcher, API 0.4, file-audio tool, errors, responsiveness and shutdown. [Evidence and rerun](docs/native-host-check.md).
- **Real BlackHole recording passed:** frames recorded and decoded; no test signal was playing, so this does not establish Live signal routing.
- **Real Live composition passed:** the native octet host created six instrument tracks, 46 clips / 523 notes and 1,679 envelope steps in Live 12.4.16; playback meters and moving filter values were read back. This is not a subjective audition or a Live loopback-capture pass. Revision-2 compact session inspection also passed through the ordinary conversation's native tool. Audio-informed revision remains unqualified.

[Run the technical Live fixture and hand off to an audio-capable model](docs/qualification.md). Save a disposable set first. Batches stop on failure and report receipts; they are **not transactions**. Occupied Arrangement destinations are refused. Never blindly retry an uncertain/partly applied batch.

Extensions run with your OS permissions, not in a sandbox. Do not publish the bridge token, private audio, captures or Live projects. `artifacts/` and common audio/project files are gitignored. The bundled SDK remains byte-for-byte upstream, with its license and hashes under `vendor/`.

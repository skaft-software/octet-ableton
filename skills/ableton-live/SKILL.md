---
name: ableton-live
description: Operates and troubleshoots Ableton Live 12 with octet-ableton, covering Sets, Session and Arrangement, audio warping, MIDI/MPE/tuning, recording, routing, devices, racks, automation, mixing, export, controllers, Push, and performance. Use for Live how-to questions or music-production tasks using ableton_compose, ableton_live_object_model, and ableton_listen. Not for developing the extension, generic music history, or choosing a specialist mastering aesthetic such as Clip-to-Zero.
compatibility: Live 12; features vary by minor version, edition, Packs, platform, and installed devices. Execution requires the actual tool catalog or an authorized UI surface. Optional installed-document discovery uses Python 3.11+ with only its standard library.
metadata:
  version: "1.1.0"
---

# Ableton Live

Turn a musical or technical request into a verified Live operation. This skill is self-contained: load the relevant topic below, not every reference. Preserve the user's material and artistic intent. A UI feature is **not** evidence that the connected API can perform it.

## Default workflow

1. **Identify the outcome.** Separate explanation, diagnosis, production, performance, and delivery. For explanation, answer without changing Live. For an edit, identify the Set, affected tracks/clips/devices, range, intended result, and what must remain unchanged.
2. **Establish actual state.** Check the installed Live version/edition, active tool schemas, current tempo/meter, Session overrides, recording/transport, routing, and available devices only as relevant. Use revision-2 `ableton_live_object_model` with `view: "session"`, then `view: "device"` with selected `parameters` and projected `fields`; batch up to 16 independent views in `queries`. Cache schema only in available code mode, invalidate it when the Set/device/layout changes, and refresh mutable values and indices. See the execution reference for exact bounds. Do not assume every Live 12 installation includes later additions, Suite instruments, Max for Live, or a particular Pack.
3. **Choose the applicable procedure** from the router. Inspect both sides of cross-cutting tasks: warping plus tempo, recording plus monitoring, automation plus clip launch, portable saving plus plug-ins. Where a procedure says to click/use a Live control, it describes UI behavior—not an invented tool call.
4. **Protect and plan.** Use a named copy for major rearrangement, rendering/replacement, consolidation, sample processing, or destructive edits. Confirm destructive/outward-facing actions not already authorized. Specify source/destination, units, expected signal path and success checks. Avoid simultaneous writers to the same Set.
5. **Preview supported changes.** With `ableton_compose`, keep `dry_run: true` first; inspect errors and deferred checks. Read actual device names, parameter ranges and routing labels before writing. Keep compact compose receipts by default; consult `receipt_path` or request `detail: "full"` only when needed, never replay writes for extra detail. Do not translate an arbitrary normalized fraction into frequency, dB, or a quantized mode.
6. **Apply a small batch and reconcile.** Apply only the authorized scope, then inspect receipts **and** resulting Live state. A failed, cancelled or disconnected batch may have already changed the Set. Never blindly replay it. Re-query after track/clip insertion or duplication; indices and previous-batch references are not stable identities.
7. **Verify at the right level.** Confirm timing, note/envelope data, routing, and saved/exported files where applicable. Audition only if requested/authorized and the selected audio route supports it. An API success or meter reading does not prove the intended sound; do not claim hearing audio that was not ingested.
8. **Report briefly.** State what changed, what was verified, where the result lives, and remaining UI-only, version-dependent, unauditioned, or untested steps. Preserve editable originals and disclose approximations.

## Task router

| Intent or symptom | Load |
| --- | --- |
| Settings, browser/search/tags, Packs/Cloud, missing samples, Projects, saving, collection, portable delivery, audio/MIDI export | [Workspace, browser and files](references/workspace-browser-files.md) |
| Arrangement edits, scenes, Session overrides, clip start/loop, fades, tempo leaders, Warp Markers or Warp Modes | [Clips, timeline and warping](references/clips-warping.md) |
| Notes, probability, MIDI Tools, scales, MPE, audio-to-MIDI, grooves, tuning systems, launch modes or Follow Actions | [MIDI, tuning and launch](references/midi-tuning-launch.md) |
| Inputs/outputs, monitoring, feedback, buses, recording, Capture MIDI, bounce, comping or stem separation | [Routing, recording and mixing](references/routing-recording-mixing.md) |
| Device chains, plug-ins, freeze, racks/macros/zones, automation versus modulation, clip envelopes or video | [Devices, racks and automation](references/devices-racks-automation.md) |
| Choose or configure a stock audio effect; filtering, dynamics, distortion, delay, reverb, spectral processing or metering | [Audio effects](references/audio-effects.md) |
| Choose or configure a stock instrument/MIDI effect; synthesis, sampling, physical modeling or arpeggiation | [Instruments and MIDI effects](references/instruments-midi-effects.md) |
| Max devices, modulation mappings, MIDI ports/remote mapping or computer-key mappings | [Max and remote control](references/max-control.md) |
| Push 1/2, Link/MIDI sync/Tempo Follower, CPU/disk/latency, audio/MIDI fidelity, accessibility or shortcuts | [Performance and troubleshooting](references/performance-troubleshooting.md) |
| Translate a procedure into this extension's real calls, timing units, safety and supported-operation boundaries | [octet-ableton execution](references/octet-workflow.md) |
| Resolve a version-specific uncertainty using help already shipped with an installed Live | [Installed documentation discovery](references/installed-documentation.md) and [read-only locator](scripts/find_live_docs.py) |

## Critical distinctions

- **Set versus Project:** saving an `.als` does not embed every external sample or install a collaborator's plug-ins. Repair missing references, collect required media into the intended Project, and verify portability. Do not delete “unused” files without approval.
- **Session versus Arrangement:** they share tracks/devices. A launched Session clip can override its track's Arrangement. **Back to Arrangement** restores timeline playback; **Re-Enable Automation** restores manually overridden automation. Neither replaces the other.
- **Warp versus transpose:** choose a mode for the material. Re-Pitch couples speed and pitch; pitch-preserving time-stretch modes have different artifacts. A transient is not automatically a committed Warp Marker, and clip meter does not change the Set's meter.
- **Audio versus MIDI:** MIDI needs an instrument or an external sound source to produce sound. Audio-to-MIDI estimates events; stem separation estimates sources. Both need inspection/audition, not confidence claims from the command completing.
- **Automation versus modulation:** absolute parameter motion and relative clip modulation are different. MIDI CC and per-note MPE are not interchangeable with a device parameter envelope.
- **Monitoring versus recording:** arm, monitor state, input selection, transport/Session recording and hardware direct monitoring are distinct. Avoid duplicate monitoring and feedback before raising gain.
- **Musical position versus API units:** this extension uses one-based bars and zero-based quarter-note beats. In constant `n/d` meter, a bar is `n * 4 / d` quarter notes. Historical meter changes and tempo automation require a verified piecewise map; do not extrapolate the current meter across the whole Set.
- **Editable versus rendered:** freeze, bounce, flatten, consolidate and export have different source-retention and routing consequences. Select the least destructive operation that produces the requested result, and keep a recoverable source.
- **Live feature versus extension capability:** when no current tool supports an operation, use an authorized, freshly observed UI workflow or explain the manual step. Do not synthesize missing `ableton_*` operations, call methods through read-only LOM, edit `.als` internals, or silently switch to a different bridge.

## Evaluation assets

[Revision-2 audio-model trials](assets/eval-cases.json) extend the existing procedural evaluation with native-tool and audition cases. They are **not run**: structural/fake tests are not model-performance, real-Live or listening evidence. Manual-derived topic references and chapter provenance remain unchanged.

## Listening and verification boundary

Use `ableton_listen` only with approved material and an understood signal path. It returns short local previews with no automatic upload; read only chosen slices together after approval. Reading audio into the model sends it to the selected provider and may retain it in session history. Permission to edit a Set is not blanket approval to upload private audio. Live loopback capture is approximate and can include other applications routed to the same device; it is not an offline, sample-accurate final render. Use the user's ears when audio ingestion is unavailable.

For a direct audition, request only the desired slices with `attach_audio: true`. After capture, Octet asks before attaching those MP3s in request order to the active model. Declining keeps them local; do not then read them without permission. Attachment requires host artifact support and an audio-capable model route for ingestion. The default returns local paths and measurements only.

Before declaring completion, verify the requested result rather than checklist compliance: correct object/range, no accidental source replacement, intended playback source and envelope, plausible signal level, and the actual saved/exported artifact if delivery was requested.

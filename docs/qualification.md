# Live + audio-model qualification

## Queued Stop after capture — revision 6

The user tested revision 5 on Live 12.4.16: capture begun during playback returned to active playback with loop restored and temporary solos cleared. Starting from stopped, the saved playhead was restored and Live stopped by the next observation, but `capture_end` rejected the preview with `restore_errors: ["is_playing"]`.

Revision 6 checks the playing flag only when restoring active playback. For a stopped transport, success means Stop and the other restoration operations returned without error, not that a later tick was sampled. No sleep or retry is needed. Local regression tests cover queued Stop and a thrown Stop error. In a subsequent user-run macOS test, capture from stopped at 150 BPM returned the saved playhead, loop bounds and all 22 solo flags unchanged. Argon reported a direct 3.2-second native attachment without `read`; the captured range was silent, so this did not verify recognition of musical content. Windows Live/Kontakt has not been qualified.

## Playing transport after capture — revision 5

In a user-run revision-4 test on Live 12.4.16 (23-track Set, 162 BPM), off-origin capture and solo restoration worked, but a capture begun during playback returned to beat 20.8704 with the loop restored **and transport stopped**. The previews were auditioned via `read`; this does not qualify direct `attach_audio` delivery.

Revision 5 uses Play rather than Continue after Stop, seeks to the saved beat, and checks the playing flag before reporting restoration. The later revision-5 Live result is recorded above. The original qualification procedure was: save the Set, `/reload` Octet, run `/ableton setup`, restart Live and verify revision **5** in `/ableton status`. In a disposable Set, capture an off-origin region with temporary solos while transport is playing. Verify playback continues from the saved region and loop/solos are restored. Repeat from stopped and confirm it stays stopped.

## Start ordering and fractional-duration regression — revision 4

**User-observed Live 12.4.16 evidence:** in an 18-track, 85 BPM Set, revision 3's endpoint guard correctly rejected a bars 3–5 capture that resumed at cached beat 40.013 rather than requested beat 8. The user verified that starting playback first and seeking second works; `continue_playing()` after a stopped seek does not. A separate bars 1–3 capture passed that guard but failed the duration preflight: 271059 frames / 48000 = 5.6470625 seconds, while ffprobe reported 5.647062.

Revision 4 starts playback before seeking in capture and combined compose seek/play; restoration also resumes before seeking to the saved playing position. The Insert Marker is unchanged. The local audio-duration check allows one output sample of metadata rounding, but decoded coverage remains exact: an actual missing frame is rejected, not padded or silently trimmed. The endpoint guard is unchanged.

**Source checks:** 169 tests pass, including corrected fakes with distinct Insert Marker, current playhead and cached stopped positions; stopped/playing restoration; seek/play cancellation receipts; the reported endpoint mismatch; and real-FFmpeg 85 BPM file and synthetic-capture regressions. The earlier fakes did not model the cached stop position and gave false confidence in revision 3's start fix. These new changes have **not been installed or requalified in Live** by this coding pass. No Set, routing, host code or provider was changed.

To deploy: save the Set, `/reload` octet, run `/ableton setup` and confirm the update, restart Live, then check `/ableton status` reports revision **4**. On an approved disposable Set at 85 BPM, repeat bars 1–3 and 3–5 with the Insert Marker and last-stopped position elsewhere. Verify the heard sections, `capture.playback` diagnostics and restoration of stopped/playing transport and solos. Also verify a combined `playhead_bar` plus `playing:true` action. Do not automatically retry uncertain mutations.

## Earlier capture-position regression — revision 3

The user reported that revision-2 captures requested at bars 5–9, 17–21 and 21–25 all played bars 1–5. Setting the playhead before normal Play was insufficient: Live restarted from the Arrangement Insert Marker. Combined compose seek/play and resuming transport after capture had the same problem. Treat earlier off-origin capture labels as unreliable; do not use them as evidence of those sections' sound.

Revision 3 used `continue_playing()` after explicit positioning, including restoration. That ordering proved insufficient in the user's Live test above and is superseded by revision 4. `capture_end` adds a Live-side monotonic endpoint timestamp; the client checks `end_beat` against the requested start plus actual elapsed playback, and checks that the requested end was reached, before encoding/labeling any preview. This allows 250 ms of transport-time discrepancy capped at half a quarter-note beat, includes cleanup/latency overhead, and is not proof of sample-accurate audio alignment. Missing timing or mismatches reject the preview after transport cleanup. A revision-2 bridge cannot supply the required endpoint timestamp.

**Historical source checks:** 162 tests passed, including fakes that reproduce Live's Insert Marker reset, resume/stop/dry-run cases, the three reported wrong-origin ranges, endpoint timing/jitter, cleanup on rejection and cancellation, and a real-FFmpeg synthetic capture. Those checks did not establish that playback started at the requested position in Live. No audio routing, Set, host code or provider was changed.

The user subsequently confirmed that this guard catches wrong-region playback rather than returning mislabeled previews. Use the revision-4 deployment and retest instructions above.

## Earlier qualification boundary

Automated tests and the recorded native octet library smoke test pass. **Actual Live composition and automation playback have been verified; non-silent loopback capture and musical quality remain unqualified.** Real BlackHole input recording produced decodable frames but silence (no test signal).

In Live 12.4.16, the native extension created the authorized six-track sketch: 46 Arrangement clips, 523 notes and 1,679 envelope steps, with 57/57 main-batch actions completed. Playback meters and moving filter values were read back. These establish technical execution, not an audition. Local receipts and score: `artifacts/demo/`.

Bridge revision 2 has been loaded. Direct batched inspection of the six demo tracks, all 195 Operator parameters and 45 Auto Filter parameters passed. A subsequent ordinary-conversation native session read also passed and found six sketch tracks at indices 0–5; never reuse the earlier indices 22–27. The user reopened the saved sketch; no save or new musical mutation was performed during this check.

Group Tracks expose `arrangement_clips` but raise when it is read. Snapshot and batch preflight now skip that unsupported property on groups; clip placement onto groups is explicitly rejected. This regression-tested fix is installed and has been reloaded. Installer backups live outside Live's Remote Scripts directory so Live does not import them as scripts.

OctetBridge uses 9878 because Ableton MCP occupies 9877. Do not kill another listener or disable the existing MCP. Local connection evidence: `artifacts/qualification/live-connection.json`. The latest Live startup log reports system speakers as output, not a confirmed BlackHole signal path. Routing changes and provider audio submission still need approval.

The inspection tool has been renamed to `ableton_live_object_model` (Ableton Live Object Model); reload octet, not Live, for that catalog change. Earlier execution evidence used `ableton_lom`. Code-mode batching subsequently returned a broken-pipe error without a result; no writes were requested. Repeated audio-informed cycles and native cancellation/failure recovery remain pending.

## Technical fixture

1. Save your work. Create a **disposable new Live Set** in 4/4 at >=60 BPM. Operator is required (Live Suite).
2. Add an empty track named **OCTET QUALIFICATION ONLY**. This explicit marker guards the test; Live's documented API does not reliably provide a saved set name.
3. Enable OctetBridge as described in the README. Route output to BlackHole 2ch (or a Multi-Output Device containing it). Record the original routing and restore it afterward. Stop playback/recording and return to Arrangement playback.
4. Run from the extension checkout:

```sh
uv run python scripts/qualify_live.py \
  --apply --expect-marker 'OCTET QUALIFICATION ONLY' \
  --output artifacts/qualification/live-run-1
```

The output directory must be new. The runner adds **one uniquely named track** with Operator and Auto Filter, writes a two-bar phrase and filter sweep at bars **5–7** (deliberately away from bar 1), verifies clip placement/staging cleanup, captures the soloed track, verifies transport restoration and rejects silent audio. It does not delete existing tracks, save/overwrite the set, or upload anything. Leaving the fixture track makes inspection/recovery easier.

Read `report.json` even after failure. A failed reply may have applied edits: **do not automatically retry**. Check the named track and current Live state first. The report's `technical_result: passed` is still not a listening judgment or proof of exact envelope transfer; the latter needs visual inspection/listening. A non-silent capture can contain unrelated loopback audio, so use an otherwise quiet route.

## Audio-capable octet handoff

Start octet with this extension enabled and a provider/model supporting audio through `read`. Use only approved audio. Example task:

> Work only in my disposable qualification set. First check `/ableton status`. Run a read-only ableton_live_object_model inspection, then use ableton_listen to capture bars 5–7 of the qualification track (look up its current index). Read the returned preview. Confirm the notes and filter motion are audible, and explicitly separate what you hear from numerical telemetry. Make one authorized, reversible improvement on a new track, listen again, and compare. Do not claim unsupported MIDI pitch-bend/CC writing, exact loopback alignment, or automatic rollback. Stop and report any partial effects instead of retrying uncertain mutations. Do not touch other projects or publish audio.

Then test the intended creative workflow against a local reference:

1. Listen to 1–4 short reference slices with a known bar grid, and read all previews together.
2. State a brief musical intention grounded in what is heard; inspect only the device parameters needed.
3. Apply one batch on a new track (use actual Live parameter units).
4. Capture its bar range, read the preview, and decide **keep/revise/reject** by ear.
5. Report the model/provider, fixture, calls used, timing/bytes, audible defects, and whether restoration/cleanup worked. Do not infer a quota benefit from preview file size alone.

Check cancellation separately: cancel a live listen, then verify playback/loop/playhead/solo restoration and a responsive `/ableton status`. The recorder has bounded subprocess cleanup; the Live lease guard attempts restoration if the client vanishes. Native frontend cancellation and real Live lease expiry have not been qualified yet.

## Evidence to retain locally

- Test command/environment and `report.json` (no token).
- Preview MP3, screenshot of Arrangement/device automation, initial/final state.
- Audio-capable model's actual listening judgments and any revision comparison.
- Original audio routing and confirmation it was restored.

Keep these in ignored `artifacts/`; they may contain private music. There is no telemetry/automatic upload service. No subjective listening judgment has been made by the coding agent.

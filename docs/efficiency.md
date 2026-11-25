# Efficient native workflow

Implemented in bridge revision 2; extension API stays 0.4 with the same three tools. No new host, provider, MCP dependency or background agent framework.

## Changes

- `ableton_live_object_model {"view":"session"}`: transport and compact track/device/clip counts. Optional `track_indices` scopes it; `[]` reads transport without enumerating tracks/devices.
- `view: "device"`: exact track/device selectors, optional parameter names/indices and projected fields, returned as a compact `columns`/`rows` table. Defaults to index/name/value. Read all 195 Operator parameters at once; default/max page size is 256, larger devices use `offset`/`limit` and `next_offset`.
- `{queries: [...]}` batches up to 16 views into one authenticated bridge request. Syntax is prevalidated, reads are sequential on Live's main thread, ordinary read failures remain per-query, cancellation stops the request. Batch `ok` is false if any query fails; successful entries remain available.
- Unavailable parameter properties produce explicit diagnostics without discarding valid values. Legacy expression reads tolerate unavailable optional object-summary properties too; explicit unavailable selectors fail clearly. Native exception text is not exposed.
- `ableton_compose` defaults to compact counts, created-track receipts, Arrangement span and visible failures. Complete receipts live in private generation-owned scratch; `detail: "full"` returns them inline. Storage failure preserves inline receipts and warns that effects were not undone. Never replay a possibly applied mutation.
- `ableton_listen` defaults `include_session_state` to false. File listening no longer contacts Live unless requested. Live listening fetches only transport metadata by default; explicit true retains the prior full snapshot behavior.
- Every tool returns local `metrics`: wall-clock `elapsed_ms`, attempted `bridge_calls`, and UTF-8 `payload_bytes` excluding metrics themselves. These do not measure provider tokens, model latency, billing or subjective music quality.

## Use the actual session, not a harness

This development installation is registered at `~/.octet/extensions/octet-ableton`, with a source launcher referring to this checkout and its `.venv`. User config enables it. `/reload` is still required at the active octet frontend's idle boundary; editing config cannot inject tools into a running model turn. `/extensions status` shows the admitted catalog. Do not rebuild a Rust host to compose music.

The updated Remote Script has been installed with its prior version backed up. Save your sketch before restarting Live. `/ableton status` now distinguishes a connected old bridge from revision 2; connection alone does not establish that new inspection views are available. This change does not restart Live, alter routing or overwrite the sketch.

For other source installations, use the README's explicit extension-directory/enable command. This local registration is not a portable published bundle.

## Small loop

1. Check readiness once (bridge revision, loopback route, model audio support).
2. Read session plus the relevant device schemas in one batch. Request only useful fields.
3. Retain immutable schema data in the host's existing code-mode store. Revalidate after device/version changes; never treat cached values or old track indices as current state.
4. Compose in one bounded batch. Read compact receipts; expand the full artifact only for debugging.
5. Verify affected objects, capture only the relevant passage, and let an audio-capable model or the user audition it. Do not substitute meters for listening.

No hidden retry, fixed musical quality guarantee, or arbitrary call-count quota is introduced. Provider budgets and model-context accounting remain host-owned.

## Observed checks

- 146 repository tests pass, including new projected/batched inspection, optional-property failures, cancellation, compact/full receipts, storage-failure semantics and metrics tests.
- Ruff passes; all Remote Script files parse as Python 3.7.
- Reused the existing compiled native octet smoke probe against the **registered source launcher**, without a build: seven checks passed in a 1.07-second command. Evidence: `artifacts/qualification/registered-native.cdvFam/run.log`.
- Re-presented the recorded successful 57-action music-demo receipt using the same compact JSON encoding: **13,627 → 428 bytes (96.9% reduction)**. Evidence: `artifacts/qualification/efficiency-s1spkxfa/benchmark.json`. No Live mutations were rerun; this is a result-size measurement, not token savings or a musical speed benchmark.
- After restart, revision-2 reads succeeded against Live 12.4.16: a direct bridge batch returned six demo tracks, 195 Operator parameters and 45 Auto Filter parameters in one request (647 ms, 11,165 bytes). Ordinary-session native-tool exposure is now verified too: a compact session read returned the six sketch tracks at their new indices 0–5 (926.63 ms, one bridge call, 1,360 payload bytes).
- A subsequent code-mode batching attempt failed with `Broken pipe (os error 32)` before returning a result. No mutation was requested. Direct-tool success does not qualify code-mode stability; that path and actual audio-informed revision remain pending.
- The inspection tool is now named `ableton_live_object_model` (Ableton Live Object Model). Reload octet to refresh its catalog; the internal bridge method and revision are unchanged. Earlier evidence used the former name `ableton_lom`.

Codex source guidance was inspected at local revision `81b995a6c`: bounded discovery, selected output emission, cached schemas and distinct execution/context budgets. We adopted the domain-level patterns rather than copying its host architecture or experimental feature defaults.

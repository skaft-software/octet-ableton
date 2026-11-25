# Live skill evaluation

**Decision: provisional procedural package.** Structure and fixture checks pass. Limited read-only planning trials produced correct plans, but did **not** show an advantage over the no-skill baseline. No Live task execution or audio audition was performed for this skill.

## Original authoring checks (before the revision-2 update)

- Indexed all **43 chapters / 837 numbered subsections** of the 1,039-page authoring source. Nine topic evidence files account for every indexed section. Front matter, welcome and credits are identified rather than converted into artificial procedures.
- Runtime: a 56-line `SKILL.md`, **11 directly linked references**, and one optional standard-library locator. Nine references cover Live topics; two cover the actual extension contract and installed-document discovery.
- External `engineering-agent-skills` validator: **PASS, zero warnings**. Its output explicitly says behavioral/safety evaluations are not run by that validator.
- Repository suite: **124 tests passed** (`uv run python -m unittest discover -s tests -v`). This includes 16 locator tests and eight skill/contract/example tests. It does not qualify actual Live operations.
- `uv run ruff check .`: **all checks passed**.
- Documented JSON examples ran against the repository's fake Live implementation; operation names match both the extension schema and bridge catalog. The 7/8 example places bar 5 at quarter-note beat 14 with a 3.5-beat bar.
- Runtime/source independence: no source PDF, extracted chapters, images, private source paths or source-specific retrieval requirement in the skill. A case-folded 32-word contiguous-overlap scan across runtime Markdown and developer evidence found no matches against the privately extracted source. This is a copying-risk heuristic, not a semantic-completeness or legal-clearance test.

Source text and retrieval excerpts remain private authoring inputs, not distributed dependencies. Maintainer evidence uses logical `private-extraction:/` identifiers and fingerprints.

## Revision-2 update

The current skill describes compact session/device views, projected and batched reads, schema invalidation, fresh mutable state, compact receipts and selective approved audio. The inspection tool is named **Ableton Live Object Model** (`ableton_live_object_model`). Repository JSON examples run through actual validation with fake Live objects; the full suite now has **146 passing tests**, Ruff passes, and the structural validator passes with zero warnings.

Three new development/validation/holdout audio-model cases are in [the runtime evaluation supplement](../../skills/ableton-live/assets/eval-cases.json). They are **not run**. The previous worker timed out but left inspectable edits; the parent reviewed those files and reran the checks. No new comparative performance, audition or activation score is claimed.

The recorded planning results and hashes in `eval-results.json` describe the earlier skill snapshot, not this revision. The procedural case file now uses the renamed tool in its input premise; the recorded trial used `ableton_lom`. Original hashes and results are retained rather than relabeled as new executions. All 43 chapters / 837 subsections and their topic provenance remain intact.

## Installed-document locator

The helper was exercised on this macOS host. It found the installed **Ableton Live 12 Suite** application and its `Contents/LegalAndDocs/Docs` directory, but the directory was empty: **`no_candidates`**, no warnings, no truncation. This validates the ordinary absence path, not successful retrieval of a local manual. Installation metadata is not evidence of which Live process is running.

Fixtures cover macOS/Windows layouts, explicit roots, absent and multiple installations, malformed/oversized metadata, bounded traversal, and symlink/reparse handling. Native Windows execution is **not run**. The helper never reads document contents, changes Live, downloads anything or silently selects a version.

## Independent source review and corrections

A read-only reviewer inspected the entry point, all 11 references, locator and skill tests, then selectively checked primary passages. It did not inspect evaluation holdout questions. The reviewer hit a turn ceiling before returning prose and was resumed solely to report already-inspected findings; this interruption is retained in the results record.

Three cross-chapter inconsistencies were independently identified and then checked by the parent against the primary passages:

| Issue | Source evidence | Final treatment |
| --- | --- | --- |
| MIDI crop boundary | §8.11, p231 gives explicit loop-state rules; §10.7.1, p287 abbreviates them to the loop brace. | Use Start–End for unlooped clips and the earlier of clip/loop start through loop end for looped clips; protect pickups and verify retained notes on a copy. |
| Humanize range | §8.5.2, p224 says half a division; §10.5.9.7, p273 specifies a quarter before or after. | Express the explicit ±quarter-grid displacement, distinguishing its half-grid total span. |
| MPE tab shortcut | Ch12, p331 gives Alt/Option+3; Ch42, pp1015/1021 distinguishes editor focus from Alt/Option+Shift+3 tab selection. | Prefer the named Note Expression tab and verify installed bindings; do not equate focus with tab selection. |

Settings-label drift (`Tempo & MIDI` versus `Link, Tempo & MIDI`) is also qualified. The relevant evidence files record these reconciliations and previous/current artifact hashes. These are source-grounded corrections, **not measured Live behavior**. Review was selective, not an exhaustive independent verification of every device parameter, shortcut or illustration.

## Controlled development planning trial

Cases and rubric were written before substantial prose; see [eval-cases.json](eval-cases.json). Three cases cover pickup-aware drum warping, two independent playback/automation overrides, and uncertain partial-batch recovery in 7/8.

- Same configured model: **`codex/gpt-6-astra`**, inherited reasoning.
- Fresh worker per condition; only the read tool; identical task inputs and output instructions.
- Same ceilings: eight turns, 360 seconds, 12,000 output bytes; at most 450 words per case.
- **Baseline:** task inputs only. **RAG:** those inputs plus selected original-source pages. **Skill:** those inputs plus `SKILL.md` and relevant on-demand references.
- All conditions received the extension-contract premises in the third case. The RAG condition used parent-selected relevant pages, not an independently measured retrieval system.
- One response/repeat per condition, fixed run order. Parent source-grounded scoring, not blinded judging. Four binary checks per case; critical violations tracked separately.

| Condition | Warping | Overrides | Partial batch | Total | Critical violations observed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 4/4 | 4/4 | 4/4 | 12/12 | 0 |
| RAG | 4/4 | 4/4 | 4/4 | 12/12 | 0 |
| Skill | 4/4 | 4/4 | 4/4 | 12/12 | 0 |

The development skill trial preceded the source-review corrections; separate input and final-runtime hashes are retained in `eval-results.json`. Those corrections did not alter these three tasks, but the development plans were not rerun afterward. The one-pass holdout used the final runtime.

All three conditions passed all three **plan** rubrics. Paired success lift is **0**, with **0/3 observed negative-transfer cases**. The skill response supplied more extension-specific details (batch-local references, truncated reads and explicit dry-run flags), but the registered rubric did not award extra points for that. There is **no demonstrated comparative improvement**.

The initial 120-second baseline attempt aborted without a complete scored response. It is not counted as a successful trial or silently discarded; all three comparison conditions were subsequently launched under the same revised budget.

**Lifecycle caveat:** complete final response texts were retained, but later host status reads reported `timed_out` even for previously completed workers. Scores describe those available texts, not clean worker completion or reliability. No latency comparison is drawn from the inconsistent lifecycle statuses. Tokens, costs and comparable tool-call/latency metrics were not collected.

## One-pass held-out planning

After the factual review corrections, a fresh read-only worker received three protected task inputs without rubrics and the final skill. Topic authors/reviewer had not been given these inputs. The parent had authored the cases and is not a blinded judge. No runtime revisions were made from this holdout's results.

| Held-out task | Score | Observed plan evidence |
| --- | ---: | --- |
| Portable collaboration | 4/4 | Repairs before collection, preserves a separate Project/editable source, distinguishes plug-in licensing from media collection, and verifies frozen/rendered fallbacks. |
| Tuning and MPE | 4/4 | Separates scales from tuning, checks actual receiver support/zones/bend range, avoids assuming universal hardware compatibility, and tests isolated voices first. |
| Export and latency | 4/4 | Separates 32-bit float from final 16-bit dither, checks tails/clipping, diagnoses duplicate monitoring, and distinguishes buffer/device/recording-placement concerns. |

No listed critical failures were observed. These are **unpaired planning results**, not held-out performance lift or actual project/export verification. Exact score observations and aborts are in [eval-results.json](eval-results.json). `runs` contains only the matched development comparison; `holdout_runs` is deliberately separate.

## Explicitly unverified

- Actual Live editing, saving, rendering, controller/hardware operations, and audible quality.
- Host skill activation, trigger precision/recall and negative-trigger selection. Six probes are designed but **not run**; mentioning a skill is not activation evidence.
- Repeated/randomized paired trials, blinded creative judging, and empirical validation-split optimization.
- Matched baseline/RAG holdout trials; adversarial prompt-injection behavior.
- Native Windows operation, every Live 12 minor version/edition/Pack, image-only UI details, and exhaustive parameter accuracy.
- Managed release archive installation and automatic discovery on an exact pinned host. The source workflow explicitly supplies `--skill-dir ./skills`; no release was published or installed.

## Recheck

```sh
uv run python -m unittest discover -s tests -v
uv run ruff check .
```

With the optional authoring skill installed, its `scripts/compare_evals.py` accepts `eval-results.json` and summarizes the nine matched development records. That deterministic summary does not upgrade planning evidence into production qualification. Future behavioral optimization needs separate validation cases and fresh, protected final holdouts.

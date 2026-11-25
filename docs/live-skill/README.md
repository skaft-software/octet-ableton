# Bundled Ableton Live skill

The runtime package is [`skills/ableton-live`](../../skills/ableton-live/SKILL.md): one entry point, task-routed procedural references, and a read-only installed-document locator. It is independent of the document used during authoring and does not redistribute it. No device-control tool, bridge, network permission, or extension-runtime behavior is added by the skill.

## Use and bundle

From this source checkout:

```sh
octet --extension-dir .. --enable-extension octet-ableton --skill-dir ./skills
```

An unmanaged source extension is not automatically a managed skill installation. The explicit `--skill-dir` is needed for this source workflow. Use `/skills` to inspect available skills. For a future managed extension archive, retain the complete `skills/ableton-live/` directory alongside `extension.toml`; octet discovers managed `skills/*/SKILL.md` candidates without a `contributes.skills` manifest key. Discovery is not permission to execute tools or scripts. This change does not publish or install a release bundle or claim an exact-host-pinned archive was tested.

The new skill is an operational Live reference for this extension, not a replacement for a user's taste-specific composition or specialist mastering skill. It avoids the personal aesthetic defaults and MCP-only assumptions of the separately installed `producing-music-in-ableton` skill. The description excludes extension development and dedicated CTZ mastering.

## Source and coverage provenance — development only

Source: **Ableton Live 12 Manual for Windows and Mac**, Ableton AG, supplied locally by the user. The title identifies Live 12 but does not pin a minor release. The supplied edition includes later features such as Bounce to Audio and Stem Separation; the skill therefore checks actual version, edition and capabilities rather than promising them on every 12.x installation.

- 1,039 PDF pages; 43 chapters; 837 numbered subsections indexed, including 344 top-level subsections.
- SHA-256: `14adfbfed52dbd10a77f7f950b39ba6f51971a2452f1d995040bec22b5ff1fd0`.
- Extraction: installed Poppler `pdftotext`, in layout and plain-text forms, retaining page boundaries in private temporary storage. Source text and rendered-page inspection artifacts are **not** in this repository/package.
- No redistribution permission is assumed. Runtime references use original paraphrased procedures, not copied passages, tables, screenshots, or a source-specific retrieval index. Names of controls/devices are retained where necessary for correct operation.
- [`coverage.json`](coverage.json) maps every chapter and numbered section to a topic guide. The companion `evidence/*.json` files record source locations, procedure mappings, synthesis, limitations and non-operational material. Private extraction paths are normalized to logical `private-extraction:/` identifiers; they are provenance labels, not distributed files or runtime dependencies. These maintainer artifacts are not prerequisites for using the skill.
- Welcome/credits are accounted for as non-operational context, not padded into invented procedures. Images are not comprehensively visually verified: text-based operational distinctions are preserved, and uncertain image-only controls must be checked against the installed UI.
- Coverage is **distillation**, not reproduction of every sentence or a guarantee of every possible Live operation. Chapter/section accounting is a structural check; semantic correctness and practical task success require separate review/testing.

The default workflow, permission boundaries, safe batch recovery and proposed verification checks are agent synthesis. The `octet-workflow.md` tool contract is grounded in this repository's current schemas and bridge code, not inferred from the Live user documentation. Recheck it when operation names, units, or capability support change.

## Optional installed help

The skill's `scripts/find_live_docs.py` looks only inside recognized installed-document layouts beneath conventional application roots or explicitly supplied installations. It uses Python 3.11+ standard library, performs bounded read-only discovery, and does not download, open, copy, index or upload documentation. It does not inspect the author's Downloads folder or require a source PDF filename.

A returned candidate is a path with installation evidence, not proof of a running-version match or document contents. Some Live releases/installations have no local document. Multiple installations and missing/empty directories are ordinary results, not reasons for an unrestricted disk or network search. Only macOS discovery can be checked on this host; Windows layouts are fixture-tested, not native-Windows-qualified.

## Evaluation and maintenance

[`eval-cases.json`](eval-cases.json) was written before substantial skill prose. It defines three development scenarios, three held-out scenarios, six trigger probes, observable checks and critical safety failures. The controlled comparison is **read-only planning**, not end-to-end music production or host trigger activation. See [`evaluation.md`](evaluation.md) for actual results, aborted attempts and unrun checks; do not treat source coverage as measured performance improvement.

The revision-2 update adds projected/batched inspection, schema-only caching with invalidation, compact receipts and approved selective audio reads. The inspection tool is now **Ableton Live Object Model** (`ableton_live_object_model`). Three additional audio-model cases live in [`skills/ableton-live/assets/eval-cases.json`](../../skills/ableton-live/assets/eval-cases.json); these remain **not run**. The original chapter references and provenance are preserved.

Repository checks:

```sh
uv run python -m unittest discover -s tests -p 'test_live_skill.py' -v
uv run python -m unittest discover -s tests -p 'test_live_docs.py' -v
uv run python -m unittest discover -s tests -v
uv run ruff check .
```

The authoring tool's additional structural validator is external to this extension; maintainers who have `engineering-agent-skills` can run its `scripts/validate_skill.py` against the runtime skill directory. The repository tests do not require that external skill, the original PDF, a running Live instance, or network access.

When updating: change the smallest affected procedure, retain source/version provenance here, run affected and regression tests, use development/validation cases for iteration, and do not repeatedly tune against final holdouts. Preserve failed/aborted evaluation evidence and keep content validation distinct from actual Live execution/audition.

# Sprint 04 — Real Corpus-Decide Without Faker

**Order:** 04 of 07  
**Theme:** Authoritative mode integrity  
**Audit reference:** Divergence matrix rows 1 (`make corpus-decide`), 4 (REAL mode is actually real), 10 (stable directory identity), §5 test-driven distortion findings 5.1, 5.2, §6 Critical gap 1 (no working end-to-end user workflow)

---

## Why this sprint exists

The audit's single most important finding is that `make corpus-decide` — documented as the primary authoritative user workflow — does not operate on real data. It:

1. Loads `metadata.json` (extracted filesystem metadata)
2. Creates empty 0-byte stub files at those paths (`full_path.touch()`)
3. Wraps everything in `FakerContext` (monkey-patches `os.path.*` and `os.stat`)
4. Builds evidence objects with `fingerprint_id=None, duration_seconds=None, existing_tags={}`
5. Calls providers who receive no useful input and cannot produce meaningful matches

This is the exact anti-pattern the docs warn against. "REAL mode" is documented as Guarantee 8: *"REAL authoritative mode is actually real."* Currently it is theatrical.

Without this sprint, no subsequent sprint can be grounded in real behavior, and the product claim ("trusted automation for music libraries") cannot be made honestly.

---

## Problem statement

The corpus-decide workflow creates phantom evidence. Providers receive null fingerprints, null durations, and empty tag sets. Directory identity degrades to a hash of `None` values. The 20 recorded decisions in `prompt_replay.json` are all "jail" because no meaningful matching could have occurred. The `expected_state.json` file contains fabricated `sample-release-*` IDs that were manually invented, not produced by any system run.

The `FakerContext` infrastructure exists to avoid requiring a real music library on disk during development. This was a reasonable short-term choice that has now become a permanent feature of the "production" workflow — the docs warn explicitly against this pattern.

---

## Target outcome

When this sprint is genuinely complete:

- `make corpus-decide` no longer uses `FakerContext` or monkey-patched `os.path` in its execution path
- Evidence objects produced during corpus-decide contain non-null `duration_seconds` (sourced from `metadata.json` or real files)
- Provider calls receive meaningful query parameters (at least artist name, album title, or track count)
- At least 5 directories in the corpus resolve to real (non-`sample-*`) release IDs
- `expected_state.json`, `expected_layout.json`, and `expected_tags.json` are regenerated from actual pipeline output — not manually authored
- The workflow is usable by someone without the exact original music library, by sourcing evidence faithfully from `metadata.json`

---

## In scope

- `scripts/corpus_decide_real_interactive.py` — remove `FakerContext`; populate evidence faithfully from `metadata.json`
- `scripts/corpus_decide_real.py` — same refactor for non-interactive variant
- `scripts/corpus_decide_real_replay.py` — verify it is consistent with the non-faker approach
- `tests/integration/_filesystem_faker.py` — demote to test-only infrastructure; add a comment or assertion preventing import in non-test contexts
- `tests/integration/test_real_world_corpus.py` — update to reflect the new evidence-building approach
- `tests/real_corpus/expected_state.json` — regenerate from actual pipeline output
- `tests/real_corpus/expected_layout.json` — regenerate (may remain `[]` if no layouts are produced, but must be honest)
- `tests/real_corpus/expected_tags.json` — regenerate
- `tests/real_corpus/prompt_replay.json` — regenerate after running corpus-decide interactively; must include at least some non-jail decisions
- `tests/real_corpus/decisions.json` — remove fabricated `sample-release-*` IDs; replace with real IDs or remove entries

---

## Out of scope

- Do not change provider scoring, canonicalization, or matching logic
- Do not change the CLI commands
- Do not redesign the state machine
- Do not require achieving 100% match rate — JAILED and QUEUED_PROMPT are valid outcomes
- Do not change the review interface (the bundle schema extension from Sprint 03 is in scope for Sprint 03, not here)
- Do not change the replay validation logic (Sprint 05)

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §5 (test-driven distortion findings, especially 5.1, 5.2)
- `docs/product/product_guarantees.md` — Guarantee 8 specifically
- `docs/product/workflows.md` — the documented make corpus-decide workflow
- `scripts/corpus_decide_real_interactive.py` — full file
- `scripts/corpus_decide_real.py` — full file
- `tests/integration/_filesystem_faker.py` — understand what it monkey-patches
- `tests/real_corpus/metadata.json` — scan headers to understand what fields are available (paths, sizes, mtimes, existing tag data if any)
- `resonance/core/` — specifically how `DirectoryRecord` and `DirectorySignature` are constructed
- `docs/system/architecture.md`

---

## Implementation requirements

1. **Remove FakerContext from the production workflow path.** `scripts/corpus_decide_real_interactive.py` and `scripts/corpus_decide_real.py` must not import or use `FakerContext`. If these scripts require a real filesystem, they require a real filesystem. If the developer does not have the original library, they should be able to work with a copy or a subset.

2. **Populate evidence from metadata.json faithfully.** `metadata.json` contains path, size, mtime, and likely file count/track metadata for each directory. Use these fields to build `DirectoryRecord` objects with non-null evidence where data is available. Specifically:
   - `duration_seconds` should be sourced from any available duration field in metadata, even if approximate
   - `existing_tags` should be populated from any tag data captured in metadata
   - `fingerprint_id` may remain `None` if fingerprinting requires the actual audio files — this is acceptable; do not fabricate a value

3. **Provider calls must receive meaningful input.** With real tag metadata available (artist, album, track count, year), provider queries will be meaningful even without fingerprints. The provider calls themselves do not need to change — they just need non-null input.

4. **Regenerate expected artifacts from actual output.** After refactoring, run corpus-decide interactively (or in non-interactive mode with the existing `decisions.json` as pinned decisions) and regenerate:
   - `expected_state.json` — from the actual state DB output
   - `expected_layout.json` — from the actual plan output (may legitimately be `[]` if no moves were planned)
   - `expected_tags.json` — from the actual tag plan output

5. **The corpus-decide result must include at least some real match decisions.** Run corpus-decide in a mode that allows provider matching (online or cache-backed). Record at least 5 real release IDs (non-`sample-*`). These do not need to be correct — a provider match that is wrong is still a real system output. Fabricated IDs are not.

6. **Demote FakerContext to test-only use.** Add a module-level comment or guard to `_filesystem_faker.py` that makes clear it is test infrastructure. Update `test_real_world_corpus.py` to reflect the new approach without FakerContext.

---

## Acceptance criteria

1. `make corpus-decide` completes without importing or using `FakerContext`.
2. After `make corpus-decide`, evidence objects in the state DB (or emitted logs) contain non-null `duration_seconds` for at least 50% of processed directories.
3. Provider query logs (if available) or the provider cache contain at least 5 queries with non-null artist or album parameters.
4. `expected_state.json` contains zero entries with `sample-release-*` IDs.
5. At least 5 directories in `expected_state.json` have a real release ID (UUID or other real provider format).
6. `make corpus-decide` completes without raising a Python exception from any import or use of `FakerContext`.
7. The corpus workflow test (`test_real_world_corpus.py`) passes with the updated approach.

---

## Required evidence

The executor must produce and preserve:

1. **`make corpus-decide` terminal output** showing the workflow running without FakerContext reference.
2. **State DB query or JSON fragment** showing at least 5 directories with non-null `duration_seconds` in their evidence.
3. **`grep -c "sample-release" tests/real_corpus/expected_state.json` output** showing zero matches.
4. **At least 5 lines from `expected_state.json`** showing real release IDs (not `sample-*`).
5. **`grep -r "FakerContext" scripts/`** showing no matches (or only comments/documentation references).

---

## Failure conditions

This sprint is NOT complete if:

- `FakerContext` is still imported or used in any script that `make corpus-decide` calls
- Evidence objects still have `duration_seconds=None` for the majority of directories
- `expected_state.json` still contains `sample-release-*` IDs
- The expected artifacts were manually edited to remove `sample-release-*` IDs without being regenerated from system output
- Providers receive queries with all-null parameters
- The sprint is declared done because tests pass, without running `make corpus-decide` end-to-end

---

## Dependencies

- **Sprint 01 must be proven complete** (stable CLI, all tests passing)
- **Sprint 02 must be proven complete** — the understanding of real audio processing informs how to build evidence correctly from metadata, and Sprint 02's tag writer verification provides confidence that apply will work

---

## Notes for executor

- The primary source of truth for this sprint is `metadata.json`. Inspect its actual schema before writing evidence builders. It was extracted from a real filesystem and likely contains track counts, file sizes, and possibly embedded tag data captured at extraction time.
- If `metadata.json` does not contain duration data, this sprint should document that gap explicitly in a comment. Do not fabricate durations — emit `None` but still remove FakerContext.
- The "at least 5 real release IDs" requirement may require an online run. If the existing cache in `tests/real_corpus/` is sufficient for provider matching on any 5 directories, use it. If not, a limited online run may be needed for this sprint.
- Running corpus-decide interactively requires patience. The goal is to record real decisions for at least some directories, even if most end up jailed. The key change is: jail decisions because matching was genuinely uncertain, not because evidence was empty.

---

## Executor prompt

```
You are implementing Sprint 04 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/04_real_corpus_decide_without_faker.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

Sprints 01 and 02 must be proven complete before you begin.

Your task:
1. Read the sprint file in full.
2. Read all files in "Required reading".
3. Remove FakerContext from scripts/corpus_decide_real_interactive.py and corpus_decide_real.py.
4. Rebuild evidence objects from metadata.json faithfully (real durations if available, real tags if available).
5. Run make corpus-decide and confirm it completes without FakerContext.
6. Regenerate expected_state.json, expected_layout.json, expected_tags.json from actual output.
7. Confirm at least 5 directories have real (non-sample-*) release IDs.

Do not:
- Change provider scoring, matching, or canonicalization
- Change CLI commands
- Fabricate expected artifacts — they must come from running the system
- Declare success based only on test results without running make corpus-decide

Required evidence before declaring success:
1. make corpus-decide terminal output (no FakerContext)
2. JSON fragment showing 5+ directories with non-null duration_seconds
3. grep -c "sample-release" expected_state.json = 0
4. 5 lines from expected_state.json with real release IDs
5. grep -r "FakerContext" scripts/ = no matches

Do not claim success without this evidence.
```

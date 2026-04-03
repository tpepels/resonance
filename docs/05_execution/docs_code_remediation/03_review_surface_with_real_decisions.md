# Sprint 03 — Review Surface with Real Decisions

**Order:** 03 of 07  
**Theme:** Inspectability  
**Audit reference:** Divergence matrix row 2 (`make corpus-review`), row 8 (decision inspectability), §6 Critical gap 3 (review surface shows no decisions)

---

## Why this sprint exists

The audit found that `make corpus-review` shows a directory tree but zero Resonance decision content. The review bundle's `expected_layout.json` contains `[]` and `expected_tags.json` contains `{"tracks": []}`. No candidate releases, no confidence tiers, no reasoning, no resolution outcomes are visible in the HTML interface.

This violates User Job 6 ("review important decisions without reading internals") and Product Guarantees 1–3 (no silent invention, decisions are inspectable, ambiguity is first-class).

The review surface is the human inspection point of the entire system. If it shows nothing, the system cannot be trusted — regardless of what it computed internally.

---

## Problem statement

The review bundle generation script (`scripts/generate_review_bundle.py`) merges five input files: `metadata.json`, `expected_state.json`, `expected_layout.json`, `expected_tags.json`, and `prompt_replay.json`. None of these input files contain:
- Per-directory identification candidates
- Confidence tier assignments
- Resolution reasoning text
- Plan summaries (what moves/tag changes were proposed)
- Apply outcomes

The HTML interface (`scripts/generate_review_interface.py`) renders what is in the bundle. Since the bundle lacks decision anatomy, the detail inspector panel shows only file listings.

---

## Target outcome

When this sprint is genuinely complete:

- The review bundle format is extended to include, for each directory: identification candidates, confidence tier, resolution reasoning, and resolution outcome
- The HTML detail inspector panel renders this decision anatomy without requiring the user to read raw JSON
- After running `make corpus-decide` followed by `make corpus-review`, a human reviewing the interface can answer for at least one directory: "what did Resonance think this was, how confident was it, and what did it decide?"
- The review bundle schema extension is documented (even briefly) so future bundle generators can follow it

---

## In scope

- `scripts/generate_review_bundle.py` — extend to accept and embed decision anatomy data (candidates, tier, reasoning, resolution state per directory)
- `scripts/generate_review_interface.py` — extend the detail inspector panel to render decision anatomy when present in the bundle
- The review bundle JSON schema (add fields; do not remove existing ones)
- Any glue needed to wire decision data from corpus-decide output into bundle generation — but only if corpus-decide already produces this data in some form
- A minimal fixture that allows `make corpus-review` to demonstrate the new panel without requiring a full corpus-decide run (for testing purposes)

---

## Out of scope

- Do not change how corpus-decide collects data (that is Sprint 04)
- Do not change the replay mechanism (that is Sprint 05)
- Do not change CLI commands
- Do not redesign the overall review interface layout — only extend the detail inspector
- Do not require live API calls to demonstrate the review surface

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §3.7 (actual review behavior), §6 Critical gap 3
- `docs/product/user_jobs.md` — job 6 in particular
- `docs/product/product_guarantees.md` — guarantees 1, 2, 3
- `scripts/generate_review_bundle.py` — full file
- `scripts/generate_review_interface.py` — full file
- `tests/real_corpus/expected_state.json` — to understand current state schema
- `review_bundle.json` — current bundle structure (note it is 2.9 MB; scan headers and per-directory structure)
- `docs/system/decision_model.md`

---

## Implementation requirements

1. **Define the decision anatomy extension to the bundle schema.** Each directory entry in the review bundle should include a `decision` object (or equivalent key) containing:
   - `candidates`: list of top-N candidates with `release_id`, `artist`, `title`, `score`, `tier`
   - `confidence_tier`: the overall tier assigned (`CERTAIN`, `PROBABLE`, `UNSURE`, or `UNRESOLVED`)
   - `reasoning`: list of string reasons or a single summary
   - `resolution_state`: the directory's final state (e.g., `RESOLVED_AUTO`, `QUEUED_PROMPT`, `JAILED`)
   - `resolution_source`: who made the decision (`AUTO`, `USER`, `REPLAY`, or `NONE`)
   - Fields should be `null`/empty if not yet computed — do not omit the keys

2. **Populate the extension from available data.** If corpus-decide already emits this data in any artifact (state DB, intermediate JSON, or logs), read it. If no such artifact currently exists, the bundle generator should emit null/empty decision anatomy — the HTML must still render gracefully (not crash or hide the panel).

3. **Extend the HTML detail inspector.** Add a "Decision" section to the right-hand panel that renders:
   - A confidence badge or indicator (e.g., CERTAIN in green, UNSURE in amber)
   - Top 3 candidates (if any) with scores
   - Resolution state and source
   - Reasoning text (or "No reasoning recorded" if absent)
   - The section should appear even when all values are null/empty, clearly labeled "Not yet processed" rather than hiding

4. **Test with a minimal fixture.** Create or use a minimal review bundle fixture that includes at least 3 directories with different decision states (e.g., one CERTAIN, one JAILED, one UNRESOLVED) to verify the HTML renders all cases correctly.

5. **Preserve backward compatibility.** The existing review bundle fields must not be removed or renamed. New fields are additive.

---

## Acceptance criteria

1. After `make corpus-review` (with whatever bundle is currently available), the HTML interface shows a "Decision" panel in the detail inspector for every directory.
2. For at least 3 directories in a test fixture, the Decision panel shows: confidence tier, at least one candidate (or "No candidates"), resolution state, and reasoning text (or "Not yet processed").
3. The detail inspector does not crash or display an empty panel when `decision` data is absent from a bundle entry.
4. `make corpus-review` launches successfully and the HTML is viewable in a browser.
5. The new bundle schema fields are present in the `review_bundle.json` output.

---

## Required evidence

The executor must produce and preserve:

1. **Screenshot or HTML source** of the detail inspector panel for at least one directory showing the new Decision section.
2. **Screenshot or HTML source** showing a directory with null/empty decision data — confirms the panel renders gracefully.
3. **`grep` output or JSON fragment** from `review_bundle.json` showing the `decision` key structure for at least one directory.
4. **`make corpus-review` terminal output** confirming the server starts without error.

---

## Failure conditions

This sprint is NOT complete if:

- The detail inspector panel only shows file listings with no decision content
- The HTML crashes or hides the Decision section when decision data is absent
- The `decision` key is present in the bundle schema but always empty/null because the bundle generator was not wired to emit real data
- The review bundle format breaks backward compatibility (existing fields removed or renamed)
- The evidence is based on a manually edited review bundle rather than one generated by running the system

---

## Dependencies

- **Sprint 01 must be proven complete** (stable test baseline, full CLI surface).
- Sprint 03 does NOT require Sprint 02 or Sprint 04. It can run concurrently with Sprint 02 if Sprint 01 is complete.
- Sprint 03 is aware that corpus-decide may not yet produce real decision data (that is Sprint 04). The HTML must handle absent data gracefully.

---

## Notes for executor

- The HTML interface is a single ~34 KB static file generated by `generate_review_interface.py`. The review data is loaded via `fetch()` from chunked JSON files. The detail inspector is probably a JavaScript function or template — find it and extend it.
- If `generate_review_bundle.py` currently has no source for decision anatomy data, the right behavior is to emit null/empty fields and ensure the HTML renders a clear "Not yet processed" state. Do not invent fake decision data to make the UI look populated.
- After Sprint 04, a follow-on pass may be needed to wire real decision data into the bundle. This sprint establishes the schema and UI scaffolding; Sprint 04 fills it with real data.
- The review bundle schema extension deferred to Sprint 03 review (`D6` in the overview deferred decisions) — pick the simplest schema that satisfies the acceptance criteria.

---

## Executor prompt

```
You are implementing Sprint 03 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/03_review_surface_with_real_decisions.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

Sprint 01 must be proven complete before you begin. Sprint 02 may run in parallel.

Your task:
1. Read the sprint file in full.
2. Read all files in "Required reading".
3. Extend the review bundle schema (generate_review_bundle.py) to include decision anatomy per directory.
4. Extend the HTML detail inspector (generate_review_interface.py) to render the new Decision panel.
5. Create a minimal fixture with 3 directories in different decision states to verify rendering.
6. Verify make corpus-review serves the updated interface correctly.

Do not:
- Change how corpus-decide collects data (Sprint 04 does that)
- Remove or rename existing bundle fields
- Invent fake decision data to populate the UI — emit null/empty and render gracefully
- Change CLI commands or the replay mechanism

Required evidence before declaring success:
1. Screenshot or HTML source of detail inspector showing Decision panel with content
2. Screenshot or HTML source showing graceful rendering when decision data is absent
3. JSON fragment from review_bundle.json showing the decision key structure
4. make corpus-review terminal output confirming no errors

Do not claim success without this evidence.
```

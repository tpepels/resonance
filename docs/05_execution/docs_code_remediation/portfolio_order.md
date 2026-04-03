# Portfolio Execution Order

**Portfolio:** Resonance Docs-to-Code Remediation  
**Governing document:** `docs/05_execution/docs_code_remediation/00_overview.md`  
**Execution model:** Strict sequential queue

---

## Execution Queue

| # | Sprint | Goal | Requires | Unblock condition for next sprint |
|---|--------|------|----------|----------------------------------|
| 01 | [Fix CLI and Baseline](01_fix_cli_and_baseline.md) | All documented CLI commands accessible; all tests passing | None | `pytest` fully green; `resonance --help` shows all 10+ documented commands; `identify` dispatches with a real provider client |
| 02 | [Real Audio Pipeline Proof](02_real_audio_pipeline_proof.md) | The pipeline has been observed processing real audio files end-to-end | Sprint 01 | Integration test on real FLAC/MP3 files passes; tag readback from a real audio file shows values written by MutagenTagWriter |
| 03 | [Review Surface with Real Decisions](03_review_surface_with_real_decisions.md) | Review bundle includes decision anatomy; HTML interface renders it | Sprint 01 | `make corpus-review` renders at least one directory with candidates, confidence tier, and reasoning visible without reading raw JSON |
| 04 | [Real Corpus-Decide Without Faker](04_real_corpus_decide_without_faker.md) | `make corpus-decide` uses real or faithfully populated evidence; FakerContext removed from production path | Sprints 01, 02 | Provider call logs show non-null query parameters; at least 5 directories produce a real (non-sample-*) release ID; evidence objects contain non-null durations |
| 05 | [Replay Proof with Real Match Decisions](05_replay_proof_with_real_matches.md) | A real match decision has been recorded, replayed successfully, and a broken replay produces hard failure | Sprint 04 | Integration test demonstrates: replay succeeds with matching fingerprint; same test with altered fingerprint produces a hard failure, not silent success |
| 06 | [Documentation Reconciliation](06_docs_reconciliation.md) | All documentation claims are verifiable by running the system | Sprints 04, 05 | No sentence in V3.1 manual or README claims a capability that cannot be demonstrated by running a command |
| 07 | [Integrated User Workflow](07_integrated_user_workflow.md) | A user with a music library can run one command and get reviewable output | Sprints 01–06 | Demo on a real 5–10 directory library produces a review bundle with visible decision content; the command does not require reading scripts/ or internal knowledge |

---

## Dependency Graph

```
01 (Fix CLI and Baseline)
 ├─▶ 02 (Real Audio Pipeline Proof)
 │    └─▶ 04 (Real Corpus-Decide Without Faker)
 │         ├─▶ 05 (Replay Proof)
 │         │    └─▶ 06 (Docs Reconciliation)
 │         └─▶ 06 (can begin concurrently if 04 is proven)
 ├─▶ 03 (Review Surface)
 │    └─▶ 07 (Integrated User Workflow, partial dependency)
 └─▶ 04 (also requires 01)

07 (Integrated User Workflow) requires all of 01–06
```

**Concurrency exception:** Sprint 06 may begin concurrently with Sprint 05 if Sprint 04 is fully proven, since Sprint 06 only documents proven outcomes.

---

## Stop/Go Gates at Each Transition

### After Sprint 01 → before Sprint 02 or 03

**Must verify:**
- [ ] `pytest` reports zero failures (all 510+ tests pass)
- [ ] `resonance --help` lists: scan, resolve, identify, prompt, plan, apply, audit, doctor, rollback, unjail
- [ ] `resonance identify --help` does not crash and shows provider-related options
- [ ] No new test-only scaffolding was introduced during the sprint

### After Sprint 02 → before Sprint 04

**Must verify:**
- [ ] Integration test on real audio files passes end-to-end (scan → resolve → plan → apply)
- [ ] Tag readback from a real audio file shows values written by `MutagenTagWriter`
- [ ] Test does not rely on empty stub files or pre-emptive `.meta.json` sidecars to simulate audio content

### After Sprint 03 → (feeds Sprint 07 only)

**Must verify:**
- [ ] Review bundle JSON for at least 3 directories contains: candidates list, confidence tier, reasoning text, resolution state
- [ ] HTML interface renders this content in the detail inspector without requiring raw JSON inspection
- [ ] `make corpus-review` serves this content after `make corpus-decide` is run

### After Sprint 04 → before Sprint 05 or 06

**Must verify:**
- [ ] Provider call logs show non-null artist, title, or duration parameters in at least 5 queries
- [ ] At least 5 directories in `prompt_replay.json` or resolution state contain real (non-`sample-*`) release IDs
- [ ] Evidence objects in scan output contain non-null `duration_seconds` values
- [ ] `FakerContext` is no longer imported or used in any script that `make corpus-decide` calls

### After Sprint 05 → before Sprint 06

**Must verify:**
- [ ] Integration test records N ≥ 3 real match decisions (not jail)
- [ ] The same test successfully replays all N decisions
- [ ] The same test, with one decision's fingerprint altered, produces a hard failure (non-zero exit, error message visible)
- [ ] The hard-failure test output is preserved as a fixture or log

### After Sprint 06 → before Sprint 07

**Must verify:**
- [ ] Every capability claim in `docs/process/V3.1_REAL_CORPUS_MANUAL.md` corresponds to a runnable command
- [ ] `expected_state.json` contains no `sample-release-*` IDs
- [ ] README "Known Limitations" section exists and is accurate
- [ ] No documentation file still claims "✅ Semantically proven" for replay unless Sprint 05 evidence exists

### After Sprint 07 → portfolio complete

**Must verify:**
- [ ] Demo run on a real 5–10 directory library succeeds
- [ ] Review output shows decision content (candidates, reasoning, confidence)
- [ ] No FakerContext, no monkey-patching, no stub files in the workflow path
- [ ] A new user following only the README/manual can complete the workflow without reading scripts/

---

## Execution Anti-Patterns (Quick Reference)

1. Do not declare a sprint complete without producing all required evidence
2. Do not begin sprint N+1 before sprint N's stop/go gate is cleared
3. Do not absorb out-of-scope work from adjacent sprints
4. Do not use `FakerContext` in any script classified as a user-facing workflow
5. Do not create `expected_*.json` files by hand — they must be regenerated from actual pipeline output

# Sprint 05 — Replay Proof with Real Match Decisions

**Order:** 05 of 07  
**Theme:** Trust guarantees  
**Audit reference:** Divergence matrix row 3 (replay determinism), §5 test-driven distortion finding 5.3, §6 Critical gap 4 (replay never proven with real match decisions)

---

## Why this sprint exists

The audit found that all 20 decisions in `prompt_replay.json` are "jail" decisions:

```json
{"chosen_option": "jail", "chosen_provider": null, "chosen_release_id": null}
```

The V3.1 manual claims *"Decision Replay: ✅ Semantically proven with hard enforcement."* This claim is false. Jailing requires no fingerprint validation, matches nothing, and proves nothing about the replay mechanism's core purpose — deterministic reproduction of *accepted match decisions* and *hard failure* when fingerprints change.

Product Guarantees 4 and 5 are:
- **Guarantee 4:** Replay is deterministic when assumptions match
- **Guarantee 5:** Replay fails loudly on mismatch

Neither guarantee can be marked as proven until a real match decision has been recorded, replayed successfully, and a deliberately broken replay has been observed to fail hard.

---

## Problem statement

The replay mechanism (`PromptReplay` class in `resonance/commands/prompt.py`) is implemented and computes SHA256 fingerprints. But:
- The only existing replay file (`prompt_replay.json`) contains only jail decisions
- No test records a non-jail (match) decision and replays it
- No test demonstrates that altering a fingerprint causes hard failure (non-zero exit, not silent continuation)
- Guarantees 4 and 5 are therefore rhetorical, not behavioral

Sprint 04 will produce real match decisions. Sprint 05 captures them in a replay file and proves the full replay guarantee.

---

## Target outcome

When this sprint is genuinely complete:

- A new integration test exists that:
  1. Records at least 3 real match decisions (not jail) via `prompt --record`
  2. Replays the recorded file via `prompt --replay` and confirms it succeeds
  3. Alters one decision's fingerprint in the replay file (e.g., changes a single character in the SHA256 hash)
  4. Replays the altered file via `prompt --replay` and confirms it produces a **hard failure** — non-zero exit code, error message identifying the mismatch
- The test is committed as a regression guard
- `prompt_replay.json` in the real corpus is updated to include at least some real match decisions alongside (or replacing) jail-only decisions

---

## In scope

- `resonance/commands/prompt.py` — fix any bugs in `run_prompt_replay()` that prevent hard failure on mismatch; ensure non-zero exit on fingerprint mismatch
- New integration test file (e.g., `tests/integration/test_replay_proof.py`) that covers: record → replay success → altered fingerprint → replay failure
- `tests/real_corpus/prompt_replay.json` — update to include at least 3 non-jail match decisions (sourced from Sprint 04 output)
- If `run_prompt_replay()` currently swallows mismatch errors or continues after a mismatch, fix this behavior

---

## Out of scope

- Do not change the corpus-decide workflow (Sprint 04)
- Do not change the review surface (Sprint 03)
- Do not change provider scoring or matching
- Do not change the CLI command surface
- Do not change `prompt_replay.json` format — only add non-jail entries; preserve existing format compatibility

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §3.6 (actual replay behavior), §5.3, §6 Critical gap 4
- `docs/system/replay_model.md`
- `resonance/commands/prompt.py` — full file, especially `PromptReplay`, `run_prompt_replay()`, and `compute_prompt_fingerprint()`
- `tests/real_corpus/prompt_replay.json` — inspect all 20 entries to confirm they are all jail
- Sprint 04 sprint file and its output evidence

---

## Implementation requirements

1. **Verify and fix hard-failure on mismatch.** Read `run_prompt_replay()` and confirm that when `compute_prompt_fingerprint()` for a candidate differs from the stored hash, the function raises an exception or exits non-zero. If it currently logs a warning and continues, that is a bug — fix it. A replay mismatch must never silently succeed.

2. **Write the record-replay integration test.** The test must:
   - Set up a small resolved corpus (can reuse Sprint 02 fixture or Sprint 04 real corpus data)
   - Run `prompt --record` mode on at least 3 directories that have real match candidates
   - Capture the generated replay file
   - Run `prompt --replay` against the same corpus with the same replay file
   - Assert the replay succeeds (exit code 0, all decisions applied)
   - Mutate one fingerprint in the replay file (change one hex character)
   - Run `prompt --replay` again
   - Assert it fails hard (non-zero exit code, error message contains "mismatch" or "fingerprint" or equivalent)

3. **Update the real corpus replay file.** After Sprint 04 produces real match decisions, regenerate `prompt_replay.json` with at least 3 non-jail entries. These entries must be produced by actually running the prompt-record workflow, not manually authored.

4. **Do not weaken the fingerprint validation.** The existing fingerprint computation uses SHA256 of `dir_id + candidate info + reasons`. Do not simplify or bypass this. The goal is to prove it works, not to make it easier to pass.

---

## Acceptance criteria

1. A new integration test (`test_replay_proof.py` or equivalent) runs to completion with all assertions passing.
2. The test demonstrates replay **success**: `prompt --replay` with a correctly recorded file exits with code 0 and all decisions are applied.
3. The test demonstrates replay **failure**: `prompt --replay` with a single altered fingerprint exits with a **non-zero code** and produces an error message identifying the mismatch. The process must not silently continue or apply a partial replay.
4. `prompt_replay.json` in the real corpus contains at least 3 entries with `"chosen_option"` set to something other than `"jail"` (e.g., a real release accept/confirm decision).
5. `pytest tests/integration/test_replay_proof.py -v` passes cleanly.

---

## Required evidence

The executor must produce and preserve:

1. **Replay success test output** — the terminal output of the integration test showing the successful replay assertion passing.
2. **Replay failure output** — the terminal output showing the hard-failure assertion passing, including the error message emitted by `run_prompt_replay()` when the fingerprint is altered.
3. **`prompt_replay.json` fragment** showing at least 3 entries with non-jail `chosen_option` values.
4. **Full `pytest tests/integration/test_replay_proof.py -v` output** (all passing).

---

## Failure conditions

This sprint is NOT complete if:

- The "failure" test passes because `prompt --replay` exits with code 0 even after fingerprint alteration
- The replay file is updated by manually authoring entries rather than running the record workflow
- The test uses a fixture with jail-only decisions and rebrands them as "matches"
- `run_prompt_replay()` is modified to weaken fingerprint validation to make the test easier to pass
- The test is marked skip in CI

---

## Dependencies

- **Sprint 04 must be proven complete** — this sprint requires real match decisions from corpus-decide. Sprint 05 cannot be executed without at least some non-jail resolution outcomes from Sprint 04.
- Sprint 01 must also be proven complete (stable test baseline).

---

## Notes for executor

- The `compute_prompt_fingerprint()` function takes `dir_id`, candidates, and reasoning as inputs. Altering the replay file's stored hash (not the candidate data) is the correct way to simulate a mismatch — change one hex character in the `fingerprint` field of a single decision entry.
- If the record/replay workflow requires interactive prompts, use the scripted/batch mode already supported by the prompt command. Read the prompt command source to understand `--record`, `--replay`, and `--batch` modes.
- The failure test must assert both: (1) non-zero exit code, and (2) some indication in stderr or stdout that the failure was due to fingerprint mismatch specifically — not just any error.
- This sprint's evidence directly refutes the V3.1 manual claim "Decision Replay: ✅ Semantically proven." After this sprint, that claim becomes true. Sprint 06 will update the documentation accordingly.

---

## Executor prompt

```
You are implementing Sprint 05 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/05_replay_proof_with_real_matches.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

Sprint 04 must be proven complete (real match decisions produced) before you begin.

Your task:
1. Read the sprint file in full.
2. Read all files in "Required reading".
3. Verify that run_prompt_replay() exits non-zero on fingerprint mismatch. Fix if not.
4. Write tests/integration/test_replay_proof.py covering:
   a. record at least 3 real match decisions
   b. replay succeeds
   c. alter one fingerprint → replay fails hard (non-zero exit, error message)
5. Update tests/real_corpus/prompt_replay.json with at least 3 non-jail entries.

Do not:
- Weaken fingerprint validation to make tests pass
- Manually author replay file entries
- Change corpus-decide workflow, review surface, or CLI surface
- Mark the test as skip in CI

Required evidence before declaring success:
1. Replay success test output (assertions passing)
2. Replay failure output showing non-zero exit and error message
3. prompt_replay.json fragment with 3+ non-jail entries
4. Full pytest test_replay_proof.py -v output (all passing)

Do not claim success without this evidence.
```

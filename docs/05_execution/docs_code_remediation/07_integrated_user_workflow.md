# Sprint 07 — Integrated User Workflow

**Order:** 07 of 07  
**Theme:** Product completion  
**Audit reference:** Divergence matrix row 1 and 2 (primary workflows), §6 Critical gap 1 (no working end-to-end user workflow), §3.9 (actual user touchpoints)

---

## Why this sprint exists

The audit found that a user with a music library cannot run a single command and get reviewable output. The individual pipeline stages (scan, resolve, prompt, plan, apply, review) work — but only when orchestrated through scripts in `scripts/`, which:
- Bypass the real CLI
- Use `FakerContext` (now removed by Sprint 04, but the structure remains script-based)
- Require internal knowledge of the codebase to operate
- Are not the documented primary interface

The documented primary interface is `make corpus-decide` followed by `make corpus-review`. After Sprint 04, `make corpus-decide` produces real output. But the workflow is still mediated through scripts that are not stable user-facing commands.

This sprint wires the full pipeline into a single, usable workflow that a real user can follow from a README.

---

## Problem statement

There is no integrated command that takes a user from "I have a directory of music" to "I have a reviewable set of Resonance decisions" without reading scripts, understanding internal modules, or running commands in a specific undocumented order.

The `Makefile` targets (`make corpus-decide`, `make corpus-review`) are close, but they rely on `scripts/corpus_decide_real_interactive.py` as an orchestration layer that is not CLI-wired and carries the historical `FakerContext` complexity.

---

## Target outcome

When this sprint is genuinely complete:

- A user can follow the README to run a workflow on their music library and get reviewable output
- `make corpus-decide` (or an equivalent Makefile target) invokes real CLI orchestration — not a standalone script bypassing the CLI
- `make corpus-review` serves a review bundle that contains actual decision content (the output wired by Sprint 03)
- The workflow does not require reading `scripts/` or understanding internal module structure
- A demo run on a small real library (5–10 directories) produces a review bundle with visible decision content in the HTML interface

---

## In scope

- `resonance/cli.py` — add a `decide` (or `workflow`) subcommand that orchestrates scan → resolve → prompt → plan → apply → generate-review in sequence
- New orchestration module (e.g., `resonance/commands/decide.py`) implementing the `decide` workflow
- `Makefile` — update `corpus-decide` and `corpus-review` targets to use the new CLI command rather than calling `scripts/` directly
- `README.md` — update the primary workflow section to reflect the new single-command path
- `scripts/` — demote to dev-only tooling; add a note that these scripts are internal development aids, not the user-facing interface
- Integration of Sprint 03's review bundle extension into the orchestration output

---

## Out of scope

- Do not re-implement any pipeline stage (scan, resolve, prompt, plan, apply) — all must delegate to the existing commands
- Do not redesign the HTML review interface (Sprint 03)
- Do not change provider logic, scoring, or canonicalization
- Do not implement daemon mode (deferred)
- Do not add new CLI commands beyond the `decide` orchestrator
- Do not delete `scripts/` — only demote it; tests may still use it

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §6 Critical gap 1, §3.9
- `docs/product/workflows.md` — the documented make corpus-decide workflow
- `docs/product/user_jobs.md` — jobs 1–7
- `resonance/cli.py` — current full file after Sprint 01
- `scripts/corpus_decide_real_interactive.py` — after Sprint 04 refactor; understand what orchestration it performs
- `scripts/generate_review_bundle.py` and `scripts/generate_review_interface.py` — after Sprint 03 extension
- `Makefile` — current corpus-decide and corpus-review targets
- Sprint 04 sprint file and evidence
- Sprint 03 sprint file and evidence

---

## Implementation requirements

1. **Create a `decide` CLI command.** Add `resonance decide [OPTIONS] LIBRARY_PATH` (or `resonance workflow`) that runs in sequence:
   - `scan LIBRARY_PATH --state-db <db>`
   - `resolve --state-db <db> --cache-db <cache>`
   - `prompt --state-db <db>` (interactive, or replay if `--replay-file` is given)
   - `plan --state-db <db>`
   - `apply --state-db <db>` (dry-run by default unless `--apply` flag is set)
   - Review bundle generation (delegate to the review bundle generator from Sprint 03)
   - Report a summary: N directories resolved, M jailed, K planned, plan output path

2. **The command must be real, not theatrical.** No `FakerContext`, no stub files, no monkey-patching. It takes a real `LIBRARY_PATH`.

3. **Update Makefile targets.** `make corpus-decide` should invoke `resonance decide` (or the equivalent) rather than calling a Python script directly. Pass the library path from an environment variable or config.

4. **Dry-run is the default.** The `apply` stage must default to dry-run mode. The user must explicitly pass `--apply` to mutate files.

5. **Review bundle is generated automatically.** After planning (and optionally applying), the `decide` command should generate the review bundle and the HTML interface, and report where they were written.

6. **`make corpus-review` should serve the current review output.** It should report the path of the generated HTML and either open it in a browser or launch a local HTTP server.

7. **README update.** Update the primary workflow section of `README.md` to show the new single-command path. The README should contain a quickstart that a new user can follow without reading `scripts/`.

8. **Demote scripts/.** Add a comment or header to each script in `scripts/` indicating it is development/maintenance tooling, not the primary user interface.

---

## Acceptance criteria

1. `resonance decide --help` exits with code 0 and describes the workflow.
2. Running `resonance decide /path/to/small_library` on a real directory with 5–10 music subdirectories completes without error (dry-run).
3. The command produces a review bundle at a reported output path.
4. `make corpus-review` serves the generated review interface with decision content visible (as extended in Sprint 03).
5. A person following only the README quickstart can complete the workflow from library path to reviewable output.
6. No `FakerContext`, no `os.path` monkey-patching, and no empty stub files are present in the `decide` command path.

---

## Required evidence

The executor must produce and preserve:

1. **`resonance decide --help` output** showing the command is registered and describes its options.
2. **Terminal output of `resonance decide /path/to/real_library`** on a small real library — showing the scan/resolve/plan/review steps completing.
3. **Review bundle summary** — a JSON fragment or log line showing N directories in the output bundle with decision content.
4. **Screenshot or HTML source** of the review interface after a `decide` run — showing at least one directory's decision panel populated (from Sprint 03 extension).
5. **`make corpus-decide` terminal output** showing it calls `resonance decide` (not a standalone Python script).

---

## Failure conditions

This sprint is NOT complete if:

- `make corpus-decide` still calls `scripts/corpus_decide_real_interactive.py` directly
- `resonance decide` uses `FakerContext` or empty stub files in any code path
- The review interface shows no decision content (decision panel empty or absent)
- A new user cannot complete the workflow following only the README
- The apply step defaults to actually mutating files (dry-run must be the default)
- The `decide` command is a thin wrapper that does nothing but call the existing script

---

## Dependencies

- **All of Sprints 01–06 must be proven complete** before this sprint begins
- Sprint 03's review bundle extension must be wired (providing decision content)
- Sprint 04's FakerContext removal must be in place
- Sprint 06's README must be up to date (the quickstart being added here builds on it)

---

## Notes for executor

- The orchestration in `decide` does not need to be complex. It is a sequential runner over existing commands. The goal is wiring, not re-architecture.
- The library path should be configurable via environment variable (for `make corpus-decide`) and as a CLI argument (for direct use).
- If the `prompt` step is interactive and cannot easily be automated in the `decide` command, provide a `--batch-decisions` or `--replay-file` option so the workflow can be run non-interactively. Interactive prompting can remain the default.
- The `--apply` flag guarding file mutations is the most important safety feature of this sprint. Default dry-run is not optional.
- Consider whether `decide` should emit a machine-readable summary JSON at the end (counts of resolved/jailed/planned/applied). This is useful for CI integration and matches the design principle of inspectable outputs.

---

## Executor prompt

```
You are implementing Sprint 07 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/07_integrated_user_workflow.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

All of Sprints 01–06 must be proven complete before you begin.

Your task:
1. Read the sprint file in full.
2. Read all files in "Required reading".
3. Create resonance/commands/decide.py implementing a decide orchestration command.
4. Register it in resonance/cli.py.
5. Update the Makefile corpus-decide target to use resonance decide.
6. Update README.md with a quickstart following the new single-command path.
7. Demote scripts/ to dev-only tooling with clear comments.

Do not:
- Re-implement scan, resolve, prompt, plan, apply — delegate to existing commands
- Use FakerContext or stub files in any new code path
- Default apply to mutating files — dry-run must be the default
- Declare success without testing on a real library

Required evidence before declaring success:
1. resonance decide --help output
2. resonance decide /path/to/real_library terminal output (dry-run, no errors)
3. Review bundle JSON fragment showing decision content
4. Screenshot or HTML source of review interface after a decide run
5. make corpus-decide output showing it calls resonance decide

Do not claim success without this evidence.
```

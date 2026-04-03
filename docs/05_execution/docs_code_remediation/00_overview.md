# Resonance Docs-to-Code Remediation Portfolio — Overview

**Portfolio type:** Divergence remediation  
**Baseline audit:** `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md`  
**Sprint count:** 7  
**Execution model:** Strict sequential queue — each sprint must be proven complete before the next begins  

---

## 1. Purpose of This Portfolio

This portfolio converts the accepted docs-to-code divergence audit into an executable set of sprints that move Resonance from a well-documented prototype toward a working product.

The audit found that:

- `make corpus-decide` operates on phantom data (FakerContext + empty stub files)
- `make corpus-review` shows filesystem structure with zero Resonance decision content
- Replay has only been exercised with "jail" decisions — real match replay has never been proven
- Four CLI commands exist in code but are unregistered and inaccessible
- The `identify` CLI command silently passes `provider_client=None`
- Eight tests fail at baseline
- Documentation overstates system capabilities

These sprints correct those conditions in dependency order.

---

## 2. Audit Baseline Being Implemented

**Source:** `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md`  
**Auditor:** resonance-system-auditor  
**Date:** 2025-04-03  
**Baseline test results at time of audit:** 502 passed, 8 failed, 7 skipped

The audit classified divergences across 20 areas. The most critical were:

| # | Area | Status |
|---|------|--------|
| 1 | `make corpus-decide` | DIVERGED |
| 2 | `make corpus-review` | DIVERGED |
| 3 | Replay determinism | PARTIAL |
| 4 | REAL mode is actually real | DIVERGED |
| 8 | Decision inspectability | DIVERGED |
| 11 | CLI surface completeness | PARTIAL |
| 20 | Documentation accuracy | DIVERGED |

Sprints 1–7 address these findings in the order imposed by their dependencies.

---

## 3. Target End-State

When all seven sprints are proven complete, Resonance will satisfy:

1. **All documented CLI commands are accessible and functional** — scan, resolve, identify, prompt, plan, apply, audit, doctor, rollback, unjail
2. **The pipeline has been observed processing real audio files** — scan → resolve → plan → apply with MutagenTagWriter, tags verified by readback
3. **`make corpus-review` shows actual decision content** — candidates, confidence tier, resolution reasoning, plan summary
4. **`make corpus-decide` uses real or faithfully populated evidence** — no FakerContext, no null fingerprints, no empty stub files in the production path
5. **Replay is behaviorally proven** — a real match decision has been recorded, successfully replayed, and intentionally broken to confirm hard failure
6. **Documentation matches what the system demonstrably does** — no unverifiable claims remain
7. **A user with a music library can run a single command and get a reviewable output**

---

## 4. Execution Rules

1. **Strict ordering.** Sprints execute in numerical order (01 → 07). No sprint begins until its predecessor has satisfied the stop/go gate.
2. **Behavioral evidence required.** Completion of a sprint requires observed command output, artifact diffs, or other concrete evidence. Code changes alone are not sufficient.
3. **No scope expansion.** Each sprint file defines explicit out-of-scope guardrails. An executor must not absorb neighboring sprint work to accelerate delivery.
4. **Deferred decisions stay deferred.** Items listed in Section 7 of this document must not be resolved inside sprint execution unless explicitly unblocked.
5. **Tests support proof, not define it.** Tests may be cited as supporting evidence, but the primary proof must be behavioral and observable.

---

## 5. Proof Standard

A sprint is complete when the executor can provide **all** required evidence items listed in the sprint's "Required evidence" section.

Evidence must be:
- **Observable** — produced by running a command, viewing a file, or inspecting a UI
- **Reproducible** — another person following the same steps gets the same evidence
- **Non-fabricated** — not manually created to satisfy a format without running the system

Minimum acceptable evidence per sprint is specified in each sprint file.

---

## 6. Stop/Go Rule Between Sprints

Before beginning sprint `N+1`:

1. Retrieve the "Required evidence" checklist from sprint `N`
2. Confirm every item has been satisfied with concrete artifacts
3. Confirm the "Failure conditions" of sprint `N` have not been triggered
4. Record the completion evidence in `docs/process/audits/` as a closure note or append to the sprint file

If any evidence item is missing or any failure condition is present, sprint `N` is **not complete**. Sprint `N+1` must not begin.

**Exception:** Sprint 6 (documentation reconciliation) may begin concurrently with Sprint 5 if Sprint 4 is fully proven, since Sprint 6 only documents proven outcomes and introduces no behavior changes.

---

## 7. Explicit Anti-Patterns to Avoid

These are the exact failure modes that caused the documented divergence. Each sprint executor must actively avoid them.

### AP-1: Test-only completion
Declaring a sprint done because tests pass, without running the actual user-facing workflow.  
**Guard:** Every sprint requires behavioral evidence beyond `pytest` output.

### AP-2: Fake real workflows
Using `FakerContext`, monkey-patching, or empty stub files in any workflow described as "real" or "authoritative."  
**Guard:** Sprint 4 acceptance criteria explicitly require inspecting evidence objects for non-null fingerprint/duration values.

### AP-3: Fabricated expected artifacts
Creating `expected_*.json` files by hand or from invented release IDs (`sample-release-1`, etc.) rather than from actual system output.  
**Guard:** Sprint 4 and 6 require expected artifacts to be regenerated from actual pipeline execution.

### AP-4: Documentation claims without behavioral proof
Writing documentation (README, manuals, sprint completion notes) that claims capabilities the system cannot currently demonstrate.  
**Guard:** Sprint 6 explicitly requires every claim in the V3.1 manual to be verifiable by running a command.

### AP-5: Starting later sprints before proving earlier ones complete
Absorbing sprint 3 review work during sprint 1 execution, or beginning sprint 5 before sprint 4's evidence is in hand.  
**Guard:** The stop/go rule in Section 6 is non-negotiable.

### AP-6: Green CI as proof of product correctness
A clean `pytest` run does not mean the user-facing workflow works. The audit documented 502 passing tests coexisting with a non-functional primary workflow.  
**Guard:** Each sprint requires at least one piece of evidence that cannot be produced by CI alone (e.g., review UI screenshot, tag readback from real audio, provider call log).

---

## 8. Portfolio at a Glance

| Sprint | Title | Theme | Unblocks |
|--------|-------|-------|---------|
| 01 | Fix CLI and Baseline | Stabilization | All subsequent sprints |
| 02 | Real Audio Pipeline Proof | Behavioral proof | Sprints 04, 05 |
| 03 | Review Surface with Real Decisions | Inspectability | Sprint 07 |
| 04 | Real Corpus-Decide Without Faker | Authoritative mode | Sprints 05, 06 |
| 05 | Replay Proof with Real Match Decisions | Trust guarantee | Sprint 06 |
| 06 | Documentation Reconciliation | Honesty | Sprint 07 |
| 07 | Integrated User Workflow | Product completion | — |

See `portfolio_order.md` for the full dependency queue and stop/go conditions.

---

## 9. Deferred Decisions

These design questions are intentionally not forced into any sprint. They should be revisited after the relevant sprints are complete.

| # | Decision | Revisit after |
|---|----------|--------------|
| D1 | Whether FakerContext has any legitimate CI role | Sprint 04 |
| D2 | Whether `.meta.json` sidecar testing remains the primary fast-test strategy | Sprint 02 |
| D3 | Classical/compilation foldering rule refinement | Sprint 07 |
| D4 | Daemon mode implementation | Sprint 07 |
| D5 | Whether golden corpus should be the primary acceptance gate vs. real-audio tests | Sprint 02 |
| D6 | Review bundle schema versioning strategy | Sprint 03 |

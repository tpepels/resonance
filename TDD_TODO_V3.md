# TDD TODO V3 — Deterministic, Expressive, Feature-Complete Release (Progress-Mapped)

This document is the **single source of truth** for V3.
It reflects **actual current progress**, mapped precisely onto the agreed V3 scope.

Legend:
- [x] COMPLETE
- [ ] TODO

---

## EXECUTION ORDER & GATES

### Phase A — Invariant Lock ✅ COMPLETE

### Phase B — Legacy Closure ✅ COMPLETE

### Phase C — Feature Delivery ⚠️ INCOMPLETE (workflow commands missing)

### Phase D — Acceptance Gate ✅ COMPLETE (core tests)

### Phase E — Workflow Integration ❌ NOT STARTED (critical gap)

---

## Phase A — Invariant & Authority Lock ✅ COMPLETE

### A.1 Canonicalization authority & surface
- [x] Single canonicalization module
- [x] `display_*` vs `match_key_*` separation
- [x] Pure functions, deterministic
- [x] Alias persistence only via DirectoryStateStore
- [x] MetadataCache excluded
- [x] Unit tests freeze behavior

### A.2 Stable directory identity & no-rematch invariant
- [x] Integration test: rerun produces no provider calls
- [x] Integration test: rename repaired without re-identify
- [x] Enforcement at resolver boundary

### A.3 Golden corpus as hard gate
- [x] Golden corpus runs before all other V3 tests
- [x] 26 deterministic scenarios
- [x] Layout, tags, state snapshots
- [x] Rerun idempotency verified
- [x] Snapshot regen protocol enforced

---

## Phase B — Legacy Closure ✅ COMPLETE

### B.1 Remove final legacy model dependency
- [x] TrackInfo / AlbumInfo fully removed from core
- [x] `resonance/core/models.py` deleted
- [x] Legacy code isolated under `resonance/legacy/`
- [x] V3 test suite green

### B.2 Declare V2 closed
- [x] V2 closure documented
- [x] Explicit deferrals recorded
- [x] CLI no longer exposes V2 paths

---

## Phase C — Feature Delivery (IN PROGRESS)

### C.1 Provider integration — Discogs
- [x] Discogs adapter implemented
- [x] Normalized ProviderRelease output
- [x] Deterministic artist/work canonicalization
- [x] Stable track + disc inference
- [x] Singles / EP detection
- [x] Prevent single→album false upgrades

### C.2 Provider integration — MusicBrainz
- [x] MusicBrainz adapter implemented
- [x] Multi-medium preservation
- [x] Write MB IDs into tags
- [x] Enforce no-rematch when MB IDs present

### C.3 Provider fusion & caching
- [x] Deterministic Discogs + MB merge
- [x] Versioned cache schema
- [x] Bounded, reproducible eviction
- [x] Zero network calls on rerun
- [x] Offline mode semantics:
  - [x] cache-hit works
  - [x] cache-miss yields deterministic outcome

### C.4 Planner completeness
- [x] Classical v1 layout rules
- [x] Deterministic filename sanitization
- [x] Conflict strategy encoded in Plan (default FAIL)

### C.5 Tag writing (real backends)
- [x] FLAC/Vorbis tagging E2E
- [x] MP3/ID3 tagging E2E
- [x] M4A/MP4 tagging E2E
- [x] Overwrite-aware diffs
- [x] Provenance tags
- [x] Tag rollback

### C.6 Applier safety & crash guarantees
- [x] Idempotent apply (formalized)
- [x] Crash-after-move recovery
- [x] Rollback correctness
- [x] Clear diagnostics

### C.7 CLI infrastructure & determinism

- [x] Deterministic human output (output.py envelope)
- [x] `--json` machine output (JSON envelope format)
- [x] Stable exit codes (error taxonomy)
- [x] Prompt UX implementation (run_prompt_uncertain exists)
- [ ] **WORKFLOW COMMANDS NOT WIRED TO CLI** (see Phase E)

---

## Phase D — Acceptance Gate ✅ COMPLETE

### D.1 Big-10 acceptance suite
- [x] Single track / single release
- [x] Standard album
- [x] Multi-disc album
- [x] Box set
- [x] Compilation
- [x] Artist name variants
- [x] Classical album
- [x] Live album
- [x] Hidden track oddities
- [x] Album with extras

Each scenario must assert:
- deterministic ranking
- correct layout
- correct tags
- silent rerun (no rematches)

---

## Phase E — Workflow Integration ✅ COMPLETE

**Status:** All CLI workflow commands implemented, tested, and documented.

**Current state:**
- ✅ `LibraryScanner` exists and tested
- ✅ `resolve_directory()` exists and tested
- ✅ `run_prompt_uncertain()` exists and tested
- ✅ `resonance scan` command wired and tested (5 integration tests)
- ✅ `resonance resolve` command wired and tested (3 integration tests)
- ✅ `resonance prompt` command wired and tested (5 integration tests)
- ✅ End-to-end workflow test using CLI (3 tests)
- ✅ README updated with workflow documentation

### E.1 Wire scan command to CLI ✅ COMPLETE

- [x] Add `resonance scan <library-root>` command
  - [x] Accepts `--state-db PATH` (required)
  - [x] Accepts `--json` for machine output
  - [x] Calls `LibraryScanner` for batch discovery
  - [x] Writes directory records to state DB
  - [x] Reports: X directories scanned, Y new, Z already tracked
  - [x] Returns exit code 0 on success

- [x] Integration test: scan command (tests/integration/test_scan_cli.py - 5 tests)
  - [x] Test: scan populates state DB with NEW directories
  - [x] Test: rescan skips already-scanned dirs with same signature
  - [x] Test: `--json` output is deterministic
  - [x] Test: scan on non-existent path returns error exit code
  - [x] Test: JSON error output is well-formed

### E.2 Wire resolve command to CLI ✅ COMPLETE

- [x] Add `resonance resolve <library-root>` command
  - [x] Accepts `--state-db PATH` (required)
  - [x] Accepts `--cache-db PATH` for provider cache
  - [x] Accepts `--json` for machine output
  - [x] Processes NEW directories (QUEUED_RESCAN not implemented)
  - [x] Auto-pins CERTAIN tier → RESOLVED_AUTO
  - [x] Queues PROBABLE/UNSURE → QUEUED_PROMPT
  - [x] Reports: X auto-resolved, Y queued for prompt, Z errors
  - [x] Returns exit code 0 on success

- [x] Integration test: resolve command (tests/integration/test_resolve_cli_simple.py - 3 tests)
  - [x] Test: resolve processes NEW directories
  - [x] Test: `--json` output is valid and parseable
  - [x] Test: resolve on non-existent path returns error

### E.3 Wire prompt command to CLI ✅ COMPLETE

- [x] Add `resonance prompt` command
  - [x] Accepts `--state-db PATH` (required)
  - [x] Accepts `--cache-db PATH` for provider cache
  - [x] Fetches all QUEUED_PROMPT directories
  - [x] For each directory:
    - [x] Shows file list with durations
    - [x] Shows candidate releases with scores
    - [x] Offers options: select candidate, manual ID, jail, skip
  - [x] Updates state to RESOLVED_USER on selection
  - [x] Returns exit code 0 on success

- [x] Integration test: prompt command CLI wrapper (tests/integration/test_prompt_cli_wrapper.py - 5 tests)
  - [x] Test: CLI entry point successfully routes to run_prompt_uncertain
  - [x] Test: candidate selection updates state to RESOLVED_USER
  - [x] Test: manual ID entry (mb:ID, dg:ID) works
  - [x] Test: jail option transitions to JAILED
  - [x] Test: skip leaves directory in QUEUED_PROMPT

### E.4 End-to-end workflow integration test ✅ COMPLETE

- [x] CLI workflow test: scan → resolve → prompt (tests/integration/test_e2e_cli_workflow.py - 3 tests)
  - [x] Setup: library with 3 albums
  - [x] Step 1: `scan` discovers all 3 directories
  - [x] Step 2: `resolve` processes directories (queues for prompt)
  - [x] Step 3: `prompt` resolves queued directories
  - [x] Verify: all directories reach RESOLVED_USER state
  - Note: plan → apply steps tested separately in existing integration tests

- [x] CLI idempotency test: rerun workflow = no-op
  - [x] After first scan and resolve
  - [x] Rerun: `scan → resolve`
  - [x] Assert: no new provider calls (no-rematch invariant)
  - [x] Assert: scan skips already tracked directories
  - [x] Assert: resolve finds no NEW directories to process

- [x] CLI JSON mode test
  - [x] Run scan and resolve with `--json`
  - [x] Assert: all outputs are valid JSON
  - [x] Assert: schema version is consistent (v1)
  - [x] Assert: machine parseable (no human prose in JSON)

### E.5 Update README to match CLI reality ✅ COMPLETE

- [x] README workflow section matches implemented commands
  - [x] Document: `scan`, `resolve`, `prompt`, `plan`, `apply`
  - [x] Remove references to unimplemented commands
  - [x] Add example workflow with actual command output
  - [x] Document state transitions (NEW → QUEUED_PROMPT → RESOLVED_USER → PLANNED → APPLIED)
  - [x] Add key invariants (no-rematch, idempotent, deterministic)
  - [x] Document JSON output mode

---

## Definition of Done (V3)

V3 is complete when:

1. ✅ Phase A and B are complete (DONE).
2. ✅ Providers are fully integrated with caching and offline semantics (DONE).
3. ✅ Tagging works across FLAC/MP3/M4A with rollback (DONE).
4. ✅ Planner outputs are complete and conflict-safe (DONE).
5. ✅ Big-10 suite is green (DONE).
6. ✅ Reruns are silent, deterministic, and offline-safe (DONE).
7. ✅ **CLI implements full scan → resolve → prompt → plan → apply workflow** (Phase E complete).

**Current Status:** V3 is complete. All phases delivered, all tests passing (379 tests), workflow documented.

---

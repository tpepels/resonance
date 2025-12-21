# TDD TODO V3 — Consolidated, Audit-Aligned, Execution-Ordered

**Purpose:**
Deliver V3 feature completeness **without regressing determinism, identity, or safety**.

This document is the **only executable TODO**.
Audit findings are referenced inline for context and risk awareness.

---

## EXECUTION ORDER & GATES (READ FIRST)

This TODO is executed in **strict phases**.
Later phases **must not proceed** until earlier phases are green.

### Phase A — Invariant Lock ✅ **COMPLETE**

Freeze identity, canonicalization, no-rematch behavior, and determinism.
No provider, tagging, or move work may proceed until Phase A is green.

**Status: All Phase A requirements complete. Phase B may now proceed.**

### Phase B — Legacy Closure ✅ **COMPLETE**

Remove remaining V2 ambiguity and formally close V2.

**Status: All Phase B requirements complete. Phase C may now proceed.**

### Phase C — Feature Delivery (V3 Proper)

Providers, tagging, moves, UX, Big-10 acceptance.

> Audit references explain *why* certain sections are blocking.
> See `CONSOLIDATED_AUDIT.md` anchors referenced inline.

---

### A.1 Canonicalization authority & surface ✅

**Goal:** one authoritative, explicit, testable canonicalization layer.

* [x] Extract canonicalization into a single core module
  * Implemented: `resonance/core/identity/canonicalize.py`
* [x] Explicitly separate:
  * `display_*` (human-readable, diacritics preserved) ✅
  * `match_key_*` (aggressive equivalence for matching/caching) ✅
* [x] Canonicalization functions are **pure**
  * No side effects, no cache access, deterministic
* [x] Persistence of aliases (if any) lives only in `DirectoryStateStore`
  * Pure functions delegate to DirectoryStateStore for persistence
* [x] `MetadataCache` is not used for canonicalization
  * Verified - cache is not involved in canonicalization

> Audit context: canonicalization ambiguity enables identity drift
> See CONSOLIDATED_AUDIT.md §C-1
> (anchor: `audit-C1-dual-architecture`)
>
> **Implementation:**
>
> * Module: `resonance/core/identity/canonicalize.py` (9 pure functions)
> * Tests: `tests/unit/test_canonicalize.py` (39 tests)
> * Export: `resonance/core/identity/__init__.py`

---

### A.2 Stable directory identity & no-rematch invariant ✅

**Goal:** once resolved, a directory is never re-matched unless content changes.

* [x] Integration test:
  * scan → resolve → apply ✅
  * rerun → **no provider calls**, **no plan**, **no mutations** ✅
  * Implemented: `test_no_rematch_on_rerun_full_pipeline`
* [x] Integration test:
  * manual rename ✅
  * rerun → deterministic repair, no re-identify ✅
  * Implemented: `test_manual_rename_does_not_trigger_rematch`
* [x] Enforce: provider calls forbidden for unchanged `RESOLVED_*` dirs
  * Fixed three bugs: signature stability, metadata preservation, state checking

> Audit context: re-matches are the primary user-visible failure mode
> See CONSOLIDATED_AUDIT.md §C-1, §1.2
> (anchors: `audit-C1-dual-architecture`, `audit-golden-corpus`)
>
> **Implementation:**
>
> * Tests: `tests/integration/test_no_rematch_invariant.py` (2 comprehensive tests)
> * Bug fixes documented: `PHASE_A2_FINDINGS.md`
> * Fixes: `signature.py`, `tag_writer.py`, `resolver.py`

---

### A.3 Golden corpus as hard gate ✅

**Goal:** freeze invariants before feature expansion.

* [x] Golden corpus runs **before all other V3 suites**
  * Implemented via `pytest_collection_modifyitems` hook in `tests/integration/conftest.py`
* [x] Failure of any scenario blocks further work
  * Documented protocol in `GOLDEN_CORPUS.md`
* [x] At least one minimal scenario:
  * **26 comprehensive scenarios** covering standard albums, classical, edge cases
  * standard album ✅
  * snapshot: layout, tags, state ✅
  * rerun = no-op (idempotency check) ✅
* [x] Snapshot regeneration requires explicit justification
  * Warning system implemented in `tests/integration/conftest.py`
  * Documentation in `GOLDEN_CORPUS.md` with protocol

> Audit context: golden corpus is the determinism firewall
> See CONSOLIDATED_AUDIT.md §1.2, §6.1
> (anchors: `audit-golden-corpus`, `audit-stop-ship`)
>
> **Implementation:**
>
> * Test: `tests/integration/test_golden_corpus.py`
> * Enforcement: `tests/integration/conftest.py`
> * Documentation: `GOLDEN_CORPUS.md`
> * Scenarios: `tests/golden/corpus_builder.py` (26 scenarios)
> * Snapshots: `tests/golden/expected/{scenario}/`

---

## Phase B — Legacy Closure ✅ **COMPLETE**

### B.1 Remove final legacy model dependency ✅

**Goal:** eliminate all remaining V2 gravity wells.

* [x] Replace remaining `TrackInfo` / `AlbumInfo` uses with V3 DTOs
  * V2 code moved to `resonance/legacy/`
* [x] Delete `resonance/core/models.py`
  * Moved to `resonance/legacy/models.py`
* [x] Fix imports and tests until green
  * 317 tests passing (V3 only)
  * 6 V2 tests moved to `tests/legacy/`

> Audit context: dual architecture bypasses invariants
> See CONSOLIDATED_AUDIT.md §C-1
> (anchor: `audit-C1-dual-architecture`)
>
> **Implementation:**
>
> * Legacy code: `resonance/legacy/` (models, services, providers, prescan)
> * Legacy tests: `tests/legacy/` (6 V2 tests)
> * Prescan command removed from CLI

---

### B.2 Declare V2 closed (with explicit deferrals) ✅

* [x] Add V2 closure note:
  * "Deferred to V3 or post-V3"
    * offline provider mode ✅
    * advanced canonical aliasing ✅
    * golden corpus expansion ✅
* [x] Declare V2 **closed** ✅

> **Implementation:**
>
> * Documentation: `V2_CLOSURE.md`
> * All V2 code isolated in `resonance/legacy/`
> * V3 tests: 317 passing (increased from 334 due to 6 V2 tests moved to legacy + 11 new tests from Phase A)

---

## Phase C — Feature Delivery (V3 Proper)

### C.1 Provider integration — Discogs

* [ ] Canonicalize Discogs output into internal `ReleaseCandidate`
* [ ] Deterministic artist/work canonicalization via match keys
* [ ] Stable track/disc inference
* [ ] Singles / EP detection
* [ ] Prevent single→album false upgrades

---

### C.2 Provider integration — MusicBrainz

* [ ] Canonicalize MB output into internal `ReleaseCandidate`
* [ ] Multi-medium preservation
* [ ] Write MB IDs into tags
* [ ] Rerun does not rematch when MB IDs exist

---

### C.3 Provider fusion & caching

* [ ] Deterministic merge of Discogs + MB candidates
* [ ] Versioned, bounded, reproducible cache
* [ ] Resolved dirs never hit network again
* [ ] Offline mode:

  * cache-hit works
  * cache-miss yields deterministic “needs network”

---

### C.4 Planner completeness

* [ ] Classical v1 path rules:

  * single composer → `Composer/Album`
  * mixed composer → `PerformerOrAlbumArtist/Album`
* [ ] Deterministic filename sanitization
* [ ] Conflict strategy encoded in plan (default FAIL)

---

### C.5 Tag writing (real backends)

* [ ] FLAC/Vorbis tagging E2E
* [ ] MP3/ID3 tagging E2E
* [ ] M4A/MP4 tagging E2E
* [ ] Overwrite-aware diffs
* [ ] Provenance tags
* [ ] Tag rollback support

---

### C.6 Applier safety & crash guarantees

* [ ] Idempotent apply
* [ ] Crash-after-move recovery
* [ ] Rollback correctness
* [ ] Clear failure diagnostics

> Audit context: crash recovery is STOP-SHIP risk
> See CONSOLIDATED_AUDIT.md §3.1
> (anchor: `audit-crash-recovery`)

---

### C.7 CLI completeness & determinism

* [ ] Deterministic human output
* [ ] `--json` machine output
* [ ] Stable exit codes
* [ ] Prompt UX with scores + reasons

---

### C.8 Big-10 acceptance suite (FINAL GATE)

**Scenarios:**

* [ ] Single track / single release
* [ ] Standard album
* [ ] Multi-disc album
* [ ] Box set
* [ ] Compilation
* [ ] Artist name variants
* [ ] Classical album
* [ ] Live album
* [ ] Hidden track oddities
* [ ] Album with extras

Each must assert:

* sensible ranking
* correct layout
* correct tags
* rerun clean (no rematches)

---

## Post-V3 Backlog (Explicitly Non-Blocking)

Canonicalization-dependent scenarios (add only after match/display split):

* Featured artist normalization
* Work nickname aliases
* Ensemble abbreviations

Scanner-only integration tests:

* Orphaned track reunification
* Split album merge

---

## Definition of Done (V3)

V3 is complete when:

1. Phase A and B are green.
2. Golden corpus invariants are frozen.
3. Providers integrated without re-matches.
4. Tagging works across formats with rollback.
5. Big-10 suite passes cleanly.
6. Reruns are deterministic and silent.

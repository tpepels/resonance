# Resonance Consolidated Audit Report

**Generated:** 2025-12-21
**Test Suite:** 483 tests
**Golden Corpus:** 26 scenarios (25 snapshot-backed + 1 scanner-skip)
**Architecture:** V3 Core + Legacy V2 Visitors

---

## Executive Summary

Resonance is in **early V3** with a solid deterministic core pipeline (scan → identify → resolve → plan → apply) protected by a comprehensive golden corpus. The project has **strong test coverage** (483 tests, up from 234 in December 2020) and enforces **core invariants** through snapshot testing.

**Key Strengths:**
- ✅ **Determinism:** All core operations are reproducible with content-based identity
- ✅ **Test Coverage:** 483 tests covering happy paths, identity logic, and edge cases
- ✅ **Golden Corpus:** 26 real-world scenarios with frozen snapshots
- ✅ **Core Invariants:** Signature-based identity, no re-matches, idempotent operations

**Critical Gaps:**
- 🎯 **Dual Architecture:** V2 visitor pipeline deprecated, ready for removal (~4 hours work, 1,200 LOC)
- 🟡 **Crash Recovery:** Core crash cases covered; still missing DB/WAL and concurrent crash scenarios
- 🟡 **Schema Versioning:** Downgrade protection + migrations covered; concurrent/compat tests remain
- ✅ **Service Construction:** DirectoryStateStore now constructed once at composition root

**Overall Grade:** 🟡 **B-** (Good coverage, strong determinism, but architectural debt and safety gaps)

---

## 1. Test Coverage Analysis

### 1.1 Test Inventory (483 Total Tests)

| Category | Tests | Status | Notes |
|----------|-------|--------|-------|
| **Unit Tests** | ~180 | ✅ GREEN | Core logic, identity, signature, planner |
| **Integration Tests** | ~280 | ✅ GREEN | Full pipeline, provider fusion, CLI |
| **Golden Corpus** | 26 scenarios | ✅ GREEN | Snapshot-based regression tests |
| **Crash Recovery** | 6 | 🟡 IN PROGRESS | Covers move-before-commit, rollback failure, tag-write crash, disk full, permission denied, tags-after-moves |
| **Schema Versioning** | 4 | 🟡 IN PROGRESS | Downgrade protection + migrations covered |
| **Security (Path Safety)** | 8 | ✅ GOOD | Path traversal, SafePath validation |

**Determinism Score:** 🟢 **Excellent**
- No `datetime.now()` in assertions (uses fixed timestamps)
- No `random` or `uuid4` usage
- Explicit ordering in all collections
- 11 explicit determinism tests

**Isolation Score:** 🟢 **Good**
- All tests use isolated `tmp_path` fixtures
- Read-only corpus files (minor shared state risk)

**Assertion Quality:** 🟡 **Good**
- Specific status checks (not just "no exception")
- Some tests could validate more data

---

### 1.2 Golden Corpus Status

**Current:** 26 scenarios (target: 26 for V3) ✅

**Snapshot-Backed Scenarios (25):**
1. `standard_album` - Basic 10-track album
2. `multi_disc` - 2-disc set with disc numbers
3. `compilation` - Various Artists with multiple track artists
4. `name_variants` - AC/DC, Björk, Alt-J (punctuation/diacritics)
5. `classical` - Composer + performer structure
6. `extras_only` - Cover art, booklet, cue/log files
7. `single_track` - Single-track release
8. `mixed_media` - Audio + video files
9. `multi_composer` - Classical compilation (Beethoven + Mozart)
10. `long_titles` - >200 char filenames (truncation)
11. `renamed_mid_processing` - Directory renamed during processing
12. `missing_middle_tracks` - Non-contiguous track numbers (1,2,5,6)
13. `case_only_rename` - Case-insensitive filesystem handling
14. `interrupted_apply` - Partial file moves
15. `opus_normalization` - Classical catalog number formatting
16. `conductor_vs_performer` - Orchestral credit disambiguation
17. `multi_performer_work` - Different soloists per movement
18. `catalog_variants` - BWV, K., Hob., D. numbering
19. `partial_opera` - Non-contiguous opera excerpts
20. `partial_tags` - Missing album/artist, inferred from siblings
21. `duplicate_files` - Same fingerprint, different filenames
22. `remaster_vs_original` - Release year disambiguation (1973 vs 2023)
23. `hidden_track` - Track 0 (pregap) + track 99 (secret)
24. `unicode_normalization` - NFD vs NFC encoding
25. `invalid_year` - Year tags "0000" or "UNKNOWN"

**Scanner-Skip Validated (1):**
- `non_audio_only` - Directory with only .jpg/.cue/.log (no audio)

**Deferred (Requires Canonicalization System):**
- `featured_artist` - "feat." ⇔ "ft" ⇔ "featuring" normalization
- `work_nickname` - "Eroica" ⇔ "Symphony No. 3" aliases
- `ensemble_variants` - "LSO" ⇔ "London Symphony Orchestra" abbreviations

**Integration Tests (Not Golden Corpus):**
- Orphaned track reunification (multi-path setup)
- Split album merge (multi-directory setup)

**Skipped (Non-Deterministic):**
- Mixed encoding tags (mojibake) - unreliable to simulate

---

## 2. Architectural Compliance Review

### 2.1 Critical Violations (Must Fix Before V3 Complete)

#### C-1: Dual Architecture Creates Determinism Bypass ⚠️ **CRITICAL** → 🎯 **READY FOR REMOVAL**

**Location:** [resonance/visitors/](resonance/visitors/), [resonance/app.py](resonance/app.py), [resonance/commands/scan.py](resonance/commands/scan.py)

**Issue:** V2 visitor pipeline (`IdentifyVisitor`, `OrganizeVisitor`) operates on mutable `AlbumInfo` objects and bypasses:
- `DirectoryStateStore` state transitions
- `resolve_directory` signature validation
- `plan_directory` deterministic layout
- `apply_plan` audit trails

**Risk:**
- Visitors can trigger re-matches on every run (violates core invariant)
- No audit trail for visitor-based operations
- Golden corpus only validates V3 pipeline; visitor path untested for determinism

**Status:** CLI `scan/daemon/prompt` require `--legacy` and `ResonanceApp.create_pipeline()` now
requires `allow_legacy=True`, preventing accidental V2 usage outside explicit legacy paths. Legacy
pipeline creation emits a `DeprecationWarning` and uses lazy imports to avoid accidental V2 coupling.

**REMOVAL PLAN - Complete V2 Pipeline Deprecation:** ✅ **PHASES 1-2-4-5 COMPLETE**

**Phase 1: Remove Legacy Pipeline Code** ✅ **COMPLETE**
- [x] Delete `resonance/visitors/` directory entirely (5 files)
- [x] Delete `resonance/core/visitor.py` (VisitorPipeline base class)
- [⚠️] Keep `resonance/core/models.py` (still used by provider/service layer - deferred to Phase 3)

**Phase 2: Remove Legacy CLI Commands** ✅ **COMPLETE**
- [x] Delete `resonance/commands/scan.py` (V2-only scan command)
- [x] Delete `resonance/commands/daemon.py` (V2-only daemon command)
- [x] Clean up `resonance/commands/prompt.py` (kept V3 `run_prompt_uncertain`)
- [x] Update `resonance/cli.py` - Removed `scan`, `daemon`, `prompt` commands
- [x] Update README.md - Documented V3 pipeline usage

**Phase 3: Remove Legacy Cache (MetadataCache)** ⏸️ **DEFERRED**
- [ ] Audit `resonance/infrastructure/cache.py` usage
- [ ] Decision: Keep MetadataCache for canonicalization OR migrate to DirectoryStateStore
- [ ] `resonance/core/models.py` removal deferred - still used by providers

**Phase 4: Remove Legacy Tests** ✅ **COMPLETE**
- [x] Delete `tests/test_visitors/` directory
- [x] Delete 7 legacy integration test files
- [x] Delete `tests/unit/test_app.py` and `tests/unit/test_models.py`

**Phase 5: Clean Up ResonanceApp** ✅ **COMPLETE**
- [x] Remove `ResonanceApp.create_pipeline()` method entirely
- [x] Remove lazy visitor imports from `resonance/app.py`

**Actual Impact:**
- **Files deleted:** 17 files (24 files modified total)
- **Lines of code removed:** 6,457 LOC
- **Tests removed:** 189 legacy tests (294 tests remaining, all passing)
- **Breaking changes:** Commands `scan --legacy`, `daemon --legacy`, `prompt --legacy` removed
- **Migration:** Users must use V3 commands (`identify`, `plan`, `apply`)

**Remaining Work (Phase 3):**
- Decide fate of `resonance/core/models.py` (TrackInfo/AlbumInfo)
- Decide fate of MetadataCache (canonicalization vs. DirectoryStateStore migration)
- Provider layer refactoring if models are removed

---

#### C-2: No Single Composition Root 🔴 **BLOCKING**

**Location:** [resonance/commands/plan.py:41](resonance/commands/plan.py#L41), [resonance/commands/apply.py:87](resonance/commands/apply.py#L87)

**Issue:** `DirectoryStateStore` constructed ad-hoc in commands, violating stated principle: "All real services should be constructed at a single composition root."

**Risk:**
- Cannot inject stores for testing/dry-run
- Schema migrations not centralized
- Daemon mode cannot share state safely

**Fix:**
- [ ] Add `DirectoryStateStore` to `ResonanceApp.__init__()`
- [ ] Expose as `app.store`
- [ ] Commands delegate construction to `ResonanceApp.from_env()`

**Status:** CLI now constructs `DirectoryStateStore` once and injects it into `run_plan`/`run_apply` (no ad-hoc store creation in those commands).

---

#### C-3: Planner Not Pure — Depends on DirectoryStateStore 🟡 **DESIGN**

**Location:** [resonance/core/planner.py:198-297](resonance/core/planner.py#L198-L297)

**Issue:** `plan_directory()` declared "pure" but performs I/O (`store.get(dir_id)`).

**Risk:**
- Cannot unit test planner without store construction
- Violates functional purity claims
- Blocks parallelization/plan pre-generation

**Fix:**
- [x] Refactor: `plan_directory(record: DirectoryRecord, ...) -> Plan` (no store)
- [x] Caller fetches record from store first

**Status:** Planner is now pure; callers fetch `DirectoryRecord` before planning.

---

#### C-4: Duplicated Layout Logic 🟡 **DEBT**

**Location:**
- [resonance/core/models.py:147-208](resonance/core/models.py#L147-L208) (`AlbumInfo.destination_path`)
- [resonance/core/planner.py:168-196](resonance/core/planner.py#L168-L196) (`_compute_destination_path`)

**Issue:** Same layout rules exist in two places (V2 visitors vs V3 planner).

**Risk:**
- Changes to layout must be duplicated
- Visitor paths may diverge from planner paths
- Year formatting differs between implementations

**Fix:**
- [x] Extract single source of truth into shared layout helper
- [x] V2 `AlbumInfo.destination_path` now delegates to shared layout logic

**Status:** Layout rules consolidated via `resonance/core/layout.py` and reused by V2+V3.

---

#### C-5: Mutable Models Violate Purity Boundary 🟡 **DESIGN** → ✅ **RESOLVED BY V2 REMOVAL**

**Location:** [resonance/core/models.py:20-262](resonance/core/models.py#L20-L262)

**Issue:** `TrackInfo` and `AlbumInfo` are mutable (`@dataclass(slots=True)` without `frozen=True`). Visitors mutate them during processing.

**Risk:**
- Hard to reason about state changes
- Cannot parallelize visitor pipeline
- Re-running visitor has side effects
- Conflicts with V3's immutable `Plan`/`DirectoryRecord` design

**Resolution:** Delete `resonance/core/models.py` entirely as part of V2 removal (Phase 1). V3 uses immutable `DirectoryRecord` and `Plan` dataclasses instead.

---

#### C-6: Business Logic in Visitors 🔴 **VIOLATION** → ✅ **RESOLVED BY V2 REMOVAL**

**Location:** [resonance/visitors/identify.py:46-152](resonance/visitors/identify.py#L46-L152), [resonance/visitors/organize.py:35-124](resonance/visitors/organize.py#L35-L124)

**Issue:** Visitors contain fingerprinting, canonicalization, and file-move logic that duplicates `extract_evidence()`, `identify()`, and `apply_plan()`.

Per architecture: "No business logic in visitors."

**Risk:**
- Changes to identification/layout logic must be duplicated
- V2 and V3 pipelines can produce different results

**Resolution:** Delete entire `resonance/visitors/` directory as part of V2 removal (Phase 1). All business logic now lives in V3 core modules (`identifier.py`, `resolver.py`, `planner.py`, `enricher.py`, `applier.py`).

---

### 2.2 High Priority Technical Debt

#### H-1: sanitize_filename Duplicated
**Locations:** [resonance/services/file_service.py:132-167](resonance/services/file_service.py#L132-L167), [resonance/core/planner.py:80-123](resonance/core/planner.py#L80-L123)

**Fix:** Extract single implementation into `resonance/core/validation.py`

**Status:** Extracted to `resonance/core/validation.py`; planner + file service now use shared helper.

---

#### H-2: IdentifyVisitor Bypasses resolve_directory for Cached Decisions → ✅ **RESOLVED BY V2 REMOVAL**

**Location:** [resonance/visitors/identify.py:63-76](resonance/visitors/identify.py#L63-L76)

**Issue:** Reads `MetadataCache` indexed by path (not `dir_id`), so path changes bypass "dir_id is identity" invariant.

**Status:** Legacy cache now keyed by `dir_id` with fallback migration from path-based entries. Will be deleted entirely with V2 removal (Phase 3 - decision needed on canonicalization migration).

---

#### H-3: Enricher Not Pure — Depends on DirectoryState
**Location:** [resonance/core/enricher.py:117-146](resonance/core/enricher.py#L117-L146)

**Issue:** `build_tag_patch()` conditional on `resolution_state`, not just inputs.

**Fix:** Document explicitly as "deterministic but state-conditional" OR remove state checks, push to caller

**Status:** Documented as deterministic but state-conditional in `build_tag_patch`.

---

#### H-4: No Validation That plan.source_path Matches record.last_seen_path
**Location:** [resonance/core/applier.py:345-356](resonance/core/applier.py#L345-L356)

**Issue:** Applier validates signature hash but not source path. Stale plans could reference moved directories.

**Fix:** Add validation or document that plans are ephemeral

**Status:** Added validation in applier: plan source_path must match record last_seen_path.

---

### 2.3 Acceptable Patterns (Non-Issues)

✅ **Applier re-scans filesystem:** Intentional safety check (files could change after plan generation)
✅ **DirectoryStateStore uses threading.Lock:** Multi-threaded access support for daemon mode
✅ **Planner has classical detection, model has classical detection:** Different data sources (provider vs tags)
✅ **Tests construct stores inline:** Test code exempt from composition root principle
✅ **extract_evidence is stubbed:** V3 mid-implementation; interface defined, tests use fixtures
✅ **Applier dry-run writes audit artifacts:** Metadata about dry-run attempts, not state transitions

---

## 3. Safety Gaps (Critical for Production)

### 3.1 Crash Recovery (STOP-SHIP GAP)

**Coverage:** 🟡 **75%** (6/8 scenarios)

| Scenario | Tested? | Risk | Priority |
|----------|---------|------|----------|
| Crash after all file moves, before DB commit | ✅ | **CRITICAL** | P0 |
| Crash during rollback | ✅ | **HIGH** | P0 |
| Power loss during SQLite transaction | ❌ | **MEDIUM** | P1 |
| Disk full during file move | ✅ | **MEDIUM** | P1 |
| Crash after file moves, before tag writes | ✅ | **MEDIUM** | P1 |
| Crash mid-tag write | ✅ | **LOW** | P2 |
| Permission denied mid-apply | ✅ | **LOW** | P2 |
| Multiple crashes (crash → recover → crash) | ❌ | **LOW** | P2 |

**Most Common Failure:** Crash after heavy file I/O succeeds but before fast DB commit.

**Current Behavior:** If all moves completed before a crash, re-apply returns `NOOP_ALREADY_APPLIED`
and updates state to `APPLIED` (verified by `test_applier_crash_after_file_moves_before_db_commit`).

**Status:** Crash-after-move, rollback failure, tag-write crash, disk-full, permission-denied, and
tags-after-moves scenarios are covered. Remaining gaps include DB/WAL failure modes.

---

### 3.2 Schema Versioning (STOP-SHIP GAP)

**Coverage:** 🟡 **57%** (4/7 scenarios)

| Scenario | Tested? | Risk | Priority |
|----------|---------|------|----------|
| v0.2.0 DB opened by v0.1.0 (downgrade) | ✅ | **CRITICAL** | P0 |
| v0.1.0 DB opened by v0.2.0 (upgrade migration) | ✅ | **CRITICAL** | P0 |
| Concurrent v1 and v2 running | ❌ | **HIGH** | P1 |
| Signature v1 + v2 algorithm (warns user) | ⚠️ | **MEDIUM** | P1 |
| Provenance v1 tags + app using v2 | ❌ | **MEDIUM** | P2 |

**Critical Gap:** Concurrent versions and signature-version mismatches need explicit handling.

**Recommended Test:**
```python
def test_directory_store_rejects_future_schema_version(tmp_path):
    """
    Opening a DB with schema_version > CURRENT_SCHEMA_VERSION must fail cleanly.
    """
    # Setup: create DB, manually set schema_version=99
    # Act: DirectoryStore(db_path)
    # Assert: raises ValueError("DB schema 99 > supported 4. Please upgrade Resonance.")
```

**Status:** Downgrade protection + migrations covered (`test_directory_store_rejects_future_schema_version`,
`test_schema_migration_from_v1_preserves_records`, `test_schema_migration_from_v3_preserves_records`).

---

### 3.3 Tag Validation (CRITICAL GAP)

**Coverage:** 🔴 **0%** (0/5 scenarios)

| Scenario | Tested? | Risk | Priority |
|----------|---------|------|----------|
| Tag value with null bytes | ❌ | **HIGH** | P1 |
| Tag value > 1000 chars | ❌ | **MEDIUM** | P2 |
| Tag value with invalid UTF-8 | ❌ | **MEDIUM** | P2 |
| Tag key namespace collision | ❌ | **LOW** | P2 |

**Risk:** Null bytes can truncate strings or crash parsers. No validation exists.

**Status:** Added validation in tag normalization and unit tests for null bytes, overlong values, and invalid UTF-8 bytes.

---

### 3.4 Path Safety (GOOD)

**Coverage:** 🟢 **75%** (4.5/6 scenarios)

✅ Path traversal (`../`) in source/destination
✅ Absolute paths outside allowed_roots
✅ Symlinks (scanner only, not applier)
⚠️ Null bytes in dir_id (format check only, not null-specific)

---

## 4. Test Quality Metrics

### 4.1 Determinism Practices

| Practice | Status | Evidence |
|----------|--------|----------|
| No `datetime.now()` in assertions | ✅ GREEN | Uses fixed timestamps, UTC Z format |
| No `random`/`uuid4` | ✅ GREEN | No usage found |
| Explicit ordering | ✅ GREEN | 11 determinism tests |
| Fixed fingerprints | ✅ GREEN | All golden corpus uses `fp-*` IDs |
| Isolated temp dirs | ✅ GREEN | All tests use `tmp_path` |

**Flakiness Risk:** 🟢 **LOW**

---

### 4.2 Assertion Quality

✅ **Good:** Specific status checks (`ApplyStatus.APPLIED`, not just "no exception")
✅ **Good:** File existence validation
⚠️ **Warning:** Some tests check only "success" without validating data contents

---

### 4.3 Test Documentation

✅ **Good:** Descriptive test names (`test_applier_fails_on_signature_mismatch`)
⚠️ **Warning:** Some complex tests lack docstrings explaining "why"

**Recommendation:** Add docstrings to complex tests explaining:
- What scenario is being tested
- Why it's important (crash safety, user request, bug fix)
- Expected behavior

---

## 5. V3 Definition of Done Progress

**From TDD_TODO_V3.md:**

| Requirement | Status | Notes |
|-------------|--------|-------|
| 1. Core invariants gate (golden corpus) | ✅ GREEN | 26/26 scenarios |
| 2. Discogs + MusicBrainz integrated | ⚙️ IN PROGRESS | Provider fixtures ready |
| 3. Tag writing (FLAC/MP3/M4A) | ⚙️ IN PROGRESS | FLAC complete; MP3/M4A depend on mutagen (skipped when unavailable) |
| 4. Move/rename behavior | ⚙️ IN PROGRESS | Multi-disc/collision tests exist |
| 5. Big 10 suite green | ❌ NOT STARTED | Waiting on provider integration |

**V3 Blocker:** Big 10 suite and provider integration.

---

## 6. Recommendations

### 6.1 Immediate (This Sprint)

**Stop-Ship Issues (13 hours total):**

1. **Crash Recovery Test** (3 hours) - `test_applier_crash_after_file_moves_before_db_commit`
   - Most common crash scenario
   - Validates partial completion detection
   - Demonstrates recovery strategy

2. **Schema Downgrade Protection** (2 hours) - `test_directory_store_rejects_future_schema_version`
   - Prevents silent data corruption
   - Add version check in `DirectoryStore.__init__()`

3. **Schema Upgrade Migration** (3 hours) - `test_directory_store_migrates_schema_v1_to_v2`
   - Users upgrading Resonance must not lose data

4. **Rollback Failure Reporting** (2 hours) - `test_rollback_failure_provides_detailed_state_report`
   - User needs clear state for manual recovery

5. **Path Traversal at Deserialization** (2 hours) - `test_plan_deserialization_rejects_path_traversal`
   - Move validation to `Plan.from_json()` (closes TOCTOU gap)

6. **Partial State Granular Diagnostics** (1 hour) - Enhance `CompletionAnalysis`
   - Distinguish "both_missing" vs "duplicated" vs "half-written"

---

### 6.2 Short-Term (Next 2 Sprints)

1. **Architectural Decision: V2 Visitors** (4-16 hours)
   - [ ] Decide: Deprecate OR harmonize with V3
   - [ ] If deprecating: Remove visitor code, update CLI
   - [ ] If harmonizing: Refactor to call V3 pipeline functions

2. **Single Composition Root** (4 hours)
   - [ ] Add `DirectoryStateStore` to `ResonanceApp`
   - [ ] Commands delegate construction to app

3. **Tag Validation** (4 hours)
   - [ ] Null byte rejection
   - [ ] Length limits (1KB per tag)
   - [ ] UTF-8 validation

4. **Planner Purity** (3 hours)
   - [ ] Refactor: Accept `DirectoryRecord` instead of `DirectoryStateStore`

---

### 6.3 Medium-Term (Post-V3)

1. **Canonicalization System** (TBD)
   - Implement `match_key_*` vs `display_*` separation
   - Add 3 deferred golden corpus scenarios

2. **Big 10 Suite** (TBD)
   - Define 10 real-world music libraries
   - Test full pipeline on realistic data

3. **Quality Improvements**
   - Add docstrings to complex tests
   - Replace permission manipulation with mocks
   - Extract sanitization functions to validation module

---

## 7. Summary & Metrics

### Current State
- **Tests:** 483 (up from 234 in Dec 2020)
- **Golden Corpus:** 26 scenarios (V3 target: complete)
- **Determinism:** Excellent (no flaky tests, explicit ordering)
- **Coverage:** Strong happy paths, remaining gaps in crash recovery and schema concurrency

### Grade Progression

| Milestone | Grade | Coverage | Missing |
|-----------|-------|----------|---------|
| **Current (Dec 2025)** | 🟡 **B-** | 75% | Crash recovery, schema versioning, V2 deprecation |
| **Stop-Ship Complete** | 🟢 **B+** | 85% | +6 critical tests (13 hours) |
| **V3 Complete (DoD)** | 🟢 **A-** | 90% | V2 removed, Big 10 green |

### Risk Summary

| Risk Area | Current | Target | Priority |
|-----------|---------|--------|----------|
| **Crash Recovery** | 🟡 75% | 🟢 80% | P0 - STOP-SHIP |
| **Schema Versioning** | 🟡 57% | 🟢 90% | P0 - STOP-SHIP |
| **Tag Validation** | 🟢 100% | 🟢 100% | ✅ DONE |
| **Path Safety** | 🟢 75% | 🟢 90% | P2 - MEDIUM |
| **V2/V3 Dual Arch** | 🎯 DEPRECATED | ✅ READY TO REMOVE | P0 - CRITICAL |

**V2 Legacy Status:**
- V2 visitor pipeline fully deprecated with `--legacy` flags required
- Removal plan documented (5 phases, ~4 hours effort)
- Ready to delete ~1,200 LOC across 15 files
- Blocker: Canonicalization migration decision needed (MetadataCache fate)

---

## 8. Appendices

### A. Related Documents

- **TDD_TODO_V3.md** - V3 implementation roadmap and golden corpus plan
- **TODO_REVIEW_V3.md** - Architectural compliance review (this audit)
- **Resonance_DESIGN_SPEC.md** - Architecture specification
- **README.md** - Project overview

### B. Test File Locations

- **Golden Corpus:** `tests/golden/corpus_builder.py`, `tests/golden/expected/`
- **Integration Tests:** `tests/integration/test_*.py`
- **Unit Tests:** `tests/unit/test_*.py`
- **Helpers:** `tests/helpers/`

### C. Key Architectural Files

- **Composition Root:** `resonance/app.py`
- **Pipeline Phases:** `resonance/core/{identifier,resolver,planner,enricher,applier}.py`
- **State Management:** `resonance/infrastructure/directory_store.py`
- **V2 Visitors (Legacy):** `resonance/visitors/`

---

**End of Consolidated Audit**

*This document supersedes: AUDIT_SUMMARY.md, CANONICALIZATION_AUDIT.md, TEST_AUDIT.md, V3_TEST_AUDIT.md, GOLDEN_CORPUS_ROADMAP.md*

*Note: This audit does not touch TDD_TODO_V3.md, which remains the authoritative implementation roadmap.*
---

## 9. Minimal‑Churn TODO (V2 Close‑Out → V3 Unblock)

The following TODO integrates the agreed **minimal‑churn plan** directly into the audit.
It represents the **only remaining work** required to fully close V2 and safely unblock V3.
No scope expansion is implied.

### Goal

Finish V2 cleanly and unblock V3 by:

- removing the **last legacy ambiguity**
- freezing **canonicalization + identity**
- enabling the **V3 golden‑corpus gate**

No new features. No refactors beyond what is strictly necessary.

---

### 9.1 Decide Canonicalization Ownership (Single Decision)

**Decision (recommended):**

- Canonicalization logic lives in **core as pure functions**
- Learned / explicit aliases are persisted in **DirectoryStateStore**
- `MetadataCache` is **not** used for canonicalization

**Tasks**
- [ ] Declare `MetadataCache` read‑only or deprecated for canonicalization
- [ ] Add explicit documentation:

  > “Canonicalization is pure; persistence (if any) lives in DirectoryStateStore.”

This is a decision task, not an implementation refactor.

---

### 9.2 Extract Canonicalization into a Single Explicit Surface

Freeze existing behavior; do not redesign.

**Tasks**
- [ ] Create `core/canonicalize.py` exposing:
  - `canonical_display_*`
  - `canonical_match_key_*`
- [ ] Move existing normalization logic without behavior changes
- [ ] Add unit tests covering:
  - diacritics (Björk / Bjork)
  - punctuation & slashes (AC/DC)
  - comma‑style names (Beatles, The)
  - collaboration markers (`feat`, `with`, `w/`)

---

### 9.3 Remove Final Legacy Model Dependency (Surgical)

This completes V2 removal.

**Tasks**
- [ ] Replace remaining uses of `TrackInfo` / `AlbumInfo` with V3 DTOs
- [ ] Delete `resonance/core/models.py`
- [ ] Fix imports and tests until green

---

### 9.4 Add Golden Corpus Skeleton (Infrastructure Only)

Minimal V3 scaffolding; no providers yet.

**Tasks**
- [ ] Add `tests/golden/` base structure
- [ ] Add deterministic corpus builder:
  - audio file creation
  - extras handling
- [ ] Add **one** golden scenario:
  - standard album (no Discogs / MB)
- [ ] Snapshot:
  - layout
  - tags
  - state
- [ ] Assert idempotency (second run = no‑op)

---

### 9.5 Lock “No Re‑Match” at Integration Level

Primary user‑visible invariant.

**Tasks**
- [ ] Integration test:
  - scan → resolve → apply
  - rerun → no provider calls, no plan, no mutations
- [ ] Integration test:
  - manual rename
  - rerun → deterministic repair, no re‑identify

---

### 9.6 Explicitly Close V2

Eliminate ambiguity and cognitive overhead.

**Tasks**
- [ ] Add V2 section:
  **“Deferred to V3”**
  - offline provider mode
  - provider fusion
  - golden corpus expansion
- [ ] Declare V2 **closed**

---

### Out of Scope (By Design)

- No new provider features
- No canonicalization improvements beyond freezing
- No golden corpus expansion beyond one scenario
- No CLI / UX changes
- No refactors not blocking V3

---

### Result After Completion

- Legacy code fully removed
- Canonicalization has a single authority
- Identity and rematch behavior frozen
- V3 can proceed with confidence
- Regressions surface immediately via tests

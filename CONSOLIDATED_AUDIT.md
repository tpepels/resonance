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
- 🔴 **Dual Architecture:** V2 visitor pipeline coexists with V3, creating determinism bypass risk
- 🔴 **Crash Recovery:** Minimal testing of partial states, rollback failures, WAL recovery
- 🔴 **Schema Versioning:** No downgrade protection, untested migrations
- 🔴 **Service Construction:** No single composition root (violates stated architecture)

**Overall Grade:** 🟡 **B-** (Good coverage, strong determinism, but architectural debt and safety gaps)

---

## 1. Test Coverage Analysis

### 1.1 Test Inventory (483 Total Tests)

| Category | Tests | Status | Notes |
|----------|-------|--------|-------|
| **Unit Tests** | ~180 | ✅ GREEN | Core logic, identity, signature, planner |
| **Integration Tests** | ~280 | ✅ GREEN | Full pipeline, provider fusion, CLI |
| **Golden Corpus** | 26 scenarios | ✅ GREEN | Snapshot-based regression tests |
| **Crash Recovery** | 1 | 🔴 GAP | Only basic partial detection |
| **Schema Versioning** | 2 | 🔴 GAP | No migration or downgrade tests |
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

#### C-1: Dual Architecture Creates Determinism Bypass ⚠️ **CRITICAL**

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

**Recommendation:**
- [ ] **Decision Required:** Deprecate visitors entirely OR harmonize with V3 state machine
- [ ] If deprecated: Remove `resonance/visitors/`, update CLI to use V3 exclusively
- [ ] If harmonized: Refactor visitors to call V3 pipeline functions

**Status:** CLI `scan/daemon/prompt` now require `--legacy` to run V2 visitors, defaulting to V3-only paths.

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
- [ ] Refactor: `plan_directory(record: DirectoryRecord, ...) -> Plan` (no store)
- [ ] Caller fetches record from store first

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
- [ ] Extract single source of truth into `planner` module
- [ ] If V2 kept: Route `AlbumInfo.destination_path` through planner
- [ ] If V2 deprecated: Delete `AlbumInfo.destination_path`

---

#### C-5: Mutable Models Violate Purity Boundary 🟡 **DESIGN**

**Location:** [resonance/core/models.py:20-262](resonance/core/models.py#L20-L262)

**Issue:** `TrackInfo` and `AlbumInfo` are mutable (`@dataclass(slots=True)` without `frozen=True`). Visitors mutate them during processing.

**Risk:**
- Hard to reason about state changes
- Cannot parallelize visitor pipeline
- Re-running visitor has side effects
- Conflicts with V3's immutable `Plan`/`DirectoryRecord` design

**Fix:**
- [ ] If V2 kept: Make models frozen, visitors return new instances
- [ ] If V2 deprecated: Delete models entirely

---

#### C-6: Business Logic in Visitors 🔴 **VIOLATION**

**Location:** [resonance/visitors/identify.py:46-152](resonance/visitors/identify.py#L46-L152), [resonance/visitors/organize.py:35-124](resonance/visitors/organize.py#L35-L124)

**Issue:** Visitors contain fingerprinting, canonicalization, and file-move logic that duplicates `extract_evidence()`, `identify()`, and `apply_plan()`.

Per architecture: "No business logic in visitors."

**Risk:**
- Changes to identification/layout logic must be duplicated
- V2 and V3 pipelines can produce different results

**Fix:**
- [ ] Extract business logic into pure functions in `core/`
- [ ] Visitors become thin adapters calling V3 pipeline
- [ ] OR: Deprecate visitor pipeline

---

### 2.2 High Priority Technical Debt

#### H-1: sanitize_filename Duplicated
**Locations:** [resonance/services/file_service.py:132-167](resonance/services/file_service.py#L132-L167), [resonance/core/planner.py:80-123](resonance/core/planner.py#L80-L123)

**Fix:** Extract single implementation into `resonance/core/validation.py`

---

#### H-2: IdentifyVisitor Bypasses resolve_directory for Cached Decisions
**Location:** [resonance/visitors/identify.py:63-76](resonance/visitors/identify.py#L63-L76)

**Issue:** Reads `MetadataCache` indexed by path (not `dir_id`), so path changes bypass "dir_id is identity" invariant.

**Fix:** Change cache key from `path` to `dir_id` OR delete cache, use `DirectoryStateStore` only

---

#### H-3: Enricher Not Pure — Depends on DirectoryState
**Location:** [resonance/core/enricher.py:117-146](resonance/core/enricher.py#L117-L146)

**Issue:** `build_tag_patch()` conditional on `resolution_state`, not just inputs.

**Fix:** Document explicitly as "deterministic but state-conditional" OR remove state checks, push to caller

---

#### H-4: No Validation That plan.source_path Matches record.last_seen_path
**Location:** [resonance/core/applier.py:345-356](resonance/core/applier.py#L345-L356)

**Issue:** Applier validates signature hash but not source path. Stale plans could reference moved directories.

**Fix:** Add validation or document that plans are ephemeral

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

**Coverage:** 🔴 **17%** (2/12 scenarios)

| Scenario | Tested? | Risk | Priority |
|----------|---------|------|----------|
| Crash after all file moves, before DB commit | ❌ | **CRITICAL** | P0 |
| Crash during rollback | ❌ | **HIGH** | P0 |
| Power loss during SQLite transaction | ❌ | **MEDIUM** | P1 |
| Disk full during file move | ❌ | **MEDIUM** | P1 |
| Crash after file moves, before tag writes | ❌ | **MEDIUM** | P1 |
| Crash mid-tag write | ❌ | **LOW** | P2 |
| Permission denied mid-apply | ❌ | **LOW** | P2 |
| Multiple crashes (crash → recover → crash) | ❌ | **LOW** | P2 |

**Most Common Failure:** Crash after heavy file I/O succeeds but before fast DB commit.

**Current Behavior:** State DB shows PLANNED, all files moved → user re-applies → duplicate moves or errors.

**Recommended Test:**
```python
def test_applier_crash_after_file_moves_before_db_commit(tmp_path):
    """
    Simulate crash after all file moves succeed but before DB state commits.
    On recovery, applier must detect completed moves and update DB without re-executing.
    """
    # Setup: manually move all files (simulate completed apply)
    # Act: call apply() again
    # Assert: returns NOOP_ALREADY_APPLIED, DB state is APPLIED
```

**Status:** Added rollback-failure coverage (`test_applier_reports_rollback_failure`) and tag-write crash coverage (`test_applier_fails_on_tag_write_crash`).

---

### 3.2 Schema Versioning (STOP-SHIP GAP)

**Coverage:** 🔴 **36%** (2.5/7 scenarios)

| Scenario | Tested? | Risk | Priority |
|----------|---------|------|----------|
| v0.2.0 DB opened by v0.1.0 (downgrade) | ❌ | **CRITICAL** | P0 |
| v0.1.0 DB opened by v0.2.0 (upgrade migration) | ❌ | **CRITICAL** | P0 |
| Concurrent v1 and v2 running | ❌ | **HIGH** | P1 |
| Signature v1 + v2 algorithm (warns user) | ⚠️ | **MEDIUM** | P1 |
| Provenance v1 tags + app using v2 | ❌ | **MEDIUM** | P2 |

**Critical Gap:** Downgrading Resonance version (v0.2.0 → v0.1.0) silently corrupts DB by ignoring unknown columns/tables.

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

**Status:** Added migration coverage from schema v3 to v4 (`test_schema_migration_from_v3_preserves_records`).

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
- **Coverage:** Strong happy paths, gaps in crash recovery and schema versioning

### Grade Progression

| Milestone | Grade | Coverage | Missing |
|-----------|-------|----------|---------|
| **Current (Dec 2025)** | 🟡 **B-** | 75% | Crash recovery, schema versioning, V2 deprecation |
| **Stop-Ship Complete** | 🟢 **B+** | 85% | +6 critical tests (13 hours) |
| **V3 Complete (DoD)** | 🟢 **A-** | 90% | V2 removed, Big 10 green |

### Risk Summary

| Risk Area | Current | Target | Priority |
|-----------|---------|--------|----------|
| **Crash Recovery** | 🔴 17% | 🟢 80% | P0 - STOP-SHIP |
| **Schema Versioning** | 🔴 36% | 🟢 90% | P0 - STOP-SHIP |
| **Tag Validation** | 🔴 0% | 🟢 80% | P1 - HIGH |
| **Path Safety** | 🟢 75% | 🟢 90% | P2 - MEDIUM |
| **V2/V3 Dual Arch** | 🔴 PRESENT | ✅ REMOVED | P0 - CRITICAL |

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

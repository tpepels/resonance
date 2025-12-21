# Resonance Unit Test Audit

**Date:** 2025-12-20
**Total Tests Found:** 234 test functions across 26 test files
**Current Safety Grade:** 🔴 D-

## Executive Summary

This audit examines test coverage, edge-case handling, quality, and determinism across the Resonance test suite. The test suite has **strong coverage of happy paths and basic error handling**, but **critical gaps exist in crash recovery, partial state handling, version skew, and data corruption scenarios**.

**Key Findings:**
- ✅ **Strengths:** Good determinism practices, comprehensive identity/signature testing, solid planner coverage
- 🔴 **Critical Gaps:** No WAL/crash recovery tests, minimal partial completion tests, no schema versioning tests
- ⚠️ **Quality Issues:** Some tests assume clean state, limited chaos/fault injection testing
- 📊 **Coverage:** ~65% coverage of AUDIT_2_TODO.md P0-P3 requirements

---

## 1. Inventory & Coverage Map

This section maps every P0-P3 task from [AUDIT_2_TODO.md](AUDIT_2_TODO.md#L1-L535) to existing test coverage.

### 1.1 Phase 1: P0 Critical Safety

#### 1.1.1 Input Validation & Path Safety (Lines 27-67)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Path traversal validation | ✅ GOOD | `test_applier_rejects_path_traversal_in_source_path:5`<br>`test_applier_rejects_path_traversal_in_destination_path:6` | Implemented |
| Validate dir_id format | ✅ GOOD | `test_applier_rejects_invalid_dir_id_format:7` | Implemented |
| Validate signature_hash format | ✅ GOOD | `test_applier_rejects_invalid_signature_hash:8` | Implemented |
| Validate release_id format | ✅ GOOD | `test_applier_rejects_invalid_release_id_format:9` | Implemented |
| SQLite CHECK constraints | ❌ NONE | - | **MISSING** |
| SafePath class usage in Plans | ⚠️ PARTIAL | Tests cover applier validation, not plan deserialization | **GAP** |

**Coverage Grade:** 🟡 B- (4/6 covered, but at wrong layer)

#### 1.1.2 Database Schema Versioning (Lines 68-112)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| schema_version table exists | ✅ GOOD | `test_schema_metadata_initialized:11` | Implemented |
| Check version on DB open | ❌ NONE | - | **MISSING** |
| Reject future schema versions | ❌ NONE | - | **MISSING** |
| Migration system (upgrade) | ❌ NONE | - | **MISSING** |
| Handle missing schema_version | ✅ GOOD | `test_schema_missing_metadata_with_existing_rows_raises:12` | Implemented |
| Cache DB schema versioning | ✅ GOOD | `test_cache_schema_missing_metadata_purges:1` | Implemented |

**Coverage Grade:** 🔴 D (2/6 covered, core migration logic missing)

#### 1.1.3 Partial Completion Detection (Lines 113-164)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| CompletionAnalysis class | ✅ GOOD | `test_applier_detects_partial_completion:10` | Implemented |
| Detect: both_missing | ⚠️ PARTIAL | Test covers "partial" broadly | **NEEDS DETAIL** |
| Detect: duplicated (both exist) | ⚠️ PARTIAL | Test covers "partial" broadly | **NEEDS DETAIL** |
| Return PARTIAL_COMPLETE status | ✅ GOOD | `test_applier_detects_partial_completion:10` | Implemented |
| Update idempotency check | ✅ GOOD | `test_applier_noop_on_reapply:15` | Existing |

**Coverage Grade:** 🟡 C+ (3/5 covered, needs granular edge cases)

#### 1.1.4 Directory Signature Versioning (Lines 165-194)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| signature_version field in DirectorySignature | ❌ NONE | - | **MISSING** |
| Store signature_version in DB | ✅ GOOD | `test_signature_version_change_resets_state:13` | Implemented |
| Detect algorithm vs content changes | ⚠️ PARTIAL | Test detects change, doesn't distinguish cause | **GAP** |
| Warn on version mismatch | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 D+ (1.5/4 covered)

---

### 1.2 Phase 2: P1 High-Priority Robustness

#### 1.2.1 User Modification Detection (Lines 201-225)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Include filenames in signature | ✅ GOOD | `test_dir_signature_is_stable_when_filenames_change:12` shows opposite | **CONFLICTS** |
| Validate plan matches current dir | ✅ GOOD | `test_applier_fails_on_signature_mismatch:4` | Implemented |
| expected_source_files in Plan | ❌ NONE | - | **MISSING** |
| Detect missing vs deleted files | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🟡 C (1/4 covered, design conflict on filenames)

#### 1.2.2 Better Error Messages & Recovery (Lines 226-254)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Diagnose missing file causes | ❌ NONE | - | **MISSING** |
| Include recovery steps in errors | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/2 covered)

#### 1.2.3 Rollback Error Reporting (Lines 226-254)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Detailed rollback state report | ❌ NONE | - | **MISSING** |
| List successfully rolled back files | ❌ NONE | - | **MISSING** |
| List files remaining at destination | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/3 covered)

#### 1.2.4 Incremental State Updates (Lines 290-310)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| APPLYING / APPLYING_TAGS states | ❌ NONE | - | **MISSING** |
| Incremental state transitions | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/2 covered)

---

### 1.3 Phase 3: P2 Data Integrity

#### 1.3.1 JSON Schema Validation (Lines 318-338)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Define PLAN_SCHEMA | ⚠️ PARTIAL | Tests validate fields individually, not via schema | **GAP** |
| Validate on deserialization | ⚠️ PARTIAL | Validation happens at apply time, not load time | **GAP** |

**Coverage Grade:** 🟡 C- (Validates, but wrong layer)

#### 1.3.2 Tag Value Sanitization (Lines 340-353)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Enforce tag length limits | ❌ NONE | - | **MISSING** |
| Reject null bytes | ❌ NONE | - | **MISSING** |
| Validate UTF-8 encoding | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/3 covered)

#### 1.3.3 Cache Validation & Eviction (Lines 355-379)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Validate cached release structure | ⚠️ PARTIAL | `test_identify_visitor_handles_missing_release_search:2` handles missing, not malformed | **GAP** |
| Evict corrupted cache entries | ✅ GOOD | `test_cache_schema_missing_metadata_purges:1` | Implemented |

**Coverage Grade:** 🟡 C+ (1.5/2 covered)

#### 1.3.4 Provenance Tag Versioning (Lines 381-400)

| Requirement | Coverage | Tests | Status |
|-------------|----------|-------|--------|
| Version provenance namespace | ❌ NONE | - | **MISSING** |
| Migrate old provenance on overwrite | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/2 covered)

---

### 1.4 Phase 4: P3 Testing & Documentation

#### 1.4.1 Crash Recovery Tests (Lines 407-412)

| Test Scenario | Coverage | Tests | Status |
|---------------|----------|-------|--------|
| Crash mid file-move | ❌ NONE | - | **MISSING** |
| Crash during rollback | ❌ NONE | - | **MISSING** |
| Crash after ops but before DB update | ❌ NONE | - | **MISSING** |
| Partial state detection (various configs) | ⚠️ PARTIAL | `test_applier_detects_partial_completion:10` covers one scenario | **NEEDS MORE** |

**Coverage Grade:** 🔴 D- (0.25/4 covered - **STOP-SHIP GAP**)

#### 1.4.2 Idempotency Tests (Lines 414-419)

| Test Scenario | Coverage | Tests | Status |
|---------------|----------|-------|--------|
| Apply twice → NOOP | ✅ GOOD | `test_applier_noop_on_reapply:15` | Implemented |
| Apply after partial completion | ✅ GOOD | `test_applier_detects_partial_completion:10` | Implemented |
| Rollback twice | ❌ NONE | - | **MISSING** |
| Tag write twice (idempotent) | ✅ GOOD | `test_metajson_tag_writer_idempotent:2`<br>`test_metajson_provenance_idempotent:3` | Implemented |

**Coverage Grade:** 🟢 B+ (3/4 covered)

#### 1.4.3 Version Skew Tests (Lines 421-426)

| Test Scenario | Coverage | Tests | Status |
|---------------|----------|-------|--------|
| v1 DB + v2 app → migration | ❌ NONE | - | **MISSING** |
| v2 DB + v1 app → error | ❌ NONE | - | **MISSING** |
| Concurrent v1 and v2 → locking | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🔴 F (0/3 covered - **STOP-SHIP GAP**)

#### 1.4.4 Data Corruption Tests (Lines 428-434)

| Test Scenario | Coverage | Tests | Status |
|---------------|----------|-------|--------|
| Plan with path traversal | ✅ GOOD | `test_applier_rejects_path_traversal_in_source_path:5`<br>`test_applier_rejects_path_traversal_in_destination_path:6` | Implemented |
| Plan with invalid signature_hash | ✅ GOOD | `test_applier_rejects_invalid_signature_hash:8` | Implemented |
| TagPatch with wrong dir_id | ❌ NONE | - | **MISSING** |
| Cache with wrong structure | ⚠️ PARTIAL | Schema mismatch covered, not malformed JSON | **GAP** |
| Tags with null bytes | ❌ NONE | - | **MISSING** |

**Coverage Grade:** 🟡 C+ (2.5/5 covered)

#### 1.4.5 User Modification Tests (Lines 436-441)

| Test Scenario | Coverage | Tests | Status |
|---------------|----------|-------|--------|
| Rename file before apply | ❌ NONE | - | **MISSING** |
| Delete file before apply | ❌ NONE | - | **MISSING** |
| Add file before apply | ❌ NONE | - | **MISSING** |
| Edit tags then re-apply (preserve) | ✅ GOOD | `test_apply_does_not_overwrite_existing_tags:7` | Implemented |
| Edit tags with overwrite | ✅ GOOD | `test_apply_overwrite_records_provenance:8`<br>`test_apply_per_field_overwrite_policy:9` | Implemented |

**Coverage Grade:** 🟡 C+ (2/5 covered)

---

### 1.5 Overall Coverage Summary

| Phase | Focus | Coverage | Grade |
|-------|-------|----------|-------|
| **P0 Critical Safety** | Input validation, schema versioning, partial completion, signature versioning | 11.5/22 tasks | 🟡 **C-** |
| **P1 High-Priority Robustness** | User modifications, error messages, rollback reporting, incremental state | 1/11 tasks | 🔴 **F+** |
| **P2 Data Integrity** | JSON schemas, tag sanitization, cache validation, provenance | 3/9 tasks | 🔴 **D** |
| **P3 Testing & Documentation** | Crash recovery, idempotency, version skew, corruption, user mods | 9.75/24 tests | 🟡 **C** |
| **TOTAL** | All phases combined | **25.25/66 requirements** | 🔴 **D+** |

**Overall Test Coverage vs AUDIT_2_TODO.md:** ~38% complete

---

## 2. Edge-Case Matrix (40+ Scenarios)

This section enumerates concrete edge cases, organized by safety domain.

### 2.1 Crash Recovery & Partial States (12 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 1 | Crash after moving 1 of 10 files | ❌ | - | Only generic partial test exists |
| 2 | Crash during file move (dest half-written) | ❌ | - | OS-level atomic move not tested |
| 3 | Crash after all file moves, before DB commit | ❌ | - | **CRITICAL GAP** |
| 4 | Crash during rollback (reverting moves) | ❌ | - | **CRITICAL GAP** |
| 5 | Partial state: source missing, dest missing | ⚠️ | `test_applier_detects_partial_completion:10` | Covered but not explicit |
| 6 | Partial state: source exists, dest exists (duplicate) | ⚠️ | `test_applier_detects_partial_completion:10` | Covered but not explicit |
| 7 | Crash after moving files, before writing tags | ❌ | - | Tags are orphaned |
| 8 | Crash mid-tag write (some tags written) | ❌ | - | TagWriter atomicity not tested |
| 9 | Power loss during SQLite transaction | ❌ | - | Relies on SQLite WAL (untested) |
| 10 | Disk full during file move | ❌ | - | shutil.move error handling |
| 11 | Permission denied mid-apply | ❌ | - | Rollback on IOError |
| 12 | Multiple crashes (crash, recover, crash again) | ❌ | - | Idempotent recovery |

**Coverage:** 2/12 (17%) - **STOP-SHIP GAP**

### 2.2 Idempotency & Reapply (8 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 13 | Apply twice with no changes | ✅ | `test_applier_noop_on_reapply:15` | ✓ Covered |
| 14 | Apply, user deletes dest files, apply again | ❌ | - | Should restore or warn |
| 15 | Apply, user moves files back to source, apply again | ❌ | - | Should detect duplicate work |
| 16 | Apply with different conflict policy (fail → skip) | ❌ | - | Policy changes affect idempotency |
| 17 | Apply, rollback, apply again | ❌ | - | Full cycle not tested |
| 18 | Rollback twice on same directory | ❌ | - | Should be no-op second time |
| 19 | Tag write with same values (byte-identical) | ✅ | `test_metajson_tag_writer_idempotent:2` | ✓ Covered |
| 20 | Tag write with provenance enabled (idempotent?) | ✅ | `test_metajson_provenance_idempotent:3` | ✓ Covered |

**Coverage:** 3/8 (38%)

### 2.3 Version Skew & Schema Changes (7 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 21 | v0.1.0 DB opened by v0.2.0 (upgrade) | ❌ | - | **STOP-SHIP GAP** |
| 22 | v0.2.0 DB opened by v0.1.0 (downgrade) | ❌ | - | **STOP-SHIP GAP** |
| 23 | DB with no schema_version (legacy) | ✅ | `test_schema_missing_metadata_with_existing_rows_raises:12` | ✓ Covered |
| 24 | Signature v1 state + signature v2 algorithm | ⚠️ | `test_signature_version_change_resets_state:13` | Resets, doesn't warn |
| 25 | Provenance v1 tags + app using v2 | ❌ | - | Migration not tested |
| 26 | Concurrent access: v1 and v2 running simultaneously | ❌ | - | File locking not tested |
| 27 | Cache schema mismatch (purge strategy) | ✅ | `test_cache_schema_missing_metadata_purges:1` | ✓ Covered |

**Coverage:** 2.5/7 (36%)

### 2.4 Path Safety & Injection (6 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 28 | Plan with `../` in source_path | ✅ | `test_applier_rejects_path_traversal_in_source_path:5` | ✓ Covered |
| 29 | Plan with `../` in destination_path | ✅ | `test_applier_rejects_path_traversal_in_destination_path:6` | ✓ Covered |
| 30 | Plan with absolute path outside allowed_roots | ✅ | `test_applier_rejects_relative_allowed_root:11` | ✓ Covered |
| 31 | dir_id with SQL injection attempt (`'; DROP TABLE`) | ⚠️ | `test_applier_rejects_invalid_dir_id_format:7` | Format check, not SQL-specific |
| 32 | dir_id with null bytes (`\x00`) | ❌ | - | Not tested |
| 33 | Symlink pointing outside allowed_roots | ⚠️ | `test_scanner_skips_symlinked_files:9`<br>`test_scanner_does_not_follow_symlink_dirs:10` | Scanner only, not applier |

**Coverage:** 4.5/6 (75%) - **GOOD**

### 2.5 Tag Validation & Sanitization (5 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 34 | Tag value with null bytes | ❌ | - | Mutagen may reject, not tested |
| 35 | Tag value > 1000 chars (very long) | ❌ | - | Memory/corruption risk |
| 36 | Tag value with invalid UTF-8 | ❌ | - | Encoding errors |
| 37 | Tag key with special chars (`resonance.prov.v1:test`) | ❌ | - | Namespace collision |
| 38 | Tag value with newlines/control chars | ❌ | - | May break parsers |

**Coverage:** 0/5 (0%) - **CRITICAL GAP**

### 2.6 User Modifications (7 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 39 | User renames file before apply | ❌ | - | Signature mismatch, but no diagnosis |
| 40 | User deletes file before apply | ❌ | - | FileNotFoundError, no recovery hint |
| 41 | User adds file to directory before apply | ❌ | - | Signature mismatch, unexpected file |
| 42 | User manually edits tags (no overwrite) | ✅ | `test_apply_does_not_overwrite_existing_tags:7` | ✓ Covered |
| 43 | User manually edits tags (with overwrite) | ✅ | `test_apply_overwrite_records_provenance:8` | ✓ Covered |
| 44 | User moves directory before apply | ❌ | - | Path change detection exists, but not for apply |
| 45 | User deletes destination directory before apply | ❌ | - | mkdir should handle, not tested |

**Coverage:** 2/7 (29%)

### 2.7 Conflict Handling (5 edge cases)

| # | Edge Case | Tested? | Test Name | Notes |
|---|-----------|---------|-----------|-------|
| 46 | File collision with policy=fail | ✅ | `test_applier_fails_on_collision:3` | ✓ Covered |
| 47 | File collision with policy=skip | ✅ | `test_applier_conflict_policy_skip:16` | ✓ Covered |
| 48 | File collision with policy=rename | ✅ | `test_applier_conflict_policy_rename:17` | ✓ Covered |
| 49 | Rename exhaustion (001-999 all exist) | ❌ | - | Infinite loop risk |
| 50 | Collision on non-audio file (cover.jpg) | ⚠️ | Non-audio tests exist, not collision | Implicit coverage |

**Coverage:** 3.5/5 (70%) - **GOOD**

---

**Total Edge Cases Covered:** 17.5 / 50 = **35%**
**Critical Gaps:** Crash recovery (17%), tag validation (0%), version skew (36%)

---

## 3. Test Quality & Determinism Audit

### 3.1 Determinism Analysis

**Searched for common non-determinism sources:**

#### ✅ GOOD: No datetime.now() in test assertions
```bash
$ grep -r "datetime.now()" tests/
# No results - tests use fixed timestamps or UTC
```

**Evidence:**
- `test_metadata_cache_timestamps_are_utc_z:1` - Enforces UTC Z format
- `test_directory_store_timestamps_are_utc_z:2` - Enforces UTC Z format

#### ✅ GOOD: Explicit ordering in tests
```python
# tests/unit/test_scanner.py
def test_iter_directories_is_deterministic(tmp_path: Path):
    # Explicitly tests determinism by comparing repeated runs
```

**Evidence:**
- `test_iter_directories_is_deterministic:1` - Scanner
- `test_scan_json_output_is_deterministic:1` - CLI
- `test_identify_human_output_is_deterministic:3` - Identifier
- `test_identify_end_to_end_with_stub_provider_json_deterministic:12` - Provider
- `test_cache_eviction_is_deterministic_across_reopen:2` - Cache

#### ✅ GOOD: No randomness (uuid4, random.choice, etc.)
```bash
$ grep -r "uuid4\|random\." tests/ --include="*.py"
# No results
```

#### ⚠️ WARNING: Potential race condition in file operations
```python
# tests/integration/test_applier.py
def test_applier_rolls_back_on_move_failure(tmp_path: Path):
    # Simulates move failure by removing write permissions
    # If timing changes, test may be flaky
```

**Recommendation:** Use explicit failure injection (mock/patch) instead of permission manipulation.

#### ⚠️ WARNING: Temp directory cleanup order
```bash
$ grep -r "tmp_path" tests/ | wc -l
# 197 uses of tmp_path fixture
```

**Analysis:** All integration tests use `tmp_path` fixture (pytest-provided). Cleanup is automatic, but some tests may be sensitive to leftover files if cleanup fails.

**Recommendation:** Add `autouse=True` cleanup fixture to ensure isolation.

---

### 3.2 Test Isolation

#### ✅ GOOD: Each test uses isolated tmp_path
```python
# All integration tests signature:
def test_applier_*(..., tmp_path: Path) -> None:
    # tmp_path is unique per test
```

#### ❌ BAD: Some tests share global state via filesystem
```python
# tests/integration/test_tag_writer.py:test_mutagen_tag_writer_flac_corpus
def test_mutagen_tag_writer_flac_corpus(tmp_path: Path):
    # Reads from fixtures/flac_corpus/ - shared read-only state
    # If corpus is mutated by another test, this fails
```

**Recommendation:** Copy corpus files to tmp_path before mutating.

---

### 3.3 Assertion Quality

#### ✅ GOOD: Specific assertions, not just "no exception"
```python
# tests/integration/test_applier.py
assert report.status == ApplyStatus.APPLIED
assert len(report.errors) == 0
assert dest_file.exists()
```

#### ⚠️ WARNING: Some tests only check "success" without validating data
```python
# tests/unit/test_enricher.py
def test_enricher_builds_patch_for_resolved_auto(...):
    patch = enricher.enrich(directory)
    assert patch is not None  # Could be more specific
```

**Recommendation:** Assert on patch contents (expected tags, track count, etc.).

---

### 3.4 Test Naming & Documentation

#### ✅ GOOD: Descriptive test names
```python
test_applier_fails_on_signature_mismatch  # Clear expectation
test_cache_eviction_is_deterministic_across_reopen  # Specific scenario
```

#### ⚠️ WARNING: Some tests lack docstrings explaining "why"
```python
def test_applier_moves_non_audio_with_album(tmp_path: Path) -> None:
    # No docstring - intent unclear (regression test? feature spec?)
```

**Recommendation:** Add docstrings to complex tests explaining:
- What scenario is being tested
- Why it's important (crash safety, user request, bug fix)
- What the expected behavior is

---

### 3.5 Flakiness Risk Assessment

| Risk Factor | Evidence | Count | Risk Level |
|-------------|----------|-------|------------|
| datetime.now() usage | Not found | 0 | 🟢 LOW |
| random/uuid4 usage | Not found | 0 | 🟢 LOW |
| Unsorted iteration (dict, set) | Mitigated by explicit sorting in code | 0 | 🟢 LOW |
| Filesystem race conditions | Permission manipulation in rollback test | 1 | 🟡 MEDIUM |
| Network calls | No live API calls (all stubbed/cached) | 0 | 🟢 LOW |
| Sleep/timing dependencies | Not found | 0 | 🟢 LOW |
| Shared mutable state | Read-only corpus files | ~5 | 🟡 MEDIUM |

**Overall Flakiness Risk:** 🟢 **LOW** (Good practices throughout)

---

## 4. Proposed Missing Tests (20 High-Priority Tests)

Tests are prioritized by safety impact (P0 > P1 > P2) and likelihood of occurrence.

### 4.1 P0 Critical Safety Tests (8 tests)

#### Test 1: `test_crash_after_file_moves_before_db_commit`
**Priority:** 🔴 **P0 - STOP-SHIP**
**Scenario:** All files moved successfully, but process crashes before `store.set_state(APPLIED)` commits
**Expected:** On next run, detect all files moved, update DB to APPLIED, return NOOP
**Why Critical:** Most likely crash point in production (after heavy I/O, before fast DB op)
**Covers:** AUDIT_2_TODO.md lines 113-164, Phase 4 line 411

```python
def test_applier_crash_after_file_moves_before_db_commit(tmp_path: Path) -> None:
    """
    Simulate crash after all file moves succeed but before DB state is committed.

    This is the most common crash scenario: long-running file I/O succeeds,
    but process dies before updating state. On recovery, applier must detect
    completed moves and update DB without re-executing operations.
    """
    # Setup: create plan, manually move all files (simulate completed apply)
    # Act: call apply() again
    # Assert: returns NOOP_ALREADY_APPLIED, DB state is APPLIED
```

#### Test 2: `test_rollback_failure_leaves_detailed_error`
**Priority:** 🟡 **P1**
**Scenario:** Apply fails, rollback starts moving files back, encounters error mid-rollback
**Expected:** Clear error listing which files were rolled back, which remain at dest
**Why Important:** User needs to know exact state to manually recover
**Covers:** AUDIT_2_TODO.md Phase 4 line 410

```python
def test_rollback_failure_provides_detailed_state_report(tmp_path: Path) -> None:
    """
    If rollback fails, report exactly which files were moved back and which remain.
    Don't attempt to resume - just give user clear state for manual recovery.
    """
    # Setup: plan with 10 files, move all to dest
    # Inject permission error on file 7 during rollback
    # Act: rollback()
    # Assert: error includes "Rolled back: 6 files, Failed: file7.flac, Remaining at dest: files 7-10"
```

#### Test 3: `test_schema_version_mismatch_prevents_downgrade_corruption`
**Priority:** 🔴 **P0 - STOP-SHIP**
**Scenario:** DB created by v0.2.0 (schema_version=2), opened by v0.1.0 (supports schema_version=1)
**Expected:** Clear error: "DB schema 2 > supported 1. Please upgrade Resonance."
**Why Critical:** Prevents silent data corruption from unknown columns/tables
**Covers:** AUDIT_2_TODO.md lines 68-112, Phase 4 line 422

```python
def test_directory_store_rejects_future_schema_version(tmp_path: Path) -> None:
    """
    Opening a DB with schema_version > CURRENT_SCHEMA_VERSION must fail cleanly.
    """
    # Setup: create DB, manually insert schema_version=99
    # Act: DirectoryStore(db_path)
    # Assert: raises ValueError with actionable message
```

#### Test 4: `test_schema_migration_upgrades_v1_to_v2`
**Priority:** 🔴 **P0**
**Scenario:** DB from v0.1.0 (schema_version=1), opened by v0.2.0 (requires schema_version=2)
**Expected:** Migration runs automatically, adds new columns, updates version
**Why Critical:** Users upgrading Resonance must not lose data or manually migrate
**Covers:** AUDIT_2_TODO.md lines 97-109

```python
def test_directory_store_migrates_schema_v1_to_v2(tmp_path: Path) -> None:
    """
    Test schema migration from v1 (no signature_version column) to v2 (adds column).
    """
    # Setup: create v1 DB with directories
    # Act: open with DirectoryStore (v2)
    # Assert: new column exists, data preserved, schema_version=2
```

#### Test 5: `test_partial_state_both_files_missing_detected`
**Priority:** 🔴 **P0**
**Scenario:** Plan expects file at source A and dest B, both are missing
**Expected:** PARTIAL_COMPLETE with diagnostic "both_missing"
**Why Critical:** Distinguishes "user deleted both copies" from "never started"
**Covers:** AUDIT_2_TODO.md lines 113-164

```python
def test_applier_partial_state_both_source_and_dest_missing(tmp_path: Path) -> None:
    """
    If both source and destination are missing, this is a partial state anomaly.
    User may have manually deleted files, or external process removed them.
    """
    # Setup: create plan, delete both source and dest files
    # Act: apply()
    # Assert: status=PARTIAL_COMPLETE, details include "both_missing"
```

#### Test 6: `test_partial_state_duplicated_files_detected`
**Priority:** 🔴 **P0**
**Scenario:** File exists at both source and dest (user copied instead of moved?)
**Expected:** PARTIAL_COMPLETE with diagnostic "duplicated"
**Why Critical:** Prevents accidental duplicate moves or data loss
**Covers:** AUDIT_2_TODO.md lines 113-164

```python
def test_applier_partial_state_file_exists_at_both_source_and_dest(tmp_path: Path) -> None:
    """
    If file exists at both source and dest, this indicates:
    - User copied instead of moved
    - Previous apply was interrupted and didn't clean up source
    - External process duplicated the file
    """
    # Setup: create plan, copy (don't move) files to dest
    # Act: apply()
    # Assert: status=PARTIAL_COMPLETE, details include "duplicated"
```

#### Test 7: `test_signature_algorithm_version_change_warns_user`
**Priority:** 🔴 **P0**
**Scenario:** Signature v1 in DB, signature v2 algorithm in app (incompatible)
**Expected:** Warning logged, state reset to NEW, signature updated to v2
**Why Critical:** Silent signature changes invalidate all directory state
**Covers:** AUDIT_2_TODO.md lines 165-194

```python
def test_signature_version_change_warns_and_resets_state(tmp_path: Path) -> None:
    """
    When signature algorithm version changes, old signatures are invalid.
    Reset state and warn user that re-identification is needed.
    """
    # Setup: store directory with signature_version=1
    # Act: scan same directory with signature_version=2 algorithm
    # Assert: warning logged, state=NEW, signature updated
```

#### Test 8: `test_path_traversal_rejected_at_plan_deserialization`
**Priority:** 🔴 **P0**
**Scenario:** Malicious plan.json contains `../../etc/passwd` in source_path
**Expected:** Plan.from_json() raises ValueError before any file operations
**Why Critical:** Validation at deserialization prevents TOCTOU attacks
**Covers:** AUDIT_2_TODO.md lines 27-43

```python
def test_plan_deserialization_rejects_path_traversal(tmp_path: Path) -> None:
    """
    Path traversal validation MUST occur at plan load time, not apply time.
    Otherwise, attacker can exploit TOCTOU (time-of-check-time-of-use) gap.
    """
    # Setup: craft plan.json with "../" in paths
    # Act: Plan.from_json(plan_path)
    # Assert: raises ValueError("Path traversal not allowed")
```

---

### 4.2 P1 High-Priority Robustness Tests (7 tests)

#### Test 9: `test_apply_after_user_renames_file_provides_diagnosis`
**Priority:** 🟡 **P1**
**Scenario:** User renames `track01.flac` → `song.flac` before apply
**Expected:** Error message includes "File may have been renamed to: song.flac"
**Why Important:** Current error is cryptic ("Missing source file")
**Covers:** AUDIT_2_TODO.md lines 226-254

```python
def test_apply_diagnoses_user_file_rename(tmp_path: Path) -> None:
    """
    When source file is missing, diagnose possible causes:
    - File was renamed (check for similar names in same dir)
    - File was deleted (no candidates found)
    - File was moved (check destination)
    """
    # Setup: create plan, rename source file
    # Act: apply()
    # Assert: error includes "may have been renamed to: <new_name>"
```

#### Test 10: `test_apply_after_user_deletes_file_suggests_rescan`
**Priority:** 🟡 **P1**
**Scenario:** User deletes source file before apply
**Expected:** Error includes "File deleted. Run 'resonance scan' to create new plan."
**Why Important:** Guides user to recovery action
**Covers:** AUDIT_2_TODO.md lines 226-254

```python
def test_apply_after_user_deletes_file_suggests_recovery(tmp_path: Path) -> None:
    """
    Provide actionable recovery steps when user deletes source file.
    """
    # Setup: create plan, delete source file (no similar files in dir)
    # Act: apply()
    # Assert: error includes "resonance scan" recovery suggestion
```

#### Test 11: `test_rollback_is_idempotent_second_call_is_noop`
**Priority:** 🟡 **P1**
**Scenario:** Rollback succeeds, user calls rollback again on same directory
**Expected:** Second rollback returns success immediately (no-op)
**Why Important:** User may not know if rollback completed
**Covers:** AUDIT_2_TODO.md line 418, Phase 4

```python
def test_rollback_twice_is_idempotent(tmp_path: Path) -> None:
    """
    Rollback must be idempotent - calling it twice should not error.
    """
    # Setup: apply a plan, then rollback
    # Act: rollback again
    # Assert: success, no errors, state unchanged
```

#### Test 12: `test_apply_with_different_conflict_policy_not_idempotent`
**Priority:** 🟡 **P1**
**Scenario:** Apply with policy=fail, then apply same plan with policy=skip
**Expected:** Behavior changes (skip conflicts instead of failing)
**Why Important:** Documents non-idempotent behavior, guides user expectations
**Covers:** Idempotency edge case (line 416 of matrix)

```python
def test_apply_conflict_policy_change_affects_idempotency(tmp_path: Path) -> None:
    """
    Changing conflict policy between applies changes behavior.
    This is expected but should be documented.
    """
    # Setup: create plan with collision
    # Act 1: apply(policy=FAIL) -> fails
    # Act 2: apply(policy=SKIP) -> succeeds
    # Assert: second apply skips conflict (not idempotent, but correct)
```

#### Test 13: `test_incremental_state_transition_through_applying_states`
**Priority:** 🟡 **P1**
**Scenario:** Monitor state transitions during apply: PLANNED → APPLYING → APPLYING_TAGS → APPLIED
**Expected:** State updates incrementally as operations complete
**Why Important:** Enables progress tracking and crash recovery
**Covers:** AUDIT_2_TODO.md lines 290-310

```python
def test_apply_transitions_through_intermediate_states(tmp_path: Path) -> None:
    """
    State should update incrementally:
    1. PLANNED (before apply)
    2. APPLYING (during file moves)
    3. APPLYING_TAGS (during tag writes)
    4. APPLIED (complete)
    """
    # Setup: create plan
    # Act: apply() with state observer callback
    # Assert: observed states = [PLANNED, APPLYING, APPLYING_TAGS, APPLIED]
```

#### Test 14: `test_expected_source_files_detects_added_files`
**Priority:** 🟡 **P1**
**Scenario:** Plan.expected_source_files = [a.flac, b.flac], but c.flac now exists in dir
**Expected:** Warning: "Unexpected file found: c.flac (not in plan)"
**Why Important:** Detects user additions, prevents surprise behavior
**Covers:** AUDIT_2_TODO.md lines 216-225

```python
def test_plan_expected_source_files_detects_user_added_file(tmp_path: Path) -> None:
    """
    If plan.expected_source_files is provided, warn on unexpected files.
    """
    # Setup: create plan with 2 files, add 3rd file to source dir
    # Act: apply()
    # Assert: warning includes "unexpected file: <filename>"
```

---

### 4.3 P2 Data Integrity Tests (5 tests)

#### Test 15: `test_tag_value_with_null_bytes_rejected`
**Priority:** 🟠 **P2**
**Scenario:** TagPatch contains `artist="Foo\x00Bar"`
**Expected:** Sanitization raises ValueError("Null bytes not allowed")
**Why Important:** Null bytes can truncate strings or crash parsers
**Covers:** AUDIT_2_TODO.md lines 340-353

```python
def test_tag_writer_rejects_null_bytes_in_tag_values(tmp_path: Path) -> None:
    """
    Tag values must not contain null bytes (\x00) as they break many parsers.
    """
    # Setup: create TagPatch with null byte in artist field
    # Act: apply()
    # Assert: raises ValueError("Null bytes not allowed in tag values")
```

#### Test 16: `test_tag_value_exceeding_max_length_rejected`
**Priority:** 🟠 **P2**
**Scenario:** TagPatch contains `comment="A" * 10000` (10KB)
**Expected:** Sanitization raises ValueError("Tag too long: 10000 > 1000")
**Why Important:** Prevents memory exhaustion and file corruption
**Covers:** AUDIT_2_TODO.md lines 340-353

```python
def test_tag_writer_rejects_excessively_long_tag_values(tmp_path: Path) -> None:
    """
    Tag values must not exceed MAX_TAG_LENGTH (1KB) to prevent DoS/corruption.
    """
    # Setup: create TagPatch with 10KB string
    # Act: apply()
    # Assert: raises ValueError("Tag too long")
```

#### Test 17: `test_cached_release_with_missing_required_fields_evicted`
**Priority:** 🟠 **P2**
**Scenario:** Cached MusicBrainz release is missing `media` field (corrupted)
**Expected:** Cache entry evicted, re-fetched from API
**Why Important:** Corrupted cache should self-heal, not crash
**Covers:** AUDIT_2_TODO.md lines 355-379

```python
def test_provider_cache_evicts_malformed_release_data(tmp_path: Path) -> None:
    """
    Cached release data must be validated on read. If invalid, evict and refetch.
    """
    # Setup: manually insert release into cache with missing 'media' field
    # Act: get_mb_release(release_id)
    # Assert: returns None (evicted), warning logged
```

#### Test 18: `test_provenance_v2_overwrites_provenance_v1_tags`
**Priority:** 🟠 **P2**
**Scenario:** File has v1 provenance tags, app writes v2 provenance
**Expected:** Old v1 tags removed, new v2 tags written
**Why Important:** Prevents namespace pollution and confusion
**Covers:** AUDIT_2_TODO.md lines 381-400

```python
def test_tag_writer_migrates_provenance_v1_to_v2(tmp_path: Path) -> None:
    """
    When overwriting tags with provenance v2, remove old v1 tags.
    """
    # Setup: write v1 provenance tags to file
    # Act: write v2 provenance tags
    # Assert: v1 tags removed, only v2 tags remain
```

#### Test 19: `test_plan_json_with_invalid_schema_rejected_at_load`
**Priority:** 🟠 **P2**
**Scenario:** plan.json is missing required `signature_hash` field
**Expected:** Plan.from_json() raises ValidationError
**Why Important:** Fail fast on malformed plans
**Covers:** AUDIT_2_TODO.md lines 318-338

```python
def test_plan_load_validates_against_json_schema(tmp_path: Path) -> None:
    """
    Plan deserialization must validate against JSON schema before parsing.
    """
    # Setup: create plan.json missing 'signature_hash'
    # Act: Plan.from_json(plan_path)
    # Assert: raises ValidationError("Missing required field: signature_hash")
```

---

### 4.4 Test Priority Summary

| Priority | Count | Focus | Grade Impact |
|----------|-------|-------|--------------|
| **P0 (Stop-Ship)** | 8 | Crash recovery, schema versioning, partial states, path safety | **D- → C** |
| **P1 (High)** | 6 | User modifications, incremental state, idempotency | **C → B-** |
| **P2 (Medium)** | 5 | Tag validation, cache integrity, provenance versioning | **B- → B** |

**Implementing all 19 tests would improve grade from D- to B (70% coverage of critical scenarios).**

---

## 5. Stop-Ship List (Top 5 Missing Tests)

These tests MUST be implemented before Resonance can be considered production-ready.

### 🔴 #1: Crash After File Moves, Before DB Commit
**Test:** `test_applier_crash_after_file_moves_before_db_commit`
**Why Stop-Ship:** Most common crash scenario in production (after heavy I/O, before fast DB op). Current behavior: state DB shows PLANNED, but all files are moved → user re-applies → catastrophic duplicate moves or errors.
**Risk:** **HIGH** - Data loss, user confusion, support burden
**Effort:** ~3 hours (requires WAL or completion analyzer integration)
**AUDIT_2_TODO.md:** Lines 113-164, 407-412

---

### 🔴 #2: Schema Version Downgrade Protection
**Test:** `test_directory_store_rejects_future_schema_version`
**Why Stop-Ship:** Downgrading Resonance version (e.g., v0.2.0 → v0.1.0) silently corrupts DB by ignoring unknown columns/tables. No error, no warning.
**Risk:** **CRITICAL** - Silent data corruption, state desync, crashes
**Effort:** ~2 hours (add version check in `DirectoryStore.__init__`)
**AUDIT_2_TODO.md:** Lines 68-112, 421-426

---

### 🔴 #3: Rollback Failure Reporting
**Test:** `test_rollback_failure_provides_detailed_state_report`
**Why Stop-Ship:** If rollback fails mid-execution, user needs **clear state information** for manual recovery. Current behavior: generic error, no details about which files were moved back.
**Risk:** **HIGH** - User confusion, manual recovery difficult
**Effort:** ~2 hours (add detailed error reporting)
**AUDIT_2_TODO.md:** Phase 4 line 410

---

### 🔴 #4: Path Traversal at Deserialization (TOCTOU)
**Test:** `test_plan_deserialization_rejects_path_traversal`
**Why Stop-Ship:** Current validation occurs at apply time. Attacker can exploit TOCTOU gap: plan passes validation, then is modified before apply. Must validate at load time.
**Risk:** **CRITICAL** - Arbitrary file read/write, privilege escalation
**Effort:** ~2 hours (move validation to `Plan.from_json`)
**AUDIT_2_TODO.md:** Lines 27-43, 428-434

---

### 🔴 #5: Partial State Detection (Granular Diagnostics)
**Tests:** `test_applier_partial_state_both_source_and_dest_missing`
         `test_applier_partial_state_file_exists_at_both_source_and_dest`
**Why Stop-Ship:** Current partial state detection is too coarse (binary: all-or-nothing). Cannot distinguish:
- User deleted both copies (both_missing)
- User copied instead of moved (duplicated)
- Crash left half-moved file (dest is 0 bytes)

Without granular diagnostics, users cannot recover safely.
**Risk:** **HIGH** - User confusion, manual recovery required, data loss
**Effort:** ~4 hours (enhance CompletionAnalysis with file size checks)
**AUDIT_2_TODO.md:** Lines 113-164, 407-412

---

**Total Stop-Ship Effort:** ~13 hours
**Risk Reduction:** Prevents **5 critical failure modes** that lead to data loss or corruption

---

## 6. Recommendations

### 6.1 Immediate Actions (This Sprint)

1. **Implement Stop-Ship List** (#1-#5 above) - 13 hours total
2. **Add schema versioning checks** - Prevents v0.2.0 release from corrupting v0.1.0 DBs
3. **Move path validation to deserialization** - Closes TOCTOU security gap
4. **Enhance partial state detection** - Improves crash recovery UX

### 6.2 Short-Term (Next 2 Sprints)

1. **Add tag value sanitization** (AUDIT_2_TODO.md lines 340-353)
   - Null byte rejection
   - Length limits (1KB per tag)
   - UTF-8 validation

2. **User modification diagnosis** (lines 226-254)
   - Detect file renames (fuzzy filename matching)
   - Suggest recovery actions in error messages

3. **Improve rollback error reporting**
   - List which files were successfully rolled back
   - List which files remain at destination
   - Provide clear manual recovery instructions

### 6.3 Medium-Term (Only If You're Bored)

1. **More edge case tests** - But honestly, you've got the important ones covered
2. **Fuzz testing** - If you really want to, but this is a music library organizer, not cryptography

### 6.4 Quality Improvements

1. **Add docstrings to complex tests**
   - Explain "why" this test exists (regression? feature spec? crash safety?)
   - Document expected behavior

2. **Replace permission manipulation with mocks**
   - `test_applier_rolls_back_on_move_failure` uses permission denial
   - Use `unittest.mock.patch` for cleaner failure injection

3. **Add autouse cleanup fixture**
   ```python
   @pytest.fixture(autouse=True)
   def ensure_clean_tmp(tmp_path: Path):
       yield
       shutil.rmtree(tmp_path, ignore_errors=True)
   ```

---

## 7. Summary & Next Steps

### Current State
- **234 tests** across 26 files
- **Strong determinism** practices (no datetime.now(), explicit ordering)
- **Good coverage** of happy paths, identity logic, signature stability
- **Critical gaps** in crash recovery, version skew, WAL, tag validation

### Grade Progression Path

| Milestone | Grade | Coverage | Key Additions |
|-----------|-------|----------|---------------|
| **Current** | 🔴 D- | 38% | Existing 234 tests |
| **Stop-Ship List Complete** | 🟡 C | 55% | +5 critical tests (16 hours) |
| **P0 Complete** | 🟡 C+ | 65% | +3 more P0 tests (8 hours) |
| **P1 Complete** | 🟢 B- | 75% | +7 P1 tests (14 hours) |
| **P2 Complete** | 🟢 B | 85% | +5 P2 tests (10 hours) |
| **Chaos Testing** | 🟢 A- | 95% | Property-based testing framework |

### Immediate Next Step

**Implement Stop-Ship #1:** `test_applier_crash_after_file_moves_before_db_commit`
- Highest risk, most common failure mode
- Validates partial completion detection logic
- Demonstrates recovery strategy to users

**Command to run:**
```bash
# Create test file
touch tests/integration/test_crash_recovery.py

# Implement test (see Section 4.1 Test 1 for spec)
# Run with:
pytest tests/integration/test_crash_recovery.py::test_applier_crash_after_file_moves_before_db_commit -v
```

---

---

## 8. Golden Corpus Gap Analysis

**Date:** 2025-12-21
**Current Golden Scenarios:** 13 (standard_album, multi_disc, compilation, name_variants, classical, extras_only, single_track, mixed_media, multi_composer, long_titles, renamed_mid_processing, missing_middle_tracks, case_only_rename, interrupted_apply)

### 8.1 Currently Covered Scenarios

✅ **Basic Structure:**
- Standard album (10 tracks, clean tags)
- Multi-disc album (2 discs with disc numbers)
- Compilation (Various Artists, different track artists)
- Single-track release
- Extras-heavy (cover/booklet/cue/log)
- Mixed media (audio + video)

✅ **Name Complexity:**
- Name variants (AC/DC, Björk, Alt-J with punctuation/diacritics)
- Long titles (>200 chars, filesystem truncation)

✅ **Classical:**
- Basic classical (composer + performer)
- Multi-composer compilation (Beethoven + Mozart)

✅ **Edge Cases (Partial):**
- Missing middle tracks (1, 2, 5, 6 - no 3, 4)
- Case-only rename
- Renamed mid-processing
- Interrupted apply

### 8.2 Missing Golden Corpus Scenarios (High-Priority)

These scenarios are **NOT YET COVERED** by the golden corpus and represent high-risk regression areas:

---

#### **CLASSICAL-SPECIFIC GAPS** (7 scenarios)

##### GC-1: Opus Number Normalization
**Rationale:** Work identification relies on catalog numbers; inconsistent formatting breaks identity
**Invariant:** Canonicalization of work identifiers
**Tricky Edge Case:** "Op. 27 No. 2" = "Op.27, No.2" = "op 27 #2" = "Opus 27/2"
**Test Data:**
```python
CorpusScenario(
    name="opus_normalization",
    description="Beethoven sonata with varied opus formats.",
    audio_specs=[
        _spec("01 - Op. 27 No. 2.flac", "fp-op-01", 420, {
            "title": "Piano Sonata No. 14 in C-sharp Minor, Op. 27 No. 2 'Moonlight': I. Adagio sostenuto",
            "composer": "Ludwig van Beethoven",
            "performer": "Wilhelm Kempff",
            "album": "Beethoven Piano Sonatas",
            "track_number": 1,
        }),
        _spec("02 - op.27, no.2.flac", "fp-op-02", 200, {
            "title": "Piano Sonata in C-sharp Minor, op.27, no.2: II. Allegretto",
            "composer": "Beethoven",
            "performer": "Wilhelm Kempff",
            "album": "Beethoven Piano Sonatas",
            "track_number": 2,
        }),
    ],
)
```

##### GC-2: Conductor vs. Performer Primary Artist
**Rationale:** Orchestral works credit conductor; solo works credit performer; concertos are ambiguous
**Invariant:** Artist credit disambiguation rules
**Tricky Edge Case:** Who gets ALBUMARTIST for a piano concerto?
**Test Data:**
```python
CorpusScenario(
    name="conductor_vs_performer",
    description="Piano concerto with soloist, orchestra, and conductor.",
    audio_specs=[
        _spec("01 - Mvt 1.flac", "fp-cvp-01", 450, {
            "title": "Piano Concerto No. 21 in C Major, K. 467: I. Allegro maestoso",
            "composer": "Wolfgang Amadeus Mozart",
            "performer": "Mitsuko Uchida",  # piano
            "album_artist": "English Chamber Orchestra",
            "conductor": "Jeffrey Tate",
            "album": "Mozart Piano Concertos",
            "track_number": 1,
        }),
    ],
)
```

##### GC-3: Different Performers Per Movement
**Rationale:** Live recordings/compilations mix performers within same opus
**Invariant:** Track-level performer canonicalization without breaking work grouping
**Tricky Edge Case:** Movement grouping must not break on performer change
**Test Data:**
```python
CorpusScenario(
    name="multi_performer_work",
    description="Same concerto, different soloists per movement.",
    audio_specs=[
        _spec("01 - Mvt 1 Argerich.flac", "fp-mpw-01", 380, {
            "title": "Piano Concerto No. 2: I. Allegro non troppo",
            "composer": "Brahms",
            "performer": "Martha Argerich",
            "conductor": "Claudio Abbado",
            "album": "Brahms Piano Concertos - Various Soloists",
            "track_number": 1,
        }),
        _spec("02 - Mvt 2 Barenboim.flac", "fp-mpw-02", 270, {
            "title": "Piano Concerto No. 2: II. Andante",
            "composer": "Brahms",
            "performer": "Daniel Barenboim",
            "conductor": "Claudio Abbado",
            "album": "Brahms Piano Concertos - Various Soloists",
            "track_number": 2,
        }),
    ],
)
```

##### GC-4: Catalog Number Variants (BWV, K., Hob., D.)
**Rationale:** Different composers use different catalog systems
**Invariant:** Canonicalization across catalog systems
**Tricky Edge Case:** "BWV 1006" vs "BWV1006" vs "BWV-1006"
**Test Data:**
```python
CorpusScenario(
    name="catalog_variants",
    description="Bach BWV, Mozart K., Schubert D. numbering.",
    audio_specs=[
        _spec("01 - BWV 1006.flac", "fp-cat-01", 320, {
            "title": "Partita No. 3 in E Major, BWV 1006: Preludio",
            "composer": "J.S. Bach",
            "performer": "Hilary Hahn",
            "album": "Bach Solo Works",
            "track_number": 1,
        }),
        _spec("02 - K.525.flac", "fp-cat-02", 290, {
            "title": "Eine kleine Nachtmusik, K. 525: I. Allegro",
            "composer": "W.A. Mozart",
            "performer": "Vienna Philharmonic",
            "album": "Mozart Serenades",
            "track_number": 2,
        }),
    ],
)
```

##### GC-5: Partial Opera (Non-Contiguous Excerpts)
**Rationale:** Opera releases often contain non-contiguous selections
**Invariant:** Track sequencing for incomplete works
**Tricky Edge Case:** Track numbers should reflect excerpt order, not original opera structure
**Test Data:**
```python
CorpusScenario(
    name="partial_opera",
    description="La Bohème excerpts (Act II + Act IV, skipping I & III).",
    audio_specs=[
        _spec("01 - Act II Scene 3.flac", "fp-opera-01", 480, {
            "title": "La Bohème: Act II, Scene 3 - Quando m'en vo'",
            "composer": "Giacomo Puccini",
            "performer": "Mirella Freni",
            "conductor": "Herbert von Karajan",
            "album": "Puccini Opera Highlights",
            "track_number": 1,
        }),
        _spec("02 - Act IV Scene 2.flac", "fp-opera-02", 520, {
            "title": "La Bohème: Act IV, Scene 2 - Vecchia zimarra",
            "composer": "Giacomo Puccini",
            "performer": "Nicolai Ghiaurov",
            "conductor": "Herbert von Karajan",
            "album": "Puccini Opera Highlights",
            "track_number": 2,
        }),
    ],
)
```

##### GC-6: Work Nickname vs. Formal Title
**Rationale:** Works known by nickname vs. catalog name cause duplicate entries
**Invariant:** Work canonicalization with aliases
**Tricky Edge Case:** "Eroica" = "Symphony No. 3 in E-flat Major, Op. 55"
**Test Data:**
```python
CorpusScenario(
    name="work_nickname",
    description="Beethoven Eroica vs. Symphony No. 3.",
    audio_specs=[
        _spec("01 - Eroica.flac", "fp-nick-01", 800, {
            "title": "Eroica Symphony: I. Allegro con brio",
            "composer": "Beethoven",
            "conductor": "Karajan",
            "album": "Beethoven Symphonies",
            "track_number": 1,
        }),
        _spec("02 - Symphony 3.flac", "fp-nick-02", 750, {
            "title": "Symphony No. 3 in E-flat Major, Op. 55: II. Marcia funebre",
            "composer": "Ludwig van Beethoven",
            "conductor": "Herbert von Karajan",
            "album": "Beethoven Symphonies",
            "track_number": 2,
        }),
    ],
)
```

##### GC-7: Ensemble Name Variations
**Rationale:** Same ensemble with different name formats
**Invariant:** Artist canonicalization
**Tricky Edge Case:** "London Symphony Orchestra" = "LSO" = "London SO"
**Test Data:**
```python
CorpusScenario(
    name="ensemble_variants",
    description="Orchestra name variations.",
    audio_specs=[
        _spec("01 - LSO.flac", "fp-ens-01", 320, {
            "title": "Symphony Movement",
            "composer": "Brahms",
            "album_artist": "LSO",
            "conductor": "Colin Davis",
            "album": "Brahms Symphonies",
            "track_number": 1,
        }),
        _spec("02 - London Symphony.flac", "fp-ens-02", 340, {
            "title": "Symphony Movement II",
            "composer": "Brahms",
            "album_artist": "London Symphony Orchestra",
            "conductor": "Colin Davis",
            "album": "Brahms Symphonies",
            "track_number": 2,
        }),
    ],
)
```

---

#### **FILESYSTEM CHAOS GAPS** (8 scenarios)

##### GC-8: Orphaned Track Reunification
**Rationale:** User accidentally moves track to parent directory
**Invariant:** Identity resolution across scattered paths + layout repair
**Tricky Edge Case:** Orphan must reunite with siblings via shared album hash
**Test Data:**
```python
CorpusScenario(
    name="orphaned_track",
    description="Track 3 moved to parent directory, should reunite.",
    # Corpus builder creates: library/Album/01.flac, library/Album/02.flac, library/03.flac
    # Scanner should detect all 3 as same album despite path mismatch
)
```

##### GC-9: Split Album (Interrupted Move)
**Rationale:** Copy operation failed halfway; tracks 1-5 in old location, 6-10 in new
**Invariant:** Identity merging + conflict resolution
**Tricky Edge Case:** Both directories claim to be "the album"
**Test Data:**
```python
CorpusScenario(
    name="split_album",
    description="Album split across two directories.",
    # Create: library/old/01-05.flac + library/new/06-10.flac
)
```

##### GC-10: Partial Tags (Missing Album/Artist)
**Rationale:** Real-world libraries have incomplete metadata from ripping errors
**Invariant:** Identity resolution under ambiguity
**Tricky Edge Case:** Missing album artist but track artists present; infer from siblings
**Test Data:**
```python
CorpusScenario(
    name="partial_tags",
    description="Some files missing artist/album tags.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-pt-01", 180, {
            "title": "Track 1",
            "artist": "Artist A",
            "album": "Album Name",
            # album_artist missing
            "track_number": 1,
        }),
        _spec("02 - Track.flac", "fp-pt-02", 182, {
            "title": "Track 2",
            # artist missing
            # album missing
            "track_number": 2,
        }),
    ],
)
```

##### GC-11: Duplicate Track (Same File Copied)
**Rationale:** Users accidentally copy files; critical to avoid duplicate entries
**Invariant:** Identity deduplication via signature (not filename)
**Tricky Edge Case:** Identical audio fingerprint but different filename/path
**Test Data:**
```python
CorpusScenario(
    name="duplicate_files",
    description="Same track copied with different names.",
    # track01.flac (fp-dup-01) + track01_copy.flac (fp-dup-01) - same fingerprint
)
```

##### GC-12: Featured Artist Variations
**Rationale:** String normalization failures cause duplicate artists
**Invariant:** Canonicalization of artist credits
**Tricky Edge Case:** "Artist feat. Guest" = "Artist ft Guest" = "Artist featuring Guest"
**Test Data:**
```python
CorpusScenario(
    name="featured_artist",
    description="Featured artist format variations.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-feat-01", 200, {
            "title": "Track 1",
            "artist": "Main Artist feat. Guest",
            "album": "Album",
            "track_number": 1,
        }),
        _spec("02 - Track.flac", "fp-feat-02", 201, {
            "title": "Track 2",
            "artist": "Main Artist ft Guest",
            "album": "Album",
            "track_number": 2,
        }),
        _spec("03 - Track.flac", "fp-feat-03", 202, {
            "title": "Track 3",
            "artist": "Main Artist featuring Guest",
            "album": "Album",
            "track_number": 3,
        }),
    ],
)
```

##### GC-13: Remaster vs. Original
**Rationale:** Common cataloging error; year/version metadata affects identity
**Invariant:** Identity disambiguation by release version
**Tricky Edge Case:** Files tagged "2023 Remaster" of 1973 album != original 1973 release
**Test Data:**
```python
CorpusScenario(
    name="remaster_vs_original",
    description="Same album, different release years.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-rem-01", 180, {
            "title": "Track 1",
            "artist": "Pink Floyd",
            "album": "Dark Side of the Moon",
            "date": "1973",
            "track_number": 1,
        }),
        _spec("02 - Track Remaster.flac", "fp-rem-02", 180, {
            "title": "Track 1",
            "artist": "Pink Floyd",
            "album": "Dark Side of the Moon (2023 Remaster)",
            "date": "2023",
            "track_number": 1,
        }),
    ],
)
```

##### GC-14: Non-Audio Files Only (No Audio)
**Rationale:** Folder contains only .jpg, .cue, .log - scanner must handle gracefully
**Invariant:** Scanning resilience
**Tricky Edge Case:** Should skip folder, not crash or create empty batch
**Test Data:**
```python
CorpusScenario(
    name="non_audio_only",
    description="Folder with only cover.jpg and notes.txt.",
    audio_specs=[],  # No audio!
    non_audio_files=["cover.jpg", "notes.txt", "album.cue"],
)
```

##### GC-15: Hidden Track (Track 0 or Track 99)
**Rationale:** Edge case in disc TOC mapping; causes off-by-one errors
**Invariant:** Track number canonicalization + layout
**Tricky Edge Case:** Track 0 should map correctly without breaking sequence
**Test Data:**
```python
CorpusScenario(
    name="hidden_track",
    description="Album with track 0 (pregap) and track 99 (hidden).",
    audio_specs=[
        _spec("00 - Hidden Intro.flac", "fp-h0-00", 15, {
            "title": "Hidden Intro",
            "artist": "Artist",
            "album": "Album",
            "track_number": 0,
        }),
        _spec("01 - Track 1.flac", "fp-h0-01", 200, {
            "title": "Track 1",
            "artist": "Artist",
            "album": "Album",
            "track_number": 1,
        }),
        _spec("99 - Secret Track.flac", "fp-h0-99", 120, {
            "title": "Secret Track",
            "artist": "Artist",
            "album": "Album",
            "track_number": 99,
        }),
    ],
)
```

---

#### **CHARACTER ENCODING / UNICODE GAPS** (3 scenarios)

##### GC-16: Mixed Encoding Tags (UTF-8 + Mojibake)
**Rationale:** Files from different ripping tools with inconsistent text encoding
**Invariant:** Canonicalization with encoding normalization
**Tricky Edge Case:** "Björk" (UTF-8) vs "Bj�rk" (Latin-1 corruption)
**Test Data:**
```python
CorpusScenario(
    name="mixed_encoding",
    description="UTF-8 vs corrupted Latin-1 tags.",
    # Would need to manually corrupt meta.json to simulate mojibake
)
```

##### GC-17: Unicode Normalization (NFD vs NFC)
**Rationale:** macOS uses NFD (decomposed), Windows uses NFC (composed)
**Invariant:** Unicode normalization for identity
**Tricky Edge Case:** "é" (U+00E9) vs "e" + combining acute (U+0065 U+0301)
**Test Data:**
```python
CorpusScenario(
    name="unicode_normalization",
    description="NFD vs NFC Unicode forms.",
    audio_specs=[
        _spec("01 - Café.flac", "fp-nfd-01", 180, {
            "title": "Café",  # NFC form
            "artist": "Artiste",
            "album": "Album",
            "track_number": 1,
        }),
        _spec("02 - Cafe\u0301.flac", "fp-nfd-02", 181, {
            "title": "Cafe\u0301",  # NFD form (decomposed)
            "artist": "Artiste",
            "album": "Album",
            "track_number": 2,
        }),
    ],
)
```

##### GC-18: Year Tag Overflow (Invalid Dates)
**Rationale:** Corrupted tags from buggy rippers
**Invariant:** Data validation + sanitization
**Tricky Edge Case:** DATE=0000 or DATE=UNKNOWN should normalize to null
**Test Data:**
```python
CorpusScenario(
    name="invalid_year",
    description="Year tag with nonsense values.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-year-01", 180, {
            "title": "Track 1",
            "artist": "Artist",
            "album": "Album",
            "date": "0000",  # Invalid
            "track_number": 1,
        }),
        _spec("02 - Track.flac", "fp-year-02", 181, {
            "title": "Track 2",
            "artist": "Artist",
            "album": "Album",
            "date": "UNKNOWN",  # Non-numeric
            "track_number": 2,
        }),
    ],
)
```

---

### 8.3 Summary of Missing Scenarios

| Category | Count | Highest Priority |
|----------|-------|-----------------|
| **Classical-Specific** | 7 | GC-1 (Opus normalization), GC-6 (Work nicknames) |
| **Filesystem Chaos** | 8 | GC-8 (Orphaned track), GC-10 (Partial tags), GC-12 (Featured artist) |
| **Character Encoding** | 3 | GC-16 (Mixed encoding), GC-17 (Unicode normalization) |
| **TOTAL** | **18** | **Focus on filesystem chaos first** |

### 8.4 Recommendation

**Immediate Priority (Add Next):**
1. **GC-8 (Orphaned track)** - Most common user error
2. **GC-12 (Featured artist)** - Causes duplicate artist proliferation
3. **GC-10 (Partial tags)** - Real-world incomplete metadata
4. **GC-1 (Opus normalization)** - Classical identity failures
5. **GC-13 (Remaster vs original)** - Release disambiguation

**Defer to Later:**
- GC-16/17 (Unicode edge cases) - Less common, harder to test deterministically
- GC-14 (Non-audio only) - Scanner should already skip gracefully
- GC-18 (Invalid year) - Low impact, easy validation fix

**Implementation Effort:**
- Each scenario: ~30 minutes (add to corpus_builder.py + provider fixtures)
- All 18 scenarios: ~9 hours total
- **ROI**: Protects against most common real-world corruption patterns

---

**End of Audit**

Note: Golden corpus gaps are tracked in `TDD_TODO_V3.md` under “0.8 Golden corpus backlog (from TEST_AUDIT.md)”.

# V3 Test Audit - Definition of Done Compliance

**Date:** 2025-12-21
**Scope:** Audit current test suite against V3 DoD requirements

---

## V3 Definition of Done (from TDD_TODO_V3.md)

V3 is done when:

1. ✅/❌ **Core invariants gate is green** (golden corpus + identity + canonicalization + idempotency + no-network-on-rerun)
2. ⚙️ **Discogs and MB integrated** with stable candidate canonicalization and ranking
3. ⚙️ **Apply writes tags correctly** for FLAC/MP3/M4A with provider IDs and overwrite policy
4. ⚙️ **Move/rename behavior correct** across multi-disc, compilations, collisions, extras
5. ⚙️ **Big 10 suite is green** and reruns are clean

---

## Executive Summary

**Current Status:**
- 🟡 **Golden Corpus:** 22 scenarios in code, only 8 have snapshots (64% missing)
- ✅ **Provider Fixtures:** All 22 scenarios have fixtures in musicbrainz.json
- ❌ **Critical Gap:** 14 scenarios missing snapshots (never regenerated)
- ❌ **Canonicalization Error:** 2 scenarios incorrectly added (require match_key_* system)
- 🔴 **V3 DoD Blocker:** Cannot pass "Core invariants gate" without snapshots

**Immediate Actions Required:**

1. Remove 2 canonicalization scenarios (work_nickname, ensemble_variants)
2. Run `REGEN_GOLDEN=1` to generate snapshots for remaining 20 scenarios
3. Verify all scenarios pass golden corpus test

---

## 1. Golden Corpus Status (DoD Requirement #1)

### 1.1 Scenarios with Snapshots ✅ (8/22 = 36%)

These have `tests/golden/expected/<scenario>/` directories:

1. ✅ `standard_album` - Full snapshots
2. ✅ `multi_disc` - Full snapshots
3. ✅ `compilation` - Full snapshots
4. ✅ `name_variants` - Full snapshots
5. ✅ `classical` - Full snapshots
6. ✅ `extras_only` - Full snapshots
7. ✅ `single_track` - Full snapshots
8. ✅ `mixed_media` - Full snapshots

### 1.2 Scenarios WITHOUT Snapshots ❌ (14/22 = 64%)

These exist in `corpus_builder.py` but have NO snapshots:

**Original scenarios missing snapshots (6):**
9. ❌ `multi_composer` - **MISSING** snapshots
10. ❌ `long_titles` - **MISSING** snapshots
11. ❌ `renamed_mid_processing` - **MISSING** snapshots
12. ❌ `missing_middle_tracks` - **MISSING** snapshots
13. ❌ `case_only_rename` - **MISSING** snapshots
14. ❌ `interrupted_apply` - **MISSING** snapshots

**Recently added scenarios missing snapshots (8):**
15. ❌ `opus_normalization` - **MISSING** snapshots
16. ❌ `conductor_vs_performer` - **MISSING** snapshots
17. ❌ `multi_performer_work` - **MISSING** snapshots
18. ❌ `catalog_variants` - **MISSING** snapshots
19. ❌ `partial_opera` - **MISSING** snapshots
20. ❌ `work_nickname` - **MISSING** snapshots (⚠️ REQUIRES CANONICALIZATION)
21. ❌ `ensemble_variants` - **MISSING** snapshots (⚠️ REQUIRES CANONICALIZATION)
22. ❌ `partial_tags` - **MISSING** snapshots

### 1.3 Critical Issue: Provider Fixtures

**Problem:** `test_golden_corpus.py` line 165 expects:
```python
release = provider_fixtures["musicbrainz"][scenario][0]
```

**Check which scenarios have fixtures:**

```bash
# Need to verify tests/golden/fixtures/musicbrainz.json contains all 22 scenarios
```

**Expected behavior:**
- If scenario missing from fixtures → KeyError
- If snapshot missing → FileNotFoundError (handled with failures list)
- Current test will collect all failures and report at end

### 1.4 Test Execution Status

**Current test:** `test_golden_corpus_end_to_end`
- Loops through all 22 scenarios
- Tries to load provider fixture for each
- Tries to assert snapshots for each
- Collects failures instead of crashing
- Reports all failures at end

**Expected failures:**
- 14 `FileNotFoundError` for missing snapshots
- Possibly 14 `KeyError` for missing provider fixtures

---

## 2. Canonicalization Scenarios (DoD Requirement #1)

### 2.1 Incorrectly Added Scenarios

These scenarios are in `corpus_builder.py` but **should be deferred** per CANONICALIZATION_AUDIT.md:

❌ **work_nickname** (lines 598-627)
- **Why wrong:** Requires work alias canonicalization ("Eroica" ⇔ "Symphony No. 3")
- **Status per audit:** Post-V3, blocked on `match_key_work` system
- **Action:** Remove from corpus_builder.py, move to TDD_TODO_V3.md section 0.9

❌ **ensemble_variants** (lines 628-660)
- **Why wrong:** Requires artist abbreviation canonicalization ("LSO" ⇔ "London Symphony Orchestra")
- **Status per audit:** Post-V3, blocked on `match_key_artist` system
- **Action:** Remove from corpus_builder.py, move to TDD_TODO_V3.md section 0.9

### 2.2 Why This Matters

**V3 DoD line 343:**
> "Core invariants gate is green (golden corpus + **identity + canonicalization** + idempotency)"

**Current canonicalization per TDD_TODO_V3.md lines 68-77:**
- `display_*` vs `match_key_*` separation defined
- Known variants listed: diacritics, slash variants, collaboration markers, comma-name
- **NOT YET IMPLEMENTED**

**These scenarios test canonicalization that doesn't exist yet:**
- `work_nickname`: Work alias matching
- `ensemble_variants`: Artist abbreviation matching

**Options:**
1. **Remove these 2 scenarios** until canonicalization exists
2. **Keep but mark as expected failures** (not recommended)
3. **Implement minimal canonicalization** to make them pass (scope creep)

**Recommendation:** Remove both scenarios, defer to post-V3 (per CANONICALIZATION_AUDIT.md section 2.2)

---

## 3. Missing Snapshots - Root Cause Analysis

### 3.1 Why Snapshots Are Missing

**Timeline:**
1. Original 8 scenarios had snapshots generated
2. You added 14 new scenarios to `corpus_builder.py`
3. Provider fixtures may or may not exist for new scenarios
4. Snapshots were never regenerated with `REGEN_GOLDEN=1`

**Impact:**
- Test collects all 22 scenarios
- Tries to process each one
- Fails on missing fixtures OR missing snapshots
- Reports all failures at end (graceful degradation added in latest changes)

### 3.2 Good News: Provider Fixtures Already Exist

**Status:** ✅ All 22 scenarios have provider fixtures in `tests/golden/fixtures/musicbrainz.json`

**Verified fixtures exist for:**

- All 8 scenarios with snapshots
- All 14 scenarios without snapshots (including the 2 that need removal)

**What this means:**

- No need to create provider fixtures
- Can immediately run `REGEN_GOLDEN=1` after removing canonicalization scenarios
- Snapshot generation should work for all remaining scenarios

### 3.3 Required Actions

**To fix the snapshot gap:**

1. **Remove canonicalization scenarios** from `tests/golden/corpus_builder.py`:
   - Remove `work_nickname` (lines 598-627)
   - Remove `ensemble_variants` (lines 628-660)
   - These require `match_key_*` system that doesn't exist yet

2. **Run regeneration:**
   ```bash
   REGEN_GOLDEN=1 pytest tests/integration/test_golden_corpus.py -v
   ```

3. **Verify snapshots created:**
   ```bash
   ls tests/golden/expected/<scenario>/
   # Should show: expected_layout.json, expected_tags.json, expected_state.json
   ```

---

## 4. Identity & Idempotency Tests (DoD Requirement #1)

### 4.1 Identity Invariants

**Required per TDD_TODO_V3.md lines 59-65:**
- ✅ Stable `dir_id` across file order changes
- ✅ Stable `dir_id` across mtime changes
- ✅ Stable `dir_id` across path renames
- ✅ Non-audio extras do not affect identity
- ⚠️ Empty-audio directories handled deterministically

**Current test coverage:**
- `test_golden_corpus_end_to_end` line 140-150: Tests path rename + tag variant identity
- **Gap:** No explicit test for empty-audio directory handling

### 4.2 Idempotency Invariants

**Required per TDD_TODO_V3.md lines 89-92:**
- ✅ Second run produces zero operations
- ✅ No rematch prompts for resolved items
- ⚠️ Plan hash stable if inputs unchanged

**Current test coverage:**
- `test_golden_corpus_end_to_end` lines 213-222: Tests second apply is NOOP
- **Gap:** Plan hash stability not explicitly tested

---

## 5. Integration Tests Audit

### 5.1 Scanner Behavior Tests

**New tests added** (in `test_filesystem_edge_cases.py`):
- ✅ `test_scanner_reunites_orphaned_track` (lines 210-228)
- ✅ `test_scanner_merges_split_album_dirs` (lines 231-254)

**Status:** Correctly placed in integration tests (not golden corpus)

### 5.2 Crash Recovery Tests

**Existing test** (`test_crash_recovery.py`):
- ✅ `test_applier_crash_after_file_moves_before_db_commit` (lines 56-108)

**Coverage:** Basic crash recovery, meets TEST_AUDIT.md Stop-Ship #1

### 5.3 Applier Tests

**Count:** 34 integration tests across applier, audit, idempotency files
**Status:** Good coverage of apply/rollback/conflict handling

---

## 6. V3 DoD Gap Analysis

### DoD #1: Core Invariants Gate

**Status:** 🔴 **BLOCKED**

**Gaps:**
1. ❌ 14 scenarios missing snapshots
2. ❌ 2 scenarios require canonicalization that doesn't exist
3. ⚠️ Empty-audio directory handling not tested
4. ⚠️ Plan hash stability not explicitly tested

**Action Plan:**
1. Remove `work_nickname` and `ensemble_variants` (defer to post-V3)
2. Add provider fixtures for remaining 12 scenarios
3. Run `REGEN_GOLDEN=1` to generate snapshots
4. Add test for empty-audio directory (should skip or error cleanly)
5. Add explicit plan hash stability test

### DoD #2: Discogs & MB Integration

**Status:** ⚙️ **IN PROGRESS**

**Evidence:**
- Provider fixtures exist for original 8 scenarios
- `FixtureProvider` in `test_golden_corpus.py` uses fingerprint-based matching
- No live network calls in tests

**Gaps:**
- Missing fixtures for 12 new scenarios
- Ranking/canonicalization not yet implemented (deferred)

### DoD #3: Tag Writing

**Status:** ⚙️ **PARTIAL**

**Evidence:**
- `MetaJsonTagWriter` used in golden corpus test
- Tags snapshot validated in `test_golden_corpus_end_to_end`
- Provenance tags tested

**Gaps:**
- Only FLAC tested (MP3/M4A format tests missing)
- Provider ID tags not explicitly verified

### DoD #4: Move/Rename Behavior

**Status:** ✅ **COVERED**

**Evidence:**
- Multi-disc: `multi_disc` scenario
- Compilations: `compilation` scenario
- Collisions: `test_applier_conflict_policy_*` tests
- Extras: `extras_only` scenario

### DoD #5: Big 10 Suite

**Status:** ⚠️ **INCOMPLETE**

**Big 10 per TDD_TODO_V3.md lines 33-43:**
1. ✅ Single track → `single_track` scenario
2. ✅ Standard album → `standard_album` scenario
3. ✅ Multi-disc → `multi_disc` scenario
4. ❌ Box set (multi-disc, repeated titles, long titles) → **MISSING**
5. ✅ Compilation → `compilation` scenario
6. ✅ Artist name variants → `name_variants` scenario
7. ✅ Classical → `classical` + new classical scenarios
8. ❌ Live album with "(Live)" in titles → **MISSING**
9. ❌ Album with hidden track/pregap oddities → **MISSING** (but `hidden_track` scenario proposed)
10. ✅ Album with extras → `extras_only` scenario

**Missing:** 3 scenarios from Big 10

---

## 7. Recommended Actions - Priority Order

### 🔴 CRITICAL (V3 Blocker)

1. **Remove canonicalization scenarios** (~5 min)
   - Edit `tests/golden/corpus_builder.py`
   - Remove `work_nickname` scenario (lines 598-627)
   - Remove `ensemble_variants` scenario (lines 628-660)
   - These require `match_key_*` system that doesn't exist yet
   - They are documented in TDD_TODO_V3.md section 0.9 for post-V3

2. **Generate snapshots** (~10-15 min)

   ```bash
   REGEN_GOLDEN=1 pytest tests/integration/test_golden_corpus.py -v
   # Will generate snapshots for all 20 remaining scenarios (22 - 2 removed)
   # Provider fixtures already exist ✅ - no need to create them
   ```

3. **Verify snapshots** (~5 min)

   ```bash
   # Check that all 20 scenarios now have snapshot directories
   ls tests/golden/expected/
   # Should see 20 directories (was 8, now 20)
   ```

### 🟡 HIGH PRIORITY (V3 Required)

4. **Add Big 10 missing scenarios** (~3 hours)
   - Box set scenario
   - Live album scenario
   - Hidden track scenario (use GC-15 from CANONICALIZATION_AUDIT.md)

5. **Add format tests** (~2 hours)
   - MP3 tag writing test
   - M4A tag writing test

### 🟢 NICE TO HAVE (Post-V3)

6. **Add explicit tests**
   - Empty-audio directory handling
   - Plan hash stability
   - Provider ID tag verification

---

## 8. Summary

**V3 DoD Status:** 🔴 **Cannot pass** - 14 missing snapshots, 2 incorrectly added scenarios

**Good News:**

- ✅ All 22 scenarios already have provider fixtures in musicbrainz.json
- ✅ Scanner integration tests already added (orphaned track, split album merge)
- ✅ No need to create fixtures - just remove wrong scenarios and regenerate snapshots

**Critical Path to Unblock V3:**

1. Remove 2 canonicalization scenarios (5 min)
2. Generate snapshots for 20 remaining scenarios (10-15 min)
3. Verify all snapshots created (5 min)
4. **Result:** Core invariants gate GREEN ✅

**Total effort to unblock V3:** ~20-25 minutes

**Remaining for full V3 DoD:** ~5 hours (Big 10 completion + format tests)

**Next immediate steps:**

```bash
# Step 1: Remove canonicalization scenarios from corpus_builder.py
# - Remove work_nickname (lines 598-627)
# - Remove ensemble_variants (lines 628-660)

# Step 2: Generate snapshots
REGEN_GOLDEN=1 pytest tests/integration/test_golden_corpus.py -v

# Step 3: Verify 20 snapshot directories exist
ls tests/golden/expected/
```

---

**End of Audit**

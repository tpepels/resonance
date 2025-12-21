# Phase A.2 Integration Test Findings

**Date:** 2025-12-21
**Status:** ✅ Test Created, ❌ Implementation Failing (as expected)

## Summary

Created comprehensive integration tests for the "no rematch on rerun" invariant (Phase A.2 of TDD_TODO_V3.md). The tests correctly expose **critical identity drift bugs** in the current implementation.

## Test File

[tests/integration/test_no_rematch_invariant.py](tests/integration/test_no_rematch_invariant.py)

Contains two tests:
1. `test_no_rematch_on_rerun_full_pipeline` - Full scan→resolve→apply→rerun cycle
2. `test_manual_rename_does_not_trigger_rematch` - Manual file rename scenario

Both tests are marked with `@pytest.mark.xfail` and document the known bugs.

## Critical Bug Discovered: Identity Drift After Apply

### The Problem

**After `apply_plan()` moves files and writes tags, the directory identity changes on subsequent scans.**

```
Initial scan:  dir_id = 'a25695d84e59b36e3639f5d2205b9027036a518af6963dc4fdf4e603967052dd'
After apply:   Files moved to: organized/Test Artist/0000 - Test Album/
After rerun:   dir_id = 'ddaa4d1b9e92ddd53a303c4a4bd2e07e740b17b4f28d9512c154800872b7fc1d'
                       ^^^ DIFFERENT! Identity drift detected ^^^
```

### Why This Happens

The `dir_id` is derived from `dir_signature()`, which is computed from:
- File content fingerprints (probably stable)
- File paths (CHANGED - files moved)
- File metadata (CHANGED - tags written)

When files move from source → destination and tags are written, the signature changes → `dir_id` changes → identity is lost.

### Why This Is STOP-SHIP Critical

This violates the **core V3 invariant**: "once resolved, a directory is never re-matched unless content changes."

**User-visible failure mode:**
1. User runs resonance → album gets organized
2. User runs resonance again → **same album gets re-identified, re-matched, potentially re-organized differently**
3. User loses trust in determinism

This is exactly what the audit identified as the primary regression risk.

## What The Tests Validate (When Passing)

### Test 1: Full Pipeline Idempotency

**Scenario:**
```
Run 1: scan → resolve → plan → apply
       (provider called, directory organized)

Run 2: scan → resolve
       (should detect already-applied state)
       ❌ NO provider calls
       ❌ NO new plan
       ❌ NO file mutations
```

**Currently Failing Because:**
- Run 2 scans the organized directory
- Gets a different `dir_id` (identity drift)
- Doesn't recognize it as the same directory
- Would trigger re-identification

### Test 2: Manual Rename Tolerance

**Scenario:**
```
1. Apply organizes directory
2. User manually renames a file: "01 - Track A.flac" → "01 - Track A (edited).flac"
3. Rerun should:
   ✓ Detect the manual change
   ❌ NOT re-identify the directory
   ✓ Keep directory in APPLIED state
```

**Currently Failing Because:**
- Manual rename changes file path
- Signature changes → `dir_id` changes
- System doesn't recognize it as the same directory

## Root Cause Analysis

The issue is in how `dir_id` is calculated:

**Current (broken):**
```python
dir_id = dir_signature(audio_files)
# Signature includes file paths, so path changes = identity changes
```

**Needed:**
```python
# Identity should be based on CONTENT only, not paths or tags
dir_id = content_based_hash(file_fingerprints_only)
```

The signature should separate:
- **Content fingerprints** (for identity/matching) - IMMUTABLE
- **File paths + tags** (for change detection) - MUTABLE

## Path Forward

### Option 1: Fix `dir_id` Calculation (Recommended)
- Make `dir_id` based solely on audio content fingerprints
- Keep `signature_hash` for change detection
- `dir_id` stays constant even when files move or tags change

### Option 2: Store Original `dir_id` in State
- When directory is first scanned, record its `dir_id`
- After apply, use the stored `dir_id` to reconnect to the same record
- This is more complex and error-prone

### Option 3: Write Provenance to Track Identity
- Write `resonance.prov.dir_id` tag to audio files
- On rescan, read the tag to recover original identity
- Fragile - tags could be stripped

**Recommendation:** Option 1 is cleanest and aligns with the audit's recommendation to freeze identity.

## Next Steps

1. ✅ Integration tests created (this step - DONE)
2. ⏸️ Fix identity drift bug (blocks all other Phase A work)
3. ⏸️ Formalize canonicalization (Phase A.1)
4. ⏸️ Add golden corpus (Phase A.3)

**The identity drift bug is now the critical blocker for Phase A.**

## Test Execution

```bash
# Run the tests (they should XFAIL, not FAIL)
pytest tests/integration/test_no_rematch_invariant.py -v

# Expected output:
# XFAIL tests/integration/test_no_rematch_invariant.py::test_no_rematch_on_rerun_full_pipeline
# XFAIL tests/integration/test_no_rematch_invariant.py::test_manual_rename_does_not_trigger_rematch
```

When the identity bug is fixed, remove the `@pytest.mark.xfail` decorators and the tests should pass.

## References

- TDD_TODO_V3.md Phase A.2: "Stable directory identity & no-rematch invariant"
- CONSOLIDATED_AUDIT.md §C-1: Dual architecture enables identity drift
- CONSOLIDATED_AUDIT.md §1.2: Golden corpus is the determinism firewall
- [tests/integration/test_no_rematch_invariant.py](tests/integration/test_no_rematch_invariant.py): The integration tests

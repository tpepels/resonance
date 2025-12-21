# Resonance TODO - Safety & Testing

**Current Status:** 🟡 C- (Most critical stuff is done!)

## What's Already Done ✅

You've already implemented the most important safety features:

- ✅ Path traversal protection (can't write outside allowed roots)
- ✅ Input validation (dir_id, signature_hash, release_id formats)
- ✅ Schema versioning (DB tracks version, supports migration)
- ✅ Partial completion detection (detects when some files moved, not all)
- ✅ Signature versioning (detects algorithm changes)
- ✅ User modification detection (signature mismatch catches renamed/deleted files)
- ✅ 234 tests with good determinism practices

**You're not losing user data, and you're not corrupting the DB. Everything else is polish.**

---

## Critical TODOs (Actually Do These)

### 1. Test: Crash Recovery (~2 hours)

**File:** `tests/integration/test_crash_recovery.py`

```python
def test_applier_crash_after_file_moves_before_db_commit(tmp_path: Path) -> None:
    """
    Simulate: All files moved, but process dies before DB.commit().
    Expected: On re-run, detect completed moves and return NOOP.
    """
    # Setup: create plan, manually move all files to simulate completed apply
    # Act: call apply() again
    # Assert: returns NOOP_ALREADY_APPLIED, DB state updated to APPLIED
```

**Why:** Most common crash point in real usage. Users will hit this.

---

### 2. Test: Schema Version Downgrade (~1 hour)

**File:** `tests/unit/test_directory_state.py` (add to existing file)

```python
def test_directory_store_rejects_future_schema_version(tmp_path: Path) -> None:
    """
    DB from v0.2.0 opened by v0.1.0 should fail with clear error.
    """
    # Setup: manually create DB with schema_version=99
    # Act: DirectoryStore(db_path)
    # Assert: raises ValueError("DB schema 99 > supported 1. Please upgrade Resonance.")
```

**Why:** Prevents silent corruption when users downgrade versions.

---

### 3. Fix: Path Validation at Deserialization (~1 hour)

**File:** `resonance/core/planner.py` or wherever Plan.from_json() lives

**Current:** Path validation happens at apply time
**Problem:** TOCTOU - plan could be modified between load and apply
**Fix:** Validate paths when loading plan.json

```python
@classmethod
def from_json(cls, path: Path) -> Plan:
    data = json.loads(path.read_text())
    # Validate paths HERE, not at apply time
    for op in data.get("operations", []):
        if ".." in str(op.get("source_path", "")):
            raise ValueError("Path traversal not allowed in plan")
        if ".." in str(op.get("destination_path", "")):
            raise ValueError("Path traversal not allowed in plan")
    return cls(**data)
```

**Why:** Security - closes TOCTOU gap.

---

## Nice-to-Have (If You're Feeling Motivated)

### 4. Better Error Messages

**When user renames/deletes files:**

```python
# Current error:
"Missing source file: /music/album/track.flac"

# Better error:
"File not found: /music/album/track.flac"
"(Did you rename or delete it? Run 'resonance scan' to update the plan)"
```

**When rollback fails:**

```python
# Current: Generic error
# Better: "Rollback partially completed:"
#         "  ✓ Moved back: track1.flac, track2.flac"
#         "  ✗ Failed on: track3.flac (permission denied)"
#         "  → Still at destination: track3.flac, track4.flac"
#         "  → Manual cleanup required"
```

---

### 5. Documentation (30 minutes)

**Add to README.md:**

```markdown
## Crash Recovery

If `resonance apply` crashes mid-way:
1. Just run `resonance apply` again - it detects completed moves
2. If you see "Partial completion detected", some files are in limbo
3. Run `resonance scan` to re-analyze the directory

## Version Upgrades

Schema migrations are automatic. If you see:
- "DB schema 2 > supported 1" → Upgrade Resonance
- "Migrating DB schema 1 → 2" → Normal, automatic
```

---

## Things You DON'T Need to Do

❌ Write-Ahead Logging (WAL) - Over-engineered for this project
❌ Chaos testing framework - You're not Netflix
❌ Fuzzy filename matching for renames - Users can just re-scan
❌ Tag validation (length limits, null bytes) - MusicBrainz already validates
❌ Cache corruption detection - Cache can just be rebuilt
❌ Provenance tag versioning - Not worth the complexity
❌ JSON Schema validation library - Simple checks are fine
❌ Incremental state updates (APPLYING, APPLYING_TAGS) - Nice to have, not critical
❌ Expected source files tracking - Signature hash already covers this

---

## Summary

**Critical (Do before v1.0):**
1. Test crash recovery (2 hours)
2. Test schema version rejection (1 hour)
3. Move path validation to deserialization (1 hour)

**Total: ~4 hours to ship v1.0**

**Nice-to-have:**
- Better error messages (1-2 hours)
- README docs (30 min)

Everything else is over-engineering for a music library organizer. Ship it! 🚀

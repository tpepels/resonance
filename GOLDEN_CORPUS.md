# Golden Corpus: The Determinism Firewall

**Phase A.3 — Invariant Lock**

The golden corpus is Resonance's **hard blocking gate** for determinism and correctness.

## Purpose

The golden corpus ensures that:

1. **Identity is stable** - `dir_id` never changes for the same audio content
2. **Canonicalization is consistent** - Artist/album names are normalized deterministically
3. **No rematching** - Resolved directories are never re-identified on rerun
4. **Output is reproducible** - Same input always produces same output (tags, paths, state)

All invariants from [TDD_TODO_V3.md](TDD_TODO_V3.md) Phase A are validated here.

## Test Structure

**File:** [`tests/integration/test_golden_corpus.py`](tests/integration/test_golden_corpus.py)

The test runs a full end-to-end pipeline for 26 comprehensive scenarios:

### Standard Scenarios
- `standard_album` - Basic 10-track album
- `multi_disc` - Two-disc album with disc numbers
- `compilation` - Various Artists compilation
- `single_track` - Single-track release

### Identity & Canonicalization
- `name_variants` - AC/DC, Björk, Alt-J (punctuation/diacritics)
- `unicode_normalization` - NFC vs NFD normalization
- `case_only_rename` - Case-only path changes

### Classical Music
- `classical` - Composer/performer/work structure
- `multi_composer` - Multiple composers in one album
- `conductor_vs_performer` - Soloist/orchestra/conductor separation
- `multi_performer_work` - Same work, different performers
- `opus_normalization` - Op. 27 No. 2 vs op.27, no.2
- `catalog_variants` - BWV, K. numbering
- `partial_opera` - Non-contiguous opera scenes

### Edge Cases
- `long_titles` - Filesystem length limits
- `missing_middle_tracks` - Gapped track numbers (1, 2, 5, 6)
- `hidden_track` - Track 0 and track 99
- `partial_tags` - Missing artist/album metadata
- `duplicate_files` - Same fingerprint, different filenames
- `remaster_vs_original` - Remaster year tagging

### Extras & Media
- `extras_only` - Cover/booklet/cue/log files
- `mixed_media` - Audio + video (bonus_video.mp4)

### Edge Case Handling
- `renamed_mid_processing` - Directory renamed after planning
- `interrupted_apply` - Apply interrupted mid-move
- `invalid_year` - Invalid date tags (0000, UNKNOWN)
- `non_audio_only` - No audio files (skipped by scanner)

### For Each Scenario

The test validates:

1. **Identity invariance** (lines 133-150)
   - Path rename doesn't change `dir_id`
   - Tag changes don't change `dir_id`

2. **Full pipeline** (lines 167-217)
   - Scan → Resolve → Plan → Apply
   - All scenarios reach `APPLIED` state

3. **Idempotency** (lines 219-234)
   - Second apply is `NOOP_ALREADY_APPLIED`
   - No mutations on rerun

4. **Snapshot validation** (lines 236-294)
   - **Layout snapshot:** File paths in organized output
   - **Tags snapshot:** Filtered tag values (album, artist, title, tracknumber, prov.*)
   - **State snapshot:** Directory state record (provider, release_id, state)

## Snapshot Files

**Location:** `tests/golden/expected/{scenario}/`

Each scenario has three snapshot files:

```
expected_layout.json   # File paths after apply
expected_tags.json     # Tag values (filtered)
expected_state.json    # DirectoryStateStore record
```

### Example: `standard_album/expected_tags.json`

```json
{
  "tracks": [
    {
      "path": "Artist A/Standard Album/01 - Track 1.flac",
      "tags": {
        "album": "Standard Album",
        "albumartist": "Artist A",
        "title": "Track 1",
        "tracknumber": "1",
        "resonance.prov.version": "3",
        "resonance.prov.tool": "resonance",
        "resonance.prov.dir_id": "dir_abc123...",
        "resonance.prov.pinned_provider": "musicbrainz",
        "resonance.prov.pinned_release_id": "mb-rel-001",
        "resonance.prov.applied_at_utc": "2024-01-01T00:00:00+00:00"
      }
    }
  ]
}
```

## Enforcement as Blocking Gate

### 1. Test Ordering (Phase A.3)

**File:** [`tests/integration/conftest.py`](tests/integration/conftest.py)

The `pytest_collection_modifyitems` hook ensures golden corpus runs **first**:

```python
def pytest_collection_modifyitems(config, items):
    golden_corpus_tests = [item for item in items if "test_golden_corpus" in item.nodeid]
    other_tests = [item for item in items if "test_golden_corpus" not in item.nodeid]
    items[:] = golden_corpus_tests + other_tests  # Golden first
```

**Effect:** If golden corpus fails, you see the failure immediately before other tests run.

### 2. Failure Interpretation

When golden corpus fails, **stop all work** and investigate:

```bash
$ pytest tests/integration/test_golden_corpus.py -v

# If FAILED:
# 1. DO NOT proceed with other work
# 2. DO NOT regenerate snapshots without investigation
# 3. Investigate root cause (identity drift? canonicalization bug?)
# 4. Fix the code, not the snapshots
```

**Valid responses to failure:**
- ✅ Fix the code to match snapshots
- ✅ Investigate why output changed
- ✅ Verify if this is a legitimate bug fix

**Invalid responses:**
- ❌ Set `REGEN_GOLDEN=1` without understanding what changed
- ❌ Continue other work while golden corpus is red
- ❌ Assume "tests are just flaky"

### 3. Regenerating Snapshots (REQUIRES JUSTIFICATION)

**WARNING:** Snapshot regeneration modifies the determinism baseline.

#### When to Regenerate

**Valid reasons:**
1. **Bug fix that changes legitimate output**
   - Example: "Fixed canonicalization of 'AC/DC' to preserve slash instead of stripping it"
   - You understand the change, it's intentional, it's better

2. **Intentional behavior change with documented rationale**
   - Example: "Changed provenance timestamp format from ISO8601 to RFC3339"
   - Breaking change is documented in TDD_TODO_V3.md or CONSOLIDATED_AUDIT.md

3. **Adding new scenarios** (existing snapshots should NOT change)
   - Example: "Added scenario for vinyl rips with different metadata"
   - Only new snapshot files created, no existing files modified

**Invalid reasons:**
1. ❌ "Tests were failing" → Fix the code, investigate the root cause
2. ❌ "Output changed" → WHY did it change? Is this a regression?
3. ❌ No explanation → Unacceptable

#### How to Regenerate

```bash
# 1. Set environment variable
export REGEN_GOLDEN=1

# 2. Run the test (you'll see a big warning)
pytest tests/integration/test_golden_corpus.py -v

# 3. Review EVERY changed file
git diff tests/golden/expected/

# 4. For each changed file, ask:
#    - Why did this change?
#    - Is this change correct?
#    - Does this represent a regression or improvement?

# 5. Document justification
git add tests/golden/expected/
git commit -m "Regenerate golden corpus: [REASON]

Justification:
- [Explain what changed]
- [Explain why it's correct]
- [Reference issue/audit finding if applicable]
"

# 6. Run tests WITHOUT REGEN_GOLDEN=1 to verify
unset REGEN_GOLDEN
pytest tests/integration/test_golden_corpus.py -v

# If tests fail without REGEN_GOLDEN=1, you have non-determinism!
# This is a critical bug - investigate before proceeding.
```

#### Warning System

When `REGEN_GOLDEN=1` is set, pytest displays a large warning:

```
================================================================================
WARNING: REGEN_GOLDEN=1 is set!

You are regenerating golden corpus snapshots. This modifies the
determinism baseline for the entire project.

Phase A.3 requirement: Snapshot regeneration requires explicit
justification in commit messages or PR descriptions.
...
================================================================================
```

This warning is **intentionally verbose** to prevent accidental regeneration.

## CI/CD Integration (Future)

**Recommended CI enforcement:**

```yaml
# .github/workflows/test.yml
jobs:
  golden-corpus-gate:
    name: "Golden Corpus (Blocking)"
    runs-on: ubuntu-latest
    steps:
      - name: Run golden corpus first
        run: pytest tests/integration/test_golden_corpus.py -v --maxfail=1
        # CRITICAL: --maxfail=1 stops on first failure

      - name: Fail if REGEN_GOLDEN was used
        run: |
          if [ -n "$(git diff tests/golden/expected/)" ]; then
            echo "ERROR: Golden corpus snapshots were modified!"
            echo "This is not allowed in CI. Run regeneration locally with justification."
            exit 1
          fi

  other-tests:
    name: "All Other Tests"
    needs: golden-corpus-gate  # BLOCKS on golden corpus
    runs-on: ubuntu-latest
    steps:
      - name: Run remaining tests
        run: pytest tests/ -v
```

## Integration with TDD_TODO_V3.md

**Phase A.3 Status:** ✅ **COMPLETE**

Requirements:
- ✅ Golden corpus runs before all other V3 suites (pytest hook)
- ✅ Failure of any scenario blocks further work (documented protocol)
- ✅ At least one minimal scenario (26 comprehensive scenarios)
  - ✅ Standard album
  - ✅ Snapshot: layout, tags, state
  - ✅ Rerun = no-op (idempotency check)
- ✅ Snapshot regeneration requires explicit justification (warning + docs)

**Phase A (Invariant Lock) Status:**
- ✅ Phase A.1: Canonicalization formalized ([resonance/core/identity/canonicalize.py](resonance/core/identity/canonicalize.py))
- ✅ Phase A.2: No-rematch invariant ([tests/integration/test_no_rematch_invariant.py](tests/integration/test_no_rematch_invariant.py))
- ✅ Phase A.3: Golden corpus gate (this document)

**Phase A is complete.** Phase B (Legacy Closure) may now proceed.

## References

- [TDD_TODO_V3.md](TDD_TODO_V3.md) - Phase-based execution plan
- [CONSOLIDATED_AUDIT.md](CONSOLIDATED_AUDIT.md) - Audit findings and context
- [tests/integration/test_golden_corpus.py](tests/integration/test_golden_corpus.py) - Test implementation
- [tests/golden/corpus_builder.py](tests/golden/corpus_builder.py) - Scenario definitions
- [PHASE_A2_FINDINGS.md](PHASE_A2_FINDINGS.md) - Identity drift bug investigation

---

**Remember:** The golden corpus is not just a test. It's the **firewall** that protects determinism.

If golden corpus is red, **nothing else matters** until it's green again.

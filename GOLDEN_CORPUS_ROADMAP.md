# Golden Corpus Implementation Roadmap

**Quick reference for adding deterministic golden corpus scenarios**

---

## Current Status

- ✅ **22 scenarios** in corpus (canonicalization-gated scenarios removed)
- 🎯 **Target for V3:** 26 scenarios (+4 new remaining)
- 🔮 **Post-V3 backlog:** 2 canonicalization scenarios + 2 integration tests

---

## Phase 1: Add 6 Deterministic Scenarios (V3 Blocker)

**Effort:** ~4 hours
**Status:** Ready to implement

### Quick Add List

1. ✅ **partial_opera** - Non-contiguous opera excerpts (Act II + IV, skip I & III)
2. ✅ **partial_tags** - Missing album/artist tags, infer from siblings
3. ⬜ **duplicate_files** - Same fingerprint, different filenames
4. ⬜ **remaster_vs_original** - Same album, different release years (1973 vs 2023)
5. ⬜ **non_audio_only** - Folder with only .jpg/.cue/.log, no audio
6. ⬜ **hidden_track** - Track 0 (pregap) and track 99 (secret)
7. ⬜ **unicode_normalization** - NFD vs NFC ("Café" different encodings)
8. ⬜ **invalid_year** - Year tags "0000" or "UNKNOWN"

### Implementation Steps

For each scenario:

1. Add to `tests/golden/corpus_builder.py` scenarios() list
2. Add provider fixture to `tests/golden/fixtures/musicbrainz.json` (if matching needed)
3. Run: `REGEN_GOLDEN=1 pytest tests/integration/test_golden_corpus.py`
4. Verify snapshots in `tests/golden/expected/<scenario>/`
5. Commit snapshots

**See CANONICALIZATION_AUDIT.md section 3.2 for full specs.**

---

## Phase 2: Integration Tests (V3 Optional)

**Effort:** ~1 hour
**File:** `tests/integration/test_scanner_edge_cases.py` (new)

1. ✅ **test_scanner_reunites_orphaned_tracks()** - Track moved to parent dir
2. ✅ **test_scanner_merges_split_album()** - Album split across two dirs

**Not golden corpus because:** Multi-directory setup doesn't fit single-scenario model.

---

## Phase 3: Post-V3 Backlog (Defer)

**Blocker:** Requires `match_key_*` canonicalization system (TDD_TODO_V3.md lines 68-77)

### Canonicalization Scenarios (2)

1. 🔮 **featured_artist** - "feat." ⇔ "ft" ⇔ "featuring"
2. 🔮 **work_nickname** - "Eroica" ⇔ "Symphony No. 3 in E-flat Major, Op. 55"
3. 🔮 **ensemble_variants** - "LSO" ⇔ "London Symphony Orchestra"

**Status:** Test data ready in CANONICALIZATION_AUDIT.md section 2.2
**Add when:** Artist/work alias canonicalization is implemented

### Skipped

- ❌ **mixed_encoding** (GC-16) - Non-deterministic, can't reliably test mojibake

---

## V3 Completion Checklist

- [ ] Phase 1: Add 6 scenarios to golden corpus (~3 hours)
- [ ] Verify all 26 scenarios pass `test_golden_corpus.py`
- [ ] (Optional) Phase 2: Add 2 scanner integration tests (~1 hour)
- [ ] Update TDD_TODO_V3.md section 0.8 with post-V3 backlog ✅ (done)
- [ ] V3 golden corpus gate: GREEN

---

**For detailed analysis, see:**
- `CANONICALIZATION_AUDIT.md` - Full determinism audit
- `TEST_AUDIT.md` - Original gap analysis
- `TDD_TODO_V3.md` section 0.8 - Post-V3 backlog

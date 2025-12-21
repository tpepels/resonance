# Canonicalization & Golden Corpus Determinism Audit

**Date:** 2025-12-21
**Scope:** Review all proposed golden corpus scenarios for determinism and canonicalization requirements

---

## Executive Summary

**Current Status:** 18 scenarios in corpus (13 original + 4 classical added + 1 in progress)
**Proposed Additions:** 18 scenarios from TEST_AUDIT.md
**Deterministic & Ready:** 10 scenarios
**Requires Canonicalization (defer to post-V3):** 4 scenarios
**Not Golden Corpus (use integration tests):** 3 scenarios
**Skip (non-deterministic):** 1 scenario

---

## 1. Current Golden Corpus (18 scenarios - all deterministic ✅)

### 1.1 Original Scenarios (13)
1. ✅ `standard_album` - 10 tracks, clean tags
2. ✅ `multi_disc` - 2 discs with disc numbers
3. ✅ `compilation` - Various Artists
4. ✅ `name_variants` - AC/DC, Björk, Alt-J (diacritics/punctuation)
5. ✅ `classical` - Basic composer + performer
6. ✅ `extras_only` - Heavy extras (cover/booklet/cue/log)
7. ✅ `single_track` - Single-track release
8. ✅ `mixed_media` - Audio + video
9. ✅ `multi_composer` - Classical compilation (Beethoven + Mozart)
10. ✅ `long_titles` - >200 char titles, truncation
11. ✅ `renamed_mid_processing` - Folder renamed after planning
12. ✅ `missing_middle_tracks` - Tracks 1, 2, 5, 6 (no 3, 4)
13. ✅ `case_only_rename` - Case-only path changes

### 1.2 Recently Added (4)
14. ✅ `opus_normalization` - "Op. 27 No. 2" vs "op.27, no.2"
15. ✅ `conductor_vs_performer` - Piano concerto credit hierarchy
16. ✅ `multi_performer_work` - Same work, different soloists per movement
17. ✅ `catalog_variants` - BWV 1006 vs K.525 numbering

### 1.3 In Progress (1)
18. ⚙️ `interrupted_apply` - Half-moved files (crash recovery)

**All 18 are deterministic** - fixed fingerprints, tags, and file structures.

---

## 2. Proposed Additions - Determinism Analysis

### 2.1 ✅ DETERMINISTIC - Can Add Immediately (10 scenarios)

These require **zero canonicalization logic** - they're pure structural/tag tests:

#### GC-10: Partial Tags (Missing Album/Artist)
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
            # artist missing, album missing
            "track_number": 2,
        }),
    ],
)
```
**Why deterministic:** Tests metadata inference from siblings, no canonicalization needed.

---

#### GC-11: Duplicate Files (Same Fingerprint)
```python
CorpusScenario(
    name="duplicate_files",
    description="Same track copied with different names.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-dup-01", 180, {...}),
        _spec("01 - Track (copy).flac", "fp-dup-01", 180, {...}),  # Same fingerprint!
    ],
)
```
**Why deterministic:** Tests deduplication via signature, works with current framework.

---

#### GC-13: Remaster vs. Original
```python
CorpusScenario(
    name="remaster_vs_original",
    description="Same album, different release years.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-rem-01", 180, {
            "artist": "Pink Floyd",
            "album": "Dark Side of the Moon",
            "date": "1973",
        }),
        _spec("02 - Track Remaster.flac", "fp-rem-02", 180, {
            "artist": "Pink Floyd",
            "album": "Dark Side of the Moon (2023 Remaster)",
            "date": "2023",
        }),
    ],
)
```
**Why deterministic:** Tests release version disambiguation by date/title.

---

#### GC-14: Non-Audio Files Only
```python
CorpusScenario(
    name="non_audio_only",
    description="Folder with only cover.jpg and notes.txt.",
    audio_specs=[],  # No audio!
    non_audio_files=["cover.jpg", "notes.txt", "album.cue"],
)
```
**Why deterministic:** Tests scanner resilience, should skip folder gracefully.

---

#### GC-15: Hidden Track (Track 0 or Track 99)
```python
CorpusScenario(
    name="hidden_track",
    description="Album with track 0 (pregap) and track 99 (hidden).",
    audio_specs=[
        _spec("00 - Hidden Intro.flac", "fp-h0-00", 15, {"track_number": 0}),
        _spec("01 - Track 1.flac", "fp-h0-01", 200, {"track_number": 1}),
        _spec("99 - Secret Track.flac", "fp-h0-99", 120, {"track_number": 99}),
    ],
)
```
**Why deterministic:** Tests track number edge cases, no canonicalization.

---

#### GC-17: Unicode Normalization (NFD vs NFC)
```python
CorpusScenario(
    name="unicode_normalization",
    description="NFD vs NFC Unicode forms.",
    audio_specs=[
        _spec("01 - Café.flac", "fp-nfd-01", 180, {
            "title": "Café",  # NFC: U+00E9
        }),
        _spec("02 - Cafe\u0301.flac", "fp-nfd-02", 181, {
            "title": "Cafe\u0301",  # NFD: U+0065 U+0301
        }),
    ],
)
```
**Why deterministic:** Unicode forms are stable, can encode in JSON.

---

#### GC-18: Invalid Year Tags
```python
CorpusScenario(
    name="invalid_year",
    description="Year tag with nonsense values.",
    audio_specs=[
        _spec("01 - Track.flac", "fp-year-01", 180, {"date": "0000"}),
        _spec("02 - Track.flac", "fp-year-02", 181, {"date": "UNKNOWN"}),
    ],
)
```
**Why deterministic:** Tests data validation, pure input/output.

---

#### GC-5: Partial Opera (Non-Contiguous Excerpts)
```python
CorpusScenario(
    name="partial_opera",
    description="La Bohème excerpts (Act II + Act IV, skipping I & III).",
    audio_specs=[
        _spec("01 - Act II Scene 3.flac", "fp-opera-01", 480, {
            "title": "La Bohème: Act II, Scene 3 - Quando m'en vo'",
            "track_number": 1,
        }),
        _spec("02 - Act IV Scene 2.flac", "fp-opera-02", 520, {
            "title": "La Bohème: Act IV, Scene 2 - Vecchia zimarra",
            "track_number": 2,
        }),
    ],
)
```
**Why deterministic:** Tests non-contiguous track sequencing, no canonicalization.

---

#### GC-2: Conductor vs. Performer (Already Added ✅)
**Status:** Already in corpus as `conductor_vs_performer`

---

#### GC-3: Multi-Performer Work (Already Added ✅)
**Status:** Already in corpus as `multi_performer_work`

---

### 2.2 ⚠️ REQUIRES CANONICALIZATION - Defer to Post-V3 (4 scenarios)

These test **artist/title canonicalization logic** that doesn't exist yet. Per TDD_TODO_V3.md, canonicalization is explicitly deferred.

#### GC-12: Featured Artist Variations
```python
audio_specs=[
    _spec("01 - Track.flac", "fp-feat-01", 200, {"artist": "Main Artist feat. Guest"}),
    _spec("02 - Track.flac", "fp-feat-02", 201, {"artist": "Main Artist ft Guest"}),
    _spec("03 - Track.flac", "fp-feat-03", 202, {"artist": "Main Artist featuring Guest"}),
]
```
**Requires:** Canonicalization of `feat.` ⇔ `ft` ⇔ `featuring`
**Status per TDD_TODO_V3.md line 75:** "collaboration markers normalized consistently (`feat`, `ft`, `featuring`, `with`, `w/`, `f.`, `x`, `pres.`)" - **planned but not implemented**

---

#### GC-6: Work Nickname vs. Formal Title
```python
audio_specs=[
    _spec("01 - Eroica.flac", "fp-nick-01", 800, {"title": "Eroica Symphony: I. Allegro"}),
    _spec("02 - Symphony 3.flac", "fp-nick-02", 750, {"title": "Symphony No. 3 in E-flat Major, Op. 55"}),
]
```
**Requires:** Work alias canonicalization ("Eroica" ⇔ "Symphony No. 3")
**Status:** Not in TDD_TODO_V3.md - **classical canonicalization is future work**

---

#### GC-7: Ensemble Name Variations
```python
audio_specs=[
    _spec("01 - LSO.flac", "fp-ens-01", 320, {"album_artist": "LSO"}),
    _spec("02 - London Symphony.flac", "fp-ens-02", 340, {"album_artist": "London Symphony Orchestra"}),
]
```
**Requires:** Artist alias canonicalization ("LSO" ⇔ "London Symphony Orchestra")
**Status per TDD_TODO_V3.md line 73:** "Björk ⇔ Bjork (match key only)" - **diacritics only, not abbreviations**

---

#### GC-1: Opus Normalization (Already Added ✅)
**Status:** Already in corpus as `opus_normalization`
**Note:** Currently tests **input variation**, not canonicalization. If system needs to match "Op. 27 No. 2" = "op.27, no.2", that's future work.

---

### 2.3 🔧 NOT GOLDEN CORPUS - Use Integration Tests (3 scenarios)

These test **scanner behavior** across directories, not end-to-end workflow.

#### GC-8: Orphaned Track Reunification
**Why not golden:** Requires multi-path setup (album in one dir, orphan in parent). Golden corpus uses single-directory scenarios.
**Where:** Add to `tests/integration/test_scanner_edge_cases.py` or `test_filesystem_edge_cases.py`

---

#### GC-9: Split Album (Interrupted Move)
**Why not golden:** Requires two separate directories with partial album data.
**Where:** Integration test for scanner merge logic.

---

#### GC-4: Catalog Variants (Already Added ✅)
**Status:** Already in corpus as `catalog_variants`
**Note:** Tests input variety (BWV vs K.), not canonicalization.

---

### 2.4 ❌ SKIP - Non-Deterministic (1 scenario)

#### GC-16: Mixed Encoding Tags (UTF-8 + Mojibake)
**Why skip:** Simulating corrupted encoding in `.meta.json` is unreliable:
- Meta.json is UTF-8 by default
- Would need raw byte manipulation to corrupt
- Reader behavior (normalize/reject) is unpredictable across platforms
**Alternative:** If needed, test with real corrupted files in a manual QA scenario.

---

## 3. Summary Tables

### 3.1 Corpus Status

| Category | Current | Add Now | Defer | Integration | Skip | **Total** |
|----------|---------|---------|-------|-------------|------|-----------|
| **Classical** | 4 | 1 (GC-5) | 2 (GC-6, GC-7) | 0 | 0 | **7** |
| **Filesystem** | 6 | 4 (GC-10,11,14,15) | 1 (GC-12) | 2 (GC-8,9) | 0 | **13** |
| **Encoding** | 1 (name_variants) | 2 (GC-17,18) | 0 | 0 | 1 (GC-16) | **4** |
| **Structure** | 7 | 1 (GC-13) | 0 | 0 | 0 | **8** |
| **TOTAL** | **18** | **+8** | **3** | **2** | **1** | **32** |

**V3 Golden Corpus Target:** 26 scenarios (18 current + 8 new)
**Post-V3 Backlog:** 3 canonicalization scenarios
**Integration Tests:** 2 scanner edge cases

---

### 3.2 Implementation Roadmap

#### ✅ Phase 1: Add 8 Deterministic Scenarios (~4 hours)

1. **GC-5** (Partial opera) - 30 min
2. **GC-10** (Partial tags) - 30 min
3. **GC-11** (Duplicate files) - 30 min
4. **GC-13** (Remaster vs original) - 30 min
5. **GC-14** (Non-audio only) - 30 min
6. **GC-15** (Hidden track) - 30 min
7. **GC-17** (Unicode NFD/NFC) - 30 min
8. **GC-18** (Invalid year) - 30 min

**All require:**
- Add scenario to `corpus_builder.py`
- Add provider fixtures to `tests/golden/fixtures/musicbrainz.json` (if needed)
- Run `REGEN_GOLDEN=1 pytest tests/integration/test_golden_corpus.py`
- Verify snapshots

---

#### ⚠️ Phase 2: Integration Tests (~1 hour)

1. **GC-8** (Orphaned track) - `test_scanner_reunites_orphaned_tracks()`
2. **GC-9** (Split album) - `test_scanner_merges_split_album()`

Add to `tests/integration/test_scanner_edge_cases.py` (new file).

---

#### 🔮 Phase 3: Post-V3 Canonicalization (defer to backlog)

These require **match_key canonicalization** (TDD_TODO_V3.md lines 68-77):

1. **GC-12** (Featured artist) - `feat.` ⇔ `ft` ⇔ `featuring`
2. **GC-6** (Work nickname) - "Eroica" ⇔ "Symphony No. 3"
3. **GC-7** (Ensemble variants) - "LSO" ⇔ "London Symphony Orchestra"

**Defer until:** Artist/work canonicalization system is implemented (post-V3).

---

## 4. Recommendations

### 4.1 For V3 Completion

**Add Phase 1 scenarios now** (8 scenarios, 4 hours):
- All are **fully deterministic**
- No canonicalization needed
- Protect high-risk edge cases (partial tags, duplicates, hidden tracks)

**Add Phase 2 integration tests** (2 tests, 1 hour):
- Cover scanner reunification logic
- Complement golden corpus with multi-directory tests

**Skip GC-16** (mojibake):
- Non-deterministic, hard to test reliably
- If encoding issues appear in real use, handle case-by-case

---

### 4.2 For Post-V3 Backlog

Add to end of `TDD_TODO_V3.md`:

```markdown
## 0.8 Golden corpus backlog (post-V3 canonicalization)

The following scenarios are deferred until artist/work canonicalization is implemented
(per TDD_TODO_V3.md section 0.4, lines 68-77):

### Canonicalization-dependent scenarios

- [ ] **GC-12: Featured artist normalization**
  - Test: "feat." ⇔ "ft" ⇔ "featuring" in match keys
  - Requires: Collaboration marker canonicalization
  - Invariant: Same artist credit → same match_key_artist

- [ ] **GC-6: Work nickname aliases (classical)**
  - Test: "Eroica" ⇔ "Symphony No. 3 in E-flat Major, Op. 55"
  - Requires: Work alias canonicalization system
  - Invariant: Nickname and formal title → same match_key_work

- [ ] **GC-7: Ensemble name abbreviations**
  - Test: "LSO" ⇔ "London Symphony Orchestra"
  - Requires: Artist alias/abbreviation canonicalization
  - Invariant: Full name and abbreviation → same match_key_artist

### Implementation note

These scenarios are **deterministic and ready to add** once the `match_key_*`
canonicalization system (display vs. match separation) is implemented. The test
data is in `CANONICALIZATION_AUDIT.md` section 2.2.
```

---

## 5. V3 Definition of Done - Checklist

Per TDD_TODO_V3.md, V3 is done when:

1. ✅ **Core invariants gate is green** (golden corpus + identity + canonicalization + idempotency)
   - Current: 18 scenarios
   - After Phase 1: **26 scenarios** (all deterministic)
   - Canonicalization: Deferred per line 68-77 (match_key vs display)

2. ⚙️ **Discogs and MB integrated** with stable candidate canonicalization
   - Fixture providers exist
   - Ranking is stable

3. ⚙️ **Apply writes tags correctly** for FLAC/MP3/M4A
   - Provenance tags included

4. ⚙️ **Move/rename behavior correct** across multi-disc, compilations, collisions
   - Tested in golden corpus

5. ⚙️ **Big 10 suite is green and reruns are clean**
   - Idempotency verified

**With Phase 1 scenarios added, V3 corpus coverage is complete for deterministic cases.**

---

**End of Audit**

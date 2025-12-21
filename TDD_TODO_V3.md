# TDD TODO V3 — Feature Delivery (Core Solid)

V3 ships real-world functionality (Discogs + MusicBrainz, real tagging, real moves) while **locking core invariants**
(identity, canonicalization, layout stability, idempotency) so the tool holds up on messy libraries.

**Related Documents:**
- [CANONICALIZATION_AUDIT.md](CANONICALIZATION_AUDIT.md) - Full determinism analysis of proposed golden corpus scenarios
- [GOLDEN_CORPUS_ROADMAP.md](GOLDEN_CORPUS_ROADMAP.md) - Quick reference for implementation phases
- [TEST_AUDIT.md](TEST_AUDIT.md) - Original test coverage audit and gap analysis

---

## 0) Core invariants gate — Golden corpus (must be green early in V3)

This section freezes *core correctness* for identity, canonicalization, layout, tagging, and idempotency.
It exists to prevent silent regressions such as rematches, drift, or unstable paths while adding
providers and real tagging.

V3 **cannot be declared done** unless this section is green.

### 0.1 Golden corpus v1 — scope and purpose

The golden corpus is a **pre-injected, deterministic mini-library** processed end-to-end and compared
against frozen expected outputs. It serves as the invariance gate for real-world behavior.

**Initial corpus scenarios (minimum viable):**
- Standard album (10–12 tracks)
- Multi-disc album (2 discs, disc numbers required)
- Compilation (Various Artists)
- Name variants (AC/DC, Björk, Alt-J, smart quotes/dashes)
- Classical (composer / work / movements)
- Extras (cover.jpg, booklet.pdf, cue/log)
- Single-track release
- Mixed media (audio + video extra)
- Classical multi-composer compilation
- Long titles requiring truncation
- Renamed folder mid-processing
- Missing middle tracks
- Case-only rename on case-insensitive filesystems
- Interrupted apply (half-moved files)

The corpus must stay **small and high-signal**. New scenarios are added only when a real bug is found.

### 0.2 Corpus construction (deterministic inputs)

- [x] Add `tests/golden/corpus_builder.py`
  - Builds small deterministic audio files (fixed seed, fixed duration)
  - Uses existing `create_test_audio_file` helpers where possible
  - Supports disc numbers, track numbers, and baseline tags
  - Generates extras (jpg, pdf, cue, log)
- [x] Audio generation must be reproducible across runs and machines

### 0.3 Fixture providers (no network)

- [x] For each golden scenario, define **fixture provider responses**:
  - Discogs candidates (JSON)
  - MusicBrainz candidates (JSON)
- [x] Provider order, IDs, and fields must be stable
- [x] Golden corpus runs must not perform network access

### 0.4 Frozen invariants (expected outputs)

For each scenario, freeze the following **expected artifacts**:

#### Identity invariants
- Stable `dir_id` across:
  - file order changes
  - mtime changes
  - path renames
- Non-audio extras do not affect identity
- Empty-audio directories are handled deterministically (skip or explicit error; not treated as a normal album)

#### Canonicalization invariants
- Introduce explicit separation:
  - `display_*` (human-readable, diacritics preserved)
  - `match_key_*` (aggressive equivalence for matching/caching)
- Known variants share identical **match keys**:
  - Björk ⇔ Bjork (match key only; display preserves Björk)
  - AC/DC with slash variants (`/`, `／`, etc.)
  - smart quotes/dashes
  - collaboration markers normalized consistently (`feat`, `ft`, `featuring`, `with`, `w/`, `f.`, `x`, `pres.`)
  - comma-name equivalence in match keys (`Beatles, The` ⇔ `The Beatles`)
- Display strings preserve diacritics and human-readable form

#### Planner / layout invariants
- Sanitized, stable destination paths
- Stable track + disc numbering rules
- Collision behavior frozen (fail or deterministic suffixing)

#### Tagging invariants
- Canonical tag model → file tags match expected values
- Overwrite policy respected
- Provenance tags present where applicable (MBID / Discogs ID)

#### Idempotency invariants
- Second run produces **zero operations**
- No rematch prompts for resolved items
- Plan hash stable if inputs unchanged

### 0.5 Snapshot format and storage

- [x] Store expected outputs as **canonical JSON** (sorted keys, stable ordering):
  - `expected_layout.json` (output paths per logical track)
  - `expected_tags.json` (read back from files after apply)
  - `expected_state.json` (dir_id, resolution status, pinned IDs)
  - `expected_plan.json` (optional; only if plan stability is required)
- [x] Snapshots must be human-readable and reviewable in diffs

### 0.6 Golden corpus runner (integration test)

- [x] Add `tests/integration/test_golden_corpus.py`
  - Copies scenario input into a temp library
  - Runs scan → resolve → apply using fixture providers
  - Compares actual outputs against frozen snapshots
  - Re-runs pipeline to assert idempotency (no-op second run)
  - Mutates inputs (rename/path + tag variants) and asserts identity + canonicalization invariants still hold

### 0.7 Controlled updates

- [ ] Add `--regen-golden` (or a helper script) to intentionally regenerate snapshots
- [ ] Snapshot changes require an explicit justification (bug fix or deliberate behavior change)

### 0.8 Golden corpus expansion for V3 (from CANONICALIZATION_AUDIT.md)

**Current corpus:** 22 scenarios (includes 2 canonicalization-gated scenarios slated for removal)
**V3 target:** 26 scenarios (+6 new deterministic scenarios)

**Status summary:**
- ✅ **6 scenarios already added:** opus_normalization, conductor_vs_performer, multi_performer_work, catalog_variants, partial_opera, partial_tags
- 🎯 **6 scenarios ready to add** (Phase 1, ~3 hours total) - see GOLDEN_CORPUS_ROADMAP.md
- ⚠️ **2 scenarios deferred** (require canonicalization system) - see below
- 🔧 **2 scenarios for integration tests** (not golden corpus) - see below
- ❌ **1 scenario skipped** (non-deterministic)

**Phase 1: Add these 8 deterministic scenarios for V3:**
- [x] GC-5 Partial opera excerpts (non-contiguous Act II + IV)
- [x] GC-10 Partial tags (missing album/artist, infer from siblings)
- [ ] GC-11 Duplicate files (same fingerprint_id, different filenames)
- [ ] GC-13 Remaster vs original (1973 vs 2023 release years)
- [ ] GC-14 Non-audio-only directory (only .jpg/.cue/.log, no audio)
- [ ] GC-15 Hidden track (track 0 pregap + track 99 secret)
- [ ] GC-17 Unicode normalization (NFD vs NFC: "Café" different encodings)
- [ ] GC-18 Invalid year tags ("0000" or "UNKNOWN")

**Implementation:** See CANONICALIZATION_AUDIT.md section 3.2 for full specs and GOLDEN_CORPUS_ROADMAP.md for steps.

**Deferred (requires canonicalization system):**
- [ ] work_nickname (work alias canonicalization)
- [ ] ensemble_variants (artist abbreviation canonicalization)

**Integration tests instead (scanner/merge behavior; not golden corpus):**
- [ ] GC-8 Orphaned track reunification (requires multi-path setup)
- [ ] GC-9 Split album across dirs (requires multi-directory setup)

**Explicitly reject (warn/skip) unless policy changes:**
- [ ] GC-16 Mixed encoding tags (mojibake; non-deterministic in JSON stubs)

### Exit criteria (V3 gate)

This section is complete when:
- All golden corpus scenarios pass
- Outputs are identical across reruns
- No provider network access occurs
- Canonicalization, identity, layout, tagging, and idempotency invariants are demonstrably frozen

---

## 1) Provider integration: Discogs

### 1.1 Discogs client basics (Unit)

- [ ] Build `DiscogsClient`:
  - search (release/master)
  - fetch release details (tracklist, artists, labels, year, formats)
- [ ] Unit tests with recorded fixtures:
  - stable ordering for identical inputs
  - handles “no results”, “multiple results”, “rate limited”, “timeouts”
- [ ] Canonicalize Discogs output into internal `ReleaseCandidate`:
  - artist credits → canonicalizer (`match_key` + `display`)
  - stable track numbering + disc inference
  - label/catalog # extraction

### 1.2 Matching heuristics: Discogs (Integration)

- [ ] E2E: singleton dir → Discogs match (CERTAIN) → plan → apply → tags written
- [ ] E2E: ambiguous results → QUEUED_PROMPT with candidate list + reasons
- [ ] Heuristics tests:
  - duration tolerance windows
  - track-count match scoring
  - fuzzy title normalization (feat variants, punctuation, apostrophes, diacritics)
  - “Various Artists” compilation handling

### 1.3 Discogs: Singles / EP detection (Feature)

- [ ] Test: singleton run identifies Single/EP releases when applicable
- [ ] Test: prevent “single upgraded to album” due to title overlap
- [ ] Implement: candidate boost/penalty based on Discogs format + track count

---

## 2) Provider integration: MusicBrainz (MB)

### 2.1 MB client basics (Unit)

- [ ] Build `MusicBrainzClient`:
  - release search (primary)
  - fetch release (tracks, mediums/discs, relationships if needed)
- [ ] Unit tests with fixtures:
  - multi-medium preserves disc structure
  - handles missing barcodes/dates
  - rate limiting behavior

### 2.2 Matching heuristics: MB (Integration)

- [ ] E2E: multi-disc dir → MB multi-medium release → plan → apply
- [ ] E2E: classical case (composer/work/performers heavy)
- [ ] Scoring tests:
  - prefer exact medium/track count match
  - penalize mismatched disc counts
  - prefer higher track-duration alignment

### 2.3 MB IDs in tags (Feature)

- [ ] Test: write MB Release ID + Recording IDs into tags (per format)
- [ ] Test: rerun does not rematch once MB IDs exist and dir is resolved

---

## 3) Provider fusion: Discogs + MB together

### 3.1 Resolution strategy (Feature)

- [ ] Implement:
  - query MB and Discogs (order configurable)
  - merge candidates into unified ranked list
  - provenance display + reason codes
- [ ] Integration tests:
  - both providers agree → auto-resolve CERTAIN
  - disagree → queue prompt with both sets
  - one provider down → still works with the other

### 3.2 Cache/offline behavior (Feature support)

- [ ] Test: resolved dirs do not re-hit network
- [ ] Test: cache miss triggers exactly one provider fetch per provider per run
- [ ] Offline mode is explicit:
  - [ ] Test: `--offline` forbids network calls
  - [ ] Test: cache-hit works; cache-miss yields deterministic “needs network” outcome

---

## 4) Tagging: actual writing (FLAC + MP3 + M4A)

### 4.1 Tag writing: FLAC/Vorbis (Integration)

- [ ] E2E: apply writes:
  - album, albumartist, artist, title, tracknumber, discnumber
  - date/year, label, catalog#, genre (if present)
  - MB IDs + Discogs IDs
- [ ] Test: preserves unrelated tags unless overwrite policy says otherwise
- [ ] Test: round-trip readback equals canonical tag model

### 4.2 Tag writing: MP3/ID3 (Integration)

- [ ] Same E2E assertions as FLAC with ID3 mapping
- [ ] Test: handles “1/12” track numbers consistently

### 4.3 Tag writing: M4A/MP4 (Integration)

- [ ] Same E2E assertions with MP4 atoms
- [ ] Test: multi-disc numbering uses `disk` correctly

### 4.4 Canonical tag model + mapping (Unit)

- [ ] Unit tests: TagPatch → per-format mapping
- [ ] Unit tests: normalization rules:
  - whitespace collapse
  - artist joining rules
  - diacritics retained in display strings (unless explicitly configured)

---

## 5) Moving/renaming behavior: trustable apply

### 5.1 Destination layout rules (Integration)

- [ ] Define V3 layout targets:
  - Artist/Year - Album/## - Title.ext
  - multi-disc strategy (Disc 1/01… or 1-01…)
  - classical mode (Composer/Work/…)
- [ ] E2E tests:
  - multi-disc box set
  - compilation
  - artist name variants (AC/DC, Björk)

### 5.2 Extras handling (Feature)

- [ ] Policy: keep/move/rename extras (cover.jpg, booklet.pdf, .cue, .log)
- [ ] Tests:
  - cover art follows album
  - extras don’t collide across discs
  - unknown extras handled deterministically (kept or moved to Extras)

### 5.3 Collision policy (Integration)

- [ ] Tests:
  - same destination filename from different sources
  - case-insensitive collisions (Track.flac vs track.flac)
- [ ] Feature behavior: FAIL by default or deterministic suffixing
- [ ] E2E: collision is explained; apply does not partially mutate

### 5.4 Idempotent rerun (Integration)

- [ ] E2E: run twice → no rematches, no moves, no tag drift
- [ ] E2E: manual rename → deterministic repair without re-matching

---

## 6) “Big 10” scenario suite (Integration)

This is the feature acceptance suite that tells you V3 is shippable.

- [ ] Single track + “single” on Discogs and MB
- [ ] Standard album (10–12 tracks)
- [ ] Multi-disc album (2 discs)
- [ ] Box set (multi-disc, repeated track titles, long titles)
- [ ] Compilation (Various Artists)
- [ ] Artist name variants (AC/DC, Björk, Sigur Rós)
- [ ] Classical: composer + work + performers; movement titles
- [ ] Live album with “(Live)” in titles and non-standard track naming
- [ ] Album with hidden track / pregap-like oddities (duration mismatch tolerance)
- [ ] Album with extras: booklet.pdf, cover.jpg, log/cue

Each scenario must assert:
- ranking/provenance makes sense or queues prompt
- chosen match yields correct move layout
- tags correct per format
- rerun clean (no rematches)
- variant edits do not destabilize identity (at least one scenario)

---

# V3 Definition of Done (Updated)

V3 is done when:

1. Core invariants gate is green (golden corpus + identity + canonicalization + idempotency + no-network-on-rerun).
2. Discogs and MB integrated with stable candidate canonicalization and ranking.
3. Apply writes tags correctly for FLAC/MP3/M4A with provider IDs and overwrite policy.
4. Move/rename behavior is correct across multi-disc, compilations, collisions, extras.
5. Big 10 suite is green and reruns are clean.

## V3 Follow-up (post-close)

- [ ] Unplumb legacy app wiring: remove or disable legacy pipeline entrypoints once V3 is green, keeping shared helpers only.

---

## 0.9 Post-V3 golden corpus backlog (from CANONICALIZATION_AUDIT.md)

The following scenarios are **deterministic and ready to add** but require canonicalization
logic that is deferred post-V3 (per section 0.4, lines 68-77: match_key vs display separation).

### Post-V3: Canonicalization-dependent scenarios (3 scenarios)

These test the **match_key canonicalization system** for artist/work aliases and variants:

- [ ] **GC-12: Featured artist normalization**
  - **Test:** "Main Artist feat. Guest" ⇔ "Main Artist ft Guest" ⇔ "Main Artist featuring Guest"
  - **Requires:** Collaboration marker canonicalization (`feat`, `ft`, `featuring`, `with`, `w/`, `f.`, `x`, `pres.`)
  - **Invariant:** Same artist credit → same `match_key_artist` (but different `display_artist`)
  - **Implementation:** 3 tracks with variant featured artist syntax, same fingerprint base, should resolve to same artist
  - **Location:** `tests/golden/corpus_builder.py` scenario #19

- [ ] **GC-6: Work nickname aliases (classical)**
  - **Test:** "Eroica Symphony" ⇔ "Symphony No. 3 in E-flat Major, Op. 55"
  - **Requires:** Work alias canonicalization system
  - **Invariant:** Nickname and formal title → same `match_key_work` (but different `display_work`)
  - **Implementation:** 2 movements with nickname vs. formal title, should resolve to same work
  - **Location:** `tests/golden/corpus_builder.py` scenario #20

- [ ] **GC-7: Ensemble name abbreviations**
  - **Test:** "LSO" ⇔ "London Symphony Orchestra" ⇔ "London SO"
  - **Requires:** Artist alias/abbreviation canonicalization
  - **Invariant:** Full name and abbreviation → same `match_key_artist`
  - **Implementation:** 2 tracks with orchestra name variants, should resolve to same artist
  - **Location:** `tests/golden/corpus_builder.py` scenario #21

**Test data:** See `CANONICALIZATION_AUDIT.md` section 2.2 for full scenario definitions.

**Implementation note:** These scenarios are blocked on the `match_key_*` canonicalization
system (display vs. match separation) described in TDD_TODO_V3.md lines 68-77. They are
**fully deterministic** and can be added once that system exists.

### Post-V3: Integration tests for scanner behavior (2 tests)

These test **scanner reunification logic** across multiple directories (not end-to-end workflow):

- [ ] **GC-8: Orphaned track reunification**
  - **Test:** Track accidentally moved to parent directory, should reunite with siblings
  - **Implementation:** `test_scanner_reunites_orphaned_tracks()` in `test_scanner_edge_cases.py`
  - **Why not golden:** Requires multi-path setup (album in dir, orphan in parent)

- [ ] **GC-9: Split album merge**
  - **Test:** Album split across two directories (interrupted move), scanner should merge
  - **Implementation:** `test_scanner_merges_split_album()` in `test_scanner_edge_cases.py`
  - **Why not golden:** Requires two separate directory structures

**Test data:** See `CANONICALIZATION_AUDIT.md` section 2.3 for full test specs.

### Skipped scenarios (non-deterministic)

- ❌ **GC-16: Mixed encoding tags (UTF-8 + mojibake)**
  - **Reason:** Simulating corrupted encoding in `.meta.json` is unreliable and non-deterministic
  - **Alternative:** Handle real-world encoding issues case-by-case if they appear

---

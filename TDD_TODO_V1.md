# Resonance TDD TODO

## (Final, Determinism-First, Spec-Aligned)

This checklist is ordered for **test-driven development**.
Each section starts with unit tests, then minimal implementation to satisfy them.

The ordering **enforces the Resonance pipeline** and explicitly prevents:

* re-matches across runs,
* accidental filesystem damage,
* architectural drift during refactors.

---

## Global constraints (apply everywhere)

* **Purity boundary**

  * Scanner, Identifier, Planner are **pure**
  * No filesystem mutation, no tag writes, no persistence writes
  * Applier is the **only** mutator
* **Identity**

  * All processing is keyed by **`dir_id`** (content-based)
  * Paths are diagnostic only
* **Pinned decisions**

  * Once a directory is `RESOLVED_*`, the pinned release is reused
  * No re-search unless explicitly invalidated
* **Plan-first**

  * Applier executes a **stored Plan artifact**
  * Applier must never recompute decisions
* **Default safety**

  * Default non-audio handling: `MOVE_WITH_ALBUM`
  * Deleting non-audio requires explicit opt-in

---

## 0) Test scaffolding + fixtures (Unit / Integration)

**Goal:** deterministic test inputs and reproducible plans.

* [x] Tempdir / in-memory FS helpers:

  * audio stubs (stable fingerprint id, duration, size)
  * non-audio stubs (jpg, pdf, cue, log, txt)
* [x] Deterministic ordering helpers (`sorted_paths`, stable tie-break)
* [x] Snapshot helper for Plan JSON (stable ordering + formatting)
* [x] Golden scenario fixtures:

  * [x] `pop_certain`
  * [x] `pop_probable`
  * [x] `compilation`
  * [x] `classical_single_composer`
  * [x] `classical_mixed_composer`
  * [x] `mixed_release_in_one_dir`
  * [x] `non_audio_present`
  * [x] `target_exists_conflict`

---

## 1) Stable Directory Identity + Signature (Unit)

**Goal:** identical content → identical identity, regardless of path or run.

* [x] `dir_signature(audio_files)` is order-independent
* [x] `dir_signature` ignores mtimes and other unstable metadata
* [x] `dir_id(signature)` stable across repeated scans
* [x] Same content in different filesystem paths → same `dir_id`
* [x] Adding/removing an audio file changes `signature_hash`
* [x] Changing audio content (size/fingerprint) changes `signature_hash`
* [x] Non-audio changes do **not** affect `dir_id` (recorded only for diagnostics)

**Invariant:** `dir_id` is strictly content-based.

---

## 2) Canonicalization Policy (Unit)

**Goal:** deterministic keys and deterministic display names—no semantic guesses.

### 2.1 Token normalization (mechanical only)

* [x] `normalize_token()`:

  * Unicode normalization (NFKC)
  * trim + collapse whitespace
  * case-fold
  * normalize joiners (`feat`, `ft`, `with`, `&`, `and`, `/`, `;`)
  * mononyms handled mechanically (no first/last inference)
* [x] No reordering of names
  (`"Beatles, The"` ≠ `"The Beatles"`)
* [x] `split_names()` is deterministic
* [x] `dedupe_names()` collapses equivalent tokens only

**Rule:** normalization produces **comparison keys**, not display names.

---

### 2.2 Canonical mapping store

* [x] Canonicalizer maps `namespace::normalized_key → canonical_display`
* [x] If mapping missing:

  * return original display string
  * use normalized token only for keying
* [x] Canonicalizer never invents equivalences or expansions

---

### 2.3 Short folder name policy

* [x] Define and test “short folder name”:

  * max length enforced (e.g. 60 chars)
  * featuring/with clauses removed **for folder display only**
  * deterministic truncation strategy
* [x] Folder shortening does **not** affect canonical mapping keys

**Invariant:** canonical identity ≠ folder display.

---

## 3) Persistence + Directory State Machine (Unit)

**Goal:** explicit, testable lifecycle; no ad-hoc flags.

### 3.1 DirectoryRecord

* [x] Record keyed by `dir_id`
* [x] Stored fields:

  * `dir_id`
  * `last_seen_path`
  * `signature_hash`
  * `state`
  * pinned release metadata
  * timestamps

### 3.2 States

* [x] `NEW`
* [x] `QUEUED_PROMPT`
* [x] `JAILED`
* [x] `RESOLVED_AUTO`
* [x] `RESOLVED_USER`
* [x] `PLANNED`
* [x] `APPLIED`
* [x] `FAILED`

---

### 3.3 Transitions + determinism rules

* [x] `JAILED` directories are skipped (logic enforced)
* [x] `--unjail` → `JAILED → NEW`
* [x] If `signature_hash` changes:

  * state resets to `NEW`
  * pinned release cleared (unless policy says otherwise)

**Critical invariants**

* [x] Path changes do **not** create new records
* [x] Pinned decisions are reused verbatim
* [x] If `RESOLVED_*` and unchanged:

  * Identifier must **not** query providers again (enforced by DirectoryStateStore)

This section is the **primary defense against re-matches**.

---

## 4) Scanner (Unit)

**Goal:** discovery only; zero side effects.

* [x] Enumerates directories containing audio files
* [x] Skips empty / non-audio-only directories
* [x] Deterministic ordering of directories and files
* [x] Produces `DirectoryBatch`:

  * audio_files
  * non_audio_files
  * `dir_id`
  * `signature_hash`
  * diagnostics only

**Invariant:** Scanner does not touch persistence.

---

## 5) Identifier: Evidence + Candidate Scoring (Unit)

**Goal:** deterministic candidate list + confidence tier.

### 5.1 Evidence extraction

* [x] Per-track:

  * fingerprint id
  * duration
  * existing tags (weak signal)
* [x] Directory-level:

  * track count
  * total duration
  * stable track ordering

---

### 5.2 Provider scoring (MB + Discogs)

* [x] Score by:

  * fingerprint coverage
  * track count match
  * duration fit
  * optional year penalty
* [x] Merge providers deterministically:

  * score desc
  * provider priority
  * release_id lexicographic tie-break

---

### 5.3 Multi-release detection

* [x] If ≥2 incompatible releases exceed minimum support:

  * tier → `UNSURE`
  * reasons include conflict details

**Rule must be quantitative and tested**
(e.g. coverage ≥ 0.30 for two releases) ✅ Implemented and tested.

---

### 5.4 Confidence tiers

* [x] Explicit thresholds (versioned):

  * `CERTAIN`
  * `PROBABLE`
  * `UNSURE`
* [x] Auto-select **only** when `CERTAIN`
* [x] Ambiguous margin → `UNSURE`
* [x] Output includes:

  * ordered candidates
  * tier
  * reasons
  * scoring_version

**Invariant:** same inputs → same result, byte-for-byte. ✅ Enforced via deterministic tie-breaking.

---

## 6) Resolver: Prompt / Jail / Pin (Unit)

**Goal:** uncertainty handled explicitly and safely.

* [x] Non-interactive:

  * `PROBABLE` / `UNSURE` → `QUEUED_PROMPT`
  * no prompting
* [ ] Interactive:

  * full track list with durations
  * candidate list with scores + reasons
  * select candidate → `RESOLVED_USER`
  * manual `mb:` / `dg:` accepted
* [x] Skip:

  * state → `JAILED`
  * reason + timestamp persisted
* [x] `CERTAIN`:

  * auto-pin → `RESOLVED_AUTO`

**Persist `resolution_type`: AUTO | USER**

**Status:** Core resolver logic complete (12/12 tests passing). Interactive prompt handler deferred to Phase 10.

---

## 7) Planner: Deterministic Plan Artifact (Unit)

**Goal:** pure, reproducible Plan JSON.

* [x] Planner runs only for `RESOLVED_*`
* [x] Uses pinned release only
* [x] Stable file ordering
* [x] Byte-identical plan for identical inputs

---

### 7.1 Path rules

* [x] Default: `Artist/Album`
* [x] Compilation: `Various Artists/Album`
* [ ] Classical v1:

  * single composer → `Composer/Album`
  * else → `PerformerOrAlbumArtist/Album`
* [ ] Short-name canonicalization applied

---

### 7.2 Track filenames

* [x] Disc/track padding defined (basic 2-digit format)
* [ ] Safe character policy deterministic
* [ ] No random capitalization or punctuation

---

### 7.3 Atomicity + conflicts

* [x] Directory never split (single destination path)
* [x] Multi-release UNSURE → planner refuses (via state check)
* [ ] Conflict strategy encoded in plan

---

### 7.4 Non-audio policy

* [x] Explicitly encoded in Plan
* [x] Default `MOVE_WITH_ALBUM`
* [x] Delete only if explicitly configured

**Status:** Core planner complete (9/9 tests passing). Classical path rules, advanced filename formatting, and conflict resolution deferred to later enhancement.

---

## 8) Enricher: Tag Patch (Unit)

**Goal:** conservative, diff-based tagging.

* [x] Produces `tag_patch` (set/unset)
* [ ] Writes provenance tags when enabled
* [x] Tagging allowed only when:

  * `RESOLVED_AUTO` (default, equivalent to tier == `CERTAIN`)
* [ ] No overwrites when not confident

**Status:** Core enricher complete (4/4 tests passing). Provenance tags and overwrite-aware diffs deferred.

---

## 9) Applier: Transactional Execution (Integration)

**Goal:** safe, boring, reversible.

* [x] Consumes stored Plan only
* [x] Preflight checks
* [x] Transaction order:

  * move
  * tag
  * cleanup
* [x] Source dir deleted only when empty + success
* [x] Idempotent: re-apply is no-op
* [x] Non-audio behavior matches Plan

**Status:** Core applier complete (6/6 integration tests passing). Conflict strategies and tag rollback deferred.

---

## 10) Daemon + Prompt CLI (Integration)

**Goal:** unattended operation without risk.

* [x] Daemon:

  * scan + identify
  * auto-pin `CERTAIN`
  * queue others
  * never prompt
* [x] `prompt-uncertain`:

  * resolves queue
  * allows manual IDs
  * allows jail
* [x] `--unjail` supported

**Status:** Phase 10 orchestration scaffolding in place (integration tests for daemon ordering/pinning/queueing and prompt/unjail behaviors).

---

## 11) Prescan CLI (Integration)

**Goal:** improve canonical mappings only.

* [x] Scans library
* [x] Records observed raw names → mapping inventory
* [x] No release pinning
* [x] Skips non-audio-only dirs

**Status:** Prescan integration tests complete (4/4). Conflict resolution deterministic.

---

## 12) Audit, Doctor, Rollback (Integration)

**Goal:** operational safety and debuggability.

* [x] `audit --dir-id` shows:

  * state
  * signature
  * pinned release
  * last plan
  * last apply summary
* [x] `doctor` validates invariants
* [x] Rollback:

  * filesystem moves reversible
  * tag rollback optional later

**Status:** Phase 12 core checks complete (3/3 integration tests passing). Tag rollback deferred.

---

### Final note (important)

This TODO is **frozen**.
If code or tests disagree with it, the code/tests must change—**not** the TODO—unless you explicitly amend the architecture.

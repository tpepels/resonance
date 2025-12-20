# Resonance TDD TODO v2 (Production Hardening + Full Requirements)

This checklist extends the frozen foundation TODO. It focuses on **real-world correctness**, **operational safety**, and **end-user completeness**, while preserving:

* determinism (same inputs → same outputs),
* dir_id identity,
* no re-matches,
* plan-first apply,
* auditability/rollback.

Each section: **tests first**, then minimal implementation.

---

## Global constraints (still apply everywhere)

* Purity boundary unchanged:

  * Scanner / Identifier / Planner are pure (no FS mutation, no tag writes, no store writes)
  * Applier is the only mutator
* Identity:

  * all state keyed by `dir_id`
  * paths are diagnostic only
* Determinism:

  * all traversal and presentation is sorted deterministically
  * cache keys and serialization are stable
* No re-matches invariant remains the top rule
* Default dry-run; mutation requires explicit `apply`

---

## 13) Phase 10 hardening (orchestration determinism locks)

**Goal:** make Phase 10 tests robust to future scoring adjustments and eliminate accidental dependencies.

### 13.1 Evidence duration correctness (Integration)

* [x] Test: evidence builder sums per-track durations deterministically (integer seconds)
* [x] Test: total duration influences scoring consistently (no platform float drift)
* [x] Implement: `_evidence_from_files` sets `total_duration_seconds = sum(...)`

### 13.2 Daemon multi-batch ordering (Integration)

* [x] Test: daemon consumes batches in reverse order but processes by sorted `dir_id`
* [x] Test: provider calls occur in deterministic `dir_id` order
* [x] Implement: enforce order at daemon orchestration boundary (not inside providers)

### 13.3 Prompt decoupled from scanner (Integration)

* [x] Test: prompt-uncertain does not instantiate Scanner and still displays stable track list
* [x] Implement: deterministic glob + metadata read for `last_seen_path`, sorted by path

### 13.4 Queue test robustness (Integration)

* [x] Test: daemon queues PROBABLE/UNSURE via forced low-evidence path (not threshold-dependent)
* [x] Implement: test provider stub supports “force tier” scenarios (e.g., two close candidates)

**Status:** Phase 13 hardening complete (Phase 10 determinism locks enforced).

---

## 14) Real tag writing backend (Mutagen) + deterministic readback

**Goal:** replace `.meta.json` test-only tagging with a real backend, without compromising determinism or rollback.

### 14.1 TagWriter abstraction (Unit)

* [x] Test: TagWriter interface supports `read_tags(path)` and `write_tags(path, patch)` (or equivalent)
* [x] Test: applying the same patch twice is idempotent (no additional changes)
* [x] Implement: `TagWriter` protocol + DTOs (`TagSnapshot`, `TagWriteResult`)

### 14.2 Mutagen backend (Integration)

* [x] Fixture: FLAC baseline tagging corpus with deterministic tag state
* [x] Test: apply TagPatch → tags updated as expected
* [x] Test: readback after write matches TagPatch exactly
* [x] Test: unsupported format yields stable, explicit error (not partial write)
* [x] Implement: `MutagenTagWriter` (FLAC first; MP3/M4A later)

### 14.3 Failure semantics (Integration)

* [x] Test: tag write failure causes apply to FAIL and triggers rollback of filesystem moves
* [x] Test: audit/rollback records include tagging errors deterministically
* [x] Implement: applier treats TagWriter failures as transactional failure points

### 14.4 Sidecar backend retained (Unit/Integration)

* [x] Test: `.meta.json` backend remains available for tests and continues to be deterministic
* [x] Implement: backend registry/selection by settings

**Status:** Backend selection wired and covered (CLI/env/config precedence + invalid backend + TagWriter injection).

---

## 15) Provenance tags + overwrite-aware diffs

**Goal:** safe tagging in libraries that already have metadata; preserve user edits and record what Resonance changed.

### 15.1 Provenance schema (Unit)

* [ ] Test: provenance tags include tool name, version, date, plan hash, pinned release id
* [ ] Test: provenance tags are deterministic (no local time; use UTC ISO8601 or fixed test clock)
* [ ] Implement: `Provenance` object and TagPatch augmentation

### 15.2 Overwrite policy (Unit)

* [ ] Test: when overwrite disabled, existing non-empty tags are not overwritten
* [ ] Test: when overwrite enabled, overwrites are recorded in provenance
* [ ] Test: per-field policies supported (e.g., overwrite title but not artist)
* [ ] Implement: overwrite-aware TagPatch generation and application rules

### 15.3 Tag rollback (Integration, optional but recommended)

* [ ] Test: apply records persist a “before” tag snapshot when real writer enabled
* [ ] Test: rollback restores pre-apply tag snapshot (formats supported)
* [ ] Implement: store tag snapshots in apply record; rollback writes them back

---

## 16) Planner completeness: classical paths + filename sanitation + conflict strategy

**Goal:** make the planner output production-quality paths/filenames while remaining pure and deterministic.

### 16.1 Classical v1 path rules (Unit)

* [ ] Test: single composer → `Composer/Album`
* [ ] Test: mixed composer → `PerformerOrAlbumArtist/Album`
* [ ] Test: canonicalization applied to folder display names only (not keys)
* [ ] Implement: classical folder artist selector (pure)

### 16.2 Safe filename policy (Unit)

* [ ] Test: deterministic sanitization of forbidden chars (`/ \ : * ? " < > |`)
* [ ] Test: whitespace collapse and trimming is deterministic
* [ ] Test: reserved Windows names handled deterministically (CON, PRN, etc.)
* [ ] Implement: `sanitize_filename()` pure function

### 16.3 Deterministic conflict strategy encoded in plan (Unit/Integration)

* [ ] Test: plan encodes conflict action: FAIL vs SKIP vs RENAME
* [ ] Test: default is FAIL (safe)
* [ ] Implement: extend Plan schema with conflict policy and applier enforcement

---

## 17) Provider caching hardening (reproducible, versioned, and bounded)

**Goal:** ensure provider results are cached deterministically, reproducibly, and safely (no silent drift).

### 17.1 Cache keys + serialization stability (Unit)

* [ ] Test: provider cache key includes provider name + request type + normalized query + version
* [ ] Test: cached payload serialization is stable (sorted keys; stable lists)
* [ ] Implement: canonical JSON serialization for provider payloads

### 17.2 Cache invalidation versioning (Unit)

* [ ] Test: bumping provider client version invalidates cache deterministically
* [ ] Test: settings_hash changes do not invalidate provider caches unless relevant
* [ ] Implement: cache schema includes `client_version`

### 17.3 Rate limiting / backoff (Integration)

* [ ] Test: daemon respects rate limiting deterministically (no jitter randomness)
* [ ] Implement: deterministic backoff schedule or fixed pacing per provider

### 17.4 Offline mode (Integration)

* [ ] Test: `--offline` uses cache only and never calls provider network
* [ ] Implement: provider client rejects network calls in offline mode with stable message

---

## 18) CLI completeness + UX determinism

**Goal:** deliver a complete CLI surface that is stable, scriptable, and safe.

### 18.1 `scan` / `identify` / `plan` / `apply` commands (Integration)

* [ ] Test: each command emits machine-readable JSON (`--json`) deterministically
* [ ] Test: default output remains human-readable but stable
* [ ] Implement: output sinks + JSON schema versioning

### 18.2 Prompt CLI ergonomics (Integration)

* [ ] Test: prompt shows track list with durations (stable formatting)
* [ ] Test: candidate list includes scores + reasons (stable ordering)
* [ ] Test: supports “jail” decision explicitly
* [ ] Implement: prompt flows + validation (1-based indexing, manual IDs)

### 18.3 Exit codes + error taxonomy (Unit/Integration)

* [ ] Test: consistent exit codes per failure class (validation vs runtime vs IO)
* [ ] Implement: central `ResonanceError` hierarchy + mapping to exit codes

---

## 19) Settings & settings_hash correctness

**Goal:** ensure that changes in relevant settings correctly invalidate planning/identification without false positives.

### 19.1 settings_hash composition (Unit)

* [ ] Test: only relevant settings affect `settings_hash` for identify/plan stages
* [ ] Test: irrelevant settings changes do not cause re-identification
* [ ] Implement: explicit “relevance sets” per stage

### 19.2 Migration/backward compatibility (Unit)

* [ ] Test: older state DB can be migrated forward deterministically
* [ ] Implement: SQLite migrations with explicit version table

---

## 20) Filesystem edge cases + safety guarantees

**Goal:** handle real library conditions safely and deterministically.

### 20.1 Symlinks and special files (Integration)

* [ ] Test: symlinks either skipped or handled per policy deterministically
* [ ] Test: device files / weird permissions produce stable failures
* [ ] Implement: scanner policy for special files

### 20.2 Case-insensitive collisions (Integration)

* [ ] Test: `Track.flac` vs `track.flac` collision detected on case-insensitive target
* [ ] Implement: preflight collision detection normalizes case where configured

### 20.3 Cross-device moves (Integration)

* [ ] Test: apply works across filesystem boundaries (copy+fsync+rename strategy) OR fails with stable message
* [ ] Implement: robust move strategy with deterministic cleanup

---

## 21) Observability: audit richness + stability reports

**Goal:** make audits actionable and deterministic for debugging and trust.

### 21.1 Audit includes last plan + last apply (Integration)

* [ ] Test: audit reports plan hash/version and last apply status/summary
* [ ] Implement: audit assembles data from store artifacts only

### 21.2 Determinism/stability report (Integration)

* [ ] Test: “stability report” compares two runs and shows no differences
* [ ] Implement: report generator consuming stored artifacts (no recomputation)

---

## 22) Packaging / distribution / operational readiness

**Goal:** ensure Resonance is installable, runnable, and safe in real environments.

* [ ] Test: CLI entrypoints work in isolated venv (smoke)
* [ ] Test: default config location discovery is deterministic
* [ ] Implement: `resonance doctor` includes environment sanity checks

---

## Definition of Done (v2)

Resonance meets “full requirements” when:

1. Real tag writing is supported for at least FLAC with idempotency and safe failure handling.
2. Provenance tags and overwrite policy prevent accidental metadata destruction.
3. Planner produces sanitized, stable paths and filenames (including classical v1 rules).
4. Provider caching is reproducible, versioned, and supports offline mode.
5. CLI outputs are deterministic and scriptable (`--json`).
6. Doctor/audit/rollback provide sufficient operational safety for unattended daemon runs.

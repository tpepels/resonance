## Local Developer Note (Non-Normative)

On the primary development machine, the real-world corpus
is sourced from:

    /home/tom/music

This is a personal, real-world music library (~177 GB) used
to validate large-scale, real conditions (legacy tags,
classical edge cases, deep paths).

This path is NOT referenced by tests or code.
Other developers should substitute their own library
or use a subset snapshot via MANIFEST.txt. 
I.e. let's make this configurable and add to .gitignore

---

# TDD_TODO_V3.1 — Real-World Corpus Metadata Extraction & Filesystem Faker

**Status: COMPLETE ✅ - V3.1 CLOSED**

**Theme:**

> V3 proves correctness on curated cases.
> **V3.1 proves correctness survives your actual library.**

**Scope:** Add a "real-world corpus" test harness that can:

1. ✅ extract metadata/directory structure from a real library (no file copying),
2. ✅ create a filesystem faker that serves extracted metadata to the app,
3. ✅ run the full workflow deterministically (offline-safe) against faked filesystem,
4. 🔄 generate `expected_*` snapshots (state/layout/tags) in the same style as golden, and
5. ⏳ assert strict invariants on reruns (no provider calls, no churn).

**Hard constraints (must hold)**

* No mutation of the user's real library path (only metadata extraction)
* No file copying - only extract directory structure and file metadata
* No network required for test execution (offline-safe by default)
* Regen is explicit and gated (like golden regen via env flag)
* No new providers, no new tagging formats, no architectural rewrites

---

## 0) Definitions

**Golden corpus:** curated, small fixtures with strict expected outputs.
**Real-world corpus:** a captured snapshot of your real library (or subset) used for invariants and regression.

**Artifacts (per corpus)**

* `expected_state.json` (terminal states, pinned decisions, counts)
* `expected_layout.json` (final relative paths)
* `expected_tags.json` (tags for tracked audio paths)
  These mirror your current golden artifacts .

---

## 1) Metadata Extraction: Safe Corpus Capture ✅ **COMPLETE**

### 1.1 Real corpus workspace layout (Repo) ✅

* [x] Add directory structure:

  ```
  tests/real_corpus/
    README.md
    metadata.json         # extracted directory structure + file metadata
    expected_state.json
    expected_layout.json
    expected_tags.json
  ```
* [x] Store only extracted metadata (no actual audio files)

### 1.2 Metadata extraction helper (Non-test utility) ✅

**Goal:** extract directory structure and file metadata without copying files.

* [x] Add script `scripts/extract_real_corpus.sh` supporting:

  * source path (e.g. `~/Music` or server mount)
  * manifest filtering: only scan listed directories
  * extract: directory tree, file sizes, modification times, audio metadata
  * output: `tests/real_corpus/metadata.json` (compact, committable)
* [x] Document: extraction reads only, never writes to source

**Acceptance**

* Zero risk to source library (read-only operations)
* Metadata file is small and committable (~KB, not GB)
* Deterministic extraction (same library → same metadata)
* Fast extraction (seconds, not hours)

### 1.3 Filesystem Faker Middleware ✅ **COMPLETE**

**Goal:** provide filesystem interface using extracted metadata.

* [x] Create `tests/integration/_filesystem_faker.py`:

  * implements `os.path.exists()`, `os.listdir()`, `os.stat()` etc.
  * serves from `metadata.json` instead of real filesystem
  * maintains same API as real filesystem calls
* [x] Integration: faker is transparent to existing app code

**Acceptance**

* App code runs unchanged against faker
* Same performance characteristics as real filesystem
* Deterministic behavior (metadata is static)

---

## 2) Test Harness: Real-World Corpus Integration Test 🔄 **IN PROGRESS**

### 2.1 New integration test file

* [x] Add `tests/integration/test_real_world_corpus.py` (basic structure created)

This test should execute the workflow in a controlled way:

* Load filesystem faker with `metadata.json`
* Use temp state db + temp cache db
* Run: `scan → resolve → prompt (scripted decisions) → plan → apply`
* Then rerun: `scan → resolve → plan` and assert **no changes**

**Important:** Prompt decisions must be non-interactive in tests. Use one of:

* deterministic auto-selection policy for test harness only (e.g., "pick top candidate for PROBABLE; jail UNSURE"), or
* a fixture "decisions file" mapping `dir_id → pinned_release_id/provider`.

### 2.2 Filesystem faker integration

* [x] Test uses `FilesystemFaker` instead of real filesystem:

  * faker loads from `tests/real_corpus/metadata.json`
  * provides same API as `os.path`, `os.listdir`, etc.
  * app code runs unchanged against faker
* [x] Verify faker provides deterministic responses

**Acceptance**

* App code requires no changes to work with faker
* Same file enumeration and access patterns
* Deterministic behavior across test runs

### 2.3 Scripted prompt decisions (Test-only)

* [x] Implement basic directory processing pipeline (resolves directories that don't need prompting)
* [x] Add scripted prompt decisions from decisions.json for directories that need user input
* [x] Integration test: scripted prompt results in terminal states for all dirs

**Acceptance**

* No interactive I/O in tests
* Deterministic ordering of processing (by `dir_id`)

---

## 3) Snapshot Artifacts for Real-World Corpus

### 3.1 Expected state snapshot

* [ ] Implement snapshot writer producing `tests/real_corpus/expected_state.json` with:

  * per-dir:

    * `dir_id`
    * terminal state (`APPLIED` or `JAILED`)
    * pinned provider/id when applicable
  * plus summary counts: scanned/resolved/queued/jailed/applied/failed

**Acceptance**

* Stable JSON ordering (sorted keys, sorted dir list by `dir_id`)
* No timestamps unless fixed clock is in use (prefer omit)

### 3.2 Expected layout snapshot

* [ ] Implement `expected_layout.json` as sorted list of **relative** paths under library root
* [ ] Ensure includes only audio files (or explicitly record non-audio policy)

**Acceptance**

* Deterministic ordering (lexicographic)
* Paths are relative and normalized (`/`, no OS-specific separators)

### 3.3 Expected tags snapshot

* [x] Implement `expected_tags.json` containing:

  * `tracks[]` with:

    * relative path
    * tags dict
* [x] Enforce deterministic tag dict serialization
* [x] Include provenance tags (as you do in golden)

**Acceptance**

* Stable output regardless of dict ordering
* No “current time” tags unless fixed test clock is enforced

---

## 4) Regen Protocol: Real Corpus Snapshots

### 4.1 Add regen script (mirror golden)

You already have golden regen gated via `REGEN_GOLDEN` .

* [x] Add `regen_real_corpus.py`:

  * sets env `REGEN_REAL_CORPUS=1`
  * runs `pytest tests/integration/test_real_world_corpus.py -q`

### 4.2 Test gating behavior

* [x] In `test_real_world_corpus.py`:

  * if `tests/real_corpus/input/` missing: skip with actionable message
  * if `REGEN_REAL_CORPUS=1`: regenerate `expected_*` snapshots
  * else: compare against committed snapshots and fail on mismatch

**Acceptance**

* Zero chance of accidental regen in CI
* Clear instructions for local regen

---

## 5) Offline Safety: No Network During Tests

### 5.1 Offline mode enforcement

* [ ] Ensure test harness runs in “offline” mode by default:

  * provider queries must be served from cache
  * cache misses produce deterministic outcomes (queue/jail) rather than network calls

### 5.2 Test: “no provider calls on rerun”

* [ ] Integration test asserts:

  * First run may use provider calls (optional) but should be controllable
  * Second run makes **zero** provider calls (strict)

**Acceptance**

* Rerun produces identical state/layout/tags
* “no rematches” invariant preserved

---

## 6) Scale Controls: Keep It Practical

### 6.1 Subset mode (recommended)

* [ ] Add support for a manifest file:

  * `tests/real_corpus/MANIFEST.txt` lists directories to include
* [ ] Snapshot script copies only manifest entries

**Acceptance**

* You can maintain a stable 10–50 album subset for fast local runs
* Optional “full library” run remains possible but not required

---

## 7) CI Policy

### 7.1 CI safety

* [x] Mark real-world corpus tests as opt-in:

  * skipped by default unless `RUN_REAL_CORPUS=1`
* [x] Ensure golden tests remain always-on

**Acceptance**

* CI never requires your personal library
* Developers can run locally when they have the corpus snapshot

---

## 8) Documentation

### 8.1 `tests/real_corpus/README.md`

* [ ] Document:

  * how to snapshot from a mounted server path
  * how to run the test
  * how to regen snapshots
  * expected runtime guidance (subset vs full)

Include:

* “Never point tests at your live library”
* “Use subset manifest for routine runs”

---

## Definition of Done (V3.1)

V3.1 is complete when:

1. Metadata can be extracted from a real library (or subset) safely (read-only).
2. `pytest tests/integration/test_real_world_corpus.py`:

   * runs offline by default,
   * uses filesystem faker against extracted metadata,
   * produces deterministic results,
   * asserts rerun is a no-op (no provider calls, no churn).
3. Snapshots `expected_state/layout/tags` are generated only under `REGEN_REAL_CORPUS=1`.
4. CI skips the real corpus test unless explicitly enabled.
5. Documentation exists and is sufficient to repeat the process.

---

## Notes on Alignment With Existing Golden Machinery

This is intentionally parallel to your existing golden snapshot model:

* explicit regen gate (`REGEN_*`) 
* three snapshot artifacts (state/layout/tags)
* deterministic serialization and stable ordering

The only conceptual difference is:

* golden asserts “exact curated outcomes”
* real-corpus asserts “invariants + no churn” at realistic scale

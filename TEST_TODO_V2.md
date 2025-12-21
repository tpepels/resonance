Below is an **audit report of the tests**, focused on **actionable TODOs**. This is a **static audit** (structure + brittleness + gap analysis).

---

# Resonance Test Suite Audit Report (Actionable TODOs)

## Executive summary

Your suite is the right shape for a safety-critical, data-mutating application:

* **36 test files**, ~**337** `test_*` functions defined (pytest’s reported “318 tests” is plausible after parametrization/collection rules).
* Healthy split:

  * Many unit tests for narrow invariants.
  * Integration tests written around real-world cases (classical, multi-artist, name variants).
* The main risks are **fixture drift**, **brittle mocking**, and **filesystem realism** (especially with unsafe characters).

If you address the **Top 5 TODOs** below, you will materially improve:

1. suite stability, 2) failure signal quality, and 3) readiness for V3 feature work.

## V2 closure

V2 is closed. Remaining boundary standardization work is explicitly deferred to V3 (see TDD_TODO_V3.md 0.x gate).

## Status update (executed)

* [x] Fixture contract: `disc_number` supported in `create_test_audio_file` and stub metadata reader.
* [x] Fixture test: stub metadata round-trips `disc_number`.
* [x] Mock hardening: private provider patch removed in multi-artist tests; provider mocks use `spec_set`.
* [x] Scoring guard: release auto-select rejects non-numeric scores; order-independent selection uses sorted candidates.
* [x] Sanitization parity: artist-variant suites now use sanitized path helpers; output paths asserted for slash/fullwidth/diacritics.
* [x] Idempotency contracts: apply-twice NOOP + resolved directory avoids provider requery + manual rename treated as no-op.
* [x] Marker hygiene: requires_network/slow are skipped unless explicitly enabled; pycache removed from repo.
* [ ] Integration boundary standardization (provider/tag/move) deferred to V3.


# Quick “Top 10” TODO list you can paste into your tracker

1. Add `disc_number` to `create_test_audio_file()` fixture and persist it in metadata.
2. Add a fixture unit test that verifies `disc_number` round-trips through your loader.
3. Replace private method patching (`_fetch_release_tracks`) with public API patching or a fake client.
4. Change `MagicMock()` provider mocks to `spec_set=` mocks (or fakes) to prevent MagicMock-leak comparisons.
5. Add assertion guards in scoring paths: `score` must be numeric.
6. Create a single helper for album dir creation that enforces production sanitization parity.
7. Update artist-variant tests to assert sanitized output paths (especially slash/fullwidth slash/diacritics).
8. Standardize integration test boundaries (provider/tag/move) to reduce white-box coupling.
9. Add 2–3 idempotency contract integration tests (apply twice, manual rename repair, cache prevents requery).
10. Remove `__pycache__`/`.pyc` from packaged test artifacts and formalize markers (`requires_network`, `slow`).

---

## Findings

### Finding A — Fixture API drift (confirmed breakage)

In `tests/conftest.py`, `create_test_audio_file()`’s inner `_create_file()` signature does **not** accept `disc_number`, but `tests/integration/test_classical.py` calls it with `disc_number=...`.

This is the kind of break that will recur as your TrackInfo model evolves unless you lock the fixture contract down.

**Impact:** immediate failures and ongoing churn whenever metadata fields are added.

---

### Finding B — Mock brittleness via “private method patching” and unspec’d mocks

In `tests/integration/test_multi_artist.py`, the MusicBrainz mock overrides a **private** method:

* `mock_mb_client._fetch_release_tracks = MagicMock(...)`

Private patching ties tests to implementation details and is a common cause of “MagicMock leaks” (e.g., a score becomes a MagicMock and later gets compared to a float).

**Impact:** tests failing for the wrong reason after internal refactors; hard-to-debug failures like `MagicMock >= float`.

---

### Finding C — Filesystem realism and unsafe characters are not consistently handled in tests

Your suite correctly includes artist/title variants (`AC/DC`, fullwidth slash, diacritics), but the way test directories are constructed is not uniformly routed through the same sanitization rules as production layout.

**Impact:** intermittent `FileNotFoundError`, incorrect test expectations, and false positives/negatives about move/layout behavior.

---

### Finding D — Integration tests lean “semi-white-box”

Several integration tests patch objects on the app/pipeline directly (e.g., `app.musicbrainz = MagicMock()`), which is fine, but the boundary is inconsistent across files.

**Impact:** tests are more sensitive than necessary to internal wiring, making them brittle during refactors.

---

### Finding E — Suite hygiene: pycache artifacts in the zip

The zip contains `__pycache__` and `.pyc` artifacts. This is harmless functionally, but it causes noise and increases the chance of confusing diffs, especially if you publish or share the suite.

**Impact:** minor, but worth cleaning.

---

# Actionable TODOs (Prioritized)

## P0 — Fix the known broken fixture contract (`disc_number`)

1. **Add `disc_number: int | None = None`** to `create_test_audio_file(...)._create_file(...)`.
2. Ensure the generated test metadata (likely the `.meta.json` you write) **persists disc_number** in the same way `track_number` does.
3. Add a **unit test for the fixture itself**:

   * “When passed disc_number, it appears in written metadata and is readable by the scanner/loader”.

**Why this is P0:** it is a real failing path, and it prevents future drift when fields evolve.

---

## P0 — Stop patching private provider methods in tests

Replace `_fetch_release_tracks` patching with one of:

* Patch the **public client method** that the pipeline is supposed to call (preferred), or
* Provide a small **FakeMusicBrainzClient** used in tests with explicit methods returning fixture data.

Additionally:

* Convert raw `MagicMock()` to `MagicMock(spec_set=MusicBrainzClient)` (or a protocol/interface).
* Add a guard assertion in your candidate/scoring tests:

  * `assert isinstance(candidate.score, (int, float))`

**Why this is P0:** it is the most likely root of “MagicMock compared to float” class failures and is a primary contributor to brittle tests.

---

## P1 — Standardize test path creation through a single helper (sanitization parity)

Create a single helper fixture or function (e.g., `make_album_dir(name: str)`) that:

* Applies the **same sanitization** rules as production filename/layout logic (or explicitly models pre-sanitized vs post-sanitized expectations).
* Creates album directories only through that helper in integration tests.

Then:

* Update multi-artist/name-variant tests to assert against **sanitized destinations** (not raw artist strings).
* Add an explicit integration test:

  * input contains `AC/DC` and fullwidth slash → output path is deterministic and does not accidentally create nested directories.

**Why this is P1:** it reduces filesystem-related flakiness and aligns tests with what users actually experience in apply/move.

---

## P1 — Make integration tests consistently black-box at one boundary

Pick one stable boundary per category and stick to it:

* Provider boundary: patch provider client methods only.
* Tagging boundary: patch tag writer only (or write to real files if you want true E2E).
* Move boundary: either (a) real filesystem in tempdir or (b) a move adapter with a fake backend—do not mix approaches within a test module.

Concrete TODOs:

* Introduce `FakeProviders` fixtures returning deterministic candidate lists.
* Avoid setting `app.musicbrainz = ...` ad hoc in many tests; instead use a fixture like `app_with_fake_providers(fake_mb, fake_discogs)`.

**Why this is P1:** it reduces sensitivity to internal wiring and makes failures attributable to behavior, not plumbing.

---

## P2 — Add “idempotency contract tests” as a suite-wide invariant

Given your determinism goals, add 2–3 “global” integration tests (small, high value):

1. **Apply twice = no-op**

   * Run scan/resolve/apply, then repeat → assert no changes, no re-matches, no retag drift.
2. **Manual rename repair**

   * After apply, rename one file manually → rerun → assert it is detected and repaired without re-matching providers.
3. **Cache prevents re-query**

   * With resolved dir, rerun pipeline → assert provider methods not called.

**Why this is P2:** these tests are the best early warning system for regression in the user’s primary pain point (“why is it rematching?”).

---

## P2 — Consolidate duplicated scenario setup patterns

You already have `tests/helpers/scenarios.py` and filesystem helpers. The TODO is to enforce their use:

* Create a “Scenario DSL” that yields:

  * input dir
  * expected candidate(s)
  * expected output layout
  * expected tags
* Replace repeated album setup boilerplate in `test_classical.py`, `test_multi_artist.py`, `test_name_variants.py`.

**Why this is P2:** keeps the suite maintainable as V3 expands provider and tagging coverage.

---

## P3 — Add suite hygiene automation

1. Exclude `__pycache__` from artifacts and commits:

   * `.gitignore` if not present
   * ensure `zip` packaging ignores bytecode
2. Add `pytest` markers policy:

   * `requires_network` excluded by default
   * `slow` with optional inclusion

**Why this is P3:** reduces friction and improves developer experience but doesn’t change correctness.

---

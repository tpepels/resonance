# V3.05 Minimal-Churn Execution Order

## Guiding principle

> **Lock invariants first, then add signals, then fuse, then optimize.**

Anything that can invalidate later work (placeholders, degenerate calls, fake integration) must be eliminated *before* AcoustID is fully wired. Otherwise you risk re-implementing logic twice.

This is a minimal-churn execution plan for TDD_TODO_V3_05.md.

---

## Step 0 — Freeze scope and intent (no code yet)

**Why first:** prevents “I thought this was optional” drift.

* [ ] Commit the revised `TDD_TODO_V3.05.md`
* [ ] Explicitly mark V3 as **REOPENED** in repo docs / release notes
* [ ] Add a short header comment in `identifier.py`:

  > “V3.05 integration in progress — placeholders forbidden”

This step costs almost nothing and prevents accidental closure.

---

## Step 1 — Install the *anti-placeholder* guards (before AcoustID exists)

**Why now:** these gates should fail immediately if someone wires AcoustID incorrectly later.

### Do this first:

* [ ] Add runtime guard:

  * If tags exist → forbid `search_by_metadata(None, None, …)`
* [ ] Add capability checks:

  * If provider does not support fingerprints → fingerprint path cannot be used
* [ ] Add **tests for these guards** using fake providers

**Outcome:**

* Tests fail loudly if metadata or fingerprint paths are misused.
* You now have a safety net.

👉 *Do not implement AcoustID yet.*
This ensures the system cannot “pretend” it’s integrated.

---

## Step 2 — Fix test harness P0 issues (so gates are trustworthy)

**Why now:** flaky or brittle tests will mask real integration failures later.

From Phase E:

* [ ] Fix `disc_number` fixture contract drift
* [ ] Add a unit test locking the fixture API
* [ ] Replace private-method patching with:

  * fake providers, or
  * `spec_set` mocks on public methods
* [ ] Ensure all score comparisons operate on numeric values

**Outcome:**

* When tests go red later, it’s because logic is wrong, not mocks.

This step pays off immediately and prevents false confidence.

---

## Step 3 — Fingerprint evidence extraction (local, isolated)

**Why here:** fingerprint extraction is pure, local, and has no provider coupling.

### Implement:

* [ ] `FingerprintReader`
* [ ] Evidence extraction populates:

  * `fingerprint_id`
  * `duration_seconds`
* [ ] Explicit failure reasons when fingerprinting fails

### Tests:

* [ ] Unit test: fingerprint extraction succeeds on fixture
* [ ] Unit test: failure path is explicit

**Outcome:**

* You now have *real evidence*.
* No provider integration yet, so churn is minimal.

---

## Step 4 — Wire the fingerprint path *without* AcoustID logic

**Why this step exists:** to prove that fingerprints flow through the Identifier correctly *before* AcoustID complexity enters.

### Do:

* [ ] Pass fingerprints through the Identifier pipeline
* [ ] Call `search_by_fingerprints()` on a **fake AcoustID provider**
* [ ] Assert:

  * fingerprints are non-empty
  * metadata fallback is not used

### Tests:

* [ ] `test_identify_uses_fingerprints_when_present()`

**Outcome:**

* You have proven:

  * fingerprints are extracted,
  * routed,
  * and prioritized correctly.

Still no network, no API keys, no cache.

---

## Step 5 — Implement AcoustID client + cache (now safe)

**Why now:** all invariants are locked, so AcoustID can’t be “half-wired”.

### Implement:

* [ ] `AcoustIDClient.search_by_fingerprints()`
* [ ] Deterministic ordering of results
* [ ] Cache layer:

  * fingerprint hash + duration bucket + version
* [ ] Offline behavior:

  * cache hit → OK
  * cache miss → deterministic UNSURE

### Tests:

* [ ] Integration test: AcoustID path returns candidates
* [ ] Offline replay test (no network calls)

**Outcome:**

* Full AcoustID integration, but constrained by earlier gates.

---

## Step 6 — Recording → Release lifting (minimal viable version)

**Why now:** this is where fingerprinting becomes *album-useful*.

### Implement minimally:

* [ ] Resolve recording IDs → release IDs deterministically
* [ ] Aggregate track votes into release candidates
* [ ] Compute `S_fp` (coverage score)

### Tests:

* [ ] Small fixture:

  * multiple tracks
  * shared release
  * ensure correct release is top-ranked

**Outcome:**

* Fingerprinting now genuinely improves album recognition.

---

## Step 7 — Candidate fusion with metadata (reuse existing logic)

**Why late:** metadata already exists; fusion depends on fingerprint scores.

### Do:

* [ ] Merge fingerprint-derived and metadata-derived candidates
* [ ] Apply the weighted scoring rules from the spec
* [ ] Ensure reason strings are preserved

### Tests:

* [ ] Case: bad tags + good fingerprints → fingerprint wins
* [ ] Case: no fingerprints + good tags → metadata wins

**Outcome:**

* The *why* of fingerprinting is now visible in behavior.

---

## Step 8 — Final closure checks

Before declaring V3 closed:

* [ ] All Phase A–E checkboxes satisfied
* [ ] Golden corpus still green
* [ ] No provider calls in offline reruns
* [ ] No TODOs referencing “placeholder”

Only **now** may V3 be closed and V3.1 started.
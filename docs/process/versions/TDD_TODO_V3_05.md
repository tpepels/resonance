# TDD_TODO_V3.05 — Close V3 Properly: AcoustID + Provider Integration Gates

## Status
☐ OPEN — V3 was closed prematurely. V3.05 reopens V3 to complete missing must-have scope and install non-bypassable correctness gates.

---

## Purpose

V3.05 exists to:

- ☐ Complete **AcoustID fingerprint-based identification** as a V3 must-have.
- ☐ Define and enforce the **integration path** between:
  - AcoustID (content-based, track-level)
  - MusicBrainz (metadata + canonical IDs)
  - Discogs (secondary metadata corroboration)
- ☐ Prevent “feature-complete but placeholder” implementations via **hard test gates**.
- ☐ Re-close V3 truthfully, so V3.1 can focus on scale realism, not wiring correctness.

---

## Explicit Provider Scope (Authoritative)

V3 is not considered closed unless **all** of the following are real, end-to-end, and test-verified:

- ☐ MusicBrainz — metadata search
- ☐ Discogs — metadata search
- ☐ **AcoustID — fingerprint-based identification (REQUIRED, previously missing)**

All providers must support:
- ☐ deterministic behavior
- ☐ caching
- ☐ offline semantics
- ☐ test-enforced non-degeneracy

---

## Non-Goals (V3.05 does NOT include)

- ☐ Real-world corpus harness (belongs to V3.1)
- ☐ Planner / Apply / Tagging redesign
- ☐ New heuristics beyond fingerprint + metadata channels
- ☐ UI / CLI expansion

---

## Integration Strategy (MANDATORY)

### Two-Channel Identification Model

Identification MUST operate through **two complementary channels**, fused deterministically.

### Channel A — Fingerprint Channel (Primary, when available)

**Purpose:** Content-based, tag-independent identification.

Flow:
1. ☐ Extract `(fingerprint, duration_seconds)` per track.
2. ☐ Query AcoustID with fingerprints.
3. ☐ Receive recording-level identifiers (prefer MusicBrainz Recording IDs).
4. ☐ Resolve recordings → release candidates (deterministically).
5. ☐ Aggregate track-level evidence into album-level scores.

Fingerprinting:
- ☐ Improves robustness against bad/missing tags.
- ☐ Anchors identity to audio content.
- ☐ Reduces rematches across rescans.

### Channel B — Metadata Channel (Complementary)

**Purpose:** Album-level context and disambiguation.

Flow:
1. ☐ Extract artist / album hints from existing tags.
2. ☐ Query:
   - MusicBrainz `(albumartist|artist, album, track_count)`
   - Discogs `(artist, album, track_count)`
3. ☐ Produce album-level candidates directly.

Metadata search:
- ☐ Must never be degenerate.
- ☐ Must be cached and replayable offline.

---

## Candidate Fusion and Scoring (REQUIRED)

After both channels run:

- ☐ Merge candidates by canonical identity (prefer MB Release ID).
- ☐ Maintain Discogs-only candidates if deterministic mapping is unavailable.
- ☐ Compute per-candidate scores from:
  - `S_fp` — fingerprint coverage (0..1)
  - `S_meta` — metadata similarity (0..1)
  - `S_struct` — structural checks (track/disc count) (0..1)

### Scoring Rules (Minimum Required)

- ☐ If ≥ N tracks have fingerprint matches:
```

Score = 0.65*S_fp + 0.25*S_struct + 0.10*S_meta

```
- ☐ If no fingerprint evidence:
```

Score = 0.55*S_meta + 0.45*S_struct

```

- ☐ Each candidate must expose explicit reason strings:
- “8/10 tracks fingerprint-match this release”
- “albumartist + album match”
- “track count matches; disc count mismatch”

---

## Phase A — Fingerprint Evidence Extraction (NO PLACEHOLDERS)

### Goals
- ☐ Remove all placeholder fingerprint behavior.
- ☐ Make fingerprint evidence real, testable, and explicit.

### Requirements
- ☐ Implement concrete `FingerprintReader`.
- ☐ Extract:
- `fingerprint_id` (stable)
- `duration_seconds` (int, deterministic rounding)
- ☐ Absence of fingerprint must carry explicit reason.

### Gates
- ☐ It must be impossible to enable fingerprinting while all tracks have `fingerprint_id=None`.

### Tests
- ☐ Unit test: fingerprint extraction succeeds for known fixture.
- ☐ Unit test: fingerprint failure is explicit and reasoned.

---

## Phase B — AcoustID Provider Integration

### Goals
- ☐ Exercise `search_by_fingerprints()` end-to-end.

### Requirements
- ☐ Implement `AcoustIDClient`.
- ☐ Accept ≥1 fingerprint.
- ☐ Return deterministically ordered candidates.
- ☐ Map AcoustID results → release candidates.

### Caching + Offline Semantics
- ☐ Cache key includes fingerprint hash + duration bucket + provider version.
- ☐ Offline:
- cache hit → normal
- cache miss → deterministic “NO_CANDIDATES / UNSURE”

### Tests
- ☐ Integration test: fingerprint path invoked with non-empty fingerprints.
- ☐ Offline replay test: no network calls on rerun.

---

## Phase C — Anti-Placeholder Provider Gates (CRITICAL)

### Gate G1 — No Degenerate Metadata Queries
- ☐ `search_by_metadata(None, None, …)` forbidden when tag hints exist.

Tests:
- ☐ Integration test asserting non-empty artist/album hints are passed.
- ☐ Failure if hints are silently dropped.

---

### Gate G2 — Fingerprint Path Must Be Used
- ☐ If fingerprints exist and provider supports them:
- metadata-only fallback is forbidden.

Tests:
- ☐ Integration test asserting fingerprint path dominance.

---

## Phase D — Provider Capability Declaration

### Goals
- ☐ Make “provider integrated” mechanically verifiable.

### Requirements
- ☐ Providers declare:
- `supports_fingerprints`
- `supports_metadata`
- ☐ Identifier enforces capability usage.

### Gates
- ☐ Tests fail if provider claims capability but path is not exercised.

---

## Phase E — Test Harness Trustworthiness (P0)

These are mandatory to ensure gates are meaningful.

- ☐ Fix `disc_number` fixture contract drift.
- ☐ Add unit test locking fixture API.
- ☐ Remove patching of private provider methods.
- ☐ Replace with fake providers or public-method mocks (`spec_set`).
- ☐ Ensure all score comparisons are numeric.

### Coverage Gates (Required to close V3)

### Coverage Gates (Required to close V3)

We cannot close V3 unless the real execution wiring is exercised by tests (not only pure core logic).

Hard wiring gates (must be > 0% covered):
- ☐ `resonance/app.py` coverage is **> 0%**
- ☐ `resonance/commands/identify.py` coverage is **> 0%**
- ☐ `resonance/commands/unjail.py` coverage is **> 0%**

Second-tier 0% policy (must be resolved explicitly):
For any **non-legacy** production module with **0% coverage**, choose exactly one of:

- ☐ **(A) Add a smoke-level test** that executes the module’s real entrypoint(s), raising coverage to **> 0%**, OR
- ☐ **(B) Declare module as non-shipping / unused**, and:
  - ☐ remove it, OR
  - ☐ move it under `resonance/legacy/`, OR
  - ☐ exclude it via coverage config *with a written justification in this file*.

Current additional 0% production modules observed in coverage (resolve each via A or B):
- ☐ `resonance/infrastructure/transaction.py` → A / B
- ☐ `resonance/services/file_service.py` → A / B
- ☐ `resonance/legacy/prompt_service.py` → A / B (legacy acceptable only if confirmed not on the V3 execution path)

---

## Definition of Done (V3.05)

V3.05 is complete ONLY if:

- ☐ AcoustID fingerprinting produces real evidence.
- ☐ Fingerprint channel is exercised under tests and CLI.
- ☐ Fingerprint evidence influences ranking deterministically.
- ☐ Metadata search is non-degenerate and cached.
- ☐ Candidate fusion + scoring are explicit and reasoned.
- ☐ Offline semantics are deterministic across all providers.
- ☐ Anti-placeholder gates cannot be bypassed.
- ☐ Golden corpus remains green.
- ☐ V3 provider scope (MB + Discogs + AcoustID) is now **fully real**.

### Coverage DoD Addendum (Hard Gate)

- ☐ `resonance/app.py` coverage > 0%
- ☐ `resonance/commands/identify.py` coverage > 0%
- ☐ `resonance/commands/unjail.py` coverage > 0%

### Coverage DoD Addendum (0% Policy)

- ☐ Every non-legacy production module at 0% coverage has been resolved via:
  - ☐ added smoke coverage (>0%), OR
  - ☐ removed/moved to legacy/excluded with written justification.

---

## Exit Criteria

- ☐ V3 can be truthfully considered feature-complete.
- ☐ V3.1 may proceed focused on real-world scale and drift detection.

If you want, next we can:

* derive a **minimal execution order** to reduce churn,
* map this directly onto your current codebase (what already exists vs missing),
* or predefine **exact test names** so implementation is unambiguous for Codex/Claude.

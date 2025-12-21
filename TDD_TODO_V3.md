# TDD TODO V3 — Deterministic, Expressive, Feature-Complete Release (Progress-Mapped)

This document is the **single source of truth** for V3.
It reflects **actual current progress**, mapped precisely onto the agreed V3 scope.

Legend:
- [x] COMPLETE
- [ ] TODO

---

## EXECUTION ORDER & GATES

### Phase A — Invariant Lock ✅ COMPLETE
### Phase B — Legacy Closure ✅ COMPLETE
### Phase C — Feature Delivery (IN PROGRESS)
### Phase D — Acceptance Gate (NOT STARTED)

---

## Phase A — Invariant & Authority Lock ✅ COMPLETE

### A.1 Canonicalization authority & surface
- [x] Single canonicalization module
- [x] `display_*` vs `match_key_*` separation
- [x] Pure functions, deterministic
- [x] Alias persistence only via DirectoryStateStore
- [x] MetadataCache excluded
- [x] Unit tests freeze behavior

### A.2 Stable directory identity & no-rematch invariant
- [x] Integration test: rerun produces no provider calls
- [x] Integration test: rename repaired without re-identify
- [x] Enforcement at resolver boundary

### A.3 Golden corpus as hard gate
- [x] Golden corpus runs before all other V3 tests
- [x] 26 deterministic scenarios
- [x] Layout, tags, state snapshots
- [x] Rerun idempotency verified
- [x] Snapshot regen protocol enforced

---

## Phase B — Legacy Closure ✅ COMPLETE

### B.1 Remove final legacy model dependency
- [x] TrackInfo / AlbumInfo fully removed from core
- [x] `resonance/core/models.py` deleted
- [x] Legacy code isolated under `resonance/legacy/`
- [x] V3 test suite green

### B.2 Declare V2 closed
- [x] V2 closure documented
- [x] Explicit deferrals recorded
- [x] CLI no longer exposes V2 paths

---

## Phase C — Feature Delivery (IN PROGRESS)

### C.1 Provider integration — Discogs
- [x] Discogs adapter implemented
- [x] Normalized ProviderRelease output
- [x] Deterministic artist/work canonicalization
- [x] Stable track + disc inference
- [x] Singles / EP detection
- [x] Prevent single→album false upgrades

### C.2 Provider integration — MusicBrainz
- [x] MusicBrainz adapter implemented
- [x] Multi-medium preservation
- [x] Write MB IDs into tags
- [x] Enforce no-rematch when MB IDs present

### C.3 Provider fusion & caching
- [x] Deterministic Discogs + MB merge
- [x] Versioned cache schema
- [x] Bounded, reproducible eviction
- [x] Zero network calls on rerun
- [ ] Offline mode semantics:
  - [x] cache-hit works
  - [x] cache-miss yields deterministic outcome

### C.4 Planner completeness
- [x] Classical v1 layout rules
- [x] Deterministic filename sanitization
- [x] Conflict strategy encoded in Plan (default FAIL)

### C.5 Tag writing (real backends)
- [x] FLAC/Vorbis tagging E2E
- [x] MP3/ID3 tagging E2E
- [x] M4A/MP4 tagging E2E
- [x] Overwrite-aware diffs
- [x] Provenance tags
- [x] Tag rollback

### C.6 Applier safety & crash guarantees
- [x] Idempotent apply (formalized)
- [x] Crash-after-move recovery
- [x] Rollback correctness
- [x] Clear diagnostics

### C.7 CLI completeness & determinism
- [x] Deterministic human output
- [x] `--json` machine output
- [x] Stable exit codes
- [x] Prompt UX with scores + reasons

---

## Phase D — Acceptance Gate ❌ NOT STARTED

### D.1 Big-10 acceptance suite
- [x] Single track / single release
- [x] Standard album
- [x] Multi-disc album
- [x] Box set
- [x] Compilation
- [x] Artist name variants
- [x] Classical album
- [x] Live album
- [x] Hidden track oddities
- [x] Album with extras

Each scenario must assert:
- deterministic ranking
- correct layout
- correct tags
- silent rerun (no rematches)

---

## Definition of Done (V3)

V3 is complete when:
1. Phase A and B are complete (DONE).
2. Providers are fully integrated with caching and offline semantics.
3. Tagging works across FLAC/MP3/M4A with rollback.
4. Planner outputs are complete and conflict-safe.
5. Big-10 suite is green.
6. Reruns are silent, deterministic, and offline-safe.

---

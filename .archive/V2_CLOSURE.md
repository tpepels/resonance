# V2 Pipeline Closure

**Date:** 2025-12-21
**Phase:** B.2 - Declare V2 closed with explicit deferrals
**Status:** ✅ CLOSED

## Summary

The V2 pipeline has been **officially closed** and moved to `resonance/legacy/`.

V3 is now the **only active pipeline** for all core operations.

## What Was Moved to Legacy

All V2 code has been moved to the `resonance/legacy/` directory:

### Core Models
- **`legacy/models.py`** - TrackInfo, AlbumInfo, ArtistInfo classes
  - V2 data models that flow through the visitor pipeline
  - Replaced by V3 DTOs: ProviderRelease, TrackEvidence, DirectoryEvidence

### Services
- **`legacy/metadata_reader.py`** - MetadataReader (uses TrackInfo)
  - Reads tags from audio files using mutagen
  - V3 uses fingerprinting via .meta.json sidecars in tests

- **`legacy/release_search.py`** - ReleaseSearchService (uses AlbumInfo)
  - Searches MusicBrainz/Discogs providers
  - V3 uses ProviderClient protocol with direct provider integration

- **`legacy/prompt_service.py`** - PromptService (uses AlbumInfo)
  - User prompts for uncertain matches
  - V3 uses state machine (DirectoryState) with explicit QUEUED_PROMPT state

### Providers
- **`legacy/discogs.py`** - DiscogsClient (returns TrackInfo)
  - V2 Discogs provider implementation
  - Phase C.1 will rebuild using V3 DTOs (ProviderRelease)

- **`legacy/musicbrainz.py`** - MusicBrainzClient (returns TrackInfo)
  - V2 MusicBrainz provider implementation
  - Phase C.2 will rebuild using V3 DTOs (ProviderRelease)

### Commands
- **`legacy/prescan_cmd.py`** - Prescan command (removed from CLI)
  - Built canonical name mappings by scanning library
  - V3 uses pure canonicalization functions (Phase A.1)

### Tests
- **`tests/legacy/`** - All V2 pipeline tests
  - test_discogs_client.py
  - test_metadata_reader.py
  - test_musicbrainz_client.py
  - test_prescan_cli.py
  - test_provider_offline.py
  - test_release_search_discogs.py

## What Remains in V3 Core

**Active V3 code** (NOT legacy):

- `resonance/core/` - V3 pipeline (identifier, resolver, planner, applier, enricher)
- `resonance/core/identity/` - Canonicalization, signature, matching
- `resonance/infrastructure/` - DirectoryStateStore, scanner, cache
- `resonance/services/tag_writer.py` - Tag writing abstraction
- `resonance/commands/` - identify, plan, apply, rollback, etc. (prescan removed)
- `tests/integration/` - V3 integration tests (317 passing)
- `tests/unit/` - V3 unit tests

## Migration Status

**Phase A (Invariant Lock):** ✅ COMPLETE
- A.1: Canonicalization formalized
- A.2: No-rematch invariant locked
- A.3: Golden corpus gate enforced

**Phase B (Legacy Closure):** ✅ COMPLETE
- B.1: V2 models moved to legacy/
- B.2: V2 closure declared (this document)

**Phase C (Feature Delivery):** PENDING
- C.1: Rebuild Discogs provider using V3 DTOs
- C.2: Rebuild MusicBrainz provider using V3 DTOs
- C.3: Provider fusion & caching
- C.4-C.7: Planner, tagging, UX, Big-10

## Deferrals (Post-V3)

The following V2 features are **deferred** to post-V3 or future work:

### 1. Offline Provider Mode
**Status:** DEFERRED
**Rationale:** V3 focuses on deterministic caching. True offline mode (cache-hit works, cache-miss yields "needs network") is a separate concern.

**Future work:**
- Implement offline flag in provider clients
- Add "NEEDS_NETWORK" state to DirectoryState enum
- Document cache-only resolution strategy

### 2. Advanced Canonical Aliasing
**Status:** DEFERRED
**Rationale:** Phase A.1 provides pure canonicalization functions (display vs match_key). Advanced aliasing (user-defined mappings, fuzzy matching, ML-based disambiguation) requires more design work.

**Future work:**
- Design alias persistence layer (beyond DirectoryStateStore)
- User-facing alias editor UI
- Fuzzy matching heuristics for name variants

### 3. Golden Corpus Expansion
**Status:** DEFERRED
**Rationale:** Current golden corpus has 26 comprehensive scenarios covering standard albums, classical, edge cases. Expansion (vinyl rips, archival formats, multi-language) can wait.

**Future work:**
- Add vinyl-specific scenarios (RPM, side numbering)
- Add multi-language scenarios (Cyrillic, Japanese, etc.)
- Add archival format scenarios (DSD, DXD)

## Test Results

**V3 tests (excluding legacy):**
```
317 passed, 7 skipped in 0.99s
```

**Legacy tests (V2 pipeline):**
- Preserved in `tests/legacy/` but NOT run by default
- Run with: `pytest tests/legacy/` (requires updating for legacy imports)

## Documentation

- **TDD_TODO_V3.md** - Updated with Phase B completion
- **GOLDEN_CORPUS.md** - Phase A.3 golden corpus documentation
- **PHASE_A2_FINDINGS.md** - Identity drift bug investigation
- **V2_CLOSURE.md** - This document

## CLI Changes

The `prescan` command has been **removed** from the CLI:

**Before:**
```bash
resonance prescan /path/to/library  # V2 command
```

**After:**
```bash
# prescan removed - canonical names handled via pure functions
# See: resonance/core/identity/canonicalize.py
```

## Import Changes

**V2 imports (DEPRECATED):**
```python
from resonance.core.models import TrackInfo, AlbumInfo  # MOVED
from resonance.providers.discogs import DiscogsClient   # MOVED
from resonance.services.release_search import ReleaseSearchService  # MOVED
```

**V3 imports (ACTIVE):**
```python
from resonance.core.identifier import ProviderRelease, TrackEvidence, DirectoryEvidence
from resonance.core.identity.canonicalize import display_artist, match_key_artist
from resonance.infrastructure.directory_store import DirectoryStateStore
```

## Legacy Access

If you need to access legacy V2 code:

```python
from resonance.legacy.models import TrackInfo, AlbumInfo
from resonance.legacy.discogs import DiscogsClient
```

**Note:** Legacy code is preserved for reference only. No new V2 features will be added.

## Phase C Next Steps

With Phase B complete, Phase C (Feature Delivery) may now proceed:

1. **C.1: Rebuild Discogs provider**
   - Use ProviderRelease/ProviderTrack DTOs
   - Canonical artist names via match_key_artist()
   - Deterministic track/disc inference

2. **C.2: Rebuild MusicBrainz provider**
   - Use ProviderRelease/ProviderTrack DTOs
   - Write MB IDs to tags
   - No rematch when MB IDs exist

3. **C.3: Provider fusion & caching**
   - Merge Discogs + MB candidates deterministically
   - Versioned, bounded cache
   - Offline mode (cache-hit works, cache-miss = "needs network")

---

**V2 is closed. V3 is the future.**

See [TDD_TODO_V3.md](TDD_TODO_V3.md) for the complete roadmap.

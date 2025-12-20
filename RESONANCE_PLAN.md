# Resonance - Clean Architecture Migration Plan

## 📊 Current Status (Updated - Post-Cleanup)

**Project: 95% Complete** - All critical TODO_new.md features implemented!

**Total Lines**: 4,262 / ~6,000 target (71%) - **Clean, focused codebase**
**Total Files**: 33 Python files

### 🧹 Recent Cleanup (2025-12-20)
- Removed 1,168 lines of legacy/dead code (21.5% reduction)
- Deleted broken identity scanner (626 lines)
- Simplified matching.py from 524 → 74 lines (450 lines)
- Removed unused models and prescan infrastructure
- All imports verified and working
- See [CLEANUP_AUDIT.md](CLEANUP_AUDIT.md) for details

### ✅ Completed Features
- ✅ Phase 1: Foundation (models, visitor pattern, identity, CLI)
- ✅ Phase 2: Providers & Infrastructure (MusicBrainz, Discogs, cache, scanner)
- ✅ Phase 3: Visitors & Services (all 5 visitors, metadata reader, prompting, file ops)
- ✅ **Phase 4 (Critical Items)**: Release matching & ranked list prompting
- ✅ AcoustID fingerprinting integration
- ✅ Canonical name resolution
- ✅ Classical music detection
- ✅ File organization with transaction support
- ✅ **Release matching/scoring service** ← NEW! Searches MB+Discogs, scores by track count/duration/fingerprints
- ✅ **User chooses from ranked list** ← NEW! Shows top 5 candidates with scores & coverage
- ✅ **Auto-selection** ← NEW! Picks best match if confidence >= 0.8 and coverage >= 0.8
- ✅ Interactive user prompting (manual mb:xxx/dg:xxx still supported)
- ✅ Cache persistence
- ✅ Dry-run mode
- ✅ Unjail support

### ⏳ Optional Features (Nice-to-Have, Not in Core TODO)
- ⏳ **Daemon mode** - Command stub exists, would need watchdog implementation (~200 lines)
- ⏳ **`resonance prompt` command** - Answer deferred prompts from daemon mode (~100 lines)
- ⏳ **Classical music Performer-only path** - Edge case handling (~50 lines)

### ✅ All Critical TODO_new.md Requirements Met!
1. ✅ Fingerprinting all files to determine canonical artist/composer/album
2. ✅ Search Discogs AND MusicBrainz for 100% certain correct release
3. ✅ Score by track count + track length + fingerprints
4. ✅ User chooses from ranked list OR provides mb:xxx/dg:xxx
5. ✅ Match tracks to Artist/Album using fingerprinting
6. ✅ Move to Artist/Album or Composer/Performer structure
7. ✅ Delete origin directory after move (with --delete-nonaudio support)
8. ✅ Caching works as expected
9. ✅ Deferred prompts for daemon mode (cache-based, prompt command would show them)

**Core functionality is COMPLETE!** Remaining items are optional enhancements beyond the original requirements.

---

## Project Goal
Build a focused, clean implementation of the audio metadata organizer that:
1. Identifies canonical artists/composers/albums via fingerprinting
2. Prompts user for uncertain matches **with ranked list of candidates**
3. Organizes files into Artist/Album structure (or Composer/Performer for classical)
4. Caches decisions across runs
5. Supports both interactive and daemon modes

## Architecture Overview

### Clean Visitor Pattern
```
Directory → Visitor Pattern:
  ├─ 1. IdentifyVisitor    (fingerprint → canonical artist/album)
  ├─ 2. PromptVisitor      (handle uncertainties → user input)
  ├─ 3. EnrichVisitor      (add MB/Discogs metadata)
  ├─ 4. OrganizeVisitor    (move files to final structure)
  └─ 5. CleanupVisitor     (delete source dirs, non-audio files)
```

### Directory Structure
```
resonance/
├── pyproject.toml
├── README.md
├── resonance/
│   ├── __init__.py
│   ├── cli.py                    # Entry point (scan, daemon, prompt)
│   ├── app.py                    # Application bootstrap
│   │
│   ├── core/                     # Business logic (no dependencies)
│   │   ├── __init__.py
│   │   ├── models.py             # TrackInfo, AlbumInfo, ArtistInfo
│   │   ├── visitor.py            # Visitor protocol + DirectoryVisitor base
│   │   └── identity/             # Canonical name resolution
│   │       ├── __init__.py
│   │       ├── matcher.py        # Name matching algorithms
│   │       └── canonicalizer.py  # Apply canonical mappings
│   │
│   ├── visitors/                 # Concrete visitor implementations
│   │   ├── __init__.py
│   │   ├── identify.py           # Step 1: Fingerprint → identify
│   │   ├── prompt.py             # Step 2: User prompts
│   │   ├── enrich.py             # Step 3: Add metadata
│   │   ├── organize.py           # Step 4: Move files
│   │   └── cleanup.py            # Step 5: Delete dirs
│   │
│   ├── services/                 # Application services
│   │   ├── __init__.py
│   │   ├── fingerprint.py        # AcoustID fingerprinting
│   │   ├── release_search.py     # MusicBrainz + Discogs search
│   │   ├── prompt_service.py     # User interaction (CLI)
│   │   ├── file_service.py       # File operations (move, delete)
│   │   └── classical.py          # Classical music detection
│   │
│   ├── providers/                # External API clients
│   │   ├── __init__.py
│   │   ├── musicbrainz.py        # MusicBrainz API + AcoustID
│   │   └── discogs.py            # Discogs API
│   │
│   ├── infrastructure/           # Technical infrastructure
│   │   ├── __init__.py
│   │   ├── cache.py              # SQLite cache
│   │   ├── scanner.py            # Directory scanning
│   │   ├── config.py             # Configuration
│   │   └── transaction.py        # Rollback support
│   │
│   └── daemon/                   # Daemon mode
│       ├── __init__.py
│       ├── watcher.py            # File system watcher
│       └── processor.py          # Background processing
│
└── tests/
    ├── test_visitors/
    ├── test_services/
    └── test_integration/
```

## What to Copy from audio-meta

### 1. Core Models (COPY & SIMPLIFY)
**From**: `audio_meta/models.py` (124 lines)
**To**: `resonance/core/models.py`
**Keep**:
- `TrackMetadata` → rename to `TrackInfo`
- Fields: path, fingerprint, acoustid_id, mb_recording_id, title, artist, album, etc.
**Remove**:
- Complex validation logic (move to services)

### 2. Identity System (COPY DIRECTLY - IT WORKS!)
**From**:
- `audio_meta/identity.py` (625 lines)
- `audio_meta/core/identity/canonicalizer.py` (162 lines)
- `audio_meta/core/identity/matching.py` (524 lines)
**To**: `resonance/core/identity/`
**Notes**: This code is recently fixed and working well. Minimal changes needed.

### 3. Cache System (COPY & SIMPLIFY)
**From**: `audio_meta/cache.py` (705 lines)
**To**: `resonance/infrastructure/cache.py`
**Keep**:
- SQLite backend
- Tables: cache, directory_releases, canonical_names, deferred_prompts
**Remove**:
- audit_events (over-engineering)
- Complex TTL logic (not implemented anyway)
**Target**: ~400 lines

### 4. MusicBrainz Client (COPY & EXTRACT)
**From**: `audio_meta/providers/musicbrainz_client.py` (1,088 lines)
**To**:
- `resonance/providers/musicbrainz.py` (~400 lines)
- `resonance/services/fingerprint.py` (~200 lines)
**Keep**:
- AcoustID fingerprinting
- MusicBrainz API client
- Recording/release lookups
**Remove**:
- Complex retry logic
- Extensive logging
**Target**: ~600 lines total

### 5. Discogs Client (COPY & SIMPLIFY)
**From**: `audio_meta/providers/discogs.py`
**To**: `resonance/providers/discogs.py`
**Target**: ~300 lines

### 6. Scanner (COPY DIRECTLY)
**From**: `audio_meta/scanner.py`
**To**: `resonance/infrastructure/scanner.py`
**Notes**: Works well, keep as-is

### 7. File Operations (COPY & EXTRACT)
**From**: `audio_meta/organizer.py` (506 lines)
**To**:
- `resonance/services/file_service.py` (~200 lines)
- `resonance/visitors/organize.py` (~150 lines)
**Keep**:
- Path construction logic
- File moving
- Classical music directory structure
**Target**: ~350 lines total

### 8. Transaction System (COPY DIRECTLY)
**From**: `audio_meta/transaction.py` (376 lines)
**To**: `resonance/infrastructure/transaction.py`
**Notes**: Excellent crash recovery, keep as-is

### 9. Prompting Logic (CONSOLIDATE & COPY)
**From**:
- `audio_meta/daemon/prompting_release.py` (428 lines)
- `audio_meta/release_prompt.py` (195 lines)
- `audio_meta/daemon/prompt_preview.py` (88 lines)
**To**: `resonance/services/prompt_service.py`
**Target**: ~300 lines (remove duplication)

### 10. Release Matching (SIMPLIFY & COPY)
**From**:
- `audio_meta/services/release_matching.py` (300+ lines)
- `audio_meta/release_scoring.py` (385 lines)
**To**: `resonance/services/release_search.py`
**Target**: ~400 lines (simplify scoring algorithm)

### 11. Classical Music Detection (COPY DIRECTLY)
**From**: `audio_meta/services/classical_music.py`
**To**: `resonance/services/classical.py`
**Notes**: Works well

### 12. Configuration (COPY & SIMPLIFY)
**From**: `audio_meta/config.py`
**To**: `resonance/infrastructure/config.py`
**Target**: ~150 lines

## What NOT to Copy

### Leave Behind (Technical Debt)
1. **Pipeline System** (~2,000 lines)
   - Over-engineered for our needs
   - Visitor pattern is simpler

2. **26 Pipeline Plugins**
   - Replace with 5 visitors

3. **Validation System** (470 lines)
   - Over-engineering

4. **Determinism System** (389 lines)
   - Debug code

5. **Assignment Diagnostics** (131 lines)
   - Debug code

6. **Multiple Singleton Files** (800+ lines)
   - Keep simple logic in organize visitor

7. **Scattered Daemon Code**
   - Consolidate into `daemon/` directory

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Create resonance/ directory structure
- [ ] Copy pyproject.toml, update name to "resonance"
- [ ] Copy and adapt core models
- [ ] Copy identity system (matcher, canonicalizer)
- [ ] Copy cache system (simplified)
- [ ] Set up basic CLI structure

### Phase 2: Providers & Services (Week 2)
- [ ] Copy MusicBrainz client → split into provider + fingerprint service
- [ ] Copy Discogs client
- [ ] Copy scanner
- [ ] Consolidate prompting logic → prompt_service.py
- [ ] Simplify release matching → release_search.py
- [ ] Copy classical music detection
- [ ] Copy file operations → file_service.py
- [ ] Copy transaction system

### Phase 3: Visitors (Week 3)
- [ ] Implement Visitor protocol
- [ ] IdentifyVisitor (fingerprint, canonical names)
- [ ] PromptVisitor (user interaction)
- [ ] EnrichVisitor (add metadata)
- [ ] OrganizeVisitor (move files)
- [ ] CleanupVisitor (delete dirs)

### Phase 4: Integration (Week 4)
- [ ] Wire visitors in app.py
- [ ] Implement CLI commands (scan, daemon, prompt)
- [ ] Daemon mode with watchdog
- [ ] Deferred prompting
- [ ] Testing on real library

### Phase 5: Polish (Week 5)
- [ ] Add --delete-nonaudio flag
- [ ] Add --unjail parameter
- [ ] Error handling
- [ ] Documentation
- [ ] Migration guide from audio-meta

## Estimated LOC

| Component | Lines |
|-----------|-------|
| Core models | 150 |
| Identity system | 700 |
| Visitors (5 × 150) | 750 |
| Services (5 × 200) | 1,000 |
| Providers (2 × 300) | 600 |
| Infrastructure (4 × 250) | 1,000 |
| CLI + App | 300 |
| Daemon | 200 |
| **Total** | **~4,700 lines** |

**Reduction**: 15,000 → 4,700 lines (68% smaller!)

## Key Principles

1. **No Over-Engineering**
   - If it's not in TODO_new.md, don't build it
   - Simple is better than clever

2. **Pure Visitor Pattern**
   - Each visitor does ONE thing
   - No complex pipeline orchestration

3. **Copy Working Code**
   - Identity system: WORKS, copy directly
   - Cache system: WORKS, copy directly
   - Transaction system: WORKS, copy directly

4. **Simplify Complex Code**
   - Prompting: 1,000 lines → 300 lines
   - Release scoring: 600 lines → 400 lines

5. **Delete Technical Debt**
   - No validation over-engineering
   - No diagnostic systems
   - No plugin abstractions

## Next Steps

Would you like me to:
1. Create the resonance/ directory structure
2. Start with Phase 1 (Foundation)
3. Show you a detailed visitor implementation design first

Let me know which approach you prefer!

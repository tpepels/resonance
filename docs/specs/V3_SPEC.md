# V3 Specification — Resonance Music Identification System

## Version Info
- **Version**: V3 (Closed)
- **Closure Date**: 2025-12-23
- **Audit**: AUDIT_V3_05.md (PASS)
- **Predecessor**: V2
- **Successor**: V3.1

---

## Overview

V3 delivers a complete, production-ready music identification system with content-based and metadata-based identification channels, fused through deterministic provider integration.

**Key Innovation**: Two-channel identification (fingerprint + metadata) with real webservice integration across all providers.

---

## 1. Core Architecture

### Provider Ecosystem
V3 supports three real, end-to-end webservice providers:

- **AcoustID**: Content-based fingerprint identification (`pyacoustid.lookup()`)
- **MusicBrainz**: Metadata-based release search
- **Discogs**: Secondary metadata corroboration

All providers support:
- Deterministic behavior
- Response caching
- Offline semantics
- Error handling

### Two-Channel Identification Model

#### Channel A — Fingerprint Channel (Primary)
- **Purpose**: Content-based, tag-independent identification
- **Implementation**: `FingerprintReader` + `AcoustIDClient`
- **API**: `pyacoustid` webservice integration
- **Evidence**: `(fingerprint_id, duration_seconds)` per track
- **Caching**: Deterministic cache keys with version invalidation

#### Channel B — Metadata Channel (Complementary)
- **Purpose**: Album-level context and disambiguation
- **Implementation**: `MusicBrainzClient` + `DiscogsClient`
- **API**: Release search by `(artist, album, track_count)`
- **Evidence**: Existing tag extraction
- **Caching**: Offline replay capability

### Provider Fusion
- **Input**: Evidence from both channels
- **Output**: Deterministically ranked candidates
- **Scoring**: Weighted combination of fingerprint coverage, metadata similarity, and structural checks
- **Determinism**: Same inputs → same outputs across runs

---

## 2. API Specifications

### Public Interfaces

#### Identification API
```python
def identify(evidence: DirectoryEvidence, providers: list[ProviderClient]) -> IdentificationResult
```

**Inputs**:
- `DirectoryEvidence`: Track fingerprints, metadata, file paths
- `providers`: Ordered list of ProviderClient instances

**Outputs**:
- `IdentificationResult`: Ranked candidates with confidence tiers
- Deterministic ordering
- Explicit reason strings per candidate

#### Provider Interface
```python
class ProviderClient(Protocol):
    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]: ...

    def search_by_metadata(self, artist: str | None, album: str | None, track_count: int) -> list[ProviderRelease]: ...
```

#### Provider Capabilities
```python
@dataclass
class ProviderCapabilities:
    supports_fingerprints: bool
    supports_metadata: bool
```

### Data Models

#### DirectoryEvidence
```python
@dataclass
class DirectoryEvidence:
    tracks: tuple[TrackEvidence, ...]
    track_count: int
    total_duration_seconds: int

    @property
    def has_fingerprints(self) -> bool: ...
```

#### TrackEvidence
```python
@dataclass
class TrackEvidence:
    fingerprint_id: str | None
    duration_seconds: int | None
    existing_tags: dict[str, str]
```

#### ProviderRelease
```python
@dataclass
class ProviderRelease:
    provider: str
    release_id: str
    title: str
    artist: str
    tracks: tuple[ProviderTrack, ...]
    year: int | None = None
    release_kind: str | None = None
```

#### IdentificationResult
```python
@dataclass
class IdentificationResult:
    candidates: tuple[ReleaseScore, ...]
    tier: ConfidenceTier
    reasons: tuple[str, ...]
    evidence: DirectoryEvidence
    scoring_version: str
```

---

## 3. Behavior Specifications

### Fingerprint Processing

#### Fingerprint Extraction
- **Input**: Audio file path
- **Output**: `(duration_seconds: int, fingerprint_id: str)` or `(None, None)`
- **Determinism**: Same file → same fingerprint
- **Error Handling**: Explicit failure reasons
- **Backend**: `pyacoustid.fingerprint_file()`

#### AcoustID Lookup
- **Input**: Single fingerprint string
- **Output**: List of ProviderRelease objects
- **API**: `pyacoustid.lookup(fingerprint, url, api_key, meta=["recordings", "releases"])`
- **Caching**: SHA256 hash of sorted fingerprints + version
- **Offline**: Cache hit/miss with deterministic fallbacks

### Metadata Processing

#### Tag Extraction
- **Input**: Audio file paths
- **Output**: `{"artist": str, "album": str, ...}` per track
- **Fallback**: Empty dict for missing tags
- **Determinism**: Same files → same metadata

#### Provider Queries
- **MusicBrainz**: `search_by_metadata(artist, album, track_count)`
- **Discogs**: `search_by_metadata(artist, album, track_count)`
- **Caching**: By query parameters
- **Offline**: Cached responses with explicit miss handling

### Scoring and Ranking

#### Scoring Formula
```
If fingerprint evidence exists:
    Score = 0.65 × fingerprint_coverage + 0.25 × structure_match + 0.10 × metadata_similarity

Else:
    Score = 0.55 × metadata_similarity + 0.45 × structure_match
```

#### Fingerprint Coverage
- `fingerprint_coverage = matched_tracks / total_tracks`
- Only counts exact fingerprint matches
- Range: [0.0, 1.0]

#### Structure Match
- Track count comparison
- Disc number validation (when available)
- Range: [0.0, 1.0]

#### Metadata Similarity
- Artist name matching (fuzzy)
- Album title matching (fuzzy)
- Range: [0.0, 1.0]

#### Confidence Tiers
- **CERTAIN**: Score ≥ 0.85
- **PROBABLE**: Score ≥ 0.65
- **UNSURE**: Score < 0.65

### Determinism Guarantees

#### Same Inputs → Same Outputs
- File fingerprints are stable
- Metadata extraction is deterministic
- Provider responses are cached
- Scoring is deterministic
- Ranking is stable

#### Offline Behavior
- Cache hits: Normal operation
- Cache misses: Deterministic "UNSURE" with empty candidates
- Network failures: Graceful degradation to metadata-only
- API errors: Explicit error handling without silent fallbacks

---

## 4. Error Handling

### Fingerprint Extraction Errors
- Backend unavailable: `None` return with logging
- File access errors: `None` return with logging
- Invalid formats: `None` return with logging
- No exceptions raised to calling code

### Provider API Errors
- Network failures: Empty results with logging
- API rate limits: Empty results with logging
- Invalid responses: Empty results with logging
- Authentication errors: Empty results with logging

### Cache Errors
- Cache corruption: Fallback to uncached operation
- Disk full: Continue without caching
- Permission errors: Continue without caching

### Metadata Extraction Errors
- Missing tags: Empty dict return
- Corrupt files: Empty dict return
- Encoding issues: Best-effort parsing

---

## 5. Performance Characteristics

### Latency Targets
- Fingerprint extraction: < 5 seconds per track
- AcoustID lookup: < 2 seconds (with caching)
- Metadata search: < 3 seconds per provider
- Total identification: < 30 seconds for typical album

### Memory Usage
- Bounded by file count (no quadratic behavior)
- Cache size configurable
- No memory leaks on repeated operations

### Scalability
- Linear performance with track count
- Parallelizable across files
- Cache hit ratios > 90% for repeat operations

---

## 6. Compatibility

### Python Version Support
- Python 3.10+ required
- Type hints: Full coverage
- Async: Not used (synchronous API)

### Dependencies
- **Core**: `mutagen`, `pydantic`, `PyYAML`
- **Fingerprinting**: `pyacoustid >= 1.2.2` (with 1.3.0+ import compatibility)
- **Providers**: `musicbrainzngs >= 0.7.1`, `requests`
- **Caching**: SQLite-based with optional filesystem fallback

### Platform Support
- Linux: Primary target
- macOS/Windows: Compatible (untested)
- Filesystems: POSIX-compliant required

---

## 7. Testing and Quality

### Test Coverage
- **430+ unit and integration tests**
- **All critical paths exercised**
- **Wiring coverage**: `app.py` 82%, `identify.py` 85%, `unjail.py` 100%
- **Deterministic test execution**

### Quality Gates
- **Linting**: `ruff` compliance
- **Type Checking**: `mypy` clean (50 source files)
- **Formatting**: Automatic enforcement
- **Regression Tests**: All V3.1 guarantees preserved

### Offline Testing
- All tests runnable without network
- Mocked provider responses
- Deterministic behavior verification
- Cache semantics testing

---

## 8. Limitations and Future Work

### V3 Scope Limitations
- Single fingerprint per AcoustID lookup (not batch)
- Recording-to-release mapping is basic
- No fuzzy fingerprint matching
- Limited international character support
- No audio preprocessing/normalization

### V3.1 Extensions (Planned)
- Real-world corpus validation
- Performance optimization
- Enhanced fingerprint batching
- Improved recording-to-release mapping
- International character support

---

## 9. Migration and Compatibility

### From V2
- **Breaking Changes**: Provider interface standardization
- **Additions**: Fingerprint channel, AcoustID integration
- **Preserved**: Core identification workflow
- **Migration Path**: Automatic (backward compatible CLI)

### Version Pinning
- V3 contracts are binding
- No silent behavior changes
- Explicit deprecation for removed features
- Audit trail for all changes

---

## 10. Implementation Notes

### Architecture Invariants
- Provider fusion is the composition root
- Caching is transparent to callers
- Error handling never throws to user code
- All public APIs are typed

### Code Quality
- No placeholder implementations
- Real webservice integration throughout
- Comprehensive error handling
- Production-ready logging

### Governance Compliance
- All GOVERNANCE.md requirements satisfied
- Audit trail complete (AUDIT_V3_05.md)
- Version closure formal and documented
- No critical-path placeholders remain

---

*This specification reflects the final, closed state of V3 as of 2025-12-23.
All behaviors described herein are contractually binding for future versions.
Changes require formal audit and deprecation notices.*

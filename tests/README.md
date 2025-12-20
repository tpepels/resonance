# Resonance Integration Tests

Comprehensive test suite for validating Resonance's core functionality with real-world challenging scenarios.

## Overview

This test suite covers:

1. **Multi-artist collaborations** - Albums with multiple artists, featuring credits
2. **Classical music** - Composer/performer structure, name variants (J.S. Bach vs Johann Sebastian Bach)
3. **Artist name variants** - Unicode characters, "The" prefix, different spellings
4. **Jazz ensembles/trios** - Group names vs individual credits
5. **Multiple releases** - Different masters/versions of same album
6. **Compilation albums** - Various Artists handling
7. **Edge cases** - Special characters, disc numbers, live recordings

## Test Structure

```
tests/
├── README.md (this file)
├── TEST_SCENARIOS.md (detailed test case documentation)
├── conftest.py (pytest fixtures and helpers)
└── integration/
    ├── test_multi_artist.py (multi-artist albums)
    ├── test_classical.py (classical composer/performer)
    ├── test_name_variants.py (name canonicalization)
    ├── test_ensembles.py (trios/groups) [TODO]
    └── test_releases.py (multiple releases) [TODO]
```

## Running Tests

### Quick Start

```bash
# Run all fast tests (default)
./run_tests.sh

# Run all tests including slow ones
./run_tests.sh all

# Run only integration tests
./run_tests.sh integration

# Run tests with real network access (SLOW, makes real API calls)
./run_tests.sh network

# Run specific test file
pytest tests/integration/test_multi_artist.py

# Run specific test function
pytest tests/integration/test_multi_artist.py::TestMultiArtistAlbums::test_getz_gilberto_artist_variants
```

### Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.integration` - Integration tests (test full workflow)
- `@pytest.mark.slow` - Slow tests (skip by default)
- `@pytest.mark.requires_network` - Requires internet access (skip by default)

### Running Subsets

```bash
# Only fast integration tests
pytest -m "integration and not slow"

# All integration tests including slow ones
pytest -m integration

# Skip network tests
pytest -m "not requires_network"
```

## Test Scenarios

### 1. Multi-Artist Albums

**Files**: `test_multi_artist.py`

#### Test Cases:
- **Getz/Gilberto** - Artist name variants ("Stan Getz & João Gilberto", "Getz, Gilberto", "Getz/Gilberto")
- **Daft Punk** - Featuring artists on different tracks
- **Various Artists** - Compilation albums (soundtracks, etc.)

**Validates**:
- Artist name canonicalization
- Album stays together despite artist variants
- Featuring credits handled correctly
- Various Artists compilations organized properly

### 2. Classical Music

**Files**: `test_classical.py`

#### Test Cases:
- **Bach Goldberg Variations** - Composer name variants (J.S. Bach, Johann Sebastian Bach, JS Bach)
- **Beethoven Symphony No. 9** - Conductor + Orchestra credits
- **Multiple Performers** - Same work by different performers (Glenn Gould 1955 vs 1981 vs András Schiff)

**Validates**:
- Composer/performer separation
- Composer name canonicalization
- Classical music detection
- Multiple performer credits
- Same work, different performer → separate directories

### 3. Artist Name Variants

**Files**: `test_name_variants.py`

#### Test Cases:
- **Björk** - Unicode characters (Björk vs Bjork)
- **The Beatles** - "The" prefix variants
- **Sigur Rós** - Special characters
- **Ampersand variants** - "&" vs "and"

**Validates**:
- Unicode normalization
- Token normalization consistency
- Canonical name preservation
- Special character handling

### 4. Test Data

Tests use **mock fixtures** for reproducibility:

```python
@pytest.fixture
def getz_gilberto_scenario():
    """Provides mock data for Getz/Gilberto test."""
    return TestScenario(
        name="getz_gilberto",
        description="Multi-artist with name variants",
        input_files=[...],
        expected_output={...},
        mock_responses={...},
    )
```

Each scenario includes:
- Input file specifications (metadata variations)
- Expected output (canonical names, paths, release IDs)
- Mock API responses (MusicBrainz, AcoustID)

## Writing New Tests

### 1. Define Scenario

Add to `TEST_SCENARIOS.md`:

```markdown
#### Test Case X.Y: Your Test Name
- **Challenge**: What makes this difficult
- **Example**: Real-world artist/album
- **Expected**: What should happen
- **MusicBrainz ID**: `actual-mbid-here`
```

### 2. Create Fixture

Add to `conftest.py`:

```python
@pytest.fixture
def your_scenario(mock_musicbrainz_response):
    mb_response = mock_musicbrainz_response(
        release_id="mbid-here",
        album_title="Album Name",
        album_artist="Artist Name",
        tracks=[...],
    )

    return TestScenario(
        name="your_test",
        description="What it tests",
        input_files=[...],
        expected_output={...},
        mock_responses={"musicbrainz": mb_response},
    )
```

### 3. Write Test

Add to appropriate `test_*.py`:

```python
def test_your_scenario(
    your_scenario,
    create_test_audio_file,
    test_cache,
    test_library,
):
    \"\"\"Test description.\"\"\"
    # Setup
    input_dir = your_scenario.setup(test_library, create_test_audio_file)

    # Create app
    app = ResonanceApp.from_env(
        library_root=test_library,
        cache_path=test_cache,
        interactive=False,
        dry_run=False,
    )

    # Run test
    try:
        album = AlbumInfo(directory=input_dir)
        pipeline = app.create_pipeline()
        success = pipeline.process(album)

        # Assertions
        assert success
        assert album.canonical_artist == your_scenario.expected_output["canonical_artist"]
        # ... more assertions

    finally:
        app.close()
```

## Assertions to Include

Every test should verify:

1. ✅ **Tracks loaded** - All audio files detected
2. ✅ **Metadata read** - Tags extracted correctly
3. ✅ **Fingerprinting** (if not mocked) - AcoustID lookup succeeded
4. ✅ **Canonical names** - Name variants mapped correctly
5. ✅ **Release matched** - Correct MusicBrainz/Discogs release identified
6. ✅ **Score reasonable** - Match confidence >= threshold
7. ✅ **Organization** - Files moved to correct structure
8. ✅ **Enrichment** - Metadata filled from release
9. ✅ **Cache persistence** - Decision cached for re-runs

## Mock vs Real API

**Default: Mock responses** (fast, reproducible, no network)

```python
# Tests use mocked MusicBrainz/Discogs responses
mock_mb_client = MagicMock()
app.musicbrainz = mock_mb_client
```

**Optional: Real API** (slow, requires network, marked with `@pytest.mark.requires_network`)

```python
@pytest.mark.slow
@pytest.mark.requires_network
def test_real_musicbrainz_lookup(...):
    \"\"\"Test with real MusicBrainz API.\"\"\"
    # Uses actual network calls
    # Run manually to verify MBIDs are correct
```

## Continuous Integration

For CI/CD, run:

```bash
# Fast tests only (no network, no slow tests)
pytest -m "not slow and not requires_network"
```

Expected run time: < 30 seconds

## Test Coverage

Target coverage:

- **Core workflow**: 100% (identify → prompt → enrich → organize → cleanup)
- **Edge cases**: 80% (classical, multi-artist, variants)
- **Error handling**: 60% (network failures, malformed data)

## Troubleshooting

### Tests fail with "ModuleNotFoundError"

```bash
# Install test dependencies
pip install pytest pytest-mock

# Install resonance in development mode
cd resonance
pip install -e .
```

### Tests fail with "No module named 'mutagen'"

```bash
# Install audio library dependencies
pip install mutagen
```

### Tests are slow

```bash
# Skip slow tests
pytest -m "not slow"

# Or use fast mode
./run_tests.sh  # (skips slow by default)
```

## Future Enhancements

- [ ] Add tests for trio/ensemble names
- [ ] Add tests for multiple releases (remaster vs original)
- [ ] Add tests for disc numbering
- [ ] Add tests for live album dates
- [ ] Create actual audio file fixtures (small samples)
- [ ] Add performance benchmarks
- [ ] Add test for cache persistence across runs
- [ ] Add test for --unjail functionality
- [ ] Add test for --delete-nonaudio cleanup

## Real-World Validation

For production readiness, manually validate with real audio files:

1. **Get sample files** from your collection or test data
2. **Run with real API**: `./run_tests.sh network`
3. **Verify output** matches expected structure
4. **Check edge cases** that might not be covered by mocks

See `TEST_SCENARIOS.md` for specific real-world albums to test with.

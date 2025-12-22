# Real-World Corpus Test Harness

This directory contains the real-world corpus test harness for V3.1. It validates
that the full resonance workflow operates correctly on a real music library at scale.

## Overview

The real-world corpus test:
- Reads directly from your music library at `/home/tom/music`
- Runs the complete workflow deterministically (scan → resolve → plan → apply)
- **Never modifies** your library files (read-only, outputs to temp directory)
- Asserts invariants on reruns (no provider calls, no layout churn, stable tags)
- Uses the same snapshot artifact model as golden tests (state/layout/tags)

## Directory Structure

```
tests/real_corpus/
  README.md                # This file
  decisions.json           # Pinned resolution decisions for determinism
  expected_state.json      # Terminal states snapshot
  expected_layout.json     # Final paths snapshot
  expected_tags.json       # Tag snapshot
  cache_export.json        # Exported cache data for review (after first run)
```

## Safety

The test is **read-only**:

1. Reads audio files and `.meta.json` files from your library
2. All outputs (organized files, tags) written to pytest's temporary directory
3. Your library files are **never modified**
4. Override library path with `LIBRARY_PATH=/custom/path` if needed

## Quick Start

### 1. First Run: Online Mode (Populate Cache)

The first run needs network access to query providers and populate the cache.

**API Configuration**:

The test uses **MusicBrainz metadata search** (no fingerprinting yet):
- **MusicBrainz**: Your email required (no API key needed)
- **AcoustID**: Not needed (fingerprinting not implemented in V3)
- **Discogs**: Not used (would require API token)

```bash
export MUSICBRAINZ_USERAGENT="your.email@example.com"

RUN_REAL_CORPUS=1 ONLINE=1 pytest tests/integration/test_real_world_corpus.py -v
```

This will:
- Read directly from `/home/tom/music` (or `LIBRARY_PATH` if set)
- Make provider API calls (MusicBrainz)
- Cache all responses for offline use
- Resolve, plan, and apply for all directories
- Show statistics: applied/jailed/failed

**Note**: This may take several hours for large libraries due to API rate limiting.

### 2. Export Cache for Review

After the first run, export the cache data for review:

```bash
python scripts/export_real_corpus_cache.py --cache /path/to/test/cache.db
```

This generates `tests/real_corpus/cache_export.json` with:
- All provider search results
- Resolution decisions
- Directory states

### 3. Review and Curate (Optional)

Review the exported cache data:

```bash
# Use an LLM to suggest improvements
cat tests/real_corpus/cache_export.json | llm "Review this music metadata cache..."

# Or manually review for errors
less tests/real_corpus/cache_export.json
```

Update `decisions.json` with any corrections or explicit jailing decisions.

### 4. Regenerate Snapshots

After curation, regenerate the expected snapshots:

```bash
python regen_real_corpus.py
```

This runs the test with `REGEN_REAL_CORPUS=1` to update:
- `expected_state.json`
- `expected_layout.json`
- `expected_tags.json`

### 5. Subsequent Runs: Offline Mode

All subsequent runs should work offline from cache:

```bash
RUN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py -v
```

This validates:
- No provider calls made (offline-only)
- Results match expected snapshots
- Workflow is deterministic

## decisions.json - Deterministic Resolutions

To ensure deterministic test runs, `decisions.json` maps each `dir_id` to a
pinned resolution decision:

```json
{
  "01234567": {
    "provider": "musicbrainz",
    "release_id": "mb:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "89abcdef": {
    "action": "JAIL"
  }
}
```

This file is generated during the first regen run and committed to the repo.

## Offline-First

The test runs **offline by default**:
- Provider queries are served from cache
- Cache misses result in deterministic outcomes (typically JAIL state)
- Rerun produces **zero provider calls** (strict invariant)

## CI Policy

The real-world corpus test is **opt-in only** for CI:
- Skipped unless `RUN_REAL_CORPUS=1`
- Does not block normal CI runs
- Developers run locally when they have a corpus snapshot

## Expected Runtime

- **First run (ONLINE=1)**: Several hours for large libraries (~177GB)
- **Subsequent runs (offline)**: Minutes

## Troubleshooting

### Test skipped: "Opt-in: RUN_REAL_CORPUS=1"

Set the environment variable:
```bash
RUN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py
```

### Snapshot mismatch after code changes

Regenerate snapshots:
```bash
python regen_real_corpus.py
```

Then review the diff to confirm expected changes.

### Provider calls on rerun

The test enforces zero provider calls on rerun. If this assertion fails:
1. Check that cache is properly populated
2. Verify offline mode is enabled
3. Ensure no fingerprint/signature changes between runs

## Notes

- This test complements golden corpus tests (exact curated outcomes)
- Real corpus tests validate invariants and scale on realistic data
- Snapshots are deterministic (fixed clock, stable ordering, no timestamps)
- The harness reuses machinery from golden tests (`_corpus_harness.py`)
- **No copying required** - test reads directly from your library
- Test is read-only and safe - your library files are never modified

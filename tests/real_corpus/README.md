# Real-World Corpus Testing

This directory contains infrastructure for testing Resonance against real-world music libraries at scale.

## ⚠️ SAFETY FIRST

**NEVER** point these tests at your live music library. Always use snapshots/copies.

## Purpose

V3 proves correctness on curated test fixtures. V3.1 proves correctness survives real-world libraries with:
- Legacy file formats and encodings
- Deep directory structures
- Large file counts
- Mixed metadata quality
- Filesystem edge cases

## Directory Structure

```
tests/real_corpus/
├── README.md              # This file - safety guidelines & usage
├── MANIFEST.txt          # List of album directories to scan
├── decisions.json        # Scripted prompt decisions for automation
├── metadata.json         # Extracted filesystem metadata (committable)
├── expected_state.json   # Terminal states snapshot
├── expected_layout.json  # Final relative paths
└── expected_tags.json    # Tag state snapshot
```

## Workflow

### 1. Prepare Corpus
```bash
# Edit MANIFEST.txt to list desired album directories
# Edit decisions.json for scripted prompt responses

# Extract metadata from your music library (read-only, safe)
./scripts/extract_real_corpus.sh /path/to/your/music/library
```

### 2. Run Tests
```bash
# Run with real corpus enabled
RUN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py

# First run populates cache, may make network calls
# Second run should be offline no-op (zero provider calls)
```

### 3. Regenerate Expectations
```bash
# Only when expectations legitimately change
REGEN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py
```

## Safety Rules

### ❌ NEVER
- Point scripts at `/home/user/Music/` or similar live paths
- Run tests with `RUN_REAL_CORPUS=1` in CI
- Use real corpus tests for development iteration

### ✅ ALWAYS
- Extraction is read-only (never modifies source)
- Keep manifest small (10-50 albums) for fast iteration
- Verify offline rerun produces identical results
- Check that provider calls are zero on second run

## Key Differences from File Copying

### Before (File Copying - DANGEROUS):
- Copies entire music files (GBs of data)
- Requires massive disk space
- Risk of accidentally committing music files
- Slow operations (minutes/hours)

### After (Metadata Extraction - SAFE):
- Extracts only directory structure + file metadata
- Small, committable `metadata.json` (~KB)
- Zero risk to source library
- Fast extraction (seconds)

## CI Integration

Real corpus tests are **opt-in only**:
- Skipped by default (`RUN_REAL_CORPUS=1` required)
- Never run in CI pipelines
- Require manual setup but no large data transfers

## Troubleshooting

### Test Skips with "Real-world corpus metadata not present"
- Run `./scripts/extract_real_corpus.sh` to generate `metadata.json`
- Verify `MANIFEST.txt` contains valid directories

### Rerun Has Provider Calls
- Cache may be stale - clear and regenerate metadata
- Network config changed - verify offline mode
- Deterministic decisions may have changed

### Performance Issues
- Reduce manifest size
- Check for filesystem bottlenecks
- Verify offline operation (no network timeouts)

## Implementation Notes

- Tests use `FilesystemFaker` against `metadata.json`
- Tests run offline by default (cache-only)
- Network failures produce deterministic "UNSURE" results
- Zero provider calls on rerun = success
- Stable snapshots enable regression detection
- App code runs unchanged against faker

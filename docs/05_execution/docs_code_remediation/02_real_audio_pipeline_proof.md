# Sprint 02 — Real Audio Pipeline Proof

**Order:** 02 of 07  
**Theme:** Behavioral proof  
**Audit reference:** Divergence matrix row 5 (provider-backed resolution), row 7 (transaction/rollback), §6 Critical gap 2 (no real audio processing proven anywhere)

---

## Why this sprint exists

The audit found that no test, script, or workflow has ever processed a real audio file through the Resonance pipeline. Every test uses either `.meta.json` sidecar files, empty stub files, or pre-computed fixture data. The `MutagenTagWriter` — the component that actually writes tags to audio files — has never been exercised in any verified workflow.

This is not a minor gap. Resonance's entire product promise is to organize audio files. If the pipeline has never been observed working on real audio, the "trusted automation" guarantee is entirely rhetorical.

This sprint proves the pipeline on real audio files in a controlled integration test.

---

## Problem statement

No integration test or user-facing workflow exercises:
- `FingerprintReader` extracting a fingerprint from a real audio file
- `MutagenTagWriter` writing tags to a real audio file
- Tag readback from a real audio file after apply confirms written values

The gap exists because all tests use `.meta.json` sidecars as a proxy for audio content, and the "real" corpus workflow uses empty stub files + `FakerContext` monkey-patching.

---

## Target outcome

When this sprint is genuinely complete:

- A new integration test exists that:
  1. Scans a small directory of real audio files (≥ 3 tracks, real FLAC or MP3)
  2. Resolves using pre-cached provider responses (no live API calls in CI)
  3. Plans file moves and/or tag updates
  4. Applies the plan using `MutagenTagWriter`
  5. Reads tags back from the modified audio files using `mutagen` directly
  6. Asserts the read-back values match the expected tag values
- The test runs in CI without API keys
- The test does not use `FakerContext`, empty stub files, or `.meta.json` sidecar substitutes for audio content
- Any bugs found in `FingerprintReader` or `MutagenTagWriter` during this sprint are fixed

---

## In scope

- **New integration test file** (e.g., `tests/integration/test_real_audio_pipeline.py`) with a small real-audio fixture
- **Small audio fixture** (3–5 real FLAC or MP3 files in `tests/fixtures/real_audio/`) — minimal, royalty-free, or synthetically generated test audio
- **`resonance/core/fingerprint.py`** — fix any bugs discovered during integration
- **`resonance/services/tag_writer.py`** — fix any bugs discovered when `MutagenTagWriter` is exercised
- **Pre-cached provider responses** for the fixture's audio content (stored as fixture JSON, not requiring API calls)
- Documentation of the fixture format in a brief comment or README in `tests/fixtures/real_audio/`

---

## Out of scope

- Do not change `scripts/`, Makefile targets, or corpus workflow scripts
- Do not change the golden corpus test suite
- Do not add API calls; use pre-cached responses only
- Do not implement fingerprinting of the real corpus (that is Sprint 04)
- Do not change the review bundle or HTML interface
- Do not change CLI commands (that was Sprint 01)
- Do not attempt to process more than 5 directories in this sprint

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §6 Critical gap 2
- `resonance/core/fingerprint.py`
- `resonance/services/tag_writer.py` — both `MetaJsonTagWriter` and `MutagenTagWriter`
- `tests/integration/test_golden_corpus.py` — read-only, to understand the existing end-to-end pattern
- `tests/integration/_corpus_harness.py` — to understand snapshot utilities
- `docs/dev/testing_strategy.md`
- `docs/dev/fixtures_and_corpus.md`

---

## Implementation requirements

1. **Create a small real-audio fixture.** Generate or obtain 3–5 audio files (FLAC or MP3) with minimal content. These must be actual audio files readable by `mutagen` — not empty files. The files should represent 1–2 artist/album combinations to allow a realistic but minimal resolution scenario.

2. **Create pre-cached provider responses.** For the fixture's content, create a cache database or fixture JSON that the `CachedProviderClient` will serve without making live API calls. This means the test is fully deterministic and CI-safe.

3. **Write the integration test.** The test must:
   - Call `resonance scan` (or invoke `run_scan` directly) on the fixture directory
   - Call `resonance resolve` (or equivalent) using the pre-cached provider responses
   - Call `resonance plan` to produce a plan
   - Call `resonance apply` using `MutagenTagWriter` (not `MetaJsonTagWriter`)
   - Use `mutagen` directly to read tags from the output files and assert they match expected values
   - Run entirely offline (no live API calls)

4. **Do not use FakerContext.** The test must operate on real filesystem paths and real audio files. If `FingerprintReader` requires AcoustID and AcoustID is unavailable in CI, use pre-extracted fingerprints stored in the cache fixture — the fingerprint extraction path can be tested separately if needed.

5. **Fix bugs found during integration.** If `MutagenTagWriter` or `FingerprintReader` fail during this test, fix the bugs. Do not stub them out.

---

## Acceptance criteria

1. Running the new integration test produces a passing result with zero errors.
2. The test produces at least one output audio file whose tags can be read back with `mutagen` directly.
3. At least one tag field (e.g., `ALBUM`, `ARTIST`, or `TITLE`) written by `MutagenTagWriter` is verified by reading it back from the audio file in the test assertions.
4. The test does not use `FakerContext`, empty `.touch()` files, or `.meta.json` sidecars as stand-ins for audio content.
5. The test passes in CI without environment variables for API keys.
6. `pytest tests/integration/test_real_audio_pipeline.py -v` passes cleanly.

---

## Required evidence

The executor must produce and preserve:

1. **Test output** from `pytest tests/integration/test_real_audio_pipeline.py -v` showing passing assertions.
2. **Tag readback assertion output** — the test should print or assert the specific field/value pair that was written and read back. Include this output in the evidence.
3. **Confirmation that the fixture audio files are real (not empty)** — e.g., `file tests/fixtures/real_audio/*.flac` or `python -c "import mutagen; print(mutagen.File('tests/fixtures/real_audio/track1.flac').info.length)"` showing a non-zero duration.
4. **Confirmation that no live API calls are made** — the test should complete without `MUSICBRAINZ_USERAGENT`, `ACOUSTID_API_KEY`, or `DISCOGS_TOKEN` being set.

---

## Failure conditions

This sprint is NOT complete if:

- The "real audio" test uses `FakerContext` or `os.path` monkey-patching
- Audio files are empty (0 bytes) or not readable by `mutagen`
- The test calls live provider APIs (requires environment variables to pass)
- The apply step uses `MetaJsonTagWriter` instead of `MutagenTagWriter`
- Tags are asserted in the test by reading a `.meta.json` sidecar, not the audio file itself
- The test is marked as skipped in CI (`@pytest.mark.skip` or environment flag guard)

---

## Dependencies

- **Sprint 01 must be proven complete** before this sprint begins. The test baseline must be clean (zero failures) before adding new tests.

---

## Notes for executor

- If generating test audio files, a silent 5-second FLAC or MP3 is sufficient. The content does not matter; what matters is that `mutagen` can read and write it.
- Tools like `sox` (`sox -n -r 44100 -c 2 output.flac trim 0.0 5.0`) can generate silent test audio.
- The pre-cached provider response can be a minimal JSON fixture that `CachedProviderClient` will serve as a cache hit. Look at how existing integration tests construct their provider stubs.
- Do not attempt fingerprinting in CI if AcoustID binary is unavailable. Store a pre-extracted fingerprint ID in the cache fixture instead. Fingerprinting of the full corpus is a concern for Sprint 04.
- MutagenTagWriter tag keys vary by format (FLAC uses Vorbis comment keys, MP3 uses ID3). Verify the test uses the correct key names for the format being tested.

---

## Executor prompt

```
You are implementing Sprint 02 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/02_real_audio_pipeline_proof.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

Sprint 01 must be proven complete (pytest green, full CLI surface) before you begin.

Your task:
1. Read the sprint file in full.
2. Read all files in "Required reading".
3. Create a small real-audio fixture (3–5 FLAC or MP3 files) in tests/fixtures/real_audio/.
4. Create pre-cached provider responses for the fixture content.
5. Write tests/integration/test_real_audio_pipeline.py that runs scan → resolve → plan → apply (MutagenTagWriter) → tag readback on real audio files.
6. Fix any bugs discovered in FingerprintReader or MutagenTagWriter.

Do not:
- Use FakerContext or empty stub files
- Call live APIs (test must pass without API keys)
- Change scripts/, Makefile, or the golden corpus test suite
- Use MetaJsonTagWriter in the apply step

Required evidence before declaring success:
1. pytest tests/integration/test_real_audio_pipeline.py -v output (all passing)
2. Tag readback assertion showing a specific field/value written and confirmed
3. Proof audio files are real (non-zero duration readable by mutagen)
4. Proof no live API calls are required

Do not claim success without this evidence.
```

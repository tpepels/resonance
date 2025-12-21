# Canonicalization & Golden Corpus Determinism Audit

**Date:** 2025-12-21
**Scope:** Determinism audit for golden corpus scenarios and canonicalization dependencies

---

## Executive Summary

**Current corpus:** 26 scenarios (25 snapshot-backed + 1 scanner-skip)
**Deferred (requires match_key canonicalization):** 3 scenarios
**Integration tests (not golden corpus):** 2 scenarios
**Skip (non-deterministic):** 1 scenario

---

## 1. Current Golden Corpus (26 scenarios)

### Snapshot-backed (25)
1. `standard_album`
2. `multi_disc`
3. `compilation`
4. `name_variants`
5. `classical`
6. `extras_only`
7. `single_track`
8. `mixed_media`
9. `multi_composer`
10. `long_titles`
11. `renamed_mid_processing`
12. `missing_middle_tracks`
13. `case_only_rename`
14. `interrupted_apply`
15. `opus_normalization`
16. `conductor_vs_performer`
17. `multi_performer_work`
18. `catalog_variants`
19. `partial_opera`
20. `partial_tags`
21. `duplicate_files`
22. `remaster_vs_original`
23. `hidden_track`
24. `unicode_normalization`
25. `invalid_year`

### Scanner-skip validated (1)
- `non_audio_only`

All scenarios above are deterministic with fixed fingerprints/tags/paths.

---

## 2. Deferred (Requires Canonicalization)

These require match_key canonicalization and are deferred until that system exists:

- `featured_artist` (feat/ft/featuring normalization)
- `work_nickname` ("Eroica" ⇔ "Symphony No. 3")
- `ensemble_variants` ("LSO" ⇔ "London Symphony Orchestra")

---

## 3. Integration Tests (Not Golden Corpus)

These require multi-directory setups and should live in dedicated integration tests:

- `GC-8` orphaned track reunification
- `GC-9` split album across dirs

---

## 4. Skip (Non-Deterministic)

- `GC-16` mixed encoding tags (mojibake)

---

## Next Steps

1. Start V3 provider integration (Discogs + MB) with deterministic fixtures.
2. Expand tag writing tests for MP3/M4A with canonical mapping.
3. Keep deferred scenarios in TDD_TODO_V3 until match_key canonicalization is implemented.

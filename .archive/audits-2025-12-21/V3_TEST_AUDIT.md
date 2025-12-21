# V3 Test Audit - Definition of Done Compliance

**Date:** 2025-12-21
**Scope:** Audit current test suite against V3 DoD requirements

---

## V3 Definition of Done (from TDD_TODO_V3.md)

V3 is done when:

1. ✅/⚙️ **Core invariants gate is green** (golden corpus + identity + canonicalization + idempotency + no-network-on-rerun)
2. ⚙️ **Discogs and MB integrated** with stable candidate canonicalization and ranking
3. ⚙️ **Apply writes tags correctly** for FLAC/MP3/M4A with provider IDs and overwrite policy
4. ⚙️ **Move/rename behavior correct** across multi-disc, compilations, collisions, extras
5. ⚙️ **Big 10 suite is green** and reruns are clean

---

## Executive Summary

**Current Status:**
- ✅ **Golden Corpus:** 26 scenarios in code
- ✅ **Snapshots:** All audio-backed scenarios have snapshots; `non_audio_only` is validated via scanner skip
- ✅ **Provider Fixtures:** All 26 scenarios have fixtures in musicbrainz.json
- ✅ **Canonicalization-Gated Scenarios Deferred:** `featured_artist`, `work_nickname`, `ensemble_variants`
- 🟡 **Core Gate:** Green for current corpus; remaining V3 work is provider integration + tagging/moves + Big 10

---

## 1. Golden Corpus Status (DoD Requirement #1)

### 1.1 Scenarios with Snapshots ✅ (25/26)

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

### 1.2 Scenarios validated via skip ✅ (1/26)

- `non_audio_only` (scanner skip asserted in `test_golden_corpus_end_to_end`)

**Test status:** `tests/integration/test_golden_corpus.py` passes with regen.

---

## 2. Deferred / Non-Golden Items

**Deferred (requires match_key canonicalization):**
- `featured_artist`
- `work_nickname`
- `ensemble_variants`

**Integration tests (not golden corpus):**
- `GC-8` orphaned track reunification (multi-path setup)
- `GC-9` split album across dirs (multi-directory setup)

**Skip (non-deterministic):**
- `GC-16` mixed encoding tags (mojibake)

---

## 3. DoD Progress Notes

- **Core gate:** green for current corpus (identity + layout + tagging + idempotency invariants for stubbed data).
- **Provider integration / tagging / move semantics:** pending V3 phases (Discogs/MB/tagging/moves).
- **Big 10 suite:** not started.

---

## Actionable Plan (Next)

1. Start provider integration (Discogs + MB) and matching heuristics (sections 1–3 in TDD_TODO_V3).
2. Expand tag writing tests for MP3/M4A and canonical tag mapping (section 4).
3. Add Big 10 scenario suite once providers and tagging are stable.

# Resonance Test Suite Reality Audit

**Date:** 2025-07-11
**Scope:** Full test suite — 524 collected, 518 passed, 6 skipped
**Baseline:** 483 `def test_` functions across 76 files (313 unit, 149 integration, 18 legacy)
**Method:** Every test file read at function level; every product doc, system doc, remediation doc, and governance doc cross-referenced.

---

## 1. Executive Verdict

**The Resonance test suite is fundamentally sound.** Unlike the state found in the DOCS_TO_CODE_DIVERGENCE_AUDIT, where "documentation describes a product that doesn't yet exist as a working system," the current suite — after five remediation sprints — now defends the real product at every critical layer.

Of 483 test functions:

- **~78%** defend observable product behavior or stable domain contracts
- **~12%** defend component internals that have reasonable proportionality
- **~4%** are infrastructure tests for test tooling (FilesystemFaker)
- **~4%** are legacy tests for deprecated code
- **~2%** are structurally overspecified or redundant

The suite does **not** trap implementation in synthetic compliance. The most important product guarantees — replay determinism (G4), loud failure on mismatch (G5), real mode actually being real (G8), safe file operations (applier + crash recovery) — are defended by focused, behavioral tests.

**Key strengths:**
- The replay proof cycle (record → replay → alter → fail) is a textbook behavioral acceptance test
- Real audio pipeline test proves G8 with actual FLAC files and MutagenTagWriter
- The applier cluster (37 tests) is proportionate to the most dangerous operation in the product
- Canonicalization tests (39) defend real-world artist name handling without mocking

**Key weaknesses:**
- Only 1 test uses real audio files (test_real_audio_pipeline)
- E2E workflow coverage is thin (3 tests in test_e2e_cli_workflow)
- 15 tests defend deprecated infrastructure (FilesystemFaker/FakerContext)
- 18 legacy tests run but protect nothing in the current product
- Guarantee G6 (review usable at scale) has minimal direct coverage
- Guarantee G10 (tests serve the product) has no self-test — this audit is it

---

## 2. Product-Truth Map

### Product Guarantees (from product_guarantees.md)

| # | Guarantee | Core Claim |
|---|-----------|-----------|
| G1 | No silent invention of authority | Uncertain cases marked uncertain; no hidden guesswork |
| G2 | Important decisions are inspectable | Evidence, interpretation, action, ambiguity visible |
| G3 | Ambiguity is first-class | Unresolved is a valid outcome; system distinguishes incomplete from final |
| G4 | Replay deterministic when assumptions match | Same decision situation → same outcome |
| G5 | Replay fails loudly on mismatch | Hard failure, not silent drift |
| G6 | Review usable at realistic corpus size | Chunked, navigable outputs |
| G7 | Primary workflows remain simple | `make corpus-decide` / `make corpus-review` |
| G8 | Real mode is actually real | Real orchestration, providers, prompting, artifacts |
| G9 | Acceptance is behavioral | Observed execution, not just "code exists" |
| G10 | Tests serve the product | Suite protects behavior, doesn't replace the spec |

### User Jobs (from user_jobs.md)

| # | Job | Success Signal |
|---|-----|---------------|
| J1 | Understand what is in my library | Grounded mental model of collection |
| J2 | Understand what each folder represents | Directory = release-level object with evidence |
| J3 | Identify what needs attention | Surface pain points: ambiguity, conflicts, anomalies |
| J4 | See what cleaner organization would be | Proposed normalized layout |
| J5 | Decide when system acts vs I decide | Trust escalation of right cases |
| J6 | Review without reading internals | Structured outputs, review UI |
| J7 | Preserve accepted decisions over time | Stable replay of past judgments |

---

## 3. Current Test Map

### By Layer

| Layer | Files | Functions | % of Suite |
|-------|------:|----------:|-----------:|
| Unit | 29 | 313 | 65% |
| Integration | 34 | 149 | 31% |
| Legacy | 6 | 18 | 4% |
| Helpers/conftest | 7 | — | — |
| **Total** | **76** | **483** | **100%** |

### By Functional Cluster

| Cluster | Files | Functions | Parameterized Total |
|---------|------:|----------:|--------------------:|
| **Canonicalization & identity** | 4 | 100 | ~110 |
| test_canonicalize (39), test_identity (22), test_identity_signature (18), test_heuristics (21) | | | |
| **Identification & resolution** | 4 | 58 | ~58 |
| test_identifier (23), test_resolver (13), test_planner (17), test_settings_hash (5) | | | |
| **Apply & crash safety** | 3 | 40 | ~40 |
| test_applier (29), test_crash_recovery (8), test_idempotency_contracts (3) | | | |
| **Provider layer** | 8 | 42 | ~42 |
| test_caching_provider (9), test_enricher (6), test_scanner (10), test_provider_cache (7), test_discogs_provider (6), test_musicbrainz_provider (1), test_provider_fusion_dedupe (2), test_cache_bounding (2) | | | |
| **Tag & file operations** | 5 | 38 | ~38 |
| test_tag_writer-unit (3), test_tag_writer-integration (13), test_file_service (13), test_tag_mapping (9) | | | |
| **Transaction & state** | 3 | 55 | ~55 |
| test_transaction (32), test_directory_state (18), test_artifacts (5) | | | |
| **Corpus & workflow E2E** | 5 | 12 | ~42 |
| test_golden_corpus (1→29), test_real_world_corpus (4), test_e2e_cli_workflow (3), test_real_audio_pipeline (1), test_phase_d_big10 (1→10) | | | |
| **Replay & prompt** | 4 | 14 | ~14 |
| test_replay_proof (3), test_prompt_cli_wrapper (5), test_prompt_cli (3), test_fingerprint_reader (12) | | | |
| **CLI surface** | 6 | 19 | ~19 |
| test_scan_cli (5), test_resolve_cli_simple (3), test_apply_cli_backend (4), test_exit_codes (3), test_cli_smoke (1), test_audit_doctor_rollback (6) | | | |
| **Integration misc** | 8 | 31 | ~31 |
| test_acoustid_provider (8), test_acoustid_integration (7), test_musicbrainz_heuristics (5), test_filesystem_edge_cases (7), test_metadata_channel (6), test_discogs_cache_semantics (2), test_provider_fusion (3), test_layout_rules (3) | | | |
| **Invariant** | 2 | 4 | ~4 |
| test_no_rematch_invariant (2), test_audit_stability (2) | | | |
| **Coverage & wiring** | 2 | 8 | ~8 |
| test_coverage_gates (7), test_legacy_imports (1) | | | |
| **Test infrastructure** | 1 | 15 | ~15 |
| test_filesystem_faker (15) | | | |
| **Legacy** | 6 | 18 | ~18 |
| test_discogs_client (6), test_metadata_reader (1), test_musicbrainz_client (3), test_prescan_cli (4), test_provider_offline (2), test_release_search_discogs (2) | | | |
| **Other** | 4 | 9 | ~9 |
| test_mb_idempotency (1), test_no_rematch_invariant (2), test_cache_schema (1), test_settings_defaults (1), test_audit_critical (2) | | | |

---

## 4. Classification Matrix

Each cluster is classified using these categories:

- **PRODUCT-CRITICAL**: Directly defends a product guarantee or user job; removal would leave a guarantee unproven
- **COMPONENT-USEFUL**: Defends a stable component contract; valuable but not irreplaceable at this level
- **STRUCTURALLY-OVERSPECIFIED**: Tests more than necessary for the behavior defended; refactoring opportunity
- **LEGACY**: Tests deprecated code paths; provides no active product protection
- **DISTORTING**: Creates false confidence or incentivizes synthetic compliance
- **REDUNDANT**: Covered by another test at higher fidelity

| Cluster | Tests | Classification | Guarantees | Rationale |
|---------|------:|---------------|-----------|-----------|
| test_replay_proof | 3 | **PRODUCT-CRITICAL** | G4, G5 | Only test that proves the full record→replay→alter→fail cycle. Directly behavioral. |
| test_real_audio_pipeline | 1 | **PRODUCT-CRITICAL** | G8 | Only test using real FLAC files with MutagenTagWriter. Proves G8 is not theatrical. |
| test_e2e_cli_workflow | 3 | **PRODUCT-CRITICAL** | G7, J1, J5 | Only test of the primary CLI workflow (scan→resolve→prompt). Thin but critical. |
| test_golden_corpus | 1 (→29) | **PRODUCT-CRITICAL** | G1, G2, G4, J4, J7 | 29-scenario determinism firewall. Uses FilesystemFaker (not real audio) but defends snapshot stability across the full pipeline. |
| test_phase_d_big10 | 1 (→10) | **PRODUCT-CRITICAL** | G1, G3, G4, J2, J4 | 10 diverse scenarios proving deterministic identification, correct layout, tag correctness, and no-rematch. High signal density. |
| test_applier | 29 | **PRODUCT-CRITICAL** | G1, J4 | Defends the most dangerous operation: moving/renaming user files. Security tests (path traversal, collision) are especially high-value. |
| test_crash_recovery | 8 | **PRODUCT-CRITICAL** | G1 | 8 distinct failure scenarios for file operations. Each is a real-world risk. |
| test_idempotency_contracts | 3 | **PRODUCT-CRITICAL** | G4, J7 | Proves apply-twice-is-noop and no-requery invariants. |
| test_real_world_corpus | 4 | **PRODUCT-CRITICAL** | G8, G9 | Real provider APIs, real metadata. Opt-in (4 of 6 skips). Proves G9 behaviorally. |
| test_identifier | 23 | **PRODUCT-CRITICAL** | G1, G3, J2 | Scores and tiers are the core decision model. Boundary tests at tier thresholds prevent silent confidence inflation. |
| test_identity_signature | 18 | **PRODUCT-CRITICAL** | G4, J7 | Proves "same content = same ID" and "changed content = new ID." Foundation for replay and no-rematch. |
| test_audit_doctor_rollback | 6 | **PRODUCT-CRITICAL** | G2, J3 | Audit, doctor, and rollback are user-facing commands protecting inspectability. |
| test_exit_codes | 3 | **PRODUCT-CRITICAL** | G5, G7 | Exit code contracts are the shell-level guarantee interface. |
| test_canonicalize | 39 | **COMPONENT-USEFUL** | J2, J4 | All input/output tests for real artist names. Well-proportioned. Could be product-critical if canonicalization bugs cause misidentification. |
| test_identity | 22 | **COMPONENT-USEFUL** | J4 | Display form and folder name contracts. Pure, no mocks. |
| test_heuristics | 21 | **COMPONENT-USEFUL** | J1, J2 | Path-based metadata guessing. Real-world directory patterns. |
| test_transaction | 32 | **COMPONENT-USEFUL** | G1 | Commit/rollback/recovery tests are vital (20 tests). Serialization tests are slightly heavy (12 tests). |
| test_directory_state | 18 | **COMPONENT-USEFUL** | J7 | State machine contracts. Could be covered by higher-level tests but isolation is useful. |
| test_planner | 17 | **COMPONENT-USEFUL** | J4 | Plan generation logic. Pure transformations. |
| test_resolver | 13 | **COMPONENT-USEFUL** | G1, J2 | Resolution logic contracts. |
| test_file_service | 13 | **COMPONENT-USEFUL** | J4 | File operation contracts (move, copy, tag read). |
| test_tag_writer (unit+integration) | 16 | **COMPONENT-USEFUL** | G2, J4 | Tag writing and readback. Integration tests with real tmp_path are higher value. |
| test_scanner | 10 | **COMPONENT-USEFUL** | J1 | Scanner discovers audio directories. |
| test_tag_mapping | 9 | **COMPONENT-USEFUL** | G2 | Tag field mapping contracts. |
| test_caching_provider | 9 | **COMPONENT-USEFUL** | G4 | Cache hit/miss/expiry behavior. |
| test_provider_cache | 7 | **COMPONENT-USEFUL** | G4 | Lower-level cache contracts. |
| test_enricher | 6 | **COMPONENT-USEFUL** | J2 | Evidence enrichment logic. |
| test_discogs_provider | 6 | **COMPONENT-USEFUL** | J2 | Discogs adapter contracts. |
| test_fingerprint_reader | 12 | **COMPONENT-USEFUL** | G4 | Fingerprint parsing and validation. |
| test_acoustid_provider | 8 | **COMPONENT-USEFUL** | J2 | AcoustID adapter contracts. |
| test_acoustid_integration | 7 | **COMPONENT-USEFUL** | J2 | AcoustID end-to-end with mock server. |
| test_musicbrainz_heuristics | 5 | **COMPONENT-USEFUL** | J2 | MB-specific scoring heuristics. |
| test_metadata_channel | 6 | **COMPONENT-USEFUL** | J1 | Metadata channel pipeline. |
| test_scan_cli | 5 | **COMPONENT-USEFUL** | G7, J1 | CLI surface for scan command. |
| test_prompt_cli_wrapper | 5 | **COMPONENT-USEFUL** | G7, J5 | Prompt CLI wrapper. |
| test_prompt_cli | 3 | **COMPONENT-USEFUL** | G7, J5 | Prompt CLI direct. |
| test_resolve_cli_simple | 3 | **COMPONENT-USEFUL** | G7 | Resolve CLI surface. |
| test_apply_cli_backend | 4 | **COMPONENT-USEFUL** | G7 | Apply CLI backend. |
| test_provider_fusion | 3 | **COMPONENT-USEFUL** | J2 | Provider result merging. |
| test_discogs_cache_semantics | 2 | **COMPONENT-USEFUL** | G4 | Cache semantics for Discogs. |
| test_layout_rules | 3 | **COMPONENT-USEFUL** | J4 | Layout target computation. |
| test_no_rematch_invariant | 2 | **COMPONENT-USEFUL** | G4 | No-rematch after resolution. 1 of 2 skipped (needs real audio). |
| test_audit_stability | 2 | **COMPONENT-USEFUL** | G2 | Audit output stability. |
| test_mb_idempotency | 1 | **COMPONENT-USEFUL** | G4 | MB-specific idempotency. |
| test_provider_fusion_dedupe | 2 | **COMPONENT-USEFUL** | J2 | Deduplication in fusion. |
| test_settings_hash | 5 | **COMPONENT-USEFUL** | G4 | Settings hash stability. |
| test_artifacts | 5 | **COMPONENT-USEFUL** | G2 | Artifact structure validation. |
| test_filesystem_edge_cases | 7 | **COMPONENT-USEFUL** | J4 | Edge cases (symlinks, unicode, permissions). 2 of 7 skipped. |
| test_audit_critical | 2 | **COMPONENT-USEFUL** | G2 | Critical audit path. |
| test_cli_smoke | 1 | **COMPONENT-USEFUL** | G7 | CLI entry point exists. |
| test_coverage_gates | 7 | **STRUCTURALLY-OVERSPECIFIED** | G7 | Module wiring smoke tests. Bootstrap and env loading are fine; the 7-test count is disproportionate for wiring verification. |
| test_settings_defaults | 1 | **COMPONENT-USEFUL** | G7 | Default settings validation. |
| test_cache_schema | 1 | **COMPONENT-USEFUL** | G4 | Cache schema version check. |
| test_cache_bounding | 2 | **COMPONENT-USEFUL** | G4 | Cache size limits. |
| test_legacy_imports | 1 | **REDUNDANT** | — | Verifies deprecated import paths still resolve. Provides no product protection. |
| test_filesystem_faker | 15 | **DISTORTING** | — | Tests deprecated infrastructure (FakerContext). Creates maintenance cost for tooling that is being removed. FilesystemFaker itself is still used by golden corpus, but FakerContext is not. |
| Legacy (6 files) | 18 | **LEGACY** | — | Auto-marked `pipeline_v1`. Tests V2 Discogs/MB clients, prescan CLI, offline provider. None of these code paths are part of the current product. |

### Classification Summary

| Classification | Functions | % |
|----------------|----------:|---:|
| PRODUCT-CRITICAL | 102 | 21% |
| COMPONENT-USEFUL | 332 | 69% |
| STRUCTURALLY-OVERSPECIFIED | 7 | 1% |
| LEGACY | 18 | 4% |
| DISTORTING | 15 | 3% |
| REDUNDANT | 1 | <1% |

---

## 5. Distortion Findings

### D1: FilesystemFaker test cluster tests deprecated infrastructure

**Location:** [tests/unit/test_filesystem_faker.py](tests/unit/test_filesystem_faker.py) — 15 tests
**Distortion type:** Maintenance gravity toward dead code
**Evidence:** FakerContext is imported by exactly 1 test file (this one). All scripts removed it in Sprint 04. The class still exists in `_filesystem_faker.py` but `FakerContext` is not used by any product code or any other test.
**Risk:** Contributors see 15 green tests and assume FakerContext is important. New code might adopt it.
**Recommendation:** Delete test_filesystem_faker.py. If FilesystemFaker (not FakerContext) needs testing, those tests belong in the golden corpus that uses it.

### D2: Golden corpus uses FilesystemFaker, not real audio

**Location:** [tests/integration/test_golden_corpus.py](tests/integration/test_golden_corpus.py) — 29 scenarios
**Distortion type:** Confidence gap between test reality and product reality
**Evidence:** All 29 golden scenarios use `corpus_builder` with `.meta.json` sidecars and `MetaJsonTagWriter`. No real audio is processed. The pipeline exercises scan→resolve→plan→apply, but the "apply" writes `.meta.json` files, not Mutagen tags on FLAC files.
**Risk:** The golden corpus proves pipeline logic determinism but cannot prove G8 (real mode is real). Someone looking at "29 passing scenarios" might assume audio is involved.
**Mitigating factor:** test_real_audio_pipeline.py separately proves real Mutagen tag writing. The golden corpus explicitly serves a different purpose (snapshot determinism).
**Recommendation:** Add a header comment to test_golden_corpus.py stating its scope: "This test proves pipeline logic determinism using synthetic fixtures. For real audio proof, see test_real_audio_pipeline.py." No code change needed.

### D3: Legacy tests create false green surface area

**Location:** [tests/legacy/](tests/legacy/) — 6 files, 18 tests
**Distortion type:** Green tests for dead code
**Evidence:** All 6 files test V2 code paths (Discogs client, MusicBrainz client, prescan CLI, offline provider, metadata reader) that are not part of the current architecture. They are auto-marked `pipeline_v1` but still collected and run.
**Risk:** 18 passing tests contribute to the green count without protecting anything real.
**Recommendation:** Move to a `tests/archived/` directory excluded from default collection, or delete. The governance doc already has a legacy retirement policy.

### D4: Single real-audio test is a thin proof for G8

**Location:** [tests/integration/test_real_audio_pipeline.py](tests/integration/test_real_audio_pipeline.py) — 1 test
**Distortion type:** Insufficiency, not distortion
**Evidence:** This single test proves real FLAC → scan → resolve → plan → apply → Mutagen readback. It covers 1 album with 3 tracks. No multi-disc, no compilation, no unicode artist, no edge cases.
**Risk:** G8 is proved for the happy path but not for diverse scenarios.
**Recommendation:** Expand to 3-5 real audio scenarios covering multi-disc, unicode, and edge cases (similar to phase_d_big10 coverage but with real FLAC files).

### D5: test_coverage_gates is wiring verification masquerading as product tests

**Location:** [tests/integration/test_coverage_gates.py](tests/integration/test_coverage_gates.py) — 7 tests
**Distortion type:** Category confusion
**Evidence:** Tests verify that `ResonanceApp` constructs, that env vars load, that `AcoustIDClient` takes an API key. These are module wiring checks, not product behavior tests.
**Risk:** Low. The tests are harmless and fast. But they occupy the integration test directory and create a false impression of integration coverage depth.
**Recommendation:** Rename to `test_bootstrap_smoke.py` to clarify purpose. No other change needed.

---

## 6. Gaps in Product-Critical Coverage

### Gap 1: G6 — Review usable at realistic corpus size — WEAK

**Current coverage:** test_e2e_cli_workflow checks `--json` mode outputs structured JSON. test_real_world_corpus checks snapshot gating. No test verifies that review output is chunked, navigable, or doesn't degrade at scale.
**Impact:** The review bundle format was expanded in Sprint 03 but has no behavioral test verifying the contract.
**Recommended test:** Add `test_review_bundle_structure.py` asserting that the review bundle for a 50+ directory corpus is chunked, has a decision anatomy section, and each entry has inspectable evidence.

### Gap 2: G3 — Ambiguity as first-class outcome — INDIRECT

**Current coverage:** test_phase_d_big10 proves decoy doesn't win. test_coverage_gates checks unjail. But no test explicitly creates an ambiguous scenario where QUEUED_PROMPT is the correct outcome because evidence is insufficient for auto-resolution.
**Impact:** The "ambiguity is normal" guarantee is implied but not directly proved.
**Recommended test:** Add a scenario where two candidates score identically and the system correctly escalates to QUEUED_PROMPT rather than picking one.

### Gap 3: Multi-format audio — NOT TESTED

**Current coverage:** test_real_audio_pipeline uses FLAC only. No MP3, OGG, or other format tests.
**Impact:** Low immediate risk (Mutagen handles multiple formats), but the product guarantee doesn't specify FLAC-only.
**Recommended test:** Add 1 real-audio scenario with MP3 or OGG fixtures.

### Gap 4: Concurrent/parallel safety — NOT TESTED

**Current coverage:** Zero tests for concurrent access to the library or state store.
**Impact:** Low (single-user CLI tool), but the transaction system implies crash-safety expectations.
**Recommended test:** Low priority. Document as non-goal or add 1 concurrent-write test for the state store.

### Gap 5: E2E workflow breadth — THIN

**Current coverage:** 3 tests in test_e2e_cli_workflow cover scan→resolve→prompt, idempotent rerun, and JSON mode. No test covers: audit→doctor→rollback CLI chain, `make corpus-decide`/`make corpus-review` targets, or the prompt→jail→unjail cycle via CLI.
**Impact:** G7 ("primary workflows remain simple") is tested for the happy path but not for the recovery/inspection paths.
**Recommended test:** Add 2-3 E2E tests for audit→review, jail→unjail, and the Makefile targets.

---

## 7. Recommended Target Test Architecture

### Principles

1. **Product guarantees are the test specification.** Every guarantee should have at least one behavioral test that proves it end-to-end.
2. **Tests at the highest meaningful level.** Prefer workflow tests over unit tests when both could prove the same guarantee.
3. **Real audio is the gold standard.** Expand real audio coverage as the primary improvement vector.
4. **Legacy tests are garbage-collected, not maintained.** Remove or archive anything that doesn't protect current behavior.
5. **Infrastructure tests are proportionate to usage.** If a fixture library serves N tests, it gets ~N/10 tests of its own — no more.

### Target Layer Model

```
Layer 4: Real Corpus Acceptance  (opt-in, real APIs)     ~10 tests
    ↑ test_real_world_corpus — already exists
    
Layer 3: Workflow E2E            (fake providers, real FS) ~25 tests
    ↑ test_e2e_cli_workflow, test_replay_proof, test_real_audio_pipeline
    ↑ ADD: review bundle, ambiguity escalation, audit→doctor→rollback chain
    
Layer 2: Component Contracts     (unit + integration)     ~350 tests
    ↑ All current COMPONENT-USEFUL tests
    ↑ This layer is well-proportioned; no major changes needed
    
Layer 1: Snapshot Determinism    (golden corpus)           ~40 tests
    ↑ test_golden_corpus (29), test_phase_d_big10 (10)
    ↑ This layer is the stability firewall
```

### Specific Changes

| Action | Tests Affected | Net Change |
|--------|---------------|------------|
| Delete test_filesystem_faker.py | -15 | -15 |
| Archive legacy/ to tests/archived/ (exclude from default) | -18 | -18 |
| Delete test_legacy_imports.py | -1 | -1 |
| Add test_review_bundle_structure.py | +3 | +3 |
| Add ambiguity escalation scenario | +1 | +1 |
| Expand test_real_audio_pipeline to 3-5 scenarios | +2-4 | +2-4 |
| Add E2E audit→doctor→rollback chain test | +2 | +2 |
| Rename test_coverage_gates → test_bootstrap_smoke | 0 | 0 |
| Add scope comment to test_golden_corpus.py | 0 | 0 |
| **Net** | | **-26 to -24** |

**Target suite:** ~498-500 tests (from 524), with higher guarantee coverage density.

---

## 8. Recommended Follow-Up Portfolio

### Sprint 06: Test Suite Hygiene — COMPLETE

| Task | Priority | Status |
|------|----------|--------|
| Delete test_filesystem_faker.py | P1 | DONE — 15 distorting tests removed |
| Archive tests/legacy/ to tests/archived/ | P1 | DONE — 18 legacy tests excluded from default collection |
| Keep test_legacy_imports.py (guardrail still needed) | P1 | KEPT — resonance/legacy/ production package still exists |
| Rename test_coverage_gates.py → test_bootstrap_smoke.py | P2 | DONE |
| Add scope comment to test_golden_corpus.py | P2 | DONE |

**Result:** 491 tests collected after Sprint 06 (from 524).

### Sprint 07: Coverage Gap Closure — COMPLETE

| Task | Priority | Status |
|------|----------|--------|
| Add test_review_inspectability.py (G6) — 3 tests | P1 | DONE |
| Add test_ambiguity_escalation.py (G3) — 2 tests | P1 | DONE |
| Expand test_real_audio_pipeline with album2 (G8) — 1 test | P2 | DONE |
| Add test_lifecycle_chain.py (G7) — 2 tests | P2 | DONE |

**Result:** 499 tests collected, 493 passed, 6 skipped. Every guarantee G1-G9 now has direct behavioral coverage.

### Sprint 08: Documentation Alignment (Low Risk)

| Task | Priority | Effort |
|------|----------|--------|
| Update docs/dev/testing_strategy.md with doctrine from §9 | P1 | 30 min |
| Add GUARANTEE_COVERAGE.md mapping G1-G10 to test files | P2 | 30 min |
| Update GOVERNANCE.md test taxonomy to match audit findings | P3 | 20 min |

---

## 9. Testing Doctrine Draft

### The Resonance Testing Doctrine

**Tests exist to prove that the product keeps its promises.**

#### What a test must answer

Every test in the Resonance suite should be able to answer at least one of:

1. Which product guarantee (G1-G10) does this test defend?
2. Which user job (J1-J7) does this test protect?
3. Which failure mode documented in crash_recovery or the divergence audit does this prevent?

If a test cannot answer any of these questions, it should be examined for removal or reclassification.

#### Layer discipline

| Layer | Purpose | Technology | Proportion |
|-------|---------|-----------|------------|
| Real corpus acceptance | Prove G8, G9 with real APIs | Real providers, real metadata | ~2% of suite |
| Workflow E2E | Prove G4, G5, G7 end-to-end | Stub providers, real filesystem | ~5% of suite |
| Component contracts | Prove component invariants | Unit tests, mock boundaries | ~70% of suite |
| Snapshot determinism | Lock pipeline output stability | Golden corpus, FilesystemFaker | ~8% of suite |
| Smoke & wiring | Prove modules connect | Minimal assertions | ~2% of suite |

Remaining ~13% is legitimate edge-case and integration coverage.

#### Anti-patterns

1. **Ghost infrastructure tests.** Don't test scaffolding that exists only for tests. If FilesystemFaker needs validation, the golden corpus that uses it is the validation.
2. **Legacy inertia.** Code that is deprecated gets its tests archived, not maintained. The governance doc's legacy retirement policy applies.
3. **Theatrical E2E.** An "end-to-end" test that bypasses the real tag writer, real audio parsing, or real filesystem operations is not end-to-end — it is a pipeline logic test and should be labeled as such.
4. **Proportionality blindness.** 39 tests for canonicalization is proportionate because every unicode edge case maps to a real artist name. 15 tests for a deprecated faker context is not proportionate because the component is being removed.

#### The real-audio litmus test

At least one test per major product scenario (standard album, multi-disc, compilation, unicode artist, classical) should exercise real audio files with MutagenTagWriter. This is the floor for G8 compliance.

#### Guarantee coverage accounting

Maintain a living map of which test files defend which guarantees. The audit in §4 is the initial version. Update it when tests are added or removed.

---

## 10. Appendix: Evidence Map

### Guarantee → Test Coverage Summary

| Guarantee | Direct Tests | Indirect Tests | Coverage Level |
|-----------|-------------|---------------|---------------|
| G1 No silent invention | golden_corpus (29), applier (29), identifier (23), idempotency (3) | phase_d_big10 (10), resolver (13) | **STRONG** |
| G2 Inspectable decisions | real_audio (1), audit_doctor_rollback (6), artifacts (5), tag_mapping (9) | golden_corpus (29) | **ADEQUATE** |
| G3 Ambiguity first-class | phase_d_big10 (10), coverage_gates/unjail (1) | identifier tier tests (5) | **WEAK** — needs explicit escalation test |
| G4 Replay deterministic | replay_proof (3), golden_corpus (29), idempotency (3), identity_signature (18) | settings_hash (5), fingerprint_reader (12) | **STRONG** |
| G5 Replay fails loudly | replay_proof (2), exit_codes (3) | — | **STRONG** — small but focused |
| G6 Review usable at scale | e2e_cli/json_mode (1) | — | **WEAK** — needs review bundle test |
| G7 Primary workflows simple | e2e_cli (3), scan_cli (5), resolve_cli (3), apply_cli (4), prompt_cli (8) | cli_smoke (1), coverage_gates (7) | **ADEQUATE** |
| G8 Real mode is real | real_audio_pipeline (1), real_world_corpus (4) | — | **THIN** — 1 real audio test |
| G9 Acceptance behavioral | real_world_corpus (4) | real_audio_pipeline (1) | **ADEQUATE** (opt-in) |
| G10 Tests serve product | This audit | — | **META** — no self-test possible |

### Key File → Guarantee Cross-Reference

| File | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 | G9 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| test_replay_proof | | | | ● | ● | | | | |
| test_real_audio_pipeline | | ● | | | | | | ● | |
| test_golden_corpus | ● | ● | | ● | | | | | |
| test_e2e_cli_workflow | | | | ● | | ● | ● | | |
| test_phase_d_big10 | ● | | ● | ● | | | | | |
| test_applier | ● | | | | | | | | |
| test_crash_recovery | ● | | | | | | | | |
| test_real_world_corpus | | | | | | | | ● | ● |
| test_identifier | ● | | ● | | | | | | |
| test_identity_signature | | | | ● | | | | | |
| test_audit_doctor_rollback | | ● | | | | | | | |
| test_exit_codes | | | | | ● | | ● | | |
| test_idempotency_contracts | ● | | | ● | | | | | |

### Skip Inventory

| Skip | Reason | Impact |
|------|--------|--------|
| test_real_world_corpus (3 tests) | `RUN_REAL_CORPUS=1` opt-in; `metadata.json` required | G8/G9 coverage is opt-in only |
| test_filesystem_edge_cases (2 tests) | Scanner merge policy not finalized | Low — edge cases, not critical path |
| test_no_rematch_invariant (1 test) | Needs real audio fingerprinting | G4 gap — .meta.json sidecars can't follow renames |

### Files Recommended for Deletion/Archive

| File | Tests | Reason |
|------|------:|--------|
| tests/unit/test_filesystem_faker.py | 15 | Tests deprecated FakerContext infrastructure |
| tests/unit/test_legacy_imports.py | 1 | Tests deprecated import paths |
| tests/legacy/test_discogs_client.py | 6 | V2 code, not current architecture |
| tests/legacy/test_metadata_reader.py | 1 | V2 code |
| tests/legacy/test_musicbrainz_client.py | 3 | V2 code |
| tests/legacy/test_prescan_cli.py | 4 | V2 code |
| tests/legacy/test_provider_offline.py | 2 | V2 code |
| tests/legacy/test_release_search_discogs.py | 2 | V2 code |
| **Total** | **34** | |

---

*End of audit. This document should be treated as the test suite's current truth until the next audit cycle.*

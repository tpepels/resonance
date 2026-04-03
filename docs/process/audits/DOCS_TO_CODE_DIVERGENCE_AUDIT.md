# Resonance Docs-to-Code Divergence Audit

**Auditor:** resonance-system-auditor
**Date:** 2025-04-03
**Scope:** Full repository — documentation, implementation, tests, scripts, data artifacts
**Baseline test results:** 502 passed, 8 failed, 7 skipped (before any changes)

---

## 1. Executive verdict

Resonance has a remarkably well-articulated product vision and documentation suite. The documentation is among the strongest I have seen in any repository — it clearly defines product purpose, user jobs, guarantees, decision anatomy, replay semantics, and architectural boundaries.

**However, the implementation has not caught up to this vision.** The gap is not one of quality — the code that exists is generally well-structured — but of completeness, workflow integration, and behavioral proof. Critical user-facing workflows documented as primary product surfaces either do not work end-to-end, rely on test-only scaffolding, or silently bypass the real system.

**Key findings:**

| Severity | Count | Summary |
|----------|-------|---------|
| Critical | 5 | Core user workflows broken or fake |
| High | 6 | Documented guarantees unproven or partially implemented |
| Medium | 7 | Implementation drift, dead code, missing surfaces |
| Low | 4 | Documentation polish, minor inconsistencies |

**Overall status: The documentation describes a product that does not yet exist as a working system.** The pipeline stages (scan, identify, resolve, plan, apply) individually work in isolation with stub providers, but the primary user workflows (`make corpus-decide`, `make corpus-review`) rely on a parallel script-based pathway that bypasses the real CLI and core orchestration. The system is closer to a well-documented prototype than a trusted automation tool.

**Confidence: HIGH** — based on reading every source file, running all tests, and tracing both documented and actual code paths.

---

## 2. Documented system model

### 2.1 Product purpose
Resonance is a music library organization system for people who want to understand, normalize, and improve a real collection of audio files. It treats a library as human-meaningful releases, editions, and organizational decisions — not a bag of filenames.

### 2.2 User jobs (7 documented)
1. Understand what is in my library
2. Understand what each folder probably represents
3. Identify what needs attention (ambiguity, duplicates, incomplete)
4. See what a cleaner organization would look like
5. Decide when the system should act vs when I should decide
6. Review important decisions without reading internals
7. Preserve accepted decisions over time

### 2.3 Primary workflows
- `make corpus-decide` — authoritative decision generation (scan → interpret → resolve → prompt → record)
- `make corpus-review` — human inspection of results via chunked HTML UI
- Replay — deterministic reproduction of accepted decisions

### 2.4 Product guarantees (10 documented)
1. No silent invention of authority
2. Important decisions are inspectable
3. Ambiguity is a first-class outcome
4. Replay is deterministic when assumptions match
5. Replay fails loudly on mismatch
6. Review remains usable at realistic corpus size
7. Primary workflows remain simple
8. REAL authoritative mode is actually real
9. Acceptance is behavioral, not rhetorical
10. Tests serve the product, not the reverse

### 2.5 System invariants (Design spec)
- Directory atomicity (no file splitting)
- Pure→impure boundary (only Apply mutates)
- Stable directory identity (content-based, not path-based)
- Persisted decisions override re-identification
- Provider results are advisory until pinned
- Default dry-run
- Identity normalization vs canonicalization separation

### 2.6 Core data/decision objects
- DirectoryRecord, DirectoryState, DirectorySignature
- IdentificationResult, ReleaseScore, ConfidenceTier
- Plan, TrackOperation, TagPatch
- ApplyReport with rollback
- PromptReplay with fingerprint validation
- Review bundle with SHA256 audit trail

### 2.7 Claimed architecture (5 layers)
1. Corpus ingestion and modeling
2. Interpretation and resolution
3. Decision orchestration
4. Review artifact generation
5. Replay and validation

### 2.8 Operational modes
- REAL mode (authoritative, provider-backed)
- Replay mode (deterministic reproduction)
- Offline mode (cache-only)

### 2.9 Explicit non-goals
- Not a generic media server
- Not a blind batch renamer
- Not a manual tag editor UI
- Not a test-driven abstraction playground

### 2.10 Acceptance signals implied by docs
- Behavioral proof over implementation presence
- Observed replay success AND failure
- Real provider-backed execution demonstrated
- Review UI navigable without raw JSON
- Green tests coexisting with working user workflow

---

## 3. Implemented system model

### 3.1 Actual entrypoints

**CLI (`resonance` command):**
- `scan` — works, populates state DB from filesystem + .meta.json sidecars
- `resolve` — works with providers (requires `--cache-db`)
- `prompt` — works with multiple modes: interactive, scripted, record, replay
- `identify` — partially works (provider_client=None hardcoded in CLI dispatch)
- `plan` — works (requires state DB with resolved directory)
- `apply` — works (transactional with rollback)

**Scripts (parallel pathway):**
- `scripts/corpus_decide.py` — offline workflow using CLI commands internally
- `scripts/corpus_decide_real_interactive.py` — real workflow via FakerContext + CLI commands
- `scripts/corpus_decide_real.py` — real workflow (non-interactive)
- `scripts/corpus_decide_real_replay.py` — replay of recorded decisions
- `scripts/generate_review_bundle.py` — merges expected_*.json files into review bundle
- `scripts/generate_review_interface.py` — generates 3-column HTML review app

**Makefile:**
- `make corpus-decide` — calls `scripts/corpus_decide_real_interactive.py`
- `make corpus-review` — serves `dist/` via `python -m http.server`
- `make corpus-decide-offline` — calls `scripts/corpus_decide.py`

### 3.2 Actual workflows

The **documented primary workflow** (`make corpus-decide`) actually:
1. Creates a FakerContext that monkey-patches `os.path.*` and `os.stat`
2. Creates empty stub files from `tests/real_corpus/metadata.json`
3. Runs scan → resolve → prompt through CLI commands on this fake filesystem
4. Records decisions to `prompt_replay.json`

The review workflow (`make corpus-review`) actually:
1. Serves pre-generated HTML from `dist/` directory
2. HTML loads `index.json` and per-directory chunks from `dist/dir/`
3. These are generated by `scripts/generate_review_interface.py` from `review_bundle.json`
4. `review_bundle.json` is generated from `expected_*.json` files in `tests/real_corpus/`

### 3.3 Actual state transitions
State machine is implemented in `DirectoryStateStore`:
- NEW → RESOLVED_AUTO (via resolve with CERTAIN confidence)
- NEW → QUEUED_PROMPT (via resolve with PROBABLE/UNSURE confidence)
- QUEUED_PROMPT → RESOLVED_USER (via prompt)
- QUEUED_PROMPT → JAILED (via prompt skip)
- RESOLVED_* → PLANNED (via plan)
- PLANNED → APPLIED (via apply)

Missing from implementation: FAILED state transition, IDENTIFIED state (mentioned in store schema but not in design spec flow).

### 3.4 Actual data artifacts
- `tests/real_corpus/metadata.json` — 3MB extracted filesystem metadata (paths, sizes, mtimes)
- `tests/real_corpus/expected_state.json` — hardcoded expected states with sample release IDs
- `tests/real_corpus/expected_layout.json` — empty array `[]`
- `tests/real_corpus/expected_tags.json` — empty `{"tracks": []}`
- `tests/real_corpus/decisions.json` — 5 scripted decisions with dummy release IDs
- `tests/real_corpus/prompt_replay.json` — 20 recorded decisions (all "jail")
- `review_bundle.json` — 2.9MB review bundle with 412 directories
- `tests/golden/expected/` — 28 golden corpus scenario snapshots (working)

### 3.5 Actual provider behavior
- MusicBrainz client: implemented, calls `musicbrainzngs` library, caches results
- Discogs client: implemented, calls REST API, caches results
- AcoustID client: implemented, calls `pyacoustid`, caches results
- CachedProviderClient: wraps any provider with cache-first semantics
- CombinedProviderClient: fuses multiple providers with dedup
- **Bug**: `PROVIDER_CALL_COUNTS` dict initialized per-provider only when `CachedProviderClient.__init__` runs, but accessed unconditionally in `search_by_*` methods → KeyError when provider name not pre-registered (causes 6 test failures)

### 3.6 Actual replay behavior
- `PromptReplay` class in `commands/prompt.py` stores decisions with fingerprints
- `compute_prompt_fingerprint()` creates SHA256 of dir_id + candidate info + reasons
- `run_prompt_replay()` validates fingerprints before applying recorded decisions
- Replay file format: `{format, created_at, app_version, corpus_input_hashes, decisions[]}`
- **Critical finding**: The 20 decisions in `prompt_replay.json` are ALL "jail" decisions — no actual release matches were recorded. This means replay has never been behaviorally proven with real matching decisions.

### 3.7 Actual review behavior
- Review bundle generation works (merges 5 input files)
- HTML interface generation works (34KB static HTML with JS)
- 3-column layout with directory tree, contents, detail inspector
- On-demand JSON loading via fetch() API
- **Critical finding**: `expected_layout.json` is `[]` and `expected_tags.json` is `{"tracks": []}` — the review surface shows directory structure from metadata.json but NO actual Resonance processing results (no plans, no tag decisions, no applied outcomes)

### 3.8 Actual failure behavior
- Error taxonomy exists (ValidationError, RuntimeFailure, IOFailure)
- Exit codes are mapped deterministically
- Transaction rollback is implemented
- **However**: No observed hard-failure on replay mismatch in any test or corpus run

### 3.9 Actual user touchpoints
- CLI works for individual pipeline stages
- Makefile provides top-level commands
- Review HTML is viewable in browser
- No integrated end-to-end user experience from scan to review

### 3.10 Actual hidden or test-only pathways
- `FilesystemFaker` + `FakerContext` monkey-patching is used in the "real" corpus workflow
- `.meta.json` sidecar files are the primary data source for fingerprints and tags (not real audio files)
- `MetaJsonTagWriter` is the default tag writer (writes JSON sidecars, not real audio tags)
- Golden corpus uses fixture-built directories with provider stubs
- Real corpus test creates empty stub files and populates evidence with `None` values

---

## 4. Divergence matrix

| # | Area | Documented intent | Implemented reality | Status | User impact | Confidence |
|---|------|------------------|---------------------|--------|-------------|------------|
| 1 | **`make corpus-decide`** | Authoritative real-provider workflow that scans, resolves, prompts, and records decisions | Script uses FakerContext + empty stub files + monkey-patched os.path. Evidence has no fingerprints, no durations, no tags. All 20 recorded decisions are "jail". | **DIVERGED** | User cannot actually process a real library. The "authoritative" workflow operates on phantom data. | HIGH |
| 2 | **`make corpus-review`** | Human inspection of what Resonance believes and why, with evidence, interpretation, and proposal visibility | Review bundle shows directory tree from metadata but `expected_layout=[]` and `expected_tags={"tracks":[]}`. No actual plans, enrichments, or apply outcomes are visible. | **DIVERGED** | Reviewer sees filesystem structure but zero Resonance decisions, evidence, or proposals. The review surface is a shell. | HIGH |
| 3 | **Replay determinism** | Accepted decisions replay deterministically; mismatch causes hard failure | PromptReplay class exists with fingerprint validation. However, all 20 real corpus decisions are "jail" (no matching). No test or corpus run demonstrates successful replay of a real match decision, nor hard failure on mismatch. | **PARTIAL** | Replay mechanism exists in code but has never been proven to work for its primary purpose. | HIGH |
| 4 | **REAL mode is actually real** | REAL mode exercises real providers, real prompts, real decision artifacts | Real mode script uses FakerContext (monkey-patched filesystem), creates empty stub files, builds evidence with `fingerprint_id=None`, `duration_seconds=None`, `existing_tags={}`. Providers are called but have nothing useful to match against. | **DIVERGED** | REAL mode is theatrical — providers are called but cannot produce meaningful results because the input evidence is empty. | HIGH |
| 5 | **Provider-backed resolution** | Providers supply evidence for candidate matching with fingerprint, duration, and metadata comparison | Providers are implemented and functional. BUT: real corpus workflow provides no fingerprints and no durations to match against. Golden corpus uses fixture stubs. No test exercises real provider-backed resolution with actual audio data. | **PARTIAL** | Provider integration works in isolation but has never been proven on real audio data in any tested workflow. | HIGH |
| 6 | **Plan-based execution** | Deterministic plans with file moves and tag updates, reviewable before applying | Planner works correctly in golden corpus tests. Plan generation is deterministic. BUT: real corpus produces no plans (all directories are jailed or pending). | **PARTIAL** | Planning works in synthetic scenarios but not in the primary real-corpus workflow. | MEDIUM |
| 7 | **Transaction/rollback** | Apply is transactional with rollback on failure | Transaction class is implemented with backup/restore. Crash recovery tests pass. BUT: only tested with MetaJsonTagWriter (JSON sidecars), never with MutagenTagWriter (real audio files). | **PARTIAL** | Transaction safety is proven for test tag writer but not for real audio file mutations. | MEDIUM |
| 8 | **Decision inspectability** | Every important decision has evidence, interpretation, proposal, confidence, and authority source | IdentificationResult contains candidates, tier, reasons, and evidence. BUT: the review surface does not render any of this. Review bundle contains directory tree and file lists, not decision anatomy. | **DIVERGED** | Users cannot inspect decision reasoning through any available surface. | HIGH |
| 9 | **Ambiguity as first-class outcome** | Uncertain cases remain explicitly unresolved; UNSURE/QUEUED_PROMPT are valid states | State machine supports QUEUED_PROMPT and JAILED states. Resolver routes UNSURE to prompt queue. In real corpus, all unresolved cases are jailed rather than preserved as ambiguous for review. | **PARTIAL** | Ambiguity exists in the model but is collapsed to "jail" in practice, not surfaced for review. | MEDIUM |
| 10 | **Stable directory identity** | Content-based dir_id from audio fingerprints/signatures, independent of path | `dir_signature()` computes hash from fingerprint_id + duration_seconds. In real corpus, files have no fingerprints and no durations, so identity degrades to a hash of `None` values. Golden corpus tests verify identity stability. | **PARTIAL** | Identity is stable in golden corpus but meaningless in real corpus due to empty evidence. | HIGH |
| 11 | **CLI surface completeness** | Design spec lists: scan, identify, prompt-uncertain, plan, apply, audit, doctor, rollback, unjail | CLI implements: scan, resolve, prompt, identify (broken — passes None for providers), plan, apply. Missing from CLI: audit, doctor, rollback, unjail (code exists in commands/ but not registered in cli.py). | **PARTIAL** | Users cannot access audit, doctor, rollback, or unjail commands from the CLI. | MEDIUM |
| 12 | **Fingerprint-based identification** | Content identity via AcoustID + MusicBrainz using actual audio fingerprints | AcoustID client exists and is functional. FingerprintReader wraps pyacoustid. BUT: no test or workflow exercises fingerprint extraction from real audio files. All tests use .meta.json sidecars with pre-computed fingerprint IDs. | **PARTIAL** | Fingerprinting code exists but has zero behavioral proof with real audio. | MEDIUM |
| 13 | **Canonical name resolution** | IdentityCanonicalizer with explicit mappings, never invents, preserves original if no mapping | Canonicalizer implemented correctly. display_artist/display_album preserve diacritics. match_key functions do aggressive normalization. Cache-backed. Well-tested in unit tests. | **MATCHES** | Working as documented. | HIGH |
| 14 | **Confidence model** | Deterministic arithmetic scoring with CERTAIN/PROBABLE/UNSURE tiers | Implemented with configurable weights, persisted scoring_version. score_release() is pure and deterministic. calculate_tier() uses threshold-based classification. Well-tested. | **MATCHES** | Working as documented. | HIGH |
| 15 | **No-rematch invariant** | Pinned decisions override re-identification; resolved directories skip provider queries | Implemented in resolver: checks for existing resolution state before calling providers. Tested in test_no_rematch_invariant.py and golden corpus (idempotency check). | **MATCHES** | Working as documented. | HIGH |
| 16 | **Settings/config system** | Hybrid config: env vars → JSON config → defaults, with priority ordering | Implemented: Settings dataclass, load_settings(), resolve_tag_writer_backend(). CLI args → env → config → defaults priority chain. settings_hash() for cache invalidation. | **MATCHES** | Working as documented. | HIGH |
| 17 | **Review at scale** | Chunked static outputs for navigability; no multi-MB ingestion | HTML interface is 22KB, loads data via fetch(). index.json + per-directory chunks. Strategy A implementation. | **MATCHES** (for the surface) | Chunking works, but there's nothing meaningful to chunk (empty results). | MEDIUM |
| 18 | **Test suite serves product** | Tests protect product behavior, not define it; behavioral proof over fixture tricks | 502 passing tests, mostly unit and integration. Golden corpus provides end-to-end proof for synthetic scenarios. Real corpus tests are opt-in and skip by default. 8 tests are broken. | **PARTIAL** | Tests protect individual components well but do not prove the primary user workflow. | HIGH |
| 19 | **State persistence** | SQLite-backed directory state store with migration support | DirectoryStateStore is well-implemented with schema versioning, upsert, audit artifacts table. MetadataCache provides generic caching. | **MATCHES** | Working as documented. | HIGH |
| 20 | **Documentation accuracy** | Docs should reflect actual system behavior | README claims workflows exist and work. V3.1 manual claims "20 directories processed deterministically" and "20 decisions recorded with cryptographic fingerprints." Reality: 20 decisions recorded, all are "jail." No directories were meaningfully processed. | **DIVERGED** | Documentation overstates implemented capabilities, creating false confidence. | HIGH |

---

## 5. Test-driven distortion findings

### 5.1 Parallel fake workflows instead of real workflows

**Finding (Critical):** The `make corpus-decide` workflow — documented as the primary authoritative user workflow — does not use a real filesystem. It:
1. Loads `metadata.json` (extracted filesystem metadata with paths and sizes)
2. Creates empty stub files at those paths (`full_path.touch()`)
3. Wraps everything in `FakerContext` (monkey-patches `os.path.*`)
4. Builds evidence with `fingerprint_id=None, duration_seconds=None, existing_tags={}`
5. Calls providers who get no useful input data

This is precisely the anti-pattern the docs warn against: *"fake 'real' paths that do not exercise actual system behavior"* (workflows.md line 138).

### 5.2 Expected artifacts defining truth instead of product behavior

**Finding (High):** The real corpus expected files contain:
- `expected_state.json`: States with `sample-release-1`, `sample-release-2` etc. as pinned release IDs — these are obviously fabricated, not the result of actual provider matching
- `expected_layout.json`: Empty array `[]`
- `expected_tags.json`: `{"tracks": []}`

The "expected" artifacts encode an invented outcome rather than recording what the system actually produced. This is another documented anti-pattern.

### 5.3 Replay being simulated rather than behaviorally real

**Finding (High):** `prompt_replay.json` contains 20 decisions, every single one choosing "jail":
```json
{"chosen_option": "jail", "chosen_provider": null, "chosen_release_id": null}
```

The V3.1 manual claims: *"Decision Replay: ✅ Semantically proven with hard enforcement"* — but replay has never been exercised with an actual match decision. Jailing requires no fingerprint validation and proves nothing about deterministic replay of real authority.

### 5.4 Green tests coexisting with broken workflows

**Finding (Medium):** The test suite reports 502 passing tests, creating an appearance of health. Meanwhile:
- 8 tests fail (caching provider KeyError, resolve CLI missing cache_db)
- The primary user workflow (`make corpus-decide`) has never produced a successful match
- The review surface shows no decisions
- Real corpus tests are opt-in and skipped in CI

The test suite protects component-level correctness but does not defend the product-level promise.

### 5.5 FilesystemFaker as test-only infrastructure in production path

**Finding (High):** `FakerContext` monkey-patches stdlib functions (`os.path.exists`, `os.stat`, etc.) during what is supposed to be the production workflow. The docs explicitly warn against *"implementation existing mainly to satisfy fixtures/tests"* (testing_strategy.md). The faker exists solely to avoid requiring a real music library during corpus processing, but its use means the "real" workflow has never operated on real files.

---

## 6. Critical gaps

### Gap 1: No working end-to-end user workflow
**What's missing:** A path from `resonance scan /path/to/music` through resolution, prompting, planning, and apply that works on actual audio files.
**Why it matters:** This is the entire product promise. Without it, Resonance is a well-documented set of components, not a product.

### Gap 2: No real audio file processing proven anywhere
**What's missing:** No test, script, or workflow exercises fingerprint extraction from real audio files, real tag reading via Mutagen, or real file moves on audio content.
**Why it matters:** The "trusted automation" guarantee requires proving the system works on the thing it's supposed to work on.

### Gap 3: Review surface shows no decisions
**What's missing:** The review bundle contains directory/file structure but zero decision reasoning, evidence, interpretation, proposals, or confidence information.
**Why it matters:** Job 6 ("review important decisions without reading internals") cannot be accomplished.

### Gap 4: Replay never proven with real match decisions
**What's missing:** A replay file containing actual release match decisions (not just jails), replayed successfully, then intentionally broken to prove hard failure.
**Why it matters:** Guarantees 4 and 5 (deterministic replay, loud failure on mismatch) are unproven.

### Gap 5: CLI commands missing from entrypoint
**What's missing:** `audit`, `doctor`, `rollback`, `unjail` commands exist as modules but are not registered in `cli.py`.
**Why it matters:** Users cannot access diagnostic and recovery tools.

### Gap 6: Identify command broken
**What's missing:** CLI dispatch passes `provider_client=None` to `run_identify()`, making the command useless for its documented purpose.
**Why it matters:** Users cannot run identification from the CLI.

---

## 7. Recommended sprint portfolio

### Sprint 1: Fix broken tests and CLI registration
**Problem:** 8 tests fail due to bugs (KeyError in caching provider, missing cache_db in resolve CLI tests). 4 CLI commands exist but aren't registered.
**Why it matters:** Stabilizes the baseline so subsequent work can be verified.
**Scope:**
- Fix `PROVIDER_CALL_COUNTS` KeyError in `resonance/providers/caching.py` (initialize dict entry in `__init__`)
- Fix resolve CLI tests to pass `cache_db` in Namespace
- Register `audit`, `doctor`, `rollback`, `unjail` in `cli.py`
- Fix `identify` command to create proper provider context
**Files:** `resonance/providers/caching.py`, `resonance/cli.py`, `tests/integration/test_e2e_cli_workflow.py`, `tests/integration/test_resolve_cli_simple.py`
**Acceptance:** All 510+ tests pass. All documented CLI commands are accessible via `resonance --help`.
**Evidence:** `pytest` green, `resonance --help` shows all commands.
**Dependencies:** None — do this first.

### Sprint 2: Prove the pipeline on real audio files
**Problem:** No test or workflow has ever processed a real audio file through the pipeline. All testing uses .meta.json sidecars and empty stub files.
**Why it matters:** The product claims to organize music libraries but has never been observed doing so.
**Scope:**
- Create a small (3-5 files) integration test fixture with real FLAC/MP3 audio files
- Prove: fingerprint extraction → provider lookup → resolution → planning → apply with MutagenTagWriter → verify tags written to real audio files
- This does NOT require API keys — use pre-cached provider responses
**Files:** New test file, `resonance/core/fingerprint.py`, `resonance/services/tag_writer.py`
**Out of scope:** Full corpus processing, review interface changes
**Acceptance:** Integration test demonstrates scan→resolve→plan→apply on real audio files with real tag writes verified by reading back.
**Evidence:** Test reads tags from output audio files and they match expected values.
**Dependencies:** Sprint 1 (stable test baseline).

### Sprint 3: Make review surface show actual decisions
**Problem:** Review bundle contains directory tree but no decision reasoning, evidence, candidates, confidence, or proposals.
**Why it matters:** User Job 6 and Guarantees 1-3 depend on inspectable decisions.
**Scope:**
- Extend review bundle generation to include: per-directory IdentificationResult (candidates, tier, reasons), resolution outcome, plan summary, apply status
- Update HTML interface to render decision anatomy in the detail inspector panel
- Wire review bundle generation into the corpus-decide workflow
**Files:** `scripts/generate_review_bundle.py`, `scripts/generate_review_interface.py`
**Out of scope:** Replay, real provider calls, filesystem mutations
**Acceptance:** After `make corpus-decide`, the review interface shows for each directory: what candidates were considered, what confidence tier was assigned, what decision was made, and why.
**Evidence:** Screenshot or HTML inspection showing decision anatomy for at least 3 directories.
**Dependencies:** Sprint 1.

### Sprint 4: Make corpus-decide use real files or faithful simulation
**Problem:** The "real" corpus workflow creates empty files and provides null evidence to providers.
**Why it matters:** Guarantee 8 ("REAL mode is actually real") is violated.
**Scope:**
- Refactor corpus-decide to either: (a) work on actual audio files, or (b) properly populate evidence from metadata.json (durations, sizes, and pre-extracted fingerprints stored in metadata)
- Remove or quarantine `FakerContext` monkey-patching from the production workflow path
- Ensure evidence objects contain real data (durations, fingerprints where available)
- Ensure provider calls receive meaningful input
**Files:** `scripts/corpus_decide_real_interactive.py`, `tests/integration/_filesystem_faker.py`, `scripts/extract_real_corpus.sh`
**Out of scope:** Achieving 100% match rate, changing provider logic
**Acceptance:** `make corpus-decide` produces evidence objects with real durations and (where available) real fingerprint IDs. Providers receive meaningful queries. At least some directories match real releases.
**Evidence:** Provider call logs show non-trivial queries. At least 5 directories resolve to real (non-sample) release IDs.
**Dependencies:** Sprint 1, Sprint 2 (understanding of real audio processing).

### Sprint 5: Prove replay with real match decisions
**Problem:** Replay has only been tested with "jail" decisions. No behavioral proof of match decision replay or mismatch failure.
**Why it matters:** Guarantees 4 and 5 are the core trust mechanism.
**Scope:**
- After Sprint 4 produces real match decisions, record them via prompt-record
- Create integration test that: (a) records N real decisions, (b) replays successfully, (c) alters one decision's fingerprint and proves hard failure
- Store this as a regression test
**Files:** `resonance/commands/prompt.py`, new integration test
**Out of scope:** UI changes, provider improvements
**Acceptance:** Integration test demonstrates: replay succeeds with matching data, replay fails with altered fingerprint.
**Evidence:** Test output showing both success and failure cases.
**Dependencies:** Sprint 4 (real decisions to replay).

### Sprint 6: Reconcile documentation with reality
**Problem:** V3.1 manual claims "20 directories processed deterministically" and "Decision Replay: ✅ Semantically proven." README claims workflows exist. `expected_state.json` contains fabricated release IDs.
**Why it matters:** Documentation overstating capability erodes the very trust the product is designed to build.
**Scope:**
- Update V3.1 manual to accurately describe current capabilities and known gaps
- Update expected_state.json to reflect actual processing results (from Sprint 4)
- Add a "Known Limitations" section to README
- Replace fabricated sample-release-* IDs with actual provider results or remove
**Files:** `docs/process/V3.1_REAL_CORPUS_MANUAL.md`, `README.md`, `tests/real_corpus/expected_state.json`
**Out of scope:** New feature work
**Acceptance:** No documentation claims that cannot be demonstrated by running the system.
**Evidence:** Every claim in the manual can be verified by running the corresponding command.
**Dependencies:** Sprint 4, Sprint 5 (actual results to document).

### Sprint 7: Integrated user workflow from scan to review
**Problem:** Individual pipeline stages work, but there is no single-command workflow that takes a user from library path to reviewable output.
**Why it matters:** This is the core product experience — the thing a real user would actually do.
**Scope:**
- Create `resonance decide /path/to/library` command (or equivalent) that orchestrates scan→resolve→prompt→plan→apply→generate review
- Ensure this command uses real system behavior (no faker, no monkey-patching)
- Ensure output includes both decision artifacts and review surface
- Retire or relegate scripts/ to development-only tooling
**Files:** `resonance/cli.py`, new orchestration module, `Makefile`
**Out of scope:** UI redesign, new provider support
**Acceptance:** A user with a music library can run one command and get a reviewable set of decisions.
**Evidence:** Demo on a small real library (5-10 directories) producing inspectable review output.
**Dependencies:** Sprints 1-6.

---

## 8. Decisions to defer until after remediation design

1. **Whether FakerContext has any legitimate role** — It might be useful for CI testing without audio files, but it should never be in the production workflow path. Defer decision until Sprint 4 clarifies the production path.

2. **Whether .meta.json sidecar-based testing is sufficient** — Unit and integration tests currently depend entirely on JSON sidecars. After Sprint 2 proves real audio processing, decide whether to keep sidecars for fast tests and add a separate real-audio test layer.

3. **Classical/compilation foldering rules** — The design spec describes classical and compilation layout rules, but these are explicitly marked as initial/conservative. Defer refinement until the basic pipeline works end-to-end.

4. **Daemon mode** — Documented in the design spec (section 12) but not implemented anywhere. Defer until the interactive mode works.

5. **Whether the golden corpus test suite should be the primary acceptance gate** — The golden corpus is the strongest test in the repo today, but it uses fixture-built directories and provider stubs. After Sprint 2, decide whether to make real-audio tests the primary gate.

6. **Review bundle schema** — Current schema is directory-tree + tracks. After Sprint 3 adds decision anatomy, the schema may need versioning. Defer schema design until the content is real.

---

## 9. Appendix: evidence map

### Evidence for divergence findings

| Claim | Evidence location | What to look for |
|-------|------------------|-----------------|
| corpus-decide uses FakerContext | `scripts/corpus_decide_real_interactive.py:58-60` | `FakerContext(faker)` wrapping the entire workflow |
| Empty stub files created | `scripts/corpus_decide_real_interactive.py:62-67` | `full_path.touch()` creating 0-byte files |
| Evidence has null values | `tests/integration/test_real_world_corpus.py:167-178` | `fingerprint_id=None, duration_seconds=None, existing_tags={}` |
| All decisions are jail | `tests/real_corpus/prompt_replay.json` | Every decision has `"chosen_option": "jail"` |
| Expected layout is empty | `tests/real_corpus/expected_layout.json` | Contains `[]` |
| Expected tags is empty | `tests/real_corpus/expected_tags.json` | Contains `{"tracks": []}` |
| Expected state has fabricated IDs | `tests/real_corpus/expected_state.json` | `sample-release-1`, `sample-release-2`, etc. |
| PROVIDER_CALL_COUNTS KeyError | `resonance/providers/caching.py:185` | Accesses `PROVIDER_CALL_COUNTS[name]` without init |
| Identify command broken | `resonance/cli.py:226-230` | `provider_client=None, fingerprint_reader=None` |
| Missing CLI commands | `resonance/cli.py` | No subparser registration for audit, doctor, rollback, unjail |
| Review bundle lacks decisions | `scripts/generate_review_bundle.py` | Merges metadata, state, layout, tags — no decision reasoning |
| V3.1 manual overstates | `docs/process/V3.1_REAL_CORPUS_MANUAL.md:341-342` | "Decision Replay: ✅ Semantically proven" |
| 8 test failures | Test run output | 6 × KeyError in caching provider, 2 × missing cache_db |
| Golden corpus works correctly | `tests/integration/test_golden_corpus.py` | Full scan→resolve→plan→apply→snapshot with 28 scenarios |
| Transaction rollback tested | `tests/integration/test_crash_recovery.py` | 6 crash/recovery test scenarios all passing |
| Canonicalization works | `tests/unit/test_canonicalize.py`, `tests/unit/test_identity.py` | Comprehensive unit tests for name normalization |
| Confidence scoring works | `tests/unit/test_identifier.py` | Tests for score_release, calculate_tier, merge_and_rank |
| No-rematch invariant works | `tests/integration/test_no_rematch_invariant.py` | Resolved directories skip provider re-query |

### File inventory by role

| Role | Files | Health |
|------|-------|--------|
| Documentation | 16 docs files + README | Excellent quality, overstates implementation |
| Core domain | 18 files in `resonance/core/` | Well-structured, well-tested at component level |
| Infrastructure | 5 files in `resonance/infrastructure/` | Solid, working |
| Providers | 4 files in `resonance/providers/` | Functional but with caching bug |
| Services | 2 files in `resonance/services/` | Working |
| CLI | `cli.py` + 13 command files | Partially incomplete (4 missing commands, 1 broken) |
| Scripts | 11 files in `scripts/` | Functional but represent a parallel workflow bypassing CLI |
| Unit tests | 28 files | Strong component coverage |
| Integration tests | 19 files | Good but 3 have failures |
| Golden corpus | 2 builder files + 28×3 snapshots | Strongest behavioral proof in the repo |
| Real corpus | 7 data files + 1 test file | Theatrical — proves metadata handling, not audio processing |

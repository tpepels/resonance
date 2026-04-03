# Ownership Matrix

**Portfolio:** Resonance Docs-to-Code Remediation  
**Purpose:** Boundary clarity for each sprint — which code/doc areas are in scope and which are not

---

## Matrix

| Code/Doc Area | Sprint 01 | Sprint 02 | Sprint 03 | Sprint 04 | Sprint 05 | Sprint 06 | Sprint 07 |
|---------------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|
| `resonance/cli.py` | **PRIMARY** | — | — | — | — | — | **PRIMARY** |
| `resonance/commands/audit.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/commands/doctor.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/commands/rollback.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/commands/unjail.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/commands/identify.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/commands/prompt.py` | — | — | — | — | **PRIMARY** | — | — |
| `resonance/providers/caching.py` | **PRIMARY** | — | — | — | — | — | — |
| `resonance/core/fingerprint.py` | — | **PRIMARY** | — | supporting | — | — | — |
| `resonance/services/tag_writer.py` | — | **PRIMARY** | — | supporting | — | — | — |
| `resonance/core/` (other) | — | supporting | — | — | — | — | — |
| `scripts/corpus_decide_real_interactive.py` | — | — | — | **PRIMARY** | — | — | — |
| `scripts/corpus_decide_real.py` | — | — | — | **PRIMARY** | — | — | — |
| `scripts/corpus_decide_real_replay.py` | — | — | — | supporting | **PRIMARY** | — | — |
| `scripts/corpus_decide.py` | — | — | — | scope-limited | — | — | — |
| `scripts/generate_review_bundle.py` | — | — | **PRIMARY** | — | — | — | supporting |
| `scripts/generate_review_interface.py` | — | — | **PRIMARY** | — | — | — | supporting |
| `tests/integration/test_e2e_cli_workflow.py` | **PRIMARY** | — | — | — | — | — | — |
| `tests/integration/test_resolve_cli_simple.py` | **PRIMARY** | — | — | — | — | — | — |
| `tests/integration/_filesystem_faker.py` | — | — | — | **PRIMARY** | — | — | — |
| `tests/integration/test_real_world_corpus.py` | — | — | — | **PRIMARY** | — | — | — |
| `tests/integration/test_golden_corpus.py` | — | read-only | — | — | — | — | — |
| New: real audio integration test | — | **PRIMARY** | — | — | supporting | — | — |
| New: replay integration test | — | — | — | — | **PRIMARY** | — | — |
| New: orchestration command | — | — | — | — | — | — | **PRIMARY** |
| `tests/real_corpus/expected_state.json` | — | — | — | **PRIMARY** | — | **PRIMARY** | — |
| `tests/real_corpus/expected_layout.json` | — | — | — | **PRIMARY** | — | supporting | — |
| `tests/real_corpus/expected_tags.json` | — | — | — | **PRIMARY** | — | supporting | — |
| `tests/real_corpus/prompt_replay.json` | — | — | — | — | **PRIMARY** | supporting | — |
| `tests/real_corpus/decisions.json` | — | — | — | **PRIMARY** | — | supporting | — |
| `docs/process/V3.1_REAL_CORPUS_MANUAL.md` | — | — | — | — | — | **PRIMARY** | — |
| `README.md` | — | — | — | — | — | **PRIMARY** | supporting |
| `Makefile` | — | — | — | supporting | — | — | **PRIMARY** |
| `docs/product/**` | — | — | — | — | — | supporting | — |
| `docs/system/**` | — | — | — | — | — | supporting | — |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| **PRIMARY** | Sprint is the owner of this area; changes expected |
| supporting | Sprint may read or lightly adjust this area, but it is not the primary target |
| read-only | Sprint executor should read this file for context but must not modify it |
| scope-limited | Sprint may only make targeted, bounded changes described in the sprint file |
| — | Not in scope for this sprint |

---

## Boundary Notes

### Sprint 01 boundaries
- Only fixes: the `PROVIDER_CALL_COUNTS` KeyError, CLI subparser registrations, the broken identify dispatch, and the two failing test files.
- Must not refactor providers, core domain, or any script.

### Sprint 02 boundaries
- Only adds a new integration test fixture with real audio files.
- Must not change `scripts/` or any Makefile target.
- Must not alter the golden corpus test suite.

### Sprint 03 boundaries
- Only extends the review bundle schema and HTML interface.
- Must not change how `corpus-decide` collects data — that is Sprint 04's domain.
- May add to `generate_review_bundle.py` and `generate_review_interface.py` but must not alter their invocation contract.

### Sprint 04 boundaries
- Scope is the corpus-decide workflow and its supporting scripts.
- Must not re-implement providers or change scoring logic.
- May update `expected_*.json` files only by regenerating them from real pipeline output.

### Sprint 05 boundaries
- Scope is the prompt/replay module and a new integration test.
- Must not change corpus scripts beyond what is needed to record match decisions.
- Must not alter the review interface.

### Sprint 06 boundaries
- Documentation only, plus `expected_state.json` alignment.
- No behavior changes. No new features.
- Any behavior gap discovered during this sprint should be filed as a follow-on, not fixed in-sprint.

### Sprint 07 boundaries
- Adds a new orchestration entry point.
- Must not re-implement any component work from earlier sprints.
- Scripts/ directory may be reorganized or demoted to dev-only but must not be deleted without confirming no tests depend on them.

This version explicitly:

* removes architectural feature creep (notably observability),
* replaces subjective UX language with **golden snapshot assertions**,
* wires existing but dormant functionality (prompt),
* formalizes the “hand it to a friend” gate as a documented ritual,
* and makes “done” objectively verifiable.

---

# TDD TODO V4 — Productization With Measurable UX Guarantees

**V4 theme:**

> V3 proves *correctness*.
> **V4 proves that the tool can be trusted and operated without insider knowledge.**

**Hard scope limits**

* ❌ No new providers
* ❌ No new tagging formats
* ❌ No new persistent schemas
* ❌ No run history / observability infrastructure
* ❌ No architectural refactors

Everything in V4 must be achievable via:

* CLI wiring
* output formatting
* error wrapping
* documentation
* snapshot tests
* minimal glue code

---

## ⚠️ V4 Prerequisites

**V4 CANNOT BEGIN until V3 Phase E is complete.**

V4 assumes the following V3 deliverables exist:

* `resonance scan` command (wired and tested)
* `resonance resolve` command (wired and tested)
* `resonance prompt` command (wired and tested)
* End-to-end workflow test passing
* README updated to match implementation

**Status check:** See [TDD_TODO_V3.md Phase E](TDD_TODO_V3.md#phase-e--workflow-integration--not-started)

---

## Global V4 Constraints (Non-Negotiable)

* All UX claims must be **snapshot-testable**
* All human-readable output must be:

  * deterministic
  * stable across runs
  * version-frozen via golden files
* No task may rely on “looks good to me” as a completion criterion

---

## 1. CLI UX — Snapshot-Defined, Not Subjective

### 1.1 Public CLI surface audit

**Goal:** explicitly define what is *public API* vs internal tooling.

**Prerequisite:** Phase E (Workflow Integration) must complete first - `scan`, `resolve`, `prompt` don't exist in CLI yet.

* [ ] Audit CLI commands

  * Public (V4 contract - workflow commands):

    * `scan` (from Phase E)
    * `resolve` (from Phase E)
    * `prompt` (from Phase E)
    * `plan`
    * `apply`
    * `doctor`
  * Public (diagnostic/inspection - read-only):

    * `identify` (single-directory inspection, does not modify state)
  * Internal / dev-only (expose with `--dev` flag or keep unlisted):

    * `audit`
    * `rollback`
    * `unjail`
    * `stability`
* [ ] Document this distinction in `docs/CLI_API.md`:
  * Workflow commands: part of scan → resolve → prompt → plan → apply pipeline
  * Diagnostic commands: read-only inspection tools (identify)
  * Internal commands: for debugging/development only
* [ ] Test: every public command supports:

  * `--help`
  * `--json`
* [ ] Test: internal commands either hidden or clearly marked as unsupported

---

### 1.2 Stable human summaries (golden snapshots)

Replace "readable summaries" with **frozen formats**.

* [ ] Snapshot test: `identify` default output contains **exactly**:

  * directory path
  * `dir_id`
  * confidence tier (`CERTAIN|PROBABLE|UNSURE`)
  * candidate count
  * top candidate summary:

    * artist
    * album
    * year
    * score
* [ ] Snapshot test: `apply --dry-run` output contains **exactly**:

  * `Would move: X files`
  * `Would tag: Y files`
  * `Would skip: Z files (reason)`
* [ ] Snapshot test: explicit "Nothing to do" output when applicable
* [ ] Snapshot test corpus:

  * standard album
  * compilation
  * classical album

**Snapshot guardrails (enforced by tests):**

* [ ] Meta-test: snapshots must NOT contain:
  * raw provider IDs (e.g., `mb-abc123...` in human output)
  * stack traces or exception class names
  * internal class names (e.g., `ProviderRelease`, `DirectoryRecord`)
  * implementation details (e.g., "signature_hash", "scoring_version" in human output)

**Wording stability rule:**

Any change to human-readable CLI output requires:

1. Snapshot update (intentional, not accidental)
2. CHANGELOG entry under "UX-visible changes"
3. Justification (why the wording improved)

---

### 1.3 Dry-run parity

* [ ] Test: `apply --dry-run` and `apply` share identical structure
* [ ] Test: mutation verbs differ only by tense (`Would move` vs `Moved`)
* [ ] Guarantee: user can assess impact without inspecting JSON plans

---

## 2. Prompt / Interactive Resolution (Concrete Wiring)

### 2.0 Prerequisite — make it reachable

**Note:** This is part of V3 Phase E, but listed here for completeness.

* [ ] Wire `resonance/commands/prompt.py` into CLI as:

  ```
  resonance prompt
  ```
* [ ] Test: `resonance prompt --help` works in clean install
* [ ] Cross-reference: See V3 Phase E.3 for full implementation checklist

---

### 2.1 Terminal UI decision (explicit, documented)

**V4 decision (locked):**

* Simple numbered list
* `input()`-based
* No curses / rich TUI

- [ ] Record decision in `docs/DECISIONS.md`

---

### 2.2 Candidate presentation (snapshot-based)

* [ ] Snapshot test: prompt output for 3 candidates shows:

  * provider (MB / Discogs)
  * year
  * label
  * format
  * disc + track count
  * short reason codes (user-friendly, not internal jargon)
* [ ] Test: candidate ordering stable across runs
* [ ] Test: pinned choice message includes:

  * "This decision is permanent unless manually cleared"
* [ ] Apply snapshot guardrails (same as §1.2):
  * No raw IDs, stack traces, class names, or internal implementation details in user output

---

### 2.3 Prompt safety guarantees

* [ ] Test: invalid input does not alter state
* [ ] Test: Ctrl-C returns directory to `QUEUED_PROMPT`
* [ ] Test: prompt is resumable (no corruption)

---

## 3. Observability — **Scoped Down to V4 Reality**

> ❗ Full observability is deferred to V5.

### 3.1 Minimal observability via existing `doctor`

* [ ] Extend `resonance doctor` output to include:

  * total directories in state
  * counts:

    * `APPLIED`
    * `QUEUED`
    * `JAILED`
    * `FAILED`
* [ ] Test: doctor output snapshot
* [ ] Guarantee: no new DB tables, no run history

---

## 4. Error Taxonomy — Enforced, Not Aspirational

### 4.1 Error cleanup audit

* [ ] Audit task:

  * grep for `raise Exception`
  * grep for `raise ValueError`
  * identify all uncategorized error paths
* [ ] Wrap all user-visible errors into:

  * `ValidationError` (bad user input, invalid config)
  * `RuntimeFailure` (provider unavailable, network errors)
  * `IOFailure` (disk full, permissions, missing paths)
* [ ] Note: `AmbiguityError` not needed in V4 (ambiguity is handled via QUEUED_PROMPT state)

---

### 4.2 Error behavior guarantees

* [ ] Integration test per error category asserting:

  * human message
  * retry safety (`safe to retry: yes/no`)
  * mutation status (“No files were changed”)
* [ ] Snapshot test: no raw stack traces in normal failures
* [ ] Document mapping in `docs/ERRORS.md`:

  ```
  error_code → what happened → what to do
  ```

---

## 5. Documentation — Diff-Based Acceptance

### 5.1 README audit (no duplication)

* [ ] Compare current README vs V4 needs:

  * ✅ What it does
  * ❌ What it does NOT do → add “Non-Goals”
  * ❌ Who it is for → add “Is this for you?”
* [ ] Acceptance: diff must show only net-new value

---

### 5.2 Quick start (snapshot-verified)

* [ ] Add `docs/QUICK_START.md`:

  * scan → resolve → prompt → plan → apply → rerun
  * real example with expected output
  * covers happy path (all auto-resolved) and prompted path
* [ ] Snapshot test: example output matches golden
* [ ] Test: documented commands actually exist and produce shown output

---

### 5.3 Mental model docs

* [ ] Add `docs/MENTAL_MODEL.md` covering:

  * why it won't ask again (no-rematch invariant explained for users)
  * when it prompts (confidence tier thresholds)
  * what's in the state DB (transparency: user choices, pinned decisions)
  * what happens on rerun (idempotency guarantee)
* [ ] No internal jargon exposed (avoid: "provider fusion", "signature hash", "scoring version")
* [ ] User-centric language (e.g., "remembered your choice" not "pinned release_id")

---

## 6. Defaults & Configuration Hygiene

* [ ] Test: default config performs no destructive actions
* [ ] Test: dangerous option combinations flagged by `doctor`
* [ ] No silent acceptance of risky configs

---

## 7. Packaging & Dependency Confidence

### 7.1 Installation guarantees

* [ ] `pyproject.toml` declares:

  * core deps
  * optional extras:

    ```
    resonance[real-tags]
    ```
* [ ] Test: pipx install in clean venv → `resonance --help`
* [ ] Test: missing API keys detected by `doctor` with guidance

### 7.2 Provider client lifecycle

* [ ] Implement provider client factory used by CLI when provider_client not injected
* [ ] Tests: resolve/prompt both honor --cache-db and offline semantics
* [ ] Snapshot: CLI indicates cache DB path and offline mode behavior

---

## 8. Acceptance Ritual — “Hand It to a Friend”

**This is a required, documented human gate.**

### 8.1 Ritual definition

* [ ] Add `docs/V4_ACCEPTANCE_RITUAL.md`:

  1. Recruit technically literate non-contributor
  2. Provide:

     * README
     * test library (10–20 albums)
  3. Observe silently
  4. Record findings

---

### 8.2 Completion criteria

* [ ] User completes:

  * scan
  * resolve
  * apply
  * rerun
* [ ] User reports:

  * no critical confusion
  * willingness to use on real library
* [ ] Findings recorded in:

  * `docs/V4_USABILITY_FINDINGS.md`
  * `docs/V4_ACCEPTANCE_REPORT.md`

---

## 9. Upgrade Safety (V3 → V4)

* [ ] Test: V3 `state.db` opens in V4 without migration
* [ ] Test: V3 `cache.db` usable or documented clear-cache
* [ ] Test: V3 `settings.json` compatible
* [ ] Document breaking changes in `CHANGELOG.md`

---

## V4 Definition of Done (Objective)

V4 is complete **only if all are true**:

1. All UX claims are snapshot-enforced
2. Prompt command is wired, tested, and safe
3. No new architecture was introduced
4. Errors are categorized, documented, and actionable
5. Documentation matches behavior exactly
6. A non-contributor successfully completes the acceptance ritual

If any item fails, V4 is **not done**.

---

## Summary of V4 Revisions

### What Changed from Original V4 TODO

**Removed (Feature Creep):**
* ❌ `resonance runs` command (requires run history infrastructure)
* ❌ `resonance status` command (requires new schema)
* ❌ `resonance explain` command (post-V4 feature)
* ❌ All observability infrastructure

**Scoped Down:**
* ✅ Observability → minimal extension to existing `doctor` command (no new tables)
* ✅ Prompt UX → explicit simple terminal UI decision (no rich TUI bikeshedding)
* ✅ Documentation → diff-based acceptance (not aspirational rewrites)

**Made Testable:**
* ✅ All "readable" / "clear" claims → golden snapshot tests
* ✅ Error messages → snapshot tests with exit codes
* ✅ CLI output → frozen format with regression detection
* ✅ "Hand it to a friend" → documented ritual with report artifacts

**Added Missing:**
* ✅ V3 Phase E prerequisite (V4 can't start without workflow commands)
* ✅ CLI surface audit (public vs internal commands)
* ✅ Upgrade safety tests (V3 → V4 state/cache compatibility)
* ✅ Dependency strategy (mutagen as optional, API key detection)

**Key Principle:**
> V4 proves usability through **snapshot-enforced guarantees**, not subjective opinions.

### V4 Scope Boundary (Locked)

**V4 IS:**
* Wiring existing code to CLI
* Freezing output formats via snapshots
* Wrapping errors with helpful messages
* Writing user-facing documentation
* Proving usability via acceptance ritual

**V4 IS NOT:**
* New features (providers, layouts, tags)
* New architecture (run history, advanced observability)
* Performance optimization
* Protocol changes (state DB schema)

---

This revised V4 TODO converts "productization" from an open-ended UX cleanup into a **bounded, testable delivery**.

# Resonance Repository Audit

**Date:** 2026-04-03  
**Scope:** Full repository — features, tech debt, architecture  
**Method:** Six parallel research subagents reading all source, doc, test, and script files; confirmed by direct file reads.  
**Baseline:** 493 tests passing, 6 skipped (post-Sprint 07)

---

## 1. Executive Verdict

### Features
**8 of 12 features are complete. Two are broken or missing in ways that block real user workflows.**

The core pipeline (scan → resolve → prompt → plan → apply) is implemented and well-tested at the unit level. Two stages are not runnable end-to-end from the CLI: `apply` fails at runtime before loading a plan (plan loading is a TODO stub), and there is no `decide` orchestration command to drive the full sequence for a real user. The `plan` command works only when `pinned_release` is injected by a caller — it cannot be invoked as a standalone CLI command.

### Tech Debt
**Nine findings. Two are critical (block real use). The highest-leverage fix is `apply.py` (~30 lines).**

The `artifacts.py` module already provides `load_plan()` and `load_tag_patch()`. The `apply` command just never calls them. This is the shortest path to unblocking the end-to-end pipeline. All other debt is medium/low severity and can be deferred without blocking product use.

### Architecture
**Overall: MOSTLY FIT. Core is sound; two structural distortions impede real use.**

The domain model is correctly layered. Provider integration is real and tested. DI via `ResonanceApp` is consistent for the `resolve` path. The two distortions are: (1) two parallel orchestration planes exist — scripts and CLI — with scripts doing what the CLI should; (2) `resonance/legacy/` is still in the production package namespace despite all tests for it being archived.

---

## 2. Feature Inventory

| Feature | Status | Reality |
|---------|--------|---------|
| `scan` | **COMPLETE** | Wired in `cli.py`, well-tested, functional |
| `resolve` | **COMPLETE** | Uses `ResonanceApp` DI, real providers, tested |
| `prompt` (interactive / replay) | **COMPLETE** | Sprint 05 fixed replay bug; record/replay tested |
| `identify` | **COMPLETE** | AcoustID + MusicBrainz two-channel, tested |
| `audit` | **COMPLETE** | Wired in `cli.py`, store inspection, tested |
| `doctor` | **COMPLETE** | Wired in `cli.py`, environment/store validation |
| `rollback` | **COMPLETE** | Transactional rollback infrastructure in `applier.py` |
| `unjail` | **COMPLETE** | Wired in `cli.py`, transitions JAILED → NEW |
| `plan` CLI command | **PARTIAL** | Raises `ValidationError` if `pinned_release` not injected; not callable standalone from CLI |
| `apply` CLI command | **BROKEN** | Plan loading is a TODO stub (`plan = None`); exits code 1 before calling `apply_plan` |
| `decide` orchestration command | **MISSING** | Sprint 07 defines it; no `decide` subparser in `cli.py` |
| Review bundle + HTML interface | **PARTIAL** | `generate_review_bundle.py` and `generate_review_interface.py` work; not wired as CLI commands; `dist/` output served by `make corpus-review` |
| `make corpus-decide` (real, interactive) | **COMPLETE** | Updated in Sprint 04 to call `corpus_decide_real_interactive.py` with real credential enforcement |
| Tag writing — real audio | **COMPLETE** as library | `MutagenTagWriter` integration-tested; default config backend is `meta-json`, not `mutagen` |

---

## 3. Feature Reality Matrix

| Feature | Documented Claim | Actual Runtime Behaviour | Status | User Impact | Evidence |
|---------|-----------------|--------------------------|--------|-------------|----------|
| `apply` command | Execute a stored plan from file; apply file moves and tag writes | Calls `apply_fn(tag_writer=writer, backend=backend)` which raises `TypeError` on the real path, OR returns exit code 1 via `plan = None` TODO stub | **BROKEN** | User cannot finalise any pipeline run from CLI | `resonance/commands/apply.py` lines 68–110 |
| `plan` command | Generate a deterministic plan for a resolved directory | Raises `ValidationError("pinned_release is required")` if called from CLI standalone (no injected release object) | **PARTIAL** | User cannot call `resonance plan` without internal knowledge | `resonance/commands/plan.py` lines 41–43 |
| `decide` command | Single-command entry point (Sprint 07 spec) | Subparser does not exist in `resonance/cli.py` | **MISSING** | User must operate scripts directly to run full workflow | `resonance/cli.py` (10 parsers, no `decide`) |
| `make corpus-decide` | Drive full real corpus workflow (scan → resolve → decide → review) | Calls `corpus_decide_real_interactive.py` with credential enforcement; real providers | **COMPLETE** | Works if credentials configured | `Makefile` lines 17–56 |
| Review bundle | CLI-accessible review generation | Script-only; `generate_review_bundle.py` requires manual invocation | **PARTIAL** | User must know about `scripts/` and call order | `scripts/generate_review_bundle.py` |
| Corpus replay | Replay recorded decisions deterministically | Working; `prompt_replay.json` has 24 real decisions | **COMPLETE** | Deterministic re-run verified | `tests/real_corpus/prompt_replay.json` |
| Tag writing (real audio) | Write tags to actual audio files | `MutagenTagWriter` tested with real FLAC; default config uses `meta-json` backend | **COMPLETE** (library); **PARTIAL** (default) | User must override default config for real audio | `tests/integration/test_real_audio_pipeline.py` |

---

## 4. Tech Debt Findings

| ID | Finding | Severity | Type | Pay-now / pay-later |
|----|---------|----------|------|----------------------|
| **T1** | `apply.py` control flow error + plan/tag-patch TODO stubs block all real apply runs | **Critical** | Incomplete feature | **Pay-now** — blocks end-to-end pipeline |
| **T2** | `plan.py` not standalone — requires injected `ProviderRelease`; raises if not provided | **High** | API design gap | **Pay-now** — blocks `resonance plan` from CLI |
| **T3** | `decide` orchestration command is missing (Sprint 07 unimplemented) | **High** | Missing feature | Pay-now (depends on T1) |
| **T4** | `resonance/legacy/` is in the production package; tests for it are archived but production code remains | **Medium** | Dead code in prod namespace | Pay-later — no functional impact but adds confusion |
| **T5** | 8 `ignore_errors = True` stanzas in `mypy.ini` — key files excluded from type checking | **Medium** | Type safety gap | Pay-later — T1 should allow removing `apply.py` stanza |
| **T6** | Two orchestration planes: CLI (`resonance` entry point) vs `scripts/corpus_decide_real_interactive.py` | **Medium** | Architectural | Pay-later (absorbed by T3) |
| **T7** | `decisions.json` is empty (`"decisions": {}`) — scripted prompt mode has no real data for offline corpus | **Low** | Data gap | Pay-later — offline workflow still works via `prompt_replay.json` |
| **T8** | Default tag backend in `settings.json` template is `meta-json` (test fixture mode), not `mutagen` (real audio) | **Low** | Config default | Pay-later — user must read docs to override |
| **T9** | `apply.py` has `[mypy-resonance.commands.apply] ignore_errors = True` — consequence of T1 | **Low** | Hygiene | Pay-now with T1 |

---

## 5. Architecture Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Core domain pipeline (scan → resolve → prompt → plan → apply) | **FIT** | Well-layered, dependency-injected, transactional `applier.py` with rollback |
| Provider integration (AcoustID / MusicBrainz / Discogs) | **FIT** | Real clients, caching, no stubs in production paths |
| DI container (`ResonanceApp`) | **MOSTLY FIT** | `from_env()` factory is sound; used consistently in `resolve` but not in `apply` / `plan` which use argument injection |
| Test suite | **FIT** | 493 passing, real audio fixtures, real corpus replay, behavioral coverage of all critical paths |
| Orchestration plane | **PARTIALLY FIT** | Two parallel planes (CLI vs scripts); `scripts/corpus_decide_real_interactive.py` does what `resonance decide` should do; Sprint 07 would unify them |
| Legacy namespace | **NOT FIT** | `resonance/legacy/` (7 files) remains in production package; `__all__ = []` prevents import pollution but namespace still exists |
| Type checking | **PARTIALLY FIT** | 8 modules excluded via `ignore_errors = True`; notably `apply.py` (consequence of broken code), `tag_writer.py`, `app.py`, `transaction.py` |

**Overall: MOSTLY FIT** — The domain model and core execution path are correctly designed and well-tested. Two features are broken or missing at the CLI level, but the underlying library code (`applier.py`, `artifacts.py`, `planner.py`) is complete and correct. The architecture would become FIT after T1+T2+T3.

---

## 6. Architectural Distortion Findings

### D1 — `apply` command bypasses its own infrastructure

`resonance/core/artifacts.py` has fully-implemented `load_plan()` and `load_tag_patch()` functions. `resonance/commands/apply.py` never calls them. The plan loading code instead contains `plan = None  # TODO` and returns exit code 1 before calling `apply_plan()`. This is not a design gap — the infrastructure exists; it was just never wired.

**Files:** `resonance/commands/apply.py` lines 93–110, `resonance/core/artifacts.py` lines 47–139

### D2 — `apply` control flow dispatches incorrectly on real path

`run_apply()` calls `result = apply_fn(tag_writer=writer, backend=backend)` unconditionally, then checks `if apply_fn is not apply_plan:`. When `apply_fn is apply_plan` (the real path), this call raises `TypeError` because `apply_plan` requires positional `plan` and `tag_patch` arguments. The guard is inverted — the simplified call should be inside the `if` block, not before it. The `[mypy-resonance.commands.apply] ignore_errors = True` stanza in `mypy.ini` suppresses detection of this error.

**Files:** `resonance/commands/apply.py` lines 68–88, `mypy.ini`

### D3 — `plan` command is not self-contained

`run_plan()` raises `ValidationError("pinned_release is required")` if called from CLI with no injection. The underlying `plan_directory()` function requires a `ProviderRelease` object, which the CLI cannot construct from arguments alone (needs a provider lookup). The command is usable only when called as a library with a caller that supplies the release object.

**Files:** `resonance/commands/plan.py` lines 41–43

### D4 — Two orchestration planes do the same work

`scripts/corpus_decide_real_interactive.py` orchestrates the full pipeline (scan → resolve → prompt → generate_review_bundle → generate_review_interface). This is exactly what a `resonance decide` CLI command should do. Both planes exist in the repository: Sprint 07 documents that `decide` should be created and that the scripts should be demoted to dev tooling, but the `decide` command was never implemented.

**Files:** `scripts/corpus_decide_real_interactive.py`, `resonance/cli.py` (no `decide` parser)

### D5 — Legacy package in production namespace

`resonance/legacy/` (7 Python files) is in the production package tree despite all its test coverage being archived in `tests/archived/`. The module's `__init__.py` declares `__all__ = []` (nothing exported) and documents "Status: CLOSED." Only `tests/archived/` files import from `resonance.legacy`. The `test_legacy_imports.py` sentinel confirms no production code imports it. The package is effectively isolated but continues to occupy the namespace and will confuse anyone reading `resonance/`.

**Files:** `resonance/legacy/` (7 files), `tests/unit/test_legacy_imports.py`

### D6 — Review surface is not CLI-accessible

`scripts/generate_review_bundle.py` and `scripts/generate_review_interface.py` are the only entry points to the review surface. They are not registered as CLI commands. `make corpus-review` serves the `dist/` directory, but only after the scripts have been manually run. The review workflow is functional but requires internal knowledge of the scripts directory.

**Files:** `scripts/generate_review_bundle.py`, `scripts/generate_review_interface.py`, `Makefile` (corpus-review target)

---

## 7. What Should Happen Next

### Immediate (blocking real use)

**1. Fix the `apply` command (T1 + D1 + D2)**

This is the highest-leverage change in the repository. The full infrastructure (`load_plan`, `load_tag_patch`, `apply_plan`) is already implemented and correct. The `apply` command just needs to call it.

Steps:
- Fix the inverted control flow in `run_apply()` (move the simplified `apply_fn()` call inside the `if apply_fn is not apply_plan:` guard)
- Replace `plan = None  # TODO` with `load_plan(args.plan, allowed_roots=())`
- Replace `tag_patch = None  # TODO` with `load_tag_patch(args.tag_patch)` if `args.tag_patch` else `None`
- Add `--tag-patch` and `--no-dry-run` arguments to the `apply` subparser in `cli.py`
- Remove `[mypy-resonance.commands.apply] ignore_errors = True` from `mypy.ini`
- Prove with a behavioral test: create a plan JSON fixture, call `run_apply()`, assert exit code 0

**2. Make `plan` command standalone (T2 + D3)**

`run_plan()` should look up the pinned release from the directory store (the store already has the pinned provider + release ID for RESOLVED directories). The command should internally construct a minimal `ProviderRelease` from stored data, removing the injection requirement for the CLI path while keeping the injection point for tests.

### Near-term

**3. Implement `decide` orchestration command (T3 + D4)**

Sprint 07 provides a complete specification. The implementation is `resonance/commands/decide.py` + a new `decide` subparser, delegating to existing scan/resolve/prompt/generate_review commands in sequence. This unifies the two orchestration planes, demotes `scripts/` to dev tooling, and gives users a single documented entry point.

**4. Update `plan` command to write plan artifact to file**

The `plan` command currently only records a hash summary in the store. It should also write the serialized plan JSON to a `--plan-output` path so that `apply` can consume it. `serialize_plan()` already exists.

### Structural

**5. Retire `resonance/legacy/` from production package (T4 + D5)**

The legacy code is isolated (nothing imports it, `__all__ = []`, tests archived). Delete the directory. Update `mypy.ini` to remove the `resonance/legacy/` exclusion. Update `test_legacy_imports.py` to assert the package does not exist (or delete it).

**6. Close mypy exclusions for corrected files (T5)**

After T1 (fix apply.py), remove `[mypy-resonance.commands.apply] ignore_errors = True`. After structural review of `app.py` and `transaction.py`, determine if type annotations can be added to close remaining exclusions.

---

## 8. Deferred Decisions

### Should `resonance decide` accept `--plan-output` to chain into a subsequent `apply`?

The `decide` command (Sprint 07 scope) could optionally persist plan artifacts to disk as it runs, enabling a two-step `decide` → `apply` workflow. Alternatively, `decide` could integrate `apply` inline (with `--dry-run` default). This affects the command interface contract and should be decided before Sprint 07 implementation to avoid a breaking change later.

### Should `resonance/legacy/` be deleted or moved to a `vendor/` tree?

The legacy code is V2 pipeline code. It has no production dependencies. Deleting it is cleanest. Moving it to `vendor/legacy/` preserves it for historical reference without occupying the `resonance.` namespace. The correct choice depends on whether any future migration guide or documentation will reference the V2 API shapes. Decision can wait until Sprint retirement cleanup.

---

## 9. Appendix: Evidence Map

| File / Artifact | Finding(s) it grounds |
|----------------|----------------------|
| `resonance/commands/apply.py` lines 68–110 | T1, D1, D2 — plan loading TODO stubs; inverted control flow |
| `resonance/core/artifacts.py` | T1, D1 — `load_plan()` and `load_tag_patch()` fully implemented; never called by apply |
| `resonance/commands/plan.py` lines 41–43 | T2, D3 — `pinned_release is None` raises ValidationError |
| `resonance/cli.py` (10 parsers, no `decide`) | T3, D4 — `decide` command absent from CLI |
| `resonance/legacy/__init__.py` | T4, D5 — `__all__ = []`, "Status: CLOSED" |
| `resonance/legacy/` (7 files) | T4, D5 — Production tree still contains legacy package |
| `tests/unit/test_legacy_imports.py` | T4, D5 — Confirms no non-legacy file imports resonance.legacy |
| `tests/archived/` (6 files with `from resonance.legacy`) | T4, D5 — All legacy imports are in archived tests only |
| `mypy.ini` (8 `ignore_errors = True` stanzas) | T5, D2 — Type errors in apply.py suppressed; key modules excluded |
| `scripts/corpus_decide_real_interactive.py` | T3, T6, D4 — Script-level orchestration doing CLI's job |
| `Makefile` lines 17–56 (corpus-decide target) | Feature inventory — `make corpus-decide` is real and complete |
| `resonance/core/applier.py` lines 193–220 | T1 — `apply_plan()` accepts `tag_patch=None`; `allowed_roots=None`; fully functional |
| `tests/real_corpus/expected_state.json` | Feature inventory — 15 RESOLVED_USER, 392 JAILED, real release IDs |
| `tests/real_corpus/prompt_replay.json` | Feature inventory — 24 recorded decisions; replay COMPLETE |
| `tests/real_corpus/decisions.json` | T7 — Empty (`"decisions": {}`); scripted offline mode has no data |
| `docs/05_execution/docs_code_remediation/07_integrated_user_workflow.md` | T3 — Full Sprint 07 spec; `decide` command not yet implemented |
| `settings.json.example` (tag_writer_backend default) | T8 — Default is `meta-json`, not `mutagen` |

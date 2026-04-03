# Sprint 01 — Fix CLI and Baseline

**Order:** 01 of 07  
**Theme:** Stabilization  
**Audit reference:** Divergence matrix rows 11 (CLI surface), plus 8 failing tests (evidence map)

---

## Why this sprint exists

The audit found that 8 tests fail at baseline and 4 CLI commands exist in code but are not registered in `cli.py`. Additionally, the `identify` command silently passes `provider_client=None`, making it a no-op. These issues undermine every subsequent sprint: they create noise in test runs, prevent users from accessing documented commands, and indicate that CLI wiring is not trusted.

No other sprint can be verified cleanly without a stable test baseline and a complete CLI surface.

---

## Problem statement

1. `PROVIDER_CALL_COUNTS` dict in `resonance/providers/caching.py` is accessed before the entry for a given provider name is initialized, causing a `KeyError` in 6 tests.
2. `tests/integration/test_resolve_cli_simple.py` and `tests/integration/test_e2e_cli_workflow.py` fail because they construct a `Namespace` object that is missing the `cache_db` attribute.
3. `audit`, `doctor`, `rollback`, and `unjail` commands are implemented in `resonance/commands/` but have no subparser registration in `resonance/cli.py` — they cannot be invoked.
4. The `identify` subcommand is registered but dispatches `run_identify(provider_client=None, fingerprint_reader=None)`, making it silently useless.

---

## Target outcome

When this sprint is genuinely complete:

- `pytest` runs with zero failures across the full suite
- `resonance --help` lists all documented commands including `audit`, `doctor`, `rollback`, `unjail`, and `identify`
- `resonance identify --help` shows provider-related options
- `resonance identify` does not crash when invoked; it either runs successfully or exits with a clear, informative error (e.g., missing API credentials)
- `resonance audit --help`, `resonance doctor --help`, `resonance rollback --help`, `resonance unjail --help` all work

---

## In scope

- `resonance/providers/caching.py` — initialize `PROVIDER_CALL_COUNTS[name]` in `__init__` before it is accessed
- `resonance/cli.py` — register `audit`, `doctor`, `rollback`, `unjail` subparsers; fix `identify` dispatch to create a real provider context
- `resonance/commands/identify.py` — ensure `run_identify()` receives a properly constructed provider client from the CLI
- `tests/integration/test_e2e_cli_workflow.py` — add `cache_db` attribute to `Namespace` constructors that are missing it
- `tests/integration/test_resolve_cli_simple.py` — same fix

---

## Out of scope

- Do not refactor providers, core domain, scoring, or canonicalization
- Do not add new CLI commands not listed in the design spec
- Do not change the golden corpus test suite
- Do not touch `scripts/` or the Makefile
- Do not add new test fixtures or corpus data
- Do not fix pre-existing documentation inaccuracies (that is Sprint 06)

---

## Required reading

- `docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md` §9 evidence map (caching bug and CLI gaps)
- `resonance/cli.py` — full file
- `resonance/providers/caching.py` — lines around `PROVIDER_CALL_COUNTS` access (audit cites line 185)
- `resonance/commands/audit.py`, `doctor.py`, `rollback.py`, `unjail.py`, `identify.py`
- `tests/integration/test_e2e_cli_workflow.py`
- `tests/integration/test_resolve_cli_simple.py`

---

## Implementation requirements

1. **Fix `PROVIDER_CALL_COUNTS` KeyError.** In `CachedProviderClient.__init__`, ensure that `PROVIDER_CALL_COUNTS[name]` is initialized to zero before any method that reads it is called. Do not assume initialization has happened in a calling context.

2. **Register missing CLI commands.** Add subparser registrations in `cli.py` for `audit`, `doctor`, `rollback`, and `unjail`. Each should expose at minimum a `--state-db` argument consistent with other commands. Follow the existing subparser registration pattern exactly.

3. **Fix `identify` dispatch.** The `identify` subcommand must construct a real `ProviderClient` (or `CachedProviderClient` wrapping the configured providers) and a real `FingerprintReader` before calling `run_identify()`. Use the same provider construction pattern as `resolve`. If provider credentials are absent, exit with a clear error rather than silently passing `None`.

4. **Fix failing test Namespace constructors.** The two failing test files construct `argparse.Namespace` objects. Add `cache_db` to every Namespace that is missing it. Do not change test intent or assertions.

5. **Verify no new test scaffolding.** Do not add mock patches or fixture workarounds to make tests pass. Fix the underlying code.

---

## Acceptance criteria

1. `pytest` exits with zero failures (all tests pass or are explicitly skipped with a documented reason).
2. `resonance --help` output contains all of: `scan`, `resolve`, `identify`, `prompt`, `plan`, `apply`, `audit`, `doctor`, `rollback`, `unjail`.
3. `resonance audit --help` exits with code 0 and prints usage.
4. `resonance doctor --help` exits with code 0 and prints usage.
5. `resonance rollback --help` exits with code 0 and prints usage.
6. `resonance unjail --help` exits with code 0 and prints usage.
7. `resonance identify --help` exits with code 0 and shows at least one provider-related option.
8. `resonance identify` invoked without credentials exits with a non-zero code and a human-readable error message (not a Python traceback from a `None` dereference).

---

## Required evidence

The executor must produce and preserve:

1. **Full `pytest` output** showing the final pass count (must be ≥ 510 passing, 0 failing).
2. **`resonance --help` terminal output** showing all 10+ commands listed.
3. **`resonance identify` invoked without provider credentials** — terminal output showing a clean error message (not `AttributeError: 'NoneType' object...`).
4. **`resonance audit --help` output** (one-liner is fine).

---

## Failure conditions

This sprint is NOT complete if:

- Any test is made to pass by adding a mock or patch rather than fixing the underlying bug
- `resonance --help` still omits any of the four previously missing commands
- `resonance identify` still crashes with a traceback on `None` dereference
- The `PROVIDER_CALL_COUNTS` fix is applied by removing the counter entirely rather than initializing it correctly
- Test count decreases (tests were removed to achieve a clean run)

---

## Dependencies

None. This is the first sprint and has no predecessors.

---

## Notes for executor

- The `PROVIDER_CALL_COUNTS` bug location is cited in the audit at `resonance/providers/caching.py:185`. Read the surrounding code before patching — the fix should be in `__init__`, not at the access site.
- The four unregistered commands likely already have `add_subparser()` or equivalent functions; you are wiring, not rewriting.
- Do not change test assertions — only fix the Namespace construction to include missing fields.
- The identify fix requires understanding how `resolve` constructs its provider context. Read that code path first.

---

## Executor prompt

```
You are implementing Sprint 01 of the Resonance docs-to-code remediation portfolio.

Sprint file: docs/05_execution/docs_code_remediation/01_fix_cli_and_baseline.md
Audit baseline: docs/process/audits/DOCS_TO_CODE_DIVERGENCE_AUDIT.md

Your task is to execute exactly the scope defined in this sprint. No more, no less.

Before making any changes:
1. Read the sprint file in full.
2. Read all files listed in "Required reading".
3. Run `pytest` and confirm you see the 8 failing tests described.
4. Run `resonance --help` and confirm the 4 missing commands are absent.

Then make the minimal changes required to satisfy all acceptance criteria.

Do not:
- Refactor providers, core domain, or scoring
- Add new tests beyond what is needed to cover the specific bugs being fixed
- Touch scripts/ or the Makefile
- Declare success without producing all required evidence items

When done, provide:
1. Full pytest output showing 0 failures
2. `resonance --help` output showing all 10+ commands
3. `resonance identify` invoked without credentials showing a clean error
4. `resonance audit --help` output

Do not claim success without this evidence.
```

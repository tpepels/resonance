# Sprint 02 - Rewire Existing CLI Through The API Boundary

## Sprint goal
Make the API layer from Sprint 01 the only execution path for current CLI commands.

## Why this sprint exists
A bounded API has no architectural value if command handlers can bypass it. This sprint removes bypass paths so both current CLI and future entrypoints run through identical orchestration and policy logic.

## In-scope deliverables
1. Route all command handlers through the API façade.
- Refactor command modules so they delegate to `ResonanceService`
- Remove direct wiring of providers/stores from command modules

2. Consolidate argument-to-contract mapping.
- Add CLI-to-API mapper utilities (for example `resonance/cli_mapping.py`)
- Ensure deterministic conversion for flags and defaults

3. Unify error and exit-code mapping.
- Commands consume API error taxonomy and map to existing exit codes
- Keep current exit-code contract stable

4. Preserve JSON envelope consistency.
- All command `--json` output comes from API event/result objects
- Human output adapter also uses same event stream

5. Add compatibility lock tests.
- Snapshot tests for key command outputs before/after rewiring

## Code touch targets
- `resonance/cli.py`
- `resonance/commands/*.py`
- `resonance/commands/output.py`
- `resonance/api/*`
- `tests/unit/test_cmd_*.py`

## Acceptance criteria
1. No command path directly invokes core orchestration bypassing API façade.
2. CLI behavior remains backward compatible for existing flags and output schema.
3. Exit codes remain stable.
4. All existing test suites pass.
5. New regression tests prove API is authoritative execution path.

## Required tests and evidence
- New: `tests/unit/test_cli_api_wiring.py`
- New: `tests/unit/test_cli_exit_code_mapping.py`
- Update: `tests/unit/test_cmd_decide.py` and related command suites for API delegation assertions
- Evidence: `pytest` full run with no regressions; include before/after command snapshot comparisons

## Out of scope
- New singular user entrypoint UX
- New automation CLI UX model
- Feature additions beyond parity

## Dependencies
Requires Sprint 01 completion.

## Risks and mitigations
- Risk: subtle output drift in command text mode.
- Mitigation: snapshot tests and strict JSON schema assertions.

## Exit gate
Sprint 02 is complete when all existing commands are API-mediated with full behavioral parity.

# Sprint 03 - Singular User Entrypoint Experience

## Sprint goal
Introduce one user-facing entrypoint from which all application features can be discovered and executed.

## Product direction
Create a single interactive shell command (for example `resonance app`) that becomes the default human interface. It should expose all major user jobs through guided flows, while delegating all execution to the bounded API.

## In-scope deliverables
1. Add a unified app entrypoint command.
- Add parser node in `resonance/cli.py` for `app`
- Add handler module (for example `resonance/commands/app.py`)

2. Implement guided workflow navigation.
- Main actions at minimum:
  - Run full pipeline
  - Resolve queued ambiguities
  - Review recent plans and outcomes
  - Run diagnostics
  - Run rollback/unjail maintenance actions
- Provide safe defaults and explicit confirmation for destructive actions

3. Add session-oriented UX context.
- Show current library root, state DB, cache DB, mode, and pending workload summary
- Surface unresolved/queued counts before action selection

4. Integrate with API modes.
- Invoke API in `interactive` mode
- Ensure prompt actions are available only where necessary

5. Add first-pass review integration.
- Include direct command from app shell to generate/open review artifacts
- Keep rendering lightweight and deterministic

## Code touch targets
- `resonance/cli.py`
- `resonance/commands/app.py` (new)
- `resonance/api/*`
- `resonance/commands/prompt.py` (adapter integration only)

## UX constraints
- Singular entrypoint must be sufficient for normal user workflows
- Existing power-user commands remain available but are no longer the primary UX path
- No hidden state mutations; every action must show what it will do

## Acceptance criteria
1. A first-time user can complete end-to-end workflow from one command entrypoint.
2. All major features are reachable from the entrypoint menu/flow.
3. Entry point delegates all execution to API layer only.
4. Ambiguous cases are handled through guided prompts inside the same session.
5. Existing standalone commands still work for compatibility.

## Required tests and evidence
- New: `tests/unit/test_cmd_app.py`
- New: `tests/integration/test_app_entrypoint_flow.py`
- Evidence: terminal recording/transcript showing discoverability of all major features from one entrypoint

## Out of scope
- Advanced TUI styling framework migration
- Remote/web UI
- Removing existing CLI commands

## Dependencies
Requires Sprint 02 completion.

## Risks and mitigations
- Risk: entrypoint becomes a thin wrapper with poor discoverability.
- Mitigation: explicit workflow IA review and integration tests for navigation paths.

## Exit gate
Sprint 03 is complete when `resonance app` is a complete, practical primary user interface for normal operations.

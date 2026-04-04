# Sprint 01 - Bounded Application API Layer

## Sprint goal
Create one architectural API boundary that becomes the only path into core functionality for both human-facing UX and automation CLI surfaces.

## Why this sprint exists
Today, command handlers and orchestration code call lower-level modules directly. That makes behavior harder to compose, harder to secure by policy, and harder to present consistently across user entrypoints.

This sprint introduces a single internal API surface so that:
- the future singular user entrypoint uses the same capabilities as the CLI
- automation behavior and interactive behavior stay consistent
- policy boundaries are explicit and testable

## In-scope deliverables
1. Add an API package with explicit contracts.
- Add `resonance/api/contracts.py`
- Define request/response models for: scan, resolve, prompt, plan, apply, decide, audit, doctor, rollback, unjail
- Define normalized error envelope and result status model

2. Add a capability-oriented application service.
- Add `resonance/api/service.py`
- Expose one façade class (for example `ResonanceService`) with bounded methods matching user jobs
- Keep all provider/state access behind this façade

3. Add invocation context and policy gates.
- Add `resonance/api/context.py`
- Define `InvocationMode` values (for example: `interactive`, `automation`, `admin`)
- Enforce policy in the API layer (for example: no interactive prompt when `automation` mode is active)

4. Add output channel abstraction.
- Add `resonance/api/output.py`
- Normalize output into one event stream model that can be rendered as human text or JSON envelope

5. Add an API composition root.
- Add `resonance/api/bootstrap.py`
- Centralize object construction and dependency wiring previously spread across command entrypoints

## Code touch targets
- `resonance/api/*` (new)
- `resonance/commands/output.py` (align envelope model)
- `resonance/errors.py` (map to API-level error taxonomy)

## Acceptance criteria
1. Every core user job is represented as an API method with typed input/output.
2. API methods can be invoked without importing command modules.
3. Invocation mode policy is enforced at API boundary.
4. Existing command behavior remains unchanged from a user perspective.
5. Unit tests prove deterministic API output shape for both text and JSON adapters.

## Required tests and evidence
- New: `tests/unit/test_api_contracts.py`
- New: `tests/unit/test_api_service.py`
- New: `tests/unit/test_api_invocation_policy.py`
- Update: command tests should pass unchanged except wiring updates
- Evidence: run a small script that calls API methods directly and shows same semantic results as CLI commands

## Out of scope
- New user interface design
- CLI argument redesign
- HTTP server exposure

## Dependencies
None. This sprint is foundational.

## Risks and mitigations
- Risk: accidental behavior drift while introducing façade.
- Mitigation: golden behavior tests comparing old command outputs to API-mediated outputs.

## Exit gate
Sprint 01 is complete when the API layer is functional, policy-aware, and fully test-covered, with no user-visible regression in existing commands.

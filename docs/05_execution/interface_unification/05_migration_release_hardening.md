# Sprint 05 - Migration, Hardening, And Release Cutover

## Sprint goal
Finalize cutover to the new interface architecture: singular user entrypoint + automation CLI profile, both protected by one bounded API.

## Why this sprint exists
Even correct architecture changes can fail in adoption without migration planning, compatibility controls, and operational confidence gates.

## In-scope deliverables
1. Compatibility and deprecation plan.
- Mark legacy direct workflows as advanced or deprecated in help/documentation where applicable
- Keep compatibility aliases for one release cycle
- Add migration notices in command output where needed

2. End-to-end acceptance matrix.
- Define acceptance matrix across:
  - normal user flow via singular entrypoint
  - automation flow via CLI profile
  - admin maintenance flow
- Ensure all routes hit same API capabilities

3. Documentation cutover.
- Update:
  - quick start to lead with singular entrypoint
  - CLI API docs to describe automation/admin posture
  - architecture docs to codify bounded API as mandatory gateway

4. Reliability and rollback readiness.
- Add high-signal smoke suite for all major workflows
- Verify rollback and failure modes remain trustworthy post-cutover

5. Release controls.
- Add release checklist with explicit gates for:
  - schema stability
  - backwards compatibility
  - operational observability
  - user-entrypoint usability proof

## Code and docs touch targets
- `resonance/cli.py`
- `resonance/api/*`
- `docs/QUICK_START.md`
- `docs/CLI_API.md`
- `docs/system/architecture.md`
- `docs/product/workflows.md`

## Acceptance criteria
1. Singular entrypoint is default path in docs and onboarding.
2. Automation/admin CLI profile is explicitly documented and proven with scripts.
3. API boundary is mandatory and bypasses are prevented by tests/lints.
4. Migration notes and compatibility windows are published.
5. Full test suite and smoke suite pass.

## Required tests and evidence
- New: `tests/integration/test_interface_cutover_smoke.py`
- New: `tests/unit/test_no_api_bypass_guards.py`
- Evidence: release checklist artifact and successful smoke transcript for user + automation + admin scenarios

## Out of scope
- Large redesign of core matching algorithms
- New provider integrations unrelated to interface architecture

## Dependencies
Requires Sprint 03 and Sprint 04 completion.

## Risks and mitigations
- Risk: partial adoption leaves fragmented user experience.
- Mitigation: docs-first cutover, compatibility aliases, and hard gate tests that reject API bypass.

## Exit gate
Sprint 05 is complete when the project has one trusted architecture: singular user entrypoint for humans, automation/admin CLI for power use, and one bounded API in front of both.

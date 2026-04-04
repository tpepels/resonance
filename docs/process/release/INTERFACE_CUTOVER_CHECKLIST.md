# Interface Cutover Release Checklist

## Scope
Cutover to:
- singular human entrypoint via `resonance app`
- automation/admin expert CLI usage profiles
- bounded API layer as the mandatory execution gateway

## Release gates
1. Full tests pass in CI and local baseline
2. API bypass guard tests pass
3. JSON envelope schema tests pass
4. App entrypoint smoke tests pass
5. Automation/admin smoke tests pass
6. Docs updated for app-first onboarding and automation profile

## Evidence links
- Unit: `tests/unit/test_no_api_bypass_guards.py`
- Unit: `tests/unit/test_output_envelope_validation.py`
- Unit: `tests/unit/test_api_contracts.py`
- Integration: `tests/integration/test_app_entrypoint_flow.py`
- Integration: `tests/integration/test_cli_automation_mode.py`
- Integration: `tests/integration/test_interface_cutover_smoke.py`

## Operational checks
1. `resonance app --help` is available
2. `resonance decide --mode automation --json` succeeds on empty library
3. `resonance prompt --mode automation` without scripted input returns validation error
4. `resonance resolve --mode automation --fail-on-warning` returns non-zero when prompt queue is created

## Signoff
- Engineering:
- QA:
- Product:
- Date:

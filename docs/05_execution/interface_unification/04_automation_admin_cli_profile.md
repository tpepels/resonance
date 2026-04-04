# Sprint 04 - Automation/Admin/Power-User CLI Profile

## Sprint goal
Reframe CLI usage around automation and operations: deterministic, scriptable, policy-bound execution with minimal interactive assumptions.

## Product direction
Keep CLI as the expert surface, optimized for:
- CI/CD pipelines
- unattended batch jobs
- operators managing large libraries
- troubleshooting and recovery workflows

All CLI commands must execute through the same bounded API in `automation` or `admin` mode.

## In-scope deliverables
1. Define explicit automation mode behavior.
- No interactive prompts unless explicitly requested
- Deterministic output and stable JSON contracts
- Clear non-zero exit semantics for partial or blocked runs

2. Add admin-oriented orchestration commands.
- Batch requeue/unjail/retry operations
- Bulk inspection summaries
- Dry-run defaults with explicit apply confirmation patterns

3. Standardize machine output contracts.
- JSON schema versioning for command envelopes
- Include run identifiers, timestamps, and stage status blocks
- Include deterministic fields suitable for diffing and alerting

4. Add profile-level flags.
- Shared flags for automation safety (for example: `--headless`, strict fail-on-prompt, strict fail-on-warning)
- Preserve backward compatibility with current flags

5. Add operational observability hooks.
- Structured logs and event categories for pipeline stages
- Optional audit artifact output path for operators

## Code touch targets
- `resonance/cli.py`
- `resonance/commands/decide.py`
- `resonance/commands/resolve.py`
- `resonance/commands/doctor.py`
- `resonance/api/*`

## Acceptance criteria
1. CLI is fully non-interactive by default in automation/admin modes.
2. Operators can run end-to-end flows with predictable exit codes and structured outputs.
3. Existing standalone command functionality remains intact.
4. Power-user maintenance tasks are first-class and documented in help output.
5. JSON outputs are schema-tested and stable.

## Required tests and evidence
- New: `tests/integration/test_cli_automation_mode.py`
- New: `tests/integration/test_cli_admin_operations.py`
- New: `tests/unit/test_json_schema_stability.py`
- Evidence: scripted run examples demonstrating unattended operation and predictable failure behavior

## Out of scope
- Replacing shell CLI with external orchestrator
- Introducing network API transport

## Dependencies
Requires Sprint 02 completion. Can overlap partially with Sprint 03 if API contracts are stable.

## Risks and mitigations
- Risk: conflicting UX needs between normal users and automation users.
- Mitigation: strict mode separation at API invocation context and command profiles.

## Exit gate
Sprint 04 is complete when CLI is demonstrably excellent for automation and operations without sacrificing compatibility.

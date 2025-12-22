# GOVERNANCE_MIN

Rules are binding. Versions close only if: DoD complete, all gates green, audit has no Must-Fix items, no critical-path placeholders. Closure is a semantic contract.

## Docs Layout (Canonical)
/docs
- specs/ : post-closure authoritative specs only
- process/
  - versions/ : TDD_TODO_Vx.md (executable intent, incomplete by design)
  - audits/ : AUDIT_Vx.md (closure decisions)
  - GOVERNANCE.md + GOVERNANCE_MIN.md
  - AUDIT_TEMPLATE.md + AUDIT_TEMPLATE_MIN.md
- <project>_DESIGN_SPEC.md : architecture, boundaries, invariants

Misplaced or duplicated docs may block closure.

## Gates
Tier0: deterministic lint+format, static typing, fast unit tests.
Tier1: full deterministic tests, coverage policy, offline semantics.
Tier2: Tier1 + install/CLI smoke + docs.

## Quality
- Tools replaceable; guarantees are not.
- Public APIs typed; ignores justified.
- Wiring files >0% coverage.
- Non-legacy 0% modules: test, delete, legacy, or justify.
- High-risk paths test success+failure.
- Semantic invariant tests for critical behavior; never weakened silently.

## Tests
Unit: fast, deterministic, no network.
Integration: deterministic, temp FS only.
Manual/network: opt-in, excluded from Tier1.

## Placeholders
Allowed only if tracked, unreachable silently, and guarded by tests.
Forbidden: silent fallbacks, degenerate queries, plausible fake data.

## Regressions
Closed-version guarantees are binding.
Regressions must be restored, deprecated (audit), or version-gated.

## Overengineering
Each version declares goals, non-goals, concept budget.
New abstractions must justify a gate/invariant and be reviewed next audit.
Prefer deletion or explicit failure over speculation.

## AI
AI may not add abstractions or weaken tests without a gate.
Ambiguity must be surfaced.
Gate changes and closures are human-authorized.

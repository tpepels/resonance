# AUDIT_TEMPLATE_MIN (Vx)

Audit is a decision record.

## Meta
Version, Date, Auditor, AI agents, Commit, Previous version

## Decision
Status: FAIL / PASS(CONDITIONS) / PASS
Annotation (if pass): CLOSED / FRAGILE / DEBT
Rationale + Confidence (High/Med/Low)

## Must-Fix
List blocking findings (module, violated invariant, required fix).

## Accepted Debt
Follow-ups with target versions.

## Architecture
Boundaries respected? Public APIs explicit? Wiring centralized?
List architectural changes and risk delta.

## Correctness
No new nondeterminism without injection.
Offline semantics deterministic.
Inventory all nondeterminism (unlisted = Must-Fix).

## Safety
Rollback/compensation present where required.
Crash consistency holds.
Analyze blast radius: corruption, detectability, rollback, delta.

## Tests/Coverage
Tier0/Tier1/Tier2 results.
Wiring coverage ok?
Any non-legacy 0% modules (A/B/C/D)?
Critical tests assert domain invariants; not weakened.

## Placeholders
No critical-path placeholders.
Remaining ones tracked, flagged off, and guarded by tests.
No implicit placeholders.

## Regressions
No closed-version invariants broken.
If broken: restore / deprecate / version-gate.

## Overengineering
Scope respected.
List new abstractions with justification.
Unused abstractions = Must-Fix.

## AI Review
No speculative abstractions.
No weakened tests.
Ambiguity surfaced.

## Closure
Close? Yes/No.
Blocking actions or roll-forward items.
Auditor signature.

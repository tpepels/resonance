# AUDIT TEMPLATE — Version Vx

> Copy this file to `docs/process/AUDITS/AUDIT_Vx.md` and complete it during version closure review.
> This audit is a **decision record**, not a checklist exercise.

---

## Metadata

- Version: Vx
- Date:
- Auditor (human / agent):
- AI agents involved (if any):
- Commit / tag:
- Previous closed version:

---

## 1) Summary & Decision

### Overall status
- ⬜ ❌ **FAIL** — Must-fix items block closure
- ⬜ ⚠️ **PASS (WITH CONDITIONS)** — Closure allowed with annotations
- ⬜ ✅ **PASS** — Eligible for closure

### Closure annotation (if passing)
- ⬜ CLOSED
- ⬜ CLOSED (FRAGILE)
- ⬜ CLOSED (DEBT)

### Decision rationale
Brief explanation of *why* this version is or is not acceptable.
Focus on risk, not effort expended.

### Confidence level
- ⬜ High
- ⬜ Medium
- ⬜ Low

If Medium or Low, explain what could invalidate this assessment.

---

## 2) Must-Fix Findings (Block Closure)

List **all** findings that must be resolved before the version can close.

- [ ] Item 1:
- [ ] Item 2:

Each must-fix item must reference:
- affected module(s)
- violated gate or invariant
- required resolution

---

## 3) Follow-Ups / Accepted Debt

Issues explicitly accepted and rolled into a future version.

- [ ] Follow-up 1 (target version):
- [ ] Follow-up 2 (target version):

Accepted debt must not violate closed-version guarantees.

---

## 4) Architecture & Boundaries

### Boundary compliance
- [ ] No forbidden cross-module dependencies introduced
- [ ] Public APIs are explicit and documented
- [ ] Composition root / wiring remains centralized

### Architectural changes since last version
- New modules introduced:
- Modules deleted:
- Boundaries tightened:
- Boundaries loosened:

### Risk assessment
Did these changes reduce, preserve, or increase architectural risk?

### Findings
- Notes:

---

## 5) Correctness & Determinism

### Determinism checks
- [ ] No new nondeterminism introduced without explicit injection
- [ ] Offline semantics remain deterministic where required
- [ ] Reruns do not trigger rematching unless explicitly intended

### Nondeterminism inventory
List all sources of nondeterminism introduced or modified in this version,
and how each is controlled (e.g., injection, seeding, isolation).

Unlisted nondeterminism is a **must-fix** finding.

### Findings
- Notes:

---

## 6) Safety & Robustness

### Safety guarantees
- [ ] Filesystem mutation paths have rollback or compensating actions where required
- [ ] Crash consistency rules still hold (if applicable)
- [ ] Error modes are explicit, actionable, and non-silent

### Blast radius analysis
If a failure occurs in this version:
- What state can be corrupted?
- Is the failure detectable?
- Is rollback possible?
- Is the blast radius larger than in the previous version?

### Findings
- Notes:

---

## 7) Test Suite & Coverage

### Gate results
- Tier 0 gates: ⬜ ✅ / ⬜ ❌
- Tier 1 gates: ⬜ ✅ / ⬜ ❌
- Tier 2 gates (if applicable): ⬜ ✅ / ⬜ ❌

### Coverage policy compliance
- Wiring coverage gates satisfied? ⬜ ✅ / ⬜ ❌
- Any non-legacy 0% modules remaining? ⬜ No / ⬜ Yes

If **Yes**, list each and its resolution (A/B/C/D per GOVERNANCE):
- Module:
- Resolution:

### Semantic adequacy
- [ ] Critical tests assert domain-level invariants (not implementation details)
- [ ] No critical tests were weakened or trivialized in this version
- [ ] Failure messages meaningfully explain invariant violations

### Findings
- Notes:

---

## 8) Placeholder & Bypass Review

### Search terms checked
(e.g. TODO, FIXME, placeholder, NotImplementedError, pass, stub)

### Checks
- [ ] No critical-path placeholders remain
- [ ] Remaining placeholders are feature-flagged off and tracked in next `TDD_TODO`
- [ ] Tests exist preventing silent placeholder execution
- [ ] No implicit placeholders (degenerate queries, default fallbacks, heuristic stubs)

### Findings
- Notes:

---

## 9) Regression Review (Closed-Version Contracts)

- [ ] No previously closed-version invariants were violated
- [ ] No tests enforcing past guarantees were weakened or removed

If violations exist, resolution strategy:
- ⬜ Restore invariant
- ⬜ Deprecate via audit addendum
- ⬜ Quarantine behind explicit version gate

Details:
- Notes:

---

## 10) Overengineering Review

### Scope discipline
- [ ] Version goals and non-goals respected
- [ ] Allowed new-concepts budget not exceeded

### New abstractions introduced
For each abstraction, list:
- Name:
- Purpose:
- Proof obligation satisfied:
- Gate or test justifying it:

Unused abstractions are a **must-fix** finding.

### Findings
- Notes:

---

## 11) AI-Specific Review (If Applicable)

- [ ] AI-generated changes did not introduce speculative abstractions
- [ ] Ambiguities were surfaced rather than silently resolved
- [ ] AI did not weaken or delete existing gates or tests
- [ ] AI-preferred deletion or explicit failure over speculation

### Findings
- Notes:

---

## 12) Closure Decision

### Close version?
- ⬜ Yes
- ⬜ No

If **No**, list required actions blocking closure:
- [ ] Action 1:
- [ ] Action 2:

If **Yes**, list follow-ups rolling forward:
- [ ] Follow-up 1 (target version):
- [ ] Follow-up 2 (target version):

Auditor signature (name / handle):

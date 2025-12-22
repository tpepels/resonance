# GOVERNANCE
### Quality Gates, Audits, and Version Closure Rules

## Purpose

This repository is developed using **Test-Driven Milestone Gating with Executable Specifications**.

Version files (`docs/process/VERSIONS/TDD_TODO_V*.md`) are **contracts**: a version is closed only when its gates are mechanically satisfied.

This document defines **global governance rules** that apply to every version, including AI-assisted development.

---

## Documentation Structure (Canonical)

All documentation MUST follow this directory layout.
Indentation and nesting are normative.

```
/docs
├─ specs/
│  └─ Vx_SPEC.md
│     (post-closure, authoritative specifications per version)
│
├─ process/
│  ├─ audits/
│  │  └─ AUDIT_Vx.md
│  │     (one audit per version)
│  │
│  ├─ versions/
│  │  └─ TDD_TODO_Vx.md
│  │     (actionable, executable version contracts)
│  │
│  ├─ GOVERNANCE.md
│  ├─ GOVERNANCE_MIN.md
│  │  (semantically equivalent; AI-context optimized)
│  │
│  ├─ AUDIT_TEMPLATE.md
│  └─ AUDIT_TEMPLATE_MIN.md
│     (semantically equivalent; AI-context optimized)
│
└─ <project_name>_DESIGN_SPEC.md
   (project/module architecture and invariants)
```

### Directory Semantics

**/docs/**
- Root of all non-code authoritative documentation

**/docs/process/**
- Governs *how* work is done
- Forward-looking and evaluative artifacts only

**/docs/process/versions/**
- Executable intent
- Incomplete by design
- Defines scope, gates, and DoD for a version

**/docs/process/audits/**
- Closure decisions
- Risk acceptance records
- One audit per version

**/docs/process/GOVERNANCE*.md**
- Global rules
- Apply to all versions
- `_MIN` variants MUST be semantically identical

**/docs/specs/**
- Backward-looking
- Post-closure only
- Reflect audited, stable truth

**/docs/<project_name>_DESIGN_SPEC.md**
- Architectural definition and invariants
- Defines boundaries, terminology, and intent
- Changes require audit visibility

### Structural Rules

- Planning and executable intent live ONLY in `/docs/process/versions/`
- Closure decisions live ONLY in `/docs/process/audits/`
- Stable, closed specifications live ONLY in `/docs/specs/`
- No closed-version material may remain solely in `/versions/`
- `_MIN.md` files MUST mirror their full counterparts exactly in meaning

Misplaced, duplicated, or stale documentation is a **process defect** and may block version closure.

---

## 1. Definitions

### Gate
A mechanically verifiable requirement enforced by:
- tests, or
- static analysis, or
- coverage policies, or
- reproducible scripts.

### Version closure
A version `Vx` is closed only when:
- all `TDD_TODO_Vx` checkboxes required for DoD are satisfied
- all governance gates are green
- the audit bundle for `Vx` has no “Must Fix” findings
- no critical-path placeholders remain (see §6)

Version closure represents a **semantic contract**, not merely a passing CI state.

---

## 2. Gate Tiers

### Tier 0 — Fast Gates (run continuously)
Must be green for any merge to main:
- linting (deterministic, auto-enforced)
- formatting (deterministic, auto-enforced)
- static type checking (scoped; see §3)
- pytest unit suite (fast)

### Tier 1 — Integration Gates (required for version closure)
- full test suite (unit + integration), excluding explicit manual/network tests
- coverage policy compliance (see §4)
- deterministic/offline semantics tests for relevant features

### Tier 2 — Release Gates (required for deployable releases, e.g., V4)
- all Tier 1 gates
- packaging/install smoke test
- CLI UX smoke tests (golden transcripts if applicable)
- documentation present and accurate:
  - quickstart
  - troubleshooting

---

## 3. Static Quality Standards

### 3.1 Linting and Formatting (Required)

The codebase must conform to a **uniform, automatically enforceable linting and formatting standard**.

Requirements:
- enforced automatically (no manual review)
- deterministic (same input → same output)
- run as part of Tier 0 gates

The specific tool(s) used (e.g. ruff, flake8, black, future tools) are an implementation detail and may change, provided these guarantees remain true.

---

### 3.2 Static Typing and Type Checking (Required)

The codebase must provide **static guarantees** that prevent entire classes of runtime errors.

Requirements:
- public APIs must be statically typed
- type checking must run automatically as part of Tier 0 gates
- type ignores require explicit justification

Typing may be adopted progressively:
- a defined “typed core” is always type-checked
- additional modules may be added over time

The specific checker (e.g. mypy, pyright, pyre) is an implementation choice, not a governance requirement.

---

## 4. Coverage Policy (Semantic Coverage)

Coverage is not a vanity metric. It is used to detect:
- unexecuted wiring paths
- dead code that claims importance
- placeholder-backed “integration”

### 4.1 Wiring Coverage Gates
Certain files must have **> 0% coverage** to prove real execution wiring is exercised.
Each version may add additional wiring gates in its `TDD_TODO`.

### 4.2 0% Module Policy
Any **non-legacy production module** with 0% coverage must be resolved by exactly one:
- (A) add a smoke-level test to raise coverage > 0%, OR
- (B) remove the module, OR
- (C) move it to `legacy/`, OR
- (D) exclude it from coverage with a written justification (in the relevant `TDD_TODO` and/or audit)

### 4.3 Branch / Critical-Path Coverage
For high-risk behaviors (e.g. filesystem mutation, cache misses, rollback correctness):
- both success and failure paths must be explicitly exercised
- branch coverage expectations are risk-weighted, not uniform

### 4.4 Semantic Invariant Tests
For critical behaviors, at least one test must assert:
- a non-obvious, domain-level property
- using semantic assertions rather than implementation details
- with a failure message that explains *why* the behavior matters

Semantic invariant tests may not be weakened or deleted without explicit audit justification.

---

## 5. Test Taxonomy

### Unit tests
- fast
- no network
- no filesystem mutation outside temp dirs
- deterministic

### Integration tests
- may hit filesystem via temp dirs
- may exercise composition root / CLI wiring
- must remain deterministic
- network disabled by default unless explicitly marked as manual

### Manual / networked tests
- opt-in only
- excluded from Tier 1 gates
- must be clearly marked and documented

---

## 6. No-Placeholder / No-Bypass Policy

Placeholders are permitted only if they:
- are explicitly tracked in the current or next version `TDD_TODO`, AND
- cannot be invoked silently in production (must raise an explicit error or be feature-flagged off), AND
- have at least one test proving they cannot masquerade as a working path

Forbidden:
- silent fallbacks that “sort of work”
- degenerate queries (e.g. calling providers with empty hints)
- stubs returning plausible-looking data without exercising real logic

---

## 7. Regression Policy

Closed-version guarantees are **binding contracts**.

Rules:
- tests enforcing closed-version behavior may not be weakened or deleted
  without an explicit audit note and decision log entry
- any change that violates a previously closed invariant is a regression,
  even if newer-version gates remain green

A regression must be resolved by exactly one:
- (A) restoring the invariant
- (B) formally deprecating it via an audit addendum
- (C) quarantining the behavior behind an explicit version gate

Silent invariant erosion is forbidden.

---

## 8. Audit Policy (Required for Each Version Closure)

A version may not close until an audit has been performed using
`docs/process/AUDIT_TEMPLATE.md` and recorded as
`docs/process/AUDITS/AUDIT_Vx.md`.

The audit must include:
- architecture boundary review
- safety and robustness review
- test and coverage review
- placeholder and bypass review
- regression risk assessment
- overengineering check (§9)

Audit findings are classified as:
- Must Fix (blocks closure)
- Should Fix (tracked explicitly)
- Observations

---

## 9. Overengineering Protections

### 9.1 Scope Budget
Each version must declare:
- explicit goals
- explicit non-goals
- an “allowed new concepts” budget (e.g. number of new modules or abstractions)

### 9.2 Proof Obligation for New Abstractions
Any new abstraction must satisfy **at least one** of the following and be justified by a gate or test that would be difficult or impossible to express otherwise:

- enables a gate or test that could not otherwise exist
- removes existing duplication or isolates nondeterminism
- enforces an architectural boundary

If none apply, the abstraction is rejected as overengineering.

### 9.3 Abstraction Lifecycle
Any abstraction introduced must:
- be referenced by at least one gate or test in the same version
- be reviewed for deletion in the next version audit

Unused abstractions are presumed overengineering and must be removed.

### 9.4 Deletion Bias
When intent is unclear, prefer:
- deleting code
- narrowing scope
- or failing explicitly

over adding generality or defensive layers.

Deletion that preserves gates is always acceptable.

---

## 10. AI Interaction Constraints

AI agents:
- may not introduce new abstractions without a corresponding gate or test
- may not weaken or delete existing tests or assertions
- must surface ambiguity rather than resolve it silently
- must prefer deletion over speculation when intent is unclear

Any AI-generated code introducing a new concept must cite:
- the gate it satisfies, or
- the invariant it enforces

Gate definitions, waivers, and closures are human-authorized actions.

---

## 11. Gate Authority and Escalation

- Gates may only be modified or waived by the human maintainer
- AI agents may propose gate changes but may not implement them
- Any gate waiver requires:
  - written justification
  - an associated audit note
  - an explicit expiration version

Permanent waivers are forbidden.

---

## 12. Version Closure Annotations

Version closure may include annotations:
- **CLOSED** — all gates satisfied
- **CLOSED (FRAGILE)** — low confidence; early re-audit required
- **CLOSED (DEBT)** — known debt tracked explicitly for the next version

Annotations must be justified in the audit.

---

## 13. Operational Assumptions

This governance model assumes:
- deterministic execution environments
- controlled inputs
- non-hostile data

If these assumptions change, new gates are required.

---

## 14. Version Closure Checklist (Global)

To close `Vx`:
- [ ] Tier 0 gates green
- [ ] Tier 1 gates green
- [ ] Coverage policy satisfied
- [ ] Audit completed; no “Must Fix” findings
- [ ] No unresolved critical-path placeholders
- [ ] `TDD_TODO_Vx` DoD checkboxes complete
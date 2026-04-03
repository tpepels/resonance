# Contributing to Resonance

## Purpose

This document defines how contributors should approach work in the Resonance repo. The goal is to keep development anchored to product truth rather than drifting into test-targeting or implementation theater.

## Start from the product, not the tests

Before changing code, identify which user job or product guarantee the change improves.

Good starting questions:

- which user problem does this solve?
- which product guarantee does this protect?
- how will a human organizing a music library experience the improvement?

If the answer is only “this makes a test pass,” the work is probably underspecified.

## Preferred development order

Contributors should generally reason in this order:

1. product purpose and user job
2. workflow impact
3. domain or decision model impact
4. implementation changes
5. test coverage and verification

This ordering reduces the risk that internals start defining the product.

## Documentation-first expectation for major changes

For major behavior changes, update the relevant docs alongside the implementation.

Typical documentation touchpoints:

- `docs/product/` when user-visible behavior or guarantees change
- `docs/system/` when architecture or stable contracts change
- `docs/dev/` when workflow, testing, or contributor practice changes

## Guardrails for agent-driven development

Because Resonance may be developed with coding agents, contributors should make the intended product behavior very explicit.

When writing implementation prompts or sprint plans:

- describe the user-facing outcome first
- define what counts as behavioral proof
- avoid goals stated only as internal refactors unless those refactors serve a named product need
- state non-goals to prevent unrelated work

## Acceptance discipline

Resonance should prefer behavioral acceptance over rhetorical acceptance.

Examples of strong acceptance:

- a user can review ambiguous cases without opening raw JSON
- REAL mode performs observable provider-backed decision generation
- replay mismatch produces hard failure in a real rerun

Examples of weak acceptance:

- validation code exists
- a fixture was added
- an interface looks cleaner

Those may be useful, but they are not automatically product proof.

## How to think about tests

Tests are essential, but they are not the product definition.

Use tests to:

- protect product guarantees
- verify stable system contracts
- defend against regressions in user-visible behavior

Do not use tests to:

- substitute for a missing product model
- reward implementation shortcuts that bypass real workflows
- treat synthetic fixture success as equivalent to real authoritative behavior

## Scope discipline

Keep changes tightly related to the product problem being solved.

Avoid:

- unrelated refactors bundled with feature work
- documentation that only mirrors code structure
- introducing new flags or modes when a simpler top-level workflow is preferable

## Recommended contribution checklist

Before marking work complete, verify:

- the change maps to a clear user job or guarantee
- the docs reflect the intended behavior
- the primary workflows remain understandable
- important behavior is proven, not merely claimed
- tests defend the right product semantics

## Summary

A good Resonance contribution makes the system more useful, more reviewable, or more trustworthy for a person organizing a music library. The repo should reward that kind of work, not just test-passing choreography.

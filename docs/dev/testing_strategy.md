# Resonance Testing Strategy

## Purpose

This document defines how testing should support Resonance without replacing the product specification.

The problem this strategy addresses is common: when a repo lacks a clear product model, tests become the most concrete truth in the codebase. Agents and contributors then optimize for passing tests instead of delivering trustworthy user-facing behavior.

Resonance should avoid that trap.

## Testing principle

Tests exist to protect product behavior and stable contracts.

They do not define the entire purpose of the system.

## What tests should protect

The test suite should primarily defend the following categories.

### 1. Product guarantees

Examples:

- ambiguity remains explicit
- replay fails loudly on mismatch
- primary workflows stay simple and coherent
- review outputs remain navigable and inspectable

### 2. Stable domain and system contracts

Examples:

- decision objects contain the required identity and authority information
- replay records preserve required validation context
- review artifacts preserve inspectable evidence structure

### 3. Real-path behavior where possible

Examples:

- authoritative workflows exercise actual orchestration
- provider-backed flows are observable in real mode
- replay validation can be demonstrated behaviorally

## Test pyramid for Resonance

A useful shape for the test strategy is:

### Unit tests

Protect pure logic and stable transformations.

Use for:

- matching heuristics
- identity calculations
- prompt fingerprint generation
- decision record validation

### Contract tests

Protect stable interfaces between layers.

Use for:

- provider adapters
- review bundle schemas
- replay record validation expectations

### Workflow tests

Protect end-to-end product behavior.

Use for:

- decide workflow semantics
- review generation semantics
- replay success and replay failure

### Real corpus acceptance runs

Protect the highest-value behavioral claims.

Use for:

- real provider-backed execution
- actual decision recording
- proof that mismatch fails hard in practice

## What tests should not become

The test suite should not become:

- a fake product spec narrower than real user needs
- a collection of fixture tricks that bypass the real system
- an incentive structure where contributors optimize for synthetic green paths rather than trustworthy workflows

## Behavioral proof vs implementation presence

Important claims should be backed by behavioral evidence when possible.

For example, replay acceptance is stronger when the system has demonstrated:

1. a real run recording decisions
2. a replay run succeeding under matching conditions
3. a replay run failing under intentional mismatch

That tells us more than a unit test of a validation helper alone.

## Good acceptance-oriented tests

Strong Resonance tests often express user-visible semantics. Examples:

- a reviewer can inspect why a directory matched a candidate release
- ambiguous cases remain unresolved when evidence is insufficient
- chunked review outputs are emitted rather than only a giant monolith
- replay refuses changed prompt structure

## Anti-patterns to avoid

### Test-defined architecture

When code structure is optimized primarily around test convenience rather than product clarity.

### Fake end-to-end tests

When “end-to-end” tests run a special simplified path that users never actually rely on.

### Assertion theater

When tests verify that files exist or functions were called but do not verify meaningful user outcomes.

## Practical guidance for new tests

When adding a test, answer these questions:

- which user job or product guarantee does this test defend?
- would this test still matter if the internal implementation changed?
- does the test encourage real functionality or test-targeting behavior?

If those answers are weak, the test probably needs reframing.

## Summary

Resonance needs tests that act like guardrails, not puppet strings. The right suite protects trust, replay integrity, reviewability, and real workflow behavior while leaving room for implementation to evolve in service of the product.

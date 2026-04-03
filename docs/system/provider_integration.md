# Resonance Provider Integration

## Purpose

Providers supply external metadata and release information that helps Resonance interpret what a library directory likely represents. Provider integration should support user trust, not undermine it.

This document defines the role of providers within the system.

## Product role of providers

From the user’s perspective, providers are evidence sources, not ultimate authorities.

They help Resonance answer questions such as:

- what release candidates plausibly match this directory
- whether a track list aligns with a known edition
- whether multiple plausible releases remain in play

A provider response should therefore be treated as an input to interpretation, not as unquestionable truth.

## Architectural role of providers

Provider integration belongs beneath the decision model and user workflow.

Providers should support:

- candidate discovery
- candidate enrichment
- evidence comparison
- ambiguity detection

Providers should not define the product model of Resonance. The repo should still make sense even if provider details change.

## Principles for provider integration

### Providers provide evidence, not authority

A provider match should contribute to confidence, but not erase ambiguity where ambiguity still exists.

### Provider behavior must be visible in REAL mode

When the product claims to have run the real authoritative workflow, provider-backed evidence gathering should actually occur where expected.

### Provider variance should not silently distort replay

Replay should not depend on fresh provider behavior in a way that changes the meaning of a previously accepted choice.

### Provider interfaces should be isolatable

Different providers may have different response styles, quality levels, and failure modes. The system should isolate those variations behind stable internal interfaces.

## Evidence flow

A healthy provider integration flow looks like this:

1. local corpus evidence is gathered
2. provider queries are formed from that local context
3. providers return candidate metadata or release matches
4. the system evaluates those candidates against local evidence
5. the decision layer determines whether authority is automatic, ambiguous, or requires human input

This prevents the system from becoming a thin wrapper around remote metadata lookups.

## Provider-related failure handling

Provider integration should fail in a way that preserves product trust.

Examples:

- provider unavailability should not be disguised as clean certainty
- low-confidence or conflicting provider results should remain reviewable
- missing provider support should degrade the interpretation path gracefully rather than silently fabricating confidence

## Development implications

Good provider-related development work tends to improve one or more of the following:

- clearer candidate evidence
- better handling of conflicting results
- more legible explanations for why a candidate was chosen
- better escalation of ambiguous cases
- cleaner boundaries between provider adapters and decision orchestration

Bad provider-related work often looks like:

- provider-specific assumptions leaking into product language
- tests that validate adapter trivia without improving user trust
- hidden heuristics that make results look authoritative without exposing uncertainty

## Acceptance examples

Useful provider acceptance criteria include:

- a real authoritative run performs observable provider-backed resolution
- a reviewer can see which candidate evidence informed a release match
- conflicting provider candidates cause review or ambiguity rather than false certainty
- replay does not silently reinterpret past decisions based on changed live provider behavior

## Summary

Providers are evidence engines inside Resonance, not the product itself. Their integration should strengthen interpretation quality, reviewability, and trust without allowing remote metadata behavior to silently define authority.

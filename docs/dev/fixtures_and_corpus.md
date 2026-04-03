# Resonance Fixtures and Corpus Guidance

## Purpose

This document explains how fixtures, sample corpora, and real corpus runs should be used in Resonance development.

These resources are important, but they must support product truth rather than replace it.

## Distinguish three kinds of inputs

### 1. Small synthetic fixtures

These are controlled inputs used for focused tests.

Use them to validate:

- parsing behavior
- edge-case matching logic
- replay record validation details
- schema and contract expectations

They are useful because they are small, deterministic, and cheap to run.

### 2. Representative sample corpora

These are medium-scale, more realistic inputs used to exercise workflow behavior under plausible library conditions.

Use them to validate:

- mixed directory structures
- ambiguity patterns
- duplicate-like scenarios
- review artifact generation at moderate scale

### 3. Real corpus runs

These are authoritative behavioral exercises over a real library or real extracted metadata set.

Use them to validate:

- real workflow equivalence
- provider-backed decision generation
- actual decision recording
- replay acceptance and rejection behavior
- review usability at real scale

## Why the distinction matters

A major repo failure mode is treating fixtures as if they are equivalent to real product behavior.

They are not.

Synthetic fixtures can prove logic. They cannot by themselves prove that the real product workflow behaves correctly under real conditions.

## Recommended use of corpus artifacts

Artifacts such as metadata snapshots, expected state files, expected layout files, and review bundles should be understood as evidence of workflow behavior, not as the product itself.

They are useful for:

- regression detection
- review inspection
- workflow reproducibility
- acceptance evidence

They are less useful when they become opaque files that nobody can relate back to a user story.

## Fixture design principles

Good fixtures:

- isolate one meaningful behavior at a time
- use names and structures that map to human-recognizable scenarios
- are small enough to understand quickly
- make ambiguity explicit when ambiguity is part of the case

Bad fixtures:

- encode arbitrary internals with no user-facing meaning
- bypass decision or replay semantics
- produce green tests while masking workflow deficiencies

## Real corpus acceptance discipline

When a claim depends on real workflow semantics, prefer a real corpus acceptance path.

Examples include:

- proving that REAL mode actually records multiple human decisions
- proving that provider-backed resolution occurs in practice
- proving that replay mismatch fails hard on an altered recorded choice

These are not merely fixture-level claims.

## Review artifact expectations

Review artifacts derived from corpora should remain inspectable and chunked where necessary. Large monolithic outputs are often difficult for both humans and agents to work with.

A corpus-related review output is healthy when:

- it maps back to meaningful decision subjects
- ambiguity is visible
- directory-level inspection is practical
- a reviewer does not need to ingest everything at once

## Contributor guidance

When adding or updating fixtures and corpus artifacts, document:

- what user-visible behavior they represent
- whether they are synthetic, representative, or real
- what they are intended to prove
- what they cannot prove

This prevents silent inflation of weak evidence into false confidence.

## Summary

Fixtures and corpora are lenses, not substitutes for the product. Use small fixtures to test logic, representative corpora to exercise workflows, and real corpus runs to prove the behavioral claims that matter most to Resonance.

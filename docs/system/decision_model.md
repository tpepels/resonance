# Resonance Decision Model

## Purpose

This document defines how Resonance should think about decisions as product-level objects.

A decision is not merely a low-level implementation event. It is the authoritative answer to a meaningful question about how the system interprets or wants to organize a part of the user’s library.

## Why decisions matter

Resonance is fundamentally a decision-producing system.

Its output is not just transformed files or generated metadata. Its output is a set of judgments such as:

- what a directory likely represents
- whether a match is good enough to accept automatically
- whether ambiguity remains
- what organizational action should be proposed
- whether a human’s accepted choice can be treated as authority later

Thinking clearly about decisions keeps the product interpretable and replayable.

## Decision anatomy

Every important decision should be understandable in terms of five components.

### 1. Subject

What is being decided?

Examples:

- a specific directory
- a grouped set of tracks
- a candidate release interpretation
- a canonical grouping question

### 2. Evidence

What information supports the decision?

Examples:

- directory structure
- track names and counts
- embedded metadata
- provider candidates
- prior accepted authority

### 3. Interpretation space

What were the plausible meanings or options?

Examples:

- release A vs release B
- keep as-is vs normalize
- split directory vs leave grouped
- duplicate vs distinct edition

### 4. Outcome

What was decided?

Examples:

- choose candidate release X
- mark ambiguous
- prompt user for review
- accept automatic normalization

### 5. Authority source

Why is this decision authoritative?

Examples:

- automatic acceptance under strong evidence
- explicit human choice in REAL mode
- deterministic replay of a prior accepted human decision

## Decision classes

Resonance decisions can be grouped into several classes.

### Interpretive decisions

These concern what a directory or file grouping appears to represent.

### Organizational decisions

These concern what the system wants to do structururally, such as normalize, split, merge, or keep unchanged.

### Review escalation decisions

These concern whether a case requires human judgment.

### Replay decisions

These concern whether a prior authoritative choice can be reused safely.

## Decision outcomes must include ambiguity

A common design mistake is to treat ambiguity as a temporary defect rather than a valid outcome.

In Resonance, an unresolved or escalated case is a legitimate decision state. The system should be able to say:

- evidence is insufficient
- multiple candidates remain plausible
- human review is required
- no authoritative outcome should be invented yet

## Decision lifecycle

### Stage 1: Candidate formation

The system collects evidence and identifies plausible interpretations.

### Stage 2: Evaluation

The candidates are compared and ambiguity is assessed.

### Stage 3: Authority selection

The system determines whether authority comes from automation, human choice, or replay.

### Stage 4: Recording

The decision and enough supporting context are persisted.

### Stage 5: Review rendering

The decision is exposed through review artifacts so humans can inspect it.

### Stage 6: Replay validation

On rerun, prior decisions may be reused if the identity and prompt context still match.

## Product requirements for the decision model

The decision model should satisfy the following requirements.

### Explainability

A user should be able to see why a major decision happened.

### Stability

Equivalent situations should produce equivalent recorded decisions.

### Replayability

Accepted authority should be reusable under validated assumptions.

### Mismatch sensitivity

Changed decision contexts should be detectable.

### Human legibility

Decision records should map to concepts humans recognize.

## Decision anti-patterns

The model should avoid:

- decisions that only make sense in terms of internal code paths
- outcomes that hide ambiguity
- replay records too weak to prove scenario equivalence
- treating test fixture shortcuts as authoritative decision behavior

## Acceptance examples

Good acceptance criteria for decision-related work include:

- a reviewer can see why a directory was matched to a release
- ambiguous cases remain explicitly unresolved when evidence is insufficient
- accepted human decisions can be replayed deterministically under matching conditions
- changed prompt fingerprints cause replay rejection

## Summary

Resonance should be treated as a system that forms, records, explains, and safely reuses library-organization decisions. A strong decision model prevents the product from collapsing into opaque automation or test-only behavior.

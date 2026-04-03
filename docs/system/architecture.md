# Resonance Architecture

## Architectural purpose

This document maps the product behavior of Resonance onto a system architecture. The architecture exists to serve the user workflow:

- understand the library
- interpret what each directory represents
- propose actions
- review important decisions
- preserve accepted authority through deterministic replay

## Top-level architecture

Resonance can be understood as five cooperating layers.

### 1. Corpus ingestion and modeling

This layer inspects the filesystem-level input and constructs a structured internal model of the corpus.

Responsibilities include:

- enumerating directories and tracks
- extracting local metadata and structural signals
- building directory-level representations
- computing input identity or hashes needed for replay and validation

This layer answers:

> What is present in the corpus?

### 2. Interpretation and resolution

This layer infers what each directory likely represents and evaluates candidate matches against metadata providers or local evidence.

Responsibilities include:

- release candidate generation
- candidate comparison and ranking
- ambiguity detection
- confidence signaling
- identifying cases that can be decided automatically vs escalated

This layer answers:

> What does this directory most likely mean?

### 3. Decision orchestration

This layer determines what to do with each interpreted case.

Responsibilities include:

- deciding whether automatic action is appropriate
- prompting the user where judgment is required
- recording accepted choices
- producing canonical decision artifacts

This layer answers:

> What authority should the system establish for this case?

### 4. Review artifact generation

This layer converts authoritative outputs into a human-usable review surface.

Responsibilities include:

- generating review bundle data
- chunking outputs for navigability
- producing static review assets
- preserving enough evidence and structure for human audit

This layer answers:

> How can a human inspect and validate these outcomes?

### 5. Replay and validation

This layer preserves accepted authority across reruns.

Responsibilities include:

- storing replayable decisions with sufficient context
- validating corpus identity and prompt fingerprints
- reproducing decisions deterministically when valid
- failing hard when assumptions do not match

This layer answers:

> Can prior authority be reused safely here?

## Product-oriented architectural boundaries

The architecture should preserve the following boundaries.

### User-facing truth vs internal mechanics

User-facing concepts such as release identity, ambiguity, decision, and reviewability should remain visible and stable even if internal matching heuristics evolve.

### Authority creation vs authority replay

REAL mode creates authority. Replay mode reuses authority under validated conditions. These must not blur together.

### Review surface vs raw implementation artifacts

The review experience should be built intentionally, not treated as accidental exposure of internal data structures.

## Core system objects

The architecture should revolve around a small number of meaningful system objects.

### Corpus object

Represents the library or corpus under examination, along with identity information used for validation.

### Directory or release candidate object

Represents a grouped unit of files that may correspond to a release-level interpretation.

### Evidence object

Represents the local and provider-derived signals used to support interpretation.

### Decision object

Represents the authoritative outcome for a case, including accepted human choices where applicable.

### Review object

Represents the rendered inspection view of decisions and supporting evidence.

### Replay object

Represents the persisted context needed to deterministically reproduce prior accepted decisions.

## Recommended dependency direction

The architecture should flow from product truth downward:

1. product concepts and user jobs
2. stable decision and review models
3. orchestration logic
4. provider adapters and storage details
5. tests and fixtures

A repo often becomes brittle when this direction reverses and tests or adapters start defining the product.

## Architectural implications for repo structure

A healthy repo structure should reflect the conceptual architecture.

Suggested high-level documentation layout:

- `docs/product/` for human-facing product truth
- `docs/system/` for stable system contracts and architecture
- `docs/dev/` for contribution practices, fixtures, and testing strategy

Suggested code-level discipline:

- keep provider integration behind clear interfaces
- keep replay validation separate from fresh authority creation
- keep review generation separate from raw processing internals
- keep domain objects understandable in terms of product concepts

## Failure modes the architecture should prevent

The architecture should resist the following common failure modes:

### Test-defined product drift

When the easiest thing to optimize is test conformance rather than product usefulness.

### Fake real-mode behavior

When the “real” path is actually a special-case path that avoids the real system.

### Replay ambiguity

When replay silently reuses old choices in a changed context.

### Review collapse

When review requires reading giant raw artifacts or internal debug output rather than a designed inspection surface.

## Summary

The Resonance architecture should be judged by whether it supports a trustworthy user workflow for understanding and improving a real music library. Internal sophistication is only useful if it strengthens that workflow.

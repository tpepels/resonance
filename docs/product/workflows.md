# Resonance Workflows

## Overview

Resonance should present a small number of understandable primary workflows. The goal is not to expose every implementation knob. The goal is to support a clear human path through the product.

The primary story is:

1. run decision generation on a real corpus
2. review the results in a human-usable form
3. preserve accepted authority through deterministic replay

User-facing interface policy:

- `resonance app` is the singular human entrypoint for guided usage
- command-specific CLI invocations are optimized for automation, administrators, and power users
- both surfaces execute through one bounded API layer

## Workflow 1: Decide

### Goal

Produce the authoritative interpretation of a real corpus.

### User intent

The user wants Resonance to inspect a library, consult evidence, resolve likely release identities, escalate ambiguous cases, and produce a decision record.

### Conceptual stages

1. **Scan**
   Build a model of what directories, tracks, and supporting artifacts exist.

2. **Interpret**
   Determine what each directory likely represents.

3. **Resolve**
   Consult providers and local evidence to identify likely release candidates.

4. **Prompt where necessary**
   Ask the user to decide unresolved cases that require human judgment.

5. **Record**
   Persist the resulting decision artifacts, expected state, and replay information.

### Primary interface

```bash
resonance app <library_root> --state-db <path>
```

Automation/admin primary interface:

```bash
resonance decide <library_root> --state-db <path> --mode automation --headless
```

### Success criteria

A successful decide run should produce:

- authoritative outputs for the corpus
- recorded decisions for prompted cases
- replay data for accepted authority
- evidence that the real workflow actually executed

## Workflow 2: Review

### Goal

Turn authoritative outputs into a human-usable inspection surface.

### User intent

The user wants to review what Resonance concluded, especially where canonicalness, duplication, or ambiguity are involved.

### Review expectations

A review surface should make it practical to inspect:

- what the system thinks each directory is
- why it thinks that
- which cases were straightforward
- which cases are ambiguous
- what actions are proposed or already accepted

### Design constraints

The review experience must remain usable at corpus scale. Chunked static outputs are preferable to oversized monoliths that are difficult for humans or agents to navigate.

### Primary interface

```bash
make corpus-review
```

## Workflow 3: Replay

### Goal

Reproduce previously accepted authority deterministically.

### User intent

The user wants accepted decisions to remain stable across reruns, without manually re-answering the same questions.

### Replay expectations

Replay should:

- validate input identity and relevant context
- use recorded decisions when the scenario matches
- fail hard if assumptions do not match

Replay should not silently reinterpret a past decision under a new situation.

## Workflow relationships

The workflows form a chain of authority.

### Decide establishes authority

REAL decide mode is where authoritative decisions are created.

### Review validates trust

Review makes those decisions understandable and auditable.

### Replay preserves authority

Replay keeps the accepted decisions stable over time when their assumptions still hold.

## Example human story

A user has a library with hundreds or thousands of directories. Some are clean. Some are badly named. Some may be duplicate editions or partial albums.

They run `make corpus-decide`. Resonance scans the corpus, interprets folders, consults providers, and prompts for cases where human judgment matters.

They then run `make corpus-review`. The generated review surface lets them inspect suspicious cases, canonicalness decisions, and ambiguous matches.

Later, they rerun the corpus workflow. Previously accepted decisions replay automatically when the context still matches. If one decision no longer matches the same prompt or corpus identity, the run fails loudly instead of quietly drifting.

## Workflow anti-patterns

The following patterns should be avoided:

- primary workflows hidden behind too many flags
- fake “real” paths that do not exercise actual system behavior
- review that depends on raw internal artifact reading
- replay that silently degrades into fresh speculative interpretation
- acceptance criteria based only on implementation presence rather than observed behavior

## Acceptance-oriented workflow criteria

Useful workflow acceptance criteria are behavioral and user-facing. Examples:

- a user can run the real authoritative workflow through a simple top-level command
- the review output makes ambiguous cases easy to inspect without opening raw JSON
- previously accepted decisions replay automatically when unchanged
- replay mismatches cause hard failure rather than fallback

These criteria keep the repo attached to product reality.

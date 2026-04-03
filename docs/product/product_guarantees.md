# Resonance Product Guarantees

## Purpose of this document

This document defines the guarantees Resonance should provide to users. These are product-level commitments, not low-level implementation details. They should shape both architecture and acceptance criteria.

## Guarantee 1: No silent invention of authority

Resonance must not silently pretend to know more than the evidence supports.

This means:

- uncertain cases should be marked as uncertain
- speculative matches should not be presented as settled fact
- replayed decisions should not be reinterpreted under changed conditions without explicit failure

A clean-looking output produced through hidden guesswork is a product failure.

## Guarantee 2: Important decisions are inspectable

For important outcomes, the user should be able to inspect:

- the relevant evidence
- the system’s inferred interpretation
- the proposed action
- the source of ambiguity or confidence
- the final accepted or unresolved status

Users should not need to trust a black box.

## Guarantee 3: Ambiguity is a first-class outcome

Resonance must treat ambiguity as a normal and meaningful result.

This means:

- ambiguous directories can remain unresolved
- review can focus on unresolved cases
- the system can distinguish incomplete authority from final judgment

A system that always produces an answer is not necessarily a trustworthy system.

## Guarantee 4: Replay is deterministic when assumptions still match

When a user has previously accepted a decision, Resonance should be able to replay that decision deterministically as long as the relevant input and prompt context still match.

This means replay data should capture enough identity and context to establish that the replay is truly about the same decision situation.

## Guarantee 5: Replay fails loudly on mismatch

When replay assumptions do not match, Resonance must fail hard rather than silently falling back to speculative behavior.

Examples include:

- different corpus input identity
- different prompt fingerprint
- missing or incompatible replay context
- structurally incompatible decision scenario

Hard failure preserves trust. Silent drift erodes it.

## Guarantee 6: Review remains usable at realistic corpus size

The review surface should remain navigable on real-world corpora.

This means the system should avoid forcing humans or agents to ingest oversized monolithic artifacts when chunked, inspectable outputs are more usable.

## Guarantee 7: Primary workflows remain simple

The main user-visible workflows should be easy to understand and difficult to misuse.

At a product level, Resonance should expose a minimal, comprehensible workflow surface such as:

```bash
make corpus-decide
make corpus-review
```

Advanced or internal modes may exist, but they should not replace the primary user story.

## Guarantee 8: Real authoritative mode is actually real

REAL mode must exercise real product behavior, not a fake path that merely resembles it.

This includes, where appropriate:

- real orchestration
- real provider calls
- real prompting and choice capture
- real decision artifacts

If REAL mode is just a theatrical set built for tests, then the product guarantee is broken.

## Guarantee 9: Acceptance is behavioral, not rhetorical

Resonance should only treat a workflow or mechanism as accepted when the behavior has been observed, not merely implemented in code.

This means acceptance often requires evidence of:

- successful real-path execution
- observed replay success under matching assumptions
- observed replay failure under mismatched assumptions

A claim that a feature exists is weaker than a demonstrated run proving it behaves correctly.

## Guarantee 10: Tests serve the product, not the reverse

The test suite exists to protect product behavior. It must not become the de facto specification when that specification is narrower than real user value.

This means:

- tests should defend meaningful guarantees
- implementation should not optimize for synthetic green states detached from user jobs
- repo structure should keep product truth visible above test mechanics

## Summary

These guarantees define the trust contract of Resonance. They are the rails that keep the project from collapsing into a test-targeting maze. Every substantial change should be explainable in terms of whether it preserves, strengthens, or weakens these guarantees.

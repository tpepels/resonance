# Resonance Replay Model

## Purpose

This document defines the role of replay in Resonance.

Replay exists to preserve previously accepted authority. It is not a shortcut for avoiding real decision generation, and it is not a permissive cache that silently tolerates changed conditions.

## Replay in product terms

A user who has already answered an important question should not need to answer it again if the same question is presented under the same conditions.

Replay is therefore the mechanism that says:

> This is the same decision scenario as before, so the accepted answer can be reused safely.

If the scenario is not the same, replay must refuse.

## Distinction between REAL mode and replay mode

### REAL mode

REAL mode creates authority. It may consult providers, evaluate fresh evidence, and ask the user to choose among options.

### Replay mode

Replay mode reuses authority. It should only operate when it can prove that the previously recorded decision still applies.

This distinction is fundamental. If replay starts creating authority, the trust model breaks.

## What replay data must capture

Replay must capture enough context to distinguish “same decision again” from “different decision that merely looks similar.”

The recorded data should include, conceptually:

- corpus or input identity
- subject identity for the decision case
- prompt or option fingerprint
- selected outcome
- enough metadata to validate that the replay scenario matches the original

The exact storage format may vary, but the trust contract should not.

## Replay validation requirements

Before reusing a prior decision, Resonance should validate at least the following classes of assumptions.

### Input identity

The relevant corpus or decision subject still corresponds to the original scenario.

### Prompt equivalence

The choice structure presented to the user has not changed in a way that would alter the meaning of the recorded answer.

### Structural compatibility

The decision type and surrounding interpretation context are still compatible with the stored outcome.

## Failure policy

Replay mismatch must fail hard.

The system should not silently do any of the following:

- reinterpret the old choice under a new prompt
- fall back to an implicit fresh decision without notice
- quietly accept a partial match as sufficient

Hard failure is not a nuisance. It is the mechanism that protects user trust.

## Replay success behavior

When the validation checks pass, replay should:

- reproduce the accepted decision deterministically
- avoid unnecessary human re-prompting
- make it clear that the authority comes from recorded prior acceptance

## Why replay must be behaviorally proven

Replay is a trust mechanism, so its value depends on observed behavior.

It is not enough to implement validation code. The system should demonstrate:

- successful replay under matching conditions
- explicit failure under mismatched conditions

Without both observations, replay remains a paper shield.

## Relationship to testing and acceptance

Tests can defend replay semantics, but they are not sufficient by themselves.

The strongest acceptance path includes a real run that:

1. records multiple actual decisions in REAL mode
2. reruns successfully under matching assumptions
3. fails when one recorded decision is intentionally altered

That is behavioral proof of the replay contract.

## Anti-patterns

The replay model should avoid:

- replay files created without real decision generation
- hand-authored decisions masquerading as equivalent to real user choices
- fallback behavior that hides mismatch
- replay records that omit the prompt structure needed for validation

## Summary

Replay in Resonance is the disciplined reuse of previously accepted authority. It only deserves user trust when it validates scenario equivalence, replays deterministically when appropriate, and fails loudly when equivalence breaks.

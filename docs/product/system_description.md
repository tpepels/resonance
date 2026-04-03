# Resonance System Description

## Purpose

Resonance exists to help a person inspect, understand, normalize, and improve a music library without losing trust in what is happening to their files.

A music library often contains a mix of clean releases, partial albums, unknown editions, duplicate folders, inconsistent naming, damaged metadata, and ambiguous release identities. Humans generally do not want to reason about these problems as raw file trees or metadata records. They want to reason about artists, releases, editions, duplicates, gaps, and organizational choices.

Resonance exists to bridge that gap.

## Product definition

Resonance is a music library organization system for real libraries. It scans a corpus of audio-related filesystem content, builds an interpretable model of what is present, consults metadata providers when useful, proposes organizational decisions, records those decisions, and presents a review surface where a human can validate or reject important judgments before file-level outcomes are treated as authoritative.

The system is valuable not merely because it automates work, but because it produces **trusted automation**. A user should be able to see:

- what Resonance believes is in the library
- why it believes that
- what it proposes to do
- where confidence is high
- where ambiguity remains
- which decisions were accepted by a human
- whether those decisions still replay safely later

## The problem from the human point of view

Users organizing music libraries typically want help with five practical questions.

### 1. What do I actually have?

A user wants an understandable inventory of their library as human-meaningful releases and folders, not just a recursive file listing.

### 2. What does each directory appear to represent?

A folder may correspond to an album, a specific edition, a compilation, a bootleg, a disc split, a duplicate, or an incoherent mix of files. The system should infer the most likely interpretation.

### 3. What is wrong, incomplete, duplicated, inconsistent, or ambiguous?

The value of the system is partly diagnostic. It should surface uncertainty and structural problems rather than hiding them behind a false appearance of confidence.

### 4. What would a cleaner, more canonical organization look like?

The user wants help moving the library toward a more consistent structure, naming scheme, and release model.

### 5. Which actions can be trusted automatically, and which require my judgment?

The system should automate where evidence is strong and escalate where human judgment is still needed.

## Core responsibilities of the product

Resonance has five user-facing responsibilities.

### Discovery

The system must identify and summarize what is present in the corpus in a way that matches human mental models. That includes entities such as artists, releases, editions, duplicates, unknowns, and suspicious groupings.

### Interpretation

The system must infer what a directory or group of files likely represents. This includes identifying probable release matches, format or edition clues, structural issues, and ambiguity.

### Proposal

The system must decide what it wants to do next. Typical outcomes include:

- keep as-is
- relabel or enrich metadata
- rename or normalize paths
- split a mixed directory
- merge duplicate representations
- mark a folder as ambiguous or suspicious
- request human review

### Review

The system must provide a human-usable surface for inspecting the results. A user should not need to inspect raw JSON or internal logs to understand important decisions.

### Reproducibility

If a human accepts a decision, the system must be able to replay that decision deterministically later, or fail clearly if the assumptions have changed.

## The two operational layers

Resonance operates in two distinct but connected layers.

### Layer 1: Authoritative decision generation

This is the real processing workflow over a corpus. It scans inputs, resolves candidate interpretations, consults providers when needed, prompts the user where necessary, and records resulting decisions.

This layer answers the question:

> What does the system believe should happen to this library?

### Layer 2: Human review

This is the inspection surface built from the authoritative outputs. It allows a person to evaluate top-level canonicalness, inspect ambiguity, and verify whether Resonance's proposals are trustworthy.

This layer answers the question:

> Why does the system believe that, and should I trust it?

## Product values

Resonance should embody the following values.

### Trust over opacity

It is better for the system to surface uncertainty than to perform silent speculative transformations.

### Human-meaningful structure over raw filesystem mechanics

The system should describe the library in terms people care about: releases, editions, duplicates, ambiguity, and proposed actions.

### Determinism where authority exists

Accepted decisions should replay deterministically when the same situation is encountered again.

### Hard failure over silent drift

When replay assumptions no longer hold, the system should fail loudly rather than quietly reinterpret old decisions.

### Reviewability at realistic scale

Large corpora should still produce outputs that remain navigable by a human reviewer.

## Modes of operation

Resonance distinguishes between two modes that serve different purposes.

### REAL mode

REAL mode is authoritative. It may consult external providers and may require human interaction for unresolved cases. Its outputs establish the decision record that represents what the system actually concluded for a real corpus.

### Replay mode

Replay mode is deterministic. It uses previously recorded decisions to reproduce accepted outcomes under validated assumptions. It is not a substitute for REAL mode. It is a faithful replay of prior authority, subject to mismatch detection.

## Product guarantees

At a product level, Resonance should guarantee the following:

- no silent invention of authority
- inspectable decision reasoning and evidence
- explicit treatment of ambiguity
- deterministic replay of accepted decisions when assumptions still match
- hard failure on replay mismatch
- a review surface that remains usable on real libraries

## Non-goals

Resonance is not attempting to be:

- a generic music player or library browser
- a full metadata encyclopedia independent of user collections
- a hidden background mutator that edits files without understandable rationale
- a repo where passing tests is treated as equivalent to delivering user value

## Summary

Resonance should be understood first as a product for humans organizing real music libraries. Internal pipelines, provider adapters, replay files, and test fixtures exist to support that purpose. The repo should therefore be shaped around human outcomes: understanding a library, trusting proposed changes, reviewing ambiguity, and preserving accepted decisions safely over time.

# Resonance User Jobs

## Why user jobs matter

Resonance should be designed around what a person is trying to get done with a music library. The system should not begin from internal implementation concepts such as providers, replay files, or pipeline stages. Those concepts matter, but they only matter insofar as they help the user complete a meaningful job.

This document defines the core user jobs Resonance must support.

## Primary user profile

The primary user is a person with a real music collection who wants to organize it more cleanly and more canonically without surrendering control.

That user may have:

- inconsistent filenames and folder names
- incomplete or damaged tags
- duplicate releases or accidental copies
- uncertainty about editions, remasters, or release identity
- a need to understand what the library contains before making changes

## Core user jobs

### Job 1: Understand what is in my library

The user wants an inventory that answers:

- what artists and releases appear to exist
- which directories look coherent
- which ones are suspicious or incomplete
- where duplicates may exist
- where the library structure appears broken or mixed

**Success condition:** the user can look at Resonance output and form a grounded mental model of the collection.

### Job 2: Understand what each folder probably represents

The user wants help interpreting a directory as a likely release or edition, rather than guessing from filenames alone.

**Success condition:** each directory can be viewed as a likely release-level object with evidence and caveats.

### Job 3: Identify what needs attention

The user wants Resonance to surface the pain points that matter:

- ambiguous matches
- conflicting metadata
- structural anomalies
- duplicates
- likely mis-groupings
- incomplete releases
- suspicious naming or track layouts

**Success condition:** the user can quickly identify where human review is necessary.

### Job 4: See what a cleaner organization would be

The user wants proposed organizational improvements, such as normalized names, cleaner grouping, more canonical release identity, or duplicate consolidation.

**Success condition:** the system proposes understandable actions that move the library toward a more coherent state.

### Job 5: Decide when the system should act and when I should decide

The user wants automation, but not blind automation. Resonance must distinguish between:

- decisions that are safe enough to accept automatically
- decisions that require review
- decisions that should remain unresolved rather than guessed

**Success condition:** the user trusts that Resonance escalates the right cases.

### Job 6: Review important decisions without reading internals

The user needs a review surface that makes canonicalness, ambiguity, duplicates, and proposed actions visible without requiring direct inspection of internal artifacts.

**Success condition:** a person can review outcomes using the review UI or structured outputs alone.

### Job 7: Preserve accepted decisions over time

Once the user has made a judgment, they want that judgment to remain stable when the same case is encountered again.

**Success condition:** accepted decisions can replay deterministically, and mismatches are clearly flagged.

## Secondary jobs

### Audit a corpus run

The user or maintainer may want to understand what happened in a specific run, including the evidence behind major decisions and the set of unresolved cases.

### Prepare a library for future cleanup

A user may not be ready to apply changes immediately, but still wants a trustworthy map of the problem space.

### Compare confidence zones

A user may want to distinguish high-confidence, low-risk areas of the library from ambiguous zones that need more attention.

## Anti-jobs

Resonance should not optimize primarily for these outcomes:

- maximizing test artifact production independent of user value
- hiding ambiguity to produce a cleaner-looking output
- producing internal JSON that only developers can interpret
- encouraging silent bulk mutation without reviewable reasoning

## Design implications

Because these are the core jobs, Resonance development should prefer work that improves the following user-visible capabilities:

- clearer library interpretation
- better explanation of why a match was chosen
- stronger representation of ambiguity
- better review surfaces
- safer replay of accepted decisions
- simpler primary workflows for running and reviewing the system

## Acceptance lens

A change is valuable when it makes at least one user job easier, safer, or more trustworthy to complete.

A change is suspect when it only makes the codebase or tests more elaborate without improving a user job.

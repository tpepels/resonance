# Resonance

Resonance is a music library organization system for people who want to understand, normalize, and improve a real collection of audio files.

It is not primarily a metadata scraper, a tag mutator, or a synthetic test harness. Those are supporting mechanisms. The product itself helps a human answer a practical sequence of questions about a library they already own:

- What is actually in this collection?
- What does each directory appear to represent?
- Which parts are complete, incomplete, duplicated, inconsistent, or ambiguous?
- What would a cleaner, more canonical organization look like?
- Which proposed changes are safe to trust automatically, and which require human judgment?

Resonance treats a library as a set of human-meaningful releases, editions, and organizational decisions. It should help a person move from a messy or uncertain library toward a more understandable and trustworthy one.

## Primary workflows

Resonance has two primary workflows.

### 1. Decide

The authoritative workflow scans a real corpus, interprets what is present, consults external providers when needed, proposes actions, prompts where human judgment is required, and records decisions.

This is the workflow behind a command such as:

```bash
make corpus-decide
```

### 2. Review

The review workflow turns the results of decision generation into a human-usable inspection surface. A user should be able to see what Resonance thinks is present, why it believes that, what it wants to do, and where ambiguity remains.

This is the workflow behind a command such as:

```bash
make corpus-review
```

## Product principles

Resonance should be developed and evaluated according to the following principles:

1. **Human intent first**
   The repo should describe what Resonance does for people organizing music libraries before it describes internal components.

2. **Decision process, not black box transformation**
   Important outcomes must be inspectable as evidence, interpretation, proposed action, confidence or ambiguity, and final decision.

3. **Trusted automation**
   The product must avoid silent invention of authority. It should only claim certainty where evidence supports it, and it must expose unresolved ambiguity clearly.

4. **Deterministic replay**
   Previously accepted decisions should replay deterministically when the conditions still match. If assumptions no longer hold, replay must fail loudly.

5. **Real workflow equivalence**
   The authoritative corpus workflow should exercise real system behavior, not a parallel fake path optimized for tests.

## Documentation map

### Product

- [System description](docs/product/system_description.md)
- [User jobs](docs/product/user_jobs.md)
- [Product guarantees](docs/product/product_guarantees.md)
- [Workflows](docs/product/workflows.md)

### System

- [Architecture](docs/system/architecture.md)
- [Decision model](docs/system/decision_model.md)
- [Replay model](docs/system/replay_model.md)
- [Provider integration](docs/system/provider_integration.md)

### Development

- [Contributing](docs/dev/contributing.md)
- [Testing strategy](docs/dev/testing_strategy.md)
- [Fixtures and corpus](docs/dev/fixtures_and_corpus.md)

## What Resonance is not

Resonance is not trying to be all of the following:

- a generic media server
- a universal tag editor for arbitrary hand-editing
- a hidden batch renamer with unexplained behavior
- a test-first abstraction game where green checks substitute for user value

It is a system for making a music library more understandable, more canonical, and more trustworthy.

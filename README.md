```
██████╗ ███████╗███████╗ ██████╗ ███╗   ██╗ █████╗ ███╗   ██╗ ██████╗███████╗
██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗████╗  ██║██╔════╝██╔════╝
██████╔╝█████╗  ███████╗██║   ██║██╔██╗ ██║███████║██╔██╗ ██║██║     █████╗
██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╗██║██╔══██║██║╚██╗██║██║     ██╔══╝
██║  ██║███████╗███████║╚██████╔╝██║ ╚████║██║  ██║██║ ╚████║╚██████╗███████╗
╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
```

# Resonance

Resonance is a music library organization system for people who want to understand, normalize, and improve a real collection of audio files.

It does not treat your library as a bag of filenames. It treats it as a set of human-meaningful releases, editions, and organizational decisions.

The goal is simple: help you move from a messy or uncertain library to one that is understandable, canonical, and trustworthy.

---

## What it does (for humans)

Resonance helps you answer five practical questions:

* What is actually in my library?
* What does each directory appear to represent?
* What is incomplete, duplicated, inconsistent, or ambiguous?
* What would a cleaner, more canonical organization look like?
* Which changes can I trust automatically, and which need my judgment?

It is not just automation. It is **trusted automation**.

Every important outcome should be explainable as:

* evidence (what was found)
* interpretation (what it likely is)
* proposal (what should change)
* confidence or ambiguity
* final decision (recorded and replayable)

---

## Core workflows

Resonance has two primary workflows.

### 1. Decide (authoritative)

Scans a real corpus, interprets it, consults providers, prompts when needed, and records decisions.

```bash
make corpus-decide
```

### 2. Review (human validation)

Presents results in a structured UI so you can inspect what Resonance believes and why.

```bash
make corpus-review
# opens http://localhost:8080/real_corpus_review.html
```

These two together form the product loop:

```
scan → interpret → propose → review → accept → replay
```

---

## What it does (system view)

Resonance organizes your music library using a deterministic, auditable pipeline:

1. **Scan**
   Identify audio files and compute content signatures

2. **Identify**
   Resolve releases using fingerprints and provider APIs (AcoustID, MusicBrainz, Discogs)

3. **Resolve**
   Handle uncertainty via scoring or human prompts

4. **Plan**
   Define file moves and tag updates with full traceability

5. **Apply**
   Execute changes transactionally with rollback support

---

## Key features

* **Deterministic pipeline**
  Same inputs → same outputs

* **Fingerprint-based identification**
  Content identity via AcoustID + MusicBrainz

* **Canonical name resolution**
  Normalize artist/composer variants

* **Plan-based execution**
  Review before applying changes

* **Transaction support**
  Rollback on failure

* **Decision recording + replay**
  Real decisions can be reproduced or validated

* **Human review surface**
  Inspect canonicalness, ambiguity, duplicates

---

## Product principles

Resonance is developed under these constraints:

1. **Human intent first**
   The system exists to help people organize libraries, not to satisfy internal abstractions.

2. **Decision process, not black box**
   Outcomes must be inspectable and explainable.

3. **Trusted automation**
   No silent invention of authority.

4. **Deterministic replay**
   Accepted decisions must replay exactly or fail loudly.

5. **Real workflow equivalence**
   The corpus workflow must use real system behavior, not test-only paths.

---

## Installation

```bash
cd resonance
pip install -e .
```

---

## Configuration

Resonance uses a hybrid configuration system:

* **Environment variables** → secrets and environment-specific settings
* **JSON config file** → application behavior

### Quick setup

```bash
cp .env.example .env
cp settings.json.example ~/.config/resonance/settings.json
```

### Environment variables (.env)

```bash
ACOUSTID_API_KEY=your_key
MUSICBRAINZ_USER_AGENT=Resonance/1.0.0 (you@example.com)

DISCOGS_CONSUMER_KEY=...
DISCOGS_CONSUMER_SECRET=...

RESONANCE_OFFLINE_MODE=false
RESONANCE_DEBUG=false
```

### JSON config

```json
{
  "tag_writer_backend": "meta-json",
  "identify_scoring_version": "v1",
  "plan_conflict_policy": "FAIL"
}
```

### Priority

1. CLI args
2. Environment
3. Config file
4. Defaults

---

## V3 pipeline (low-level workflow)

For direct control:

```bash
resonance scan /path --state-db state.db
resonance resolve /path --state-db state.db
resonance prompt --state-db state.db
resonance plan --dir-id <id> --state-db state.db
resonance apply --plan plan.json --state-db state.db
```

### State machine

```
NEW → RESOLVED_AUTO | QUEUED_PROMPT
QUEUED_PROMPT → RESOLVED_USER | JAILED
RESOLVED → PLANNED → APPLIED
```

### Invariants

* No-rematch after resolution
* Idempotent reruns
* Deterministic outputs

---

## Architecture (mental model)

Resonance has two layers:

### 1. Decision generation (authoritative)

* real corpus processing
* real providers
* real prompts
* produces decision artifacts

### 2. Human review (inspection)

* static, chunked UI
* no multi-MB ingestion
* focused on validation of meaning

---

## Documentation

### Product

* docs/product/system_description.md
* docs/product/user_jobs.md
* docs/product/product_guarantees.md
* docs/product/workflows.md

### System

* docs/system/architecture.md
* docs/system/decision_model.md
* docs/system/replay_model.md
* docs/system/provider_integration.md

### Development

* docs/dev/contributing.md
* docs/dev/testing_strategy.md
* docs/dev/fixtures_and_corpus.md

---

## What Resonance is not

* not a generic media server
* not a blind batch renamer
* not a manual tag editor UI
* not a test-driven abstraction playground

It is a system for making a music library **more understandable, more canonical, and more trustworthy**.

---

## License

MIT

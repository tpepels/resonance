# Mental Model

## What Resonance does

Resonance takes a messy music library and organizes it deterministically using audio fingerprinting. It identifies what each album *is* (via AcoustID, MusicBrainz, Discogs), then generates a reproducible plan to rename and tag the files.

## Pipeline stages

```
  scan → resolve → prompt → plan → apply
```

Each stage reads from and writes to a **state DB** (SQLite). Stages are idempotent — re-running a stage with the same inputs produces the same result.

### 1. Scan

Walks the library root, discovers directories containing audio files, computes a content fingerprint (signature hash), and records each directory in the state DB with state `NEW`.

### 2. Resolve

For each `NEW` directory, queries providers (AcoustID for fingerprints, MusicBrainz/Discogs for metadata). Scores candidates using a deterministic algorithm. High-confidence matches → `RESOLVED_AUTO`. Ambiguous matches → `QUEUED_PROMPT`.

### 3. Prompt

Presents ambiguous directories to the user for manual selection. The user picks which release matches, or jails the directory. Result: `RESOLVED_USER` or `JAILED`.

### 4. Plan

For each resolved directory, generates a deterministic **Plan artifact** — a JSON file specifying exactly which files to move and where. Plans are pure (no I/O) and byte-identical for identical inputs.

### 5. Apply

Executes a Plan — moves files, writes tags. Default mode is dry-run (no changes). With `--no-dry-run`, files are actually moved. Includes transactional rollback on failure.

## Directory lifecycle

```
NEW → RESOLVED_AUTO → PLANNED → APPLIED
NEW → QUEUED_PROMPT → RESOLVED_USER → PLANNED → APPLIED
NEW → QUEUED_PROMPT → JAILED
*   → FAILED
```

## Key concepts

| Concept | Description |
|---------|-------------|
| **dir_id** | Stable identifier for a directory (derived from path) |
| **signature_hash** | SHA-256 of audio file contents — detects content changes |
| **pinned release** | The provider release a directory is matched to |
| **confidence tier** | CERTAIN (auto-pin), PROBABLE (suggest), UNSURE (manual) |
| **Plan** | Frozen artifact: list of file moves + destination paths |
| **TagPatch** | Frozen artifact: metadata tags to write to audio files |

## Providers

| Provider | Capability | Used for |
|----------|-----------|----------|
| AcoustID | Fingerprint search | Content-based identification |
| MusicBrainz | Metadata search, release lookup | Album/track metadata |
| Discogs | Metadata search | Corroboration, alternative metadata |

Providers are wrapped with a **cache-first** layer. Second runs hit cache, zero HTTP. Offline mode uses cache only.

## Safety model

- **Dry-run default**: `apply` is dry-run unless `--no-dry-run` is explicit
- **Rollback**: Failed applies attempt automatic rollback of moved files
- **Conflict policies**: FAIL (default), SKIP, RENAME for destination collisions
- **Path validation**: All paths are validated against allowed roots to prevent traversal

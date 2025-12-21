```
██████╗ ███████╗███████╗ ██████╗ ███╗   ██╗ █████╗ ███╗   ██╗ ██████╗███████╗
██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗████╗  ██║██╔════╝██╔════╝
██████╔╝█████╗  ███████╗██║   ██║██╔██╗ ██║███████║██╔██╗ ██║██║     █████╗
██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╗██║██╔══██║██║╚██╗██║██║     ██╔══╝
██║  ██║███████╗███████║╚██████╔╝██║ ╚████║██║  ██║██║ ╚████║╚██████╗███████╗
╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
```

Clean, focused audio metadata organizer using fingerprinting and canonical artist detection.

## What It Does

Resonance organizes your music library using a deterministic, auditable pipeline:
1. **Scan** directories to identify audio files and compute content signatures
2. **Identify** releases using fingerprints and provider APIs (MusicBrainz, Discogs)
3. **Resolve** uncertain matches with user input or automatic scoring
4. **Plan** file moves and tag updates with full auditability
5. **Apply** plans transactionally with rollback support

## Key Features

- **Deterministic Pipeline**: Content-based identity, no re-matches on repeat runs
- **Fingerprint-Based Identification**: Uses AcoustID + MusicBrainz
- **Canonical Name Resolution**: Merges artist variants (e.g., "Bach, J.S." → "Johann Sebastian Bach")
- **Transaction Support**: Rollback on errors or crashes
- **Classical Music Support**: Special handling for composer/performer structures
- **Plan-Based Execution**: Review changes before applying

## Installation

```bash
cd resonance
pip install -e .
```

## Usage

### V3 Pipeline (Complete Workflow)

The V3 pipeline uses a deterministic state machine with explicit state transitions:

```bash
# 1. Scan library to discover audio directories
resonance scan /path/to/library --state-db ~/.local/share/resonance/state.db

# 2. Resolve directories using provider metadata (MusicBrainz, Discogs)
resonance resolve /path/to/library --state-db ~/.local/share/resonance/state.db

# 3. Answer prompts for uncertain matches
resonance prompt --state-db ~/.local/share/resonance/state.db

# 4. Create a plan for a resolved directory
resonance plan --dir-id <dir-id> --state-db ~/.local/share/resonance/state.db

# 5. Apply the plan
resonance apply --plan plan.json --state-db ~/.local/share/resonance/state.db
```

### State Transitions

Directories flow through the following states:

```
NEW → (resolve) → RESOLVED_AUTO or QUEUED_PROMPT
QUEUED_PROMPT → (prompt) → RESOLVED_USER or JAILED
RESOLVED_AUTO/RESOLVED_USER → (plan) → PLANNED
PLANNED → (apply) → APPLIED
```

**Key Invariants:**

- **No-rematch**: Once resolved, directories are never re-queried to providers
- **Idempotent**: Rerunning scan/resolve on unchanged directories is a no-op
- **Deterministic**: Same inputs always produce same outputs

### JSON Output Mode

All workflow commands support `--json` for machine-readable output:

```bash
# Scan with JSON output
resonance scan /path/to/library --state-db state.db --json

# Resolve with JSON output
resonance resolve /path/to/library --state-db state.db --json
```

### Diagnostic Commands

```bash
# Show help
resonance --help

# Identify a single directory (diagnostic, doesn't modify state)
resonance identify /path/to/album

# Build canonical artist/composer mappings
resonance prescan /path/to/library --cache ~/.cache/resonance/metadata.db
```

## Architecture

Resonance uses a **V3 deterministic pipeline**:

```
scan → resolve → prompt → plan → apply
```

Each phase is:

- **Pure**: No side effects in scan, resolve (read-only), and plan stages
- **Auditable**: Full trace of decisions and changes
- **Deterministic**: Same inputs always produce same outputs
- **Transactional**: Apply operations can be rolled back

See [Resonance_DESIGN_SPEC.md](Resonance_DESIGN_SPEC.md) for full architecture details.

## State Management

Resonance maintains state in two locations:
- **DirectoryStateStore** (`~/.local/share/resonance/state.db`): Directory resolution state, plans
- **MetadataCache** (`~/.cache/resonance/metadata.db`): Provider API responses, canonical name mappings

## Migrating from audio-meta

Resonance is a clean rewrite of the audio-meta project. Your cache will work automatically - just point Resonance at your library.

## License

MIT

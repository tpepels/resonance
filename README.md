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

### V3 Pipeline (Recommended)

The V3 pipeline uses a deterministic state machine with explicit plan artifacts:

```bash
# 1. Identify a directory
resonance identify /path/to/album --json > identification.json

# 2. Create a plan (requires directory in state DB)
resonance plan --dir-id <dir-id> --state-db ~/.local/share/resonance/state.db

# 3. Apply the plan
resonance apply --plan plan.json --state-db ~/.local/share/resonance/state.db
```

### Prescan (Build Canonical Mappings)

```bash
# Scan library to build canonical artist/composer mappings
resonance prescan /path/to/library --cache ~/.cache/resonance/metadata.db
```

### Commands

```bash
# Show help
resonance --help

# Identify a directory
resonance identify /path/to/album

# Create a plan
resonance plan --dir-id <dir-id> --state-db state.db

# Apply a plan
resonance apply --plan plan.json --state-db state.db
```

## Architecture

Resonance uses a **V3 deterministic pipeline**:

```
scan → identify → resolve → plan → apply
```

Each phase is:
- **Pure**: No side effects in scan, identify, and plan stages
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

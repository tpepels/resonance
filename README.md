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

## Configuration

Resonance uses a **hybrid configuration system**:

- **Environment Variables**: For API keys and environment-specific settings
- **JSON Config Files**: For application settings that can be version controlled

### Quick Setup

1. **Copy example files:**
```bash
cp .env.example .env
cp settings.json.example ~/.config/resonance/settings.json
```

2. **Edit with your values:**
```bash
# Edit .env with your API keys
nano .env

# Edit settings.json with your preferences
nano ~/.config/resonance/settings.json
```

3. **Optional: Auto-load .env files**
```bash
pip install python-dotenv
```
**Note:** The CLI automatically loads `.env` files from the current directory. No additional setup required!

### Environment Variables (.env)

Used for **secrets and environment-specific settings**:

```bash
# ===========================================
# API KEYS (Required for full functionality)
# ===========================================

# AcoustID - Get from https://acoustid.org/api-key
ACOUSTID_API_KEY=your_acoustid_api_key_here

# MusicBrainz - Required user agent
MUSICBRAINZ_USER_AGENT=Resonance/1.0.0 (your-email@example.com)

# Discogs - Optional, get from https://www.discogs.com/developers
DISCOGS_CONSUMER_KEY=your_discogs_consumer_key
DISCOGS_CONSUMER_SECRET=your_discogs_consumer_secret

# ===========================================
# ENVIRONMENT SETTINGS
# ===========================================

# Enable offline mode (cache-only, no network calls)
RESONANCE_OFFLINE_MODE=false

# Enable debug logging
RESONANCE_DEBUG=false
```

### JSON Config File (settings.json)

Used for **application settings** (stored in `~/.config/resonance/settings.json`):

```json
{
  "tag_writer_backend": "meta-json",
  "identify_scoring_version": "v1",
  "plan_conflict_policy": "FAIL"
}
```

### Configuration Priority

Settings are resolved in this priority order:

1. **CLI Arguments** (highest priority)
2. **Environment Variables**
3. **JSON Config File**
4. **Defaults** (lowest priority)

### Complete Example

**Environment Variables (.env):**
```bash
ACOUSTID_API_KEY=abcd1234
MUSICBRAINZ_USER_AGENT=Resonance/1.0.0 (user@example.com)
RESONANCE_OFFLINE_MODE=false
```

**Application Settings (~/.config/resonance/settings.json):**
```json
{
  "tag_writer_backend": "mutagen",
  "identify_scoring_version": "v1",
  "plan_conflict_policy": "FAIL"
}
```

This gives you secure API key management with flexible application configuration.

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

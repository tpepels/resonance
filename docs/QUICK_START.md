# Quick Start

## Prerequisites

- Python 3.10+
- An [AcoustID API key](https://acoustid.org/new-application) (free)
- Optional: [Discogs personal access token](https://www.discogs.com/settings/developers)

## Install

```bash
pip install -e .
```

## Configure credentials

```bash
export ACOUSTID_API_KEY="your-key-here"
export DISCOGS_TOKEN="your-token-here"       # optional, improves matching
```

## One-command pipeline

The `decide` command runs the full workflow: scan → resolve → prompt → plan.

```bash
resonance decide /path/to/music/library \
  --state-db state.db \
  --cache-db cache.db
```

This will:
1. **Scan** your library for audio directories
2. **Resolve** each directory against AcoustID/MusicBrainz/Discogs
3. **Prompt** you for ambiguous matches (interactive)
4. **Plan** deterministic rename/tag operations

## Step-by-step workflow

If you prefer more control, run each stage separately:

```bash
# 1. Scan library into state DB
resonance scan /path/to/music --state-db state.db

# 2. Resolve directories using provider metadata
resonance resolve /path/to/music --state-db state.db --cache-db cache.db

# 3. Interactively decide ambiguous matches
resonance prompt --state-db state.db --cache-db cache.db

# 4. Generate plan artifacts for resolved directories
resonance plan --dir-id <dir-id> --state-db state.db --cache-db cache.db --library-root /path/to/music

# 5. Apply the plan (dry-run by default)
resonance apply --plan plan.json --state-db state.db --library-root /path/to/music

# 6. Apply for real
resonance apply --plan plan.json --state-db state.db --library-root /path/to/music --no-dry-run
```

## Diagnostic commands

```bash
# Identify a single directory and score candidates
resonance identify /path/to/album --cache-db cache.db

# Inspect directory state
resonance audit <dir-id> --state-db state.db

# Validate DB and environment
resonance doctor --state-db state.db

# Rollback an applied plan
resonance rollback --report report.json --state-db state.db --library-root /path/to/music

# Reset a jailed directory
resonance unjail <dir-id> --state-db state.db
```

## JSON output

All commands support `--json` for machine-readable output:

```bash
resonance scan /path/to/music --state-db state.db --json | jq .
```

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

Resonance organizes your music library by:
1. **Fingerprinting** audio files to identify canonical artist/composer/album information
2. **Prompting** you for uncertain matches (with preview and manual entry options)
3. **Enriching** metadata from MusicBrainz and Discogs
4. **Organizing** files into `Artist/Album/tracks` structure (or `Composer/Performer` for classical)
5. **Cleaning up** source directories after successful moves

## Key Features

- **Visitor Pattern Architecture**: Clean, simple processing pipeline
- **Fingerprint-Based Identification**: Uses AcoustID + MusicBrainz
- **Canonical Name Resolution**: Merges artist variants (e.g., "Bach, J.S." → "Johann Sebastian Bach")
- **Interactive & Daemon Modes**: Process immediately or defer user prompts
- **Smart Caching**: Remembers decisions across runs
- **Transaction Support**: Rollback on errors or crashes
- **Classical Music Support**: Special handling for composer/performer structures

## Installation

```bash
cd resonance
pip install -e .
```

## Usage

### Interactive Scan
```bash
resonance scan /path/to/music
```

### Daemon Mode
```bash
# Start watching a directory
resonance daemon /path/to/music

# Later, answer deferred prompts
resonance prompt
```

### Other Commands
```bash
# Show help
resonance --help

# Reprocess skipped directories
resonance scan --unjail /path/to/music
```

## Architecture

Resonance uses a clean **Visitor Pattern**:

```
Directory → Process with Visitors:
  1. IdentifyVisitor    - Fingerprint files, determine canonical artist/album
  2. PromptVisitor      - Ask user for uncertain matches
  3. EnrichVisitor      - Add metadata from MusicBrainz/Discogs
  4. OrganizeVisitor    - Move files to Artist/Album structure
  5. CleanupVisitor     - Delete empty source directories
```

## Migrating from audio-meta

Resonance is a clean rewrite of the audio-meta project. Your cache will work automatically - just point Resonance at your library.

## License

MIT

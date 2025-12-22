#!/usr/bin/env bash
#
# snapshot_real_corpus.sh
#
# Safely snapshot a music library (or subset) into tests/real_corpus/input/
# for use with the real-world corpus test harness.
#
# Safety:
# - Operates on a copy only (never modifies source)
# - Idempotent (can be run multiple times)
# - Respects MANIFEST.txt for subset snapshots
#
# Usage:
#   ./scripts/snapshot_real_corpus.sh [SOURCE_PATH]
#
# If SOURCE_PATH is omitted, defaults to /home/tom/music

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REAL_CORPUS_DIR="$REPO_ROOT/tests/real_corpus"
INPUT_DIR="$REAL_CORPUS_DIR/input"
MANIFEST_FILE="$REAL_CORPUS_DIR/MANIFEST.txt"

# Default source path (can be overridden by argument)
DEFAULT_SOURCE="/home/tom/music"
SOURCE_PATH="${1:-$DEFAULT_SOURCE}"

# Validate source path
if [[ ! -d "$SOURCE_PATH" ]]; then
    echo "Error: Source path does not exist: $SOURCE_PATH" >&2
    echo "Usage: $0 [SOURCE_PATH]" >&2
    exit 1
fi

echo "==> Real-World Corpus Snapshot"
echo "    Source: $SOURCE_PATH"
echo "    Target: $INPUT_DIR"
echo ""

# Check for FULL_LIBRARY environment variable
if [[ "${FULL_LIBRARY:-0}" == "1" ]]; then
    MODE="full"
    echo "==> Full library mode (FULL_LIBRARY=1)"
elif [[ -f "$MANIFEST_FILE" ]]; then
    # Filter out comments and empty lines
    MANIFEST_DIRS=($(grep -v '^#' "$MANIFEST_FILE" | grep -v '^[[:space:]]*$' || true))

    if [[ ${#MANIFEST_DIRS[@]} -eq 0 ]]; then
        echo "==> Full library mode (MANIFEST.txt empty)"
        MODE="full"
    else
        MODE="manifest"
        echo "==> Manifest mode: snapshotting ${#MANIFEST_DIRS[@]} directories"
        for dir in "${MANIFEST_DIRS[@]}"; do
            echo "    - $dir"
        done
        echo ""
    fi
else
    echo "==> Full library mode (no MANIFEST.txt)"
    MODE="full"
fi

# Create input directory if needed
mkdir -p "$INPUT_DIR"

# Snapshot logic
if [[ "$MODE" == "manifest" ]]; then
    # Manifest mode: copy only listed directories
    echo "==> Copying directories from manifest..."

    for dir in "${MANIFEST_DIRS[@]}"; do
        SOURCE_DIR="$SOURCE_PATH/$dir"
        TARGET_DIR="$INPUT_DIR/$dir"

        if [[ ! -d "$SOURCE_DIR" ]]; then
            echo "Warning: Directory not found in source: $dir" >&2
            continue
        fi

        echo "    Copying: $dir"
        rsync -a --delete \
              --exclude='*.db' \
              --exclude='*.db-journal' \
              --exclude='.DS_Store' \
              --exclude='Thumbs.db' \
              "$SOURCE_DIR/" "$TARGET_DIR/"
    done

    # Clean up any directories in input/ that are no longer in manifest
    echo "==> Cleaning up stale directories..."
    for existing in "$INPUT_DIR"/*/ ; do
        if [[ -d "$existing" ]]; then
            basename_dir="$(basename "$existing")"
            found=0
            for manifest_dir in "${MANIFEST_DIRS[@]}"; do
                if [[ "$basename_dir" == "$manifest_dir" ]]; then
                    found=1
                    break
                fi
            done
            if [[ $found -eq 0 ]]; then
                echo "    Removing: $basename_dir (not in manifest)"
                rm -rf "$existing"
            fi
        fi
    done

else
    # Full mode: copy entire library
    echo "==> Copying entire library..."
    echo "    Warning: This may take a while for large libraries."
    echo ""

    rsync -a --delete \
          --exclude='*.db' \
          --exclude='*.db-journal' \
          --exclude='.DS_Store' \
          --exclude='Thumbs.db' \
          "$SOURCE_PATH/" "$INPUT_DIR/"
fi

echo ""
echo "==> Snapshot complete!"
echo "    Input directory: $INPUT_DIR"
echo ""

# Count directories and estimate size
DIR_COUNT=$(find "$INPUT_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
TOTAL_SIZE=$(du -sh "$INPUT_DIR" 2>/dev/null | cut -f1 || echo "unknown")

echo "    Directories: $DIR_COUNT"
echo "    Total size:  $TOTAL_SIZE"
echo ""
echo "Next steps:"
echo "  1. Review the snapshot: ls -la $INPUT_DIR"
echo "  2. Run the test:       RUN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py"
echo "  3. Generate snapshots: python regen_real_corpus.py"
echo ""

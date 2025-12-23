#!/bin/bash
# Safe metadata extraction script for real-world corpus testing
# Extracts directory structure and file metadata without copying files

set -uo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CORPUS_ROOT="$REPO_ROOT/tests/real_corpus"
METADATA_FILE="$CORPUS_ROOT/metadata.json"
MANIFEST_FILE="$CORPUS_ROOT/MANIFEST.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

# Safety checks
check_safety() {
    local source_path="$1"

    # Allow specific known safe paths
    if [[ "$source_path" == "/home/tom/music" ]]; then
        log_warn "Allowing extraction from /home/tom/music (explicitly permitted)"
        return
    fi

    # Never allow paths that look like live libraries (except explicitly allowed above)
    if [[ "$source_path" =~ ^/home/[^/]+/Music(/|$) ]] || \
       [[ "$source_path" =~ ^/home/[^/]+/music(/|$) ]] || \
       [[ "$source_path" =~ ^/Users/[^/]+/Music(/|$) ]] || \
       [[ "$source_path" =~ ^/Users/[^/]+/music(/|$) ]]; then
        log_error "Refusing to extract from what appears to be a live library path: $source_path"
        log_error "This is for safety - extraction is read-only but we block common live paths."
        log_error "Use a different path if you really need to extract from a live library."
        exit 1
    fi

    # Check if source exists
    if [[ ! -d "$source_path" ]]; then
        log_error "Source path does not exist: $source_path"
        exit 1
    fi

    # Manifest is optional - if it doesn't exist or is empty, we'll scan the entire library
}

# Parse manifest file
parse_manifest() {
    local manifest_file="$1"

    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue

        echo "$line"
    done < "$manifest_file"
}

# Extract file metadata
extract_file_metadata() {
    local file_path="$1"
    local rel_path="$2"

    # Basic file stats
    local size=$(stat -c%s "$file_path" 2>/dev/null || echo "0")
    local mtime=$(stat -c%Y "$file_path" 2>/dev/null || echo "0")
    local permissions=$(stat -c%a "$file_path" 2>/dev/null || echo "644")

    # Audio file detection (basic)
    local is_audio=false
    local audio_info="{}"

    case "${file_path,,}" in
        *.flac|*.mp3|*.m4a|*.aac|*.ogg|*.wma|*.wav)
            is_audio=true
            # Extract basic audio metadata if possible
            if command -v ffprobe >/dev/null 2>&1; then
                # Try to extract duration only (simpler and more reliable)
                local duration_str
                duration_str=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$file_path" 2>/dev/null || echo "")
                if [[ -n "$duration_str" ]] && [[ "$duration_str" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                    # Convert to integer seconds (truncate decimal)
                    local duration
                    duration=${duration_str%.*}
                    audio_info="{\"duration\": $duration}"
                fi
            elif command -v mediainfo >/dev/null 2>&1; then
                # Fallback to mediainfo
                local duration
                duration=$(mediainfo --Inform="General;%Duration%" "$file_path" 2>/dev/null || echo "")
                if [[ -n "$duration" ]]; then
                    # Convert milliseconds to seconds
                    duration=$((duration / 1000))
                    audio_info="{\"duration\": $duration}"
                fi
            fi
            ;;
    esac

    # Create JSON entry (escape path for JSON)
    escaped_path=$(printf '%s\n' "$rel_path" | sed 's/\\/\\\\/g; s/"/\\"/g')
    cat << EOF
{
  "path": "$escaped_path",
  "size": $size,
  "mtime": $mtime,
  "permissions": "$permissions",
  "is_audio": $is_audio,
  "audio_info": $audio_info
}
EOF
}

# Extract directory tree
extract_directory_tree() {
    local source_path="$1"
    shift  # Remove source_path from arguments
    local manifest_entries=("$@")  # Remaining args are manifest entries

    log_info "Extracting metadata from: $source_path"

    # If no manifest entries provided, scan the entire source directory
    if [[ ${#manifest_entries[@]} -eq 0 ]]; then
        log_info "No manifest entries - scanning entire library"
        local scan_paths=("$source_path")
    else
        log_info "Manifest entries: ${#manifest_entries[@]}"
        local -a scan_paths=()
        for entry in "${manifest_entries[@]}"; do
            local full_path="$source_path/$entry"
            if [[ -d "$full_path" ]]; then
                scan_paths+=("$full_path")
            else
                log_warn "Directory not found, skipping: $entry"
            fi
        done
    fi

    local -a metadata_entries=()
    local scanned_count=0
    local audio_count=0

    for scan_path in "${scan_paths[@]}"; do
        log_info "Scanning: ${scan_path#$source_path/}"

        # Find all files in this directory tree
        while IFS= read -r -d '' file_path; do
            # Get relative path from source directory
            local rel_path="${file_path#$source_path/}"

            # No need to skip long filenames - Resonance now uses hash-based metadata naming

            # Extract metadata
            local metadata
            metadata=$(extract_file_metadata "$file_path" "$rel_path")

            metadata_entries+=("$metadata")
            ((scanned_count++))

            # Count audio files
            if [[ "$metadata" == *"\"is_audio\": true"* ]]; then
                ((audio_count++))
            fi

        done < <(find "$scan_path" -type f -print0)
    done

    # Create final JSON structure
    {
        echo "{"
        echo "  \"_comment\": \"Extracted filesystem metadata for real-world corpus testing\","
        echo "  \"_extraction_time\": \"$(date -Iseconds)\","
        echo "  \"_source_path\": \"$source_path\","
        echo "  \"_total_files\": $scanned_count,"
        echo "  \"_audio_files\": $audio_count,"
        echo "  \"files\": ["

        # Join metadata entries with commas
        local first=true
        for metadata in "${metadata_entries[@]}"; do
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            echo "$metadata"
        done

        echo ""
        echo "  ]"
        echo "}"
    } > "$METADATA_FILE"

    log_success "Metadata extraction complete: $scanned_count files, $audio_count audio files"
    log_info "Metadata saved to: $METADATA_FILE"
    log_info "File size: $(du -h "$METADATA_FILE" | cut -f1)"
}

# Main execution
main() {
    if [[ $# -ne 1 ]]; then
        echo "Usage: $0 <source_library_path>"
        echo ""
        echo "Safely extracts metadata from music library directories for corpus testing."
        echo "Never modifies the source library - read-only operation."
        echo ""
        echo "Example:"
        echo "  $0 /path/to/music/library"
        echo ""
        echo "See $CORPUS_ROOT/README.md for details."
        exit 1
    fi

    local source_path="$1"

    log_info "Real-World Corpus Metadata Extraction"
    log_info "====================================="

    # Safety checks
    check_safety "$source_path"

    # Parse manifest (optional)
    if [[ -f "$MANIFEST_FILE" ]]; then
        log_info "Parsing manifest: $MANIFEST_FILE"
        mapfile -t manifest_entries < <(parse_manifest "$MANIFEST_FILE")
        if [[ ${#manifest_entries[@]} -gt 0 ]]; then
            log_info "Found ${#manifest_entries[@]} manifest entries"
        else
            log_info "Manifest exists but contains no entries - scanning entire library"
            manifest_entries=()
        fi
    else
        log_info "No manifest file found - scanning entire library"
        manifest_entries=()
    fi

    # Extract metadata
    extract_directory_tree "$source_path" "${manifest_entries[@]}"

    log_success "Metadata extraction complete!"
    log_info "Run: RUN_REAL_CORPUS=1 pytest tests/integration/test_real_world_corpus.py"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

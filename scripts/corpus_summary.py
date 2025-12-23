#!/usr/bin/env python3
"""
Corpus summary script for debugging and validation.

This script provides a small summary (<200KB) of corpus data without
opening large files, suitable for agent-side validation and debugging.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any

def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def get_file_info(file_path: Path) -> Dict[str, Any]:
    """Get file size and hash without reading content."""
    stat = file_path.stat()
    return {
        "size": stat.st_size,
        "size_human": format_size(stat.st_size),
        "sha256": compute_sha256(file_path)
    }

def format_size(bytes_size: int | float) -> str:
    """Format bytes to human readable."""
    if bytes_size == 0:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return ".1f"
        bytes_size /= 1024.0
    return ".1f"

def analyze_metadata(metadata_path: Path) -> Dict[str, Any]:
    """Analyze metadata.json structure without loading full file."""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        # Read just enough to get structure
        content = f.read(2048)  # Read first 2KB
        first_brace = content.find('{')
        if first_brace >= 0:
            # Find the end of the files array start
            files_start = content.find('"files": [', first_brace)
            if files_start >= 0:
                # Extract header info before files array
                header = content[:files_start]
                try:
                    # Parse header as JSON
                    header_json = json.loads(header[:-1] + '}}')  # Close the object
                    return {
                        "total_files": header_json.get("_total_files", 0),
                        "audio_files": header_json.get("_audio_files", 0),
                        "extraction_time": header_json.get("_extraction_time", "unknown"),
                        "source_path": header_json.get("_source_path", "unknown"),
                        "files_array_start": files_start
                    }
                except json.JSONDecodeError:
                    pass

    return {"error": "Could not parse metadata header"}

def analyze_review_bundle(bundle_path: Path) -> Dict[str, Any]:
    """Analyze review_bundle.json structure."""
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    return {
        "format": bundle.get("_format", "unknown"),
        "generated_at": bundle.get("_generated_at", "unknown"),
        "total_directories": bundle["corpus_summary"]["total_directories"],
        "total_files": bundle["corpus_summary"]["total_files"],
        "audio_files": bundle["corpus_summary"]["audio_files"],
        "directory_tree_count": len(bundle.get("directory_tree", [])),
        "tracks_count": len(bundle.get("tracks", [])),
        "input_file_hashes": bundle.get("input_file_hashes", {}),
        "expected_states_count": len(bundle.get("expected_outcomes", {}).get("states", {})),
        "expected_tags_count": len(bundle.get("expected_outcomes", {}).get("tags", [])),
        "decisions_count": len(bundle.get("expected_outcomes", {}).get("decisions", {}))
    }

def analyze_directory_depths(bundle_path: Path) -> Dict[str, Any]:
    """Analyze directory depth statistics."""
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    depths = []
    for dir_info in bundle.get("directory_tree", []):
        path = dir_info["dir_path"]
        depth = len(path.split('/'))
        depths.append(depth)

    if depths:
        return {
            "min_depth": min(depths),
            "max_depth": max(depths),
            "avg_depth": sum(depths) / len(depths),
            "depth_distribution": {
                f"depth_{d}": depths.count(d) for d in sorted(set(depths))
            }
        }
    return {"error": "No directories found"}

def sample_directories(bundle_path: Path, count: int = 5) -> list:
    """Get sample directory information."""
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    directories = bundle.get("directory_tree", [])
    if len(directories) <= count:
        return directories

    # Sample from different positions
    samples = []
    step = len(directories) // count
    for i in range(0, len(directories), step):
        if len(samples) < count:
            samples.append(directories[i])

    return samples

def sample_tracks(bundle_path: Path, count: int = 5) -> list:
    """Get sample track information."""
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    tracks = bundle.get("tracks", [])
    if len(tracks) <= count:
        return tracks

    # Sample from different positions
    samples = []
    step = len(tracks) // count
    for i in range(0, len(tracks), step):
        if len(samples) < count:
            samples.append(tracks[i])

    return samples

def main():
    """Main entry point."""
    print("Corpus Summary Analysis")
    print("=" * 50)

    # File paths
    metadata_path = Path("tests/real_corpus/metadata.json")
    bundle_path = Path("review_bundle.json")
    expected_state_path = Path("tests/real_corpus/expected_state.json")
    expected_layout_path = Path("tests/real_corpus/expected_layout.json")
    expected_tags_path = Path("tests/real_corpus/expected_tags.json")
    decisions_path = Path("tests/real_corpus/decisions.json")

    # Analyze file sizes
    print("\n1. FILE SIZES:")
    files_to_check = [
        ("metadata.json", metadata_path),
        ("review_bundle.json", bundle_path),
        ("expected_state.json", expected_state_path),
        ("expected_layout.json", expected_layout_path),
        ("expected_tags.json", expected_tags_path),
        ("decisions.json", decisions_path),
    ]

    for name, path in files_to_check:
        if path.exists():
            info = get_file_info(path)
            print(".1f")
        else:
            print(f"  {name}: NOT FOUND")

    # Analyze metadata structure
    print("\n2. METADATA ANALYSIS:")
    if metadata_path.exists():
        meta_info = analyze_metadata(metadata_path)
        for key, value in meta_info.items():
            print(f"  {key}: {value}")

    # Analyze review bundle
    print("\n3. REVIEW BUNDLE ANALYSIS:")
    if bundle_path.exists():
        bundle_info = analyze_review_bundle(bundle_path)
        for key, value in bundle_info.items():
            if isinstance(value, dict):
                print(f"  {key}: {len(value)} items")
            else:
                print(f"  {key}: {value}")

    # Directory depth analysis
    print("\n4. DIRECTORY DEPTH ANALYSIS:")
    if bundle_path.exists():
        depth_info = analyze_directory_depths(bundle_path)
        for key, value in depth_info.items():
            print(f"  {key}: {value}")

    # Sample directories
    print("\n5. SAMPLE DIRECTORIES:")
    if bundle_path.exists():
        samples = sample_directories(bundle_path, 3)
        for i, sample in enumerate(samples):
            print(f"  [{i+1}] {sample['dir_path']}")
            print(f"      Audio files: {sample['audio_files']}")
            print(f"      Total size: {format_size(sample['total_size'])}")

    # Sample tracks
    print("\n6. SAMPLE TRACKS:")
    if bundle_path.exists():
        samples = sample_tracks(bundle_path, 3)
        for i, sample in enumerate(samples):
            print(f"  [{i+1}] {sample['original_path']}")
            print(f"      Size: {format_size(sample['file_size'])}")
            print(f"      Duration: {sample['audio_info']['duration']}s")

    # Schema keys summary
    print("\n7. SCHEMA SUMMARY:")
    schemas = {
        "metadata.json": ["_comment", "_extraction_time", "_source_path", "_total_files", "_audio_files", "files"],
        "review_bundle.json": ["_format", "_generated_at", "_generation_info", "input_file_hashes", "corpus_summary", "directory_tree", "tracks", "expected_outcomes", "review_metadata"],
        "expected_state.json": ["_comment", "_format", "summary", "states"],
        "expected_tags.json": ["_comment", "_format", "tracks"],
        "decisions.json": ["_comment", "_format", "_decisions", "decisions"]
    }

    for filename, keys in schemas.items():
        print(f"  {filename}: {len(keys)} top-level keys")
        print(f"    Keys: {', '.join(keys)}")

    print("\n8. DETERMINISM NOTES:")
    print("  - Directory IDs use stable SHA256-based identifiers")
    print("  - File ordering is deterministic (sorted by filename)")
    print("  - Hashes computed for all inputs and outputs")
    print("  - Generation timestamp included for audit trail")

if __name__ == "__main__":
    main()

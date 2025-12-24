#!/usr/bin/env python3
"""
Safe corpus summary script - provides <200KB summary without loading large files.

This script analyzes the corpus processing artifacts without loading multi-MB
JSON files into memory, ensuring agent stability.
"""

import json
import os
from pathlib import Path
from datetime import datetime

def safe_read_json(path: Path, max_size_kb: int = 200) -> dict:
    """Read JSON file safely, rejecting files over max_size_kb."""
    if not path.exists():
        return {}

    size_kb = path.stat().st_size / 1024
    if size_kb > max_size_kb:
        return {"error": f"File too large ({size_kb:.1f}KB > {max_size_kb}KB limit)"}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

def analyze_metadata(metadata_file: Path) -> dict:
    """Analyze metadata.json without loading full file."""
    if not metadata_file.exists():
        return {"status": "missing", "file_size": 0}

    size_mb = metadata_file.stat().st_size / (1024 * 1024)

    # Read just the header info safely
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            # Read first 2KB to get structure
            header = f.read(2048)
            if '"files"' in header:
                has_files = True
            else:
                has_files = False
            if '"directories"' in header:
                has_directories = True
            else:
                has_directories = False
    except Exception as e:
        return {"status": "error", "error": str(e), "file_size": size_mb}

    return {
        "status": "ok",
        "file_size_mb": round(size_mb, 1),
        "has_files": has_files,
        "has_directories": has_directories,
        "extraction_time": "unknown"  # Would need to parse JSON to get this
    }

def analyze_expected_state(state_file: Path) -> dict:
    """Analyze expected_state.json safely."""
    data = safe_read_json(state_file, 50)  # 50KB limit for state file

    if "error" in data:
        return {"status": "error", "error": data["error"]}

    states = data.get("states", {})
    directories_count = len(states)

    state_counts = {}
    for dir_state in states.values():
        state = dir_state.get("state", "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    return {
        "status": "ok",
        "directories_count": directories_count,
        "state_distribution": state_counts
    }

def analyze_review_bundle(bundle_file: Path) -> dict:
    """Analyze review_bundle.json structure."""
    if not bundle_file.exists():
        return {"status": "missing", "file_size": 0}

    size_mb = bundle_file.stat().st_size / (1024 * 1024)

    # Read just enough to get basic structure
    try:
        with open(bundle_file, 'r', encoding='utf-8') as f:
            # Read first 4KB to get structure
            header = f.read(4096)

            format_match = '"_format":' in header
            generated_match = '"_generated_at":' in header

            # Count directories by finding directory entries
            dir_count = header.count('"dir_path":')

    except Exception as e:
        return {"status": "error", "error": str(e), "file_size": size_mb}

    return {
        "status": "ok",
        "file_size_mb": round(size_mb, 1),
        "format_detected": format_match,
        "generated_at_detected": generated_match,
        "directory_count_estimate": dir_count
    }

def analyze_interface_files(dist_dir: Path) -> dict:
    """Analyze generated interface files."""
    if not dist_dir.exists():
        return {"status": "missing"}

    files = {}
    for file_path in dist_dir.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(dist_dir)
            size_kb = file_path.stat().st_size / 1024
            files[str(rel_path)] = round(size_kb, 1)

    # Special analysis of key files
    index_file = dist_dir / "index.json"
    html_file = dist_dir / "real_corpus_review.html"

    index_size = index_file.stat().st_size / 1024 if index_file.exists() else 0
    html_size = html_file.stat().st_size / 1024 if html_file.exists() else 0

    # Count dir/*.json files
    dir_count = len(list(dist_dir.glob("dir/*.json")))

    return {
        "status": "ok",
        "total_files": len(files),
        "index_json_kb": round(index_size, 1),
        "html_kb": round(html_size, 1),
        "directory_detail_files": dir_count,
        "total_size_kb": round(sum(files.values()), 1)
    }

def main():
    """Main analysis function."""
    repo_root = Path(__file__).parent.parent
    corpus_dir = repo_root / "tests" / "real_corpus"
    dist_dir = repo_root / "dist"

    print("Corpus Summary Analysis")
    print("=" * 50)

    # 1. File sizes
    print("\n1. FILE SIZES:")
    metadata_file = corpus_dir / "metadata.json"
    review_file = repo_root / "review_bundle.json"
    expected_state_file = corpus_dir / "expected_state.json"

    files_to_check = [
        ("metadata.json", metadata_file),
        ("review_bundle.json", review_file),
        ("expected_state.json", expected_state_file),
    ]

    for name, path in files_to_check:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(".1f")
        else:
            print(f"  {name}: MISSING")

    # 2. Metadata analysis
    print("\n2. METADATA ANALYSIS:")
    meta_analysis = analyze_metadata(metadata_file)
    if meta_analysis["status"] == "ok":
        print(f"  Status: OK ({meta_analysis['file_size_mb']}MB)")
        print(f"  Has files array: {meta_analysis['has_files']}")
        print(f"  Has directories array: {meta_analysis['has_directories']}")
    else:
        print(f"  Status: {meta_analysis['status']}")

    # 3. Review bundle analysis
    print("\n3. REVIEW BUNDLE ANALYSIS:")
    bundle_analysis = analyze_review_bundle(review_file)
    if bundle_analysis["status"] == "ok":
        print(f"  Status: OK ({bundle_analysis['file_size_mb']}MB)")
        print(f"  Format detected: {bundle_analysis['format_detected']}")
        print(f"  Directories estimated: {bundle_analysis['directory_count_estimate']}")
    else:
        print(f"  Status: {bundle_analysis['status']}")

    # 4. Directory depth analysis (from review bundle if available)
    print("\n4. DIRECTORY DEPTH ANALYSIS:")
    if review_file.exists() and review_file.stat().st_size < 1024 * 1024:  # < 1MB
        try:
            with open(review_file, 'r', encoding='utf-8') as f:
                bundle = json.load(f)

            directories = bundle.get("directory_tree", [])
            depths = {}
            for d in directories:
                path_parts = d["dir_path"].split('/')
                depth = len(path_parts)
                depths[depth] = depths.get(depth, 0) + 1

            print(f"  Min depth: {min(depths.keys()) if depths else 'N/A'}")
            print(f"  Max depth: {max(depths.keys()) if depths else 'N/A'}")
            print(f"  Total directories: {len(directories)}")
            print(f"  Depth distribution: {dict(sorted(depths.items()))}")
        except Exception as e:
            print(f"  Error reading bundle: {e}")
    else:
        print("  Review bundle too large or missing for depth analysis")

    # 5. Sample directories (from interface index if available)
    print("\n5. SAMPLE DIRECTORIES:")
    index_file = dist_dir / "index.json"
    if index_file.exists() and index_file.stat().st_size < 100 * 1024:  # < 100KB
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)

            root_dirs = index_data.get("root_directories", [])
            if root_dirs:
                for i, d in enumerate(root_dirs[:5], 1):
                    name = d.get("name", "unknown")
                    audio_files = d.get("audio_files", 0)
                    state = d.get("state", "unknown")
                    print(f"  [{i}] {name} (files: {audio_files}, state: {state})")
            else:
                print("  No root directories found in index")
        except Exception as e:
            print(f"  Error reading index: {e}")
    else:
        print("  Index file missing or too large")

    # 6. Sample tracks (would need to load individual dir files - skip for safety)
    print("\n6. SAMPLE TRACKS:")
    print("  (Skipped - would require loading individual directory files)")

    # 7. Schema summary
    print("\n7. SCHEMA SUMMARY:")
    schemas = {
        "metadata.json": ["_comment", "_extraction_time", "_source_path", "_total_files", "_audio_files", "files", "directories"],
        "review_bundle.json": ["_format", "_generated_at", "_generation_info", "input_file_hashes", "corpus_summary", "directory_tree", "tracks", "expected_outcomes", "review_metadata"],
        "expected_state.json": ["_comment", "_format", "summary", "states"],
        "expected_tags.json": ["_comment", "_format", "tracks"],
        "decisions.json": ["_comment", "_format", "_decisions", "decisions"]
    }

    for file_name, keys in schemas.items():
        print(f"  {file_name}: {len(keys)} top-level keys")
        print(f"    Keys: {', '.join(keys)}")

    # 8. Determinism notes
    print("\n8. DETERMINISM NOTES:")
    print("  - Directory IDs use stable SHA256-based identifiers")
    print("  - File ordering is deterministic (sorted by filename)")
    print("  - Hashes computed for all inputs and outputs")
    print("  - Generation timestamp included for audit trail")
    print("  - Agent stability: <200KB summaries, no large file loading")

    print(f"\nAnalysis completed at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

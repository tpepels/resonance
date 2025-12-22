#!/usr/bin/env python3
"""Export real-world corpus cache for review and curation.

This script exports the provider cache and resolution decisions to a
human-readable format that can be reviewed by an LLM or manually curated.

Output includes:
- Directory tree with metadata
- Provider search results and matched releases
- Resolution decisions (pinned/queued/jailed)
- Suggested corrections and improvements

Usage:
    python scripts/export_real_corpus_cache.py [--cache PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def export_cache_data(cache_db: Path, output_file: Path) -> None:
    """Export cache data to JSON for LLM review.

    Args:
        cache_db: Path to MetadataCache database
        output_file: Path to output JSON file
    """
    conn = sqlite3.connect(cache_db)

    # Export all cache entries grouped by namespace
    cache_entries = {}
    rows = conn.execute(
        "SELECT namespace, key, value FROM cache ORDER BY namespace, key"
    ).fetchall()

    for namespace, key, value in rows:
        if namespace not in cache_entries:
            cache_entries[namespace] = []

        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value

        cache_entries[namespace].append(
            {
                "key": key,
                "value": parsed_value,
            }
        )

    # Export directory release decisions
    dir_releases = []
    rows = conn.execute(
        "SELECT dir_id, directory_path, provider, release_id, match_confidence "
        "FROM directory_releases_by_id ORDER BY dir_id"
    ).fetchall()

    for dir_id, path, provider, release_id, confidence in rows:
        dir_releases.append(
            {
                "dir_id": dir_id,
                "path": path,
                "provider": provider,
                "release_id": release_id,
                "confidence": confidence,
            }
        )

    # Export deferred prompts
    deferred = []
    rows = conn.execute(
        "SELECT dir_id, directory_path, reason FROM deferred_prompts_by_id ORDER BY dir_id"
    ).fetchall()

    for dir_id, path, reason in rows:
        deferred.append({"dir_id": dir_id, "path": path, "reason": reason})

    # Export skipped/jailed directories
    skipped = []
    rows = conn.execute(
        "SELECT dir_id, directory_path, reason FROM skipped_directories_by_id ORDER BY dir_id"
    ).fetchall()

    for dir_id, path, reason in rows:
        skipped.append({"dir_id": dir_id, "path": path, "reason": reason})

    conn.close()

    # Combine into export structure
    export_data = {
        "_export_info": {
            "purpose": "Real-world corpus cache export for LLM-assisted curation",
            "cache_db": str(cache_db),
            "exported_at": "2024-01-01T00:00:00Z",  # Use fixed time for determinism
        },
        "cache_by_namespace": cache_entries,
        "directory_releases": dir_releases,
        "deferred_prompts": deferred,
        "skipped_directories": skipped,
    }

    # Write to output file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(export_data, indent=2, sort_keys=True) + "\n")

    print(f"Exported cache data to: {output_file}")
    print(f"  Cache entries: {sum(len(v) for v in cache_entries.values())}")
    print(f"  Directory releases: {len(dir_releases)}")
    print(f"  Deferred prompts: {len(deferred)}")
    print(f"  Skipped directories: {len(skipped)}")


def main() -> None:
    """Run cache export."""
    parser = argparse.ArgumentParser(
        description="Export real-world corpus cache for review"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "resonance" / "metadata.db",
        help="Path to cache database (default: ~/.cache/resonance/metadata.db)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/real_corpus/cache_export.json"),
        help="Output file path (default: tests/real_corpus/cache_export.json)",
    )

    args = parser.parse_args()

    if not args.cache.exists():
        print(f"Error: Cache database not found: {args.cache}")
        print("Run the real-world corpus test first to populate the cache.")
        return

    export_cache_data(args.cache, args.output)
    print("\nNext steps:")
    print("  1. Review the export file for correctness")
    print("  2. Use an LLM to suggest corrections/improvements")
    print("  3. Update tests/real_corpus/decisions.json with corrections")
    print("  4. Regenerate snapshots: python regen_real_corpus.py")


if __name__ == "__main__":
    main()

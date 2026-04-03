#!/usr/bin/env python3
"""Resolve a targeted subset of corpus directories using real provider APIs.

Produces real release IDs for at least 5 directories, then patches
expected_state.json with the results. Designed for Sprint 04 criterion 5.

Reads credentials from .env file (supports KEY=VALUE and YAML-style formats).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts._corpus_library import build_library_from_metadata

# Well-known albums likely to match on MusicBrainz/Discogs
TARGET_DIRS = [
    "John Coltrane/A Love Supreme",
    "John Coltrane/Giant Steps",
    "Miles Davis/Kind of Blue",
    "Nina Simone/I Put a Spell on You",
    "Nina Simone/Little Girl Blue",
    "Joy Division/Unknown Pleasures",
    "Joy Division/Closer",
    "Nirvana/MTV Unplugged in New York",
    "Portishead/Dummy",
    "Talking Heads/Stop Making Sense",
    "Aretha Franklin/Original Album Series",
    "Art Blakey & The Jazz Messengers/Moanin'",
    "The_Beatles/Sgt._Pepper_s_Lonely_Hearts_Club_Band__Remastered_",
    "Agnes Obel/Aventine",
    "Ahmad Jamal/Midnite Jazz & Blues: Waltz for Debby",
]


def _load_env(env_path: Path) -> dict[str, str]:
    """Parse .env file supporting KEY=VALUE and YAML-style key: value formats."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Standard KEY=VALUE
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
            continue
        # YAML-style key: "value"
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*["\']?([^"\']*)["\']?\s*$', line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    return env


def _filter_metadata(metadata: dict, target_dirs: list[str]) -> dict:
    """Return a metadata dict containing only files under target directories."""
    filtered_files = []
    for f in metadata["files"]:
        rel = f["path"]
        for td in target_dirs:
            if rel.startswith(td + "/"):
                filtered_files.append(f)
                break
    return {**metadata, "files": filtered_files}


def main() -> None:
    project_root = Path(__file__).parent.parent
    corpus_root = project_root / "tests" / "real_corpus"
    metadata_file = corpus_root / "metadata.json"

    if not metadata_file.exists():
        raise SystemExit(f"ERROR: {metadata_file} not found")

    # Load credentials from .env
    env = _load_env(project_root / ".env")
    acoustid_key = os.environ.get("ACOUSTID_API_KEY") or env.get("ACOUSTID_API_KEY")
    # .env has YAML-style discogs_token, map to DISCOGS_TOKEN
    discogs_token = (
        os.environ.get("DISCOGS_TOKEN")
        or env.get("DISCOGS_TOKEN")
        or env.get("discogs_token")
    )

    if not acoustid_key:
        raise SystemExit("ERROR: ACOUSTID_API_KEY not found in .env or environment")
    if not discogs_token:
        raise SystemExit("ERROR: DISCOGS_TOKEN / discogs_token not found in .env or environment")

    print(f"Credentials: ACOUSTID_API_KEY={'*' * len(acoustid_key)}, DISCOGS_TOKEN={'*' * len(discogs_token)}")

    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Filter metadata to target subset
    subset = _filter_metadata(metadata, TARGET_DIRS)
    print(f"Filtered to {len(subset['files'])} files across target directories")

    temp_dir = Path(tempfile.mkdtemp(prefix="resonance_subset_"))
    library_root = temp_dir / "library"
    cache_db = temp_dir / "cache.db"

    try:
        # Build library
        print("==> Building library tree...")
        build_library_from_metadata(subset, library_root)

        # Create provider client directly (keep alive for all calls)
        print("==> Creating provider client with real credentials...")
        from resonance.app import ResonanceApp
        from resonance.core.identifier import extract_evidence, identify
        from resonance.infrastructure.scanner import LibraryScanner

        # Set env vars so from_env() works
        os.environ["ACOUSTID_API_KEY"] = acoustid_key
        os.environ["DISCOGS_TOKEN"] = discogs_token

        app = ResonanceApp.from_env(
            library_root=library_root,
            cache_path=cache_db,
            offline=False,
        )
        provider_client = app.provider_client
        print(f"  Provider client: {type(provider_client).__name__}")
        print(f"  Capabilities: {provider_client.capabilities}")

        # Identify each target directory directly (no scan/resolve needed)
        results: dict[str, dict] = {}

        for target_dir in TARGET_DIRS:
            dir_path = library_root / target_dir
            if not dir_path.exists():
                print(f"  SKIP (not in metadata): {target_dir}")
                continue

            audio_files = sorted(
                p
                for p in dir_path.iterdir()
                if p.is_file()
                and p.suffix.lower() in LibraryScanner.DEFAULT_EXTENSIONS
            )
            if not audio_files:
                print(f"  SKIP (no audio): {target_dir}")
                continue

            evidence = extract_evidence(audio_files)
            print(
                f"\n==> Identifying: {target_dir} "
                f"({evidence.track_count} tracks, {evidence.total_duration_seconds}s)"
            )

            artist = evidence.tracks[0].existing_tags.get("artist") if evidence.tracks else None
            album = evidence.tracks[0].existing_tags.get("album") if evidence.tracks else None
            print(f"    Hints: artist={artist!r}, album={album!r}")

            try:
                result = identify(evidence, provider_client)
            except Exception as exc:
                print(f"    ERROR: {type(exc).__name__}: {exc}")
                results[target_dir] = {"state": "JAILED"}
                continue

            print(f"    Candidates: {len(result.candidates)}, tier={result.tier}")

            if result.best_candidate:
                best = result.best_candidate
                print(
                    f"    BEST: {best.release.provider}:{best.release.release_id} "
                    f'"{best.release.title}" by {best.release.artist} '
                    f"({best.release.track_count} tracks, score={best.total_score:.3f})"
                )
                results[target_dir] = {
                    "state": "RESOLVED_USER",
                    "provider": best.release.provider,
                    "release_id": best.release.release_id,
                }
            else:
                print("    No candidates — JAILED")
                results[target_dir] = {"state": "JAILED"}

        app.close()

        # Report provider stats
        from resonance.providers.caching import PROVIDER_CALL_COUNTS

        print("\n==> Provider Statistics:")
        for provider, stats in PROVIDER_CALL_COUNTS.items():
            http = stats["http_calls"]
            cache = stats["cache_hits"]
            if http + cache > 0:
                print(f"  {provider}: {http} HTTP, {cache} cache")

        # Summary
        resolved = {k: v for k, v in results.items() if v["state"] != "JAILED"}
        print(f"\n==> Results: {len(results)} dirs processed, {len(resolved)} with real release IDs")

        if len(resolved) < 5:
            print("WARNING: fewer than 5 real release IDs obtained")

        for dir_name, info in sorted(resolved.items()):
            print(f"  {dir_name}: {info['provider']}:{info['release_id']}")

        # Patch expected_state.json
        expected_state_path = corpus_root / "expected_state.json"
        with open(expected_state_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

        patched = 0
        for dir_name, result in results.items():
            if dir_name in expected["states"] and result["state"] in (
                "RESOLVED_AUTO",
                "RESOLVED_USER",
            ):
                expected["states"][dir_name] = {
                    "state": result["state"],
                    "provider": result["provider"],
                    "release_id": result["release_id"],
                }
                patched += 1

        # Update summary
        applied_count = sum(
            1
            for v in expected["states"].values()
            if isinstance(v, dict)
            and v.get("state") in ("RESOLVED_AUTO", "RESOLVED_USER", "APPLIED")
        )
        jailed_count = sum(
            1
            for v in expected["states"].values()
            if isinstance(v, dict) and v.get("state") == "JAILED"
        )
        expected["summary"]["applied"] = applied_count
        expected["summary"]["jailed"] = jailed_count
        expected["_format"] = "Generated by Sprint 04 — subset resolved with real provider APIs"

        with open(expected_state_path, "w", encoding="utf-8") as f:
            json.dump(expected, f, indent=2, ensure_ascii=False)

        print(f"\n==> Patched {patched} directories in expected_state.json")

    finally:
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

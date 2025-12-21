"""Prompt command - answer deferred user prompts."""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from ..app import ResonanceApp
from ..core.models import AlbumInfo
from ..core.identifier import identify
from ..core.state import DirectoryState
from ..infrastructure.scanner import LibraryScanner
from ..infrastructure.cache import MetadataCache


def run_prompt(args: Namespace) -> int:
    """Run the prompt command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    if not getattr(args, "legacy", False):
        print(
            "prompt uses deprecated V2 visitor pipeline; rerun with --legacy or use V3 commands."
        )
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    cache_path = Path(args.cache).expanduser()
    cache = MetadataCache(cache_path)

    deferred = cache.get_deferred_prompts_by_id()
    if not deferred:
        print("No deferred prompts found.")
        cache.close()
        return 0

    print(f"Resonance prompt mode ({len(deferred)} pending)")
    print(f"  Cache: {cache_path}")
    print()

    app = ResonanceApp.from_env(
        library_root=Path.cwd(),
        cache_path=cache_path,
        interactive=True,
        dry_run=False,
    )

    try:
        pipeline = app.create_pipeline(allow_legacy=True)
        for dir_id, directory, _reason in deferred:
            if directory is None or not directory.exists():
                if dir_id:
                    cache.remove_deferred_prompt_by_id(dir_id)
                elif directory:
                    cache.remove_deferred_prompt(directory)
                continue

            if dir_id:
                cache.remove_deferred_prompt_by_id(dir_id)
            else:
                cache.remove_deferred_prompt(directory)
            album = AlbumInfo(directory=directory, dir_id=dir_id)
            pipeline.process(album)
    except KeyboardInterrupt:
        print("\nPrompt processing interrupted by user")
        return 130
    finally:
        app.close()
        cache.close()

    return 0


def run_prompt_uncertain(
    *,
    store,
    provider_client,
    input_provider=input,
    output_sink=print,
    evidence_builder=None,
) -> None:
    """Resolve queued directories via injected I/O (testable)."""
    queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
    queued = sorted(
        queued,
        key=lambda record: (str(record.last_seen_path), record.dir_id),
    )
    extensions = LibraryScanner.DEFAULT_EXTENSIONS

    for record in queued:
        audio_files = sorted(
            path
            for path in record.last_seen_path.iterdir()
            if path.is_file() and path.suffix.lower() in extensions
        )
        if not audio_files:
            continue
        if evidence_builder is None:
            raise ValueError("evidence_builder is required")
        evidence = evidence_builder(audio_files)
        result = identify(evidence, provider_client)
        candidates = list(result.candidates)

        output_sink(f"Queued: {record.last_seen_path}")
        output_sink("Tracks:")
        for index, path in enumerate(audio_files, start=1):
            duration = None
            if index - 1 < len(evidence.tracks):
                duration = evidence.tracks[index - 1].duration_seconds
            duration_str = f" ({duration}s)" if duration else ""
            output_sink(f"  {index}. {path.name}{duration_str}")
        if candidates:
            for idx, candidate in enumerate(candidates, start=1):
                output_sink(
                    f"[{idx}] {candidate.release.provider}:{candidate.release.release_id} "
                    f"{candidate.release.artist} - {candidate.release.title} "
                    f"score={candidate.total_score:.2f} coverage={candidate.fingerprint_coverage:.2f}"
                )
        else:
            output_sink("No candidates available.")

        if result.reasons:
            output_sink(f"Reasons: {'; '.join(result.reasons)}")

        options = [
            "Options:",
            "  [1..N] Select a release from the list",
            "  [mb:ID] Provide MusicBrainz release ID",
            "  [dg:ID] Provide Discogs release ID",
            "  [s] Jail this directory",
            "  [enter] Skip for now",
        ]
        for line in options:
            output_sink(line)

        response = input_provider("Choice: ").strip().lower()
        if not response:
            continue
        if response == "s":
            store.set_state(record.dir_id, DirectoryState.JAILED)
            continue
        if response.isdigit():
            choice = int(response)
            if 1 <= choice <= len(candidates):
                selected = candidates[choice - 1].release
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider=selected.provider,
                    pinned_release_id=selected.release_id,
                )
            continue
        if response.startswith("mb:"):
            release_id = response[3:].strip()
            if release_id:
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider="musicbrainz",
                    pinned_release_id=release_id,
                )
            continue
        if response.startswith("dg:"):
            release_id = response[3:].strip()
            if release_id:
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider="discogs",
                    pinned_release_id=release_id,
                )
            continue

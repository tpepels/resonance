"""User prompting service for uncertain matches."""

from __future__ import annotations

from typing import Optional

from .models import AlbumInfo, UserSkippedError


class PromptService:
    """Service for prompting user to resolve uncertain matches."""

    def __init__(self, interactive: bool = True):
        """Initialize prompt service.

        Args:
            interactive: If False, defer prompts (for daemon mode)
        """
        self.interactive = interactive

    def prompt_for_release(self, album: AlbumInfo) -> Optional[tuple[str, str]]:
        """Prompt user to choose or provide a release.

        Args:
            album: Album with uncertain match

        Returns:
            Tuple of (provider, release_id) or None if skipped

        Raises:
            UserSkippedError: If user chooses to skip this directory
        """
        if not self.interactive:
            # Daemon mode - don't prompt
            return None

        print(f"\n{'='*70}")
        print(f"Uncertain match: {album.directory}")
        print(f"{'='*70}")

        # Show what we know
        print(f"\nTracks: {album.total_tracks}")
        if album.canonical_artist:
            print(f"Artist: {album.canonical_artist}")
        if album.canonical_composer:
            print(f"Composer: {album.canonical_composer}")
        if album.canonical_performer:
            print(f"Performer: {album.canonical_performer}")
        if album.canonical_album:
            print(f"Album: {album.canonical_album}")

        # Show sample tracks
        print("\nSample tracks:")
        for i, track in enumerate(album.tracks[:5], 1):
            duration_str = f" ({track.duration_seconds}s)" if track.duration_seconds else ""
            title = track.title or track.path.stem
            print(f"  {i}. {title}{duration_str}")

        if len(album.tracks) > 5:
            print(f"  ... and {len(album.tracks) - 5} more")

        # Show release candidates if available
        candidates = album.extra.get("release_candidates", [])
        if candidates:
            print(f"\nFound {len(candidates)} release candidates:")
            for i, candidate in enumerate(candidates[:5], 1):
                year_str = f" ({candidate.year})" if candidate.year else ""
                provider_tag = "MB" if candidate.provider == "musicbrainz" else "DG"
                print(f"  [{i}] {candidate.artist} - {candidate.title}{year_str}")
                print(f"      [{provider_tag}] {candidate.track_count} tracks | "
                      f"score: {candidate.score:.2f} | coverage: {candidate.coverage:.0%}")

        print("\nOptions:")
        if candidates:
            print(f"  [1-{min(5, len(candidates))}] Select a release from the list")
        print("  [s] Skip this directory (jail it)")
        print("  [mb:ID] Provide MusicBrainz release ID")
        print("  [dg:ID] Provide Discogs release ID")
        print("  [enter] Skip for now (will prompt again)")

        while True:
            try:
                response = input("\nYour choice: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()  # Newline after ^C/^D
                raise UserSkippedError("User interrupted")

            if not response:
                continue

            normalized = response.lower()
            if normalized in {"s", "skip"}:
                raise UserSkippedError("User chose to skip")

            # Check if user selected a number from the list
            if normalized.isdigit():
                choice = int(normalized)
                if 1 <= choice <= min(5, len(candidates)):
                    selected = candidates[choice - 1]
                    print(f"Selected: {selected.artist} - {selected.title}")
                    return (selected.provider, selected.release_id)
                print(f"Invalid choice: {choice}")
                continue

            if normalized.startswith('mb:'):
                release_id = normalized[3:].strip()
                if release_id:
                    return ("musicbrainz", release_id)

            if normalized.startswith('dg:'):
                release_id = normalized[3:].strip()
                if release_id:
                    return ("discogs", release_id)

    def show_preview(self, album: AlbumInfo) -> None:
        """Show detailed preview of album."""
        print(f"\n{'='*70}")
        print(f"Album Preview: {album.directory.name}")
        print(f"{'='*70}\n")

        if album.is_classical:
            print("Type: Classical")
            if album.canonical_composer:
                print(f"Composer: {album.canonical_composer}")
            if album.canonical_performer:
                print(f"Performer: {album.canonical_performer}")
        else:
            print("Type: Popular")
            if album.canonical_artist:
                print(f"Artist: {album.canonical_artist}")
            if album.canonical_album:
                print(f"Album: {album.canonical_album}")

        if album.year:
            print(f"Year: {album.year}")

        if album.musicbrainz_release_id:
            print(f"MusicBrainz: {album.musicbrainz_release_id}")
        if album.discogs_release_id:
            print(f"Discogs: {album.discogs_release_id}")

        print(f"\nTracks ({len(album.tracks)}):")
        for track in album.tracks:
            num = f"{track.track_number:02d}" if track.track_number else "??"
            title = track.title or track.path.stem
            duration = f" ({track.duration_seconds}s)" if track.duration_seconds else ""
            print(f"  {num}. {title}{duration}")

        if album.destination_path:
            print(f"\nDestination: {album.destination_path}")

        print()

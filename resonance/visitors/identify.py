"""IdentifyVisitor - Step 1: Fingerprint files and determine canonical artist/album."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..core.models import AlbumInfo, MatchSource
from ..core.visitor import BaseVisitor
from ..core.identity import IdentityCanonicalizer
from ..core.identity.matching import strip_featuring
from ..infrastructure.cache import MetadataCache
from ..providers.musicbrainz import MusicBrainzClient
from ..services.metadata_reader import MetadataReader
from ..services.release_search import ReleaseSearchService

logger = logging.getLogger(__name__)


class IdentifyVisitor(BaseVisitor):
    """First visitor: Identify canonical artist/composer/album using fingerprints.

    This visitor:
    1. Reads metadata from all files in the directory
    2. Fingerprints files using AcoustID
    3. Looks up recordings in MusicBrainz
    4. Determines canonical artist/composer/album
    5. Applies identity canonicalization
    6. Sets album.canonical_artist, album.canonical_album, etc.
    """

    def __init__(
        self,
        musicbrainz: MusicBrainzClient,
        canonicalizer: IdentityCanonicalizer,
        cache: MetadataCache,
        release_search: Optional[ReleaseSearchService],
    ):
        super().__init__("Identify")
        self.musicbrainz = musicbrainz
        self.canonicalizer = canonicalizer
        self.cache = cache
        self.release_search = release_search

    def visit(self, album: AlbumInfo) -> bool:
        """Identify the album using fingerprinting.

        Args:
            album: Album to identify

        Returns:
            True to continue to next visitor, False to stop
        """
        logger.info(f"Identifying: {album.directory}")

        # Check if directory is skipped
        if self.cache.is_directory_skipped(album.directory):
            logger.info(f"  Skipped (jailed): {album.directory}")
            album.is_skipped = True
            return False

        # Check cache for existing release decision
        cached = self.cache.get_directory_release(album.directory)
        if cached:
            provider, release_id, confidence = cached
            logger.info(f"  Cached decision: {provider}:{release_id} ({confidence:.2f})")

            if provider == "musicbrainz":
                album.musicbrainz_release_id = release_id
            elif provider == "discogs":
                album.discogs_release_id = release_id

            album.match_confidence = confidence
            album.match_source = MatchSource.EXISTING

        # Read metadata from all files
        for file_path in self._get_audio_files(album.directory):
            track = MetadataReader.read_track(file_path)
            album.tracks.append(track)

        if not album.tracks:
            logger.warning(f"  No audio files found in: {album.directory}")
            return False

        album.total_tracks = len(album.tracks)
        logger.info(f"  Found {album.total_tracks} tracks")

        # Fingerprint and enrich tracks via MusicBrainz
        fingerprinted_count = 0
        matched_count = 0

        for track in album.tracks:
            # Try to enrich with MusicBrainz (includes fingerprinting)
            result = self.musicbrainz.enrich(track)
            if result:
                matched_count += 1
                if track.fingerprint:
                    fingerprinted_count += 1

        logger.info(f"  Fingerprinted: {fingerprinted_count}/{album.total_tracks}")
        logger.info(f"  Matched: {matched_count}/{album.total_tracks}")

        # Determine canonical identities from the tracks
        self._determine_canonical_identities(album)

        # Search for release candidates (if not already cached)
        if (
            not album.musicbrainz_release_id
            and not album.discogs_release_id
            and self.release_search
        ):
            candidates = self.release_search.search_releases(album)

            if candidates:
                logger.info(f"  Found {len(candidates)} release candidates")

                # Try auto-selection
                best = self.release_search.auto_select_best(candidates)
                if best:
                    logger.info(f"  Auto-selected: {best.title} (score: {best.score:.2f})")
                    if best.provider == "musicbrainz":
                        album.musicbrainz_release_id = best.release_id
                    else:
                        album.discogs_release_id = best.release_id
                    album.match_confidence = best.score
                    album.match_source = MatchSource.FINGERPRINT
                else:
                    # Store candidates for prompt visitor
                    album.extra["release_candidates"] = candidates
                    album.is_uncertain = True
                    logger.info("  Uncertain - will prompt user")
            else:
                logger.warning("  No release candidates found")
                album.is_uncertain = True

        # Check if we have enough information
        if not album.canonical_artist and not album.canonical_composer:
            logger.warning("  Unable to determine artist/composer")
            album.is_uncertain = True

        if not album.canonical_album and not album.canonical_performer:
            logger.warning("  Unable to determine album/performer")
            album.is_uncertain = True

        # Log what we found
        if album.is_classical:
            logger.info(f"  Classical: {album.canonical_composer} / {album.canonical_performer}")
        else:
            logger.info(f"  Popular: {album.canonical_artist} - {album.canonical_album}")

        return True

    def _get_audio_files(self, directory: Path) -> list[Path]:
        """Get all audio files in a directory."""
        extensions = {'.mp3', '.flac', '.m4a', '.ogg', '.opus'}
        files = []

        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in extensions:
                files.append(path)

        return files

    def _determine_canonical_identities(self, album: AlbumInfo) -> None:
        """Determine canonical artist/composer/album from track metadata.

        Uses the canonicalizer to apply name mappings, then picks the most
        common values across all tracks.
        """
        # Count occurrences of each canonical name
        artists: dict[str, int] = {}
        composers: dict[str, int] = {}
        performers: dict[str, int] = {}
        albums: dict[str, int] = {}

        for track in album.tracks:
            # Canonicalize and count artists
            if track.artist:
                base_artist = strip_featuring(track.artist)
                canonical = self.canonicalizer.canonicalize(base_artist, "artist")
                artists[canonical] = artists.get(canonical, 0) + 1

            # Canonicalize and count composers
            if track.composer:
                canonical = self.canonicalizer.canonicalize(track.composer, "composer")
                composers[canonical] = composers.get(canonical, 0) + 1

            # Canonicalize and count performers
            if track.performer:
                canonical = self.canonicalizer.canonicalize(track.performer, "performer")
                performers[canonical] = performers.get(canonical, 0) + 1

            # Albums don't need canonicalization (same within directory)
            if track.album:
                albums[track.album] = albums.get(track.album, 0) + 1

        # Pick most common for each category
        album.canonical_artist = self._most_common(artists)
        album.canonical_composer = self._most_common(composers)
        album.canonical_performer = self._most_common(performers)
        album.canonical_album = self._most_common(albums)

        # For classical music, if we have a composer but no performer,
        # check if album_artist or artist could be the performer
        if album.is_classical and album.canonical_composer and not album.canonical_performer:
            # Try to extract performer from album_artist or artist
            for track in album.tracks:
                if track.album_artist:
                    canonical = self.canonicalizer.canonicalize(track.album_artist, "performer")
                    performers[canonical] = performers.get(canonical, 0) + 1
                elif track.artist and not track.composer:
                    # If artist is set but not composer, artist might be performer
                    canonical = self.canonicalizer.canonicalize(track.artist, "performer")
                    performers[canonical] = performers.get(canonical, 0) + 1

            album.canonical_performer = self._most_common(performers)

    @staticmethod
    def _most_common(counts: dict[str, int]) -> Optional[str]:
        """Get the most common value from a count dictionary."""
        if not counts:
            return None
        return max(counts.items(), key=lambda x: x[1])[0]

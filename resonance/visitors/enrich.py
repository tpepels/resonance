"""EnrichVisitor - Step 3: Enrich metadata from MusicBrainz/Discogs."""

from __future__ import annotations

import logging
from typing import Optional

from ..core.models import AlbumInfo, MatchSource
from ..core.visitor import BaseVisitor
from ..providers.musicbrainz import MusicBrainzClient
from ..providers.discogs import DiscogsClient

logger = logging.getLogger(__name__)


class EnrichVisitor(BaseVisitor):
    """Third visitor: Enrich metadata from external providers.

    This visitor:
    1. Uses MusicBrainz to enrich track metadata (if we have fingerprints)
    2. Falls back to Discogs if MusicBrainz fails
    3. Only updates metadata if confidence is high (>= 0.8)
    4. Updates track.title, track.artist, etc.
    """

    def __init__(
        self,
        musicbrainz: MusicBrainzClient,
        discogs: Optional[DiscogsClient] = None,
        min_confidence: float = 0.8,
    ):
        super().__init__("Enrich")
        self.musicbrainz = musicbrainz
        self.discogs = discogs
        self.min_confidence = min_confidence

    def visit(self, album: AlbumInfo) -> bool:
        """Enrich album metadata.

        Args:
            album: Album to enrich

        Returns:
            True to continue to next visitor
        """
        logger.info(f"Enriching: {album.directory}")

        enriched_count = 0
        mb_count = 0
        dg_count = 0

        # Enrich each track
        for track in album.tracks:
            # Try MusicBrainz first
            result = self.musicbrainz.enrich(track)

            if result and result.score >= self.min_confidence:
                mb_count += 1
                enriched_count += 1
                track.match_source = MatchSource.MUSICBRAINZ
                track.match_confidence = result.score
                logger.debug(f"    MB enriched: {track.path.name} (score: {result.score:.2f})")
                continue

            # Try Discogs as fallback
            if self.discogs:
                result = self.discogs.enrich(track)

                if result and result.score >= self.min_confidence:
                    dg_count += 1
                    enriched_count += 1
                    track.match_source = MatchSource.DISCOGS
                    track.match_confidence = result.score
                    logger.debug(f"    Discogs enriched: {track.path.name} (score: {result.score:.2f})")
                    continue

            # No enrichment possible
            logger.debug(f"    No enrichment: {track.path.name}")

        logger.info(f"  Enriched: {enriched_count}/{len(album.tracks)} "
                   f"(MB: {mb_count}, Discogs: {dg_count})")

        # Update album-level match info
        if enriched_count > 0:
            # Calculate average confidence
            confidences = [
                t.match_confidence for t in album.tracks
                if t.match_confidence is not None
            ]
            if confidences:
                album.match_confidence = sum(confidences) / len(confidences)

            # Set match source based on majority
            if mb_count > dg_count:
                album.match_source = MatchSource.MUSICBRAINZ
            elif dg_count > 0:
                album.match_source = MatchSource.DISCOGS

        return True

"""PromptVisitor - Step 2: Ask user for uncertain matches."""

from __future__ import annotations

import logging

from ..core.models import AlbumInfo, UserSkippedError, MatchSource
from ..core.visitor import BaseVisitor
from ..infrastructure.cache import MetadataCache
from ..services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class PromptVisitor(BaseVisitor):
    """Second visitor: Prompt user for uncertain matches.

    This visitor:
    1. Checks if album.is_uncertain
    2. If uncertain, prompts user with options
    3. User can:
       - Skip (jail the directory)
       - Provide mb:xxx or dg:xxx
       - Skip for now (defer)
    4. Stores user's choice in cache
    """

    def __init__(
        self,
        prompt_service: PromptService,
        cache: MetadataCache,
    ):
        super().__init__("Prompt")
        self.prompt_service = prompt_service
        self.cache = cache

    def visit(self, album: AlbumInfo) -> bool:
        """Prompt for uncertain matches.

        Args:
            album: Album to check

        Returns:
            True to continue, False to stop (if skipped)
        """
        # Skip if already certain
        if not album.is_uncertain:
            logger.debug(f"  Certain, skipping prompt: {album.directory}")
            return True

        # Skip if already has a release decision
        if album.musicbrainz_release_id or album.discogs_release_id:
            logger.debug(f"  Has release ID, skipping prompt: {album.directory}")
            return True

        logger.info(f"Prompting for: {album.directory}")

        # Defer if in non-interactive mode
        if not self.prompt_service.interactive:
            logger.info(f"  Deferring prompt (daemon mode)")
            self.cache.add_deferred_prompt(
                album.directory,
                reason="uncertain_match"
            )
            return False

        # Prompt user
        try:
            result = self.prompt_service.prompt_for_release(album)

            if result:
                provider, release_id = result
                logger.info(f"  User provided: {provider}:{release_id}")

                # Store in album
                if provider == "musicbrainz":
                    album.musicbrainz_release_id = release_id
                elif provider == "discogs":
                    album.discogs_release_id = release_id

                album.match_source = MatchSource.USER_PROVIDED
                album.is_uncertain = False

                # Cache the decision
                self.cache.set_directory_release(
                    album.directory,
                    provider,
                    release_id,
                    confidence=1.0
                )

                return True
            else:
                # User pressed enter - defer for now
                logger.info(f"  User deferred decision")
                self.cache.add_deferred_prompt(
                    album.directory,
                    reason="user_deferred"
                )
                return False

        except UserSkippedError as e:
            # User chose to skip (jail)
            logger.info(f"  User skipped: {e}")
            album.is_skipped = True
            self.cache.add_skipped_directory(
                album.directory,
                reason=str(e)
            )
            return False

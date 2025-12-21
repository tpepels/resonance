"""PromptVisitor - Step 2: Ask user for uncertain matches."""

from __future__ import annotations

import logging

from ..core.models import AlbumInfo, UserSkippedError, MatchSource
from ..core.visitor import BaseVisitor
from ..core.identity import dir_id as compute_dir_id
from ..core.identity import dir_signature
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
        dir_key = album.dir_id
        if dir_key is None and album.tracks:
            signature = dir_signature([track.path for track in album.tracks])
            dir_key = compute_dir_id(signature)
            album.dir_id = dir_key

        # Defer if in non-interactive mode
        if not self.prompt_service.interactive:
            logger.info("  Deferring prompt (daemon mode)")
            if dir_key:
                self.cache.add_deferred_prompt_by_id(
                    dir_key,
                    album.directory,
                    reason="uncertain_match",
                )
            else:
                self.cache.add_deferred_prompt(
                    album.directory,
                    reason="uncertain_match"
                )
            return False

        # Prompt user
        try:
            result = self.prompt_service.prompt_for_release(album)

            if result:
                provider = None
                release_id = None
                confidence = 1.0
                if isinstance(result, str):
                    if ":" in result:
                        provider, release_id = result.split(":", 1)
                elif isinstance(result, tuple):
                    if len(result) >= 2:
                        provider = result[0]
                        release_id = result[1]
                    if len(result) >= 3 and isinstance(result[2], (int, float)):
                        confidence = float(result[2])
                if not provider or not release_id:
                    logger.info("  Unable to parse prompt result; deferring")
                    if dir_key:
                        self.cache.add_deferred_prompt_by_id(
                            dir_key,
                            album.directory,
                            reason="invalid_prompt_result",
                        )
                    else:
                        self.cache.add_deferred_prompt(
                            album.directory,
                            reason="invalid_prompt_result"
                        )
                    return False
                provider_key = provider

                logger.info(f"  User provided: {provider}:{release_id}")

                # Store in album
                if provider_key in ("musicbrainz", "mb"):
                    album.musicbrainz_release_id = release_id
                elif provider_key in ("discogs", "dg"):
                    album.discogs_release_id = release_id

                album.match_source = MatchSource.USER_PROVIDED
                album.is_uncertain = False

                # Cache the decision
                if dir_key:
                    self.cache.set_directory_release_by_id(
                        dir_key,
                        album.directory,
                        provider_key,
                        release_id,
                        confidence=confidence,
                    )
                else:
                    self.cache.set_directory_release(
                        album.directory,
                        provider_key,
                        release_id,
                        confidence=confidence
                    )

                return True
            else:
                # User pressed enter - defer for now
                logger.info("  User deferred decision")
                if dir_key:
                    self.cache.add_deferred_prompt_by_id(
                        dir_key,
                        album.directory,
                        reason="user_deferred",
                    )
                else:
                    self.cache.add_deferred_prompt(
                        album.directory,
                        reason="user_deferred"
                    )
                return False

        except UserSkippedError as e:
            # User chose to skip (jail)
            logger.info(f"  User skipped: {e}")
            album.is_skipped = True
            if dir_key:
                self.cache.add_skipped_directory_by_id(
                    dir_key,
                    album.directory,
                    reason=str(e),
                )
            else:
                self.cache.add_skipped_directory(
                    album.directory,
                    reason=str(e)
                )
            return False

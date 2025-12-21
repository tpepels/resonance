"""Application bootstrap with dependency injection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .core.identity import IdentityCanonicalizer
from .core.visitor import VisitorPipeline
from .infrastructure.cache import MetadataCache
from .infrastructure.scanner import LibraryScanner
from .providers.musicbrainz import MusicBrainzClient
from .providers.discogs import DiscogsClient
from .services.file_service import FileService
from .services.prompt_service import PromptService
from .services.release_search import ReleaseSearchService
import warnings


class ResonanceApp:
    """Main application with dependency injection."""

    def __init__(
        self,
        library_root: Path,
        cache_path: Path,
        acoustid_api_key: Optional[str] = None,
        discogs_token: Optional[str] = None,
        interactive: bool = True,
        dry_run: bool = False,
        delete_nonaudio: bool = False,
        offline: bool = False,
    ):
        """Initialize Resonance application.

        Args:
            library_root: Root directory of music library
            cache_path: Path to SQLite cache database
            acoustid_api_key: AcoustID API key for fingerprinting
            discogs_token: Discogs API token (optional)
            interactive: If True, prompt user for uncertainmatches
            dry_run: If True, don't actually move files
            delete_nonaudio: If True, delete non-audio files during cleanup
        """
        self.library_root = library_root
        self.cache_path = cache_path
        self.interactive = interactive
        self.dry_run = dry_run
        self.delete_nonaudio = delete_nonaudio
        self.offline = offline

        # Initialize infrastructure
        self.cache = MetadataCache(cache_path)

        # Initialize providers
        self.musicbrainz = None
        if acoustid_api_key:
            self.musicbrainz = MusicBrainzClient(
                acoustid_api_key=acoustid_api_key,
                cache=self.cache,
                offline=offline,
            )

        self.discogs = None
        if discogs_token:
            self.discogs = DiscogsClient(
                token=discogs_token,
                cache=self.cache,
                offline=offline,
            )

        # Initialize services
        self.canonicalizer = IdentityCanonicalizer(cache=self.cache)
        self.prompt_service = PromptService(interactive=interactive)
        self.file_service = FileService(
            library_root=library_root,
            dry_run=dry_run,
        )

        # Initialize scanner
        self.scanner = LibraryScanner(
            roots=[library_root],
            extensions={'.mp3', '.flac', '.m4a', '.ogg', '.opus'},
        )

        # Initialize release search service
        self.release_search = None
        if self.musicbrainz:
            self.release_search = ReleaseSearchService(
                musicbrainz=self.musicbrainz,
                discogs=self.discogs,
            )

    def create_pipeline(self, *, allow_legacy: bool = False) -> VisitorPipeline:
        """Create the visitor pipeline.

        Returns:
            VisitorPipeline with all 5 visitors
        """
        if not allow_legacy:
            raise ValueError(
                "V2 visitor pipeline is deprecated; pass allow_legacy=True to use it."
            )
        warnings.warn(
            "V2 visitor pipeline is deprecated; prefer V3 commands.",
            DeprecationWarning,
            stacklevel=2,
        )
        from .visitors import (  # legacy-only import
            IdentifyVisitor,
            PromptVisitor,
            EnrichVisitor,
            OrganizeVisitor,
            CleanupVisitor,
        )
        visitors = []

        # 1. Identify (fingerprinting + canonical names)
        if self.musicbrainz:
            visitors.append(IdentifyVisitor(
                musicbrainz=self.musicbrainz,
                canonicalizer=self.canonicalizer,
                cache=self.cache,
                release_search=self.release_search,
            ))

        # 2. Prompt (user interaction)
        visitors.append(PromptVisitor(
            prompt_service=self.prompt_service,
            cache=self.cache,
        ))

        # 3. Enrich (metadata from providers)
        if self.musicbrainz:
            visitors.append(EnrichVisitor(
                musicbrainz=self.musicbrainz,
                discogs=self.discogs,
            ))

        # 4. Organize (move files)
        visitors.append(OrganizeVisitor(
            file_service=self.file_service,
        ))

        # 5. Cleanup (delete empty dirs)
        visitors.append(CleanupVisitor(
            file_service=self.file_service,
            delete_nonaudio=self.delete_nonaudio,
        ))

        return VisitorPipeline(visitors)

    def close(self) -> None:
        """Clean up resources."""
        if self.cache:
            self.cache.close()

    @classmethod
    def from_env(
        cls,
        library_root: Path,
        cache_path: Path,
        **kwargs,
    ) -> ResonanceApp:
        """Create app with credentials from environment variables.

        Environment variables:
            ACOUSTID_API_KEY: AcoustID API key
            DISCOGS_TOKEN: Discogs API token

        Args:
            library_root: Root directory of music library
            cache_path: Path to cache database
            **kwargs: Additional arguments to pass to __init__

        Returns:
            ResonanceApp instance
        """
        return cls(
            library_root=library_root,
            cache_path=cache_path,
            acoustid_api_key=os.getenv('ACOUSTID_API_KEY'),
            discogs_token=os.getenv('DISCOGS_TOKEN'),
            **kwargs,
        )

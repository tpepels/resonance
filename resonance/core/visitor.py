"""Visitor pattern protocol for processing directories.

This module defines the core Visitor pattern that Resonance uses to process
audio directories. Each visitor implements one step of the processing pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .models import AlbumInfo


class DirectoryVisitor(Protocol):
    """Protocol for visitors that process a directory of audio files.

    Each visitor implements one step of the processing pipeline:
    1. IdentifyVisitor - Fingerprint files, determine canonical artist/album
    2. PromptVisitor - Ask user for uncertain matches
    3. EnrichVisitor - Add metadata from MusicBrainz/Discogs
    4. OrganizeVisitor - Move files to Artist/Album structure
    5. CleanupVisitor - Delete empty source directories

    Visitors can return False to stop processing this directory.
    """

    def visit(self, album: AlbumInfo) -> bool:
        """Process the album.

        Args:
            album: Album information with tracks

        Returns:
            True to continue to next visitor, False to stop processing
        """
        ...


class BaseVisitor(ABC):
    """Base class for concrete visitor implementations.

    Provides common functionality and enforces the visitor interface.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def visit(self, album: AlbumInfo) -> bool:
        """Process the album.

        Args:
            album: Album information with tracks

        Returns:
            True to continue to next visitor, False to stop processing
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"


class VisitorPipeline:
    """Executes a sequence of visitors on an album.

    This is simpler than the plugin-based pipeline in audio-meta.
    Just a straightforward sequence of visitor calls.
    """

    def __init__(self, visitors: list[DirectoryVisitor]):
        self.visitors = visitors

    def process(self, album: AlbumInfo) -> bool:
        """Process an album through all visitors.

        Args:
            album: Album to process

        Returns:
            True if all visitors completed successfully, False if stopped early
        """
        for visitor in self.visitors:
            try:
                should_continue = visitor.visit(album)
                if not should_continue:
                    return False
            except Exception as e:
                print(f"Error in {visitor}: {e}")
                raise

        return True

    def __repr__(self) -> str:
        visitor_names = [v.__class__.__name__ for v in self.visitors]
        return f"VisitorPipeline({', '.join(visitor_names)})"

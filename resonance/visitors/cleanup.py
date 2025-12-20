"""CleanupVisitor - Step 5: Delete empty source directories."""

from __future__ import annotations

import logging

from ..core.models import AlbumInfo
from ..core.visitor import BaseVisitor
from ..services.file_service import FileService

logger = logging.getLogger(__name__)


class CleanupVisitor(BaseVisitor):
    """Fifth visitor: Clean up empty source directories.

    This visitor:
    1. Checks if source directory is empty after file moves
    2. Optionally deletes non-audio files (--delete-nonaudio)
    3. Deletes empty parent directories recursively
    """

    def __init__(
        self,
        file_service: FileService,
        delete_nonaudio: bool = False,
    ):
        super().__init__("Cleanup")
        self.file_service = file_service
        self.delete_nonaudio = delete_nonaudio

    def visit(self, album: AlbumInfo) -> bool:
        """Clean up after organization.

        Args:
            album: Album that was just organized

        Returns:
            True (always continues)
        """
        source_dir = album.source_directory
        if not source_dir:
            logger.debug("  Cleanup skipped: missing source directory")
            return True

        # Skip cleanup if album was not moved.
        try:
            if source_dir.resolve() == album.directory.resolve():
                logger.debug("  Cleanup skipped: source equals destination")
                return True
        except FileNotFoundError:
            # If either path vanished, cleanup will handle it below.
            pass

        logger.info(f"Cleanup: {source_dir}")

        deleted = self.file_service.delete_if_empty(
            source_dir,
            delete_nonaudio=self.delete_nonaudio,
        )
        if not deleted:
            return True

        # Recursively delete empty parent directories up to library root.
        current = source_dir.parent
        while True:
            if current == current.parent:
                break
            if current == self.file_service.library_root:
                break
            if not self.file_service.delete_if_empty(current, delete_nonaudio=False):
                break
            current = current.parent

        return True

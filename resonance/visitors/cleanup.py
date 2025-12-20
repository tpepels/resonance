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
        # Note: album.directory now points to the NEW location after organize
        # We need to track the original source directory separately

        # This is a limitation of the current design - we don't track source dir
        # For now, we'll just log and return
        # TODO: Track original directory in AlbumInfo

        logger.info(f"Cleanup: {album.directory}")
        logger.debug(f"  Cleanup not yet fully implemented (needs source dir tracking)")

        # In a full implementation, we would:
        # 1. Check if source_directory is empty
        # 2. If delete_nonaudio, delete non-audio files
        # 3. Delete source_directory if empty
        # 4. Recursively delete empty parent directories

        return True

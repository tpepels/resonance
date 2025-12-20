"""OrganizeVisitor - Step 4: Move files to final directory structure."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.models import AlbumInfo
from ..core.visitor import BaseVisitor
from ..infrastructure.transaction import Transaction
from ..services.file_service import FileService

logger = logging.getLogger(__name__)


class OrganizeVisitor(BaseVisitor):
    """Fourth visitor: Move files to Artist/Album or Composer/Performer structure.

    This visitor:
    1. Calculates destination path from album.destination_path
    2. Moves all track files to destination
    3. Uses transaction for rollback support
    4. Updates cache with move records
    """

    def __init__(
        self,
        file_service: FileService,
        use_transactions: bool = True,
    ):
        super().__init__("Organize")
        self.file_service = file_service
        self.use_transactions = use_transactions

    def visit(self, album: AlbumInfo) -> bool:
        """Organize album files.

        Args:
            album: Album to organize

        Returns:
            True to continue to next visitor
        """
        logger.info(f"Organizing: {album.directory}")

        # Skip if uncertain or skipped
        if album.is_uncertain:
            logger.info(f"  Skipping: uncertain match")
            return False

        if album.is_skipped:
            logger.info(f"  Skipping: jailed")
            return False

        # Calculate destination
        destination_path = album.destination_path
        if not destination_path:
            logger.warning(f"  Cannot determine destination path")
            return False

        # Make destination absolute within library
        if not destination_path.is_absolute():
            destination_path = self.file_service.library_root / destination_path

        # Sanitize path components
        parts = []
        for part in destination_path.parts:
            if part not in ('/', '\\'):
                parts.append(self.file_service.sanitize_filename(part))

        destination_path = Path(*parts) if parts else destination_path

        logger.info(f"  Destination: {destination_path}")

        # Check if already in correct location
        if album.directory.resolve() == destination_path.resolve():
            logger.info(f"  Already in correct location")
            return True

        # Move files with transaction support
        try:
            if self.use_transactions:
                with Transaction() as txn:
                    self._move_files(album, destination_path, txn)
            else:
                self._move_files(album, destination_path, None)

            logger.info(f"  Moved {len(album.tracks)} tracks")
            return True

        except Exception as e:
            logger.error(f"  Failed to organize: {e}")
            return False

    def _move_files(
        self,
        album: AlbumInfo,
        destination_dir: Path,
        transaction: Transaction | None,
    ) -> None:
        """Move all track files to destination directory.

        Args:
            album: Album with tracks to move
            destination_dir: Destination directory
            transaction: Optional transaction for rollback
        """
        for track in album.tracks:
            new_path = self.file_service.move_track(
                track.path,
                destination_dir,
                transaction
            )

            # Update track path
            track.path = new_path

        # Update album directory
        album.directory = destination_dir

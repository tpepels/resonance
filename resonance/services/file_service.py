"""File operations service (move, copy, delete)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from resonance.core.validation import sanitize_filename

from ..infrastructure.transaction import Transaction


class FileService:
    """Service for safe file operations with transaction support."""

    def __init__(self, library_root: Path, dry_run: bool = False):
        """Initialize file service.

        Args:
            library_root: Root directory for the music library
            dry_run: If True, don't actually move files
        """
        self.library_root = library_root
        self.dry_run = dry_run

    def move_track(
        self,
        source: Path,
        destination_dir: Path,
        transaction: Optional[Transaction] = None,
    ) -> Path:
        """Move a track file to a destination directory.

        Args:
            source: Source file path
            destination_dir: Destination directory (will be created if needed)
            transaction: Optional transaction for rollback support

        Returns:
            Final destination path
        """
        # Construct destination path
        destination = destination_dir / source.name

        # Handle conflicts (add number suffix if needed)
        if destination.exists() and destination != source:
            base = destination.stem
            ext = destination.suffix
            counter = 1

            while destination.exists():
                destination = destination_dir / f"{base}_{counter}{ext}"
                counter += 1

        # Don't move if source and destination are the same
        if source.resolve() == destination.resolve():
            return destination

        if self.dry_run:
            print(f"  [DRY RUN] Would move: {source} -> {destination}")
            return destination

        # Create destination directory
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Move file
        if transaction:
            transaction.move_file(source, destination)
        else:
            shutil.move(str(source), str(destination))

        return destination

    def delete_if_empty(self, directory: Path, delete_nonaudio: bool = False) -> bool:
        """Delete directory if empty (or only contains non-audio files).

        Args:
            directory: Directory to check and potentially delete
            delete_nonaudio: If True, delete non-audio files first

        Returns:
            True if directory was deleted, False otherwise
        """
        if not directory.exists() or not directory.is_dir():
            return False

        # Check if directory is within library_root
        # (safety check to not delete outside library)
        try:
            directory.relative_to(self.library_root)
        except ValueError:
            # Directory is outside library root, don't delete
            return False

        # List contents
        contents = list(directory.iterdir())

        if not contents:
            # Already empty
            if not self.dry_run:
                directory.rmdir()
            return True

        # Check if all files are non-audio
        audio_extensions = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav"}
        has_audio = any(f.is_file() and f.suffix.lower() in audio_extensions for f in contents)

        if has_audio:
            # Has audio files, don't delete
            return False

        if delete_nonaudio:
            # Delete all non-audio files
            for item in contents:
                if self.dry_run:
                    print(f"  [DRY RUN] Would delete: {item}")
                else:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

            # Now delete the directory
            if not self.dry_run:
                directory.rmdir()
            return True

        return False

    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in filenames.

        Args:
            name: String to sanitize

        Returns:
            Sanitized string safe for filenames
        """
        return sanitize_filename(name)

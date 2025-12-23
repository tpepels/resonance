"""Shared layout helpers for deterministic destination paths."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def _apply_component(
    value: Optional[str],
    *,
    sanitize: Callable[[str], str],
    canonicalize_display: Optional[Callable[[str, str], str]] = None,
    category: str,
) -> Optional[str]:
    if not value:
        return None
    display_value = (
        canonicalize_display(value, category) if canonicalize_display is not None else value
    )
    cleaned = sanitize(display_value)
    return cleaned or None


def build_album_folder(
    title: Optional[str],
    *,
    year: Optional[int] = None,
    include_year: bool,
    sanitize: Callable[[str], str],
) -> Optional[str]:
    if not title:
        return None
    if include_year:
        year_str = f"{year:04d}" if year is not None else "0000"
        return sanitize(f"{year_str} - {title}")
    return sanitize(title)


def compute_destination_path(
    *,
    album_title: Optional[str],
    artist: Optional[str],
    composer: Optional[str],
    performer: Optional[str],
    is_classical: bool,
    is_compilation: bool,
    year: Optional[int] = None,
    include_year: bool,
    include_performer_subdir: bool,
    sanitize: Callable[[str], str],
    canonicalize_display: Optional[Callable[[str, str], str]] = None,
) -> Optional[Path]:
    """Compute destination path from normalized display components."""
    album_folder = build_album_folder(
        album_title,
        year=year,
        include_year=include_year,
        sanitize=sanitize,
    )
    artist_value = _apply_component(
        artist,
        sanitize=sanitize,
        canonicalize_display=canonicalize_display,
        category="artist",
    )
    composer_value = _apply_component(
        composer,
        sanitize=sanitize,
        canonicalize_display=canonicalize_display,
        category="composer",
    )
    performer_value = _apply_component(
        performer,
        sanitize=sanitize,
        canonicalize_display=canonicalize_display,
        category="performer",
    )
    various_artists = _apply_component(
        "Various Artists",
        sanitize=sanitize,
        canonicalize_display=canonicalize_display,
        category="artist",
    )

    if is_compilation:
        if not album_folder or not various_artists:
            return None
        return Path(various_artists) / album_folder

    if is_classical:
        if composer_value:
            if album_folder and include_performer_subdir and performer_value:
                return Path(composer_value) / album_folder / performer_value
            if album_folder:
                return Path(composer_value) / album_folder
            return Path(composer_value)
        if performer_value and album_folder:
            return Path(performer_value) / album_folder
        if performer_value:
            return Path(performer_value)
        if album_folder and various_artists:
            return Path(various_artists) / album_folder
        return None

    if artist_value and album_folder:
        return Path(artist_value) / album_folder
    return None

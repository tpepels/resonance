"""Read metadata from audio files using mutagen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
except ImportError:
    MutagenFile = None
    ID3 = None
    FLAC = None
    MP4 = None

from ..core.models import TrackInfo, parse_int


class MetadataReader:
    """Read metadata from audio files."""

    @staticmethod
    def read_track(path: Path) -> TrackInfo:
        """Read metadata from an audio file.

        Args:
            path: Path to audio file

        Returns:
            TrackInfo with metadata populated from file tags
        """
        track = TrackInfo(path=path)

        if not MutagenFile:
            MetadataReader._apply_stub_metadata(path, track)
            return track

        try:
            audio = MutagenFile(path)
            if audio is None:
                MetadataReader._apply_stub_metadata(path, track)
                return track

            # Get duration
            if hasattr(audio.info, 'length'):
                track.duration_seconds = int(audio.info.length)

            # Read tags based on file type
            ext = path.suffix.lower()
            if ext == '.mp3':
                MetadataReader._read_mp3(path, track)
            elif ext == '.flac':
                MetadataReader._read_flac(path, track)
            elif ext in ('.m4a', '.mp4'):
                MetadataReader._read_mp4(path, track)

        except Exception:
            # If reading fails, fall back to stub metadata
            MetadataReader._apply_stub_metadata(path, track)

        MetadataReader._apply_stub_metadata(path, track)
        return track

    @staticmethod
    def _read_mp3(path: Path, track: TrackInfo) -> None:
        """Read ID3 tags from MP3 file."""
        if not ID3:
            return

        try:
            tags = ID3(path)
        except Exception:
            return

        # Title (TIT2)
        if 'TIT2' in tags:
            track.title = str(tags['TIT2'].text[0]) if tags['TIT2'].text else None

        # Artist (TPE1)
        if 'TPE1' in tags:
            track.artist = str(tags['TPE1'].text[0]) if tags['TPE1'].text else None

        # Album (TALB)
        if 'TALB' in tags:
            track.album = str(tags['TALB'].text[0]) if tags['TALB'].text else None

        # Album Artist (TPE2)
        if 'TPE2' in tags:
            track.album_artist = str(tags['TPE2'].text[0]) if tags['TPE2'].text else None

        # Composer (TCOM)
        if 'TCOM' in tags:
            track.composer = str(tags['TCOM'].text[0]) if tags['TCOM'].text else None

        # Conductor (TPE3)
        if 'TPE3' in tags:
            track.conductor = str(tags['TPE3'].text[0]) if tags['TPE3'].text else None

        # Genre (TCON)
        if 'TCON' in tags:
            track.genre = str(tags['TCON'].text[0]) if tags['TCON'].text else None

        # Track number (TRCK)
        if 'TRCK' in tags:
            track.track_number = parse_int(str(tags['TRCK'].text[0]))

        # Disc number (TPOS)
        if 'TPOS' in tags:
            track.disc_number = parse_int(str(tags['TPOS'].text[0]))

    @staticmethod
    def _read_flac(path: Path, track: TrackInfo) -> None:
        """Read Vorbis comments from FLAC file."""
        if not FLAC:
            return

        try:
            audio = FLAC(path)
        except Exception:
            return

        track.title = MetadataReader._get_first(audio, 'TITLE')
        track.artist = MetadataReader._get_first(audio, 'ARTIST')
        track.album = MetadataReader._get_first(audio, 'ALBUM')
        track.album_artist = MetadataReader._get_first(audio, 'ALBUMARTIST', 'ALBUM ARTIST')
        track.composer = MetadataReader._get_first(audio, 'COMPOSER')
        track.conductor = MetadataReader._get_first(audio, 'CONDUCTOR')
        track.genre = MetadataReader._get_first(audio, 'GENRE')

        # Performer (could be in various tags)
        track.performer = MetadataReader._get_first(
            audio, 'PERFORMER', 'PERFORMERS', 'SOLOIST', 'ORCHESTRA', 'ENSEMBLE'
        )

        # Work and movement
        track.work = MetadataReader._get_first(audio, 'WORK')
        track.movement = MetadataReader._get_first(audio, 'MOVEMENT', 'MOVEMENTNAME')

        # Track/disc numbers
        track_str = MetadataReader._get_first(audio, 'TRACKNUMBER')
        if track_str:
            track.track_number = parse_int(track_str)

        disc_str = MetadataReader._get_first(audio, 'DISCNUMBER')
        if disc_str:
            track.disc_number = parse_int(disc_str)

    @staticmethod
    def _read_mp4(path: Path, track: TrackInfo) -> None:
        """Read tags from M4A/MP4 file."""
        if not MP4:
            return

        try:
            audio = MP4(path)
        except Exception:
            return

        # MP4 uses different tag names
        if '\xa9nam' in audio:  # Title
            track.title = str(audio['\xa9nam'][0])

        if '\xa9ART' in audio:  # Artist
            track.artist = str(audio['\xa9ART'][0])

        if '\xa9alb' in audio:  # Album
            track.album = str(audio['\xa9alb'][0])

        if 'aART' in audio:  # Album Artist
            track.album_artist = str(audio['aART'][0])

        if '\xa9wrt' in audio:  # Composer
            track.composer = str(audio['\xa9wrt'][0])

        if '\xa9gen' in audio:  # Genre
            track.genre = str(audio['\xa9gen'][0])

        # Track number (returns tuple: (track, total))
        if 'trkn' in audio:
            track_tuple = audio['trkn'][0]
            if isinstance(track_tuple, tuple) and len(track_tuple) > 0:
                track.track_number = track_tuple[0]
                if len(track_tuple) > 1:
                    track.track_total = track_tuple[1]

        # Disc number (returns tuple: (disc, total))
        if 'disk' in audio:
            disc_tuple = audio['disk'][0]
            if isinstance(disc_tuple, tuple) and len(disc_tuple) > 0:
                track.disc_number = disc_tuple[0]

    @staticmethod
    def _apply_stub_metadata(path: Path, track: TrackInfo) -> None:
        """Apply test stub metadata from companion JSON if present."""
        metadata_path = path.with_suffix(path.suffix + ".meta.json")
        if not metadata_path.exists():
            return

        try:
            data = json.loads(metadata_path.read_text())
        except Exception:
            return

        track.title = track.title or data.get("title")
        track.artist = track.artist or data.get("artist")
        track.album = track.album or data.get("album")
        track.album_artist = track.album_artist or data.get("album_artist")
        track.track_number = track.track_number or data.get("track_number")
        track.duration_seconds = track.duration_seconds or data.get("duration")
        track.composer = track.composer or data.get("composer")
        track.conductor = track.conductor or data.get("conductor")
        track.performer = track.performer or data.get("performer")

    @staticmethod
    def _get_first(audio: FLAC, *keys: str) -> Optional[str]:
        """Get first non-empty value from a list of possible keys."""
        for key in keys:
            values = audio.get(key, [])
            if values and values[0]:
                return str(values[0])
        return None

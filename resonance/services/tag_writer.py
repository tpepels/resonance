"""Tag writer backends for applying TagPatch data."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional, Protocol, Sequence

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TXXX
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
except ImportError:  # pragma: no cover - optional dependency
    MutagenFile = None
    ID3 = None
    TIT2 = None
    TPE1 = None
    TALB = None
    TPE2 = None
    TRCK = None
    TPOS = None
    TXXX = None
    FLAC = None
    MP4 = None


@dataclass(frozen=True)
class TagWriteResult:
    file_path: Path
    tags_set: tuple[str, ...]
    tags_skipped: tuple[str, ...]
    error: Optional[str] = None


@dataclass(frozen=True)
class TagSnapshot:
    """Deterministic snapshot of tag state."""

    tags: tuple[tuple[str, str], ...]

    @classmethod
    def from_tags(cls, tags: dict[str, str]) -> "TagSnapshot":
        return cls(tags=tuple(sorted(tags.items())))


class TagWriter(Protocol):
    """Backend interface for reading and writing tags."""

    def read_tags(self, path: Path) -> dict[str, str]:
        ...

    def apply_patch(
        self, path: Path, set_tags: dict[str, str], allow_overwrite: bool
    ) -> TagWriteResult:
        ...

    def write_tags_exact(self, path: Path, tags: dict[str, str]) -> None:
        ...


TagValue = str | Sequence[str]


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_tag_set(tags: dict[str, TagValue]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in tags.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts = [_collapse_whitespace(str(part)) for part in value if part]
            joined = "; ".join(part for part in parts if part)
            if joined:
                normalized[key] = joined
            continue
        normalized[key] = _collapse_whitespace(str(value))
    return normalized


def _mp4_mapping() -> dict[str, str]:
    return {
        "title": "\xa9nam",
        "artist": "\xa9ART",
        "album": "\xa9alb",
        "albumartist": "aART",
        "tracknumber": "trkn",
        "discnumber": "disk",
        "musicbrainz_albumid": "----:com.apple.iTunes:MusicBrainz Album Id",
        "musicbrainz_recordingid": "----:com.apple.iTunes:MusicBrainz Track Id",
    }


def format_tag_keys(ext: str) -> tuple[str, ...]:
    ext = ext.lower().lstrip(".")
    if ext == "mp3":
        keys = set(MutagenTagWriter._MP3_KEYS.keys()) | set(MutagenTagWriter._MP3_MB_DESCS.keys())
        return tuple(sorted(keys))
    if ext in ("m4a", "mp4"):
        return tuple(sorted(_mp4_mapping().keys()))
    return ()


def get_tag_writer(backend: str) -> TagWriter:
    if backend == "meta-json":
        return MetaJsonTagWriter()
    if backend == "mutagen":
        return MutagenTagWriter()
    raise ValueError(f"Unknown tag writer backend: {backend}")


class MetaJsonTagWriter:
    """Tag writer that stores tags in .meta.json sidecars (tests)."""

    def read_tags(self, path: Path) -> dict[str, str]:
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            return {}
        data = json.loads(meta_path.read_text())
        return dict(data.get("tags", {}))

    def apply_patch(
        self, path: Path, set_tags: dict[str, str], allow_overwrite: bool
    ) -> TagWriteResult:
        normalized = normalize_tag_set(set_tags)
        existing = self.read_tags(path)
        tags_set: list[str] = []
        tags_skipped: list[str] = []
        for key in sorted(normalized.keys()):
            value = normalized[key]
            if not allow_overwrite and existing.get(key):
                tags_skipped.append(key)
                continue
            existing[key] = value
            tags_set.append(key)
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({"tags": existing}, indent=2, sort_keys=True))
        return TagWriteResult(
            file_path=path,
            tags_set=tuple(tags_set),
            tags_skipped=tuple(tags_skipped),
        )

    def write_tags_exact(self, path: Path, tags: dict[str, str]) -> None:
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = normalize_tag_set(tags)
        meta_path.write_text(json.dumps({"tags": dict(normalized)}, indent=2, sort_keys=True))


class MutagenTagWriter:
    """Tag writer backed by mutagen for real audio files."""

    _MP3_KEYS = {
        "title": TIT2,
        "artist": TPE1,
        "album": TALB,
        "albumartist": TPE2,
        "tracknumber": TRCK,
        "discnumber": TPOS,
    }
    _MP3_MB_DESCS = {
        "musicbrainz_albumid": "MusicBrainz Album Id",
        "musicbrainz_recordingid": "MusicBrainz Recording Id",
    }

    def _require_mutagen(self) -> None:
        if MutagenFile is None:
            raise RuntimeError("mutagen is not available")

    def read_tags(self, path: Path) -> dict[str, str]:
        self._require_mutagen()
        ext = path.suffix.lower()
        if ext not in (".mp3", ".flac", ".m4a", ".mp4"):
            raise ValueError(f"Unsupported audio format: {ext}")
        if ext == ".mp3":
            tags: dict[str, str] = {}
            try:
                id3 = ID3(path)
            except Exception:
                return {}
            for key, frame in self._MP3_KEYS.items():
                if frame and frame.__name__ in id3:
                    value = id3.get(frame.__name__).text[0]
                    tags[key] = str(value)
            for frame in id3.getall("TXXX"):
                if frame.desc in self._MP3_MB_DESCS.values():
                    for key, desc in self._MP3_MB_DESCS.items():
                        if frame.desc == desc and frame.text:
                            tags[key] = str(frame.text[0])
            return tags
        audio = MutagenFile(path)
        if audio is None or audio.tags is None:
            return {}
        if ext == ".flac" and isinstance(audio, FLAC):
            return {k.lower(): v[0] for k, v in audio.tags.items() if v}
        if ext in (".m4a", ".mp4") and isinstance(audio, MP4):
            tags: dict[str, str] = {}
            for key, mp4_key in _mp4_mapping().items():
                if mp4_key in audio.tags:
                    value = audio.tags[mp4_key][0]
                    if isinstance(value, tuple):
                        value = value[0]
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="ignore")
                    tags[key] = str(value)
            return tags
        return {}

    def apply_patch(
        self, path: Path, set_tags: dict[str, str], allow_overwrite: bool
    ) -> TagWriteResult:
        self._require_mutagen()
        normalized = normalize_tag_set(set_tags)
        existing = self.read_tags(path)
        tags_set: list[str] = []
        tags_skipped: list[str] = []
        for key in sorted(normalized.keys()):
            value = normalized[key]
            if not allow_overwrite and existing.get(key):
                tags_skipped.append(key)
                continue
            existing[key] = value
            tags_set.append(key)
        ext = path.suffix.lower()
        if ext == ".mp3":
            id3 = ID3()
            for key, frame in self._MP3_KEYS.items():
                if key in existing and frame:
                    id3.add(frame(encoding=3, text=str(existing[key])))
            for key, desc in self._MP3_MB_DESCS.items():
                if key in existing:
                    id3.add(TXXX(encoding=3, desc=desc, text=str(existing[key])))
            id3.save(path)
        elif ext == ".flac":
            audio = FLAC(path)
            for key, value in existing.items():
                audio[key.upper()] = str(value)
            audio.save()
        elif ext in (".m4a", ".mp4"):
            audio = MP4(path)
            for key, mp4_key in _mp4_mapping().items():
                if key in existing:
                    audio.tags[mp4_key] = [existing[key]]
            audio.save()
        else:
            raise ValueError(f"Unsupported audio format: {ext}")
        supported_keys: set[str]
        if ext == ".mp3":
            supported_keys = set(self._MP3_KEYS.keys()) | set(self._MP3_MB_DESCS.keys())
        elif ext in (".m4a", ".mp4"):
            supported_keys = {
                "title",
                "artist",
                "album",
                "albumartist",
                "tracknumber",
                "discnumber",
                "musicbrainz_albumid",
                "musicbrainz_recordingid",
            }
        else:
            supported_keys = set(set_tags.keys())
        readback = self.read_tags(path)
        mismatched = sorted(
            key for key in tags_set
            if key in supported_keys and readback.get(key) != set_tags[key]
        )
        if mismatched:
            keys = ", ".join(mismatched)
            raise ValueError(f"Tag write verification failed for {path}: {keys}")
        return TagWriteResult(
            file_path=path,
            tags_set=tuple(tags_set),
            tags_skipped=tuple(tags_skipped),
        )

    def write_tags_exact(self, path: Path, tags: dict[str, str]) -> None:
        self._require_mutagen()
        ext = path.suffix.lower()
        if ext == ".mp3":
            id3 = ID3()
            for key, frame in self._MP3_KEYS.items():
                if key in tags and frame:
                    id3.add(frame(encoding=3, text=str(tags[key])))
            id3.save(path)
            return
        if ext == ".flac":
            audio = FLAC(path)
            audio.clear()
            for key, value in tags.items():
                audio[key.upper()] = str(value)
            audio.save()
            return
        if ext in (".m4a", ".mp4"):
            audio = MP4(path)
            audio.tags.clear()
            for key, mp4_key in _mp4_mapping().items():
                if key in tags:
                    audio.tags[mp4_key] = [tags[key]]
            audio.save()
            return
        raise ValueError(f"Unsupported audio format: {ext}")

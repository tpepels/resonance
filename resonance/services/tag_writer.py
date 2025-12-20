"""Tag writer backends for applying TagPatch data."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional, Protocol

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS
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
        existing = self.read_tags(path)
        tags_set: list[str] = []
        tags_skipped: list[str] = []
        for key in sorted(set_tags.keys()):
            value = set_tags[key]
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

    def _require_mutagen(self) -> None:
        if MutagenFile is None:
            raise RuntimeError("mutagen is not available")

    def read_tags(self, path: Path) -> dict[str, str]:
        self._require_mutagen()
        ext = path.suffix.lower()
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
            return tags
        audio = MutagenFile(path)
        if audio is None or audio.tags is None:
            return {}
        if ext == ".flac" and isinstance(audio, FLAC):
            return {k.lower(): v[0] for k, v in audio.tags.items() if v}
        if ext in (".m4a", ".mp4") and isinstance(audio, MP4):
            tags: dict[str, str] = {}
            mapping = {
                "title": "\xa9nam",
                "artist": "\xa9ART",
                "album": "\xa9alb",
                "albumartist": "aART",
                "tracknumber": "trkn",
                "discnumber": "disk",
            }
            for key, mp4_key in mapping.items():
                if mp4_key in audio.tags:
                    value = audio.tags[mp4_key][0]
                    if isinstance(value, tuple):
                        value = value[0]
                    tags[key] = str(value)
            return tags
        raise ValueError(f"Unsupported audio format: {ext}")

    def apply_patch(
        self, path: Path, set_tags: dict[str, str], allow_overwrite: bool
    ) -> TagWriteResult:
        self._require_mutagen()
        existing = self.read_tags(path)
        tags_set: list[str] = []
        tags_skipped: list[str] = []
        for key in sorted(set_tags.keys()):
            value = set_tags[key]
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
            id3.save(path)
        elif ext == ".flac":
            audio = FLAC(path)
            for key, value in existing.items():
                audio[key.upper()] = str(value)
            audio.save()
        elif ext in (".m4a", ".mp4"):
            audio = MP4(path)
            mapping = {
                "title": "\xa9nam",
                "artist": "\xa9ART",
                "album": "\xa9alb",
                "albumartist": "aART",
                "tracknumber": "trkn",
                "discnumber": "disk",
            }
            for key, mp4_key in mapping.items():
                if key in existing:
                    audio.tags[mp4_key] = [existing[key]]
            audio.save()
        else:
            raise ValueError(f"Unsupported audio format: {ext}")
        return TagWriteResult(
            file_path=path,
            tags_set=tuple(tags_set),
            tags_skipped=tuple(tags_skipped),
        )

"""Golden scenario fixtures for deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fs import AudioStubSpec, build_album_dir


@dataclass(frozen=True)
class GoldenScenario:
    """Defines a golden scenario fixture."""
    name: str
    description: str
    input_dir: Path
    audio_specs: list[AudioStubSpec]
    non_audio_files: list[str]
    expected: dict[str, Any]


SCENARIO_DEFS: dict[str, dict[str, Any]] = {
    "pop_certain": {
        "description": "All fingerprints match a single release.",
        "audio_specs": [
            AudioStubSpec("01 - Opening.flac", "fp-pop-001", duration_seconds=210),
            AudioStubSpec("02 - Chorus.flac", "fp-pop-002", duration_seconds=198),
            AudioStubSpec("03 - Finale.flac", "fp-pop-003", duration_seconds=242),
        ],
        "non_audio_files": [],
        "expected": {"tier": "CERTAIN", "track_count": 3},
    },
    "pop_probable": {
        "description": "One missing or weak fingerprint in otherwise consistent release.",
        "audio_specs": [
            AudioStubSpec("01 - Intro.flac", "fp-pop-101", duration_seconds=120),
            AudioStubSpec("02 - Single.flac", "fp-pop-102", duration_seconds=205),
            AudioStubSpec("03 - Ballad.flac", "fp-pop-103", duration_seconds=233),
            AudioStubSpec("04 - Interlude.flac", "fp-pop-missing", duration_seconds=95),
        ],
        "non_audio_files": [],
        "expected": {"tier": "PROBABLE", "missing_fingerprint_count": 1},
    },
    "compilation": {
        "description": "Compilation album with various artists.",
        "audio_specs": [
            AudioStubSpec(
                "01 - Artist A - Track One.flac",
                "fp-comp-001",
                duration_seconds=201,
                tags={"artist": "Artist A", "album_artist": "Various Artists"},
            ),
            AudioStubSpec(
                "02 - Artist B - Track Two.flac",
                "fp-comp-002",
                duration_seconds=189,
                tags={"artist": "Artist B", "album_artist": "Various Artists"},
            ),
            AudioStubSpec(
                "03 - Artist C - Track Three.flac",
                "fp-comp-003",
                duration_seconds=214,
                tags={"artist": "Artist C", "album_artist": "Various Artists"},
            ),
        ],
        "non_audio_files": [],
        "expected": {"compilation": True},
    },
    "classical_single_composer": {
        "description": "Classical album with a single reliable composer.",
        "audio_specs": [
            AudioStubSpec(
                "01 - Aria.flac",
                "fp-classical-001",
                duration_seconds=305,
                tags={"composer": "J.S. Bach"},
            ),
            AudioStubSpec(
                "02 - Variation I.flac",
                "fp-classical-002",
                duration_seconds=277,
                tags={"composer": "J.S. Bach"},
            ),
        ],
        "non_audio_files": [],
        "expected": {"composer": "J.S. Bach", "track_count": 2},
    },
    "classical_mixed_composer": {
        "description": "Classical album with multiple composers.",
        "audio_specs": [
            AudioStubSpec(
                "01 - Symphony.flac",
                "fp-classical-101",
                duration_seconds=412,
                tags={"composer": "Mozart"},
            ),
            AudioStubSpec(
                "02 - Concerto.flac",
                "fp-classical-102",
                duration_seconds=389,
                tags={"composer": "Bach"},
            ),
        ],
        "non_audio_files": [],
        "expected": {"composer": "mixed"},
    },
    "mixed_release_in_one_dir": {
        "description": "Conflicting evidence points to multiple releases.",
        "audio_specs": [
            AudioStubSpec("01 - Release A.flac", "fp-mix-a-001", duration_seconds=202),
            AudioStubSpec("02 - Release A.flac", "fp-mix-a-002", duration_seconds=198),
            AudioStubSpec("03 - Release B.flac", "fp-mix-b-001", duration_seconds=207),
            AudioStubSpec("04 - Release B.flac", "fp-mix-b-002", duration_seconds=211),
        ],
        "non_audio_files": [],
        "expected": {"tier": "UNSURE", "multi_release": True},
    },
    "non_audio_present": {
        "description": "Album directory contains cover art and supplemental files.",
        "audio_specs": [
            AudioStubSpec("01 - Track One.flac", "fp-non-001", duration_seconds=188),
            AudioStubSpec("02 - Track Two.flac", "fp-non-002", duration_seconds=201),
        ],
        "non_audio_files": [
            "cover.jpg",
            "booklet.pdf",
            "rip.log",
            "album.cue",
            "notes.txt",
        ],
        "expected": {"non_audio_count": 5},
    },
    "target_exists_conflict": {
        "description": "Target directory exists and may cause conflicts.",
        "audio_specs": [
            AudioStubSpec("01 - Track A.flac", "fp-conf-001", duration_seconds=176),
            AudioStubSpec("02 - Track B.flac", "fp-conf-002", duration_seconds=193),
        ],
        "non_audio_files": [],
        "expected": {"target_exists": True},
    },
}


def build_golden_scenario(base_dir: Path, name: str) -> GoldenScenario:
    """Create a golden scenario fixture by name."""
    if name not in SCENARIO_DEFS:
        raise KeyError(f"Unknown golden scenario: {name}")

    definition = SCENARIO_DEFS[name]
    album = build_album_dir(
        base_dir / "golden",
        name,
        definition["audio_specs"],
        definition["non_audio_files"],
    )

    return GoldenScenario(
        name=name,
        description=definition["description"],
        input_dir=album.path,
        audio_specs=definition["audio_specs"],
        non_audio_files=definition["non_audio_files"],
        expected=definition["expected"],
    )

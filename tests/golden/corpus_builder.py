"""Deterministic golden corpus builder for V3 invariants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.helpers.fs import AudioStubSpec, AlbumFixture, build_album_dir


@dataclass(frozen=True)
class CorpusScenario:
    name: str
    description: str
    audio_specs: list[AudioStubSpec]
    non_audio_files: list[str]


def _spec(
    filename: str,
    fingerprint_id: str,
    duration: int,
    tags: dict[str, Any],
) -> AudioStubSpec:
    return AudioStubSpec(
        filename=filename,
        fingerprint_id=fingerprint_id,
        duration_seconds=duration,
        tags=tags,
    )


def scenarios() -> list[CorpusScenario]:
    """Return the deterministic golden corpus scenario definitions."""
    return [
        CorpusScenario(
            name="standard_album",
            description="Standard album with 10 tracks.",
            audio_specs=[
                _spec(
                    f"{index:02d} - Track {index}.flac",
                    f"fp-std-{index:02d}",
                    180 + index,
                    {
                        "title": f"Track {index}",
                        "artist": "Artist A",
                        "album": "Standard Album",
                        "album_artist": "Artist A",
                        "track_number": index,
                    },
                )
                for index in range(1, 11)
            ],
            non_audio_files=["cover.jpg", "booklet.pdf", "rip.log", "album.cue"],
        ),
        CorpusScenario(
            name="multi_disc",
            description="Two-disc album with disc numbers.",
            audio_specs=[
                _spec(
                    f"D{disc}-{track:02d} - Track {disc}-{track}.flac",
                    f"fp-md-{disc}-{track:02d}",
                    200 + track,
                    {
                        "title": f"Track {disc}-{track}",
                        "artist": "Artist B",
                        "album": "Multi Disc Album",
                        "album_artist": "Artist B",
                        "track_number": track,
                        "disc_number": disc,
                    },
                )
                for disc in (1, 2)
                for track in range(1, 6)
            ],
            non_audio_files=["cover.jpg"],
        ),
        CorpusScenario(
            name="compilation",
            description="Compilation album with Various Artists.",
            audio_specs=[
                _spec(
                    f"{index:02d} - Artist {index} - Track {index}.flac",
                    f"fp-comp-{index:02d}",
                    170 + index,
                    {
                        "title": f"Track {index}",
                        "artist": f"Artist {index}",
                        "album": "Compilation Album",
                        "album_artist": "Various Artists",
                        "track_number": index,
                    },
                )
                for index in range(1, 9)
            ],
            non_audio_files=["cover.jpg", "notes.txt"],
        ),
        CorpusScenario(
            name="name_variants",
            description="Name variants and punctuation/diacritics.",
            audio_specs=[
                _spec(
                    "01 - AC DC - Track.flac",
                    "fp-nv-01",
                    181,
                    {
                        "title": "Track",
                        "artist": "AC/DC",
                        "album": "Name Variants",
                        "album_artist": "AC/DC",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Bjork - Track.flac",
                    "fp-nv-02",
                    182,
                    {
                        "title": "Track",
                        "artist": "Björk",
                        "album": "Name Variants",
                        "album_artist": "Björk",
                        "track_number": 2,
                    },
                ),
                _spec(
                    "03 - Alt J - Track.flac",
                    "fp-nv-03",
                    183,
                    {
                        "title": "Track",
                        "artist": "Alt-J",
                        "album": "Name Variants",
                        "album_artist": "Alt-J",
                        "track_number": 3,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="classical",
            description="Classical work with composer and movement titles.",
            audio_specs=[
                _spec(
                    "01 - Movement I.flac",
                    "fp-classical-01",
                    420,
                    {
                        "title": "Movement I",
                        "composer": "J.S. Bach",
                        "performer": "Performer A",
                        "album": "Classical Work",
                        "track_number": 1,
                        "disc_number": 1,
                    },
                ),
                _spec(
                    "02 - Movement II.flac",
                    "fp-classical-02",
                    410,
                    {
                        "title": "Movement II",
                        "composer": "J.S. Bach",
                        "performer": "Performer A",
                        "album": "Classical Work",
                        "track_number": 2,
                        "disc_number": 1,
                    },
                ),
            ],
            non_audio_files=["cover.jpg", "booklet.pdf"],
        ),
        CorpusScenario(
            name="extras_only",
            description="Extras-heavy album with cover/booklet/cue/log.",
            audio_specs=[
                _spec(
                    "01 - Track A.flac",
                    "fp-extra-01",
                    205,
                    {
                        "title": "Track A",
                        "artist": "Artist C",
                        "album": "Extras Album",
                        "album_artist": "Artist C",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track B.flac",
                    "fp-extra-02",
                    199,
                    {
                        "title": "Track B",
                        "artist": "Artist C",
                        "album": "Extras Album",
                        "album_artist": "Artist C",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=["cover.jpg", "booklet.pdf", "rip.log", "album.cue"],
        ),
        CorpusScenario(
            name="single_track",
            description="Single-track release.",
            audio_specs=[
                _spec(
                    "01 - Single Track.flac",
                    "fp-single-01",
                    215,
                    {
                        "title": "Single Track",
                        "artist": "Artist D",
                        "album": "Standalone Single",
                        "album_artist": "Artist D",
                        "track_number": 1,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="mixed_media",
            description="Album with audio plus a video extra.",
            audio_specs=[
                _spec(
                    "01 - Track One.flac",
                    "fp-mixed-01",
                    201,
                    {
                        "title": "Track One",
                        "artist": "Artist E",
                        "album": "Mixed Media Album",
                        "album_artist": "Artist E",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track Two.flac",
                    "fp-mixed-02",
                    198,
                    {
                        "title": "Track Two",
                        "artist": "Artist E",
                        "album": "Mixed Media Album",
                        "album_artist": "Artist E",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=["bonus_video.mp4", "cover.jpg"],
        ),
        CorpusScenario(
            name="multi_composer",
            description="Classical compilation with multiple composers.",
            audio_specs=[
                _spec(
                    "01 - Symphony Movement.flac",
                    "fp-mc-01",
                    401,
                    {
                        "title": "Symphony Movement",
                        "composer": "L. van Beethoven",
                        "performer": "Orchestra A",
                        "album": "Classical Mix",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Concerto Movement.flac",
                    "fp-mc-02",
                    389,
                    {
                        "title": "Concerto Movement",
                        "composer": "W.A. Mozart",
                        "performer": "Orchestra A",
                        "album": "Classical Mix",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=["cover.jpg"],
        ),
        CorpusScenario(
            name="long_titles",
            description="Very long movement titles requiring truncation.",
            audio_specs=[
                _spec(
                    "01 - Long Title.flac",
                    "fp-long-01",
                    312,
                    {
                        "title": (
                            "Piano Concerto No. 23 in A Major, K. 488: II. "
                            "Adagio in F-sharp Minor (Soloist Name; Orchestra Name; "
                            "Conductor Name) with additional descriptive text to "
                            "exceed typical filesystem limits and enforce deterministic "
                            "truncation behavior in filenames"
                        ),
                        "artist": "Soloist Name",
                        "album": "Long Title Album",
                        "album_artist": "Orchestra Name",
                        "track_number": 1,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="renamed_mid_processing",
            description="Album folder renamed after planning.",
            audio_specs=[
                _spec(
                    "01 - Track A.flac",
                    "fp-rename-01",
                    180,
                    {
                        "title": "Track A",
                        "artist": "Artist F",
                        "album": "Rename Album",
                        "album_artist": "Artist F",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track B.flac",
                    "fp-rename-02",
                    182,
                    {
                        "title": "Track B",
                        "artist": "Artist F",
                        "album": "Rename Album",
                        "album_artist": "Artist F",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="missing_middle_tracks",
            description="Album with missing middle tracks.",
            audio_specs=[
                _spec(
                    "01 - Track 1.flac",
                    "fp-gap-01",
                    201,
                    {
                        "title": "Track 1",
                        "artist": "Artist G",
                        "album": "Gapped Album",
                        "album_artist": "Artist G",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track 2.flac",
                    "fp-gap-02",
                    202,
                    {
                        "title": "Track 2",
                        "artist": "Artist G",
                        "album": "Gapped Album",
                        "album_artist": "Artist G",
                        "track_number": 2,
                    },
                ),
                _spec(
                    "05 - Track 5.flac",
                    "fp-gap-05",
                    205,
                    {
                        "title": "Track 5",
                        "artist": "Artist G",
                        "album": "Gapped Album",
                        "album_artist": "Artist G",
                        "track_number": 5,
                    },
                ),
                _spec(
                    "06 - Track 6.flac",
                    "fp-gap-06",
                    206,
                    {
                        "title": "Track 6",
                        "artist": "Artist G",
                        "album": "Gapped Album",
                        "album_artist": "Artist G",
                        "track_number": 6,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="case_only_rename",
            description="Case-only rename scenario for destination paths.",
            audio_specs=[
                _spec(
                    "01 - Track A.flac",
                    "fp-case-01",
                    190,
                    {
                        "title": "Track A",
                        "artist": "Artist H",
                        "album": "Case Album",
                        "album_artist": "Artist H",
                        "track_number": 1,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="interrupted_apply",
            description="Apply interrupted mid-move.",
            audio_specs=[
                _spec(
                    "01 - Track A.flac",
                    "fp-crash-01",
                    180,
                    {
                        "title": "Track A",
                        "artist": "Artist I",
                        "album": "Crash Album",
                        "album_artist": "Artist I",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track B.flac",
                    "fp-crash-02",
                    181,
                    {
                        "title": "Track B",
                        "artist": "Artist I",
                        "album": "Crash Album",
                        "album_artist": "Artist I",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="opus_normalization",
            description="Opus number formatting variants.",
            audio_specs=[
                _spec(
                    "01 - Op. 27 No. 2.flac",
                    "fp-op-01",
                    420,
                    {
                        "title": "Piano Sonata No. 14 in C-sharp Minor, Op. 27 No. 2 'Moonlight': I. Adagio sostenuto",
                        "composer": "Ludwig van Beethoven",
                        "performer": "Wilhelm Kempff",
                        "album": "Beethoven Piano Sonatas",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - op.27, no.2.flac",
                    "fp-op-02",
                    200,
                    {
                        "title": "Piano Sonata in C-sharp Minor, op.27, no.2: II. Allegretto",
                        "composer": "Beethoven",
                        "performer": "Wilhelm Kempff",
                        "album": "Beethoven Piano Sonatas",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="conductor_vs_performer",
            description="Piano concerto with soloist, orchestra, and conductor.",
            audio_specs=[
                _spec(
                    "01 - Mvt 1.flac",
                    "fp-cvp-01",
                    450,
                    {
                        "title": "Piano Concerto No. 21 in C Major, K. 467: I. Allegro maestoso",
                        "composer": "Wolfgang Amadeus Mozart",
                        "performer": "Mitsuko Uchida",
                        "album_artist": "English Chamber Orchestra",
                        "conductor": "Jeffrey Tate",
                        "album": "Mozart Piano Concertos",
                        "track_number": 1,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="multi_performer_work",
            description="Same work, different performers per movement.",
            audio_specs=[
                _spec(
                    "01 - Mvt 1 Argerich.flac",
                    "fp-mpw-01",
                    380,
                    {
                        "title": "Piano Concerto No. 2: I. Allegro non troppo",
                        "composer": "Brahms",
                        "performer": "Martha Argerich",
                        "conductor": "Claudio Abbado",
                        "album": "Brahms Piano Concertos - Various Soloists",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Mvt 2 Barenboim.flac",
                    "fp-mpw-02",
                    270,
                    {
                        "title": "Piano Concerto No. 2: II. Andante",
                        "composer": "Brahms",
                        "performer": "Daniel Barenboim",
                        "conductor": "Claudio Abbado",
                        "album": "Brahms Piano Concertos - Various Soloists",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="catalog_variants",
            description="Catalog numbering variants (BWV, K.).",
            audio_specs=[
                _spec(
                    "01 - BWV 1006.flac",
                    "fp-cat-01",
                    320,
                    {
                        "title": "Partita No. 3 in E Major, BWV 1006: Preludio",
                        "composer": "J.S. Bach",
                        "performer": "Hilary Hahn",
                        "album": "Bach Solo Works",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - K.525.flac",
                    "fp-cat-02",
                    290,
                    {
                        "title": "Eine kleine Nachtmusik, K. 525: I. Allegro",
                        "composer": "W.A. Mozart",
                        "performer": "Vienna Philharmonic",
                        "album": "Mozart Serenades",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="partial_opera",
            description="Opera excerpts with non-contiguous scenes.",
            audio_specs=[
                _spec(
                    "01 - Act II Scene 3.flac",
                    "fp-opera-01",
                    480,
                    {
                        "title": "La Boheme: Act II, Scene 3 - Quando m'en vo'",
                        "composer": "Giacomo Puccini",
                        "performer": "Mirella Freni",
                        "conductor": "Herbert von Karajan",
                        "album": "Puccini Opera Highlights",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Act IV Scene 2.flac",
                    "fp-opera-02",
                    520,
                    {
                        "title": "La Boheme: Act IV, Scene 2 - Vecchia zimarra",
                        "composer": "Giacomo Puccini",
                        "performer": "Nicolai Ghiaurov",
                        "conductor": "Herbert von Karajan",
                        "album": "Puccini Opera Highlights",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="partial_tags",
            description="Tracks with missing artist/album tags.",
            audio_specs=[
                _spec(
                    "01 - Track.flac",
                    "fp-pt-01",
                    180,
                    {
                        "title": "Track 1",
                        "artist": "Artist J",
                        "album": "Partial Tags Album",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Track.flac",
                    "fp-pt-02",
                    182,
                    {
                        "title": "Track 2",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="duplicate_files",
            description="Same track copied with different filenames.",
            audio_specs=[
                _spec(
                    "01 - Track A.flac",
                    "fp-dup-01",
                    180,
                    {
                        "title": "Track A",
                        "artist": "Artist K",
                        "album": "Duplicate Files",
                        "album_artist": "Artist K",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "01 - Track A (copy).flac",
                    "fp-dup-01",
                    180,
                    {
                        "title": "Track A",
                        "artist": "Artist K",
                        "album": "Duplicate Files",
                        "album_artist": "Artist K",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="remaster_vs_original",
            description="Same album with remaster year tags.",
            audio_specs=[
                _spec(
                    "01 - Track 1.flac",
                    "fp-rem-01",
                    180,
                    {
                        "title": "Track 1",
                        "artist": "Artist L",
                        "album": "Remaster Album (2023 Remaster)",
                        "album_artist": "Artist L",
                        "track_number": 1,
                        "date": "2023",
                    },
                ),
                _spec(
                    "02 - Track 2.flac",
                    "fp-rem-02",
                    181,
                    {
                        "title": "Track 2",
                        "artist": "Artist L",
                        "album": "Remaster Album (2023 Remaster)",
                        "album_artist": "Artist L",
                        "track_number": 2,
                        "date": "2023",
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="non_audio_only",
            description="Directory with no audio files.",
            audio_specs=[],
            non_audio_files=["cover.jpg", "album.cue", "rip.log", "notes.txt"],
        ),
        CorpusScenario(
            name="hidden_track",
            description="Album with track 0 and track 99.",
            audio_specs=[
                _spec(
                    "00 - Hidden Intro.flac",
                    "fp-hidden-00",
                    15,
                    {
                        "title": "Hidden Intro",
                        "artist": "Artist M",
                        "album": "Hidden Track Album",
                        "album_artist": "Artist M",
                        "track_number": 0,
                    },
                ),
                _spec(
                    "01 - Track 1.flac",
                    "fp-hidden-01",
                    200,
                    {
                        "title": "Track 1",
                        "artist": "Artist M",
                        "album": "Hidden Track Album",
                        "album_artist": "Artist M",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "99 - Secret Track.flac",
                    "fp-hidden-99",
                    120,
                    {
                        "title": "Secret Track",
                        "artist": "Artist M",
                        "album": "Hidden Track Album",
                        "album_artist": "Artist M",
                        "track_number": 99,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="unicode_normalization",
            description="Unicode NFC vs NFD normalization in tags.",
            audio_specs=[
                _spec(
                    "01 - Cafe.flac",
                    "fp-unicode-01",
                    180,
                    {
                        "title": "Café",
                        "artist": "Artist N",
                        "album": "Unicode Album",
                        "album_artist": "Artist N",
                        "track_number": 1,
                    },
                ),
                _spec(
                    "02 - Cafe-alt.flac",
                    "fp-unicode-02",
                    181,
                    {
                        "title": "Cafe\u0301",
                        "artist": "Artist N",
                        "album": "Unicode Album",
                        "album_artist": "Artist N",
                        "track_number": 2,
                    },
                ),
            ],
            non_audio_files=[],
        ),
        CorpusScenario(
            name="invalid_year",
            description="Invalid year tags that should be sanitized.",
            audio_specs=[
                _spec(
                    "01 - Track 1.flac",
                    "fp-year-01",
                    180,
                    {
                        "title": "Track 1",
                        "artist": "Artist O",
                        "album": "Invalid Year Album",
                        "album_artist": "Artist O",
                        "track_number": 1,
                        "date": "0000",
                    },
                ),
                _spec(
                    "02 - Track 2.flac",
                    "fp-year-02",
                    181,
                    {
                        "title": "Track 2",
                        "artist": "Artist O",
                        "album": "Invalid Year Album",
                        "album_artist": "Artist O",
                        "track_number": 2,
                        "date": "UNKNOWN",
                    },
                ),
            ],
            non_audio_files=[],
        ),
    ]


def build_corpus(base_dir: Path) -> dict[str, AlbumFixture]:
    """Build the golden corpus scenarios under base_dir."""
    fixtures: dict[str, AlbumFixture] = {}
    for scenario in scenarios():
        fixtures[scenario.name] = build_album_dir(
            base_dir,
            scenario.name,
            scenario.audio_specs,
            scenario.non_audio_files,
        )
    return fixtures

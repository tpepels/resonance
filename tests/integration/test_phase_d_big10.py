"""Phase D Big-10 acceptance suite."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identity.signature import dir_signature
from resonance.core.identifier import DirectoryEvidence, ProviderCapabilities, ProviderRelease, ProviderTrack, TrackEvidence, identify
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.helpers.fs import AudioStubSpec, build_album_dir


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    audio_specs: list[AudioStubSpec]
    non_audio_files: list[str]
    release: ProviderRelease
    expected_dest_tail: tuple[str, str]


class _FlippingProvider:
    """Provider that flips release order on each call for determinism checks."""

    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = list(releases)
        self._flip = False
        self.search_by_fingerprints_calls = 0
        self.search_by_metadata_calls = 0

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self.search_by_fingerprints_calls += 1
        _ = fingerprints
        self._flip = not self._flip
        if self._flip:
            return list(self._releases)
        return list(reversed(self._releases))

    def search_by_metadata(self, artist: str | None, album: str | None, track_count: int) -> list[ProviderRelease]:
        self.search_by_metadata_calls += 1
        _ = (artist, album, track_count)
        return []


def _evidence_from_files(audio_files: list[Path]) -> DirectoryEvidence:
    tracks: list[TrackEvidence] = []
    total_duration = 0
    for path in sorted(audio_files):
        data = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())
        duration = data.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tags = data.get("tags")
        tracks.append(
            TrackEvidence(
                fingerprint_id=data.get("fingerprint_id"),
                duration_seconds=duration if isinstance(duration, int) else None,
                existing_tags=tags if isinstance(tags, dict) else {},
            )
        )
    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def _release_from_specs(
    *,
    release_id: str,
    title: str,
    artist: str,
    year: int,
    specs: list[AudioStubSpec],
    composer: str | None = None,
) -> ProviderRelease:
    tracks = tuple(
        ProviderTrack(
            position=spec.tags.get("track_number", index),
            title=spec.tags.get("title", f"Track {index}"),
            duration_seconds=spec.duration_seconds,
            fingerprint_id=spec.fingerprint_id,
            recording_id=f"rec-{release_id}-{index:02d}",
            composer=composer,
            disc_number=spec.tags.get("disc_number"),
        )
        for index, spec in enumerate(specs, start=1)
    )
    return ProviderRelease(
        provider="musicbrainz",
        release_id=release_id,
        title=title,
        artist=artist,
        tracks=tracks,
        year=year,
    )


def _decoy_release(primary: ProviderRelease) -> ProviderRelease:
    tracks = tuple(
        ProviderTrack(
            position=track.position,
            title=track.title,
            duration_seconds=track.duration_seconds,
            fingerprint_id=f"decoy-{track.position:02d}",
        )
        for track in primary.tracks
    )
    return ProviderRelease(
        provider=primary.provider,
        release_id=f"{primary.release_id}-decoy",
        title=primary.title,
        artist=primary.artist,
        tracks=tracks,
        year=primary.year,
    )


def _scenarios() -> list[Scenario]:
    standard_specs = [
        AudioStubSpec(
            f"{index:02d} - Track {index}.flac",
            f"fp-std-{index:02d}",
            duration_seconds=180 + index,
            tags={
                "title": f"Track {index}",
                "artist": "Artist A",
                "album": "Standard Album",
                "album_artist": "Artist A",
                "track_number": index,
            },
        )
        for index in range(1, 11)
    ]
    multi_disc_specs = []
    track_index = 1
    for disc in (1, 2):
        for track in range(1, 6):
            multi_disc_specs.append(
                AudioStubSpec(
                    f"D{disc}-{track:02d} - Track {disc}-{track}.flac",
                    f"fp-md-{disc}-{track:02d}",
                    duration_seconds=200 + track,
                    tags={
                        "title": f"Track {disc}-{track}",
                        "artist": "Artist B",
                        "album": "Multi Disc Album",
                        "album_artist": "Artist B",
                        "track_number": track_index,
                        "disc_number": disc,
                    },
                )
            )
            track_index += 1

    box_set_specs = []
    track_index = 1
    for disc in (1, 2, 3, 4):
        for track in range(1, 4):
            box_set_specs.append(
                AudioStubSpec(
                    f"Box-{disc}-{track:02d}.flac",
                    f"fp-box-{disc}-{track:02d}",
                    duration_seconds=190 + track,
                    tags={
                        "title": f"Box Track {disc}-{track}",
                        "artist": "Artist Box",
                        "album": "Box Set",
                        "album_artist": "Artist Box",
                        "track_number": track_index,
                        "disc_number": disc,
                    },
                )
            )
            track_index += 1
    compilation_specs = [
        AudioStubSpec(
            f"{index:02d} - Artist {index} - Track {index}.flac",
            f"fp-comp-{index:02d}",
            duration_seconds=170 + index,
            tags={
                "title": f"Track {index}",
                "artist": f"Artist {index}",
                "album": "Compilation Album",
                "album_artist": "Various Artists",
                "track_number": index,
            },
        )
        for index in range(1, 9)
    ]
    name_variant_specs = [
        AudioStubSpec(
            "01 - AC DC - Track.flac",
            "fp-nv-01",
            duration_seconds=181,
            tags={
                "title": "Track",
                "artist": "AC/DC",
                "album": "Name Variants",
                "album_artist": "AC/DC",
                "track_number": 1,
            },
        ),
        AudioStubSpec(
            "02 - Bjork - Track.flac",
            "fp-nv-02",
            duration_seconds=182,
            tags={
                "title": "Track",
                "artist": "Björk",
                "album": "Name Variants",
                "album_artist": "Björk",
                "track_number": 2,
            },
        ),
    ]
    classical_specs = [
        AudioStubSpec(
            "01 - Movement I.flac",
            "fp-classical-01",
            duration_seconds=420,
            tags={
                "title": "Movement I",
                "composer": "J.S. Bach",
                "performer": "Performer A",
                "album": "Classical Work",
                "track_number": 1,
                "disc_number": 1,
            },
        ),
        AudioStubSpec(
            "02 - Movement II.flac",
            "fp-classical-02",
            duration_seconds=410,
            tags={
                "title": "Movement II",
                "composer": "J.S. Bach",
                "performer": "Performer A",
                "album": "Classical Work",
                "track_number": 2,
                "disc_number": 1,
            },
        ),
    ]
    live_specs = [
        AudioStubSpec(
            "01 - Live Intro.flac",
            "fp-live-01",
            duration_seconds=210,
            tags={
                "title": "Live Intro",
                "artist": "Artist Live",
                "album": "Live at The Forum",
                "album_artist": "Artist Live",
                "track_number": 1,
            },
        ),
        AudioStubSpec(
            "02 - Live Finale.flac",
            "fp-live-02",
            duration_seconds=240,
            tags={
                "title": "Live Finale",
                "artist": "Artist Live",
                "album": "Live at The Forum",
                "album_artist": "Artist Live",
                "track_number": 2,
            },
        ),
    ]
    hidden_specs = [
        AudioStubSpec(
            "00 - Hidden Intro.flac",
            "fp-hidden-00",
            duration_seconds=15,
            tags={
                "title": "Hidden Intro",
                "artist": "Artist Hidden",
                "album": "Hidden Track Album",
                "album_artist": "Artist Hidden",
                "track_number": 0,
            },
        ),
        AudioStubSpec(
            "01 - Track 1.flac",
            "fp-hidden-01",
            duration_seconds=200,
            tags={
                "title": "Track 1",
                "artist": "Artist Hidden",
                "album": "Hidden Track Album",
                "album_artist": "Artist Hidden",
                "track_number": 1,
            },
        ),
        AudioStubSpec(
            "99 - Secret Track.flac",
            "fp-hidden-99",
            duration_seconds=120,
            tags={
                "title": "Secret Track",
                "artist": "Artist Hidden",
                "album": "Hidden Track Album",
                "album_artist": "Artist Hidden",
                "track_number": 99,
            },
        ),
    ]
    extras_specs = [
        AudioStubSpec(
            "01 - Track A.flac",
            "fp-extra-01",
            duration_seconds=205,
            tags={
                "title": "Track A",
                "artist": "Artist C",
                "album": "Extras Album",
                "album_artist": "Artist C",
                "track_number": 1,
            },
        ),
        AudioStubSpec(
            "02 - Track B.flac",
            "fp-extra-02",
            duration_seconds=199,
            tags={
                "title": "Track B",
                "artist": "Artist C",
                "album": "Extras Album",
                "album_artist": "Artist C",
                "track_number": 2,
            },
        ),
    ]
    single_specs = [
        AudioStubSpec(
            "01 - Single Track.flac",
            "fp-single-01",
            duration_seconds=215,
            tags={
                "title": "Single Track",
                "artist": "Artist D",
                "album": "Standalone Single",
                "album_artist": "Artist D",
                "track_number": 1,
            },
        )
    ]
    return [
        Scenario(
            name="single_track",
            description="Single track release.",
            audio_specs=single_specs,
            non_audio_files=[],
            release=_release_from_specs(
                release_id="mb-single-1",
                title="Standalone Single",
                artist="Artist D",
                year=2018,
                specs=single_specs,
            ),
            expected_dest_tail=("Artist D", "2018 - Standalone Single"),
        ),
        Scenario(
            name="standard_album",
            description="Standard album.",
            audio_specs=standard_specs,
            non_audio_files=["cover.jpg"],
            release=_release_from_specs(
                release_id="mb-std-1",
                title="Standard Album",
                artist="Artist A",
                year=2020,
                specs=standard_specs,
            ),
            expected_dest_tail=("Artist A", "2020 - Standard Album"),
        ),
        Scenario(
            name="multi_disc",
            description="Multi-disc album.",
            audio_specs=multi_disc_specs,
            non_audio_files=["cover.jpg"],
            release=_release_from_specs(
                release_id="mb-md-1",
                title="Multi Disc Album",
                artist="Artist B",
                year=2019,
                specs=multi_disc_specs,
            ),
            expected_dest_tail=("Artist B", "2019 - Multi Disc Album"),
        ),
        Scenario(
            name="box_set",
            description="Box set with many discs.",
            audio_specs=box_set_specs,
            non_audio_files=["booklet.pdf"],
            release=_release_from_specs(
                release_id="mb-box-1",
                title="Box Set",
                artist="Artist Box",
                year=1995,
                specs=box_set_specs,
            ),
            expected_dest_tail=("Artist Box", "1995 - Box Set"),
        ),
        Scenario(
            name="compilation",
            description="Compilation release.",
            audio_specs=compilation_specs,
            non_audio_files=["cover.jpg"],
            release=_release_from_specs(
                release_id="mb-comp-1",
                title="Compilation Album",
                artist="Various Artists",
                year=2005,
                specs=compilation_specs,
            ),
            expected_dest_tail=("Various Artists", "2005 - Compilation Album"),
        ),
        Scenario(
            name="name_variants",
            description="Artist name variants.",
            audio_specs=name_variant_specs,
            non_audio_files=[],
            release=_release_from_specs(
                release_id="mb-nv-1",
                title="Name Variants",
                artist="Björk/ACDC",
                year=2012,
                specs=name_variant_specs,
            ),
            expected_dest_tail=("Björk ACDC", "2012 - Name Variants"),
        ),
        Scenario(
            name="classical",
            description="Classical album.",
            audio_specs=classical_specs,
            non_audio_files=["cover.jpg"],
            release=_release_from_specs(
                release_id="mb-classical-1",
                title="Classical Work",
                artist="Performer A",
                year=1990,
                specs=classical_specs,
                composer="J.S. Bach",
            ),
            expected_dest_tail=("J.S. Bach", "1990 - Classical Work"),
        ),
        Scenario(
            name="live_album",
            description="Live album.",
            audio_specs=live_specs,
            non_audio_files=["poster.jpg"],
            release=_release_from_specs(
                release_id="mb-live-1",
                title="Live at The Forum",
                artist="Artist Live",
                year=2003,
                specs=live_specs,
            ),
            expected_dest_tail=("Artist Live", "2003 - Live at The Forum"),
        ),
        Scenario(
            name="hidden_track",
            description="Hidden track oddities.",
            audio_specs=hidden_specs,
            non_audio_files=[],
            release=_release_from_specs(
                release_id="mb-hidden-1",
                title="Hidden Track Album",
                artist="Artist Hidden",
                year=2009,
                specs=hidden_specs,
            ),
            expected_dest_tail=("Artist Hidden", "2009 - Hidden Track Album"),
        ),
        Scenario(
            name="extras_album",
            description="Album with extras.",
            audio_specs=extras_specs,
            non_audio_files=["cover.jpg", "booklet.pdf", "rip.log"],
            release=_release_from_specs(
                release_id="mb-extra-1",
                title="Extras Album",
                artist="Artist C",
                year=2001,
                specs=extras_specs,
            ),
            expected_dest_tail=("Artist C", "2001 - Extras Album"),
        ),
    ]


def _assert_tags(writer: MetaJsonTagWriter, dest_dir: Path, release: ProviderRelease) -> None:
    track_by_position = {track.position: track for track in release.tracks}
    for audio in sorted(dest_dir.rglob("*.flac")):
        tags = writer.read_tags(audio)
        track_number = int(tags["tracknumber"])
        track = track_by_position[track_number]
        assert tags["album"] == release.title
        assert tags["albumartist"] == release.artist
        assert tags["title"] == track.title
        assert tags["musicbrainz_albumid"] == release.release_id
        if track.recording_id:
            assert tags["musicbrainz_recordingid"] == track.recording_id
        assert tags["resonance.prov.pinned_release_id"] == release.release_id


def test_phase_d_big10(tmp_path: Path) -> None:
    output_root = tmp_path / "organized"
    writer = MetaJsonTagWriter()
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        for scenario in _scenarios():
            fixture = build_album_dir(
                tmp_path / "library",
                scenario.name,
                scenario.audio_specs,
                scenario.non_audio_files,
            )
            evidence = _evidence_from_files(fixture.audio_files)
            signature_hash = dir_signature(fixture.audio_files).signature_hash
            primary = scenario.release
            decoy = _decoy_release(primary)

            # Deterministic ranking: flipping order should not change candidate order.
            flipping_provider = _FlippingProvider([primary, decoy])
            first = identify(evidence, flipping_provider)
            second = identify(evidence, flipping_provider)
            assert [c.release.release_id for c in first.candidates] == [
                c.release.release_id for c in second.candidates
            ]
            assert first.candidates[0].release.release_id == primary.release_id

            provider = _FlippingProvider([primary, decoy])
            outcome = resolve_directory(
                dir_id="dir-" + scenario.name,
                path=fixture.path,
                signature_hash=signature_hash,
                evidence=evidence,
                store=store,
                provider_client=provider,
            )
            assert outcome.state == DirectoryState.RESOLVED_AUTO
            assert outcome.pinned_release_id == primary.release_id

            record = store.get(outcome.dir_id)
            assert record is not None
            plan = plan_directory(
                record=record,
                pinned_release=primary,
                source_files=fixture.audio_files,
            )
            assert plan.destination_path.parts[-2:] == scenario.expected_dest_tail

            store.set_state(
                record.dir_id,
                DirectoryState.PLANNED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
            tag_patch = build_tag_patch(
                plan,
                primary,
                DirectoryState.RESOLVED_AUTO,
            )
            report = apply_plan(
                plan,
                tag_patch,
                store,
                allowed_roots=(output_root,),
                dry_run=False,
                tag_writer=writer,
            )
            assert report.status == ApplyStatus.APPLIED

            dest_dir = output_root / plan.destination_path
            _assert_tags(writer, dest_dir, primary)

            # Rerun should not rematch (provider call count unchanged).
            pre_calls = provider.search_by_fingerprints_calls
            rerun_outcome = resolve_directory(
                dir_id=record.dir_id,
                path=fixture.path,
                signature_hash=signature_hash,
                evidence=evidence,
                store=store,
                provider_client=provider,
            )
            assert rerun_outcome.state == DirectoryState.APPLIED
            assert provider.search_by_fingerprints_calls == pre_calls
    finally:
        store.close()

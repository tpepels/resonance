"""Integration scaffolding for Phase 10 daemon + prompt CLI."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Iterable

import pytest

from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
    score_release,
)
from resonance.core.state import DirectoryState
from resonance.core.identity.signature import dir_id, dir_signature
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import DirectoryBatch
from tests.helpers.fs import AudioStubSpec, build_album_dir


class StubScanner:
    """Deterministic scanner stub for daemon tests."""

    def __init__(self, batches: Iterable[DirectoryBatch]) -> None:
        self._batches = list(batches)

    def iter_directories(self):
        yield from self._batches


class StubProviderClient:
    def __init__(
        self,
        *,
        fingerprint_releases: list[ProviderRelease] | None = None,
        metadata_releases: list[ProviderRelease] | None = None,
    ) -> None:
        self.fingerprint_releases = fingerprint_releases or []
        self.metadata_releases = metadata_releases or []
        self.search_by_fingerprints_calls = 0
        self.search_by_metadata_calls = 0
        self.fingerprint_calls: list[str] = []

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self.search_by_fingerprints_calls += 1
        if fingerprints:
            self.fingerprint_calls.append(fingerprints[0])
        return list(self.fingerprint_releases)

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        self.search_by_metadata_calls += 1
        return list(self.metadata_releases)

    @property
    def total_calls(self) -> int:
        return self.search_by_fingerprints_calls + self.search_by_metadata_calls


def _evidence_from_files(audio_files: list[Path]) -> DirectoryEvidence:
    tracks: list[TrackEvidence] = []
    total_duration = 0
    for path in sorted(audio_files):
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        data = json.loads(meta_path.read_text())
        duration = data.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tracks.append(
            TrackEvidence(
                fingerprint_id=data.get("fingerprint_id"),
                duration_seconds=duration,
                existing_tags={},
            )
        )
    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def _make_batch(fixture_path: Path) -> DirectoryBatch:
    audio_files = sorted(fixture_path.glob("*.flac"))
    signature = dir_signature(audio_files)
    return DirectoryBatch(
        directory=fixture_path,
        files=audio_files,
        non_audio_files=[],
        signature_hash=signature.signature_hash,
        dir_id=dir_id(signature),
    )


def test_evidence_builder_sums_durations(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a", duration_seconds=181),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b", duration_seconds=199),
        ],
    )
    evidence = _evidence_from_files(sorted(fixture.path.glob("*.flac")))
    assert evidence.total_duration_seconds == 380


def test_duration_scoring_uses_integer_buckets(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a", duration_seconds=180)],
    )
    evidence = _evidence_from_files(sorted(fixture.path.glob("*.flac")))
    release_close = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A", duration_seconds=180),),
    )
    release_far = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-2",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A", duration_seconds=300),),
    )
    score_close = score_release(evidence, release_close)
    score_far = score_release(evidence, release_far)
    assert score_close.duration_fit == 1.0
    assert score_far.duration_fit == 0.5


def test_daemon_autopins_certain(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    batch = _make_batch(fixture.path)
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A", fingerprint_id="fp-a"),
            ProviderTrack(position=2, title="Track B", fingerprint_id="fp-b"),
        ),
    )
    provider = StubProviderClient(fingerprint_releases=[release])
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        daemon_cmd = importlib.import_module("resonance.commands.daemon")
        daemon_cmd.run_daemon_once(
            scanner=StubScanner([batch]),
            store=store,
            provider_client=provider,
            evidence_builder=_evidence_from_files,
        )
        record = store.get(batch.dir_id)
        assert record is not None
        assert record.state == DirectoryState.RESOLVED_AUTO
    finally:
        store.close()


def test_daemon_queues_uncertain(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id=""),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id=""),
        ],
    )
    batch = _make_batch(fixture.path)
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-2",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A"),
            ProviderTrack(position=2, title="Track B"),
        ),
    )
    release_alt = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-3",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A"),
            ProviderTrack(position=2, title="Track B"),
        ),
    )
    provider = StubProviderClient(metadata_releases=[release, release_alt])
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        daemon_cmd = importlib.import_module("resonance.commands.daemon")
        daemon_cmd.run_daemon_once(
            scanner=StubScanner([batch]),
            store=store,
            provider_client=provider,
            evidence_builder=_evidence_from_files,
        )
        record = store.get(batch.dir_id)
        assert record is not None
        assert record.state == DirectoryState.QUEUED_PROMPT
    finally:
        store.close()


def test_daemon_processes_sorted_dir_id_order(tmp_path: Path) -> None:
    fixture_a = build_album_dir(
        tmp_path,
        "album_a",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    fixture_b = build_album_dir(
        tmp_path,
        "album_b",
        [AudioStubSpec(filename="01 - Track B.flac", fingerprint_id="fp-b")],
    )
    batch_a = _make_batch(fixture_a.path)
    batch_b = _make_batch(fixture_b.path)
    provider = StubProviderClient()
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        daemon_cmd = importlib.import_module("resonance.commands.daemon")
        outcomes = daemon_cmd.run_daemon_once(
            scanner=StubScanner([batch_b, batch_a]),
            store=store,
            provider_client=provider,
            evidence_builder=_evidence_from_files,
        )
        ordered = sorted([batch_a, batch_b], key=lambda b: (b.dir_id, str(b.directory)))
        assert [outcome.dir_id for outcome in outcomes] == [b.dir_id for b in ordered]
        expected = []
        for batch in ordered:
            meta = json.loads(
                batch.files[0].with_suffix(batch.files[0].suffix + ".meta.json").read_text()
            )
            expected.append(meta.get("fingerprint_id"))
        assert provider.fingerprint_calls == expected
    finally:
        store.close()


def test_daemon_skips_jailed(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    batch = _make_batch(fixture.path)
    provider = StubProviderClient()
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create(batch.dir_id, batch.directory, batch.signature_hash)
        store.set_state(batch.dir_id, DirectoryState.JAILED)
        daemon_cmd = importlib.import_module("resonance.commands.daemon")
        daemon_cmd.run_daemon_once(
            scanner=StubScanner([batch]),
            store=store,
            provider_client=provider,
            evidence_builder=_evidence_from_files,
        )
        record = store.get(batch.dir_id)
        assert record is not None
        assert record.state == DirectoryState.JAILED
        assert provider.total_calls == 0
    finally:
        store.close()


def test_daemon_respects_pinned_decisions(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    batch = _make_batch(fixture.path)
    provider = StubProviderClient()
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create(batch.dir_id, batch.directory, batch.signature_hash)
        store.set_state(
            batch.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
        )
        daemon_cmd = importlib.import_module("resonance.commands.daemon")
        daemon_cmd.run_daemon_once(
            scanner=StubScanner([batch]),
            store=store,
            provider_client=provider,
            evidence_builder=_evidence_from_files,
        )
        assert provider.total_calls == 0
    finally:
        store.close()


def test_prompt_selects_candidate_by_index(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    batch = _make_batch(fixture.path)
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A"),),
    )
    provider = StubProviderClient(metadata_releases=[release])
    store = DirectoryStateStore(tmp_path / "state.db")

    outputs: list[str] = []
    input_values = iter(["1"])

    def input_provider(_: str) -> str:
        return next(input_values)

    def output_sink(message: str) -> None:
        outputs.append(message)

    try:
        store.get_or_create(batch.dir_id, batch.directory, batch.signature_hash)
        store.set_state(batch.dir_id, DirectoryState.QUEUED_PROMPT)
        prompt_cmd = importlib.import_module("resonance.commands.prompt")
        prompt_cmd.run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=input_provider,
            output_sink=output_sink,
            evidence_builder=_evidence_from_files,
        )
        record = store.get(batch.dir_id)
        assert record is not None
        assert record.state == DirectoryState.RESOLVED_USER
        assert record.pinned_provider == "musicbrainz"
        assert record.pinned_release_id == "mb-123"
    finally:
        store.close()


def test_prompt_outputs_tracks_in_stable_order(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b", duration_seconds=200),
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a", duration_seconds=180),
        ],
    )
    batch = _make_batch(fixture.path)
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A"),),
    )
    provider = StubProviderClient(metadata_releases=[release])
    store = DirectoryStateStore(tmp_path / "state.db")
    outputs: list[str] = []
    input_values = iter(["1"])

    def input_provider(_: str) -> str:
        return next(input_values)

    def output_sink(message: str) -> None:
        outputs.append(message)

    try:
        store.get_or_create(batch.dir_id, batch.directory, batch.signature_hash)
        store.set_state(batch.dir_id, DirectoryState.QUEUED_PROMPT)
        prompt_cmd = importlib.import_module("resonance.commands.prompt")
        prompt_cmd.run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=input_provider,
            output_sink=output_sink,
            evidence_builder=_evidence_from_files,
        )
        track_lines = [line for line in outputs if line.strip().startswith(("1.", "2."))]
        assert track_lines == [
            "  1. 01 - Track A.flac (180s)",
            "  2. 02 - Track B.flac (200s)",
        ]
    finally:
        store.close()


def test_prompt_accepts_manual_id(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    batch = _make_batch(fixture.path)
    provider = StubProviderClient()
    store = DirectoryStateStore(tmp_path / "state.db")

    input_values = iter(["mb:xyz"])

    def input_provider(_: str) -> str:
        return next(input_values)

    try:
        store.get_or_create(batch.dir_id, batch.directory, batch.signature_hash)
        store.set_state(batch.dir_id, DirectoryState.QUEUED_PROMPT)
        prompt_cmd = importlib.import_module("resonance.commands.prompt")
        prompt_cmd.run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=input_provider,
            output_sink=lambda _msg: None,
            evidence_builder=_evidence_from_files,
        )
        record = store.get(batch.dir_id)
        assert record is not None
        assert record.state == DirectoryState.RESOLVED_USER
        assert record.pinned_provider == "musicbrainz"
        assert record.pinned_release_id == "xyz"
    finally:
        store.close()


def test_unjail_resets_to_new(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "sig-1")
        store.set_state(record.dir_id, DirectoryState.JAILED)

        unjail_cmd = importlib.import_module("resonance.commands.unjail")
        unjail_cmd.run_unjail(store=store, dir_id=record.dir_id)

        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.NEW
    finally:
        store.close()

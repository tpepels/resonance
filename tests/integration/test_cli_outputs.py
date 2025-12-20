"""Integration tests for CLI JSON and stable output."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from resonance.commands.apply import run_apply
from resonance.commands.identify import run_identify
from resonance.commands.plan import run_plan
from resonance.commands.scan import run_scan
from resonance.core.applier import ApplyReport, ApplyStatus, FileOpResult
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class StubProviderClient:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return list(self._releases)


def _capture_output() -> tuple[list[str], callable]:
    lines: list[str] = []

    def sink(value: str) -> None:
        lines.append(value)

    return lines, sink


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")


def test_scan_json_output_is_deterministic(tmp_path: Path) -> None:
    directory = tmp_path / "album"
    _write_audio(directory / "01 - Track A.flac")
    _write_audio(directory / "02 - Track B.flac")
    (directory / "readme.txt").write_text("notes")

    lines, sink = _capture_output()
    args = Namespace(
        directory=directory,
        cache=tmp_path / "cache.db",
        unjail=False,
        delete_nonaudio=False,
        dry_run=True,
        json=True,
    )
    run_scan(args, output_sink=sink)
    payload = json.loads(lines[0])
    assert payload["schema_version"] == "v1"
    assert payload["command"] == "scan"
    data = payload["data"]
    assert data["audio_count"] == 2
    assert data["non_audio_count"] == 1
    assert data["status"] == "FOUND"


def test_identify_outputs_json_and_human(tmp_path: Path) -> None:
    directory = tmp_path / "album"
    _write_audio(directory / "01 - Track A.flac")
    _write_audio(directory / "02 - Track B.flac")

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=10),
            ProviderTrack(position=2, title="Track B", duration_seconds=10),
        ),
    )

    def evidence_builder(_files: list[Path]) -> DirectoryEvidence:
        tracks = (
            TrackEvidence(fingerprint_id=None, duration_seconds=10, existing_tags={}),
            TrackEvidence(fingerprint_id=None, duration_seconds=10, existing_tags={}),
        )
        return DirectoryEvidence(
            tracks=tracks,
            track_count=2,
            total_duration_seconds=20,
        )

    provider = StubProviderClient([release])

    lines, sink = _capture_output()
    args = Namespace(directory=directory, json=True)
    run_identify(args, provider_client=provider, evidence_builder=evidence_builder, output_sink=sink)
    payload = json.loads(lines[0])
    assert payload["schema_version"] == "v1"
    assert payload["command"] == "identify"
    assert payload["data"]["tier"] == "UNSURE"
    assert len(payload["data"]["candidates"]) == 1

    lines, sink = _capture_output()
    args = Namespace(directory=directory, json=False)
    run_identify(args, provider_client=provider, evidence_builder=evidence_builder, output_sink=sink)
    assert lines == [
        f"identify: dir_id={payload['data']['dir_id']} tier=UNSURE",
        "identify: candidates=1 tracks=2",
    ]


def test_plan_outputs_json_and_human(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
        )
        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-1",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track A"),),
        )

        lines, sink = _capture_output()
        args = Namespace(dir_id=record.dir_id, state_db=None, json=True)
        run_plan(args, store=store, pinned_release=release, output_sink=sink)
        payload = json.loads(lines[0])
        assert payload["schema_version"] == "v1"
        assert payload["command"] == "plan"
        assert payload["data"]["dir_id"] == record.dir_id

        lines, sink = _capture_output()
        args = Namespace(dir_id=record.dir_id, state_db=None, json=False)
        run_plan(args, store=store, pinned_release=release, output_sink=sink)
        assert lines == [
            f"plan: dir_id={record.dir_id} ops=1",
            f"plan: destination={payload['data']['destination_path']}",
        ]
    finally:
        store.close()


def test_apply_outputs_json(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "meta-json"}))

    report = ApplyReport(
        dir_id="dir-1",
        plan_version="v1",
        tagpatch_version="v1",
        status=ApplyStatus.APPLIED,
        dry_run=False,
        file_ops=(
            FileOpResult(
                source_path=tmp_path / "a",
                destination_path=tmp_path / "b",
                status="OK",
            ),
        ),
        tag_ops=(),
        errors=(),
        rollback_attempted=False,
        rollback_success=False,
    )

    def apply_fn(**_kwargs):
        return report

    lines, sink = _capture_output()
    args = Namespace(
        config=config_path,
        tag_writer_backend=None,
        plan=tmp_path / "plan.json",
        state_db=tmp_path / "state.db",
        json=True,
    )
    run_apply(args, apply_fn=apply_fn, output_sink=sink)
    payload = json.loads(lines[0])
    assert payload["schema_version"] == "v1"
    assert payload["command"] == "apply"
    assert payload["data"]["status"] == "APPLIED"


def test_identify_outputs_provider_not_configured_json(tmp_path: Path) -> None:
    directory = tmp_path / "album"
    _write_audio(directory / "01 - Track A.flac")

    lines, sink = _capture_output()
    args = Namespace(directory=directory, json=True)
    run_identify(args, provider_client=None, output_sink=sink)
    payload = json.loads(lines[0])
    assert payload["schema_version"] == "v1"
    assert payload["command"] == "identify"
    assert payload["data"]["status"] == "NO_PROVIDER"
    assert payload["data"]["provider_status"] == "NOT_CONFIGURED"

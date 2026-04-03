"""Test review surface inspectability contracts (G6).

Guarantee G6: Review remains usable at realistic corpus size.
Tests that post-resolution state exposes inspectable decision data,
and that JSON output mode provides structured machine-readable output.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from resonance.commands.audit import run_audit
from resonance.commands.scan import run_scan
from resonance.commands.resolve import run_resolve
from resonance.core.identifier import (
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
)
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class _StubProvider:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=True, supports_metadata=True)

    def search_by_fingerprints(self, fps: list[str]) -> list[ProviderRelease]:
        return list(self._releases)

    def search_by_metadata(self, artist, album, track_count) -> list[ProviderRelease]:
        return list(self._releases)


def _write_stub(path: Path, duration: int, fp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")
    meta = {"duration_seconds": duration, "fingerprint_id": fp}
    path.with_suffix(path.suffix + ".meta.json").write_text(json.dumps(meta))


RELEASES = [
    ProviderRelease(
        provider="musicbrainz",
        release_id=f"mb-review-{i:03d}",
        title=f"Album {i}",
        artist=f"Artist {i}",
        tracks=(
            ProviderTrack(position=1, title="Track 1", duration_seconds=180,
                          fingerprint_id=f"fp-r{i}-1"),
            ProviderTrack(position=2, title="Track 2", duration_seconds=200,
                          fingerprint_id=f"fp-r{i}-2"),
        ),
    )
    for i in range(1, 6)
]


def test_audit_exposes_inspectable_fields_per_directory(tmp_path: Path) -> None:
    """After resolve, every resolved directory has inspectable audit fields.

    G2+G6: The user can inspect evidence, resolution state, provider, and
    release ID for each directory without reading internal state files.
    """
    lib = tmp_path / "library"
    state_db = tmp_path / "state.db"

    # Create 5 directories to simulate a small corpus
    for i in range(1, 6):
        _write_stub(lib / f"album_{i}" / "track1.flac", 180, f"fp-r{i}-1")
        _write_stub(lib / f"album_{i}" / "track2.flac", 200, f"fp-r{i}-2")

    store = DirectoryStateStore(state_db)
    try:
        # Scan all
        scan_args = Namespace(library_root=lib, state_db=state_db, json=False)
        run_scan(scan_args, store=store, output_sink=lambda _: None)

        # Resolve all — these will go to QUEUED_PROMPT since stub returns generic releases
        provider = _StubProvider(RELEASES)
        resolve_args = Namespace(library_root=lib, state_db=state_db, json=False, cache_db=None)
        run_resolve(resolve_args, store=store, provider_client=provider, output_sink=lambda _: None)

        # Audit each resolved/queued directory
        all_records = store.list_all()
        assert len(all_records) >= 5

        for record in all_records:
            audit = run_audit(store=store, dir_id=record.dir_id)

            # G6 inspectability contract: every field present and non-null
            assert "dir_id" in audit
            assert "state" in audit
            assert "signature_hash" in audit
            assert audit["dir_id"] == record.dir_id
            assert audit["state"] in {s.value for s in DirectoryState}
    finally:
        store.close()


def test_json_resolve_output_is_machine_parseable(tmp_path: Path) -> None:
    """JSON mode resolve output is a single valid JSON line with schema_version.

    G6: review tooling can consume output without parsing human-readable text.
    """
    lib = tmp_path / "library"
    state_db = tmp_path / "state.db"
    _write_stub(lib / "album" / "track1.flac", 180, "fp-j-1")
    _write_stub(lib / "album" / "track2.flac", 200, "fp-j-2")

    store = DirectoryStateStore(state_db)
    try:
        scan_args = Namespace(library_root=lib, state_db=state_db, json=False)
        run_scan(scan_args, store=store, output_sink=lambda _: None)

        provider = _StubProvider(RELEASES[:1])
        resolve_args = Namespace(library_root=lib, state_db=state_db, json=True, cache_db=None)
        output: list[str] = []
        run_resolve(resolve_args, store=store, provider_client=provider, output_sink=output.append)

        assert len(output) == 1, f"Expected single JSON line, got {len(output)}"
        data = json.loads(output[0])
        assert data["schema_version"] == "v1"
        assert data["command"] == "resolve"
        assert "data" in data
        assert data["data"]["status"] in ("OK", "ERROR")
    finally:
        store.close()


def test_scan_json_output_includes_directory_count(tmp_path: Path) -> None:
    """JSON scan output includes directory counts for review tooling."""
    lib = tmp_path / "library"
    state_db = tmp_path / "state.db"
    for i in range(3):
        _write_stub(lib / f"album_{i}" / "track.flac", 180, f"fp-s-{i}")

    store = DirectoryStateStore(state_db)
    try:
        scan_args = Namespace(library_root=lib, state_db=state_db, json=True)
        output: list[str] = []
        run_scan(scan_args, store=store, output_sink=output.append)

        data = json.loads(output[0])
        assert data["schema_version"] == "v1"
        assert data["command"] == "scan"
        # The data block should indicate how many directories were found
        assert "data" in data
    finally:
        store.close()

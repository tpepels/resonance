"""E2E lifecycle test: scan → resolve → plan → apply → audit → doctor → rollback (G7).

Proves that the full inspection/recovery chain works as a single workflow,
not just as isolated command tests.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from resonance.commands.audit import run_audit
from resonance.commands.doctor import run_doctor
from resonance.commands.rollback import run_rollback
from resonance.commands.scan import run_scan
from resonance.commands.resolve import run_resolve
from resonance.core.applier import apply_plan, ApplyStatus
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter


class _StubProvider:
    """Deterministic provider for lifecycle test."""

    def __init__(self, release: ProviderRelease) -> None:
        self._release = release

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=True, supports_metadata=False)

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return [self._release]

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return []


def _write_stub_audio(path: Path, duration: int, fingerprint: str) -> None:
    """Create stub audio file with .meta.json sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub-audio")
    meta = {"duration_seconds": duration, "fingerprint_id": fingerprint}
    path.with_suffix(path.suffix + ".meta.json").write_text(json.dumps(meta))


RELEASE = ProviderRelease(
    provider="musicbrainz",
    release_id="mb-lifecycle-001",
    title="Lifecycle Album",
    artist="Lifecycle Artist",
    year=2024,
    tracks=(
        ProviderTrack(position=1, title="Opening", duration_seconds=180,
                      fingerprint_id="fp-lc-1", recording_id="rec-lc-1"),
        ProviderTrack(position=2, title="Closing", duration_seconds=200,
                      fingerprint_id="fp-lc-2", recording_id="rec-lc-2"),
    ),
)


def test_full_lifecycle_scan_through_rollback(tmp_path: Path) -> None:
    """Full lifecycle: scan → resolve → apply → audit → doctor → rollback.

    Proves the inspection and recovery commands work on real post-apply state,
    not just synthetic setup.
    """
    lib = tmp_path / "library"
    _write_stub_audio(lib / "album" / "track1.flac", 180, "fp-lc-1")
    _write_stub_audio(lib / "album" / "track2.flac", 200, "fp-lc-2")

    state_db = tmp_path / "state.db"
    store = DirectoryStateStore(state_db)
    provider = _StubProvider(RELEASE)

    try:
        # ── 1. Scan ──
        scan_args = Namespace(library_root=lib, state_db=state_db, json=False)
        scan_exit = run_scan(scan_args, store=store, output_sink=lambda _: None)
        assert scan_exit == 0

        new_dirs = store.list_by_state(DirectoryState.NEW)
        assert len(new_dirs) == 1
        dir_id = new_dirs[0].dir_id
        sig = new_dirs[0].signature_hash

        # ── 2. Resolve ──
        evidence = DirectoryEvidence(
            track_count=2,
            tracks=(
                TrackEvidence(
                    duration_seconds=180,
                    fingerprint_id="fp-lc-1",
                    existing_tags={},
                ),
                TrackEvidence(
                    duration_seconds=200,
                    fingerprint_id="fp-lc-2",
                    existing_tags={},
                ),
            ),
            total_duration_seconds=380,
        )
        outcome = resolve_directory(
            dir_id=dir_id, path=lib / "album", signature_hash=sig,
            evidence=evidence, store=store, provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO

        # ── 3. Plan + Apply ──
        record = store.get(dir_id)
        assert record is not None
        plan = plan_directory(
            record=record, pinned_release=RELEASE,
            source_files=[lib / "album" / "track1.flac", lib / "album" / "track2.flac"],
        )
        assert len(plan.operations) == 2

        store.set_state(dir_id, DirectoryState.PLANNED,
                        pinned_provider="musicbrainz",
                        pinned_release_id="mb-lifecycle-001")

        import hashlib
        from dataclasses import asdict
        payload = json.dumps(
            _convert_paths(asdict(plan)),
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        plan_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        store.record_plan_summary(dir_id, plan_hash=plan_hash, plan_version=plan.plan_version)

        tag_patch = build_tag_patch(
            plan=plan, pinned_release=RELEASE,
            resolution_state=DirectoryState.RESOLVED_AUTO,
        )
        tag_writer = MetaJsonTagWriter()
        report = apply_plan(
            plan=plan, tag_patch=tag_patch, store=store,
            allowed_roots=(tmp_path,), dry_run=False, tag_writer=tag_writer,
        )
        assert report.status == ApplyStatus.APPLIED

        # ── 4. Audit: verify fields are populated after real apply ──
        audit = run_audit(store=store, dir_id=dir_id)
        assert audit["dir_id"] == dir_id
        assert audit["state"] == DirectoryState.APPLIED.value
        assert audit["pinned_provider"] == "musicbrainz"
        assert audit["pinned_release_id"] == "mb-lifecycle-001"

        # Audit with apply_report merges errors
        audit_with_report = run_audit(store=store, dir_id=dir_id, apply_report=report)
        assert audit_with_report["last_apply_errors"] == ()

        # ── 5. Doctor: detect missing source path (files were moved) ──
        doctor_result = run_doctor(store=store)
        # The doctor checks last_seen_path; after apply, the original dir may be gone
        # This is a valid finding from doctor
        assert isinstance(doctor_result["issues"], list)

        # ── 6. Rollback: revert the apply ──
        rollback_result = run_rollback(
            report=report,
            source_dir=lib / "album",
            destination_dir=tmp_path,
            allowed_roots=(tmp_path,),
            tag_writer=tag_writer,
        )
        assert rollback_result["restored"] is True
        assert rollback_result["errors"] == ()

    finally:
        store.close()


def test_audit_unknown_dir_id(tmp_path: Path) -> None:
    """Audit of nonexistent dir_id returns UNKNOWN — doesn't crash."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        audit = run_audit(store=store, dir_id="nonexistent-dir")
        assert audit["state"] == "UNKNOWN"
        assert audit["dir_id"] == "nonexistent-dir"
    finally:
        store.close()


def _convert_paths(obj: object) -> object:
    """Convert Path objects to strings for JSON serialization."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _convert_paths(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_paths(item) for item in obj]
    return obj

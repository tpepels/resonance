"""Integration tests for audit, doctor, and rollback commands."""

from __future__ import annotations

from pathlib import Path

from resonance.core.applier import ApplyReport, ApplyStatus, FileOpResult, TagOpResult
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
import pytest


def _make_store(tmp_path: Path) -> DirectoryStateStore:
    return DirectoryStateStore(tmp_path / "state.db")


def test_audit_reports_core_fields(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        from resonance.commands.audit import run_audit

        report = run_audit(store=store, dir_id=record.dir_id)
        assert report["dir_id"] == "dir-1"
        assert report["state"] == DirectoryState.RESOLVED_AUTO.value
        assert report["signature_hash"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert report["pinned_release_id"] == "mb-123"
    finally:
        store.close()


def test_doctor_detects_missing_dir(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        from resonance.commands.doctor import run_doctor

        result = run_doctor(store=store)
        issues = result["issues"]
        assert any(issue["dir_id"] == "dir-1" for issue in issues)
    finally:
        store.close()


def test_doctor_reports_missing_config(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        from resonance.commands.doctor import run_doctor

        config_path = tmp_path / "settings.json"
        result = run_doctor(store=store, config_path=config_path)
        issues = result["issues"]
        assert any(issue["issue"] == "missing_config" for issue in issues)
    finally:
        store.close()


def test_rollback_reverts_applied_move(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        source = tmp_path / "source"
        source.mkdir(parents=True, exist_ok=True)
        src_file = source / "track.flac"
        src_file.write_text("audio")
        dest_root = tmp_path / "library"
        dest_root.mkdir(parents=True, exist_ok=True)
        dest_file = dest_root / "Artist" / "Album" / "track.flac"
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.replace(dest_file)

        report = ApplyReport(
            dir_id="dir-1",
            plan_version="v1",
            tagpatch_version=None,
            status=ApplyStatus.APPLIED,
            dry_run=False,
            file_ops=(
                FileOpResult(
                    source_path=source / "track.flac",
                    destination_path=dest_file,
                    status="MOVED",
                    error=None,
                ),
            ),
            tag_ops=(),
            errors=(),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        from resonance.commands.rollback import run_rollback

        result = run_rollback(
            report=report,
            source_dir=source,
            destination_dir=dest_root,
        )
        assert result["restored"] is True
        assert result["errors"] == ()
        assert (source / "track.flac").exists()
        assert not dest_file.exists()
    finally:
        store.close()


def test_audit_includes_tag_errors(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.FAILED,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )
        report = ApplyReport(
            dir_id="dir-1",
            plan_version="v1",
            tagpatch_version="v1",
            status=ApplyStatus.FAILED,
            dry_run=False,
            file_ops=(),
            tag_ops=(),
            errors=("Tag write failed for /tmp/file.flac: boom",),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        from resonance.commands.audit import run_audit

        audit = run_audit(store=store, dir_id=record.dir_id, apply_report=report)
        assert audit["last_apply_errors"] == report.errors
    finally:
        store.close()


def test_rollback_restores_tag_snapshot(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        source = tmp_path / "source"
        source.mkdir(parents=True, exist_ok=True)
        src_file = source / "track.flac"
        src_file.write_text("audio")
        dest_root = tmp_path / "library"
        dest_root.mkdir(parents=True, exist_ok=True)
        dest_file = dest_root / "Artist" / "Album" / "track.flac"
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.replace(dest_file)

        from resonance.services.tag_writer import MetaJsonTagWriter

        writer = MetaJsonTagWriter()
        writer.apply_patch(dest_file, {"title": "After"}, allow_overwrite=True)

        report = ApplyReport(
            dir_id="dir-1",
            plan_version="v1",
            tagpatch_version="v1",
            status=ApplyStatus.FAILED,
            dry_run=False,
            file_ops=(
                FileOpResult(
                    source_path=source / "track.flac",
                    destination_path=dest_file,
                    status="MOVED",
                    error=None,
                ),
            ),
            tag_ops=(
                TagOpResult(
                    file_path=dest_file,
                    tags_set=("title",),
                    tags_skipped=(),
                    before_tags=(("title", "Before"),),
                ),
            ),
            errors=(),
            warnings=(),
            rollback_attempted=True,
            rollback_success=False,
        )
        from resonance.commands.rollback import run_rollback

        result = run_rollback(
            report=report,
            source_dir=source,
            destination_dir=dest_root,
            tag_writer=writer,
        )
        assert result["restored"] is True
        assert writer.read_tags(source / "track.flac")["title"] == "Before"
    finally:
        store.close()

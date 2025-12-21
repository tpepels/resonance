"""Integration tests for audit richness and stability reports."""

from __future__ import annotations

import hashlib

from resonance.commands.audit import run_audit
from resonance.commands.stability import run_stability_report
from resonance.core.applier import ApplyStatus
from resonance.infrastructure.directory_store import DirectoryStateStore


def test_audit_includes_plan_and_apply_summaries(tmp_path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(
            "dir-1", tmp_path / "album", "a" * 64
        )
        store.record_plan_summary(record.dir_id, "p" * 64, "v1")
        store.record_apply_summary(record.dir_id, ApplyStatus.APPLIED.value, ())
        report = run_audit(store=store, dir_id=record.dir_id)
        assert report["last_plan_hash"] == "p" * 64
        assert report["last_plan_version"] == "v1"
        assert report["last_apply_status"] == ApplyStatus.APPLIED.value
        assert report["last_apply_errors"] == ()
    finally:
        store.close()


def test_stability_report_no_differences(tmp_path) -> None:
    report = {
        "dir_id": "dir-1",
        "state": "APPLIED",
        "signature_hash": "a" * 64,
        "last_plan_hash": hashlib.sha256(b"plan").hexdigest(),
    }
    result = run_stability_report(report, dict(report))
    assert result["same"] is True
    assert result["differences"] == []

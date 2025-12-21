"""Audit command - inspect a directory by dir_id."""

from __future__ import annotations


def run_audit(*, store, dir_id: str, apply_report=None) -> dict[str, str | None | tuple[str, ...]]:
    """Return audit information for a directory."""
    record = store.get(dir_id)
    if not record:
        return {"dir_id": dir_id, "state": "UNKNOWN"}
    report = {
        "dir_id": record.dir_id,
        "state": record.state.value,
        "signature_hash": record.signature_hash,
        "pinned_provider": record.pinned_provider,
        "pinned_release_id": record.pinned_release_id,
    }
    report.update(store.get_audit_artifacts(dir_id))
    if apply_report is not None:
        report["last_apply_errors"] = tuple(apply_report.errors)
    return report

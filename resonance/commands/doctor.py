"""Doctor command - validate store invariants."""

from __future__ import annotations


def run_doctor(*, store) -> dict[str, list[dict[str, str]]]:
    """Return a list of detected issues."""
    issues: list[dict[str, str]] = []
    for record in store.list_all():
        if not record.last_seen_path.exists():
            issues.append(
                {
                    "dir_id": record.dir_id,
                    "issue": "missing_path",
                    "path": str(record.last_seen_path),
                }
            )
    return {"issues": issues}

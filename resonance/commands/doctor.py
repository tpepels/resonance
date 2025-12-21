"""Doctor command - validate store invariants and environment sanity."""

from __future__ import annotations

from pathlib import Path

from resonance.settings import Settings, load_settings
from resonance.services.tag_writer import get_tag_writer

def run_doctor(
    *, store, config_path: Path | None = None, settings: Settings | None = None
) -> dict[str, list[dict[str, str]]]:
    """Return a list of detected issues."""
    issues: list[dict[str, str]] = []
    if config_path is not None and not config_path.exists():
        issues.append(
            {
                "issue": "missing_config",
                "path": str(config_path),
            }
        )
    if settings is None:
        settings = load_settings(config_path) if config_path else Settings()
    if settings.tag_writer_backend == "mutagen":
        try:
            get_tag_writer("mutagen")
        except Exception:
            issues.append({"issue": "missing_dependency", "dependency": "mutagen"})
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

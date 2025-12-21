"""Application settings and backend selection."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Optional


_DEFAULT_BACKEND = "meta-json"
_ALLOWED_BACKENDS = {"meta-json", "mutagen"}
_DEFAULT_SCORING_VERSION = "v1"
_DEFAULT_CONFLICT_POLICY = "FAIL"


@dataclass(frozen=True)
class Settings:
    tag_writer_backend: str = _DEFAULT_BACKEND
    identify_scoring_version: str = _DEFAULT_SCORING_VERSION
    plan_conflict_policy: str = _DEFAULT_CONFLICT_POLICY


def load_settings(path: Optional[Path]) -> Settings:
    if not path:
        return Settings()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text())
    backend = data.get("tag_writer_backend", _DEFAULT_BACKEND)
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(f"Unsupported tag writer backend: {backend}")
    return Settings(
        tag_writer_backend=backend,
        identify_scoring_version=data.get(
            "identify_scoring_version", _DEFAULT_SCORING_VERSION
        ),
        plan_conflict_policy=data.get("plan_conflict_policy", _DEFAULT_CONFLICT_POLICY),
    )


def default_config_path() -> Path:
    return Path.home() / ".config" / "resonance" / "settings.json"


def resolve_tag_writer_backend(
    *,
    cli_backend: Optional[str],
    env_backend: Optional[str],
    config_backend: str,
) -> str:
    if cli_backend:
        backend = cli_backend
    elif env_backend:
        backend = env_backend
    else:
        backend = config_backend
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(f"Unsupported tag writer backend: {backend}")
    return backend


def settings_hash(settings: Settings, stage: str) -> str:
    relevance = _relevance_sets().get(stage)
    if relevance is None:
        raise ValueError(f"Unknown settings hash stage: {stage}")
    payload = {key: getattr(settings, key) for key in relevance}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _relevance_sets() -> dict[str, tuple[str, ...]]:
    return {
        "identify": ("identify_scoring_version",),
        "plan": ("plan_conflict_policy",),
        "apply": ("tag_writer_backend",),
    }

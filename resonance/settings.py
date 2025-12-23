"""Application settings and backend selection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
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
    """Load settings from JSON config file, with environment variable overrides.

    Priority order:
    1. Environment variables (for appropriate settings)
    2. JSON config file
    3. Defaults

    Args:
        path: Path to JSON config file, or None to use defaults only

    Returns:
        Settings object with resolved values
    """
    # Load JSON config if available
    json_settings = {}
    if path and path.exists():
        json_settings = json.loads(path.read_text())

    # Resolve each setting with environment variable override
    backend = os.getenv("RESONANCE_TAG_WRITER_BACKEND") or json_settings.get("tag_writer_backend", _DEFAULT_BACKEND)
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(f"Unsupported tag writer backend: {backend}")

    scoring_version = json_settings.get("identify_scoring_version", _DEFAULT_SCORING_VERSION)
    conflict_policy = json_settings.get("plan_conflict_policy", _DEFAULT_CONFLICT_POLICY)

    return Settings(
        tag_writer_backend=backend,
        identify_scoring_version=scoring_version,
        plan_conflict_policy=conflict_policy,
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

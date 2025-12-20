"""Application settings and backend selection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional


_DEFAULT_BACKEND = "meta-json"
_ALLOWED_BACKENDS = {"meta-json", "mutagen"}


@dataclass(frozen=True)
class Settings:
    tag_writer_backend: str = _DEFAULT_BACKEND


def load_settings(path: Optional[Path]) -> Settings:
    if not path:
        return Settings()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text())
    backend = data.get("tag_writer_backend", _DEFAULT_BACKEND)
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(f"Unsupported tag writer backend: {backend}")
    return Settings(tag_writer_backend=backend)


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

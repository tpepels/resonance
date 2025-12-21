"""Directory state records and transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class DirectoryState(str, Enum):
    """Directory processing lifecycle states."""

    NEW = "NEW"
    QUEUED_PROMPT = "QUEUED_PROMPT"
    JAILED = "JAILED"
    RESOLVED_AUTO = "RESOLVED_AUTO"
    RESOLVED_USER = "RESOLVED_USER"
    PLANNED = "PLANNED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DirectoryRecord:
    """Persisted directory state keyed by dir_id."""

    dir_id: str
    last_seen_path: Path
    signature_hash: str
    state: DirectoryState
    signature_version: int = 1
    pinned_provider: Optional[str] = None
    pinned_release_id: Optional[str] = None
    pinned_confidence: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

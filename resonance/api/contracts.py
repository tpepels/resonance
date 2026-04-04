"""Typed request and response contracts for the Resonance API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApiError:
    """Normalized API error payload."""

    error_type: str
    message: str


@dataclass(frozen=True)
class ApiResult:
    """Normalized API result envelope for command-like operations."""

    command: str
    exit_code: int
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    events: tuple[str, ...] = ()
    error: ApiError | None = None

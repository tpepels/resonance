"""Typed request and response contracts for the Resonance API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from typing import Any


API_CONTRACT_VERSION = "v1"
CommandName = Literal[
    "app",
    "scan",
    "resolve",
    "prompt",
    "identify",
    "plan",
    "apply",
    "decide",
    "audit",
    "doctor",
    "rollback",
    "unjail",
]


@dataclass(frozen=True)
class BaseRequest:
    """Base request contract for bounded API operations."""

    command: CommandName
    json_output: bool = False
    mode: Literal["interactive", "automation", "admin"] = "interactive"


@dataclass(frozen=True)
class ScanRequest(BaseRequest):
    """Request model for scan operation."""

    command: CommandName = "scan"
    library_root: Path = Path(".")
    state_db: Path = Path("state.db")


@dataclass(frozen=True)
class ResolveRequest(BaseRequest):
    """Request model for resolve operation."""

    command: CommandName = "resolve"
    library_root: Path = Path(".")
    state_db: Path = Path("state.db")
    cache_db: Path | None = None
    offline: bool = False
    auto_probable: bool = False
    auto_probable_min_gap: float = 0.15


@dataclass(frozen=True)
class DecideRequest(BaseRequest):
    """Request model for decide orchestration operation."""

    command: CommandName = "decide"
    library_root: Path = Path(".")
    state_db: Path = Path("state.db")
    cache_db: Path | None = None
    offline: bool = False
    decisions_file: Path | None = None
    auto_probable: bool = False
    auto_probable_min_gap: float = 0.15
    headless: bool = False
    plan_dir: Path | None = None
    fail_on_prompt: bool = False
    fail_on_warning: bool = False


@dataclass(frozen=True)
class ApiError:
    """Normalized API error payload."""

    error_type: str
    message: str


@dataclass(frozen=True)
class ApiResult:
    """Normalized API result envelope for command-like operations."""

    command: CommandName
    exit_code: int
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    events: tuple[str, ...] = ()
    error: ApiError | None = None
    contract_version: str = API_CONTRACT_VERSION

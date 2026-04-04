"""Invocation context and policy for API calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InvocationMode(str, Enum):
    """Execution profile for bounded API invocations."""

    INTERACTIVE = "interactive"
    AUTOMATION = "automation"
    ADMIN = "admin"


@dataclass(frozen=True)
class InvocationContext:
    """Per-call policy context used by the bounded API."""

    mode: InvocationMode = InvocationMode.INTERACTIVE
    json_output: bool = False

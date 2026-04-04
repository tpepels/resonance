"""Output capture utilities for API execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class OutputCollector:
    """Collect command output in-memory while optionally mirroring to sink."""

    sink: Callable[[str], None] | None = None
    lines: list[str] = field(default_factory=list)

    def write(self, line: str) -> None:
        self.lines.append(line)
        if self.sink is not None:
            self.sink(line)

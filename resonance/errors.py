"""Error taxonomy and exit code mapping for CLI."""

from __future__ import annotations


class ResonanceError(Exception):
    """Base error for deterministic CLI exit codes."""

    exit_code: int = 1


class ValidationError(ResonanceError):
    """Invalid user input or command usage."""

    exit_code = 2


class RuntimeFailure(ResonanceError):
    """Unexpected runtime failure."""

    exit_code = 1


class IOFailure(ResonanceError):
    """Filesystem or I/O failure."""

    exit_code = 3


def exit_code_for_exception(exc: BaseException) -> int:
    """Resolve a deterministic exit code for an exception."""
    if isinstance(exc, ResonanceError):
        return exc.exit_code
    if isinstance(exc, OSError):
        return IOFailure.exit_code
    return RuntimeFailure.exit_code

"""Guards to ensure CLI routes through bounded API service."""

from __future__ import annotations

import inspect

from resonance import cli


def test_cli_uses_service_execution_path() -> None:
    src = inspect.getsource(cli.main)
    assert "build_service" in src
    assert "service.execute(args)" in src


def test_cli_no_direct_command_dispatch_blocks() -> None:
    src = inspect.getsource(cli.main)
    forbidden = [
        "args.command == \"scan\"",
        "args.command == \"resolve\"",
        "args.command == \"prompt\"",
        "args.command == \"identify\"",
        "args.command == \"plan\"",
        "args.command == \"apply\"",
        "args.command == \"decide\"",
    ]
    for token in forbidden:
        assert token not in src

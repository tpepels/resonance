"""Regenerate golden corpus snapshots."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = dict(os.environ)
    env["REGEN_GOLDEN"] = "1"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_golden_corpus.py",
        "-q",
    ]
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())

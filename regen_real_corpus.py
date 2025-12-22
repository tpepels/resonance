#!/usr/bin/env python3
"""Regenerate real-world corpus snapshots.

This script runs the real-world corpus test with REGEN_REAL_CORPUS=1 to
regenerate expected snapshots (state/layout/tags).

Usage:
    python regen_real_corpus.py

Prerequisites:
    - tests/real_corpus/input/ must be populated via scripts/snapshot_real_corpus.sh
    - First regen may require online mode to populate provider cache
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    """Run real-world corpus test in regen mode."""
    env = os.environ.copy()
    env["REGEN_REAL_CORPUS"] = "1"
    env["RUN_REAL_CORPUS"] = "1"

    print("==> Regenerating real-world corpus snapshots")
    print("    This will overwrite:")
    print("      - tests/real_corpus/expected_state.json")
    print("      - tests/real_corpus/expected_layout.json")
    print("      - tests/real_corpus/expected_tags.json")
    print("")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_real_world_corpus.py",
            "-v",
        ],
        env=env,
    )

    if result.returncode == 0:
        print("")
        print("==> Snapshots regenerated successfully!")
        print("    Review changes with: git diff tests/real_corpus/")
        print("")
    else:
        print("")
        print("==> Regeneration failed. See errors above.")
        print("")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

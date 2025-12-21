"""Integration test configuration and fixtures.

This module enforces the golden corpus gate (Phase A.3).
"""

from __future__ import annotations

import os
import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Reorder tests to run golden corpus first as a blocking gate.

    Phase A.3 requirement: Golden corpus must run before all other V3 tests.
    If golden corpus fails, it should be caught early before running other tests.
    """
    golden_corpus_tests: list[pytest.Item] = []
    other_tests: list[pytest.Item] = []

    for item in items:
        if "test_golden_corpus" in item.nodeid:
            golden_corpus_tests.append(item)
        else:
            other_tests.append(item)

    # Golden corpus first, then everything else
    items[:] = golden_corpus_tests + other_tests


@pytest.fixture(scope="session", autouse=True)
def warn_about_golden_regen() -> None:
    """Warn when REGEN_GOLDEN=1 is set.

    Phase A.3 requirement: Snapshot regeneration requires explicit justification.
    This warning ensures developers are aware they're modifying the invariant baseline.
    """
    if os.environ.get("REGEN_GOLDEN") == "1":
        # Print to stderr instead of warnings.warn to avoid pytest treating it as an error
        import sys
        message = (
            "\n" + "=" * 80 + "\n"
            "WARNING: REGEN_GOLDEN=1 is set!\n\n"
            "You are regenerating golden corpus snapshots. This modifies the\n"
            "determinism baseline for the entire project.\n\n"
            "Phase A.3 requirement: Snapshot regeneration requires explicit\n"
            "justification in commit messages or PR descriptions.\n\n"
            "Valid reasons for regeneration:\n"
            "  - Bug fix that changes legitimate output (e.g., fixing incorrect\n"
            "    canonicalization that was generating wrong artist names)\n"
            "  - Intentional behavior change with documented rationale\n"
            "  - Adding new scenarios (existing snapshots should not change)\n\n"
            "Invalid reasons:\n"
            "  - \"Tests were failing\" (fix the code, not the snapshots)\n"
            "  - \"Output changed\" (investigate WHY it changed first)\n"
            "  - No explanation\n\n"
            "After regeneration:\n"
            "  1. Review EVERY changed snapshot file in git diff\n"
            "  2. Verify changes are intentional and correct\n"
            "  3. Document justification in commit message\n"
            "  4. Run tests WITHOUT REGEN_GOLDEN=1 to verify they pass\n"
            + "=" * 80 + "\n"
        )
        print(message, file=sys.stderr, flush=True)

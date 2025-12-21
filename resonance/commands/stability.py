"""Stability report generator for stored audit artifacts."""

from __future__ import annotations

from typing import Any


def run_stability_report(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    """Compare two audit reports and return deterministic diff summary."""
    keys = sorted(set(report_a.keys()) | set(report_b.keys()))
    diffs: list[dict[str, Any]] = []
    for key in keys:
        left = report_a.get(key)
        right = report_b.get(key)
        if left != right:
            diffs.append({"field": key, "left": left, "right": right})
    return {"differences": diffs, "same": len(diffs) == 0}

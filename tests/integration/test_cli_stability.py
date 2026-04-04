"""CLI regression test for the stability command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

def test_cli_stability_command(tmp_path: Path) -> None:
    # Create two minimal audit report files
    report_a = tmp_path / "report_a.json"
    report_b = tmp_path / "report_b.json"
    data_a = {"dir_id": "dir-1", "state": "APPLIED", "signature_hash": "abc123"}
    data_b = {"dir_id": "dir-1", "state": "APPLIED", "signature_hash": "abc123"}
    report_a.write_text(json.dumps(data_a))
    report_b.write_text(json.dumps(data_b))

    # Should report no differences
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "stability",
            str(report_a),
            str(report_b),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["same"] is True
    assert output["differences"] == []

    # Now introduce a difference
    data_b["signature_hash"] = "def456"
    report_b.write_text(json.dumps(data_b))
    result2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "stability",
            str(report_a),
            str(report_b),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result2.returncode == 0
    output2 = json.loads(result2.stdout)
    assert output2["same"] is False
    assert any(d["field"] == "signature_hash" for d in output2["differences"])

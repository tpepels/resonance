"""JSON schema stability checks for command envelopes."""

from __future__ import annotations

import json
from pathlib import Path

from resonance.commands.scan import run_scan
from resonance.infrastructure.directory_store import DirectoryStateStore


def test_scan_json_envelope_stability(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()

    state_db = tmp_path / "state.db"
    store = DirectoryStateStore(state_db)
    try:
        from argparse import Namespace

        args = Namespace(library_root=library, state_db=state_db, json=True)
        captured: list[str] = []
        code = run_scan(args, store=store, output_sink=captured.append)
        assert code == 0
        assert len(captured) == 1

        payload = json.loads(captured[0])
        assert payload["schema_version"] == "v1"
        assert payload["command"] == "scan"
        assert isinstance(payload["data"], dict)
        assert "status" in payload["data"]
        assert "library_root" in payload["data"]
    finally:
        store.close()

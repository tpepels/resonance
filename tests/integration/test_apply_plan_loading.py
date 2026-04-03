"""Behavioural proof: run_apply loads plan from file and executes apply_plan.

Before this fix, run_apply with the default apply_fn=apply_plan would either:
  - raise TypeError (`apply_fn(tag_writer=writer, backend=backend)` before the guard), OR
  - return exit code 1 via the `plan = None  # TODO` stub.

After the fix, run_apply loads the plan from disk using load_plan() and calls
apply_plan() correctly, returning exit code 0 on success.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.apply import run_apply
from resonance.core.artifacts import serialize_plan
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from tests.helpers.fs import AudioStubSpec, create_audio_stub


_DIR_ID = "dir-apply-proof"
_RELEASE_ID = "mb-apply-proof-1"


def _make_args(
    plan: Path,
    state_db: Path,
    *,
    no_dry_run: bool = False,
    tag_patch: Path | None = None,
    library_root: Path | None = None,
) -> Namespace:
    return Namespace(
        plan=plan,
        state_db=state_db,
        config=None,
        tag_writer_backend=None,
        no_dry_run=no_dry_run,
        tag_patch=tag_patch,
        library_root=library_root,
        json=False,
    )


def _build_resolved_plan_and_store(
    tmp_path: Path,
) -> tuple[Plan, Path, DirectoryStateStore]:
    """Create a source dir with one audio stub, a matching plan, and a PLANNED store record."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    dest_dir = tmp_path / "library"
    dest_dir.mkdir()

    stub_path = create_audio_stub(
        source_dir / "01 - Track A.flac",
        AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-apply-001", duration_seconds=200),
    )

    # Compute real signature — apply_plan will verify this against the source file
    sig_hash = dir_signature([stub_path]).signature_hash

    abs_dest = dest_dir / "Test Artist" / "Test Album" / "01 - Track A.flac"

    plan = Plan(
        dir_id=_DIR_ID,
        source_path=source_dir,
        signature_hash=sig_hash,
        provider="musicbrainz",
        release_id=_RELEASE_ID,
        release_title="Test Album",
        release_artist="Test Artist",
        destination_path=dest_dir / "Test Artist" / "Test Album",
        operations=(
            TrackOperation(
                track_position=1,
                source_path=stub_path,
                destination_path=abs_dest,
                track_title="Track A",
            ),
        ),
        non_audio_policy="MOVE_WITH_ALBUM",
        plan_version="v1",
    )

    state_db = tmp_path / "state.db"
    store = DirectoryStateStore(state_db)
    store.get_or_create(_DIR_ID, source_dir, sig_hash)
    store.set_state(
        _DIR_ID,
        DirectoryState.RESOLVED_AUTO,
        pinned_provider="musicbrainz",
        pinned_release_id=_RELEASE_ID,
    )
    store.set_state(
        _DIR_ID,
        DirectoryState.PLANNED,
        pinned_provider="musicbrainz",
        pinned_release_id=_RELEASE_ID,
    )
    # Store is open and in PLANNED state — hand it directly to run_apply
    return plan, state_db, store


def test_apply_loads_plan_from_json_and_returns_zero(tmp_path: Path) -> None:
    """run_apply with real apply_plan returns exit code 0 in dry-run mode.

    BEFORE fix: raised TypeError or returned exit code 1 (plan = None stub).
    AFTER fix: loads plan via load_plan(), calls apply_plan(), returns 0.
    """
    plan, state_db, store = _build_resolved_plan_and_store(tmp_path)

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(serialize_plan(plan))

    captured: list[str] = []
    exit_code = run_apply(
        _make_args(plan_path, state_db, no_dry_run=False, library_root=tmp_path / "library"),
        store=store,
        output_sink=captured.append,
    )

    assert exit_code == 0, f"Expected 0, got {exit_code}. Output:\n" + "\n".join(captured)
    combined = "\n".join(captured)
    # Confirm dry_run mode was active
    assert "dry_run=True" in combined
    # Confirm the plan was actually processed (status emitted)
    assert "APPLIED" in combined or "NOOP" in combined


def test_apply_returns_plan_load_error_on_missing_file(tmp_path: Path) -> None:
    """run_apply returns exit code 1 with a plan load error when plan JSON is absent.

    This replaces the old PLAN_LOAD_NOT_IMPLEMENTED placeholder error.
    """
    state_db = tmp_path / "state.db"
    store = DirectoryStateStore(state_db)

    captured: list[str] = []
    exit_code = run_apply(
        _make_args(tmp_path / "nonexistent.json", state_db),
        store=store,
        output_sink=captured.append,
    )

    assert exit_code == 1
    combined = "\n".join(captured)
    # Human output contains "plan load error" (structured status in JSON payload)
    assert "plan load error" in combined.lower()
    # Old behaviour placeholder must not appear
    assert "NOT_IMPLEMENTED" not in combined


def test_apply_no_dry_run_moves_files(tmp_path: Path) -> None:
    """run_apply with --no-dry-run actually moves files to the destination."""
    plan, state_db, store = _build_resolved_plan_and_store(tmp_path)

    # Identify source and destination from the single operation
    op = plan.operations[0]
    assert op.source_path.exists(), "Stub source file must exist"
    assert not op.destination_path.exists(), "Destination must not exist before apply"

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(serialize_plan(plan))

    captured: list[str] = []
    exit_code = run_apply(
        _make_args(plan_path, state_db, no_dry_run=True, library_root=tmp_path / "library"),
        store=store,
        output_sink=captured.append,
    )

    assert exit_code == 0, f"Expected 0, got {exit_code}. Output:\n" + "\n".join(captured)
    combined = "\n".join(captured)
    assert "dry_run=False" in combined
    # File was actually moved
    assert op.destination_path.exists(), "Destination file must exist after real apply"
    assert not op.source_path.exists(), "Source file must no longer exist after real apply"

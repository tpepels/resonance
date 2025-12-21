"""Unit tests for artifact loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance.core.artifacts import load_plan, load_tag_patch


def _write_plan(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def _write_tag_patch(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def _base_plan(tmp_path: Path) -> dict:
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    return {
        "dir_id": "dir_1",
        "source_path": str(source),
        "signature_hash": "a" * 64,
        "provider": "musicbrainz",
        "release_id": "mb-1",
        "release_title": "Album",
        "release_artist": "Artist",
        "destination_path": "Artist/Album",
        "operations": [
            {
                "track_position": 1,
                "source_path": "01 - Track A.flac",
                "destination_path": "Artist/Album/01 - Track A.flac",
                "track_title": "Track A",
            }
        ],
        "non_audio_policy": "MOVE_WITH_ALBUM",
        "plan_version": "v1",
        "is_compilation": False,
        "compilation_reason": None,
        "is_classical": False,
        "conflict_policy": "FAIL",
        "settings_hash": None,
    }


def test_load_plan_rejects_path_traversal_source(tmp_path: Path) -> None:
    payload = _base_plan(tmp_path)
    payload["operations"][0]["source_path"] = "../evil.flac"
    plan_path = _write_plan(tmp_path / "plan.json", payload)
    with pytest.raises(ValueError, match="Path traversal not allowed"):
        load_plan(plan_path, allowed_roots=(tmp_path / "library",))


def test_load_plan_rejects_destination_outside_root(tmp_path: Path) -> None:
    payload = _base_plan(tmp_path)
    payload["destination_path"] = "/outside/album"
    payload["operations"][0]["destination_path"] = "/outside/album/track.flac"
    plan_path = _write_plan(tmp_path / "plan.json", payload)
    with pytest.raises(ValueError, match="Path outside allowed roots"):
        load_plan(plan_path, allowed_roots=(tmp_path / "library",))


def test_load_plan_rejects_invalid_dir_id(tmp_path: Path) -> None:
    payload = _base_plan(tmp_path)
    payload["dir_id"] = "dir/1"
    plan_path = _write_plan(tmp_path / "plan.json", payload)
    with pytest.raises(ValueError, match="Invalid dir_id format"):
        load_plan(plan_path, allowed_roots=(tmp_path / "library",))


def test_plan_from_json_rejects_path_traversal(tmp_path: Path) -> None:
    from resonance.core.planner import Plan

    payload = _base_plan(tmp_path)
    payload["operations"][0]["destination_path"] = "../escape.flac"
    plan_path = _write_plan(tmp_path / "plan.json", payload)
    with pytest.raises(ValueError, match="Path traversal not allowed"):
        Plan.from_json(plan_path, allowed_roots=(tmp_path / "library",))


def test_load_tag_patch_rejects_invalid_release_id(tmp_path: Path) -> None:
    payload = {
        "dir_id": "dir_1",
        "provider": "musicbrainz",
        "release_id": "mb/1",
        "version": "v1",
        "allowed": True,
        "reason": None,
        "album_patch": {"set_tags": {"album": "Album"}},
        "track_patches": [{"track_position": 1, "set_tags": {"title": "Track A"}}],
        "provenance_tags": {},
        "allow_overwrite": False,
        "overwrite_fields": [],
    }
    tag_path = _write_tag_patch(tmp_path / "tag.json", payload)
    with pytest.raises(ValueError, match="Invalid release_id format"):
        load_tag_patch(tag_path)

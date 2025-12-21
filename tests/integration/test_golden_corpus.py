"""Golden corpus integration test for V3 invariants."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil

from resonance import __version__
from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import DirectoryEvidence, TrackEvidence
from resonance.core.identity.signature import dir_id, dir_signature
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import LibraryScanner
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.golden.corpus_builder import build_corpus
from tests.golden.provider_fixtures import load_provider_fixtures


EXPECTED_ROOT = Path(__file__).resolve().parents[1] / "golden" / "expected"
PROV_KEYS = (
    "resonance.prov.version",
    "resonance.prov.tool",
    "resonance.prov.tool_version",
    "resonance.prov.dir_id",
    "resonance.prov.pinned_provider",
    "resonance.prov.pinned_release_id",
    "resonance.prov.applied_at_utc",
)


def _evidence_from_files(audio_files: list[Path]) -> DirectoryEvidence:
    tracks: list[TrackEvidence] = []
    total_duration = 0
    for path in sorted(audio_files):
        data = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())
        duration = data.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tags = data.get("tags")
        tracks.append(
            TrackEvidence(
                fingerprint_id=data.get("fingerprint_id"),
                duration_seconds=duration,
                existing_tags=tags if isinstance(tags, dict) else {},
            )
        )
    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


class FixtureProvider:
    """Deterministic provider stub keyed by fingerprint id."""

    def __init__(self, fixtures: dict[str, dict[str, tuple]]) -> None:
        self._by_fingerprint: dict[str, object] = {}
        self._by_release_id: dict[str, object] = {}
        for scenarios in fixtures.values():
            for releases in scenarios.values():
                for release in releases:
                    self._by_release_id[release.release_id] = release
                    for track in release.tracks:
                        if track.fingerprint_id:
                            self._by_fingerprint[track.fingerprint_id] = release
        self.search_by_fingerprints_calls: list[tuple[str, ...]] = []
        self.search_by_metadata_calls = 0

    def search_by_fingerprints(self, fingerprints: list[str]):
        self.search_by_fingerprints_calls.append(tuple(fingerprints))
        if not fingerprints:
            return []
        release = self._by_fingerprint.get(fingerprints[0])
        return [release] if release else []

    def search_by_metadata(self, artist, album, track_count):
        self.search_by_metadata_calls += 1
        return []

    def release_by_id(self, release_id: str):
        return self._by_release_id[release_id]


def _snapshot_path(scenario: str, name: str) -> Path:
    return EXPECTED_ROOT / scenario / name


def _assert_or_write_snapshot(path: Path, payload: object, regen: bool) -> None:
    if regen:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        return
    if not path.exists():
        raise FileNotFoundError(f"Missing snapshot: {path}. Set REGEN_GOLDEN=1 to create.")
    expected = json.loads(path.read_text())
    assert payload == expected


def _read_tags(writer: MetaJsonTagWriter, file_path: Path) -> dict[str, str]:
    return writer.read_tags(file_path)


def _filter_tags(tags: dict[str, str]) -> dict[str, str]:
    filtered = {key: tags[key] for key in PROV_KEYS if key in tags}
    for key in ("album", "albumartist", "title", "tracknumber"):
        if key in tags:
            filtered[key] = tags[key]
    return filtered


def _assert_plan_hash(tags: dict[str, str]) -> None:
    plan_hash = tags.get("resonance.prov.plan_hash")
    assert plan_hash is not None
    assert re.fullmatch(r"[0-9a-f]{64}", plan_hash)


def test_golden_corpus_end_to_end(tmp_path: Path) -> None:
    corpus_root = tmp_path / "library"
    fixtures = build_corpus(corpus_root)
    provider_fixtures = load_provider_fixtures()
    provider = FixtureProvider(provider_fixtures)

    # Identity invariants: path rename + tag variants must not change dir_id.
    renamed_root = tmp_path / "library_renamed"
    renamed_root.mkdir(parents=True, exist_ok=True)
    source_variants = fixtures["name_variants"].path
    renamed_variants = renamed_root / "renamed_variants"
    shutil.copytree(source_variants, renamed_variants)
    original_audio = sorted(source_variants.glob("*.flac"))
    renamed_audio = sorted(renamed_variants.glob("*.flac"))
    assert dir_id(dir_signature(original_audio)) == dir_id(dir_signature(renamed_audio))

    variant_meta = renamed_audio[0].with_suffix(renamed_audio[0].suffix + ".meta.json")
    variant_data = json.loads(variant_meta.read_text())
    tags = variant_data.get("tags", {})
    if isinstance(tags, dict):
        tags["artist"] = "Bjork"
        variant_data["tags"] = tags
    variant_meta.write_text(json.dumps(variant_data, indent=2))
    assert dir_id(dir_signature(original_audio)) == dir_id(dir_signature(renamed_audio))

    output_root = tmp_path / "organized"
    scanner = LibraryScanner([corpus_root])
    batches = sorted(scanner.iter_directories(), key=lambda b: b.dir_id)

    regen = os.environ.get("REGEN_GOLDEN") == "1"
    fixed_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    store = DirectoryStateStore(tmp_path / "state.db")
    writer = MetaJsonTagWriter()
    failures: list[str] = []
    try:
        for batch in batches:
            scenario = batch.directory.name
            release = provider_fixtures["musicbrainz"][scenario][0]

            evidence = _evidence_from_files(batch.files)
            outcome = resolve_directory(
                dir_id=batch.dir_id,
                path=batch.directory,
                signature_hash=batch.signature_hash,
                evidence=evidence,
                store=store,
                provider_client=provider,
            )
            assert outcome.state == DirectoryState.RESOLVED_AUTO

            plan = plan_directory(
                dir_id=batch.dir_id,
                store=store,
                pinned_release=release,
                source_files=batch.files,
            )
            store.set_state(
                batch.dir_id,
                DirectoryState.PLANNED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )

            tag_patch = build_tag_patch(
                plan,
                release,
                DirectoryState.RESOLVED_AUTO,
                now_fn=lambda: fixed_now,
            )

            report = apply_plan(
                plan,
                tag_patch,
                store,
                allowed_roots=(output_root,),
                dry_run=False,
                tag_writer=writer,
            )
            if report.status != ApplyStatus.APPLIED:
                failures.append(
                    f"{scenario}: apply status {report.status.value} errors={report.errors}"
                )
                if output_root.exists():
                    shutil.rmtree(output_root)
                continue

            # Idempotency: second apply is a no-op.
            store.set_state(
                plan.dir_id,
                DirectoryState.PLANNED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
            rerun = apply_plan(
                plan,
                tag_patch,
                store,
                allowed_roots=(output_root,),
                dry_run=False,
                tag_writer=writer,
            )
            assert rerun.status == ApplyStatus.NOOP_ALREADY_APPLIED

            # Layout snapshot (audio + extras, excluding .meta.json)
            actual_layout = sorted(
                str(path.relative_to(output_root))
                for path in output_root.rglob("*")
                if path.is_file() and path.suffix != ".json"
            )
            try:
                _assert_or_write_snapshot(
                    _snapshot_path(scenario, "expected_layout.json"),
                    actual_layout,
                    regen,
                )
            except FileNotFoundError as exc:
                failures.append(f"{scenario}: {exc}")
                if output_root.exists():
                    shutil.rmtree(output_root)
                continue

            # Tags snapshot (filtered, stable keys)
            tag_entries: list[dict[str, object]] = []
            for path in sorted(output_root.rglob("*.flac")):
                tags = _read_tags(writer, path)
                _assert_plan_hash(tags)
                tag_entries.append(
                    {
                        "path": str(path.relative_to(output_root)),
                        "tags": _filter_tags(tags),
                    }
                )
            try:
                _assert_or_write_snapshot(
                    _snapshot_path(scenario, "expected_tags.json"),
                    {"tracks": tag_entries},
                    regen,
                )
            except FileNotFoundError as exc:
                failures.append(f"{scenario}: {exc}")
                if output_root.exists():
                    shutil.rmtree(output_root)
                continue

            # State snapshot
            record = store.get(batch.dir_id)
            assert record is not None
            try:
                _assert_or_write_snapshot(
                    _snapshot_path(scenario, "expected_state.json"),
                    {
                        "pinned_provider": record.pinned_provider,
                        "pinned_release_id": record.pinned_release_id,
                        "state": record.state.value,
                    },
                    regen,
                )
            except FileNotFoundError as exc:
                failures.append(f"{scenario}: {exc}")
                if output_root.exists():
                    shutil.rmtree(output_root)
                continue

            # Reset output root for next scenario
            if output_root.exists():
                shutil.rmtree(output_root)
        if failures:
            raise AssertionError(
                "Golden corpus failures:\n" + "\n".join(failures)
            )
    finally:
        store.close()

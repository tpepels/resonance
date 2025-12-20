"""Applier - transactional execution of plans and tag patches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil
from typing import Optional

from resonance.core.enricher import TagPatch
from resonance.core.planner import Plan
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter, TagWriter


class ApplyStatus(str, Enum):
    """Apply result status."""

    APPLIED = "APPLIED"
    NOOP_ALREADY_APPLIED = "NOOP_ALREADY_APPLIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class FileOpResult:
    source_path: Path
    destination_path: Path
    status: str
    error: Optional[str] = None


@dataclass(frozen=True)
class TagOpResult:
    file_path: Path
    tags_set: tuple[str, ...]
    tags_skipped: tuple[str, ...]
    error: Optional[str] = None


@dataclass(frozen=True)
class ApplyReport:
    dir_id: str
    plan_version: str
    tagpatch_version: Optional[str]
    status: ApplyStatus
    dry_run: bool
    file_ops: tuple[FileOpResult, ...]
    tag_ops: tuple[TagOpResult, ...]
    errors: tuple[str, ...]
    rollback_attempted: bool
    rollback_success: bool


_SUPPORTED_PLAN_VERSIONS = frozenset({"v1"})
_SUPPORTED_TAGPATCH_VERSIONS = frozenset({"v1"})


def _is_within(parent: Path, child: Path) -> bool:
    parent = parent.resolve()
    child = child.resolve()
    return parent == child or parent in child.parents


def _resolve_source_path(source_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return source_root / path


def _resolve_destination_path(
    path: Path, allowed_roots: tuple[Path, ...] | None
) -> Path:
    if path.is_absolute():
        return path
    if not allowed_roots or len(allowed_roots) != 1:
        raise ValueError("Relative destination path requires a single allowed_root")
    return allowed_roots[0] / path


def _sidecar_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".meta.json")


def apply_plan(
    plan: Plan,
    tag_patch: TagPatch | None,
    store: DirectoryStateStore,
    *,
    allowed_roots: tuple[Path, ...] | None = None,
    dry_run: bool = True,
    tag_writer: TagWriter | None = None,
) -> ApplyReport:
    """Apply a plan (and optional tag patch) with deterministic preflight."""
    errors: list[str] = []
    record = store.get(plan.dir_id)
    tag_writer = tag_writer or MetaJsonTagWriter()

    def _fail(report_errors: list[str]) -> ApplyReport:
        if record:
            store.set_state(
                plan.dir_id,
                DirectoryState.FAILED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
        return ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.FAILED,
            dry_run=dry_run,
            file_ops=(),
            tag_ops=(),
            errors=tuple(report_errors),
            rollback_attempted=False,
            rollback_success=False,
        )

    if plan.plan_version not in _SUPPORTED_PLAN_VERSIONS:
        errors.append(f"Unsupported plan version: {plan.plan_version}")
    if tag_patch and tag_patch.version not in _SUPPORTED_TAGPATCH_VERSIONS:
        errors.append(f"Unsupported tag patch version: {tag_patch.version}")
    if not record:
        errors.append(f"Unknown dir_id: {plan.dir_id}")
    elif record.state != DirectoryState.PLANNED:
        errors.append(f"Directory state must be PLANNED, got {record.state.value}")
    elif record.signature_hash != plan.signature_hash:
        errors.append("Signature hash mismatch between plan and store")

    if tag_patch:
        if tag_patch.dir_id != plan.dir_id:
            errors.append("Tag patch dir_id does not match plan")
        if tag_patch.provider != plan.provider or tag_patch.release_id != plan.release_id:
            errors.append("Tag patch release does not match plan")

    if errors:
        return _fail(errors)

    ordered_ops = sorted(plan.operations, key=lambda op: op.track_position)
    file_moves: list[tuple[Path, Path]] = []
    try:
        for op in ordered_ops:
            src = _resolve_source_path(plan.source_path, op.source_path)
            dest = _resolve_destination_path(op.destination_path, allowed_roots)
            file_moves.append((src, dest))
            sidecar = _sidecar_path(src)
            if sidecar.exists():
                file_moves.append((sidecar, _sidecar_path(dest)))
    except ValueError as exc:
        return _fail([str(exc)])

    source_exists = [src.exists() for src, _ in file_moves]
    dest_exists = [dest.exists() for _, dest in file_moves]
    if all(not exists for exists in source_exists) and all(dest_exists):
        return ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.NOOP_ALREADY_APPLIED,
            dry_run=dry_run,
            file_ops=(),
            tag_ops=(),
            errors=(),
            rollback_attempted=False,
            rollback_success=False,
        )

    if not plan.source_path.exists() or not plan.source_path.is_dir():
        errors.append("Plan source_path does not exist or is not a directory")

    if plan.non_audio_policy == "MOVE_WITH_ALBUM" and not errors:
        try:
            dest_root = _resolve_destination_path(plan.destination_path, allowed_roots)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            audio_sources = {src.resolve() for src, _ in file_moves}
            for entry in sorted(plan.source_path.iterdir(), key=lambda p: p.name):
                if not entry.is_file():
                    continue
                if entry.resolve() in audio_sources:
                    continue
                file_moves.append((entry, dest_root / entry.name))

    for src, _ in file_moves:
        if not src.exists():
            errors.append(f"Missing source file: {src}")
        elif not _is_within(plan.source_path, src):
            errors.append(f"Source file outside source_path: {src}")

    if allowed_roots:
        for _, dest in file_moves:
            if not any(_is_within(root, dest) for root in allowed_roots):
                errors.append(f"Destination outside allowed roots: {dest}")

    for _, dest in file_moves:
        if dest.exists():
            errors.append(f"Destination already exists: {dest}")

    if errors:
        return _fail(errors)

    file_ops: list[FileOpResult] = []
    completed_moves: list[tuple[Path, Path]] = []
    if dry_run:
        for src, dest in file_moves:
            file_ops.append(
                FileOpResult(source_path=src, destination_path=dest, status="DRY_RUN")
            )
        return ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.APPLIED,
            dry_run=True,
            file_ops=tuple(file_ops),
            tag_ops=(),
            errors=(),
            rollback_attempted=False,
            rollback_success=False,
        )

    rollback_attempted = False
    rollback_success = False
    try:
        for src, dest in file_moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            completed_moves.append((src, dest))
            file_ops.append(
                FileOpResult(source_path=src, destination_path=dest, status="MOVED")
            )
    except Exception as exc:  # noqa: BLE001 - surface rollback behavior
        file_ops.append(
            FileOpResult(
                source_path=src,
                destination_path=dest,
                status="FAILED",
                error=str(exc),
            )
        )
        rollback_attempted = True
        rollback_success = True
        for moved_src, moved_dest in reversed(completed_moves):
            try:
                moved_src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(moved_dest), str(moved_src))
            except Exception:
                rollback_success = False
        errors.append(f"Move failed: {exc}")
        store.set_state(
            plan.dir_id,
            DirectoryState.FAILED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        return ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.FAILED,
            dry_run=False,
            file_ops=tuple(file_ops),
            tag_ops=(),
            errors=tuple(errors),
            rollback_attempted=rollback_attempted,
            rollback_success=rollback_success,
        )

    tag_ops: list[TagOpResult] = []
    if tag_patch and tag_patch.allowed:
        tags_errors: list[str] = []
        rollback_attempted = False
        rollback_success = False
        by_position = {op.track_position: op for op in ordered_ops}
        album_tags = tag_patch.album_patch.set_tags if tag_patch.album_patch else {}
        for track_patch in tag_patch.track_patches:
            op = by_position.get(track_patch.track_position)
            if not op:
                tags_errors.append(
                    f"Missing track position in plan: {track_patch.track_position}"
                )
                continue
            try:
                dest = _resolve_destination_path(op.destination_path, allowed_roots)
                write_result = tag_writer.apply_patch(
                    dest,
                    {**album_tags, **track_patch.set_tags},
                    tag_patch.allow_overwrite,
                )
                tag_ops.append(
                    TagOpResult(
                        file_path=write_result.file_path,
                        tags_set=tuple(sorted(write_result.tags_set)),
                        tags_skipped=tuple(sorted(write_result.tags_skipped)),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - surface tag error
                tags_errors.append(f"Tag write failed for {dest}: {exc}")
                tag_ops.append(
                    TagOpResult(
                        file_path=dest,
                        tags_set=(),
                        tags_skipped=(),
                        error=str(exc),
                    )
                )
        if tags_errors:
            rollback_attempted = True
            rollback_success = True
            for moved_src, moved_dest in reversed(completed_moves):
                try:
                    moved_src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(moved_dest), str(moved_src))
                except Exception:
                    rollback_success = False
            store.set_state(
                plan.dir_id,
                DirectoryState.FAILED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
            return ApplyReport(
                dir_id=plan.dir_id,
                plan_version=plan.plan_version,
                tagpatch_version=tag_patch.version,
                status=ApplyStatus.FAILED,
                dry_run=False,
                file_ops=tuple(file_ops),
                tag_ops=tuple(tag_ops),
                errors=tuple(tags_errors),
                rollback_attempted=rollback_attempted,
                rollback_success=rollback_success,
            )

    if plan.non_audio_policy == "DELETE":
        for entry in sorted(plan.source_path.iterdir(), key=lambda p: p.name):
            if entry.is_file():
                entry.unlink()

    if not any(plan.source_path.iterdir()):
        plan.source_path.rmdir()

    store.set_state(
        plan.dir_id,
        DirectoryState.APPLIED,
        pinned_provider=plan.provider,
        pinned_release_id=plan.release_id,
    )
    return ApplyReport(
        dir_id=plan.dir_id,
        plan_version=plan.plan_version,
        tagpatch_version=tag_patch.version if tag_patch else None,
        status=ApplyStatus.APPLIED,
        dry_run=False,
        file_ops=tuple(file_ops),
        tag_ops=tuple(tag_ops),
        errors=(),
        rollback_attempted=False,
        rollback_success=False,
    )

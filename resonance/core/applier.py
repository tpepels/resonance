"""Applier - transactional execution of plans and tag patches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import errno
import os
import shutil
from typing import Optional

from resonance.core.enricher import TagPatch
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.core.validation import (
    SafePath,
    validate_dir_id,
    validate_release_id,
    validate_signature_hash,
)
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter, TagWriter
from resonance.infrastructure.scanner import LibraryScanner


class ApplyStatus(str, Enum):
    """Apply result status."""

    APPLIED = "APPLIED"
    NOOP_ALREADY_APPLIED = "NOOP_ALREADY_APPLIED"
    PARTIAL_COMPLETE = "PARTIAL_COMPLETE"
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
    before_tags: tuple[tuple[str, str], ...] = ()
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
    warnings: tuple[str, ...]
    rollback_attempted: bool
    rollback_success: bool


_SUPPORTED_PLAN_VERSIONS = frozenset({"v1"})
_SUPPORTED_TAGPATCH_VERSIONS = frozenset({"v1"})


def _is_within(parent: Path, child: Path) -> bool:
    parent = parent.resolve()
    child = child.resolve()
    return parent == child or parent in child.parents


def _resolve_source_path(source_root: Path, path: Path) -> Path:
    if ".." in path.parts:
        raise ValueError(f"Path traversal not allowed: {path}")
    if path.is_absolute():
        return path
    return source_root / path


def _resolve_destination_path(
    path: Path, allowed_roots: tuple[Path, ...] | None
) -> Path:
    if ".." in path.parts:
        raise ValueError(f"Path traversal not allowed: {path}")
    if path.is_absolute():
        return path
    if not allowed_roots or len(allowed_roots) != 1:
        raise ValueError("Relative destination path requires a single allowed_root")
    return allowed_roots[0] / path


def _collect_audio_files(source_path: Path) -> list[Path]:
    extensions = LibraryScanner.DEFAULT_EXTENSIONS
    files = [
        path
        for path in source_path.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() in extensions
    ]
    return sorted(files)


def _cleanup_empty_dest_parents(dest: Path, allowed_roots: tuple[Path, ...] | None) -> None:
    roots = [root.resolve() for root in allowed_roots or ()]
    current = dest.parent
    while True:
        try:
            current.rmdir()
        except OSError:
            break
        if current in roots:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent


def _sidecar_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".meta.json")


def _manual_rename_detected(dest: Path) -> bool:
    """Detect manual rename in destination directory for a track file."""
    if not dest.parent.exists() or not dest.parent.is_dir():
        return False
    match = re.match(r"^(\d{2})\b", dest.name)
    if not match:
        return False
    prefix = match.group(1)
    for candidate in sorted(dest.parent.iterdir(), key=lambda p: p.name):
        if not candidate.is_file():
            continue
        if candidate == dest or candidate.suffix != dest.suffix:
            continue
        if candidate.name.startswith(prefix + " ") or candidate.name.startswith(prefix + "-") or candidate.name.startswith(prefix + "_"):
            return True
    return False


def _move_file(src: Path, dest: Path) -> None:
    try:
        shutil.move(str(src), str(dest))
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        temp = dest.with_suffix(dest.suffix + ".tmp")
        shutil.copy2(str(src), str(temp))
        os.replace(str(temp), str(dest))
        src.unlink()


@dataclass(frozen=True)
class CompletionAnalysis:
    not_started: tuple[tuple[Path, Path], ...]
    completed: tuple[tuple[Path, Path], ...]
    partial: tuple[tuple[Path, Path, str], ...]


def _analyze_completion(file_moves: list[tuple[Path, Path]]) -> CompletionAnalysis:
    not_started: list[tuple[Path, Path]] = []
    completed: list[tuple[Path, Path]] = []
    partial: list[tuple[Path, Path, str]] = []
    for src, dest in file_moves:
        src_exists = src.exists()
        dest_exists = dest.exists()
        if src_exists and not dest_exists:
            not_started.append((src, dest))
        elif not src_exists and dest_exists:
            completed.append((src, dest))
        elif not src_exists and not dest_exists:
            if _manual_rename_detected(dest):
                completed.append((src, dest))
            else:
                partial.append((src, dest, "both_missing"))
    return CompletionAnalysis(
        not_started=tuple(not_started),
        completed=tuple(completed),
        partial=tuple(partial),
    )


def apply_plan(
    plan: Plan,
    tag_patch: TagPatch | None,
    store: DirectoryStateStore,
    *,
    allowed_roots: tuple[Path, ...] | None = None,
    dry_run: bool = True,
    tag_writer: TagWriter | None = None,
    settings_hash: str | None = None,
    case_insensitive_collisions: bool = False,
) -> ApplyReport:
    """Apply a plan (and optional tag patch) with deterministic preflight."""
    errors: list[str] = []
    warnings: list[str] = []
    record = store.get(plan.dir_id)
    tag_writer = tag_writer or MetaJsonTagWriter()

    def _record_apply(status: ApplyStatus, report_errors: tuple[str, ...]) -> None:
        if record:
            store.record_apply_summary(plan.dir_id, status.value, report_errors)

    def _fail(report_errors: list[str]) -> ApplyReport:
        if record:
            store.set_state(
                plan.dir_id,
                DirectoryState.FAILED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
        report = ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.FAILED,
            dry_run=dry_run,
            file_ops=(),
            tag_ops=(),
            errors=tuple(report_errors),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        _record_apply(ApplyStatus.FAILED, tuple(report_errors))
        return report

    try:
        validate_dir_id(plan.dir_id)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        validate_signature_hash(plan.signature_hash)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        validate_release_id(plan.release_id)
    except ValueError as exc:
        errors.append(str(exc))

    if plan.plan_version not in _SUPPORTED_PLAN_VERSIONS:
        errors.append(f"Unsupported plan version: {plan.plan_version}")
    if tag_patch and tag_patch.version not in _SUPPORTED_TAGPATCH_VERSIONS:
        errors.append(f"Unsupported tag patch version: {tag_patch.version}")
    if allowed_roots:
        for root in allowed_roots:
            if not root.is_absolute():
                errors.append(f"Allowed root must be absolute: {root}")
    if not record:
        errors.append(f"Unknown dir_id: {plan.dir_id}")
    elif record.state != DirectoryState.PLANNED:
        errors.append(f"Directory state must be PLANNED, got {record.state.value}")
    elif record.signature_hash != plan.signature_hash:
        errors.append("Signature hash mismatch between plan and store")
    if plan.settings_hash is not None and plan.settings_hash != settings_hash:
        errors.append("Settings hash mismatch between plan and apply")

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
            SafePath(src, (plan.source_path,))
            if allowed_roots:
                SafePath(dest, allowed_roots)
            file_moves.append((src, dest))
            sidecar = _sidecar_path(src)
            if sidecar.exists():
                file_moves.append((sidecar, _sidecar_path(dest)))
    except ValueError as exc:
        return _fail([str(exc)])

    analysis = _analyze_completion(file_moves)
    if analysis.partial or (analysis.completed and analysis.not_started):
        if record:
            store.set_state(
                plan.dir_id,
                DirectoryState.FAILED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
        report = ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.PARTIAL_COMPLETE,
            dry_run=dry_run,
            file_ops=(),
            tag_ops=(),
            errors=(
                "Partial completion detected: inconsistent file move state",
            ),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        _record_apply(
            ApplyStatus.PARTIAL_COMPLETE,
            ("Partial completion detected: inconsistent file move state",),
        )
        return report
    if not analysis.not_started and analysis.completed:
        if record:
            store.set_state(
                plan.dir_id,
                DirectoryState.APPLIED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
        report = ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.NOOP_ALREADY_APPLIED,
            dry_run=dry_run,
            file_ops=(),
            tag_ops=(),
            errors=(),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        _record_apply(ApplyStatus.NOOP_ALREADY_APPLIED, ())
        return report

    if not plan.source_path.exists() or not plan.source_path.is_dir():
        errors.append("Plan source_path does not exist or is not a directory")
    else:
        audio_files = _collect_audio_files(plan.source_path)
        if not audio_files:
            errors.append("Signature check failed: no audio files found")
        else:
            signature = dir_signature(audio_files).signature_hash
            if signature != plan.signature_hash:
                errors.append(
                    "Signature hash mismatch between plan and source directory"
                )

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

    if case_insensitive_collisions:
        normalized: dict[str, Path] = {}
        for _, dest in file_moves:
            key = str(dest).lower()
            prior = normalized.get(key)
            if prior and prior != dest:
                errors.append(f"Case-insensitive collision: {prior} vs {dest}")
                break
            normalized[key] = dest
            if dest.parent.exists():
                for entry in dest.parent.iterdir():
                    if entry.name.lower() == dest.name.lower() and entry.name != dest.name:
                        errors.append(
                            f"Case-insensitive collision: {entry} vs {dest}"
                        )
                        break
                if errors:
                    break

    if allowed_roots:
        for _, dest in file_moves:
            if not any(_is_within(root, dest) for root in allowed_roots):
                errors.append(f"Destination outside allowed roots: {dest}")

    if plan.conflict_policy == "FAIL":
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
        report = ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.APPLIED,
            dry_run=True,
            file_ops=tuple(file_ops),
            tag_ops=(),
            errors=(),
            warnings=(),
            rollback_attempted=False,
            rollback_success=False,
        )
        _record_apply(ApplyStatus.APPLIED, ())
        return report

    rollback_attempted = False
    rollback_success = False
    try:
        for src, dest in file_moves:
            target = dest
            if target.exists():
                if plan.conflict_policy == "SKIP":
                    file_ops.append(
                        FileOpResult(
                            source_path=src,
                            destination_path=target,
                            status="SKIPPED",
                        )
                    )
                    continue
                if plan.conflict_policy == "RENAME":
                    base = target.stem
                    suffix = target.suffix
                    index = 1
                    while True:
                        candidate = target.with_name(f"{base} ({index}){suffix}")
                        if not candidate.exists():
                            target = candidate
                            break
                        index += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            _move_file(src, target)
            completed_moves.append((src, target))
            file_ops.append(
                FileOpResult(source_path=src, destination_path=target, status="MOVED")
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
                _cleanup_empty_dest_parents(moved_dest, allowed_roots)
            except Exception:
                rollback_success = False
        errors.append(f"Move failed: {exc}")
        store.set_state(
            plan.dir_id,
            DirectoryState.FAILED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        report = ApplyReport(
            dir_id=plan.dir_id,
            plan_version=plan.plan_version,
            tagpatch_version=tag_patch.version if tag_patch else None,
            status=ApplyStatus.FAILED,
            dry_run=False,
            file_ops=tuple(file_ops),
            tag_ops=(),
            errors=tuple(errors),
            warnings=(),
            rollback_attempted=rollback_attempted,
            rollback_success=rollback_success,
        )
        _record_apply(ApplyStatus.FAILED, tuple(errors))
        return report

    tag_ops: list[TagOpResult] = []
    if tag_patch and tag_patch.allowed:
        tags_errors: list[str] = []
        rollback_attempted = False
        rollback_success = False
        by_position = {op.track_position: op for op in ordered_ops}
        album_tags = tag_patch.album_patch.set_tags if tag_patch.album_patch else {}
        provenance_tags = tag_patch.provenance_tags
        overwrite_fields = set(tag_patch.overwrite_fields or ())
        for track_patch in tag_patch.track_patches:
            operation: TrackOperation | None = by_position.get(track_patch.track_position)
            if operation is None:
                tags_errors.append(
                    f"Missing track position in plan: {track_patch.track_position}"
                )
                continue
            try:
                dest = _resolve_destination_path(operation.destination_path, allowed_roots)
                existing = tag_writer.read_tags(dest)
                before_snapshot = tuple(sorted(existing.items()))
                combined = {**album_tags, **track_patch.set_tags, **provenance_tags}
                planned_set: dict[str, str] = {}
                planned_skipped: list[str] = []
                overwritten: list[str] = []
                for key, value in combined.items():
                    existing_value = existing.get(key)
                    is_provenance = key.startswith("resonance.prov.")
                    has_value = (
                        existing_value is not None
                        and str(existing_value).strip() != ""
                    )
                    if has_value and not (
                        is_provenance
                        or tag_patch.allow_overwrite
                        or key in overwrite_fields
                    ):
                        planned_skipped.append(key)
                        continue
                    if has_value and not is_provenance:
                        overwritten.append(key)
                    planned_set[key] = value
                if overwritten:
                    planned_set["resonance.prov.overwrote_keys"] = ",".join(
                        sorted(set(overwritten))
                    )
                write_result = tag_writer.apply_patch(
                    dest,
                    planned_set,
                    allow_overwrite=True,
                )
                tag_ops.append(
                    TagOpResult(
                        file_path=write_result.file_path,
                        tags_set=tuple(sorted(planned_set.keys())),
                        tags_skipped=tuple(sorted(planned_skipped)),
                        before_tags=before_snapshot,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - surface tag error
                tags_errors.append(f"Tag write failed for {dest}: {exc}")
                tag_ops.append(
                    TagOpResult(
                        file_path=dest,
                        tags_set=(),
                        tags_skipped=(),
                        before_tags=(),
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
                    _cleanup_empty_dest_parents(moved_dest, allowed_roots)
                except Exception:
                    rollback_success = False
            store.set_state(
                plan.dir_id,
                DirectoryState.FAILED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )
            report = ApplyReport(
                dir_id=plan.dir_id,
                plan_version=plan.plan_version,
                tagpatch_version=tag_patch.version,
                status=ApplyStatus.FAILED,
                dry_run=False,
                file_ops=tuple(file_ops),
                tag_ops=tuple(tag_ops),
                errors=tuple(tags_errors),
                warnings=(),
                rollback_attempted=rollback_attempted,
                rollback_success=rollback_success,
            )
            _record_apply(ApplyStatus.FAILED, tuple(tags_errors))
            return report

    if plan.non_audio_policy == "DELETE":
        for entry in sorted(plan.source_path.iterdir(), key=lambda p: p.name):
            if entry.is_file():
                entry.unlink()
    elif plan.source_path.exists():
        if any(plan.source_path.iterdir()):
            warnings.append(
                f"Cleanup skipped due to non-audio policy: {plan.non_audio_policy}"
            )

    if not any(plan.source_path.iterdir()):
        plan.source_path.rmdir()

    store.set_state(
        plan.dir_id,
        DirectoryState.APPLIED,
        pinned_provider=plan.provider,
        pinned_release_id=plan.release_id,
    )
    report = ApplyReport(
        dir_id=plan.dir_id,
        plan_version=plan.plan_version,
        tagpatch_version=tag_patch.version if tag_patch else None,
        status=ApplyStatus.APPLIED,
        dry_run=False,
        file_ops=tuple(file_ops),
        tag_ops=tuple(tag_ops),
        errors=(),
        warnings=tuple(warnings),
        rollback_attempted=False,
        rollback_success=False,
    )
    _record_apply(ApplyStatus.APPLIED, ())
    return report

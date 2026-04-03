"""Prompt command - answer deferred user prompts."""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Callable

from ..core.identifier import ConfidenceTier, extract_evidence, identify
from ..core.state import DirectoryState
from ..errors import ValidationError
from ..infrastructure.scanner import LibraryScanner


# Replay file schema
class PromptReplay:
    """Schema for decision replay files."""

    def __init__(self, corpus_input_hashes: Dict[str, str], app_version: str = "3.1.0"):
        self.metadata = {
            "format": "resonance_prompt_replay_v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "app_version": app_version,
            "corpus_input_hashes": corpus_input_hashes,
        }
        self.decisions: List[Dict[str, Any]] = []

    def add_decision(self, dir_id: str, prompt_fingerprint: str, chosen_option: str,
                    chosen_provider: str | None = None, chosen_release_id: str | None = None):
        """Add a recorded decision."""
        self.decisions.append({
            "dir_id": dir_id,
            "prompt_fingerprint": prompt_fingerprint,
            "chosen_option": chosen_option,
            "chosen_provider": chosen_provider,
            "chosen_release_id": chosen_release_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            **self.metadata,
            "decisions": self.decisions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptReplay':
        """Load from dictionary."""
        if data.get("format") != "resonance_prompt_replay_v1":
            raise ValidationError("Invalid replay file format")

        replay = cls(
            corpus_input_hashes=data["corpus_input_hashes"],
            app_version=data.get("app_version", "unknown")
        )
        replay.metadata = {k: v for k, v in data.items() if k != "decisions"}
        replay.decisions = data["decisions"]
        return replay

    def find_decision(self, dir_id: str, prompt_fingerprint: str) -> Dict[str, Any]:
        """Find recorded decision for a directory."""
        for decision in self.decisions:
            if decision["dir_id"] == dir_id:
                if decision["prompt_fingerprint"] != prompt_fingerprint:
                    raise ValidationError(
                        f"Replay fingerprint mismatch for {dir_id}: "
                        f"expected {decision['prompt_fingerprint']}, got {prompt_fingerprint}"
                    )
                return decision
        raise ValidationError(f"No recorded decision found for directory {dir_id}")


def compute_prompt_fingerprint(dir_id: str, candidates: List, result_reasons: List[str] | tuple[str, ...]) -> str:
    """Compute stable fingerprint for a prompt situation."""
    # Include directory ID, candidate release IDs (stable order), and reasons
    candidate_ids = []
    for candidate in candidates:
        candidate_ids.append(f"{candidate.release.provider}:{candidate.release.release_id}")

    fingerprint_data = {
        "dir_id": dir_id,
        "candidate_ids": sorted(candidate_ids),  # Stable ordering
        "result_reasons": sorted(result_reasons),  # Stable ordering
    }

    # Create stable JSON representation
    json_str = json.dumps(fingerprint_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def run_prompt_uncertain(
    *,
    store,
    provider_client,
    input_provider=input,
    output_sink=print,
    evidence_builder=None,
    replay_recorder=None,
    replay_data=None,
) -> None:
    """Resolve queued directories via injected I/O (testable)."""
    queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
    queued = sorted(
        queued,
        key=lambda record: (str(record.last_seen_path), record.dir_id),
    )
    extensions = LibraryScanner.DEFAULT_EXTENSIONS

    for record in queued:
        audio_files = sorted(
            path
            for path in record.last_seen_path.iterdir()
            if path.is_file() and path.suffix.lower() in extensions
        )
        if not audio_files:
            continue
        if evidence_builder is None:
            raise ValueError("evidence_builder is required")
        evidence = evidence_builder(audio_files)
        result = identify(evidence, provider_client)
        candidates = list(result.candidates)

        output_sink(f"Queued: {record.last_seen_path}")
        output_sink("Tracks:")
        for index, path in enumerate(audio_files, start=1):
            duration = None
            if index - 1 < len(evidence.tracks):
                duration = evidence.tracks[index - 1].duration_seconds
            duration_str = f" ({duration}s)" if duration else ""
            output_sink(f"  {index}. {path.name}{duration_str}")
        if candidates:
            for idx, candidate in enumerate(candidates, start=1):
                output_sink(
                    f"[{idx}] {candidate.release.provider}:{candidate.release.release_id} "
                    f"{candidate.release.artist} - {candidate.release.title} "
                    f"score={candidate.total_score:.2f} coverage={candidate.fingerprint_coverage:.2f}"
                )
        else:
            output_sink("No candidates available.")

        if result.reasons:
            output_sink(f"Reasons: {'; '.join(result.reasons)}")

        options = [
            "Options:",
            "  [1..N] Select a release from the list",
            "  [mb:ID] Provide MusicBrainz release ID",
            "  [dg:ID] Provide Discogs release ID",
            "  [s] Jail this directory",
            "  [enter] Skip for now",
        ]
        for line in options:
            output_sink(line)

        # Handle recording/replay modes
        if replay_data is not None:
            # REPLAY MODE: Use recorded decision
            prompt_fingerprint = compute_prompt_fingerprint(record.dir_id, candidates, result.reasons)
            recorded_decision = replay_data.find_decision(record.dir_id, prompt_fingerprint)
            response = recorded_decision["chosen_option"]
            output_sink(f"REPLAY: Using recorded choice '{response}'")
        else:
            # INTERACTIVE MODE: Get user input
            response = input_provider("Choice: ").strip().lower()

        if not response:
            if replay_recorder:
                replay_recorder.add_decision(record.dir_id,
                                           compute_prompt_fingerprint(record.dir_id, candidates, result.reasons),
                                           "skip")
            continue
        if response == "s":
            store.set_state(record.dir_id, DirectoryState.JAILED)
            if replay_recorder:
                replay_recorder.add_decision(record.dir_id,
                                           compute_prompt_fingerprint(record.dir_id, candidates, result.reasons),
                                           "jail")
            continue
        if response.isdigit():
            choice = int(response)
            if 1 <= choice <= len(candidates):
                selected = candidates[choice - 1].release
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider=selected.provider,
                    pinned_release_id=selected.release_id,
                )
                if replay_recorder:
                    replay_recorder.add_decision(record.dir_id,
                                               compute_prompt_fingerprint(record.dir_id, candidates, result.reasons),
                                               f"choice_{choice}",
                                               selected.provider,
                                               selected.release_id)
            continue
        if response.startswith("mb:"):
            release_id = response[3:].strip()
            if release_id:
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider="musicbrainz",
                    pinned_release_id=release_id,
                )
                if replay_recorder:
                    replay_recorder.add_decision(record.dir_id,
                                               compute_prompt_fingerprint(record.dir_id, candidates, result.reasons),
                                               f"mb:{release_id}",
                                               "musicbrainz",
                                               release_id)
            continue
        if response.startswith("dg:"):
            release_id = response[3:].strip()
            if release_id:
                store.set_state(
                    record.dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider="discogs",
                    pinned_release_id=release_id,
                )
                if replay_recorder:
                    replay_recorder.add_decision(record.dir_id,
                                               compute_prompt_fingerprint(record.dir_id, candidates, result.reasons),
                                               f"dg:{release_id}",
                                               "discogs",
                                               release_id)
            continue


def run_prompt(
    args: Namespace,
    *,
    store=None,
    provider_client=None,
    input_provider=input,
    output_sink=print,
) -> int:
    """CLI entry point for prompt command."""
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")

    # Check for replay file (non-interactive, recorded decisions)
    replay_file = getattr(args, 'replay_file', None)
    if replay_file:
        return run_prompt_replay(args, store=store, output_sink=output_sink)

    # Check for scripted decisions file (non-interactive mode)
    decisions_file = getattr(args, 'decisions_file', None)
    if decisions_file:
        return run_prompt_scripted(args, store=store, output_sink=output_sink)

    # Check for record mode (interactive with recording)
    record_replay = getattr(args, 'record_replay', None)
    if record_replay:
        return run_prompt_record(args, store=store, provider_client=provider_client,
                               input_provider=input_provider, output_sink=output_sink)

    # Regular interactive mode
    # TODO: Get or create provider client from cache_db if provided
    # For now, provider_client should be passed in or will be None

    # Use extract_evidence as the evidence builder
    def evidence_builder(audio_files):
        return extract_evidence(audio_files)

    # Call the interactive prompt function
    run_prompt_uncertain(
        store=store,
        provider_client=provider_client,
        input_provider=input_provider,
        output_sink=output_sink,
        evidence_builder=evidence_builder,
    )

    return 0


def run_prompt_scripted(args: Namespace, *, store, output_sink=print) -> int:
    """Apply scripted decisions from JSON file (non-interactive)."""
    decisions_file = args.decisions_file

    if not decisions_file.exists():
        raise ValidationError(f"Decisions file not found: {decisions_file}")

    # Load and validate decisions file
    import json
    try:
        with open(decisions_file, 'r', encoding='utf-8') as f:
            decisions_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValidationError(f"Failed to load decisions file: {exc}")

    # Check if this is a replay file (preferred) or old-style decisions
    if decisions_data.get("format") == "resonance_prompt_replay_v1":
        # This is a replay file - validate and use it
        try:
            replay = PromptReplay.from_dict(decisions_data)
            return run_prompt_replay_internal(args, store=store, replay=replay, output_sink=output_sink)
        except ValidationError:
            raise  # Re-raise validation errors
    else:
        # This is an old-style decisions.json file
        # In REAL mode, we should reject these and require replay files
        # Check if we're in REAL mode by looking for required credentials
        import os
        is_real_mode = bool(os.environ.get('ACOUSTID_API_KEY') and os.environ.get('DISCOGS_TOKEN'))

        if is_real_mode:
            raise ValidationError(
                f"REAL mode requires replay files, not hand-authored decisions. "
                f"Use 'make corpus-decide-real-interactive' to create a replay file first. "
                f"File: {decisions_file}"
            )

        # In offline mode, accept old-style decisions for backward compatibility
        scripted_decisions = decisions_data.get('decisions', {})

    # Process all queued directories (old-style path)
    from ..core.state import DirectoryState
    queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
    processed = 0

    for record in queued:
        dir_id = record.dir_id
        scripted_decision = scripted_decisions.get(dir_id)

        if scripted_decision == "AUTO":
            # Run identification to get candidates and pick best
            from ..core.identifier import extract_evidence, identify
            from ..infrastructure.scanner import LibraryScanner

            # Get provider client
            if hasattr(args, 'cache_db') and args.cache_db:
                from resonance.app import ResonanceApp
                app = ResonanceApp.from_env(
                    library_root=Path("/tmp"),  # dummy
                    cache_path=args.cache_db,
                    offline=True,  # Always offline for scripted mode
                )
                provider_client = app.provider_client
                app.close()
                if provider_client is None:
                    output_sink(f"WARNING: No provider client for {dir_id}, jailing")
                    store.set_state(dir_id, DirectoryState.JAILED)
                    continue
            else:
                output_sink(f"WARNING: No cache_db for {dir_id}, jailing")
                store.set_state(dir_id, DirectoryState.JAILED)
                continue

            # Extract evidence and identify
            audio_files = sorted(
                path for path in record.last_seen_path.iterdir()
                if path.is_file() and path.suffix.lower() in LibraryScanner.DEFAULT_EXTENSIONS
            )
            if not audio_files:
                store.set_state(dir_id, DirectoryState.JAILED)
                continue

            evidence = extract_evidence(audio_files)
            result = identify(evidence, provider_client)

            if result.best_candidate and result.tier in (ConfidenceTier.PROBABLE, ConfidenceTier.CERTAIN):
                best = result.best_candidate
                store.set_state(
                    dir_id,
                    DirectoryState.RESOLVED_USER,
                    pinned_provider=best.release.provider,
                    pinned_release_id=best.release.release_id,
                    pinned_confidence=best.total_score,
                )
                output_sink(f"SCRIPTED: {dir_id} -> AUTO ({best.release.provider}:{best.release.release_id})")
            else:
                store.set_state(dir_id, DirectoryState.JAILED)
                output_sink(f"SCRIPTED: {dir_id} -> JAIL (no good candidates)")

        elif scripted_decision == "JAIL":
            store.set_state(dir_id, DirectoryState.JAILED)
            output_sink(f"SCRIPTED: {dir_id} -> JAIL")

        elif isinstance(scripted_decision, str):
            # Specific release_id provided in format "provider:release_id"
            if ":" in scripted_decision:
                provider_name, release_id = scripted_decision.split(":", 1)
                # Validate provider name
                if provider_name in ("musicbrainz", "discogs", "acoustid"):
                    store.set_state(
                        dir_id,
                        DirectoryState.RESOLVED_USER,
                        pinned_provider=provider_name,
                        pinned_release_id=release_id,
                    )
                    output_sink(f"SCRIPTED: {dir_id} -> {provider_name}:{release_id}")
                else:
                    store.set_state(dir_id, DirectoryState.JAILED)
                    output_sink(f"SCRIPTED: {dir_id} -> JAIL (invalid provider {provider_name})")
            else:
                store.set_state(dir_id, DirectoryState.JAILED)
                output_sink(f"SCRIPTED: {dir_id} -> JAIL (invalid format)")

        else:
            # No scripted decision available
            store.set_state(dir_id, DirectoryState.JAILED)
            output_sink(f"SCRIPTED: {dir_id} -> JAIL (no decision)")

        processed += 1

    output_sink(f"Processed {processed} queued directories with scripted decisions")
    return 0


def run_prompt_record(args: Namespace, *, store, provider_client=None,
                     input_provider=input, output_sink=print) -> int:
    """Run interactive prompt with decision recording."""
    record_file = args.record_replay

    # Compute corpus input hashes for replay metadata
    corpus_hashes = {}
    corpus_root = Path(__file__).parent.parent.parent / 'tests' / 'real_corpus'
    for artifact in ['metadata.json', 'expected_state.json', 'expected_layout.json', 'expected_tags.json']:
        artifact_path = corpus_root / artifact
        if artifact_path.exists():
            corpus_hashes[artifact] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    # Create replay recorder
    replay_recorder = PromptReplay(corpus_hashes)

    # Get provider client if not provided
    if provider_client is None and hasattr(args, 'cache_db') and args.cache_db:
        from resonance.app import ResonanceApp
        app = ResonanceApp.from_env(
            library_root=Path("/tmp"),  # dummy
            cache_path=args.cache_db,
            offline=False,  # Recording mode should use live providers
        )
        provider_client = app.provider_client
        app.close()
        if provider_client is None:
            raise ValidationError("Provider client required for recording mode")

    # Use extract_evidence as the evidence builder
    def evidence_builder(audio_files):
        return extract_evidence(audio_files)

    # Run interactive prompt with recording
    try:
        run_prompt_uncertain(
            store=store,
            provider_client=provider_client,
            input_provider=input_provider,
            output_sink=output_sink,
            evidence_builder=evidence_builder,
            replay_recorder=replay_recorder,
        )
    finally:
        # Save replay file atomically
        import tempfile
        import os
        temp_file = record_file.with_suffix(record_file.suffix + '.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(replay_recorder.to_dict(), f, indent=2, ensure_ascii=False)
            temp_file.replace(record_file)
            output_sink(f"Recorded {len(replay_recorder.decisions)} decisions to {record_file}")
        except Exception as exc:
            output_sink(f"Failed to save replay file: {exc}")
            if temp_file.exists():
                temp_file.unlink()
            return 1

    return 0


def run_prompt_replay(args: Namespace, *, store, output_sink=print) -> int:
    """Replay decisions from recorded replay file."""
    replay_file = args.replay_file

    if not replay_file.exists():
        raise ValidationError(f"Replay file not found: {replay_file}")

    # Load replay data
    try:
        with open(replay_file, 'r', encoding='utf-8') as f:
            replay_data = PromptReplay.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValidationError(f"Failed to load replay file: {exc}")

    # Validate corpus input hashes
    corpus_root = Path(__file__).parent.parent.parent / 'tests' / 'real_corpus'
    for artifact, expected_hash in replay_data.metadata["corpus_input_hashes"].items():
        artifact_path = corpus_root / artifact
        if not artifact_path.exists():
            raise ValidationError(f"Corpus artifact missing: {artifact}")
        actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValidationError(
                f"Corpus input hash mismatch for {artifact}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    # Get provider client (can be offline since we're replaying)
    provider_client = None
    if hasattr(args, 'cache_db') and args.cache_db:
        from resonance.app import ResonanceApp
        app = ResonanceApp.from_env(
            library_root=Path("/tmp"),  # dummy
            cache_path=args.cache_db,
            offline=True,  # Replay can use cached data
        )
        provider_client = app.provider_client
        app.close()

    # Use extract_evidence as the evidence builder
    def evidence_builder(audio_files):
        return extract_evidence(audio_files)

    # Run prompt in replay mode
    run_prompt_uncertain(
        store=store,
        provider_client=provider_client,
        input_provider=lambda _: "",  # No input needed in replay mode
        output_sink=output_sink,
        evidence_builder=evidence_builder,
        replay_data=replay_data,
    )

    output_sink(f"Replayed {len(replay_data.decisions)} decisions from {replay_file}")
    return 0


def run_prompt_replay_internal(args: Namespace, *, store, replay: PromptReplay, output_sink=print) -> int:
    """Internal function to replay decisions from a PromptReplay object."""
    # Get provider client (can be offline since we're replaying)
    provider_client = None
    if hasattr(args, 'cache_db') and args.cache_db:
        from resonance.app import ResonanceApp
        app = ResonanceApp.from_env(
            library_root=Path("/tmp"),  # dummy
            cache_path=args.cache_db,
            offline=True,  # Replay can use cached data
        )
        provider_client = app.provider_client
        app.close()

    # Use extract_evidence as the evidence builder
    def evidence_builder(audio_files):
        return extract_evidence(audio_files)

    # Run prompt in replay mode
    run_prompt_uncertain(
        store=store,
        provider_client=provider_client,
        input_provider=lambda _: "",  # No input needed in replay mode
        output_sink=output_sink,
        evidence_builder=evidence_builder,
        replay_data=replay,
    )

    output_sink(f"Replayed {len(replay.decisions)} decisions from replay object")
    return 0

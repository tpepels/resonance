"""Fixture provider responses for golden corpus runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resonance.core.identifier import ProviderRelease, ProviderTrack


def load_provider_fixtures() -> dict[str, dict[str, tuple[ProviderRelease, ...]]]:
    """Load fixture provider releases keyed by provider/scenario."""
    base = Path(__file__).parent / "fixtures"
    return {
        "musicbrainz": _load_provider(base / "musicbrainz.json", "musicbrainz"),
        "discogs": _load_provider(base / "discogs.json", "discogs"),
    }


def _load_provider(path: Path, provider: str) -> dict[str, tuple[ProviderRelease, ...]]:
    payload = json.loads(path.read_text())
    scenarios: dict[str, tuple[ProviderRelease, ...]] = {}
    for scenario, releases in payload.items():
        items = tuple(_release_from_dict(provider, entry) for entry in releases)
        scenarios[scenario] = items
    return scenarios


def _release_from_dict(provider: str, data: dict[str, Any]) -> ProviderRelease:
    tracks = tuple(
        ProviderTrack(
            position=track["position"],
            title=track["title"],
            duration_seconds=track.get("duration_seconds"),
            fingerprint_id=track.get("fingerprint_id"),
            composer=track.get("composer"),
            disc_number=track.get("disc_number"),
            recording_id=track.get("recording_id"),
        )
        for track in data["tracks"]
    )
    return ProviderRelease(
        provider=provider,
        release_id=data["release_id"],
        title=data["title"],
        artist=data["artist"],
        tracks=tracks,
        year=data.get("year"),
    )

"""Deterministic provider cache helpers."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return canonical JSON with stable ordering."""

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: normalize(value[k]) for k in sorted(value)}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    normalized = normalize(payload)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_cache_key(
    *,
    provider: str,
    request_type: str,
    query: dict[str, str],
    version: str,
) -> str:
    parts = [f"{key}={query[key]}" for key in sorted(query)]
    normalized = "|".join(parts)
    return f"{provider}:{request_type}:{version}:{normalized}"


def provider_cache_key(
    *,
    provider: str,
    request_type: str,
    query: dict[str, str],
    version: str,
    client_version: str,
) -> str:
    base = build_cache_key(
        provider=provider,
        request_type=request_type,
        query=query,
        version=version,
    )
    return f"{provider}:{request_type}:{version}:{client_version}:{base.split(':', 3)[-1]}"


def provider_cache_relevant_settings(settings: dict[str, object]) -> dict[str, object]:
    """Return the subset of settings relevant to provider cache validity."""
    return {
        "offline": settings.get("offline", False),
    }

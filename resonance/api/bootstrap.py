"""Composition root for API service construction."""

from __future__ import annotations

from resonance.api.service import ResonanceService


def build_service() -> ResonanceService:
    """Build the bounded API service."""
    return ResonanceService()

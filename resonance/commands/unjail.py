"""Unjail command - reset jailed directories."""

from __future__ import annotations


def run_unjail(*, store, dir_id: str):
    """Reset a jailed directory to NEW."""
    return store.unjail(dir_id)

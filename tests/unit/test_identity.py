# tests/unit/test_identity.py
from __future__ import annotations

from dataclasses import dataclass
import pytest

from resonance.core.identity.matching import (
    normalize_token,
    split_names,
    dedupe_names,
    short_folder_name,
)
from resonance.core.identity.canonicalizer import IdentityCanonicalizer


@dataclass
class FakeCanonicalCache:
    """Minimal cache stub for IdentityCanonicalizer unit tests."""
    store: dict[str, str]

    def get_canonical_name(self, key: str) -> str | None:
        return self.store.get(key)

    def set_canonical_name(self, key: str, canonical: str) -> None:
        self.store[key] = canonical


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Björk", "bjork"),
        ("Sigur Rós", "sigurros"),
        ("  The Beatles  ", "thebeatles"),
        ("Daft Punk feat. Pharrell Williams", "daftpunk"),
        ("Daft Punk featuring Pharrell Williams", "daftpunk"),
        ("AC/DC", "acdc"),
        ("Guns N' Roses", "gunsnroses"),
        ("", ""),
        (None, ""),  # type: ignore[arg-type]
    ],
)
def test_normalize_token_common_variants(raw, expected):
    assert normalize_token(raw) == expected


def test_normalize_token_is_idempotent():
    raw = "Björk"
    t1 = normalize_token(raw)
    t2 = normalize_token(t1)
    assert t1 == t2


def test_canonicalizer_prefers_cached_mapping():
    cache = FakeCanonicalCache(store={
        "artist::bach": "Johann Sebastian Bach",
    })
    canonicalizer = IdentityCanonicalizer(cache=cache)

    assert canonicalizer.canonicalize("Bach", "artist") == "Johann Sebastian Bach"


def test_canonicalizer_falls_back_to_original_when_missing():
    cache = FakeCanonicalCache(store={})
    canonicalizer = IdentityCanonicalizer(cache=cache)

    assert canonicalizer.canonicalize("Bjork", "artist") == "Bjork"
    assert canonicalizer.canonicalize("Björk", "artist") == "Björk"


def test_canonicalize_multi_deduplicates_equivalents():
    cache = FakeCanonicalCache(store={
        "artist::bjork": "Björk",
    })
    canonicalizer = IdentityCanonicalizer(cache=cache)

    out = canonicalizer.canonicalize_multi("Björk, Bjork; Björk", "artist")
    assert out == "Björk"


def test_canonicalizer_preserves_display_when_missing_mapping():
    cache = FakeCanonicalCache(store={})
    canonicalizer = IdentityCanonicalizer(cache=cache)

    assert canonicalizer.canonicalize("Daft Punk feat. Pharrell Williams", "artist") == (
        "Daft Punk feat. Pharrell Williams"
    )
    assert canonicalizer.canonicalize("Beatles, The", "artist") == "Beatles, The"


def test_split_names_deterministic():
    assert split_names("A & B / C") == ["A", "B", "C"]
    assert split_names("Daft Punk feat. Pharrell") == ["Daft Punk", "Pharrell"]
    assert split_names("Björk, Bjork; Björk") == ["Björk", "Bjork", "Björk"]


def test_dedupe_names_collapses_equivalents():
    parts = ["Björk", "Bjork", "Björk"]
    assert dedupe_names(parts) == ["Björk"]


def test_short_folder_name_removes_featuring():
    assert short_folder_name("Daft Punk feat. Pharrell Williams") == "Daft Punk"
    assert short_folder_name("Daft Punk (feat. Pharrell Williams)") == "Daft Punk"


def test_short_folder_name_enforces_max_length():
    value = "Artist Name - Deluxe Edition - Super Extra Long Bonus Disc"
    assert short_folder_name(value, max_length=30) == "Artist Name - Deluxe Edition"
    assert len(short_folder_name(value, max_length=20)) <= 20

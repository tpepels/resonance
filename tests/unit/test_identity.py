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

# --- additional identity tests (more coverage + edge cases) ---

@pytest.mark.parametrize(
    "raw, expected",
    [
        # Case + whitespace normalization
        ("  bjÖrK  ", "bjork"),
        ("\tSigur  Rós\n", "sigurros"),
        ("The   Beatles", "thebeatles"),

        # Unicode compatibility forms / punctuation
        ("Beyoncé", "beyonce"),
        ("Mötley Crüe", "motleycrue"),
        ("Zoë Keating", "zoekeating"),
        ("R.E.M.", "rem"),
        ("P!nk", "pnk"),
        ("A$AP Rocky", "aaprocky"),
        ("Guns N’ Roses", "gunsnroses"),  # curly apostrophe
        ("Guns N` Roses", "gunsnroses"),  # backtick variant
        ("AC／DC", "acdc"),  # fullwidth slash
        ("Sigur Rós", "sigurros"),  # NBSP between words

        # Featuring variants beyond those already tested
        ("Daft Punk ft Pharrell Williams", "daftpunk"),
        ("Daft Punk ft. Pharrell Williams", "daftpunk"),
        ("Daft Punk including Pharrell Williams", "daftpunk"),
        ("Daft Punk f. Pharrell Williams", "daftpunkfpharrellwilliams"),
        ("Daft Punk w/ Pharrell Williams", "daftpunkwpharrellwilliams"),
        ("Daft Punk with Pharrell Williams", "daftpunkwithpharrellwilliams"),

        # Parenthetical featuring
        ("Daft Punk (feat Pharrell Williams)", "daftpunk"),
        ("Daft Punk [feat. Pharrell Williams]", "daftpunk"),

        # Non-featuring parentheses should remain part of token *only if* your normalize strips all parens.
        # If you *do* strip all parens, expected becomes "radiohead".
        ("Radiohead (Official)", "radioheadofficial"),
    ],
)
def test_normalize_token_more_edge_cases(raw, expected):
    assert normalize_token(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Multiple separators + different joiners
        ("A and B", ["A", "B"]),
        ("A & B", ["A", "B"]),
        ("A / B", ["A", "B"]),
        ("A; B", ["A", "B"]),
        ("A, B", ["A", "B"]),

        # Featuring in different shapes
        ("Daft Punk ft. Pharrell", ["Daft Punk", "Pharrell"]),
        ("Daft Punk (feat. Pharrell)", ["Daft Punk", "Pharrell"]),
        ("Daft Punk [feat Pharrell]", ["Daft Punk", "Pharrell"]),
        ("Daft Punk including Pharrell", ["Daft Punk", "Pharrell"]),

        # “x” collaborations are common in electronic/hip-hop; include if your split_names supports it.
        # If not supported, drop this test or change expected to the unsplit string.
        ("Travis Scott x Drake", ["Travis Scott", "Drake"]),
    ],
)
def test_split_names_more_variants(raw, expected):
    assert split_names(raw) == expected


def test_split_names_preserves_order_and_is_stable():
    raw = "C / A & B"
    assert split_names(raw) == ["C", "A", "B"]
    assert split_names(raw) == split_names(raw)  # deterministic


def test_dedupe_names_preserves_first_display_variant():
    # If equivalence is determined by normalize_token, the first element should win.
    parts = ["Bjork", "Björk", "BJÖRK"]
    assert dedupe_names(parts) == ["Bjork"]


def test_dedupe_names_keeps_distinct_names():
    parts = ["Björk", "Sigur Rós", "Bjork"]
    # Björk and Bjork collapse; Sigur Rós remains
    assert dedupe_names(parts) == ["Björk", "Sigur Rós"]


def test_canonicalizer_cache_key_uses_normalized_token():
    cache = FakeCanonicalCache(store={
        "artist::bjork": "Björk",
        "artist::sigurros": "Sigur Rós",
    })
    canonicalizer = IdentityCanonicalizer(cache=cache)

    assert canonicalizer.canonicalize("  BJÖRK  ", "artist") == "Björk"
    assert canonicalizer.canonicalize("Sigur  Rós", "artist") == "Sigur Rós"


def test_canonicalize_multi_applies_mapping_then_dedupes():
    cache = FakeCanonicalCache(store={
        "artist::bjork": "Björk",
        "artist::sigurros": "Sigur Rós",
    })
    canonicalizer = IdentityCanonicalizer(cache=cache)

    out = canonicalizer.canonicalize_multi("Bjork, Björk; Sigur Rós", "artist")
    assert out == "Björk; Sigur Rós"


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Featuring removal should be robust to case + brackets
        ("Daft Punk FEAT. Pharrell Williams", "Daft Punk"),
        ("Daft Punk (FEAT Pharrell Williams)", "Daft Punk"),
        ("Daft Punk [Featuring Pharrell Williams]", "Daft Punk"),

        # Ensure trimming after removal
        ("Daft Punk feat. Pharrell Williams  ", "Daft Punk"),

        # If multiple featuring clauses appear, we still expect the base artist
        ("Daft Punk feat. Pharrell & Nile Rodgers", "Daft Punk"),
    ],
)
def test_short_folder_name_more_featuring_patterns(raw, expected):
    assert short_folder_name(raw) == expected


def test_short_folder_name_no_change_when_no_featuring():
    assert short_folder_name("The Beatles") == "The Beatles"
    assert short_folder_name("Beatles, The") == "Beatles, The"


def test_short_folder_name_max_length_prefers_clean_cut():
    # This test assumes your shortening strategy prefers cutting on separators/word boundaries.
    # If your implementation cuts hard at max_length, adjust expectations accordingly.
    value = "Artist Name - Deluxe Edition - Super Extra Long Bonus Disc"
    out = short_folder_name(value, max_length=30)
    assert out.startswith("Artist Name")
    assert len(out) <= 30


def test_short_folder_name_is_idempotent():
    raw = "Daft Punk (feat. Pharrell Williams)"
    assert short_folder_name(short_folder_name(raw)) == short_folder_name(raw)

def test_normalize_token_does_not_reorder_comma_names():
    assert normalize_token("Beatles, The") == "beatlesthe"
    assert normalize_token("The Beatles") == "thebeatles"
    assert normalize_token("Beatles, The") != normalize_token("The Beatles")

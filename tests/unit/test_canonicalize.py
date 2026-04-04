"""Unit tests for canonicalization functions.

Tests the explicit display vs match_key split as required by Phase A.1.
Also covers normalize_token, short_folder_name, and IdentityCanonicalizer
(migrated from test_identity.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from resonance.core.identity.canonicalize import (
    display_artist,
    display_album,
    display_work,
    match_key_artist,
    match_key_album,
    match_key_work,
    split_names,
    dedupe_names,
)
from resonance.core.identity.matching import (
    normalize_token,
    short_folder_name,
)
from resonance.core.identity.canonicalizer import IdentityCanonicalizer


# ============================================================================
# Helpers
# ============================================================================


@dataclass
class FakeCanonicalCache:
    """Minimal cache stub for IdentityCanonicalizer unit tests."""

    store: dict[str, str]

    def get_canonical_name(self, key: str) -> str | None:
        return self.store.get(key)

    def set_canonical_name(self, key: str, canonical: str) -> None:
        self.store[key] = canonical


# ============================================================================
# Display Canonicalization Tests
# ============================================================================


class TestDisplayArtist:
    """Test display_artist() preserves diacritics and proper casing."""

    def test_preserves_diacritics(self):
        assert display_artist("Björk") == "Björk"
        assert display_artist("Dvořák") == "Dvořák"
        assert display_artist("Mötley Crüe") == "Mötley Crüe"

    def test_normalizes_whitespace(self):
        assert display_artist("  The Beatles  ") == "The Beatles"
        assert display_artist("The  Beatles") == "The Beatles"

    def test_unicode_normalization(self):
        # NFKC normalization
        assert display_artist("Björk") == "Björk"  # Already NFC

    def test_empty_and_whitespace(self):
        assert display_artist("") == ""
        assert display_artist("   ") == ""


class TestDisplayAlbum:
    """Test display_album() preserves diacritics."""

    def test_preserves_diacritics(self):
        assert display_album("Homogénic") == "Homogénic"

    def test_normalizes_whitespace(self):
        assert display_album("  The Album  ") == "The Album"


class TestDisplayWork:
    """Test display_work() preserves musical symbols and diacritics."""

    def test_preserves_musical_notation(self):
        assert display_work("Piano Sonata No. 14 in C♯ minor") == "Piano Sonata No. 14 in C♯ minor"

    def test_preserves_diacritics(self):
        assert display_work("Für Elise") == "Für Elise"


# ============================================================================
# Match Key Canonicalization Tests
# ============================================================================


class TestMatchKeyArtist:
    """Test match_key_artist() creates aggressive normalized keys."""

    def test_removes_diacritics(self):
        """Björk and Bjork should produce the same match key."""
        assert match_key_artist("Björk") == "bjork"
        assert match_key_artist("Bjork") == "bjork"
        assert match_key_artist("Dvořák") == "dvorak"
        assert match_key_artist("Dvorak") == "dvorak"

    def test_removes_punctuation(self):
        """AC/DC, AC-DC, AC DC should all match."""
        assert match_key_artist("AC/DC") == "acdc"
        assert match_key_artist("AC-DC") == "acdc"
        assert match_key_artist("AC DC") == "acdc"

    def test_normalizes_joiners(self):
        """&, and, /, etc. are normalized."""
        assert match_key_artist("Art Blakey & The Jazz Messengers") == "artblakeythejazzmessengers"
        assert match_key_artist("Art Blakey and The Jazz Messengers") == "artblakeythejazzmessengers"
        assert match_key_artist("Art Blakey / The Jazz Messengers") == "artblakeythejazzmessengers"

    def test_removes_featuring(self):
        """Featured artists are stripped from match key."""
        assert match_key_artist("Artist feat. Guest") == "artist"
        assert match_key_artist("Artist (feat. Guest)") == "artist"
        assert match_key_artist("Artist ft. Guest") == "artist"

    def test_handles_comma_style_names(self):
        """Beatles, The → beatlesthe (match key, not display)."""
        # Note: We intentionally DON'T swap "The" in match keys
        # That's a display-level transformation
        assert match_key_artist("Beatles, The") == "beatlesthe"
        assert match_key_artist("The Beatles") == "thebeatles"

    def test_lowercases(self):
        assert match_key_artist("BJÖRK") == "bjork"
        assert match_key_artist("Björk") == "bjork"
        assert match_key_artist("björk") == "bjork"

    def test_removes_spaces(self):
        assert match_key_artist("Yo-Yo Ma") == "yoyoma"
        assert match_key_artist("Ludwig van Beethoven") == "ludwigvanbeethoven"

    def test_empty_and_whitespace(self):
        assert match_key_artist("") == ""
        assert match_key_artist("   ") == ""


class TestMatchKeyAlbum:
    """Test match_key_album() normalization."""

    def test_removes_diacritics(self):
        assert match_key_album("Homogénic") == "homogenic"

    def test_normalizes_similar_to_artist(self):
        # Albums use the same normalization as artists
        assert match_key_album("The Best of Björk") == "thebestofbjork"


class TestMatchKeyWork:
    """Test match_key_work() for compositions."""

    def test_removes_punctuation(self):
        assert match_key_work("Piano Sonata No. 14") == "pianosonatano14"

    def test_removes_diacritics(self):
        assert match_key_work("Für Elise") == "furelise"


# ============================================================================
# Multi-Name Handling Tests
# ============================================================================


class TestSplitNames:
    """Test split_names() handles various separators."""

    def test_ampersand_separator(self):
        assert split_names("Art Blakey & The Jazz Messengers") == [
            "Art Blakey",
            "The Jazz Messengers",
        ]

    def test_feat_separator(self):
        assert split_names("Artist feat. Guest") == ["Artist", "Guest"]
        assert split_names("Artist (feat. Guest)") == ["Artist", "Guest"]
        assert split_names("Artist ft. Guest") == ["Artist", "Guest"]

    def test_comma_separator(self):
        assert split_names("Artist A, Artist B") == ["Artist A", "Artist B"]

    def test_semicolon_separator(self):
        assert split_names("Artist A; Artist B") == ["Artist A", "Artist B"]

    def test_multiple_separators(self):
        assert split_names("A & B, C feat. D") == ["A", "B", "C", "D"]

    def test_single_name(self):
        assert split_names("Single Artist") == ["Single Artist"]

    def test_empty(self):
        assert split_names("") == []
        assert split_names("   ") == []


class TestDedupeNames:
    """Test dedupe_names() removes duplicates using match keys."""

    def test_removes_diacritic_duplicates(self):
        """Björk and Bjork are the same artist."""
        result = dedupe_names(["Björk", "Bjork", "björk"])
        assert result == ["Björk"]  # First occurrence preserved

    def test_removes_punctuation_duplicates(self):
        result = dedupe_names(["AC/DC", "AC-DC", "AC DC"])
        assert result == ["AC/DC"]

    def test_preserves_order(self):
        result = dedupe_names(["Artist A", "Artist B", "Artist A"])
        assert result == ["Artist A", "Artist B"]

    def test_preserves_display_form(self):
        """First occurrence's display form is preserved."""
        result = dedupe_names(["björk", "Björk", "BJÖRK"])
        assert result == ["björk"]  # First one kept

    def test_empty(self):
        assert dedupe_names([]) == []


# ============================================================================
# Integration Tests
# ============================================================================


class TestDisplayVsMatchKeyInvariant:
    """Test that display and match_key are properly separated."""

    def test_display_preserves_diacritics_match_key_removes(self):
        """Core invariant: display keeps Unicode, match_key strips it."""
        name = "Björk"
        assert display_artist(name) == "Björk"  # Preserved
        assert match_key_artist(name) == "bjork"  # Stripped

    def test_different_displays_same_match_key(self):
        """Different display forms can map to same match key."""
        names = ["Björk", "Bjork", "BJÖRK"]
        match_keys = [match_key_artist(n) for n in names]
        assert len(set(match_keys)) == 1  # All the same
        assert match_keys[0] == "bjork"

    def test_match_keys_enable_equivalence_check(self):
        """Match keys allow us to detect equivalent names."""
        name1 = "AC/DC"
        name2 = "AC-DC"
        assert display_artist(name1) != display_artist(name2)  # Different displays
        assert match_key_artist(name1) == match_key_artist(name2)  # Same key


class TestCommonArtistNames:
    """Test common real-world artist names."""

    # TDD_TODO_V3.md Phase A.1 specifies these test cases
    def test_bjork_variants(self):
        """Björk with and without diacritic."""
        assert display_artist("Björk") == "Björk"
        assert match_key_artist("Björk") == "bjork"
        assert match_key_artist("Bjork") == "bjork"

    def test_acdc_variants(self):
        """AC/DC with punctuation."""
        assert display_artist("AC/DC") == "AC/DC"
        assert match_key_artist("AC/DC") == "acdc"

    def test_beatles_comma_style(self):
        """Beatles, The (comma-style name)."""
        assert display_artist("Beatles, The") == "Beatles, The"
        assert match_key_artist("Beatles, The") == "beatlesthe"

    def test_collaboration_markers(self):
        """Artist feat. Guest patterns."""
        assert split_names("Artist feat. Guest") == ["Artist", "Guest"]
        assert split_names("Artist with Guest") == ["Artist", "Guest"]
        assert split_names("Artist w/ Guest") == ["Artist", "Guest"]


# ============================================================================
# normalize_token (migrated from test_identity.py)
# ============================================================================


class TestNormalizeToken:
    """Test normalize_token() edge cases and variants."""

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
            (None, ""),
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
            ("Guns N\u2019 Roses", "gunsnroses"),  # curly apostrophe
            ("Guns N` Roses", "gunsnroses"),  # backtick variant
            ("AC\uff0fDC", "acdc"),  # fullwidth slash
            ("Sigur\xa0Rós", "sigurros"),  # NBSP between words
            # Featuring variants
            ("Daft Punk ft Pharrell Williams", "daftpunk"),
            ("Daft Punk ft. Pharrell Williams", "daftpunk"),
            ("Daft Punk including Pharrell Williams", "daftpunk"),
            ("Daft Punk f. Pharrell Williams", "daftpunkfpharrellwilliams"),
            ("Daft Punk w/ Pharrell Williams", "daftpunkwpharrellwilliams"),
            ("Daft Punk with Pharrell Williams", "daftpunkwithpharrellwilliams"),
            # Parenthetical featuring
            ("Daft Punk (feat Pharrell Williams)", "daftpunk"),
            ("Daft Punk [feat. Pharrell Williams]", "daftpunk"),
            ("Radiohead (Official)", "radioheadofficial"),
        ],
        ids=lambda v: repr(v)[:40],
    )
    def test_normalize_token_variants(self, raw, expected):
        assert normalize_token(raw) == expected

    def test_is_idempotent(self):
        t1 = normalize_token("Björk")
        assert normalize_token(t1) == t1

    def test_does_not_reorder_comma_names(self):
        assert normalize_token("Beatles, The") == "beatlesthe"
        assert normalize_token("The Beatles") == "thebeatles"
        assert normalize_token("Beatles, The") != normalize_token("The Beatles")


# ============================================================================
# split_names / dedupe_names additional variants (migrated from test_identity.py)
# ============================================================================


class TestSplitNamesExtended:
    """Extended split_names tests with more separator variants."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("A and B", ["A", "B"]),
            ("A & B", ["A", "B"]),
            ("A / B", ["A", "B"]),
            ("A; B", ["A", "B"]),
            ("A, B", ["A", "B"]),
            ("Daft Punk ft. Pharrell", ["Daft Punk", "Pharrell"]),
            ("Daft Punk (feat. Pharrell)", ["Daft Punk", "Pharrell"]),
            ("Daft Punk [feat Pharrell]", ["Daft Punk", "Pharrell"]),
            ("Daft Punk including Pharrell", ["Daft Punk", "Pharrell"]),
            ("Travis Scott x Drake", ["Travis Scott", "Drake"]),
        ],
    )
    def test_split_names_separator_variants(self, raw, expected):
        assert split_names(raw) == expected

    def test_preserves_order_and_is_stable(self):
        raw = "C / A & B"
        assert split_names(raw) == ["C", "A", "B"]
        assert split_names(raw) == split_names(raw)

    def test_deterministic(self):
        assert split_names("A & B / C") == ["A", "B", "C"]
        assert split_names("Björk, Bjork; Björk") == ["Björk", "Bjork", "Björk"]


class TestDedupeNamesExtended:
    """Extended dedupe_names tests."""

    def test_preserves_first_display_variant(self):
        assert dedupe_names(["Bjork", "Björk", "BJÖRK"]) == ["Bjork"]

    def test_keeps_distinct_names(self):
        assert dedupe_names(["Björk", "Sigur Rós", "Bjork"]) == ["Björk", "Sigur Rós"]


# ============================================================================
# short_folder_name (migrated from test_identity.py)
# ============================================================================


class TestShortFolderName:
    """Test short_folder_name() featuring removal and length enforcement."""

    def test_removes_featuring(self):
        assert short_folder_name("Daft Punk feat. Pharrell Williams") == "Daft Punk"
        assert short_folder_name("Daft Punk (feat. Pharrell Williams)") == "Daft Punk"

    def test_enforces_max_length(self):
        value = "Artist Name - Deluxe Edition - Super Extra Long Bonus Disc"
        assert short_folder_name(value, max_length=30) == "Artist Name - Deluxe Edition"
        assert len(short_folder_name(value, max_length=20)) <= 20

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Daft Punk FEAT. Pharrell Williams", "Daft Punk"),
            ("Daft Punk (FEAT Pharrell Williams)", "Daft Punk"),
            ("Daft Punk [Featuring Pharrell Williams]", "Daft Punk"),
            ("Daft Punk feat. Pharrell Williams  ", "Daft Punk"),
            ("Daft Punk feat. Pharrell & Nile Rodgers", "Daft Punk"),
        ],
    )
    def test_featuring_pattern_variants(self, raw, expected):
        assert short_folder_name(raw) == expected

    def test_no_change_when_no_featuring(self):
        assert short_folder_name("The Beatles") == "The Beatles"
        assert short_folder_name("Beatles, The") == "Beatles, The"

    def test_max_length_prefers_clean_cut(self):
        value = "Artist Name - Deluxe Edition - Super Extra Long Bonus Disc"
        out = short_folder_name(value, max_length=30)
        assert out.startswith("Artist Name")
        assert len(out) <= 30

    def test_is_idempotent(self):
        raw = "Daft Punk (feat. Pharrell Williams)"
        assert short_folder_name(short_folder_name(raw)) == short_folder_name(raw)


# ============================================================================
# IdentityCanonicalizer (migrated from test_identity.py)
# ============================================================================


class TestIdentityCanonicalizer:
    """Test IdentityCanonicalizer with fake cache."""

    def test_prefers_cached_mapping(self):
        cache = FakeCanonicalCache(store={"artist::bach": "Johann Sebastian Bach"})
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize("Bach", "artist") == "Johann Sebastian Bach"

    def test_falls_back_to_original_when_missing(self):
        cache = FakeCanonicalCache(store={})
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize("Bjork", "artist") == "Bjork"
        assert canonicalizer.canonicalize("Björk", "artist") == "Björk"

    def test_canonicalize_multi_deduplicates_equivalents(self):
        cache = FakeCanonicalCache(store={"artist::bjork": "Björk"})
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize_multi("Björk, Bjork; Björk", "artist") == "Björk"

    def test_preserves_display_when_missing_mapping(self):
        cache = FakeCanonicalCache(store={})
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize("Daft Punk feat. Pharrell Williams", "artist") == (
            "Daft Punk feat. Pharrell Williams"
        )
        assert canonicalizer.canonicalize("Beatles, The", "artist") == "Beatles, The"

    def test_cache_key_uses_normalized_token(self):
        cache = FakeCanonicalCache(store={
            "artist::bjork": "Björk",
            "artist::sigurros": "Sigur Rós",
        })
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize("  BJÖRK  ", "artist") == "Björk"
        assert canonicalizer.canonicalize("Sigur  Rós", "artist") == "Sigur Rós"

    def test_canonicalize_multi_applies_mapping_then_dedupes(self):
        cache = FakeCanonicalCache(store={
            "artist::bjork": "Björk",
            "artist::sigurros": "Sigur Rós",
        })
        canonicalizer = IdentityCanonicalizer(cache=cache)
        assert canonicalizer.canonicalize_multi("Bjork, Björk; Sigur Rós", "artist") == (
            "Björk; Sigur Rós"
        )

"""Unit tests for canonicalization functions.

Tests the explicit display vs match_key split as required by Phase A.1.
"""

from __future__ import annotations

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

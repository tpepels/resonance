"""Unit tests for input validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.core.validation import (
    SafePath,
    resolve_destination_path,
    resolve_source_path,
    sanitize_filename,
    validate_dir_id,
    validate_release_id,
    validate_signature_hash,
)


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("hello world", "hello world"),
            ('Track <1>: "Demo"', "Track 1 Demo"),
            ("a/b\\c|d?e*f", "a b c d e f"),
            ("   spaced   out   ", "spaced out"),
            ("", "_"),
            ("   ", "_"),
        ],
        ids=["passthrough", "forbidden_chars", "all_separators", "collapse_spaces", "empty", "whitespace_only"],
    )
    def test_sanitize(self, raw: str, expected: str) -> None:
        assert sanitize_filename(raw) == expected

    @pytest.mark.parametrize("name", ["CON", "con", "PRN", "AUX", "NUL", "LPT1", "COM9"])
    def test_reserved_names(self, name: str) -> None:
        assert sanitize_filename(name) == f"_{name}"

    def test_truncates_long_names(self) -> None:
        long_name = "a" * 250
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestValidateIdentifiers:
    @pytest.mark.parametrize(
        "value",
        ["dir-1", "abc_DEF-123", "a" * 64],
        ids=["simple", "mixed", "max_length"],
    )
    def test_valid_dir_id(self, value: str) -> None:
        validate_dir_id(value)  # should not raise

    @pytest.mark.parametrize(
        "value",
        ["", "has spaces", "a" * 65, "dir/id"],
        ids=["empty", "spaces", "too_long", "slash"],
    )
    def test_invalid_dir_id(self, value: str) -> None:
        with pytest.raises(ValueError, match="Invalid dir_id"):
            validate_dir_id(value)

    def test_valid_signature_hash(self) -> None:
        validate_signature_hash("a" * 64)

    @pytest.mark.parametrize(
        "value",
        ["", "abc", "A" * 64, "g" * 64],
        ids=["empty", "short", "uppercase", "non_hex"],
    )
    def test_invalid_signature_hash(self, value: str) -> None:
        with pytest.raises(ValueError, match="Invalid signature_hash"):
            validate_signature_hash(value)

    def test_valid_release_id(self) -> None:
        validate_release_id("mb:12345678-abcd-1234-abcd-123456789abc")

    @pytest.mark.parametrize(
        "value",
        ["", "a" * 129, "id with spaces"],
        ids=["empty", "too_long", "spaces"],
    )
    def test_invalid_release_id(self, value: str) -> None:
        with pytest.raises(ValueError, match="Invalid release_id"):
            validate_release_id(value)


class TestSafePath:
    def test_valid_path_within_root(self, tmp_path: Path) -> None:
        child = tmp_path / "subdir" / "file.txt"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        sp = SafePath(child, (tmp_path,))
        assert sp.path == child.resolve()

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        evil = tmp_path / "subdir" / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="traversal"):
            SafePath(evil, (tmp_path,))

    def test_rejects_outside_root(self, tmp_path: Path) -> None:
        outside = Path("/tmp/outside_root")
        outside.mkdir(exist_ok=True)
        with pytest.raises(ValueError, match="outside allowed roots"):
            SafePath(outside, (tmp_path,))


class TestResolveSourcePath:
    def test_relative_path(self, tmp_path: Path) -> None:
        result = resolve_source_path(tmp_path, Path("sub/file.flac"))
        assert result == tmp_path / "sub/file.flac"

    def test_absolute_path_passthrough(self) -> None:
        abs_path = Path("/abs/path/file.flac")
        assert resolve_source_path(Path("/root"), abs_path) == abs_path

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="traversal"):
            resolve_source_path(tmp_path, Path("../escape"))


class TestResolveDestinationPath:
    def test_relative_with_single_root(self, tmp_path: Path) -> None:
        result = resolve_destination_path(Path("Artist/Album"), (tmp_path,))
        assert result == tmp_path / "Artist/Album"

    def test_absolute_passthrough(self) -> None:
        abs_path = Path("/dest/Artist/Album")
        assert resolve_destination_path(abs_path, None) == abs_path

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="traversal"):
            resolve_destination_path(Path("../escape"), (tmp_path,))

    def test_rejects_relative_without_single_root(self) -> None:
        with pytest.raises(ValueError, match="single allowed_root"):
            resolve_destination_path(Path("relative"), None)

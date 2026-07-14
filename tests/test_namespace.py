"""Tests for gateway.namespace glob matching helper."""

from __future__ import annotations

from gateway.namespace import matches_any


def test_matches_any_wildcard() -> None:
    assert matches_any("anything", ["*"]) is True


def test_matches_any_exact() -> None:
    assert matches_any("read_file", ["read_file"]) is True
    assert matches_any("write_file", ["read_file"]) is False


def test_matches_any_glob_prefix() -> None:
    assert matches_any("read_file", ["read_*"]) is True
    assert matches_any("write_file", ["read_*"]) is False


def test_matches_any_multiple_patterns() -> None:
    patterns = ["read_*", "list_*"]
    assert matches_any("read_file", patterns) is True
    assert matches_any("list_directory", patterns) is True
    assert matches_any("write_file", patterns) is False


def test_matches_any_empty_patterns() -> None:
    assert matches_any("anything", []) is False

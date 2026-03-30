"""Tests for utils.py helper functions."""

import pytest
from agents.types import ReviewComment


def test_make_diff_identical():
    from utils import make_diff
    result = make_diff("hello\n", "hello\n", "file.txt")
    assert result == ""


def test_make_diff_addition():
    from utils import make_diff
    result = make_diff("line1\n", "line1\nline2\n", "file.txt")
    assert "+line2" in result
    assert "a/file.txt" in result
    assert "b/file.txt" in result


def test_make_diff_deletion():
    from utils import make_diff
    result = make_diff("line1\nline2\n", "line1\n", "file.txt")
    assert "-line2" in result


def test_make_diff_empty_inputs():
    from utils import make_diff
    result = make_diff("", "new content\n", "new.py")
    assert "+new content" in result


def test_count_changed_lines_no_changes():
    from utils import count_changed_lines
    result = count_changed_lines([{"before": "same", "after": "same"}])
    assert result == 0


def test_count_changed_lines_with_changes():
    from utils import count_changed_lines
    result = count_changed_lines([
        {"before": "line1\nline2", "after": "line1\nchanged"},
    ])
    assert result > 0


def test_count_changed_lines_new_file():
    from utils import count_changed_lines
    result = count_changed_lines([
        {"before": "", "after": "line1\nline2\nline3"},
    ])
    assert result == 3


def test_format_comment_all_fields():
    from utils import format_comment
    c = ReviewComment(
        file_path="src/app.py",
        line_number=10,
        severity="critical",
        category="security",
        comment="SQL injection via string interpolation.",
        suggestion="Use parameterized queries.",
        confidence=0.95,
    )
    result = format_comment(c)
    assert "[CRITICAL]" in result
    assert "security" in result
    assert "95%" in result
    assert "SQL injection" in result
    assert "parameterized queries" in result


def test_format_comment_no_suggestion():
    from utils import format_comment
    c = ReviewComment(
        file_path="test.py",
        severity="nit",
        category="style",
        comment="Trailing whitespace.",
        confidence=0.5,
    )
    result = format_comment(c)
    assert "[NIT]" in result
    assert "Suggestion" not in result

"""Shared helper functions."""

import difflib
from agents.types import ReviewComment


def make_diff(before: str, after: str, path: str) -> str:
    """Return a unified diff string for two code versions of a given path."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "".join(diff_lines)


def count_changed_lines(file_changes: list) -> int:
    """Count total added + removed lines across all file changes."""
    total = 0
    for fc in file_changes:
        before_lines = fc.get("before", "").splitlines()
        after_lines = fc.get("after", "").splitlines()
        sm = difflib.SequenceMatcher(None, before_lines, after_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                total += (i2 - i1) + (j2 - j1)
    return total


SEVERITY_EMOJI = {
    "critical": "[CRITICAL]",
    "major": "[MAJOR]",
    "minor": "[MINOR]",
    "nit": "[NIT]",
}


def format_comment(comment: ReviewComment) -> str:
    """Format a ReviewComment into a readable string for posting to a PR."""
    badge = SEVERITY_EMOJI.get(comment.severity, "")
    parts = [f"{badge} **{comment.category}** (confidence: {comment.confidence:.0%})"]
    parts.append(comment.comment)
    if comment.suggestion:
        parts.append(f"\n**Suggestion:** {comment.suggestion}")
    return "\n\n".join(parts)

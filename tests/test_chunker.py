"""Tests for the token-aware chunker."""

import pytest
from agents.chunker import estimate_tokens, chunk_file_changes, MAX_CHUNK_TOKENS


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 400) == 100


def test_single_small_file():
    files = [{"path": "a.py", "before": "x" * 100, "after": "y" * 100}]
    chunks = chunk_file_changes(files)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1


def test_empty_input():
    assert chunk_file_changes([]) == []


def test_multiple_files_under_limit():
    files = [
        {"path": f"file{i}.py", "before": "x" * 100, "after": "y" * 100}
        for i in range(5)
    ]
    chunks = chunk_file_changes(files)
    assert len(chunks) == 1
    assert len(chunks[0]) == 5


def test_files_split_when_over_limit():
    # Each file is ~half the limit
    size = MAX_CHUNK_TOKENS * 2  # chars, so tokens = size/4 = half limit
    files = [
        {"path": f"file{i}.py", "before": "x" * size, "after": "y" * size}
        for i in range(3)
    ]
    chunks = chunk_file_changes(files)
    assert len(chunks) >= 2


def test_sorted_by_path():
    files = [
        {"path": "c.py", "before": "", "after": "x"},
        {"path": "a.py", "before": "", "after": "x"},
        {"path": "b.py", "before": "", "after": "x"},
    ]
    chunks = chunk_file_changes(files)
    paths = [f["path"] for f in chunks[0]]
    assert paths == ["a.py", "b.py", "c.py"]

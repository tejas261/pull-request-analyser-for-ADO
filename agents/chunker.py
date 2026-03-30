"""Token-aware chunking for large PRs."""

from __future__ import annotations
from typing import List

MAX_CHUNK_TOKENS = 80_000  # conservative limit per LLM call


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return len(text) // 4


def chunk_file_changes(file_changes: List[dict]) -> List[List[dict]]:
    """Split file changes into token-bounded chunks.

    Files are sorted by path for deterministic ordering.
    Each chunk stays under MAX_CHUNK_TOKENS.
    """
    if not file_changes:
        return []

    sorted_files = sorted(file_changes, key=lambda f: f["path"])
    chunks: List[List[dict]] = []
    current_chunk: List[dict] = []
    current_tokens = 0

    for fc in sorted_files:
        fc_tokens = estimate_tokens(
            fc.get("before", "") + fc.get("after", "")
        )
        if current_tokens + fc_tokens > MAX_CHUNK_TOKENS and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0
        current_chunk.append(fc)
        current_tokens += fc_tokens

    if current_chunk:
        chunks.append(current_chunk)
    return chunks

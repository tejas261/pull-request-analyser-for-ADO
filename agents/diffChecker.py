"""Diff checker agent — uses provider abstraction to fetch PR changes."""

from __future__ import annotations
from langgraph.graph import StateGraph, START, END


async def fetch_changes(state: dict) -> dict:
    """Fetch PR metadata and all file changes via the provider."""
    provider = state["provider"]
    pr_id: int = state["pr_id"]

    pr_metadata = await provider.get_pr_metadata(pr_id)
    file_changes = await provider.get_file_changes(pr_id)

    # Convert FileChange dataclasses to dicts for downstream agents
    fc_dicts = [
        {
            "path": fc.path,
            "change_type": fc.change_type,
            "before": fc.before,
            "after": fc.after,
            "old_path": fc.old_path,
        }
        for fc in file_changes
    ]

    paths = [fc.path for fc in file_changes]
    change_summary = []
    for fc in file_changes:
        prefix = {"add": "+", "delete": "-", "rename": "~", "edit": "M"}.get(
            fc.change_type, "?"
        )
        label = f"  {prefix} {fc.path}"
        if fc.old_path:
            label += f" (from {fc.old_path})"
        change_summary.append(label)

    return {
        "diff": "\n".join(paths),
        "diff_summary": "\n".join(change_summary),
        "pr_id": pr_id,
        "file_changes": fc_dicts,
        "pr_metadata": {
            "pr_id": pr_metadata.pr_id,
            "title": pr_metadata.title,
            "description": pr_metadata.description,
            "author": pr_metadata.author,
            "reviewers": pr_metadata.reviewers,
            "reviewer_details": pr_metadata.reviewer_details,
            "source_branch": pr_metadata.source_branch,
            "target_branch": pr_metadata.target_branch,
            "url": pr_metadata.url,
            "raw": pr_metadata.raw,
        },
    }


def build_diff_checker_graph() -> StateGraph:
    """Build the diff checker graph."""
    g = StateGraph(state_schema=dict)
    g.add_node("fetch_changes", fetch_changes)
    g.add_edge(START, "fetch_changes")
    g.add_edge("fetch_changes", END)
    return g

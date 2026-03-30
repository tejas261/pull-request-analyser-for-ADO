"""Commenter agent — posts synthesised review comments via the provider."""

from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from agents.types import ReviewComment
from utils import format_comment


async def post_comments(state: dict) -> dict:
    """Post inline and summary comments to the PR via the platform provider."""
    provider = state["provider"]
    pr_id: int = state["pr_id"]
    review_comments = state.get("review_comments", [])
    summary = state.get("summary", "")

    if not review_comments and not summary:
        return {"status": "No review findings to post."}

    posted = 0
    errors = 0

    # Post individual inline comments
    for raw in review_comments:
        comment = ReviewComment.model_validate(raw) if isinstance(raw, dict) else raw
        body = format_comment(comment)
        try:
            await provider.post_review_comment(
                pr_id=pr_id,
                body=body,
                path=comment.file_path or None,
                line=comment.line_number,
            )
            posted += 1
        except Exception as e:
            errors += 1
            print(f"  [warn] Failed to post comment on {comment.file_path}: {e}")

    # Post the overall summary as a top-level comment
    if summary:
        try:
            await provider.post_review_comment(pr_id=pr_id, body=summary)
            posted += 1
        except Exception as e:
            errors += 1
            print(f"  [warn] Failed to post summary comment: {e}")

    status = f"Posted {posted} comments"
    if errors:
        status += f" ({errors} failed)"
    return {"status": status}


def build_commenter_graph() -> StateGraph:
    """Build the commenter graph."""
    g = StateGraph(state_schema=dict)
    g.add_node("post_comments", post_comments)
    g.add_edge(START, "post_comments")
    g.add_edge("post_comments", END)
    return g

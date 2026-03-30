"""Main workflow orchestrator — platform-agnostic PR review pipeline."""

import os
import sys
import asyncio

from config import MCP_CONFIG
from providers.factory import get_provider
from agents.diffChecker import build_diff_checker_graph
from agents.reviewer import build_review_graph
from agents.commenter import build_commenter_graph
from agents.messenger import build_messenger_graph


async def main(pr_id: int) -> None:
    """Run the full PR analysis workflow."""
    provider = get_provider()

    try:
        # 1. Fetch diffs and PR metadata
        print(f"[1/4] Fetching PR #{pr_id} changes...")
        diff_app = build_diff_checker_graph().compile()
        diff_out = await diff_app.ainvoke({"pr_id": pr_id, "provider": provider})
        print(f"=== CHANGES ({len(diff_out['file_changes'])} files) ===")
        print(diff_out.get("diff_summary", diff_out["diff"]))
        print()

        # 2. Run specialised reviewers
        print("[2/4] Running specialised reviewers...")
        review_app = build_review_graph().compile()
        review_out = await review_app.ainvoke({
            "pr_id": pr_id,
            "file_changes": diff_out["file_changes"],
            "pr_metadata": diff_out["pr_metadata"],
        })
        n_comments = len(review_out.get("review_comments", []))
        print(f"=== REVIEW ({n_comments} findings) ===")
        print(review_out["summary"])
        print()

        # 3. Post comments to PR
        print("[3/4] Posting review comments...")
        comment_app = build_commenter_graph().compile()
        comment_out = await comment_app.ainvoke({
            "pr_id": pr_id,
            "provider": provider,
            "review_comments": review_out.get("review_comments", []),
            "summary": review_out["summary"],
        })
        print(f"=== COMMENTS === {comment_out['status']}")
        print()

        # 4. Slack notification (optional, still uses MCP)
        # if "slack" in MCP_CONFIG:
        #     print("[4/4] Sending Slack notification...")
        #     from langchain_mcp_adapters.client import MultiServerMCPClient
        #     from langchain_mcp_adapters.tools import load_mcp_tools

        #     client = MultiServerMCPClient(MCP_CONFIG)
        #     async with client.session("slack") as slack_session:
        #         slack_tools = await load_mcp_tools(slack_session)
        #         messenger_app = build_messenger_graph().compile()
        #         messenger_out = await messenger_app.ainvoke({
        #             "pr_id": pr_id,
        #             "summary": review_out["summary"],
        #             "tools": slack_tools,
        #             "pr_metadata": diff_out["pr_metadata"],
        #         })
        #         print(f"=== SLACK === {messenger_out['status']}")
        # else:
        #     print("[4/4] Slack: skipped (not configured)")

    finally:
        await provider.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <PR_ID>")
        raise SystemExit(1)
    try:
        pr = int(sys.argv[1])
    except ValueError:
        print(f"Error: PR_ID must be an integer, got '{sys.argv[1]}'")
        raise SystemExit(1)
    asyncio.run(main(pr_id=pr))

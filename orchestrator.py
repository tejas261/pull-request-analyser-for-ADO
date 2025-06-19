import os
import asyncio

from config import MCP_CONFIG
from agents.diffChecker import build_diff_checker_graph
from agents.reviewer import build_review_graph
from agents.commenter import build_commenter_graph
from agents.messenger import build_messenger_graph   
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

async def main(pr_id: int):
    client = MultiServerMCPClient(MCP_CONFIG)
    async with client.session("azureDevOps") as azure_session, client.session("slack") as slack_session:
        all_azure_tools = await load_mcp_tools(azure_session)
        pr_tools = [t for t in all_azure_tools if t.name in (
            "list_repositories", "list_pull_requests", "add_pull_request_comment"
        )]

        slack_tools = await load_mcp_tools(slack_session)

        # 1. Diff Checker
        diff_app = build_diff_checker_graph().compile()
        diff_out = await diff_app.ainvoke({"pr_id": pr_id, "tools": pr_tools})
        print("=== DIFF ===\n", diff_out["diff"], "\n")

        # 2. Review
        review_app = build_review_graph().compile()
        review_out = await review_app.ainvoke({
            "pr_id":        pr_id,
            "repo_id":      diff_out["repo_id"],
            "diff":         diff_out["diff"],
            "tools":        pr_tools,
            "file_changes": diff_out.get("file_changes", []),
        })
        print("=== REVIEW ===\n", review_out["summary"], "\n")

        # 3. Commenter
        comment_app = build_commenter_graph().compile()
        comment_out = await comment_app.ainvoke({
            "pr_id": pr_id,
            "repo_id": diff_out["repo_id"],
            "summary": review_out["summary"],
            "tools": pr_tools,
            "file_changes": diff_out.get("file_changes", []) 
        })
        print("=== COMMENT ===\n", comment_out["status"])

        # 4. Messenger (Slack)
        messenger_app = build_messenger_graph().compile()
        messenger_out = await messenger_app.ainvoke({
            "pr_id": pr_id,
            "repo_id": diff_out["repo_id"],
            "summary": review_out["summary"],
            "tools": slack_tools,
            "pr_data": review_out["pr_data"],
        })
        print("=== SLACK ===\n", messenger_out["status"])

if __name__ == "__main__":
    pr = int(os.getenv("PR_ID", "0"))
    asyncio.run(main(pr_id=pr))
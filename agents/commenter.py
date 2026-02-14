from langgraph.graph import StateGraph, START, END
from config import PROJECT
import difflib

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import os

GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4o-mini')  # Fallback model

async def post_comment(state: dict) -> dict:
    """Post inline PR comments summarizing code changes with an LLM."""
    tools = state["tools"]
    pr_id: int = state["pr_id"]
    repo_id: str = state["repo_id"]

    add_comment = next((t for t in tools if t.name == "add_pull_request_comment"), None)
    if add_comment is None:
        raise ValueError("Required tool 'add_pull_request_comment' not available.")

    # 1. Post summary comment (unchanged) Not necessary 
    # body = state.get("summary")
    # if isinstance(body, str) and body.strip():
    #     payload = {
    #         "projectId":     PROJECT,
    #         "repositoryId":  repo_id,
    #         "pullRequestId": pr_id,
    #         "content":       body,
    #         "status":        "active"
    #     }
    #     await add_comment.arun(payload)

    # 2. Post summarized inline comments using LLM for change summaries
    file_changes = state.get("file_changes", [])
    max_comments_per_file = 3            # Limit per file
    min_hunk_length = 3                  # Minimum number of edited lines to consider

    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.2)

    if not file_changes:
        return {"status": "No file changes detected; no inline comments posted."}

    for file in file_changes:
        path = file["path"]
        before = file["before"].splitlines()
        after = file["after"].splitlines()

        sm = difflib.SequenceMatcher(None, before, after)
        opcodes = sm.get_opcodes()
        inlines = []

        for tag, i1, i2, j1, j2 in opcodes:
            if tag in ("replace", "insert", "delete"):
                before_block = before[i1:i2]
                after_block = after[j1:j2]
                # Skip tiny/insignificant changes (single blank etc)
                if len(after_block) < min_hunk_length:
                    if (len(after_block) == 1 and after_block and after_block[0].strip() != ""):
                        pass
                    else:
                        continue
                # Only summarize if it's not blank
                summary_lines = [line for line in after_block if line.strip() != ""]
                if not summary_lines:
                    continue

                # Compose input for the LLM
                prompt = (
                    f"File: {path}\n"
                    f"Lines {j1+1}-{j2}: summarize the change below for a code reviewer.\n"
                    f"--- BEFORE ---\n{chr(10).join(before_block)}\n"
                    f"--- AFTER ---\n{chr(10).join(after_block)}\n"
                    "Give a concise, clear summary for a code review comment. Only describe what and why, do not repeat the code."
                )

                resp = await llm.ainvoke([HumanMessage(content=prompt)])
                inline_comment = {
                    "filePath":   path,
                    "lineNumber": j1 + 1,
                    "content":    resp.content.strip()
                }
                inlines.append(inline_comment)

        # Post up to N comments per file
        inlines = inlines[:max_comments_per_file]
        for comment in inlines:
            payload = {
                "projectId":     PROJECT,
                "repositoryId":  repo_id,
                "pullRequestId": pr_id,
                "content":       comment["content"],
                "filePath":      comment["filePath"],
                "lineNumber":    comment["lineNumber"],
                "status":        "active"
            }
            await add_comment.arun(payload)

    return {"status": "Summary and valuable LLM-based inline comments posted successfully!"}

def build_commenter_graph() -> StateGraph:
    """Build the commenter graph that posts inline review comments."""
    g = StateGraph(state_schema=dict)
    g.add_node("post_comment", post_comment)
    g.add_edge(START, "post_comment")
    g.add_edge("post_comment", END)
    return g
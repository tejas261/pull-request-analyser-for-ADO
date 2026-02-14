import json
import aiohttp
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from config import PROJECT, ORG_URL, PAT
from utils import make_diff
from dotenv import load_dotenv
import os

load_dotenv(override=True)

GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4o-mini')

async def fetch_pr_details(state: dict) -> dict:
    """Fetch PR metadata via REST and ensure repo_id is set.

    Avoids relying on MCP tools for listing PRs to prevent StopIteration
    when PRs are paginated or filtered unexpectedly.
    """
    pr_id: int = state["pr_id"]

    url = f"{ORG_URL}/{PROJECT}/_apis/git/pullrequests/{pr_id}?api-version=7.1"
    auth = aiohttp.BasicAuth("", PAT)
    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(auth=auth, connector=conn) as sess:
        async with sess.get(url) as resp:
            if resp.status == 404:
                raise ValueError(f"PR '{pr_id}' not found in project '{PROJECT}'")
            resp.raise_for_status()
            pr_data = await resp.json()

    repo = pr_data.get("repository") or {}
    repo_id = repo.get("id")
    if not repo_id:
            raise ValueError("Unable to resolve repository ID from PR data")

    return {
        "pr_data": pr_data,
        "repo_id": repo_id,
        "diff": state.get("diff", ""),
        "pr_id": pr_id,
        "tools": state.get("tools"),
        "file_changes": state.get("file_changes", []),
    }

async def analyze(state: dict) -> dict:
    """Analyze PR changes using the LLM and produce a markdown summary."""
    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)
    pr_meta       = state["pr_data"]
    diff          = state["diff"]
    file_changes  = state["file_changes"]

    descs = []
    for ch in file_changes:
        d = make_diff(ch["before"], ch["after"], ch["path"])
        excerpt = "\n".join(d.splitlines()[:200])
        descs.append(f"--- {ch['path']} ---\n{excerpt}\n")
    all_desc = "\n".join(descs)

    prompt = (
        "You are a senior frontend engineer with deep expertise in best practices, performance, security, "
        "and user experience in modern web applications.\n\n"
        "PR Metadata:\n"
        f"{json.dumps(pr_meta, indent=2)}\n\n"
        "Changed Files:\n"
        "List of file paths that were modified:\n"
        f"{diff}\n\n"
        "File Contents:\n"
        "For each file above, you have the ‘before’ and ‘after’ code blocks.\n"
        f"{all_desc}\n\n"
        "TASK:\n"
        "Please produce a comprehensive Pull Request review that includes:\n"
        "  1. Summary of Changes:\n"
        "     – What features or components were added, removed, or refactored?\n"
        "     – High-level description of the intent behind each change.\n\n"
        "  2. UI/UX & Layout:\n"
        "     – Evaluate consistency with established design patterns and visual language.\n"
        "     – Identify broken layouts, responsiveness issues, or visual regressions.\n"
        "     – Highlight any UI/UX improvements or inconsistencies (spacing, alignment, interactions).\n\n"
        "  3. Best Practices & Style:\n"
        "     – Consistency with existing code style (naming, patterns, formatting).\n"
        "     – Performance considerations (rendering efficiency, bundle size, hooks usage).\n"
        "     – Maintainability (separation of concerns, readability, reusability).\n\n"
        "  4. Security & Accessibility:\n"
        "     – Potential security vulnerabilities (XSS, injection, insecure dependencies).\n"
        "     – Accessibility gaps (ARIA attributes, keyboard navigation, color contrast, screen reader support).\n\n"
        "  5. Test Coverage:\n"
        "     – Identify missing unit or integration tests for new or modified components.\n"
        "     – Recommend specific test cases and strategies to improve coverage.\n\n"
        "  6. Suggestions & References:\n"
        "     – Provide concrete code snippets or links to relevant documentation and standards.\n\n"
        "FORMAT:\n"
        "- Use Markdown with headings for each section.\n"
        "- Bullet-point feedback under each heading.\n"
        "- If you reference a specific file or line number, prefix with `File: <path>`.\n\n"
    )

    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"summary": resp.content, "pr_data": pr_meta,}

def build_review_graph() -> StateGraph:
    """Build the review graph consisting of metadata fetch and analysis."""
    g = StateGraph(state_schema=dict)
    g.add_node("fetch_pr_details", fetch_pr_details)
    g.add_node("analyze", analyze)
    g.add_edge(START, "fetch_pr_details")
    g.add_edge("fetch_pr_details", "analyze")
    g.add_edge("analyze", END)
    return g

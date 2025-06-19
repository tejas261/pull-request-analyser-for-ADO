import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from config import PROJECT, REPO_NAME
from utils import make_diff
from dotenv import load_dotenv
import os

load_dotenv(override=True)

GPT_MODEL = os.getenv('GPT_MODEL')

async def fetch_pr_details(state: dict):
    pr_id = state["pr_id"]
    tools = state["tools"]
    # find repo id
    list_repos = next(t for t in tools if t.name == "list_repositories")
    raw_repos = await list_repos.arun({"project": PROJECT})
    repos_data = json.loads(raw_repos) if isinstance(raw_repos, str) else raw_repos
    if isinstance(repos_data, dict):
        repo_list = repos_data.get("value", [])
    elif isinstance(repos_data, list):
        repo_list = repos_data
    else:
        raise ValueError(f"Unexpected shape for list_repositories: {type(repos_data)}")
    repo = next(r for r in repo_list if r["name"] == REPO_NAME)
    repo_id = repo["id"]
    # find PR metadata
    list_prs = next(t for t in tools if t.name == "list_pull_requests")
    raw_prs  = await list_prs.arun({"project": PROJECT, "repositoryId": repo_id})
    prs_data = json.loads(raw_prs) if isinstance(raw_prs, str) else raw_prs
    if isinstance(prs_data, dict):
        prs_list = prs_data.get("value", [])
    elif isinstance(prs_data, list):
        prs_list = prs_data
    else:
        raise ValueError(f"Unexpected shape for list_pull_requests: {type(prs_data)}")
    normalized = [json.loads(i) if isinstance(i, str) else i for i in prs_list]
    pr = next(p for p in normalized if str(p.get("pullRequestId", p.get("id"))) == str(pr_id))
    return {
        "pr_data": pr,
        "repo_id": repo_id,
        "diff": state.get("diff", ""),
        "pr_id": pr_id,
        "tools": state.get("tools"),
        "file_changes": state.get("file_changes", [])
    }

async def analyze(state: dict):
    llm           = ChatOpenAI(model=GPT_MODEL, temperature=0.1)
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

def build_review_graph():
    g = StateGraph(state_schema=dict)
    g.add_node("fetch_pr_details", fetch_pr_details)
    g.add_node("analyze",          analyze)
    g.add_edge(START, "fetch_pr_details")
    g.add_edge("fetch_pr_details", "analyze")
    g.add_edge("analyze", END)
    return g

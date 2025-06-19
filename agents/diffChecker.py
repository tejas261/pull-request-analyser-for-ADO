import json
import aiohttp
from langgraph.graph import StateGraph, START, END
from config import ORG_URL, PROJECT, REPO_NAME, PAT

async def resolve_repo(state: dict):
    pr_id = state["pr_id"]
    tools = state["tools"]
    list_repos = next(t for t in tools if t.name == "list_repositories")
    raw = await list_repos.arun({"project": PROJECT})
    data = json.loads(raw) if isinstance(raw, str) else raw

    repos = data.get("value", []) if isinstance(data, dict) else data
    match = next((r for r in repos if r.get("name") == REPO_NAME), None)
    if not match:
        raise ValueError(f"Repo '{REPO_NAME}' not found in '{PROJECT}'")
    return {"repo_id": match["id"], "pr_id": pr_id}

async def list_iterations(state: dict):
    repo_id = state["repo_id"]; pr_id = state["pr_id"]
    url = (
        f"{ORG_URL}/{PROJECT}/_apis/git/repositories/"
        f"{repo_id}/pullRequests/{pr_id}/iterations?api-version=7.1"
    )
    auth = aiohttp.BasicAuth("", PAT)
    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(auth=auth, connector=conn) as sess:
        async with sess.get(url) as resp:
            resp.raise_for_status()
            payload = await resp.json()
    iters = payload.get("value", payload) if isinstance(payload, dict) else payload
    latest_iteration = max(iters, key=lambda i: i["id"])
    return {"latest_iteration": latest_iteration, "repo_id": repo_id, "pr_id": pr_id}

async def get_changes(state: dict):
    from utils import make_diff  # only for context; actual diffing is done in review
    repo_id          = state["repo_id"]
    pr_id            = state["pr_id"]
    latest_iteration = state["latest_iteration"]
    iter_id          = latest_iteration["id"]
    head_commit      = latest_iteration["sourceRefCommit"]["commitId"]
    base_commit      = latest_iteration["commonRefCommit"]["commitId"]

    auth = aiohttp.BasicAuth("", PAT)
    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(auth=auth, connector=conn) as sess:
        # list changes
        changes_url = (
            f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
            f"/pullRequests/{pr_id}/iterations/{iter_id}/changes?api-version=7.1"
        )
        async with sess.get(changes_url) as resp:
            resp.raise_for_status()
            changes = await resp.json()
        paths = [
            e["item"]["path"]
            for e in changes.get("changeEntries", [])
            if e.get("changeType") in ("edit", "rename")
        ]

        # fetch content helper
        async def fetch_content(commit_id: str, path: str) -> str:
            url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/items"
            params = {
                "path": path,
                "includeContent": "true",
                "resolveLfs": "true",
                "versionDescriptor.versionType": "commit",
                "versionDescriptor.version": commit_id,
                "api-version": "7.1",
            }
            async with sess.get(url, params=params) as resp:
                if resp.status == 404:
                    return ""
                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "")
                if "application/json" in ctype:
                    data = await resp.json()
                    return data.get("content", "")
                return await resp.text()

        file_changes = []
        for p in paths:
            before = await fetch_content(base_commit, p)
            after  = await fetch_content(head_commit, p)
            file_changes.append({"path": p, "before": before, "after": after})

    return {
        "diff": "\n".join(paths),
        "repo_id": repo_id,
        "pr_id": pr_id,
        "file_changes": file_changes,
    }

def build_diff_checker_graph():
    g = StateGraph(state_schema=dict)
    g.add_node("resolve_repo",    resolve_repo)
    g.add_node("list_iterations", list_iterations)
    g.add_node("get_changes",     get_changes)
    g.add_edge(START, "resolve_repo")
    g.add_edge("resolve_repo", "list_iterations")
    g.add_edge("list_iterations", "get_changes")
    g.add_edge("get_changes", END)
    return g

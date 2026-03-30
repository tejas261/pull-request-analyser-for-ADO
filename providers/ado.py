"""Azure DevOps provider — direct REST API calls."""

from __future__ import annotations
from typing import List, Optional
import aiohttp

from config import ORG_URL, PROJECT, PAT
from providers.base import PRProvider, PRMetadata, FileChange
from retry import with_retry


class ADOProvider(PRProvider):
    """Talks to Azure DevOps REST API v7.1."""

    def __init__(self) -> None:
        self._auth = aiohttp.BasicAuth("", PAT)
        self._session: Optional[aiohttp.ClientSession] = None
        self._repo_id: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            conn = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(auth=self._auth, connector=conn)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── helpers ──────────────────────────────────────────────────────

    @with_retry
    async def _get_json(self, url: str, **params) -> dict:
        sess = await self._get_session()
        async with sess.get(url, params=params) as resp:
            if resp.status == 404:
                return {}
            resp.raise_for_status()
            return await resp.json()

    @with_retry
    async def _get_text(self, url: str, **params) -> str:
        sess = await self._get_session()
        async with sess.get(url, params=params) as resp:
            if resp.status == 404:
                return ""
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                data = await resp.json()
                return data.get("content", "")
            return await resp.text()

    async def _resolve_repo_id(self, pr_id: int) -> str:
        if self._repo_id:
            return self._repo_id
        data = await self._get_json(
            f"{ORG_URL}/{PROJECT}/_apis/git/pullrequests/{pr_id}",
            **{"api-version": "7.1"},
        )
        repo = data.get("repository") or {}
        rid = repo.get("id")
        if not rid:
            raise ValueError(f"Cannot resolve repo ID for PR {pr_id}")
        self._repo_id = rid
        return rid

    async def _fetch_content(self, repo_id: str, commit_id: str, path: str) -> str:
        url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/items"
        return await self._get_text(
            url,
            path=path,
            includeContent="true",
            resolveLfs="true",
            **{
                "versionDescriptor.versionType": "commit",
                "versionDescriptor.version": commit_id,
                "api-version": "7.1",
            },
        )

    # ── public API ───────────────────────────────────────────────────

    async def get_pr_metadata(self, pr_id: int) -> PRMetadata:
        data = await self._get_json(
            f"{ORG_URL}/{PROJECT}/_apis/git/pullrequests/{pr_id}",
            **{"api-version": "7.1"},
        )
        if not data:
            raise ValueError(f"PR {pr_id} not found in project {PROJECT}")

        repo = data.get("repository") or {}
        self._repo_id = repo.get("id", "")
        repo_name = repo.get("name", "")

        reviewers_raw = data.get("reviewers", [])
        reviewer_names = [
            r.get("displayName") or r.get("uniqueName", "") for r in reviewers_raw
        ]

        return PRMetadata(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            author=(data.get("createdBy") or {}).get("displayName", ""),
            reviewers=reviewer_names,
            reviewer_details=reviewers_raw,
            source_branch=data.get("sourceRefName", ""),
            target_branch=data.get("targetRefName", ""),
            url=f"{ORG_URL}/{PROJECT}/_git/{repo_name}/pullrequest/{pr_id}",
            raw=data,
        )

    async def get_file_changes(self, pr_id: int) -> List[FileChange]:
        repo_id = await self._resolve_repo_id(pr_id)

        # get latest iteration
        iters_data = await self._get_json(
            f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
            f"/pullRequests/{pr_id}/iterations",
            **{"api-version": "7.1"},
        )
        iters = iters_data.get("value", iters_data)
        if isinstance(iters, dict):
            iters = [iters]
        latest = max(iters, key=lambda i: i["id"])
        iter_id = latest["id"]
        head_commit = latest["sourceRefCommit"]["commitId"]
        base_commit = latest["commonRefCommit"]["commitId"]

        # get change entries
        changes_data = await self._get_json(
            f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
            f"/pullRequests/{pr_id}/iterations/{iter_id}/changes",
            **{"api-version": "7.1"},
        )
        entries = changes_data.get("changeEntries", [])

        TYPE_MAP = {
            "edit": "edit",
            "rename": "rename",
            "add": "add",
            "delete": "delete",
            "rename, edit": "rename",
        }

        file_changes: List[FileChange] = []
        for entry in entries:
            raw_type = entry.get("changeType", "").lower().strip()
            change_type = TYPE_MAP.get(raw_type)
            if not change_type:
                continue

            item = entry.get("item", {})
            path = item.get("path", "")
            if not path or item.get("isFolder"):
                continue

            old_path = None
            if change_type == "rename":
                old_path = (entry.get("sourceServerItem") or "")

            before = ""
            after = ""
            if change_type in ("edit", "rename"):
                fetch_path = old_path or path
                before = await self._fetch_content(repo_id, base_commit, fetch_path)
                after = await self._fetch_content(repo_id, head_commit, path)
            elif change_type == "add":
                after = await self._fetch_content(repo_id, head_commit, path)
            elif change_type == "delete":
                before = await self._fetch_content(repo_id, base_commit, path)

            file_changes.append(
                FileChange(
                    path=path,
                    change_type=change_type,
                    before=before,
                    after=after,
                    old_path=old_path,
                )
            )

        return file_changes

    async def post_review_comment(
        self,
        pr_id: int,
        body: str,
        path: Optional[str] = None,
        line: Optional[int] = None,
    ) -> None:
        repo_id = await self._resolve_repo_id(pr_id)
        sess = await self._get_session()

        url = (
            f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
            f"/pullRequests/{pr_id}/threads?api-version=7.1"
        )

        thread: dict = {
            "comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
            "status": "active",
        }
        if path:
            thread_context: dict = {"filePath": path}
            if line:
                thread_context["rightFileStart"] = {"line": line, "offset": 1}
                thread_context["rightFileEnd"] = {"line": line, "offset": 1}
            thread["threadContext"] = thread_context

        async with sess.post(url, json=thread) as resp:
            resp.raise_for_status()

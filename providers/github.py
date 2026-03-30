"""GitHub provider — direct REST API calls."""

from __future__ import annotations
import base64
import ssl
from typing import List, Optional
import aiohttp
import certifi

from config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
from providers.base import PRProvider, PRMetadata, FileChange
from retry import with_retry

BASE = "https://api.github.com"


class GitHubProvider(PRProvider):
    """Talks to GitHub REST API v3."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._head_sha: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            self._session = aiohttp.ClientSession(
                headers=headers, connector=connector
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── helpers ──────────────────────────────────────────────────────

    @with_retry
    async def _get_json(self, url: str, **params) -> dict | list:
        sess = await self._get_session()
        async with sess.get(url, params=params or None) as resp:
            if resp.status == 404:
                return {}
            resp.raise_for_status()
            return await resp.json()

    @with_retry
    async def _post_json(self, url: str, payload: dict) -> dict:
        sess = await self._get_session()
        async with sess.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _fetch_file(self, path: str, ref: str) -> str:
        """Fetch file content at a given git ref."""
        url = f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
        sess = await self._get_session()
        async with sess.get(url, params={"ref": ref}) as resp:
            if resp.status == 404:
                return ""
            resp.raise_for_status()
            data = await resp.json()
            content = data.get("content", "")
            encoding = data.get("encoding", "")
            if encoding == "base64" and content:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            return content

    # ── public API ───────────────────────────────────────────────────

    async def get_pr_metadata(self, pr_id: int) -> PRMetadata:
        url = f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_id}"
        data = await self._get_json(url)
        if not data:
            raise ValueError(
                f"PR {pr_id} not found in {GITHUB_OWNER}/{GITHUB_REPO}"
            )

        reviewers_raw = data.get("requested_reviewers", [])
        reviewer_names = [r.get("login", "") for r in reviewers_raw]

        user = data.get("user") or {}
        self._head_sha = (data.get("head") or {}).get("sha")

        return PRMetadata(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("body", "") or "",
            author=user.get("login", ""),
            reviewers=reviewer_names,
            reviewer_details=reviewers_raw,
            source_branch=(data.get("head") or {}).get("ref", ""),
            target_branch=(data.get("base") or {}).get("ref", ""),
            url=data.get("html_url", ""),
            raw=data,
        )

    async def get_file_changes(self, pr_id: int) -> List[FileChange]:
        # Get PR details for base/head refs
        pr_url = f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_id}"
        pr_data = await self._get_json(pr_url)
        if not pr_data:
            raise ValueError(f"PR {pr_id} not found")

        base_ref = (pr_data.get("base") or {}).get("sha", "")
        head_ref = (pr_data.get("head") or {}).get("sha", "")
        self._head_sha = head_ref

        # List changed files (paginated up to 300)
        files_url = f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_id}/files"
        all_files: list = []
        page = 1
        while True:
            batch = await self._get_json(files_url, per_page="100", page=str(page))
            if not batch or not isinstance(batch, list):
                break
            all_files.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        STATUS_MAP = {
            "added": "add",
            "removed": "delete",
            "modified": "edit",
            "renamed": "rename",
            "changed": "edit",
            "copied": "add",
        }

        file_changes: List[FileChange] = []
        for f in all_files:
            status = f.get("status", "modified")
            change_type = STATUS_MAP.get(status, "edit")
            path = f.get("filename", "")
            old_path = f.get("previous_filename")

            before = ""
            after = ""
            if change_type in ("edit", "rename"):
                fetch_path = old_path or path
                before = await self._fetch_file(fetch_path, base_ref)
                after = await self._fetch_file(path, head_ref)
            elif change_type == "add":
                after = await self._fetch_file(path, head_ref)
            elif change_type == "delete":
                before = await self._fetch_file(path, base_ref)

            file_changes.append(
                FileChange(
                    path=path,
                    change_type=change_type,
                    before=before,
                    after=after,
                    old_path=old_path if change_type == "rename" else None,
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
        if path and line and self._head_sha:
            # Inline review comment
            url = (
                f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/pulls/{pr_id}/comments"
            )
            payload = {
                "body": body,
                "commit_id": self._head_sha,
                "path": path,
                "line": line,
                "side": "RIGHT",
            }
            try:
                await self._post_json(url, payload)
            except aiohttp.ClientResponseError:
                # Fall back to general comment if inline fails
                # (e.g. line not part of diff)
                await self._post_general_comment(pr_id, f"**{path}:{line}**\n\n{body}")
        else:
            await self._post_general_comment(pr_id, body)

    async def _post_general_comment(self, pr_id: int, body: str) -> None:
        url = (
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{pr_id}/comments"
        )
        await self._post_json(url, {"body": body})

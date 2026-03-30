"""Tests for provider implementations using mocked HTTP responses."""

import pytest
import json
import base64
from unittest.mock import patch, AsyncMock


# ── GitHub Provider Tests ────────────────────────────────────────────


class TestGitHubProviderMetadata:
    @pytest.fixture
    def mock_pr_response(self):
        return {
            "title": "Fix login bug",
            "body": "Fixes the auth redirect issue",
            "user": {"login": "testuser"},
            "head": {"ref": "fix/login", "sha": "abc123"},
            "base": {"ref": "main", "sha": "def456"},
            "html_url": "https://github.com/owner/repo/pull/1",
            "requested_reviewers": [{"login": "reviewer1"}],
        }

    @pytest.mark.asyncio
    async def test_get_pr_metadata_parses_correctly(self, mock_pr_response):
        with patch.dict("os.environ", {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_OWNER": "owner",
            "GITHUB_REPO": "repo",
            "PLATFORM": "github",
            "OPENAI_API_KEY": "test",
        }):
            # We need to reimport to pick up env vars
            import importlib
            import config
            importlib.reload(config)

            from providers.github import GitHubProvider
            provider = GitHubProvider()

            # Mock the _get_json method
            provider._get_json = AsyncMock(return_value=mock_pr_response)

            metadata = await provider.get_pr_metadata(1)
            assert metadata.title == "Fix login bug"
            assert metadata.author == "testuser"
            assert metadata.source_branch == "fix/login"
            assert metadata.target_branch == "main"
            assert "reviewer1" in metadata.reviewers
            await provider.close()


class TestGitHubProviderFileChanges:
    @pytest.mark.asyncio
    async def test_handles_all_change_types(self):
        with patch.dict("os.environ", {
            "GITHUB_TOKEN": "test-token",
            "GITHUB_OWNER": "owner",
            "GITHUB_REPO": "repo",
            "PLATFORM": "github",
            "OPENAI_API_KEY": "test",
        }):
            import importlib
            import config
            importlib.reload(config)

            from providers.github import GitHubProvider
            provider = GitHubProvider()

            pr_data = {
                "base": {"sha": "base123"},
                "head": {"sha": "head456"},
            }
            files_data = [
                {"filename": "new.py", "status": "added"},
                {"filename": "edit.py", "status": "modified"},
                {"filename": "old.py", "status": "removed"},
                {"filename": "moved.py", "status": "renamed", "previous_filename": "original.py"},
            ]

            call_count = 0
            async def mock_get_json(url, **params):
                nonlocal call_count
                if "pulls/" in url and "/files" not in url:
                    return pr_data
                return files_data

            provider._get_json = mock_get_json
            provider._fetch_file = AsyncMock(return_value="content")

            changes = await provider.get_file_changes(1)
            assert len(changes) == 4
            types = {c.change_type for c in changes}
            assert types == {"add", "edit", "delete", "rename"}
            await provider.close()


# ── Synthesizer Integration (no mocking needed) ────────────────────

class TestSynthesizerIntegration:
    def test_end_to_end(self):
        from agents.types import ReviewResult, ReviewComment
        from agents.reviewers.synthesizer import synthesize

        results = [
            ReviewResult(
                agent_name="security",
                comments=[
                    ReviewComment(
                        file_path="api.py", line_number=5, severity="critical",
                        category="security", comment="SQL injection",
                        suggestion="Use params", confidence=0.95,
                    ),
                ],
                summary="Found 1 critical security issue.",
            ),
            ReviewResult(
                agent_name="best_practices",
                comments=[
                    ReviewComment(
                        file_path="api.py", line_number=10, severity="minor",
                        category="best-practice", comment="Bare except",
                        suggestion="Use except Exception", confidence=0.8,
                    ),
                ],
                summary="Code quality is generally good.",
            ),
        ]

        comments, md = synthesize(results, 200)
        assert len(comments) == 2
        assert comments[0].severity == "critical"
        assert "CRITICAL" in md
        assert "SQL injection" in md

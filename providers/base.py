"""Abstract interface every PR platform provider must implement."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FileChange:
    """Represents a single file changed in the PR."""

    path: str
    change_type: str  # "add", "edit", "delete", "rename"
    before: str = ""  # empty for adds
    after: str = ""  # empty for deletes
    old_path: Optional[str] = None  # set for renames


@dataclass
class PRMetadata:
    """Normalised PR metadata across platforms."""

    pr_id: int
    title: str
    description: str
    author: str
    reviewers: List[str] = field(default_factory=list)
    reviewer_details: List[dict] = field(default_factory=list)
    source_branch: str = ""
    target_branch: str = ""
    url: str = ""
    raw: dict = field(default_factory=dict)


class PRProvider(ABC):
    """Interface for fetching PR data and posting comments."""

    @abstractmethod
    async def get_pr_metadata(self, pr_id: int) -> PRMetadata:
        ...

    @abstractmethod
    async def get_file_changes(self, pr_id: int) -> List[FileChange]:
        ...

    @abstractmethod
    async def post_review_comment(
        self,
        pr_id: int,
        body: str,
        path: Optional[str] = None,
        line: Optional[int] = None,
    ) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources (sessions, etc.)."""
        ...

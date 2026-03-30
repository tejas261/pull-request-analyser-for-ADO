"""Shared types for review agents."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class ReviewComment(BaseModel):
    """A single review finding with severity and actionable suggestion."""

    file_path: str = ""
    line_number: Optional[int] = None
    severity: Literal["critical", "major", "minor", "nit"] = "minor"
    category: Literal[
        "security",
        "best-practice",
        "style",
        "test-coverage",
        "performance",
        "accessibility",
        "dependency",
        "pr-description",
    ] = "best-practice"
    comment: str = ""
    suggestion: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ReviewResult(BaseModel):
    """Aggregated output from a single specialized reviewer."""

    agent_name: str = ""
    comments: List[ReviewComment] = Field(default_factory=list)
    summary: str = ""

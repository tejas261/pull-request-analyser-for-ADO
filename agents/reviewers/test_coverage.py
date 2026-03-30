"""Test-coverage reviewer — identifies missing tests and test-to-code mapping gaps."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GPT_MODEL
from agents.types import ReviewResult, ReviewComment
from agents.router import find_test_pairs
from utils import make_diff

SYSTEM_PROMPT = """\
You are a senior QA/test engineer reviewing code changes for test coverage gaps.

Your job:
1. Identify changed source code that lacks corresponding test changes.
2. Suggest specific test cases that should be written.
3. Review test quality if test files are included in the changes.

For every finding:
- severity: "major" (untested critical path), "minor" (nice-to-have test), "nit" (test improvement)
- category: always "test-coverage"
- confidence: 0.0-1.0
- suggestion: describe the specific test case to add

## Few-shot examples

Example 1 - Missing test for new function:
{
  "file_path": "src/utils/validator.ts",
  "line_number": 12,
  "severity": "major",
  "category": "test-coverage",
  "comment": "New `validateEmail()` function added but no test file updated. This validates user input and should have edge-case coverage.",
  "suggestion": "Add tests in validator.test.ts: valid email, missing @, unicode chars, empty string, max-length boundary.",
  "confidence": 0.90
}

Example 2 - Weak assertion:
{
  "file_path": "tests/test_api.py",
  "line_number": 45,
  "severity": "minor",
  "category": "test-coverage",
  "comment": "Test only asserts status code 200 but doesn't verify response body or side effects.",
  "suggestion": "Add assertions for response JSON shape and verify database state changed.",
  "confidence": 0.75
}

Respond with ONLY valid JSON matching the ReviewResult schema.
"""


async def run_test_coverage_review(
    file_changes: list, pr_metadata: dict
) -> ReviewResult:
    """Check for test coverage gaps in the PR."""
    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)

    # Static analysis: find source files without corresponding test changes
    missing_pairs = find_test_pairs(file_changes)
    static_comments = []
    for pair in missing_pairs:
        static_comments.append(
            ReviewComment(
                file_path=pair["source"],
                severity="major",
                category="test-coverage",
                comment=(
                    f"Source file changed but no corresponding test file was updated. "
                    f"Expected test file pattern: {pair['expected_test']}"
                ),
                suggestion="Add or update tests covering the changed functionality.",
                confidence=0.85,
            )
        )

    # LLM analysis for deeper test quality issues
    diffs = []
    for fc in file_changes:
        d = make_diff(fc.get("before", ""), fc.get("after", ""), fc["path"])
        if fc.get("change_type") == "add":
            diffs.append(f"=== {fc['path']} (NEW FILE) ===\n{fc.get('after', '')[:3000]}")
        elif d.strip():
            diffs.append(f"=== {fc['path']} ===\n{d[:3000]}")

    if not diffs:
        return ReviewResult(
            agent_name="test_coverage",
            comments=static_comments,
            summary="Static test-to-code mapping analysis only.",
        )

    user_prompt = (
        f"PR Title: {pr_metadata.get('title', '')}\n\n"
        "Review these changes for test coverage:\n\n"
        + "\n\n".join(diffs)
        + '\n\nRespond with JSON: {"agent_name": "test_coverage", "comments": [...], "summary": "..."}'
    )

    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        llm_result = ReviewResult.model_validate_json(raw)
        # Merge static + LLM findings
        all_comments = static_comments + llm_result.comments
        return ReviewResult(
            agent_name="test_coverage",
            comments=all_comments,
            summary=llm_result.summary,
        )
    except Exception:
        return ReviewResult(
            agent_name="test_coverage",
            comments=static_comments,
            summary="LLM analysis failed; showing static mapping results only.",
        )

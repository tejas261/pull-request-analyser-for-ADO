"""PR description validator — checks if the PR is well-documented."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GPT_MODEL
from agents.types import ReviewResult, ReviewComment


SYSTEM_PROMPT = """\
You are reviewing a Pull Request's description (not the code).

A good PR description should:
1. Explain WHAT changed (features, bug fixes, refactors)
2. Explain WHY it changed (motivation, ticket reference, user impact)
3. Note any breaking changes or migration steps
4. Mention testing done or how to test

Evaluate the PR description against these criteria given the list of changed files.

If the description is adequate, return empty comments.
If it's missing key information, return findings with:
- severity: "major" (empty or completely uninformative), "minor" (missing important details)
- category: always "pr-description"
- confidence: 0.0-1.0

Respond with ONLY valid JSON matching the ReviewResult schema.
"""


async def run_pr_description_review(
    pr_metadata: dict, changed_file_paths: list[str]
) -> ReviewResult:
    """Validate PR description quality."""
    description = pr_metadata.get("description", "") or ""
    title = pr_metadata.get("title", "") or ""

    # Quick check: empty or trivially short description
    if len(description.strip()) < 10:
        return ReviewResult(
            agent_name="pr_description",
            comments=[
                ReviewComment(
                    file_path="",
                    severity="major",
                    category="pr-description",
                    comment=(
                        f"PR description is empty or trivially short ({len(description.strip())} chars). "
                        "A good description should explain what changed, why, and how to test."
                    ),
                    suggestion="Add a description covering: what changed, why, any breaking changes, and testing steps.",
                    confidence=0.99,
                )
            ],
            summary="PR description is missing or inadequate.",
        )

    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)
    user_prompt = (
        f"PR Title: {title}\n"
        f"PR Description:\n{description}\n\n"
        f"Changed files ({len(changed_file_paths)}):\n"
        + "\n".join(f"  - {p}" for p in changed_file_paths[:50])
        + '\n\nRespond with JSON: {"agent_name": "pr_description", "comments": [...], "summary": "..."}'
    )

    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return ReviewResult.model_validate_json(raw)
    except Exception:
        return ReviewResult(
            agent_name="pr_description",
            comments=[],
            summary=resp.content[:500] if resp.content else "Parse error",
        )

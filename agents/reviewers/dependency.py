"""Dependency change reviewer — checks package.json, requirements.txt, etc."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GPT_MODEL
from agents.types import ReviewResult
from utils import make_diff

SYSTEM_PROMPT = """\
You are a supply-chain security and dependency management expert reviewing package/dependency file changes.

Focus on:
1. New dependencies: are they necessary? Are they well-maintained? Any known vulnerabilities?
2. Version changes: major bumps may introduce breaking changes. Are they justified?
3. Lockfile consistency: does the lockfile match the manifest?
4. Removed dependencies: could this break existing functionality?
5. Version pinning: are versions properly pinned or using unsafe ranges?

For every finding:
- severity: "critical" (known vulnerability or malicious package), "major" (risky version range or unnecessary dep), "minor" (improvement), "nit" (style)
- category: always "dependency"
- confidence: 0.0-1.0
- suggestion: concrete action to take

## Few-shot examples

Example 1 - Overly broad version range:
{
  "file_path": "package.json",
  "line_number": 15,
  "severity": "major",
  "category": "dependency",
  "comment": "Using '*' version for 'lodash' allows any version including ones with known prototype pollution vulnerabilities.",
  "suggestion": "Pin to a specific version: \\"lodash\\": \\"^4.17.21\\"",
  "confidence": 0.92
}

Example 2 - Unnecessary dependency:
{
  "file_path": "package.json",
  "line_number": 22,
  "severity": "minor",
  "category": "dependency",
  "comment": "Adding 'left-pad' (8 lines of code). This functionality exists natively via String.prototype.padStart().",
  "suggestion": "Remove dependency and use native padStart() instead.",
  "confidence": 0.88
}

Respond with ONLY valid JSON matching the ReviewResult schema.
"""


async def run_dependency_review(
    file_changes: list, pr_metadata: dict
) -> ReviewResult:
    """Review dependency file changes."""
    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)

    diffs = []
    for fc in file_changes:
        d = make_diff(fc.get("before", ""), fc.get("after", ""), fc["path"])
        if fc.get("change_type") == "add":
            diffs.append(f"=== {fc['path']} (NEW FILE) ===\n{fc.get('after', '')}")
        elif d.strip():
            diffs.append(f"=== {fc['path']} ===\n{d}")

    if not diffs:
        return ReviewResult(agent_name="dependency", comments=[], summary="No dependency changes.")

    user_prompt = (
        f"PR Title: {pr_metadata.get('title', '')}\n"
        f"PR Description: {pr_metadata.get('description', '')}\n\n"
        "Review these dependency file changes:\n\n"
        + "\n\n".join(diffs)
        + '\n\nRespond with JSON: {"agent_name": "dependency", "comments": [...], "summary": "..."}'
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
            agent_name="dependency",
            comments=[],
            summary=resp.content[:500] if resp.content else "Parse error",
        )

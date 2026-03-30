"""Security-focused reviewer agent."""

from __future__ import annotations
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GPT_MODEL
from agents.types import ReviewResult
from utils import make_diff

SYSTEM_PROMPT = """\
You are a senior application security engineer performing a code review.
Your ONLY job is to find security vulnerabilities. Do NOT comment on style, naming, or best practices.

For every finding you MUST provide:
- severity: "critical" (exploitable now), "major" (likely exploitable), "minor" (defense-in-depth), "nit" (hardening suggestion)
- confidence: 0.0-1.0 how certain you are this is a real issue
- A concrete suggestion showing how to fix it

If there are NO security issues, return an empty comments list. Do NOT invent findings.

## Few-shot examples

Example 1 - XSS:
{
  "file_path": "src/components/Comment.tsx",
  "line_number": 42,
  "severity": "critical",
  "category": "security",
  "comment": "Using dangerouslySetInnerHTML with user-supplied `comment.body` without sanitization enables stored XSS.",
  "suggestion": "Use DOMPurify: dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(comment.body)}}",
  "confidence": 0.95
}

Example 2 - SQL Injection:
{
  "file_path": "api/queries.py",
  "line_number": 18,
  "severity": "critical",
  "category": "security",
  "comment": "String interpolation in SQL query allows injection. `cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')`",
  "suggestion": "Use parameterized query: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
  "confidence": 0.98
}

Example 3 - Secrets in code:
{
  "file_path": "config/settings.py",
  "line_number": 5,
  "severity": "critical",
  "category": "security",
  "comment": "Hardcoded API key in source code. This will be committed to version control.",
  "suggestion": "Move to environment variable: os.getenv('API_KEY')",
  "confidence": 0.99
}

Respond with ONLY valid JSON matching the ReviewResult schema. No markdown, no explanation outside the JSON.
"""


async def run_security_review(file_changes: list, pr_metadata: dict) -> ReviewResult:
    """Analyse file changes for security vulnerabilities."""
    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)

    diffs = []
    for fc in file_changes:
        d = make_diff(fc.get("before", ""), fc.get("after", ""), fc["path"])
        if d.strip():
            diffs.append(f"=== {fc['path']} (change_type: {fc.get('change_type', 'edit')}) ===\n{d}")

    if not diffs:
        return ReviewResult(agent_name="security", comments=[], summary="No changes to review.")

    user_prompt = (
        "Review the following code changes for security vulnerabilities.\n\n"
        f"PR Title: {pr_metadata.get('title', '')}\n"
        f"PR Description: {pr_metadata.get('description', '')}\n\n"
        "Changed files:\n\n"
        + "\n\n".join(diffs)
        + "\n\nRespond with a JSON object matching: {\"agent_name\": \"security\", \"comments\": [...], \"summary\": \"...\"}"
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
            agent_name="security",
            comments=[],
            summary=resp.content[:500] if resp.content else "Parse error",
        )

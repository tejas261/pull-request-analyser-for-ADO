"""Best-practices and style reviewer agent — adapts prompt to file type."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GPT_MODEL
from agents.types import ReviewResult
from utils import make_diff

SYSTEM_PROMPT_TEMPLATE = """\
You are a senior {domain} engineer performing a code review focused on best practices, style, and performance.
Do NOT review security — a separate agent handles that.

For every finding you MUST provide:
- severity: "critical" (will cause bugs/outages), "major" (significant quality issue), "minor" (improvement), "nit" (style/preference)
- confidence: 0.0-1.0
- A concrete suggestion showing the fix. If you can't suggest a fix, don't mention it.

{domain_guidance}

## Few-shot examples

Example 1 - Performance (major):
{{
  "file_path": "src/Dashboard.tsx",
  "line_number": 15,
  "severity": "major",
  "category": "performance",
  "comment": "Creating a new object literal inside the render causes unnecessary re-renders of all children. This is inside a component rendered on every route change.",
  "suggestion": "Extract `{{ padding: 16 }}` to a module-level constant or use useMemo.",
  "confidence": 0.85
}}

Example 2 - Best practice (minor):
{{
  "file_path": "utils/format.py",
  "line_number": 30,
  "severity": "minor",
  "category": "best-practice",
  "comment": "Bare except catches SystemExit and KeyboardInterrupt, masking real errors.",
  "suggestion": "Use `except Exception:` instead of bare `except:`",
  "confidence": 0.92
}}

Example 3 - Nit:
{{
  "file_path": "src/api.ts",
  "line_number": 8,
  "severity": "nit",
  "category": "style",
  "comment": "Inconsistent naming: other API functions use camelCase but this one uses snake_case.",
  "suggestion": "Rename `get_user_data` to `getUserData` to match the existing convention.",
  "confidence": 0.80
}}

Respond with ONLY valid JSON matching the ReviewResult schema. No markdown outside JSON.
"""

FRONTEND_GUIDANCE = """\
Focus on:
- React/Vue/Svelte patterns (hooks rules, key props, effect dependencies)
- Rendering efficiency and unnecessary re-renders
- Bundle size impact (large imports, tree-shaking issues)
- Accessibility (ARIA, keyboard nav, color contrast, semantic HTML)
- CSS consistency (spacing, layout patterns, responsive design)
"""

BACKEND_GUIDANCE = """\
Focus on:
- Error handling (swallowed exceptions, missing error propagation)
- Resource management (unclosed connections, missing context managers)
- API design (consistent naming, proper HTTP methods, validation)
- Concurrency issues (race conditions, deadlocks, thread safety)
- Logging and observability
"""

GENERAL_GUIDANCE = """\
Focus on:
- Code clarity and readability
- DRY violations and unnecessary complexity
- Naming conventions consistency
- Dead code or commented-out code
- Missing input validation at system boundaries
"""


def _get_domain_info(file_category: str) -> tuple[str, str]:
    if file_category == "frontend":
        return "frontend", FRONTEND_GUIDANCE
    if file_category == "backend":
        return "backend", BACKEND_GUIDANCE
    return "software", GENERAL_GUIDANCE


async def run_best_practices_review(
    file_changes: list, pr_metadata: dict, file_category: str = "other"
) -> ReviewResult:
    """Review code for best practices, adapting to file type."""
    llm = ChatOpenAI(model=GPT_MODEL, temperature=0.1)
    domain, guidance = _get_domain_info(file_category)

    system = SYSTEM_PROMPT_TEMPLATE.format(domain=domain, domain_guidance=guidance)

    diffs = []
    for fc in file_changes:
        d = make_diff(fc.get("before", ""), fc.get("after", ""), fc["path"])
        # Include full after-content for new files
        if fc.get("change_type") == "add":
            diffs.append(
                f"=== {fc['path']} (NEW FILE) ===\n{fc.get('after', '')}"
            )
        elif d.strip():
            diffs.append(f"=== {fc['path']} ===\n{d}")

    if not diffs:
        return ReviewResult(agent_name="best_practices", comments=[], summary="No changes to review.")

    user_prompt = (
        f"PR Title: {pr_metadata.get('title', '')}\n"
        f"PR Description: {pr_metadata.get('description', '')}\n\n"
        "Review these changes for best practices, style, and performance:\n\n"
        + "\n\n".join(diffs)
        + '\n\nRespond with JSON: {"agent_name": "best_practices", "comments": [...], "summary": "..."}'
    )

    resp = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_prompt),
    ])

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return ReviewResult.model_validate_json(raw)
    except Exception:
        return ReviewResult(
            agent_name="best_practices",
            comments=[],
            summary=resp.content[:500] if resp.content else "Parse error",
        )

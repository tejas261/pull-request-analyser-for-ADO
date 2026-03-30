"""Synthesizer — merges results from all specialized reviewers, deduplicates, and prioritises."""

from __future__ import annotations
from typing import List
from config import COMMENT_SCALE_FACTOR
from agents.types import ReviewResult, ReviewComment

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3}
MIN_CONFIDENCE = 0.4


def compute_max_comments(total_changed_lines: int) -> int:
    """Scale comment limit with PR size."""
    return max(5, int(total_changed_lines * COMMENT_SCALE_FACTOR / 100))


def synthesize(
    results: List[ReviewResult],
    total_changed_lines: int,
) -> tuple[List[ReviewComment], str]:
    """Merge, deduplicate, filter, and prioritise review comments.

    Returns (filtered_comments, markdown_summary).
    """
    all_comments: List[ReviewComment] = []
    summaries: List[str] = []

    for r in results:
        all_comments.extend(r.comments)
        if r.summary:
            summaries.append(f"**{r.agent_name}**: {r.summary}")

    # Filter low-confidence
    all_comments = [c for c in all_comments if c.confidence >= MIN_CONFIDENCE]

    # Deduplicate by (file, line, category)
    seen: set = set()
    unique: List[ReviewComment] = []
    for c in all_comments:
        key = (c.file_path, c.line_number, c.category, c.comment[:60])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Sort by severity then confidence
    unique.sort(key=lambda c: (SEVERITY_ORDER.get(c.severity, 9), -c.confidence))

    # Apply smart limit
    max_comments = compute_max_comments(total_changed_lines)
    # Always keep all critical findings
    critical = [c for c in unique if c.severity == "critical"]
    non_critical = [c for c in unique if c.severity != "critical"]
    remaining_budget = max(0, max_comments - len(critical))
    filtered = critical + non_critical[:remaining_budget]

    # Build markdown summary
    md_parts = ["## PR Review Summary\n"]

    # Stats
    sev_counts = {}
    for c in filtered:
        sev_counts[c.severity] = sev_counts.get(c.severity, 0) + 1
    stats = " | ".join(f"**{s}**: {n}" for s, n in sorted(sev_counts.items(), key=lambda x: SEVERITY_ORDER.get(x[0], 9)))
    if stats:
        md_parts.append(f"Findings: {stats}\n")

    # Agent summaries
    if summaries:
        md_parts.append("### Agent Summaries\n")
        for s in summaries:
            md_parts.append(f"- {s}")
        md_parts.append("")

    # Detailed findings by severity
    for sev in ("critical", "major", "minor", "nit"):
        sev_comments = [c for c in filtered if c.severity == sev]
        if not sev_comments:
            continue
        badge = {"critical": "!!!", "major": "!!", "minor": "!", "nit": "~"}[sev]
        md_parts.append(f"### {badge} {sev.upper()} ({len(sev_comments)})\n")
        for c in sev_comments:
            loc = f"`{c.file_path}`" + (f":{c.line_number}" if c.line_number else "")
            md_parts.append(f"- **[{c.category}]** {loc}: {c.comment}")
            if c.suggestion:
                md_parts.append(f"  - Suggestion: {c.suggestion}")
        md_parts.append("")

    summary_md = "\n".join(md_parts)
    return filtered, summary_md

"""Review orchestrator — fans out to specialised reviewers, then synthesises."""

from __future__ import annotations
import asyncio
from langgraph.graph import StateGraph, START, END

from agents.router import partition_files, classify_file
from agents.chunker import chunk_file_changes
from agents.reviewers.security import run_security_review
from agents.reviewers.best_practices import run_best_practices_review
from agents.reviewers.test_coverage import run_test_coverage_review
from agents.reviewers.dependency import run_dependency_review
from agents.reviewers.pr_description import run_pr_description_review
from agents.reviewers.synthesizer import synthesize
from agents.types import ReviewResult
from utils import count_changed_lines


async def run_all_reviewers(state: dict) -> dict:
    """Fan-out to all specialised reviewers and collect results."""
    file_changes = state["file_changes"]
    pr_metadata = state["pr_metadata"]

    groups = partition_files(file_changes)
    chunks = chunk_file_changes(file_changes)

    tasks = []

    # ── Security review (all files) ──────────────────────────────────
    for chunk in chunks:
        tasks.append(run_security_review(chunk, pr_metadata))

    # ── Best-practices review (by file category per chunk) ───────────
    for chunk in chunks:
        chunk_groups = partition_files(chunk)
        for category, cat_files in chunk_groups.items():
            if category == "dependency":
                continue  # handled separately
            tasks.append(
                run_best_practices_review(cat_files, pr_metadata, category)
            )

    # ── Test-coverage review (all files) ─────────────────────────────
    tasks.append(run_test_coverage_review(file_changes, pr_metadata))

    # ── Dependency review (only if dependency files changed) ─────────
    dep_files = groups.get("dependency", [])
    if dep_files:
        tasks.append(run_dependency_review(dep_files, pr_metadata))

    # ── PR description review ────────────────────────────────────────
    changed_paths = [fc["path"] for fc in file_changes]
    tasks.append(run_pr_description_review(pr_metadata, changed_paths))

    # Run all in parallel
    results: list[ReviewResult] = await asyncio.gather(*tasks)

    # ── Synthesise ───────────────────────────────────────────────────
    total_lines = count_changed_lines(file_changes)
    filtered_comments, summary_md = synthesize(results, total_lines)

    return {
        "summary": summary_md,
        "review_comments": [c.model_dump() for c in filtered_comments],
        "pr_metadata": pr_metadata,
    }


def build_review_graph() -> StateGraph:
    """Build the review graph with fan-out to specialized agents."""
    g = StateGraph(state_schema=dict)
    g.add_node("run_all_reviewers", run_all_reviewers)
    g.add_edge(START, "run_all_reviewers")
    g.add_edge("run_all_reviewers", END)
    return g

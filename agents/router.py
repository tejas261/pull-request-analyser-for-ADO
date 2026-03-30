"""File-type classification for routing to specialized reviewers."""

from __future__ import annotations
from typing import List
import os

FRONTEND_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    ".css", ".scss", ".sass", ".less", ".html",
}
BACKEND_EXTS = {
    ".py", ".go", ".java", ".rs", ".rb", ".cs", ".php",
    ".kt", ".scala", ".ex", ".exs",
}
INFRA_PATTERNS = {
    "Dockerfile", "docker-compose", "Makefile", "Jenkinsfile",
    "azure-pipelines", ".github/workflows/",
}
INFRA_EXTS = {".tf", ".tfvars", ".hcl", ".yaml", ".yml"}
TEST_PATTERNS = {
    "test_", "_test.", ".test.", ".spec.", "__tests__/",
    "tests/", "testing/",
}
DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "Pipfile", "Pipfile.lock", "pyproject.toml",
    "poetry.lock", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "Gemfile.lock",
}


def classify_file(path: str) -> str:
    """Return one of: frontend, backend, infra, test, dependency, other."""
    basename = os.path.basename(path)
    _, ext = os.path.splitext(basename)

    if basename in DEPENDENCY_FILES:
        return "dependency"

    for pattern in TEST_PATTERNS:
        if pattern in path.lower():
            return "test"

    for pattern in INFRA_PATTERNS:
        if pattern in path:
            return "infra"
    if ext in INFRA_EXTS and not any(p in path for p in ("src/", "lib/", "app/")):
        return "infra"

    if ext in FRONTEND_EXTS:
        return "frontend"
    if ext in BACKEND_EXTS:
        return "backend"

    return "other"


def partition_files(file_changes: list) -> dict:
    """Group FileChange dicts by classification."""
    groups: dict[str, list] = {}
    for fc in file_changes:
        cat = classify_file(fc["path"])
        groups.setdefault(cat, []).append(fc)
    return groups


def find_test_pairs(file_changes: list) -> List[dict]:
    """Identify source files whose corresponding test files are missing from the PR.

    Returns a list of dicts: {"source": path, "expected_test": pattern}.
    """
    changed_paths = {fc["path"] for fc in file_changes}
    missing = []

    for fc in file_changes:
        cat = classify_file(fc["path"])
        if cat in ("test", "dependency", "infra"):
            continue

        path = fc["path"]
        basename = os.path.basename(path)
        name, ext = os.path.splitext(basename)

        # Common test naming conventions
        candidates = [
            f"test_{name}{ext}",
            f"{name}_test{ext}",
            f"{name}.test{ext}",
            f"{name}.spec{ext}",
        ]

        has_test = any(
            any(c in changed for c in candidates)
            for changed in changed_paths
        )
        if not has_test:
            missing.append({
                "source": path,
                "expected_test": f"test_{name}{ext} / {name}.test{ext} / {name}.spec{ext}",
            })

    return missing

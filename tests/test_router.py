"""Tests for the file-type router."""

import pytest
from agents.router import classify_file, partition_files, find_test_pairs


class TestClassifyFile:
    def test_frontend_tsx(self):
        assert classify_file("src/components/App.tsx") == "frontend"

    def test_frontend_css(self):
        assert classify_file("styles/main.css") == "frontend"

    def test_frontend_vue(self):
        assert classify_file("src/views/Home.vue") == "frontend"

    def test_backend_python(self):
        assert classify_file("api/views.py") == "backend"

    def test_backend_go(self):
        assert classify_file("cmd/server/main.go") == "backend"

    def test_dependency_package_json(self):
        assert classify_file("package.json") == "dependency"

    def test_dependency_requirements(self):
        assert classify_file("requirements.txt") == "dependency"

    def test_dependency_cargo_toml(self):
        assert classify_file("Cargo.toml") == "dependency"

    def test_test_file_python(self):
        assert classify_file("tests/test_api.py") == "test"

    def test_test_file_jest(self):
        assert classify_file("src/App.test.tsx") == "test"

    def test_test_file_spec(self):
        assert classify_file("src/utils.spec.ts") == "test"

    def test_infra_dockerfile(self):
        assert classify_file("Dockerfile") == "infra"

    def test_infra_github_workflow(self):
        assert classify_file(".github/workflows/ci.yml") == "infra"

    def test_other_markdown(self):
        assert classify_file("README.md") == "other"

    def test_other_json(self):
        assert classify_file("data/config.json") == "other"


class TestPartitionFiles:
    def test_groups_correctly(self):
        files = [
            {"path": "src/App.tsx"},
            {"path": "api/views.py"},
            {"path": "package.json"},
        ]
        groups = partition_files(files)
        assert "frontend" in groups
        assert "backend" in groups
        assert "dependency" in groups
        assert len(groups["frontend"]) == 1
        assert len(groups["backend"]) == 1


class TestFindTestPairs:
    def test_finds_missing_tests(self):
        files = [
            {"path": "src/utils/format.py"},
        ]
        missing = find_test_pairs(files)
        assert len(missing) == 1
        assert missing[0]["source"] == "src/utils/format.py"

    def test_no_missing_when_test_present(self):
        files = [
            {"path": "src/utils/format.py"},
            {"path": "tests/test_format.py"},
        ]
        missing = find_test_pairs(files)
        # format.py has a corresponding test_format.py
        assert all(m["source"] != "src/utils/format.py" for m in missing)

    def test_skips_test_files(self):
        files = [
            {"path": "tests/test_api.py"},
        ]
        missing = find_test_pairs(files)
        assert len(missing) == 0

    def test_skips_dependency_files(self):
        files = [
            {"path": "package.json"},
        ]
        missing = find_test_pairs(files)
        assert len(missing) == 0

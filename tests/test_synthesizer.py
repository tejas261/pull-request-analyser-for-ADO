"""Tests for the synthesizer module."""

import pytest
from agents.types import ReviewResult, ReviewComment
from agents.reviewers.synthesizer import synthesize, compute_max_comments


class TestComputeMaxComments:
    def test_minimum_is_5(self):
        assert compute_max_comments(0) == 5
        assert compute_max_comments(10) == 5

    def test_scales_with_lines(self):
        # default factor is 2.0, so 1000 lines -> 20 comments
        result = compute_max_comments(1000)
        assert result == 20

    def test_small_pr(self):
        assert compute_max_comments(100) == 5


class TestSynthesize:
    def _make_comment(self, severity="minor", confidence=0.8, path="a.py",
                      line=1, category="best-practice", comment="test"):
        return ReviewComment(
            file_path=path,
            line_number=line,
            severity=severity,
            category=category,
            comment=comment,
            confidence=confidence,
        )

    def test_empty_results(self):
        comments, md = synthesize([], 100)
        assert comments == []
        assert "Summary" in md

    def test_filters_low_confidence(self):
        result = ReviewResult(
            agent_name="test",
            comments=[self._make_comment(confidence=0.1)],
            summary="test",
        )
        comments, _ = synthesize([result], 100)
        assert len(comments) == 0

    def test_keeps_high_confidence(self):
        result = ReviewResult(
            agent_name="test",
            comments=[self._make_comment(confidence=0.9)],
            summary="test",
        )
        comments, _ = synthesize([result], 100)
        assert len(comments) == 1

    def test_deduplicates(self):
        c = self._make_comment()
        result = ReviewResult(agent_name="a", comments=[c, c], summary="")
        comments, _ = synthesize([result], 100)
        assert len(comments) == 1

    def test_critical_always_kept(self):
        critical = [
            self._make_comment(severity="critical", line=i)
            for i in range(20)
        ]
        result = ReviewResult(agent_name="sec", comments=critical, summary="")
        comments, _ = synthesize([result], 10)  # tiny PR, low budget
        # All critical should be kept regardless of budget
        assert len(comments) == 20

    def test_sorts_by_severity_then_confidence(self):
        comments_in = [
            self._make_comment(severity="nit", confidence=0.9, line=1),
            self._make_comment(severity="critical", confidence=0.7, line=2),
            self._make_comment(severity="major", confidence=0.8, line=3),
        ]
        result = ReviewResult(agent_name="test", comments=comments_in, summary="")
        comments, _ = synthesize([result], 1000)
        assert comments[0].severity == "critical"
        assert comments[1].severity == "major"
        assert comments[2].severity == "nit"

    def test_markdown_summary_contains_sections(self):
        c = self._make_comment(severity="major", comment="issue found")
        result = ReviewResult(agent_name="test", comments=[c], summary="agent summary")
        _, md = synthesize([result], 100)
        assert "MAJOR" in md
        assert "issue found" in md
        assert "agent summary" in md

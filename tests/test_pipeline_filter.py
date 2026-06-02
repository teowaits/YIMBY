"""Tests for in-scope works eligibility filter."""

from regional_scout.models import AuthorRecord
from regional_scout.pipeline import filter_eligible_candidates


def _author(aid: str) -> AuthorRecord:
    return AuthorRecord(aid, "Name", None, "it", 10, 5)


def test_filter_keeps_authors_meeting_minimum():
    candidates = [_author("A1"), _author("A2"), _author("A3")]
    counts = {"A1": 2, "A2": 0, "A3": 1}
    eligible = filter_eligible_candidates(candidates, counts, min_works=1)
    assert [a.openalex_id for a in eligible] == ["A1", "A3"]


def test_filter_disabled_when_zero():
    candidates = [_author("A1")]
    counts = {"A1": 0}
    eligible = filter_eligible_candidates(candidates, counts, min_works=0)
    assert len(eligible) == 1

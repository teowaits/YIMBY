"""Tests for works OR-fetch merge logic."""

from regional_scout.models import ScopeVector, WorkRecord
from regional_scout.works import merge_work_records


def test_merge_dedupes_and_filters_out_of_scope():
    scope = ScopeVector(
        topic_ids=frozenset({"T100", "T200"}),
        source_ids=frozenset({"S1"}),
    )
    works = [
        WorkRecord("W1", "a", 2024, "T100", None, 1.0, []),
        WorkRecord("W1", "a", 2024, "T100", None, 1.0, []),  # dup
        WorkRecord("W2", "b", 2024, "T999", None, 1.0, []),  # out of scope
        WorkRecord("W3", "c", 2024, None, "S1", 1.0, []),
    ]
    merged = merge_work_records(works, scope)
    ids = {w.openalex_id for w in merged}
    assert ids == {"W1", "W3"}


def test_merge_empty_scope_topics_still_keeps_sources():
    scope = ScopeVector(topic_ids=frozenset(), source_ids=frozenset({"S1"}))
    works = [WorkRecord("W1", "a", 2024, "T1", "S1", 1.0, [])]
    assert len(merge_work_records(works, scope)) == 1

"""Tests for in-scope works in JSON output."""

from pathlib import Path

from regional_scout.models import (
    AuthorRecord,
    RunMetadata,
    ScoreBreakdown,
    ScoredAuthor,
    WorkRecord,
)
from regional_scout.output.json_writer import write_shortlist


def _scored() -> ScoredAuthor:
    return ScoredAuthor(
        author=AuthorRecord("A1", "Alice", "Uni", "it", 100, 10),
        breakdown=ScoreBreakdown(0.5, 0.5, 0.5, 0.5, 0.0, 0.5, 0.5, 0.5, 0.5, 0.5),
        wiley_friendly=False,
        wiley_journal=None,
        in_scope_work_count=2,
        mean_fwci=1.2,
    )


def test_json_includes_work_summaries(tmp_path: Path):
    works = [
        WorkRecord("W1", "Older", 2023, "T1", None, 1.0, []),
        WorkRecord("W2", "Newer", 2025, "T1", "S1", 2.0, []),
    ]
    meta = RunMetadata(
        region_label="it",
        topic_count=1,
        candidate_count=1,
        eligible_count=1,
        excluded_in_scope_count=0,
        credits_estimated=0,
        credits_used=0,
        cache_hits=0,
        api_calls=0,
        publication_year_from=2022,
        publication_year_to=2026,
        output_dir=str(tmp_path),
        scope_summary={},
    )
    path = tmp_path / "shortlist.json"
    write_shortlist(
        [_scored()],
        path,
        meta=meta,
        version="test",
        works_map={"A1": works},
        include_works=True,
        max_works_per_author=5,
    )
    import json

    doc = json.loads(path.read_text())
    row = doc["shortlist"][0]
    assert len(row["in_scope_works"]) == 2
    assert row["in_scope_works"][0]["title"] == "Newer"

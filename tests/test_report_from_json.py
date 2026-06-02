"""Tests for JSON-driven HTML report."""

import json
from pathlib import Path

from regional_scout.output.html_writer import write_report_from_json


def test_report_from_enriched_json(tmp_path: Path):
    doc = {
        "generated_at": "2026-05-28T20:00:00+00:00",
        "region": "it",
        "publication_year_window": {"from": 2022, "to": 2026},
        "candidates_evaluated": 10,
        "candidates_eligible": 8,
        "candidates_excluded_in_scope": 2,
        "scope": {"topic_count": 90},
        "credits": {"used": 0, "api_calls": 0, "cache_hits": 5},
        "published_with_us": {
            "target_journal_name": "Advanced Intelligent Systems",
            "target_source_id": "S4210212817",
            "year_from": 2022,
            "year_to": 2026,
            "credits_used": 200,
        },
        "shortlist": [
            {
                "rank": 1,
                "openalex_id": "A1",
                "display_name": "Alice",
                "institution_name": "Uni",
                "composite_score": 0.5,
                "score_breakdown": {
                    "relevance": 1.0,
                    "productivity": 0.5,
                    "impact": 0.5,
                    "centrality": 0.0,
                    "wiley": 0.0,
                },
                "wiley_friendly": False,
                "in_scope_work_count": 2,
                "mean_fwci": 1.5,
                "in_scope_works": [
                    {"title": "Paper A", "publication_year": 2025, "fwci": 2.0}
                ],
                "published_with_us": {
                    "published": False,
                    "latest_work": {
                        "title": "Latest paper",
                        "source_display_name": "Nature",
                        "publication_year": 2026,
                    },
                },
            }
        ],
    }
    json_path = tmp_path / "shortlist.json"
    json_path.write_text(json.dumps(doc))
    html_path = write_report_from_json(json_path)
    html = html_path.read_text()
    assert "Advanced Intelligent Systems" in html
    assert "Latest paper" in html
    assert "Paper A" in html

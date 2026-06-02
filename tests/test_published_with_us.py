"""Tests for published-with-us I/O and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from regional_scout.published_with_us.io import (
    extract_author_id_from_row,
    find_openalex_id_column,
    load_shortlist,
    write_shortlist_enriched,
)
from regional_scout.published_with_us.enrich import estimate_enrich_credits, _year_range


def test_extract_openalex_id_from_shortlist_row():
    row = {"openalex_id": "A5023556434", "display_name": "Test"}
    assert extract_author_id_from_row(row) == "A5023556434"


def test_reject_work_id_in_csv_row():
    row = {"OpenAlex ID": "W1234567890"}
    with pytest.raises(ValueError, match="Work ID"):
        extract_author_id_from_row(row)


def test_load_shortlist(tmp_path: Path):
    p = tmp_path / "shortlist.json"
    p.write_text(
        json.dumps({"shortlist": [{"openalex_id": "A1", "display_name": "X"}]}),
        encoding="utf-8",
    )
    doc, rows = load_shortlist(p)
    assert "shortlist" in doc
    assert len(rows) == 1


def test_find_openalex_column():
    assert find_openalex_id_column(["Name", "OpenAlex ID"]) == "OpenAlex ID"


def test_credit_estimate():
    assert estimate_enrich_credits(10, latest_for_prospects=False) == 100
    assert estimate_enrich_credits(10, latest_for_prospects=True) == 200


def test_year_range_all_time():
    y0, y1 = _year_range(0)
    assert y0 is None


def test_write_shortlist_merges_enrich_credits(tmp_path: Path):
    p = tmp_path / "shortlist.json"
    doc = {
        "credits": {"used": 4000, "api_calls": 400, "cache_hits": 50},
        "shortlist": [{"openalex_id": "A1"}],
    }
    p.write_text(json.dumps(doc), encoding="utf-8")
    write_shortlist_enriched(
        doc,
        doc["shortlist"],
        p,
        target_source_id="S1",
        target_journal_name="Test Journal",
        year_window=(2022, 2026),
        credits_used=200,
    )
    out = json.loads(p.read_text())
    assert out["credits"]["pipeline_used"] == 4000
    assert out["credits"]["enrich_used"] == 200
    assert out["credits"]["used"] == 4200

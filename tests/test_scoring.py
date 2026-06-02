"""Unit tests for scoring.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from regional_scout.config import Config, OpenAlexConfig, OutputConfig, RegionConfig, ScoringConfig, ScopeConfig, WileyPortfolioConfig
from regional_scout.models import AuthorRecord, RawScoreComponents, ScopeVector, WorkRecord
from regional_scout.scoring import compute_raw_components, normalize_and_composite

FIXTURES = Path(__file__).parent / "fixtures"


def _minimal_config(**kwargs) -> Config:
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345", work_window_years=5),
        region=RegionConfig(country_codes=["it"]),
        scoring=ScoringConfig(**kwargs.get("scoring", {})),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(),
    )


def _load_works() -> list[WorkRecord]:
    data = json.loads((FIXTURES / "sample_works.json").read_text())
    return [WorkRecord(**w) for w in data]


def test_single_author_pool_normalized_to_one():
    config = _minimal_config()
    author = AuthorRecord(
        openalex_id="A1",
        display_name="Alice",
        institution_name="Uni",
        country_code="it",
        cited_by_count=100,
        works_count=10,
    )
    scope = ScopeVector(topic_ids=frozenset({"T100"}), source_ids=frozenset())
    raw = compute_raw_components(author, _load_works(), 0.8, scope, config)
    scored = normalize_and_composite(
        [raw],
        {"A1": author},
        {"A1": 2},
        {"A1": 1.75},
        {"A1": False},
        {"A1": None},
        config,
    )
    assert len(scored) == 1
    b = scored[0].breakdown
    assert b.relevance == pytest.approx(1.0)
    assert b.productivity == pytest.approx(1.0)
    assert b.impact == pytest.approx(1.0)
    assert b.centrality == pytest.approx(1.0)


def test_null_fwci_excluded_from_impact():
    config = _minimal_config()
    author = AuthorRecord(
        openalex_id="A2",
        display_name="Bob",
        institution_name=None,
        country_code="it",
        cited_by_count=50,
        works_count=5,
    )
    works = [
        WorkRecord(
            openalex_id="W1",
            title="x",
            publication_year=2024,
            primary_topic_id="T100",
            primary_source_id=None,
            fwci=None,
            coauthor_ids=["A2"],
        ),
    ]
    scope = ScopeVector(topic_ids=frozenset({"T100"}), source_ids=frozenset())
    raw = compute_raw_components(author, works, 0.5, scope, config)
    assert raw.impact == 0.0


def test_all_null_fwci_impact_zero():
    config = _minimal_config()
    author = AuthorRecord(
        openalex_id="A2",
        display_name="Bob",
        institution_name=None,
        country_code="it",
        cited_by_count=50,
        works_count=5,
    )
    scope = ScopeVector(topic_ids=frozenset({"T200"}), source_ids=frozenset())
    raw = compute_raw_components(author, _load_works()[2:], 0.5, scope, config)
    assert raw.impact == 0.0


def test_ties_min_max():
    config = _minimal_config()
    scope = ScopeVector(topic_ids=frozenset({"T100"}), source_ids=frozenset())
    authors = {
        "A1": AuthorRecord("A1", "A", None, "it", 1, 1),
        "A2": AuthorRecord("A2", "B", None, "it", 1, 1),
    }
    raws = [
        RawScoreComponents("A1", 0.5, 1.0, 1.0, 0.5, 0.0),
        RawScoreComponents("A2", 0.5, 1.0, 1.0, 0.5, 0.0),
    ]
    scored = normalize_and_composite(
        raws, authors, {"A1": 1, "A2": 1}, {"A1": 1.0, "A2": 1.0},
        {"A1": False, "A2": False}, {"A1": None, "A2": None}, config,
    )
    for s in scored:
        assert s.breakdown.relevance == pytest.approx(1.0)

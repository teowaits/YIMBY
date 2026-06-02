"""Tests for scoped candidate merge."""

from regional_scout.candidates import (
    AUTHOR_TOPIC_BATCH,
    merge_authors_by_citations,
    _region_citation_filter,
)
from regional_scout.config import (
    Config,
    OpenAlexConfig,
    OutputConfig,
    RegionConfig,
    ScoringConfig,
    ScopeConfig,
    WileyPortfolioConfig,
)
from regional_scout.models import AuthorRecord


def _config() -> Config:
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(country_codes=["it"]),
        scoring=ScoringConfig(),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(),
    )


def test_merge_authors_keeps_highest_citation_and_sorts():
    authors = [
        AuthorRecord("A1", "Low", None, "it", 10, 5),
        AuthorRecord("A2", "High", None, "it", 100, 5),
        AuthorRecord("A1", "Low dup", None, "it", 50, 5),
    ]
    merged = merge_authors_by_citations(authors)
    assert [a.openalex_id for a in merged] == ["A2", "A1"]
    assert merged[1].cited_by_count == 50


def test_region_filter_excludes_publication_year():
    filt = _region_citation_filter(_config())
    assert "publication_year" not in filt
    assert "country_code:it" in filt


def test_author_topic_batch_smaller_than_works_batch():
    assert AUTHOR_TOPIC_BATCH <= 50

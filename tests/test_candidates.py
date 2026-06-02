"""Candidate fetch affiliation verification."""

from __future__ import annotations

from regional_scout.candidates import _is_primarily_local, _verify_institution_affiliation
from regional_scout.config import (
    CityRegion,
    Config,
    OpenAlexConfig,
    OutputConfig,
    RegionConfig,
    ScoringConfig,
    ScopeConfig,
    WileyPortfolioConfig,
)

UCM_ID = "I126973510"
HARBIN_ID = "I201646483"


def _config(**city_kw) -> Config:
    city = CityRegion(name="Madrid", country_code="ES", **city_kw)
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(country_codes=[], city=city),
        scoring=ScoringConfig(),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(),
    )


def _author(
    *,
    affiliations: list | None = None,
    last_known: list | None = None,
) -> dict:
    return {
        "id": "https://openalex.org/A123",
        "affiliations": affiliations if affiliations is not None else [],
        "last_known_institutions": last_known or [],
    }


def test_is_primarily_local_true():
    raw = _author(
        affiliations=[
            {
                "institution": {"id": f"https://openalex.org/{UCM_ID}"},
                "years": [2022, 2024],
            }
        ]
    )
    assert _is_primarily_local(raw, {UCM_ID}, recency_years=3, current_year=2026)


def test_is_primarily_local_false_old_affiliation():
    raw = _author(
        affiliations=[
            {
                "institution": {"id": f"https://openalex.org/{UCM_ID}"},
                "years": [2016, 2018],
            }
        ]
    )
    assert not _is_primarily_local(raw, {UCM_ID}, recency_years=3, current_year=2026)


def test_is_primarily_local_false_coauthor_only():
    raw = _author(
        affiliations=[
            {
                "institution": {"id": f"https://openalex.org/{HARBIN_ID}"},
                "years": [2023, 2025],
            }
        ],
        last_known=[
            {"id": f"https://openalex.org/{UCM_ID}", "display_name": "UCM"},
            {"id": f"https://openalex.org/{HARBIN_ID}", "display_name": "Harbin"},
        ],
    )
    assert not _is_primarily_local(raw, {UCM_ID}, recency_years=3, current_year=2026)


def test_is_primarily_local_fallback():
    raw = _author(
        affiliations=[],
        last_known=[{"id": f"https://openalex.org/{UCM_ID}", "display_name": "UCM"}],
    )
    assert _is_primarily_local(raw, {UCM_ID}, recency_years=3, current_year=2026)


def test_post_fetch_filter_drops_coauthors():
    ucm_author = _author(
        affiliations=[
            {
                "institution": {"id": f"https://openalex.org/{UCM_ID}"},
                "years": [2024],
            }
        ]
    )
    harbin_author = _author(
        affiliations=[
            {
                "institution": {"id": f"https://openalex.org/{HARBIN_ID}"},
                "years": [2024],
            }
        ],
        last_known=[{"id": f"https://openalex.org/{UCM_ID}", "display_name": "UCM"}],
    )
    cfg = _config(institution_ids=[UCM_ID])
    kept = _verify_institution_affiliation([ucm_author, harbin_author], cfg)
    assert kept == [ucm_author]

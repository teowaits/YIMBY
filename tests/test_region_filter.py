"""Region filter priority and geo filter formatting."""

from __future__ import annotations

import logging

import pytest

from regional_scout.candidates import (
    _author_geo_fragment,
    _id_batches,
    _region_citation_filter,
    _works_geo_fragment,
)
from regional_scout.config import (
    CityRegion,
    Config,
    OpenAlexConfig,
    OutputConfig,
    RegionConfig,
    ScoringConfig,
    ScopeConfig,
    WileyPortfolioConfig,
    active_filter,
)
from regional_scout.server.runner import merge_run_overrides


def _config(**region_kw) -> Config:
    city_kw = region_kw.pop("city", {})
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(
            country_codes=region_kw.pop("country_codes", ["it"]),
            ror_ids=region_kw.pop("ror_ids", []),
            city=CityRegion(**city_kw) if city_kw else CityRegion(),
            **region_kw,
        ),
        scoring=ScoringConfig(),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(),
    )


def test_active_filter_priority_ror_beats_city_and_country():
    region = RegionConfig(
        ror_ids=["https://ror.org/02rxjx940"],
        country_codes=["it"],
        city=CityRegion(name="Madrid", institution_ids=["I123"]),
    )
    assert active_filter(region) == ("ror", ["https://ror.org/02rxjx940"])


def test_active_filter_city_beats_country():
    region = RegionConfig(
        country_codes=["it"],
        city=CityRegion(name="Madrid", institution_ids=["I123", "I456"]),
    )
    assert active_filter(region) == ("institution", ["I123", "I456"])


def test_active_filter_country_fallback():
    region = RegionConfig(country_codes=["de"])
    assert active_filter(region) == ("country", ["de"])


def test_city_name_without_institution_ids_falls_through_to_country():
    region = RegionConfig(
        country_codes=["es"],
        city=CityRegion(name="Madrid", country_code="es", institution_ids=[]),
    )
    assert active_filter(region) == ("country", ["es"])


def test_institution_filter_format():
    frag = _author_geo_fragment("institution", ["I123", "I456"])
    assert frag == "last_known_institutions.id:I123|I456"
    works = _works_geo_fragment("institution", ["I123", "I456"])
    assert works == "authorships.institutions.id:I123|I456"


def test_author_and_works_fragments_same_branch():
    cfg = _config(city={"institution_ids": ["I111", "I222"]}, country_codes=["it"])
    ftype, ids = active_filter(cfg.region)
    assert _author_geo_fragment(ftype, ids).startswith("last_known_institutions.id:")
    assert _works_geo_fragment(ftype, ids).startswith("authorships.institutions.id:")


def test_country_filter_info_logged(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="regional_scout.candidates")
    _region_citation_filter(_config(country_codes=["it"]))
    assert any("country_code" in r.message for r in caplog.records)


def test_id_batches_splits_over_50():
    ids = [f"I{i}" for i in range(55)]
    batches = _id_batches(ids)
    assert len(batches) == 2
    assert len(batches[0]) == 50
    assert len(batches[1]) == 5


def test_merge_overrides_clears_country_when_institution_ids_set():
    base = _config(country_codes=["it"])
    merged = merge_run_overrides(
        base,
        {
            "institution_ids": ["I123"],
            "city_name": "Madrid",
            "city_country_code": "es",
        },
    )
    assert merged.region.city.institution_ids == ["I123"]
    assert merged.region.country_codes == []

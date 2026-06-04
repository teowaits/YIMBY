"""City institution resolution — haversine and coordinate filtering."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from regional_scout.city import (
    _effective_works_threshold,
    _institutions_within_radius,
    haversine_km,
    resolve_city_institutions,
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
)

MILAN_LAT, MILAN_LON = 45.4642, 9.1900
ROME_LAT, ROME_LON = 41.9028, 12.4964
UNIMI_LAT, UNIMI_LON = 45.4654, 9.1866
STANFORD_LAT, STANFORD_LON = 37.4275, -122.1697
PALO_ALTO_LAT, PALO_ALTO_LON = 37.4419, -122.1430


def _config(**city_kw) -> Config:
    city = CityRegion(name="Milan", country_code="it", **city_kw)
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(country_codes=["it"], city=city),
        scoring=ScoringConfig(),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(),
    )


def test_haversine_known_distance():
    dist = haversine_km(MILAN_LAT, MILAN_LON, ROME_LAT, ROME_LON)
    assert 475 <= dist <= 479


def test_geocode_returns_canonical_name():
    cfg = _config()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "lat": "45.4642",
            "lon": "9.1900",
            "display_name": "Milan, Lombardy, Italy",
        }
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("regional_scout.city.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_response
        from regional_scout.city import _geocode_city

        result = _geocode_city("Milano", "IT", cfg)

    assert result["lat"] == pytest.approx(45.4642)
    assert result["lon"] == pytest.approx(9.1900)
    assert "Milan" in result["canonical_name"]


def test_coordinate_filter_finds_university_of_milan():
    institutions = [
        {
            "id": "I861853513",
            "display_name": "Università degli Studi di Milano",
            "works_count": 72341,
            "type": "education",
            "geo": {"latitude": UNIMI_LAT, "longitude": UNIMI_LON, "city": "Milan"},
        }
    ]
    nearby = _institutions_within_radius(
        institutions,
        city_lat=MILAN_LAT,
        city_lon=MILAN_LON,
        radius_km=30,
    )
    assert len(nearby) == 1
    assert nearby[0]["display_name"] == "Università degli Studi di Milano"
    assert nearby[0]["distance_km"] < 5


def test_coordinate_filter_finds_stanford_from_palo_alto():
    institutions = [
        {
            "id": "I97018004",
            "display_name": "Stanford University",
            "works_count": 284621,
            "type": "education",
            "geo": {"latitude": STANFORD_LAT, "longitude": STANFORD_LON, "city": "Stanford"},
        }
    ]
    nearby = _institutions_within_radius(
        institutions,
        city_lat=PALO_ALTO_LAT,
        city_lon=PALO_ALTO_LON,
        radius_km=30,
    )
    assert len(nearby) == 1
    assert nearby[0]["display_name"] == "Stanford University"


def test_stanford_missed_by_name_search_but_found_by_coords():
    name = "Stanford University"
    assert "palo alto" not in name.lower()

    institutions = [
        {
            "id": "I97018004",
            "display_name": name,
            "works_count": 284621,
            "type": "education",
            "geo": {"latitude": STANFORD_LAT, "longitude": STANFORD_LON},
        }
    ]
    nearby = _institutions_within_radius(
        institutions,
        city_lat=PALO_ALTO_LAT,
        city_lon=PALO_ALTO_LON,
        radius_km=30,
    )
    assert nearby


def test_large_country_threshold():
    cfg = _config(works_count_min=50)
    assert _effective_works_threshold("us", cfg) == 500
    assert _effective_works_threshold("it", cfg) == 500
    assert _effective_works_threshold("lu", cfg) == 50

    cfg_high = _config(works_count_min=1000)
    assert _effective_works_threshold("us", cfg_high) == 1000


def test_resolve_city_institutions_wires_geocode_and_filter():
    cfg = _config(radius_km=30)
    client = MagicMock()
    client.fetch_list.return_value = [
        {
            "id": "https://openalex.org/I861853513",
            "display_name": "Università degli Studi di Milano",
            "works_count": 72341,
            "type": "education",
            "geo": {"latitude": UNIMI_LAT, "longitude": UNIMI_LON, "city": "Milan"},
        }
    ]
    geocode = {"lat": MILAN_LAT, "lon": MILAN_LON, "canonical_name": "Milan, Italy"}

    with patch("regional_scout.city._geocode_city", return_value=geocode):
        institutions, geo = resolve_city_institutions(client, "Milano", "IT", cfg)

    assert geo == geocode
    assert len(institutions) == 1
    assert institutions[0]["id"] == "I861853513"
    assert institutions[0]["distance_km"] <= 30

"""init-city: resolve city institutions via geocoding + coordinate filter."""

from __future__ import annotations

import logging
import math
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from ruamel.yaml import YAML

from regional_scout.cache import Cache
from regional_scout.config import Config, load_config, normalize_institution_id
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex import openalex_id as norm_id

logger = logging.getLogger(__name__)

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "regional-scout/1.0 mcavalleri@wiley.com"

LARGE_COUNTRIES = frozenset(
    {"us", "cn", "gb", "de", "in", "jp", "fr", "br", "ru", "kr", "au", "ca", "es", "it"}
)

SUPPLEMENT_NOTE = (
    "Review and supplement if needed — coordinate resolution may miss institutions "
    "without geo coordinates in OpenAlex, or those just outside the {radius_km} km "
    "radius. Add them manually to region.city.institution_ids."
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _effective_works_threshold(country_code: str, config: Config) -> int:
    threshold = config.region.city.works_count_min
    cc = country_code.strip().lower()
    if cc in LARGE_COUNTRIES and threshold < 500:
        logger.info(
            "Large country — applying works_count:>500 pre-filter for speed."
        )
        return 500
    return threshold


def _nominatim_cache_url(city: str, country_code: str) -> str:
    return f"nominatim://{city.strip().lower()}:{country_code.strip().lower()}"


def _geocode_city(city: str, country_code: str, config: Config) -> dict[str, Any]:
    """Geocode city via Nominatim; result cached in SQLite."""
    cc = country_code.strip().upper()
    city_q = city.strip()
    query = f"{city_q},{cc}"
    params = {
        "q": query,
        "format": "json",
        "limit": "1",
        "addressdetails": "1",
    }
    request_url = f"{NOMINATIM_BASE}?{urlencode(params)}"
    cache = Cache(config.openalex.cache_path)
    cache_key = _nominatim_cache_url(city_q, cc)

    try:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                request_url,
                headers={"User-Agent": NOMINATIM_USER_AGENT},
            )
            resp.raise_for_status()
            rows = resp.json()

        if not rows:
            raise ValueError(
                f"No geocoding result for {city_q!r} in {cc}. "
                "Check spelling or add a country code."
            )

        row = rows[0]
        result = {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "canonical_name": row.get("display_name") or query,
        }
        cache.set(cache_key, result)
        return result
    finally:
        cache.close()


def _institution_works_count(raw: dict[str, Any]) -> int:
    if raw.get("works_count") is not None:
        return int(raw["works_count"])
    stats = raw.get("summary_stats") or {}
    return int(stats.get("works_count") or 0)


def _fetch_country_institutions(
    client: OpenAlexClient,
    country_code: str,
    config: Config,
) -> list[dict[str, Any]]:
    cc = country_code.strip().lower()
    threshold = _effective_works_threshold(cc, config)
    filt = (
        f"country_code:{cc},works_count:>{threshold - 1},"
        f"type:education|facility"
    )
    raw = client.fetch_list(
        "/institutions",
        {
            "filter": filt,
            "select": "id,display_name,works_count,type,geo,summary_stats",
            "sort": "works_count:desc",
            "per-page": "200",
        },
        max_pages=None,
    )
    return raw


def _institutions_within_radius(
    institutions: list[dict[str, Any]],
    *,
    city_lat: float,
    city_lon: float,
    radius_km: float,
) -> list[dict[str, Any]]:
    nearby: list[dict[str, Any]] = []
    for inst in institutions:
        geo = inst.get("geo") or {}
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            continue
        dist = haversine_km(city_lat, city_lon, float(lat), float(lon))
        if dist <= radius_km:
            nearby.append(
                {
                    "id": normalize_institution_id(norm_id(inst["id"])),
                    "display_name": inst.get("display_name") or "",
                    "name": inst.get("display_name") or "",
                    "works_count": _institution_works_count(inst),
                    "type": inst.get("type") or "",
                    "distance_km": round(dist, 1),
                    "geo_city": geo.get("city") or "",
                }
            )
    nearby.sort(key=lambda x: x["works_count"], reverse=True)
    return nearby


def resolve_city_institutions(
    client: OpenAlexClient,
    city: str,
    country_code: str,
    config: Config,
    *,
    radius_km: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (institutions, geocode_result).

    institutions: {id, display_name, name, works_count, type, distance_km, geo_city}
    geocode_result: {lat, lon, canonical_name}
    """
    geocode = _geocode_city(city, country_code, config)
    institutions = _fetch_country_institutions(client, country_code, config)
    effective_radius = (
        radius_km if radius_km is not None else config.region.city.radius_km
    )
    nearby = _institutions_within_radius(
        institutions,
        city_lat=geocode["lat"],
        city_lon=geocode["lon"],
        radius_km=effective_radius,
    )
    return nearby, geocode


def _print_table(rows: list[dict], *, radius_km: float) -> None:
    print(
        f"{'#':<4}{'OpenAlex ID':<16}{'Type':<14}{'Dist km':<10}{'Works':<8}Name"
    )
    for i, row in enumerate(rows, start=1):
        print(
            f"{i:<4}{row['id']:<16}{row['type']:<14}"
            f"{row['distance_km']:<10}{row['works_count']:<8}{row['display_name']}"
        )
    print(f"\nRadius: {radius_km} km", file=sys.stderr)


def init_city(
    config_path: Path,
    *,
    city: str,
    country: str,
    write: bool = False,
    radius: float | None = None,
) -> list[dict]:
    config = load_config(config_path)
    client = OpenAlexClient(config)
    effective_radius = (
        radius if radius is not None else config.region.city.radius_km
    )
    try:
        rows, geocode = resolve_city_institutions(
            client, city, country, config, radius_km=radius
        )
        print(
            f"Resolved {city!r} → {geocode['canonical_name']} "
            f"({geocode['lat']:.4f}, {geocode['lon']:.4f})",
            file=sys.stderr,
        )
        if not rows:
            print(
                f"No institutions within {effective_radius} km of "
                f"{city!r} in {country.upper()}",
                file=sys.stderr,
            )
        else:
            _print_table(rows, radius_km=effective_radius)

        inst_ids = [r["id"] for r in rows]

        if write and inst_ids:
            yaml = YAML()
            yaml.preserve_quotes = True
            with config_path.open() as f:
                data = yaml.load(f)

            region = data.setdefault("region", {})
            city_block = region.setdefault("city", {})
            city_block["name"] = city
            city_block["country_code"] = country.lower()
            city_block["institution_ids"] = inst_ids
            if radius is None:
                city_block["radius_km"] = config.region.city.radius_km

            with config_path.open("w") as f:
                yaml.dump(data, f)
            print(
                f"Written {len(inst_ids)} institution IDs to {config_path}.",
                file=sys.stderr,
            )

        print(
            SUPPLEMENT_NOTE.format(radius_km=effective_radius),
            file=sys.stderr,
        )
        return rows
    finally:
        client.close()

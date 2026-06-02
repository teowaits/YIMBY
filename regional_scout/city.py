"""init-city: resolve city institutions via OpenAlex."""

from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML

from regional_scout.config import load_config, normalize_institution_id
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex import openalex_id as norm_id

SUPPLEMENT_NOTE = (
    "Review and supplement if needed — some institutions may not include "
    "'{city}' in their name (e.g. CSIC branches, hospitals). Add them manually "
    "to region.city.institution_ids."
)


def resolve_city_institutions(
    client: OpenAlexClient,
    city: str,
    country_code: str,
) -> list[dict]:
    """Query /institutions; return rows sorted by works_count descending."""
    cc = country_code.strip().lower()
    city_q = city.strip()
    raw = client.fetch_list(
        "/institutions",
        {
            "filter": f"country_code:{cc},display_name.search:{city_q}",
            "select": "id,display_name,works_count,type",
            "per-page": "50",
        },
        max_pages=1,
    )
    rows = sorted(
        raw,
        key=lambda r: int(r.get("works_count") or 0),
        reverse=True,
    )
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id": normalize_institution_id(norm_id(r["id"])),
                "display_name": r.get("display_name") or "",
                "works_count": int(r.get("works_count") or 0),
                "type": r.get("type") or "",
            }
        )
    return out


def _print_table(rows: list[dict]) -> None:
    print(f"{'#':<4}{'OpenAlex ID':<16}{'Type':<14}{'Works':<8}Name")
    for i, row in enumerate(rows, start=1):
        print(
            f"{i:<4}{row['id']:<16}{row['type']:<14}"
            f"{row['works_count']:<8}{row['display_name']}"
        )


def init_city(
    config_path: Path,
    *,
    city: str,
    country: str,
    write: bool = False,
) -> list[dict]:
    config = load_config(config_path)
    client = OpenAlexClient(config)
    try:
        rows = resolve_city_institutions(client, city, country)
        if not rows:
            print(f"No institutions found for {city!r} in {country.upper()}", file=sys.stderr)
        else:
            _print_table(rows)

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

            with config_path.open("w") as f:
                yaml.dump(data, f)
            print(
                f"Written {len(inst_ids)} institution IDs to {config_path}.",
                file=sys.stderr,
            )

        print(SUPPLEMENT_NOTE.format(city=city), file=sys.stderr)
        return rows
    finally:
        client.close()

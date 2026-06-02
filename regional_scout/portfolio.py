"""init-portfolio: resolve ISSNs to OpenAlex source IDs."""

from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML

from regional_scout.config import PORTFOLIO_ISSNS, load_config
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex import openalex_id as norm_id


def _resolve_issn(client: OpenAlexClient, issn: str) -> str | None:
    rows = client.fetch_list(
        "/sources",
        {"filter": f"issn:{issn}", "select": "id,display_name", "per-page": "5"},
        max_pages=1,
    )
    if not rows:
        return None
    return norm_id(rows[0]["id"])


def init_portfolio(config_path: Path, *, write: bool = False) -> None:
    config = load_config(config_path)
    client = OpenAlexClient(config)
    try:
        updates: dict[str, str | None] = {}
        for key, issn in PORTFOLIO_ISSNS.items():
            current = getattr(config.wiley_portfolio, key)
            if current:
                continue
            sid = _resolve_issn(client, issn)
            updates[key] = sid
            if sid:
                print(f"{key}: {sid} (ISSN {issn})", file=sys.stderr)
            else:
                print(f"{key}: not found (ISSN {issn})", file=sys.stderr)

        yaml = YAML()
        yaml.preserve_quotes = True
        with config_path.open() as f:
            data = yaml.load(f)

        wp = data.setdefault("wiley_portfolio", {})
        for key, sid in updates.items():
            if sid:
                wp[key] = sid

        if write:
            with config_path.open("w") as f:
                yaml.dump(data, f)
            print(f"Updated {config_path}", file=sys.stderr)
        else:
            yaml.dump(data, sys.stdout)
    finally:
        client.close()

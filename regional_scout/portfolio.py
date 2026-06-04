"""init-portfolio: resolve ISSNs to OpenAlex source IDs."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from regional_scout.config import load_config
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex import openalex_id as norm_id

PORTFOLIO_JOURNALS: list[dict[str, Any]] = [
    {"key": "advanced_science", "issn": "2198-3844", "display": "Advanced Science"},
    {
        "key": "advanced_intelligent_systems",
        "issn": "2640-4567",
        "display": "Advanced Intelligent Systems",
    },
    {
        "key": "advanced_intelligent_discovery",
        "issn": "2943-9981",
        "display": "Advanced Intelligent Discovery",
    },
    {
        "key": "advanced_robotics_research",
        "issn": "2943-9973",
        "display": "Advanced Robotics Research",
    },
    {
        "key": "advanced_theory_simulations",
        "issn": "2513-0390",
        "display": "Advanced Theory and Simulations",
    },
    {"key": "advanced_computing", "issn": "3054-100X", "display": "Advanced Computing"},
    {"key": "applied_ai_letters", "issn": "2689-5595", "display": "Applied AI Letters"},
    {
        "key": "ijis",
        "issn": ["1098-111X", "0884-8173"],
        "display": "International Journal of Intelligent Systems",
    },
]

IJIS_DISPLAY_SHORT = "Int. Journal of Intelligent Systems"
ATS_DISPLAY_SHORT = "Advanced Theory and Sims"


@dataclass
class ResolvedJournal:
    key: str
    display: str
    source_id: str | None
    issn_label: str
    already_set: bool = False
    discontinued_warning: bool = False
    works_count: int | None = None
    last_work_year: int | None = None


def _issn_list(entry: dict[str, Any]) -> list[str]:
    issn = entry["issn"]
    if isinstance(issn, list):
        return issn
    return [issn]


def _issn_label(entry: dict[str, Any]) -> str:
    return " / ".join(_issn_list(entry))


def _lookup_source_by_issn(client: OpenAlexClient, issn: str) -> dict[str, Any] | None:
    rows = client.fetch_list(
        "/sources",
        {"filter": f"issn:{issn}", "select": "id,display_name,issn_l,works_count", "per-page": "5"},
        max_pages=1,
    )
    return rows[0] if rows else None


def _latest_work_year(client: OpenAlexClient, source_id: str) -> int | None:
    rows = client.fetch_list(
        "/works",
        {
            "filter": f"primary_location.source.id:{source_id}",
            "sort": "publication_year:desc",
            "select": "publication_year",
            "per-page": "1",
        },
        max_pages=1,
    )
    if not rows:
        return None
    year = rows[0].get("publication_year")
    return int(year) if year is not None else None


def _resolve_journal(
    client: OpenAlexClient,
    entry: dict[str, Any],
) -> tuple[str | None, bool, int | None, int | None]:
    """Returns (source_id, discontinued_warning, works_count, last_work_year)."""
    for issn in _issn_list(entry):
        raw = _lookup_source_by_issn(client, issn)
        if raw is None:
            continue
        sid = norm_id(raw["id"])
        works_count = int(raw.get("works_count") or 0)
        last_year = _latest_work_year(client, sid)
        warning = False
        if entry["key"] == "ijis":
            if works_count < 100 or (last_year is not None and last_year < 2022):
                warning = True
                print(
                    f"⚠ IJIS ({issn}): source found but appears discontinued "
                    f"(last work: {last_year}, total works: {works_count}). "
                    "Including in Wiley AI/Comp signal check but note limited recent coverage.",
                    file=sys.stderr,
                )
        return sid, warning, works_count, last_year
    return None, False, None, None


def _format_row(display: str, result: ResolvedJournal) -> str:
    if display == PORTFOLIO_JOURNALS[-1]["display"]:
        name = IJIS_DISPLAY_SHORT
    elif display == "Advanced Theory and Simulations":
        name = ATS_DISPLAY_SHORT
    else:
        name = display
    name_col = f"{name:<42}"
    if result.source_id:
        status = "(already set)" if result.already_set else "✓"
        if result.discontinued_warning:
            status = "⚠ discontinued?"
        return f"  {name_col} → {result.source_id:<14} {status}"
    if result.key == "advanced_computing":
        return f"  {name_col} → not found in OpenAlex (ISSN {result.issn_label})"
    return f"  {name_col} → not found (ISSN {result.issn_label})"


def init_portfolio(config_path: Path, *, write: bool = False) -> None:
    config = load_config(config_path)
    client = OpenAlexClient(config)
    try:
        results: list[ResolvedJournal] = []
        updates: dict[str, str] = {}

        print("Portfolio source IDs resolved:", file=sys.stderr)

        for entry in PORTFOLIO_JOURNALS:
            key = entry["key"]
            display = entry["display"]
            issn_label = _issn_label(entry)
            current = getattr(config.wiley_portfolio, key)

            if current:
                sid = current
                already_set = True
                warning = False
                works_count = None
                last_year = None
                if key == "ijis":
                    raw = _lookup_source_by_issn(client, _issn_list(entry)[0])
                    if raw is None and len(_issn_list(entry)) > 1:
                        raw = _lookup_source_by_issn(client, _issn_list(entry)[1])
                    if raw:
                        works_count = int(raw.get("works_count") or 0)
                        last_year = _latest_work_year(client, sid)
                        if works_count < 100 or (
                            last_year is not None and last_year < 2022
                        ):
                            warning = True
            else:
                sid, warning, works_count, last_year = _resolve_journal(client, entry)
                already_set = False
                if sid:
                    updates[key] = sid
                elif key == "advanced_computing":
                    print(
                        f"WARNING: Advanced Computing not found in OpenAlex "
                        f"(ISSN {issn_label}) — leaving null.",
                        file=sys.stderr,
                    )

            result = ResolvedJournal(
                key=key,
                display=display,
                source_id=sid,
                issn_label=issn_label,
                already_set=already_set,
                discontinued_warning=warning,
                works_count=works_count,
                last_work_year=last_year,
            )
            results.append(result)
            print(_format_row(display, result), file=sys.stderr)

        resolved_count = sum(1 for r in results if r.source_id)
        print(
            f"\nWiley AI/Comp signal will check {resolved_count} of "
            f"{len(PORTFOLIO_JOURNALS)} portfolio journals.",
            file=sys.stderr,
        )

        yaml = YAML()
        yaml.preserve_quotes = True
        with config_path.open() as f:
            data = yaml.load(f)

        wp = data.setdefault("wiley_portfolio", {})
        for key, sid in updates.items():
            wp[key] = sid

        if write:
            with config_path.open("w") as f:
                yaml.dump(data, f)
            print(f"Updated {config_path}", file=sys.stderr)
        elif updates:
            yaml.dump(data, sys.stdout)
    finally:
        client.close()

"""Load shortlist.json / CSV and write enrichment outputs."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from regional_scout.openalex import openalex_id

OPENALEX_AUTHOR_RE = re.compile(r"^A\d+$", re.IGNORECASE)


def load_shortlist(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open() as f:
        doc = json.load(f)
    rows = doc.get("shortlist")
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected top-level 'shortlist' array")
    return doc, rows


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{path}: CSV has no header row")
        headers = [h.strip() for h in reader.fieldnames]
        rows = [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return headers, rows


def find_openalex_id_column(headers: list[str]) -> str:
    for h in headers:
        norm = h.lower().replace(" ", "")
        if norm in ("openalex_id", "openalexid") or (
            "openalex" in h.lower() and "id" in h.lower()
        ):
            return h
    raise ValueError(
        f'No OpenAlex author ID column found. Headers: {", ".join(headers)}'
    )


def extract_author_id_from_row(row: dict[str, Any]) -> str | None:
    if "openalex_id" in row:
        val = str(row["openalex_id"]).strip()
        if OPENALEX_AUTHOR_RE.match(val):
            return openalex_id(val)
    for key, val in row.items():
        if "openalex" in key.lower() and "id" in key.lower():
            v = str(val).strip()
            if OPENALEX_AUTHOR_RE.match(v):
                return openalex_id(v)
            if re.match(r"^W\d+$", v, re.I):
                raise ValueError(
                    "Work ID (W…) found — use an authors export with author IDs (A…)"
                )
    return None


def write_shortlist_enriched(
    doc: dict[str, Any],
    rows: list[dict[str, Any]],
    path: Path,
    *,
    target_source_id: str,
    target_journal_name: str,
    year_window: tuple[int | None, int],
    credits_used: int,
) -> None:
    y0, y1 = year_window
    doc = dict(doc)
    doc["shortlist"] = rows
    doc["published_with_us"] = {
        "target_source_id": target_source_id,
        "target_journal_name": target_journal_name,
        "year_from": y0,
        "year_to": y1,
        "credits_used": credits_used,
    }
    credits = dict(doc.get("credits") or {})
    pipeline_used = int(credits.get("used") or 0)
    credits["pipeline_used"] = pipeline_used
    credits["enrich_used"] = credits_used
    credits["used"] = pipeline_used + credits_used
    doc["credits"] = credits
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(doc, f, indent=2)


def write_csv_subset(
    headers: list[str],
    rows: list[dict[str, str]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

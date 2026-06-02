"""Enrich shortlist.json or author CSV with published-with-us checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from regional_scout.config import Config
from regional_scout.logging_config import configure_logging
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex import openalex_id as norm_id
from regional_scout.published_with_us.check import (
    check_author_published,
    fetch_latest_work_anywhere,
)
from regional_scout.published_with_us.io import (
    extract_author_id_from_row,
    find_openalex_id_column,
    load_csv,
    load_shortlist,
    write_csv_subset,
    write_shortlist_enriched,
)
from regional_scout.published_with_us.models import AuthorPublishResult

logger = logging.getLogger(__name__)

LIST_CREDITS = 10


@dataclass
class EnrichOptions:
    input_path: Path
    output_path: Path | None
    source_id: str
    journal_name: str
    year_window_years: int | None  # None = all time
    fetch_latest_for_prospects: bool = True
    export_csv_dir: Path | None = None


def _year_range(years: int | None) -> tuple[int | None, int]:
    end = date.today().year
    if years is None or years <= 0:
        return None, end
    return end - years + 1, end


def estimate_enrich_credits(n_authors: int, *, latest_for_prospects: bool) -> int:
    """Upper bound before run."""
    est = n_authors * LIST_CREDITS
    if latest_for_prospects:
        est += n_authors * LIST_CREDITS
    return est


def resolve_journal_name(client: OpenAlexClient, source_id: str) -> str:
    sid = norm_id(source_id)
    data = client.fetch_page(
        "/sources",
        {"filter": f"id:{sid}", "select": "id,display_name", "per-page": "1"},
    )
    results = data.get("results") or []
    if results:
        return results[0].get("display_name") or sid
    return sid


def _apply_result_to_shortlist_row(
    row: dict[str, Any],
    result: AuthorPublishResult,
    *,
    journal_name: str,
) -> None:
    row["wiley_friendly"] = result.published
    row["wiley_journal"] = journal_name if result.published else None
    row["published_with_us"] = result.to_dict()
    if result.sample_work and result.published:
        row["wiley_journal"] = result.sample_work.source_display_name or journal_name


def enrich_file(config: Config, options: EnrichOptions) -> dict[str, int]:
    configure_logging(api_key=config.openalex.api_key)
    year_from, year_to = _year_range(options.year_window_years)

    input_path = options.input_path
    is_json = input_path.suffix.lower() == ".json"

    if is_json:
        doc, rows = load_shortlist(input_path)
        authors = []
        for row in rows:
            aid = extract_author_id_from_row(row)
            if not aid:
                logger.warning("Skipping row without openalex_id: %s", row.get("display_name"))
                continue
            authors.append(
                AuthorPublishResult(
                    openalex_id=aid,
                    published=False,
                    publication_count=0,
                    display_name=row.get("display_name"),
                    source_row=row,
                )
            )
        csv_headers: list[str] = []
        csv_rows: list[dict[str, str]] = []
    else:
        doc = {}
        csv_headers, csv_rows = load_csv(input_path)
        oa_col = find_openalex_id_column(csv_headers)
        authors = []
        for row in csv_rows:
            aid = extract_author_id_from_row(row)
            if not aid:
                val = row.get(oa_col, "")
                if val:
                    logger.warning("Skipping invalid OpenAlex ID: %s", val)
                continue
            authors.append(
                AuthorPublishResult(
                    openalex_id=aid,
                    published=False,
                    publication_count=0,
                    display_name=row.get("Name") or row.get("name"),
                    source_row=row,
                )
            )

    n = len(authors)
    est = estimate_enrich_credits(n, latest_for_prospects=options.fetch_latest_for_prospects)
    limit = config.openalex.max_credits_per_run
    if est > limit:
        raise SystemExit(
            f"Estimated credits ({est:,}) exceed max_credits_per_run ({limit:,}). "
            f"Reduce input size or raise the limit."
        )
    logger.info("Enriching %d authors (est. %d credits)", n, est)

    client = OpenAlexClient(config)
    try:
        journal_name = options.journal_name or resolve_journal_name(
            client, options.source_id
        )
        published_rows: list[dict[str, str]] = []
        prospect_rows: list[dict[str, str]] = []

        for i, author in enumerate(authors):
            pub, count, sample = check_author_published(
                client,
                author.openalex_id,
                options.source_id,
                year_from,
                year_to,
            )
            author.published = pub
            author.publication_count = count
            author.sample_work = sample
            logger.info(
                "[%d/%d] %s — %s",
                i + 1,
                n,
                author.display_name or author.openalex_id,
                "published" if pub else "prospect",
            )

        if options.fetch_latest_for_prospects:
            prospects = [a for a in authors if not a.published]
            for i, author in enumerate(prospects):
                author.latest_work = fetch_latest_work_anywhere(client, author.openalex_id)
                logger.info(
                    "[%d/%d] Latest work for %s",
                    i + 1,
                    len(prospects),
                    author.openalex_id,
                )

        if is_json:
            by_id = {a.openalex_id: a for a in authors}
            for row in rows:
                aid = extract_author_id_from_row(row)
                if aid and aid in by_id:
                    _apply_result_to_shortlist_row(
                        row, by_id[aid], journal_name=journal_name
                    )
            out = options.output_path or input_path.with_name(
                input_path.stem + ".enriched.json"
            )
            write_shortlist_enriched(
                doc,
                rows,
                out,
                target_source_id=norm_id(options.source_id),
                target_journal_name=journal_name,
                year_window=(year_from, year_to),
                credits_used=client.credits.used,
            )
            logger.info("Wrote %s", out)
        else:
            for author in authors:
                row = author.source_row
                if author.published:
                    published_rows.append(row)  # type: ignore[arg-type]
                else:
                    prospect_rows.append(row)  # type: ignore[arg-type]

            csv_dir = options.export_csv_dir or input_path.parent
            pub_path = csv_dir / f"{input_path.stem}_already_published.csv"
            new_path = csv_dir / f"{input_path.stem}_new_prospects.csv"
            write_csv_subset(csv_headers, published_rows, pub_path)
            write_csv_subset(csv_headers, prospect_rows, new_path)
            logger.info("Wrote %s (%d rows)", pub_path, len(published_rows))
            logger.info("Wrote %s (%d rows)", new_path, len(prospect_rows))

        pipeline_used = int((doc.get("credits") or {}).get("used") or 0) if is_json else 0
        enrich_used = client.credits.used
        return {
            "authors": n,
            "published": sum(1 for a in authors if a.published),
            "prospects": sum(1 for a in authors if not a.published),
            "credits_used": enrich_used,
            "total_credits_used": pipeline_used + enrich_used if is_json else enrich_used,
        }
    finally:
        client.close()

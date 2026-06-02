"""Fetch regional author candidates from OpenAlex."""

from __future__ import annotations

import logging

from regional_scout.config import (
    Config,
    FilterType,
    active_filter,
    log_active_filter_warnings,
)
from regional_scout.models import AuthorRecord, ScopeVector
from regional_scout.openalex import OpenAlexClient, MAX_FILTER_IDS, openalex_id
from regional_scout.openalex_parse import parse_author

logger = logging.getLogger(__name__)

AUTHOR_SELECT = (
    "id,display_name,last_known_institutions,cited_by_count,works_count,counts_by_year"
)
MAX_PAGES_PER_BATCH = 5
# Authors endpoint: topics.id OR lists; keep batches smaller than works
AUTHOR_TOPIC_BATCH = 25


def _id_batches(ids: list[str]) -> list[list[str]]:
    """Split IDs into batches of ≤ MAX_FILTER_IDS for OR-chained filters."""
    if not ids:
        return [[]]
    return [ids[i : i + MAX_FILTER_IDS] for i in range(0, len(ids), MAX_FILTER_IDS)]


def _format_geo_value(filter_type: FilterType, ids: list[str]) -> str:
    if filter_type == "ror":
        return "|".join(Config._normalize_ror(r) for r in ids)
    return "|".join(ids)


def _author_geo_fragment(filter_type: FilterType, ids: list[str]) -> str:
    """Geo filter fragment for /authors (last_known_institutions.*)."""
    value = _format_geo_value(filter_type, ids)
    if filter_type == "country":
        return f"last_known_institutions.country_code:{value}"
    return f"last_known_institutions.id:{value}"


def _works_geo_fragment(filter_type: FilterType, ids: list[str]) -> str:
    """
    Geo filter fragment for /works (authorships.institutions.*).

    MUST stay aligned with _author_geo_fragment — same active_filter() branch
    and ID batch. The portfolio-works scan uses this to discover authors for
    scope prefilter; the co-author graph is built from in-scope works of the
    candidate pool (graph.py has no separate geo filter), so a mismatch here
    would pull a different author set than /authors filtering.
    """
    value = _format_geo_value(filter_type, ids)
    if filter_type == "country":
        return f"authorships.institutions.country_code:{value}"
    return f"authorships.institutions.id:{value}"


def _geo_id_batches(config: Config) -> tuple[FilterType, list[list[str]]]:
    filter_type, ids = active_filter(config.region)
    log_active_filter_warnings(config.region, filter_type)
    if filter_type == "country":
        logger.info(
            "Filtering by country_code. Note: last_known_institutions is an array "
            "in OpenAlex — results may include authors with secondary affiliations "
            "in %s. For tighter results use city.institution_ids.",
            ids,
        )
    return filter_type, _id_batches(ids)


def _region_citation_filter_for_batch(config: Config, id_batch: list[str]) -> str:
    filter_type, _ = active_filter(config.region)
    min_cites = config.scoring.min_cited_by_count
    geo = _author_geo_fragment(filter_type, id_batch)
    return f"{geo},cited_by_count:>{min_cites - 1}"


def _region_citation_filter(config: Config) -> str:
    """Single-batch geo + citation filter (for tests and single-batch paths)."""
    _, batches = _geo_id_batches(config)
    return _region_citation_filter_for_batch(config, batches[0])


def _works_region_filter_for_batch(config: Config, id_batch: list[str]) -> str:
    filter_type, _ = active_filter(config.region)
    return _works_geo_fragment(filter_type, id_batch)


def merge_authors_by_citations(authors: list[AuthorRecord]) -> list[AuthorRecord]:
    by_id: dict[str, AuthorRecord] = {}
    for a in authors:
        existing = by_id.get(a.openalex_id)
        if existing is None or a.cited_by_count > existing.cited_by_count:
            by_id[a.openalex_id] = a
    return sorted(by_id.values(), key=lambda a: a.cited_by_count, reverse=True)


def _fetch_authors_list(
    client: OpenAlexClient,
    geo_filter: str,
    *,
    max_pages: int,
    extra_filter: str | None = None,
) -> list[AuthorRecord]:
    filt = f"{geo_filter},{extra_filter}" if extra_filter else geo_filter
    raw = client.fetch_list(
        "/authors",
        {
            "filter": filt,
            "sort": "cited_by_count:desc",
            "per-page": "200",
            "select": AUTHOR_SELECT,
        },
        max_pages=max_pages,
    )
    return [parse_author(r) for r in raw]


def fetch_candidates(
    client: OpenAlexClient,
    config: Config,
    scope: ScopeVector | None = None,
) -> list[AuthorRecord]:
    """
    When scope_author_prefilter is on (default), only authors likely relevant
    to the scope are returned:
    - /authors filtered by region, citations, and topics.id (no publication_year)
    - /works in portfolio sources + window + region → author IDs → /authors
    """
    if scope is not None and config.scoring.scope_author_prefilter:
        return _fetch_scoped_candidates(client, config, scope)
    return _fetch_regional_candidates(client, config)


def _fetch_regional_candidates(
    client: OpenAlexClient, config: Config
) -> list[AuthorRecord]:
    filter_type, batches = _geo_id_batches(config)
    collected: list[AuthorRecord] = []
    max_pages = max(1, (config.openalex.max_candidates + 199) // 200)

    for batch in batches:
        geo_filter = _region_citation_filter_for_batch(config, batch)
        collected.extend(_fetch_authors_list(client, geo_filter, max_pages=max_pages))

    merged = merge_authors_by_citations(collected)
    capped = merged[: config.openalex.max_candidates]
    logger.info(
        "Fetched %d regional candidates (cap %d, no scope prefilter, %s batches)",
        len(capped),
        config.openalex.max_candidates,
        len(batches),
    )
    return capped


def _fetch_authors_by_ids(
    client: OpenAlexClient, author_ids: set[str]
) -> list[AuthorRecord]:
    if not author_ids:
        return []
    collected: list[AuthorRecord] = []
    sorted_ids = sorted(author_ids)
    for i in range(0, len(sorted_ids), MAX_FILTER_IDS):
        chunk = sorted_ids[i : i + MAX_FILTER_IDS]
        filt = f"openalex_id:{'|'.join(chunk)}"
        raw = client.fetch_list(
            "/authors",
            {"filter": filt, "select": AUTHOR_SELECT, "per-page": "200"},
            max_pages=1,
        )
        collected.extend(parse_author(r) for r in raw)
    return collected


def _author_ids_from_portfolio_works(
    client: OpenAlexClient,
    config: Config,
    scope: ScopeVector,
) -> set[str]:
    """
    Discover regional authors via in-window works in portfolio sources.
    Uses _works_geo_fragment (same active_filter branch as /authors).
    """
    y0, y1 = config.publication_year_range
    sources = "|".join(sorted(scope.source_ids))
    _, batches = _geo_id_batches(config)
    ids: set[str] = set()
    total_works = 0

    for batch in batches:
        works_geo = _works_region_filter_for_batch(config, batch)
        filt = ",".join(
            [
                f"primary_location.source.id:{sources}",
                f"publication_year:{y0}-{y1}",
                works_geo,
            ]
        )
        raw = client.fetch_list(
            "/works",
            {"filter": filt, "select": "authorships", "per-page": "200"},
            max_pages=MAX_PAGES_PER_BATCH * 2,
        )
        total_works += len(raw)
        for work in raw:
            for auth in work.get("authorships") or []:
                author = auth.get("author") or {}
                if author.get("id"):
                    ids.add(openalex_id(author["id"]))

    logger.info(
        "Portfolio works scan: %d works → %d unique author IDs (%d geo batches)",
        total_works,
        len(ids),
        len(batches),
    )
    return ids


def _fetch_scoped_candidates(
    client: OpenAlexClient,
    config: Config,
    scope: ScopeVector,
) -> list[AuthorRecord]:
    _, geo_batches = _geo_id_batches(config)
    collected: list[AuthorRecord] = []

    topic_ids = sorted(scope.topic_ids)
    for geo_batch in geo_batches:
        base = _region_citation_filter_for_batch(config, geo_batch)
        for i in range(0, len(topic_ids), AUTHOR_TOPIC_BATCH):
            chunk = topic_ids[i : i + AUTHOR_TOPIC_BATCH]
            topics = "|".join(chunk)
            collected.extend(
                _fetch_authors_list(
                    client,
                    base,
                    max_pages=MAX_PAGES_PER_BATCH,
                    extra_filter=f"topics.id:{topics}",
                )
            )

    if scope.source_ids:
        work_author_ids = _author_ids_from_portfolio_works(client, config, scope)
        collected.extend(_fetch_authors_by_ids(client, work_author_ids))

    merged = merge_authors_by_citations(collected)
    min_cites = config.scoring.min_cited_by_count
    merged = [a for a in merged if a.cited_by_count >= min_cites]
    capped = merged[: config.openalex.max_candidates]
    logger.info(
        "Fetched %d scope-matched candidates (cap %d, from %d unique after cite filter)",
        len(capped),
        config.openalex.max_candidates,
        len(merged),
    )
    return capped

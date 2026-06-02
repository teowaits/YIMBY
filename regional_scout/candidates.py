"""Fetch regional author candidates from OpenAlex."""

from __future__ import annotations

import logging

from regional_scout.config import Config
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


def _region_citation_filter(config: Config) -> str:
    field, value = config.region_filter()
    min_cites = config.scoring.min_cited_by_count
    return f"{field}:{value},cited_by_count:>{min_cites - 1}"


def _works_region_filter(config: Config) -> str:
    """Region filter for /works (authorships.institutions.*)."""
    if config.region.ror_ids:
        rors = "|".join(Config._normalize_ror(r) for r in config.region.ror_ids)
        return f"authorships.institutions.id:{rors}"
    codes = "|".join(c.lower() for c in config.region.country_codes)
    return f"authorships.institutions.country_code:{codes}"


def merge_authors_by_citations(authors: list[AuthorRecord]) -> list[AuthorRecord]:
    by_id: dict[str, AuthorRecord] = {}
    for a in authors:
        existing = by_id.get(a.openalex_id)
        if existing is None or a.cited_by_count > existing.cited_by_count:
            by_id[a.openalex_id] = a
    return sorted(by_id.values(), key=lambda a: a.cited_by_count, reverse=True)


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
    filt = _region_citation_filter(config)
    raw = client.fetch_list(
        "/authors",
        {
            "filter": filt,
            "sort": "cited_by_count:desc",
            "per-page": "200",
            "select": AUTHOR_SELECT,
        },
        max_pages=max(1, (config.openalex.max_candidates + 199) // 200),
    )
    authors = [parse_author(r) for r in raw]
    capped = authors[: config.openalex.max_candidates]
    logger.info(
        "Fetched %d regional candidates (cap %d, no scope prefilter)",
        len(capped),
        config.openalex.max_candidates,
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
    """Discover regional authors via in-window works in portfolio sources."""
    y0, y1 = config.publication_year_range
    sources = "|".join(sorted(scope.source_ids))
    filt = ",".join(
        [
            f"primary_location.source.id:{sources}",
            f"publication_year:{y0}-{y1}",
            _works_region_filter(config),
        ]
    )
    raw = client.fetch_list(
        "/works",
        {"filter": filt, "select": "authorships", "per-page": "200"},
        max_pages=MAX_PAGES_PER_BATCH * 2,
    )
    ids: set[str] = set()
    for work in raw:
        for auth in work.get("authorships") or []:
            author = auth.get("author") or {}
            if author.get("id"):
                ids.add(openalex_id(author["id"]))
    logger.info(
        "Portfolio works scan: %d works → %d unique author IDs",
        len(raw),
        len(ids),
    )
    return ids


def _fetch_scoped_candidates(
    client: OpenAlexClient,
    config: Config,
    scope: ScopeVector,
) -> list[AuthorRecord]:
    base = _region_citation_filter(config)
    collected: list[AuthorRecord] = []

    topic_ids = sorted(scope.topic_ids)
    for i in range(0, len(topic_ids), AUTHOR_TOPIC_BATCH):
        chunk = topic_ids[i : i + AUTHOR_TOPIC_BATCH]
        topics = "|".join(chunk)
        raw = client.fetch_list(
            "/authors",
            {
                "filter": f"{base},topics.id:{topics}",
                "sort": "cited_by_count:desc",
                "per-page": "200",
                "select": AUTHOR_SELECT,
            },
            max_pages=MAX_PAGES_PER_BATCH,
        )
        collected.extend(parse_author(r) for r in raw)

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

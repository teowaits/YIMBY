"""Fetch regional author candidates from OpenAlex."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from regional_scout.config import (
    Config,
    FilterType,
    active_filter,
    log_active_filter_warnings,
    normalize_institution_id,
)
from regional_scout.models import AuthorRecord, ScopeVector
from regional_scout.openalex import OpenAlexClient, MAX_FILTER_IDS, openalex_id
from regional_scout.openalex_parse import parse_author

logger = logging.getLogger(__name__)

AUTHOR_SELECT = (
    "id,display_name,orcid,last_known_institutions,affiliations,"
    "cited_by_count,works_count,counts_by_year"
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

    Used only for auxiliary /works queries — not for candidate pool construction.
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


def _is_primarily_local(
    raw: dict[str, Any],
    target_institution_ids: set[str],
    recency_years: int,
    current_year: int,
) -> bool:
    """
    True if the author has a recent affiliation with a target institution.

    Uses affiliations from the /authors response when present; falls back to
    last_known_institutions when affiliation history is sparse.
    """
    threshold_year = current_year - recency_years

    affiliations = raw.get("affiliations") or []
    if affiliations:
        for aff in affiliations:
            inst = aff.get("institution") or {}
            inst_id = inst.get("id")
            if not inst_id:
                continue
            if normalize_institution_id(inst_id) in target_institution_ids:
                aff_years = aff.get("years") or []
                if not aff_years or max(aff_years) >= threshold_year:
                    return True
        return False

    for inst in raw.get("last_known_institutions") or []:
        inst_id = inst.get("id")
        if inst_id and normalize_institution_id(inst_id) in target_institution_ids:
            return True
    return False


def _verify_institution_affiliation(
    raw_authors: list[dict[str, Any]],
    config: Config,
) -> list[dict[str, Any]]:
    """Drop authors with only incidental target-institution affiliation."""
    filter_type, ids = active_filter(config.region)
    if filter_type != "institution":
        return raw_authors

    target_ids = set(ids)
    recency_years = config.region.city.affiliation_recency_years
    current_year = date.today().year
    kept = [
        raw
        for raw in raw_authors
        if _is_primarily_local(raw, target_ids, recency_years, current_year)
    ]
    n_dropped = len(raw_authors) - len(kept)
    if n_dropped:
        logger.info(
            "Post-fetch affiliation verification: dropped %d candidates with "
            "incidental local affiliation (co-authored with local researchers "
            "but not primarily based here).",
            n_dropped,
        )
    return kept


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
    config: Config,
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
    verified = _verify_institution_affiliation(raw, config)
    return [parse_author(r) for r in verified]


def fetch_candidates(
    client: OpenAlexClient,
    config: Config,
    scope: ScopeVector | None = None,
) -> list[AuthorRecord]:
    """
    When scope_author_prefilter is on (default), only authors likely relevant
    to the scope are returned via /authors filtered by region, citations, and
    topics.id (no publication_year).
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
        collected.extend(
            _fetch_authors_list(client, geo_filter, config, max_pages=max_pages)
        )

    merged = merge_authors_by_citations(collected)
    capped = merged[: config.openalex.max_candidates]
    logger.info(
        "Fetched %d regional candidates (cap %d, no scope prefilter, %s batches)",
        len(capped),
        config.openalex.max_candidates,
        len(batches),
    )
    return capped


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
                    config,
                    max_pages=MAX_PAGES_PER_BATCH,
                    extra_filter=f"topics.id:{topics}",
                )
            )

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

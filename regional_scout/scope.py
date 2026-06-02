"""Build scope vector from OpenAlex corpora."""

from __future__ import annotations

import logging
from collections import Counter

from regional_scout.config import PORTFOLIO_ISSNS, Config
from regional_scout.models import ScopeVector
from regional_scout.openalex import OpenAlexClient
from regional_scout.openalex_parse import topic_id_from_work

logger = logging.getLogger(__name__)

TOP_N_TOPICS = 50


def _year_filter(config: Config) -> str:
    y0, y1 = config.publication_year_range
    return f"publication_year:{y0}-{y1}"


def _top_topics_from_works(works: list[dict], n: int = TOP_N_TOPICS) -> set[str]:
    counts: Counter[str] = Counter()
    for w in works:
        tid = topic_id_from_work(w)
        if tid:
            counts[tid] += 1
    return {tid for tid, _ in counts.most_common(n)}


def _fetch_works_for_source(
    client: OpenAlexClient, source_id: str, config: Config
) -> list[dict]:
    yf = _year_filter(config)
    return client.fetch_list(
        "/works",
        {
            "filter": f"primary_location.source.id:{source_id},{yf}",
            "select": "id,primary_topic",
        },
        max_pages=3,
    )


def _fetch_works_for_doi(client: OpenAlexClient, doi: str) -> list[dict]:
    data = client.fetch_list(
        "/works",
        {"filter": f"doi:{doi}", "select": "id,primary_topic"},
        max_pages=1,
    )
    return data


def _resolve_source_by_issn(client: OpenAlexClient, issn: str) -> str | None:
    rows = client.fetch_list(
        "/sources",
        {"filter": f"issn:{issn}", "select": "id", "per-page": "5"},
        max_pages=1,
    )
    if not rows:
        return None
    from regional_scout.openalex import openalex_id

    return openalex_id(rows[0]["id"])


def build_scope_vector(client: OpenAlexClient, config: Config) -> ScopeVector:
    topic_ids: set[str] = set(config.scope.additional_topic_ids)
    source_ids: set[str] = set(config.wiley_portfolio.portfolio_source_ids())

    portfolio = config.wiley_portfolio
    ais_id = portfolio.advanced_intelligent_systems
    aidi_id = portfolio.advanced_intelligent_discovery

    if ais_id:
        source_ids.add(ais_id)
        ais_works = _fetch_works_for_source(client, ais_id, config)
        topic_ids |= _top_topics_from_works(ais_works)
        logger.info("AIS scope: %d topics from %d works", len(topic_ids), len(ais_works))

    aidi_topics: set[str] = set()
    if aidi_id:
        source_ids.add(aidi_id)
        aidi_works = _fetch_works_for_source(client, aidi_id, config)
        aidi_topics = _top_topics_from_works(aidi_works)
        topic_ids |= aidi_topics
        logger.info("AIDI scope: %d topics", len(aidi_topics))

    for doi in config.scope.seed_dois:
        for w in _fetch_works_for_doi(client, doi):
            tid = topic_id_from_work(w)
            if tid:
                topic_ids.add(tid)

    for comp in config.scope.competitor_journals:
        sid = _resolve_source_by_issn(client, comp.issn)
        if not sid:
            logger.warning("No OpenAlex source for competitor ISSN %s", comp.issn)
            continue
        comp_works = _fetch_works_for_source(client, sid, config)
        comp_topics = _top_topics_from_works(comp_works)
        if aidi_topics:
            topic_ids |= comp_topics & aidi_topics
        else:
            topic_ids |= comp_topics

    # Topic fan-out from other resolved portfolio journals (e.g. Advanced Science)
    skip = {x for x in (ais_id, aidi_id) if x}
    for key in PORTFOLIO_ISSNS:
        sid = getattr(portfolio, key, None)
        if not sid or sid in skip:
            continue
        works = _fetch_works_for_source(client, sid, config)
        added = _top_topics_from_works(works)
        before = len(topic_ids)
        topic_ids |= added
        logger.info(
            "%s fan-out: +%d topics from %d works",
            key.replace("_", " "),
            len(topic_ids) - before,
            len(works),
        )

    logger.info("Scope vector: %d topics, %d sources", len(topic_ids), len(source_ids))
    return ScopeVector(topic_ids=frozenset(topic_ids), source_ids=frozenset(source_ids))

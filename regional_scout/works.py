"""Fetch per-author works in scope (topic OR source, not AND)."""

from __future__ import annotations

import logging

from regional_scout.config import Config
from regional_scout.models import ScopeVector, WorkRecord
from regional_scout.openalex import OpenAlexClient, openalex_id
from regional_scout.openalex_parse import parse_work

logger = logging.getLogger(__name__)

MAX_TOPIC_BATCH = 50
WORK_SELECT = "id,title,publication_year,primary_topic,primary_location,authorships,fwci"


def _year_filter(config: Config) -> str:
    y0, y1 = config.publication_year_range
    return f"publication_year:{y0}-{y1}"


def _work_in_scope(work: WorkRecord, scope: ScopeVector) -> bool:
    if work.primary_source_id and work.primary_source_id in scope.source_ids:
        return True
    if work.primary_topic_id and work.primary_topic_id in scope.topic_ids:
        return True
    return False


def merge_work_records(works: list[WorkRecord], scope: ScopeVector) -> list[WorkRecord]:
    """Dedupe by work ID; keep only in-scope rows."""
    by_id: dict[str, WorkRecord] = {}
    for w in works:
        if _work_in_scope(w, scope):
            by_id[w.openalex_id] = w
    return list(by_id.values())


def fetch_works(
    client: OpenAlexClient,
    author_id: str,
    scope: ScopeVector,
    config: Config,
) -> list[WorkRecord]:
    """
    Fetch in-scope works via separate OpenAlex queries (OR semantics):
    - author + year + each topic batch
    - author + year + portfolio sources
    Merged and deduped by work ID.
    """
    aid = openalex_id(author_id)
    year_filt = _year_filter(config)
    author_year = f"authorships.author.id:{aid},{year_filt}"

    collected: list[WorkRecord] = []

    if scope.source_ids:
        sources = "|".join(sorted(scope.source_ids))
        raw = client.fetch_list(
            "/works",
            {
                "filter": f"{author_year},primary_location.source.id:{sources}",
                "select": WORK_SELECT,
                "per-page": "200",
            },
        )
        collected.extend(parse_work(w) for w in raw)

    topic_ids = sorted(scope.topic_ids)
    for i in range(0, len(topic_ids), MAX_TOPIC_BATCH):
        chunk = topic_ids[i : i + MAX_TOPIC_BATCH]
        topics = "|".join(chunk)
        raw = client.fetch_list(
            "/works",
            {
                "filter": f"{author_year},topics.id:{topics}",
                "select": WORK_SELECT,
                "per-page": "200",
            },
        )
        collected.extend(parse_work(w) for w in raw)

    return merge_work_records(collected, scope)


def in_scope_works(
    works: list[WorkRecord], scope: ScopeVector, config: Config
) -> list[WorkRecord]:
    y0, y1 = config.publication_year_range
    return [
        w
        for w in works
        if y0 <= w.publication_year <= y1 and _work_in_scope(w, scope)
    ]

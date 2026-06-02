"""Parse OpenAlex API JSON into domain models."""

from __future__ import annotations

from typing import Any

from regional_scout.models import AuthorRecord, WorkRecord
from regional_scout.openalex import openalex_id


def parse_author(raw: dict[str, Any]) -> AuthorRecord:
    inst = None
    country = None
    insts = raw.get("last_known_institutions") or []
    if insts:
        inst = insts[0].get("display_name")
        country = insts[0].get("country_code")

    first_year = None
    counts = raw.get("counts_by_year") or []
    if counts:
        years = [c["year"] for c in counts if c.get("year")]
        if years:
            first_year = min(years)

    return AuthorRecord(
        openalex_id=openalex_id(raw["id"]),
        display_name=raw.get("display_name") or "",
        institution_name=inst,
        country_code=country,
        cited_by_count=int(raw.get("cited_by_count") or 0),
        works_count=int(raw.get("works_count") or 0),
        first_publication_year=first_year,
    )


def parse_work(raw: dict[str, Any]) -> WorkRecord:
    topic = raw.get("primary_topic") or {}
    loc = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    coauthors = []
    for auth in raw.get("authorships") or []:
        author = auth.get("author") or {}
        if author.get("id"):
            coauthors.append(openalex_id(author["id"]))

    fwci = None
    if raw.get("fwci") is not None:
        fwci = float(raw["fwci"])

    return WorkRecord(
        openalex_id=openalex_id(raw["id"]),
        title=raw.get("title") or raw.get("display_name") or "",
        publication_year=int(raw.get("publication_year") or 0),
        primary_topic_id=openalex_id(topic["id"]) if topic.get("id") else None,
        primary_source_id=openalex_id(source["id"]) if source.get("id") else None,
        fwci=fwci,
        coauthor_ids=coauthors,
    )


def topic_id_from_work(raw: dict[str, Any]) -> str | None:
    topic = raw.get("primary_topic") or {}
    if topic.get("id"):
        return openalex_id(topic["id"])
    return None

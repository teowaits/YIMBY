"""OpenAlex publication checks for a single author."""

from __future__ import annotations

from regional_scout.openalex import OpenAlexClient, openalex_id
from regional_scout.published_with_us.models import WorkSample


def _parse_work_sample(raw: dict) -> WorkSample:
    loc = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    doi = raw.get("doi")
    if isinstance(doi, str) and doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "")
    return WorkSample(
        openalex_id=openalex_id(raw["id"]),
        title=raw.get("title") or raw.get("display_name") or "",
        publication_year=raw.get("publication_year"),
        doi=doi if isinstance(doi, str) else None,
        source_display_name=source.get("display_name"),
    )


def check_author_published(
    client: OpenAlexClient,
    author_id: str,
    source_id: str,
    year_from: int | None,
    year_to: int,
) -> tuple[bool, int, WorkSample | None]:
    """
    One list call (10 credits). Returns published flag, count, newest sample in window.
    """
    aid = openalex_id(author_id)
    sid = openalex_id(source_id)
    parts = [f"authorships.author.id:{aid}", f"primary_location.source.id:{sid}"]
    if year_from is not None:
        parts.append(f"publication_year:{year_from}-{year_to}")

    data = client.fetch_page(
        "/works",
        {
            "filter": ",".join(parts),
            "sort": "publication_year:desc",
            "per-page": "1",
            "select": "id,title,doi,publication_year,primary_location",
        },
    )
    count = int((data.get("meta") or {}).get("count") or 0)
    if count <= 0:
        return False, 0, None
    results = data.get("results") or []
    sample = _parse_work_sample(results[0]) if results else None
    return True, count, sample


def fetch_latest_work_anywhere(
    client: OpenAlexClient,
    author_id: str,
) -> WorkSample | None:
    """Latest work in any journal (10 credits). For new-prospect enrichment."""
    aid = openalex_id(author_id)
    data = client.fetch_page(
        "/works",
        {
            "filter": f"authorships.author.id:{aid}",
            "sort": "publication_year:desc",
            "per-page": "1",
            "select": "id,title,doi,publication_year,primary_location",
        },
    )
    results = data.get("results") or []
    if not results:
        return None
    return _parse_work_sample(results[0])

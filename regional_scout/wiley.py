"""Live OpenAlex Wiley AI/Comp portfolio signal."""

from __future__ import annotations

import logging

from regional_scout.config import Config
from regional_scout.openalex import OpenAlexClient, openalex_id

logger = logging.getLogger(__name__)


def check_wiley_signal(
    client: OpenAlexClient,
    author_id: str,
    portfolio_source_ids: list[str],
    window: tuple[int, int],
    config: Config,
) -> tuple[bool, str | None, int]:
    """
    One list call per author (10 credits).
    Returns (is_friendly, journal_display_name, count_in_window).
    """
    source_ids = [sid for sid in portfolio_source_ids if sid]
    if not source_ids:
        logger.warning(
            "wiley_portfolio has no resolved source IDs — "
            "run init-portfolio to resolve them. "
            "Wiley signal will be False for all candidates."
        )
        return False, None, 0

    aid = openalex_id(author_id)
    y0, y1 = window
    sources = "|".join(source_ids)
    filt = (
        f"authorships.author.id:{aid},"
        f"primary_location.source.id:{sources},"
        f"publication_year:{y0}-{y1}"
    )

    data = client.fetch_page(
        "/works",
        {
            "filter": filt,
            "per-page": "1",
            "select": "id,primary_location",
        },
    )
    meta = data.get("meta") or {}
    count = int(meta.get("count") or 0)
    if count <= 0:
        return False, None, 0

    results = data.get("results") or []
    if not results:
        return True, None, count

    loc = results[0].get("primary_location") or {}
    source = loc.get("source") or {}
    name = source.get("display_name")
    return True, name, count

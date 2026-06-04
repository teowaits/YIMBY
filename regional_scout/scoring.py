"""Pure scoring functions — no I/O."""

from __future__ import annotations

import math
from datetime import date

from regional_scout.config import Config
from regional_scout.models import (
    AuthorRecord,
    RawScoreComponents,
    ScoreBreakdown,
    ScopeVector,
    ScoredAuthor,
    WorkRecord,
)

PRODUCTIVITY_HALF_LIFE_YEARS = 3.0


def _in_scope(work: WorkRecord, scope: ScopeVector) -> bool:
    if work.primary_source_id and work.primary_source_id in scope.source_ids:
        return True
    if work.primary_topic_id and work.primary_topic_id in scope.topic_ids:
        return True
    return False


def _recency_weight(year: int, current_year: int) -> float:
    age = max(0, current_year - year)
    return 0.5 ** (age / PRODUCTIVITY_HALF_LIFE_YEARS)


def _career_boost_multiplier(author: AuthorRecord, config: Config) -> float:
    if not config.scoring.career_stage_boost:
        return 1.0
    if author.first_publication_year is None:
        return 1.0
    years = date.today().year - author.first_publication_year
    if 5 <= years <= 15:
        return config.scoring.career_stage_boost_multiplier
    return 1.0


def compute_raw_components(
    author: AuthorRecord,
    works: list[WorkRecord],
    centrality: float,
    scope: ScopeVector,
    config: Config,
    *,
    wiley_flag: float = 0.0,
) -> RawScoreComponents:
    current_year = date.today().year
    year_from, year_to = config.publication_year_range

    scoped = [
        w
        for w in works
        if year_from <= w.publication_year <= year_to and _in_scope(w, scope)
    ]

    if not scoped:
        return RawScoreComponents(
            openalex_id=author.openalex_id,
            relevance=0.0,
            productivity=0.0,
            impact=0.0,
            centrality=centrality,
            wiley_flag=wiley_flag,
            career_boost_multiplier=_career_boost_multiplier(author, config),
        )

    topic_hits = sum(
        1 for w in scoped if w.primary_topic_id and w.primary_topic_id in scope.topic_ids
    )
    relevance = topic_hits / len(scoped)

    productivity = sum(
        _recency_weight(w.publication_year, current_year) for w in scoped
    )

    fwcis = [w.fwci for w in scoped if w.fwci is not None]
    impact = sum(fwcis) / len(fwcis) if fwcis else 0.0

    return RawScoreComponents(
        openalex_id=author.openalex_id,
        relevance=relevance,
        productivity=productivity,
        impact=impact,
        centrality=centrality,
        wiley_flag=wiley_flag,
        career_boost_multiplier=_career_boost_multiplier(author, config),
    )


def _min_max_normalize(values: list[float]) -> list[float]:
    if len(values) == 1:
        return [1.0] * len(values)
    lo = min(values)
    hi = max(values)
    if math.isclose(lo, hi):
        return [1.0 if hi > 0 else 0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def normalize_and_composite(
    all_raw: list[RawScoreComponents],
    authors: dict[str, AuthorRecord],
    works_counts: dict[str, int],
    mean_fwcis: dict[str, float | None],
    wiley_flags: dict[str, bool],
    wiley_journals: dict[str, str | None],
    wiley_counts: dict[str, int],
    config: Config,
) -> list[ScoredAuthor]:
    if not all_raw:
        return []

    rel = _min_max_normalize([r.relevance for r in all_raw])
    prod = _min_max_normalize([r.productivity for r in all_raw])
    imp = _min_max_normalize([r.impact for r in all_raw])
    cent = _min_max_normalize([r.centrality for r in all_raw])
    wiley = _min_max_normalize([r.wiley_flag for r in all_raw])

    w = config.scoring.weights
    scored: list[ScoredAuthor] = []

    for i, raw in enumerate(all_raw):
        norm_rel, norm_prod, norm_imp, norm_cent, norm_wiley = (
            rel[i],
            prod[i],
            imp[i],
            cent[i],
            wiley[i],
        )
        composite = (
            w.relevance * norm_rel
            + w.productivity * norm_prod
            + w.impact * norm_imp
            + w.centrality * norm_cent
            + w.wiley * norm_wiley
        ) * raw.career_boost_multiplier

        author = authors[raw.openalex_id]
        breakdown = ScoreBreakdown(
            relevance=norm_rel,
            productivity=norm_prod,
            impact=norm_imp,
            centrality=norm_cent,
            wiley=norm_wiley,
            composite=composite,
            raw_relevance=raw.relevance,
            raw_productivity=raw.productivity,
            raw_impact=raw.impact,
            raw_centrality=raw.centrality,
        )
        scored.append(
            ScoredAuthor(
                author=author,
                breakdown=breakdown,
                wiley_friendly=wiley_flags.get(raw.openalex_id, False),
                wiley_journal=wiley_journals.get(raw.openalex_id),
                wiley_count=wiley_counts.get(raw.openalex_id, 0),
                in_scope_work_count=works_counts.get(raw.openalex_id, 0),
                mean_fwci=mean_fwcis.get(raw.openalex_id),
            )
        )

    scored.sort(key=lambda s: s.breakdown.composite, reverse=True)
    return scored

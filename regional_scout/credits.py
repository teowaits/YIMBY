"""Pre-run OpenAlex credit estimation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from regional_scout.config import Config
from regional_scout.openalex import MAX_FILTER_IDS

LIST_CREDITS = 10


@dataclass
class CreditEstimate:
    total: int
    scope: int
    candidates: int
    works: int
    wiley: int
    auto_enrich: int = 0
    breakdown: dict[str, int] = field(default_factory=dict)

    def format_message(self) -> str:
        lines = [
            f"  scope:       {self.scope:,}",
            f"  candidates:  {self.candidates:,}",
            f"  works:       {self.works:,}",
            f"  wiley:       {self.wiley:,}",
        ]
        if self.auto_enrich:
            lines.append(f"  auto_enrich: {self.auto_enrich:,}")
        lines.append(f"  TOTAL:       {self.total:,}")
        return "Estimated OpenAlex credits:\n" + "\n".join(lines)


def should_check_wiley(config: Config) -> bool:
    return config.wiley_portfolio.should_check_wiley(config.scoring.weights.wiley)


def topic_batch_count(n_topics: int, *, batch_size: int = MAX_FILTER_IDS) -> int:
    if n_topics <= 0:
        return 0
    return math.ceil(n_topics / batch_size)


def estimate_works_calls_per_author(n_topics: int, n_sources: int) -> int:
    """List calls per author for OR-style works fetch."""
    calls = topic_batch_count(n_topics)
    if n_sources > 0:
        calls += 1
    return max(calls, 1)


def scope_credit_plan(config: Config) -> int:
    """
    Conservative fixed estimate for scope-building API calls.
    Covers: portfolio sources, seed DOIs, competitor ISSN lookups, topic fan-out pages.
    """
    n = 0
    n += 2 * 3 * LIST_CREDITS
    n += len(config.scope.seed_dois) * 1
    n += len(config.scope.competitor_journals) * 3 * LIST_CREDITS
    if config.scope.additional_topic_ids:
        n += LIST_CREDITS
    return n


def estimate_run_credits(config: Config) -> CreditEstimate:
    max_n = config.openalex.max_candidates
    pages_est = config.openalex.works_pages_estimate

    scope = scope_credit_plan(config)

    # Assume ~90 topics / 2 sources until scope is built (conservative)
    n_topics_est = 90
    n_sources_est = 2

    if config.scoring.scope_author_prefilter:
        author_batches = topic_batch_count(n_topics_est, batch_size=25) + (
            1 if n_sources_est else 0
        )
        # topic author batches + portfolio works scan + author ID lookups
        candidates = author_batches * 3 * LIST_CREDITS + 10 * LIST_CREDITS
    else:
        candidates = math.ceil(max_n / 200) * LIST_CREDITS

    per_author = estimate_works_calls_per_author(n_topics_est, n_sources_est)
    works = max_n * pages_est * per_author * LIST_CREDITS
    wiley = max_n * LIST_CREDITS if should_check_wiley(config) else 0
    enrich = 0
    if config.output.auto_enrich:
        n_short = config.output.shortlist_size
        enrich = n_short * LIST_CREDITS
        if config.output.enrich_latest_work:
            enrich += n_short * LIST_CREDITS

    total = scope + candidates + works + wiley + enrich
    breakdown = {
        "scope": scope,
        "candidates": candidates,
        "works": works,
        "wiley": wiley,
        "auto_enrich": enrich,
    }
    return CreditEstimate(
        total=total,
        scope=scope,
        candidates=candidates,
        works=works,
        wiley=wiley,
        auto_enrich=enrich,
        breakdown=breakdown,
    )


def assert_within_budget(config: Config, estimate: CreditEstimate) -> None:
    limit = config.openalex.max_credits_per_run
    if estimate.total > limit:
        raise SystemExit(
            f"Estimated credits ({estimate.total:,}) exceed max_credits_per_run "
            f"({limit:,}).\n{estimate.format_message()}\n"
            "Lower max_candidates, works_pages_estimate, or raise the limit."
        )

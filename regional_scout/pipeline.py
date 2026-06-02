"""Orchestrate the regional-scout run."""

from __future__ import annotations

import logging
from pathlib import Path

from regional_scout import __version__
from regional_scout.candidates import fetch_candidates
from regional_scout.config import (
    Config,
    active_filter,
    region_filter_metadata,
    region_summary_label,
    resolve_enrich_target,
)
from regional_scout.credits import assert_within_budget, estimate_run_credits, should_check_wiley
from regional_scout.graph import build_coauthor_graph, compute_centrality
from regional_scout.models import AuthorRecord, RunMetadata, ScoredAuthor, WorkRecord
from regional_scout.openalex import OpenAlexClient
from regional_scout.output.html_writer import write_report_from_json
from regional_scout.output.json_writer import write_shortlist
from regional_scout.output.paths import resolve_run_output_dir, write_latest_pointer
from regional_scout.scope import build_scope_vector
from regional_scout.scoring import compute_raw_components, normalize_and_composite
from regional_scout.wiley import check_wiley_signal
from regional_scout.logging_config import configure_logging
from regional_scout.works import fetch_works, in_scope_works

logger = logging.getLogger(__name__)


def filter_eligible_candidates(
    candidates: list[AuthorRecord],
    works_counts: dict[str, int],
    min_works: int,
) -> list[AuthorRecord]:
    if min_works <= 0:
        return candidates
    return [a for a in candidates if works_counts.get(a.openalex_id, 0) >= min_works]


def _maybe_auto_enrich(config: Config, shortlist_path: Path) -> None:
    if not config.output.auto_enrich:
        return
    try:
        source_id, journal_name = resolve_enrich_target(config)
    except ValueError as e:
        logger.warning("Skipping auto_enrich: %s", e)
        return

    from regional_scout.published_with_us.enrich import EnrichOptions, enrich_file

    logger.info(
        "Auto-enrich against %s (%s)…",
        journal_name,
        source_id,
    )
    stats = enrich_file(
        config,
        EnrichOptions(
            input_path=shortlist_path,
            output_path=shortlist_path,
            source_id=source_id,
            journal_name=journal_name,
            year_window_years=config.openalex.work_window_years,
            fetch_latest_for_prospects=config.output.enrich_latest_work,
        ),
    )
    logger.info(
        "Auto-enrich done: %d published, %d prospects, %d credits (run total %d)",
        stats["published"],
        stats["prospects"],
        stats["credits_used"],
        stats.get("total_credits_used", stats["credits_used"]),
    )


def run_pipeline(config: Config) -> list[ScoredAuthor]:
    configure_logging(api_key=config.openalex.api_key)

    estimate = estimate_run_credits(config)
    logger.info("%s", estimate.format_message())
    assert_within_budget(config, estimate)

    filter_type, filter_ids = active_filter(config.region)
    logger.info("Region filter: %s (%d value(s))", filter_type, len(filter_ids))
    if filter_type == "country":
        logger.warning(
            "Country-level filter active. For trip-mode accuracy use "
            "'regional-scout init-city --city <name> --country <code> --write' first."
        )

    check_wiley = should_check_wiley(config)
    portfolio_ids = config.wiley_portfolio.portfolio_source_ids()
    year_range = config.publication_year_range
    out_dir = resolve_run_output_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Writing output to %s", out_dir)

    client = OpenAlexClient(config)
    try:
        scope = build_scope_vector(client, config)
        candidates = fetch_candidates(client, config, scope)

        works_map: dict[str, list[WorkRecord]] = {}
        wiley_flags: dict[str, bool] = {}
        wiley_journals: dict[str, str | None] = {}
        works_counts: dict[str, int] = {}
        mean_fwcis: dict[str, float | None] = {}

        for author in candidates:
            works = fetch_works(client, author.openalex_id, scope, config)
            scoped = in_scope_works(works, scope, config)
            works_map[author.openalex_id] = scoped
            works_counts[author.openalex_id] = len(scoped)

            fwcis = [w.fwci for w in scoped if w.fwci is not None]
            mean_fwcis[author.openalex_id] = (
                sum(fwcis) / len(fwcis) if fwcis else None
            )

        min_in_scope = config.scoring.min_in_scope_works
        eligible = filter_eligible_candidates(candidates, works_counts, min_in_scope)
        excluded = len(candidates) - len(eligible)
        if excluded:
            logger.info(
                "Excluded %d candidates with fewer than %d in-scope works",
                excluded,
                min_in_scope,
            )
        if not eligible:
            raise SystemExit(
                f"No candidates have at least {min_in_scope} in-scope works. "
                "Lower scoring.min_in_scope_works, widen scope, or increase max_candidates."
            )

        for author in eligible:
            if check_wiley:
                friendly, journal = check_wiley_signal(
                    client,
                    author.openalex_id,
                    portfolio_ids,
                    year_range,
                    config,
                )
                wiley_flags[author.openalex_id] = friendly
                wiley_journals[author.openalex_id] = journal
            else:
                wiley_flags[author.openalex_id] = False
                wiley_journals[author.openalex_id] = None

        g = build_coauthor_graph(eligible, works_map)
        centrality = compute_centrality(g)

        authors_by_id = {a.openalex_id: a for a in eligible}
        raws = []
        for author in eligible:
            wf = 1.0 if wiley_flags.get(author.openalex_id) else 0.0
            raws.append(
                compute_raw_components(
                    author,
                    works_map[author.openalex_id],
                    centrality.get(author.openalex_id, 0.0),
                    scope,
                    config,
                    wiley_flag=wf,
                )
            )

        scored = normalize_and_composite(
            raws,
            authors_by_id,
            works_counts,
            mean_fwcis,
            wiley_flags,
            wiley_journals,
            config,
        )

        top = scored[: config.output.shortlist_size]
        shortlist_path = out_dir / "shortlist.json"
        meta = RunMetadata(
            region_label=region_summary_label(config.region),
            topic_count=len(scope.topic_ids),
            candidate_count=len(candidates),
            eligible_count=len(eligible),
            excluded_in_scope_count=excluded,
            credits_estimated=estimate.total,
            credits_used=client.credits.used,
            cache_hits=client.credits.cache_hits,
            api_calls=client.credits.api_calls,
            publication_year_from=config.publication_year_range[0],
            publication_year_to=config.publication_year_range[1],
            output_dir=str(out_dir),
            scope_summary={
                "topic_count": len(scope.topic_ids),
                "source_count": len(scope.source_ids),
                "min_in_scope_works": min_in_scope,
                "scope_author_prefilter": config.scoring.scope_author_prefilter,
            },
            region_filter=region_filter_metadata(config.region),
        )

        top_works_map = {
            s.author.openalex_id: works_map[s.author.openalex_id] for s in top
        }
        write_shortlist(
            top,
            shortlist_path,
            meta=meta,
            version=__version__,
            works_map=top_works_map,
            include_works=config.output.include_works_in_json,
            max_works_per_author=config.output.max_works_per_author,
        )

        _maybe_auto_enrich(config, shortlist_path)
        html_path = write_report_from_json(shortlist_path)
        logger.info("Wrote %s", html_path)
        write_latest_pointer(config, out_dir)

        logger.info(
            "Done. %d shortlisted from %d eligible (%d fetched, %d excluded in-scope). "
            "Credits: %d used (%d API calls, %d cache hits; estimated %d)",
            len(top),
            len(eligible),
            len(candidates),
            excluded,
            client.credits.used,
            client.credits.api_calls,
            client.credits.cache_hits,
            estimate.total,
        )
        return top
    finally:
        client.close()

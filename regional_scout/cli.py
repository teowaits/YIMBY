"""Typer CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="regional-scout",
    help="Identify and rank regional researchers for Wiley AI×science editorial scouting.",
)


@app.command("report")
def report_cmd(
    input_path: Path = typer.Option(
        Path("output/shortlist.json"),
        "--input",
        "-i",
        help="Path to shortlist.json",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="HTML output path (default: alongside JSON)",
    ),
) -> None:
    """Regenerate shortlist.html from shortlist.json (e.g. after manual enrich)."""
    from regional_scout.output.html_writer import write_report_from_json

    out = write_report_from_json(input_path, output)
    typer.echo(f"Wrote {out}")


@app.command("estimate")
def estimate_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        readable=True,
    ),
) -> None:
    """Print OpenAlex credit estimate without running the pipeline."""
    from regional_scout.config import load_config
    from regional_scout.credits import assert_within_budget, estimate_run_credits

    cfg = load_config(config)
    est = estimate_run_credits(cfg)
    typer.echo(est.format_message())
    if est.total > cfg.openalex.max_credits_per_run:
        typer.secho(
            f"WARNING: over max_credits_per_run ({cfg.openalex.max_credits_per_run:,})",
            fg=typer.colors.YELLOW,
            err=True,
        )
    else:
        typer.secho("Within max_credits_per_run budget.", fg=typer.colors.GREEN)


@app.command("run")
def run_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        readable=True,
    ),
) -> None:
    """Run the scouting pipeline."""
    from regional_scout.config import load_config
    from regional_scout.pipeline import run_pipeline

    cfg = load_config(config)
    run_pipeline(cfg)


@app.command("enrich")
def enrich_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        readable=True,
    ),
    input_path: Path = typer.Option(
        Path("output/shortlist.json"),
        "--input",
        "-i",
        help="shortlist.json or author CSV (OpenAlex ID column)",
        exists=True,
        readable=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON path (default: <input>.enriched.json)",
    ),
    source_id: str | None = typer.Option(
        None,
        "--source-id",
        help="Target journal OpenAlex source ID (e.g. S4210212817)",
    ),
    years: int | None = typer.Option(
        None,
        "--years",
        help="Publication window in years (default: openalex.work_window_years; 0 = all time)",
    ),
    latest_work: bool = typer.Option(
        True,
        "--latest-work/--no-latest-work",
        help="For prospects, fetch latest work in any journal",
    ),
    export_csv_dir: Path | None = typer.Option(
        None,
        "--export-csv-dir",
        help="When input is CSV, write already_published / new_prospects CSVs here",
    ),
) -> None:
    """Check authors against a target journal (published-with-us backend)."""
    from regional_scout.config import PORTFOLIO_ISSNS, load_config, resolve_enrich_target
    from regional_scout.published_with_us.enrich import EnrichOptions, enrich_file

    cfg = load_config(config)
    if source_id:
        sid = source_id
        journal_name = sid
        for key in PORTFOLIO_ISSNS:
            if getattr(cfg.wiley_portfolio, key, None) == sid:
                from regional_scout.config import PORTFOLIO_DISPLAY_NAMES
                journal_name = PORTFOLIO_DISPLAY_NAMES.get(key, sid)
                break
    else:
        sid, journal_name = resolve_enrich_target(cfg)
        typer.echo(f"Using enrich source {journal_name} ({sid})", err=True)

    window = years if years is not None else cfg.openalex.work_window_years
    if years == 0:
        window = None

    stats = enrich_file(
        cfg,
        EnrichOptions(
            input_path=input_path,
            output_path=output,
            source_id=sid,
            journal_name=journal_name,
            year_window_years=window,
            fetch_latest_for_prospects=latest_work,
            export_csv_dir=export_csv_dir,
        ),
    )
    typer.echo(
        f"Done: {stats['published']} published, {stats['prospects']} prospects, "
        f"{stats['credits_used']} credits"
    )


@app.command("cache-clear")
def cache_clear_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml (for cache_path)",
        exists=True,
        readable=True,
    ),
) -> None:
    """Clear the OpenAlex SQLite response cache."""
    from regional_scout.cache import Cache
    from regional_scout.config import load_config

    cfg = load_config(config)
    cache = Cache(cfg.openalex.cache_path)
    cache.clear()
    cache.close()
    typer.echo(f"Cleared cache at {cfg.openalex.cache_path}")


@app.command("serve")
def serve_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml (API key loaded server-side only)",
        exists=True,
        readable=True,
    ),
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload (dev)"),
) -> None:
    """Start the local API server for the web UI."""
    import uvicorn

    from regional_scout.server.app import app, set_config_path

    set_config_path(config)
    typer.echo(f"Regional Scout API → http://{host}:{port}")
    typer.echo("Web UI: cd web && npm install && npm run dev")
    uvicorn.run(app, host=host, port=port, reload=reload)


@app.command("init-city")
def init_city_cmd(
    city: str = typer.Option(..., "--city", help="City name (e.g. Madrid)"),
    country: str = typer.Option(..., "--country", help="ISO 2-letter country code (e.g. ES)"),
    radius: float | None = typer.Option(
        None,
        "--radius",
        help="Search radius in km (overrides config radius_km). Default: value from config (30 km).",
    ),
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        readable=True,
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Update config in place (preserves comments via ruamel.yaml)",
    ),
) -> None:
    """Resolve OpenAlex institution IDs for a city."""
    from regional_scout.city import init_city

    init_city(config, city=city, country=country, write=write, radius=radius)


@app.command("init-portfolio")
def init_portfolio_cmd(
    config: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml",
        exists=True,
        readable=True,
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Update config.yaml in place (preserves comments via ruamel.yaml)",
    ),
) -> None:
    """Resolve missing Wiley AI/Comp portfolio OpenAlex source IDs from ISSNs."""
    from regional_scout.portfolio import init_portfolio

    init_portfolio(config, write=write)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

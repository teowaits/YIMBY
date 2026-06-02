"""FastAPI app for regional-scout web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from regional_scout import __version__
from regional_scout.config import (
    PORTFOLIO_DISPLAY_NAMES,
    PORTFOLIO_ISSNS,
    Config,
    load_config,
)
from regional_scout.credits import estimate_run_credits
from regional_scout.server.jobs import create_job, get_job
from regional_scout.server.runner import merge_run_overrides, start_run

app = FastAPI(title="regional-scout", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_config_path: Path = Path("config.yaml")
_base_config: Config | None = None


def set_config_path(path: Path) -> None:
    global _config_path, _base_config
    _config_path = path
    _base_config = load_config(path)


def get_base_config() -> Config:
    if _base_config is None:
        set_config_path(_config_path)
    assert _base_config is not None
    return _base_config


class RunOverrides(BaseModel):
    country_codes: list[str] | None = None
    ror_ids: list[str] | None = None
    max_candidates: int | None = None
    work_window_years: int | None = None
    max_credits_per_run: int | None = None
    shortlist_size: int | None = None
    min_in_scope_works: int | None = None
    auto_enrich: bool | None = None
    timestamp_runs: bool | None = None


class EstimateRequest(BaseModel):
    overrides: RunOverrides = Field(default_factory=RunOverrides)


class RunRequest(BaseModel):
    overrides: RunOverrides = Field(default_factory=RunOverrides)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/settings")
def settings() -> dict[str, Any]:
    cfg = get_base_config()
    y0, y1 = cfg.publication_year_range
    portfolio = []
    for key in PORTFOLIO_ISSNS:
        sid = cfg.wiley_portfolio.source_id_for_key(key)
        portfolio.append(
            {
                "key": key,
                "name": PORTFOLIO_DISPLAY_NAMES.get(key, key),
                "source_id": sid,
                "issn": PORTFOLIO_ISSNS[key],
            }
        )
    return {
        "version": __version__,
        "config_path": str(_config_path),
        "region": {
            "country_codes": cfg.region.country_codes,
            "ror_ids": cfg.region.ror_ids,
        },
        "openalex": {
            "work_window_years": cfg.openalex.work_window_years,
            "max_candidates": cfg.openalex.max_candidates,
            "max_credits_per_run": cfg.openalex.max_credits_per_run,
            "works_pages_estimate": cfg.openalex.works_pages_estimate,
        },
        "scoring": {
            "min_in_scope_works": cfg.scoring.min_in_scope_works,
            "min_cited_by_count": cfg.scoring.min_cited_by_count,
            "scope_author_prefilter": cfg.scoring.scope_author_prefilter,
            "weights": cfg.scoring.weights.model_dump(),
        },
        "output": {
            "shortlist_size": cfg.output.shortlist_size,
            "output_dir": cfg.output.output_dir,
            "timestamp_runs": cfg.output.timestamp_runs,
            "auto_enrich": cfg.output.auto_enrich,
            "enrich_source_id": cfg.output.enrich_source_id,
        },
        "publication_year_window": {"from": y0, "to": y1},
        "portfolio": portfolio,
        "has_api_key": bool(cfg.openalex.api_key and cfg.openalex.api_key != "YOUR_KEY_HERE"),
    }


@app.post("/api/estimate")
def estimate(body: EstimateRequest) -> dict[str, Any]:
    cfg = merge_run_overrides(get_base_config(), body.overrides.model_dump(exclude_none=True))
    est = estimate_run_credits(cfg)
    return {
        "total": est.total,
        "scope": est.scope,
        "candidates": est.candidates,
        "works": est.works,
        "wiley": est.wiley,
        "auto_enrich": est.auto_enrich,
        "breakdown": est.breakdown,
        "within_budget": est.total <= cfg.openalex.max_credits_per_run,
        "max_credits_per_run": cfg.openalex.max_credits_per_run,
        "message": est.format_message(),
    }


@app.post("/api/run")
def run_scout(body: RunRequest) -> dict[str, str]:
    job = create_job()
    start_run(
        _config_path,
        body.overrides.model_dump(exclude_none=True),
        job.id,
    )
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "status": job.status,
        "logs": job.logs,
        "error": job.error,
        "result": job.result,
    }


@app.get("/api/runs")
def list_runs() -> dict[str, list[dict[str, Any]]]:
    cfg = get_base_config()
    base = Path(cfg.output.output_dir)
    runs: list[dict[str, Any]] = []

    latest_path = base / "latest"
    if latest_path.is_file():
        rel = latest_path.read_text().strip()
        p = base / rel / "shortlist.json"
        if p.is_file():
            runs.append(_run_summary(rel, p))

    if base.is_dir():
        for child in sorted(base.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            sj = child / "shortlist.json"
            if sj.is_file() and not any(r["id"] == child.name for r in runs):
                runs.append(_run_summary(child.name, sj))

    flat = base / "shortlist.json"
    if flat.is_file() and not any(r["id"] == "." for r in runs):
        runs.append(_run_summary(".", flat))

    return {"runs": runs[:30]}


def _run_summary(run_id: str, path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError:
        doc = {}
    return {
        "id": run_id,
        "path": str(path.parent),
        "generated_at": doc.get("generated_at"),
        "region": doc.get("region"),
        "shortlist_count": len(doc.get("shortlist") or []),
        "credits_used": (doc.get("credits") or {}).get("used"),
    }


@app.get("/api/runs/{run_id}/shortlist")
def get_shortlist(run_id: str) -> dict[str, Any]:
    cfg = get_base_config()
    base = Path(cfg.output.output_dir)
    if run_id == ".":
        path = base / "shortlist.json"
    else:
        path = base / run_id / "shortlist.json"
    if not path.is_file():
        raise HTTPException(404, "Shortlist not found")
    return json.loads(path.read_text())


# Serve built web UI when web/dist exists (after `cd web && npm run build`)
_web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if _web_dist.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")

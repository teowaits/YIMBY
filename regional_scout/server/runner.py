"""Run pipeline in a background thread with log capture."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from regional_scout.config import Config, load_config
from regional_scout.credits import assert_within_budget, estimate_run_credits
from regional_scout.pipeline import run_pipeline
from regional_scout.server.jobs import append_log, set_status


class JobLogHandler(logging.Handler):
    def __init__(self, job_id: str) -> None:
        super().__init__()
        self.job_id = job_id

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith("regional_scout"):
            return
        msg = self.format(record)
        if msg:
            append_log(self.job_id, msg)


def merge_run_overrides(base: Config, overrides: dict[str, Any]) -> Config:
    data = base.model_dump()
    if overrides.get("country_codes") is not None:
        data["region"]["country_codes"] = overrides["country_codes"]
        if overrides.get("ror_ids") is None:
            data["region"]["ror_ids"] = []
    if overrides.get("ror_ids") is not None:
        data["region"]["ror_ids"] = overrides["ror_ids"]
    if overrides.get("max_candidates") is not None:
        data["openalex"]["max_candidates"] = overrides["max_candidates"]
    if overrides.get("work_window_years") is not None:
        data["openalex"]["work_window_years"] = overrides["work_window_years"]
    if overrides.get("max_credits_per_run") is not None:
        data["openalex"]["max_credits_per_run"] = overrides["max_credits_per_run"]
    if overrides.get("shortlist_size") is not None:
        data["output"]["shortlist_size"] = overrides["shortlist_size"]
    if overrides.get("min_in_scope_works") is not None:
        data["scoring"]["min_in_scope_works"] = overrides["min_in_scope_works"]
    if overrides.get("auto_enrich") is not None:
        data["output"]["auto_enrich"] = overrides["auto_enrich"]
    if overrides.get("timestamp_runs") is not None:
        data["output"]["timestamp_runs"] = overrides["timestamp_runs"]
    return Config.model_validate(data)


def _run_job(job_id: str, config: Config) -> None:
    handler = JobLogHandler(job_id)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("regional_scout")
    root.addHandler(handler)
    set_status(job_id, "running")
    try:
        est = estimate_run_credits(config)
        append_log(job_id, est.format_message())
        assert_within_budget(config, est)
        run_pipeline(config)
        base = Path(config.output.output_dir)
        out_dir = base
        latest_file = base / "latest"
        if latest_file.is_file():
            rel = latest_file.read_text(encoding="utf-8").strip()
            if rel:
                out_dir = base / rel
        shortlist_path = out_dir / "shortlist.json"
        doc: dict[str, Any] = {}
        if shortlist_path.is_file():
            doc = json.loads(shortlist_path.read_text())
        set_status(
            job_id,
            "done",
            result={
                "output_dir": str(out_dir),
                "shortlist_path": str(shortlist_path),
                "shortlist": doc,
            },
        )
    except SystemExit as e:
        set_status(job_id, "error", error=str(e) or "Pipeline aborted")
    except Exception as e:
        set_status(job_id, "error", error=str(e))
    finally:
        root.removeHandler(handler)


def start_run(config_path: Path, overrides: dict[str, Any], job_id: str) -> None:
    base = load_config(config_path)
    cfg = merge_run_overrides(base, overrides)

    def target() -> None:
        _run_job(job_id, cfg)

    threading.Thread(target=target, daemon=True).start()

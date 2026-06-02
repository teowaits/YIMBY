"""Pydantic config loading and validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

FilterType = Literal["ror", "institution", "country"]

# ISSN → config key for init-portfolio
PORTFOLIO_ISSNS: dict[str, str] = {
    "advanced_science": "2198-3844",
    "advanced_intelligent_systems": "2640-4567",
    "advanced_intelligent_discovery": "2943-9981",
    "advanced_robotics_research": "2943-9973",
    "advanced_theory_simulations": "2513-0390",
    "advanced_computing": "3054-100X",
}

PORTFOLIO_DISPLAY_NAMES: dict[str, str] = {
    "advanced_science": "Advanced Science",
    "advanced_intelligent_systems": "Advanced Intelligent Systems",
    "advanced_intelligent_discovery": "Advanced Intelligent Discovery",
    "advanced_robotics_research": "Advanced Robotics Research",
    "advanced_theory_simulations": "Advanced Theory and Simulations",
    "advanced_computing": "Advanced Computing",
}


class OpenAlexConfig(BaseModel):
    api_key: str
    max_credits_per_run: int = 50_000
    work_window_years: int = 5
    max_candidates: int = 200
    works_pages_estimate: int = 3
    cache_path: str = ".cache/regional-scout/openalex.db"

    @field_validator("api_key")
    @classmethod
    def api_key_not_placeholder(cls, v: str) -> str:
        if not v or v == "YOUR_KEY_HERE":
            raise ValueError(
                "openalex.api_key must be set (get a free key at https://openalex.org/settings/api)"
            )
        return v


class CityRegion(BaseModel):
    name: str | None = None
    country_code: str | None = None
    institution_ids: list[str] = Field(default_factory=list)


class RegionConfig(BaseModel):
    country_codes: list[str] = Field(default_factory=list)
    city: CityRegion = Field(default_factory=CityRegion)
    ror_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_region(self) -> RegionConfig:
        has_ror = bool(self.ror_ids)
        has_city = bool(self.city.institution_ids)
        has_country = bool(self.country_codes)
        if not (has_ror or has_city or has_country):
            raise ValueError(
                "region: at least one of ror_ids, city.institution_ids, "
                "or country_codes must be non-empty"
            )
        return self


def normalize_institution_id(inst_id: str) -> str:
    """OpenAlex institution ID to short I… form."""
    r = inst_id.strip()
    if r.startswith("https://openalex.org/"):
        return r.rsplit("/", 1)[-1]
    return r


def active_filter(region: RegionConfig) -> tuple[FilterType, list[str]]:
    """Returns (filter_type, ids) — priority: ror > institution > country."""
    if region.ror_ids:
        return ("ror", list(region.ror_ids))
    if region.city.institution_ids:
        return (
            "institution",
            [normalize_institution_id(i) for i in region.city.institution_ids],
        )
    return ("country", [c.lower() for c in region.country_codes])


def region_filter_metadata(region: RegionConfig) -> dict[str, Any]:
    filter_type, ids = active_filter(region)
    meta: dict[str, Any] = {
        "type": filter_type,
        "city": region.city.name,
        "country_code": region.city.country_code,
        "institution_count": len(ids) if filter_type == "institution" else None,
        "values": ids,
    }
    if filter_type == "country":
        meta["country_code"] = meta["country_code"] or (
            ids[0] if len(ids) == 1 else None
        )
    return meta


def log_active_filter_warnings(region: RegionConfig, filter_type: FilterType) -> None:
    if filter_type == "ror":
        if region.city.institution_ids or region.country_codes:
            logger.warning(
                "Using ror_ids; city.institution_ids and country_codes ignored."
            )
    elif filter_type == "institution":
        if region.country_codes:
            logger.warning(
                "Using city.institution_ids (%d); country_codes ignored.",
                len(region.city.institution_ids),
            )


class ScoringWeights(BaseModel):
    relevance: float = 0.35
    productivity: float = 0.20
    impact: float = 0.25
    centrality: float = 0.15
    wiley: float = 0.0

    @model_validator(mode="after")
    def weights_non_negative(self) -> ScoringWeights:
        for name in ("relevance", "productivity", "impact", "centrality", "wiley"):
            if getattr(self, name) < 0:
                raise ValueError(f"scoring.weights.{name} must be >= 0")
        return self


class ScoringConfig(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    career_stage_boost: bool = False
    career_stage_boost_multiplier: float = 1.15
    min_cited_by_count: int = 5
    min_in_scope_works: int = 1
    scope_author_prefilter: bool = True


class CompetitorJournal(BaseModel):
    issn: str


class ScopeConfig(BaseModel):
    seed_dois: list[str] = Field(default_factory=list)
    competitor_journals: list[CompetitorJournal] = Field(default_factory=list)
    additional_topic_ids: list[str] = Field(default_factory=list)


class WileyPortfolioConfig(BaseModel):
    always_check: bool = False
    advanced_science: str | None = None
    advanced_intelligent_systems: str | None = "S4210212817"
    advanced_intelligent_discovery: str | None = "S5407036554"
    advanced_robotics_research: str | None = None
    advanced_theory_simulations: str | None = None
    advanced_computing: str | None = None

    def portfolio_source_ids(self) -> list[str]:
        ids: list[str] = []
        for key in PORTFOLIO_ISSNS:
            val = getattr(self, key)
            if val:
                ids.append(val)
        return ids

    def should_check_wiley(self, wiley_weight: float) -> bool:
        return self.always_check or wiley_weight > 0

    def source_id_for_key(self, key: str) -> str | None:
        return getattr(self, key, None)


class OutputConfig(BaseModel):
    shortlist_size: int = 10
    output_dir: str = "./output"
    timestamp_runs: bool = False
    auto_enrich: bool = False
    enrich_source_id: str | None = None
    enrich_latest_work: bool = True
    include_works_in_json: bool = True
    max_works_per_author: int = 5


class Config(BaseModel):
    openalex: OpenAlexConfig
    region: RegionConfig
    scoring: ScoringConfig
    scope: ScopeConfig
    wiley_portfolio: WileyPortfolioConfig
    output: OutputConfig

    @property
    def publication_year_range(self) -> tuple[int, int]:
        from datetime import date

        end = date.today().year
        start = end - self.openalex.work_window_years + 1
        return (start, end)

    def region_filter(self) -> tuple[str, str]:
        """Return (filter_field, filter_value) for OpenAlex /authors endpoint."""
        filter_type, ids = active_filter(self.region)
        log_active_filter_warnings(self.region, filter_type)

        if filter_type == "ror":
            value = "|".join(self._normalize_ror(r) for r in ids)
            return ("last_known_institutions.id", value)
        if filter_type == "institution":
            value = "|".join(ids)
            return ("last_known_institutions.id", value)

        logger.info(
            "Filtering by country_code. Note: last_known_institutions is an array "
            "in OpenAlex — results may include authors with secondary affiliations "
            "in %s. For tighter results use city.institution_ids.",
            ids,
        )
        return ("last_known_institutions.country_code", "|".join(ids))

    @staticmethod
    def _normalize_ror(ror: str) -> str:
        r = ror.strip()
        if r.startswith("https://ror.org/"):
            return r
        if r.startswith("ror.org/"):
            return f"https://{r}"
        return f"https://ror.org/{r}"


def resolve_enrich_target(config: Config) -> tuple[str, str]:
    """Return (source_id, journal_display_name) for enrich / auto_enrich."""
    sid = config.output.enrich_source_id
    if sid:
        for key, val in PORTFOLIO_ISSNS.items():
            if config.wiley_portfolio.source_id_for_key(key) == sid:
                return sid, PORTFOLIO_DISPLAY_NAMES.get(key, sid)
        return sid, sid

    for key in PORTFOLIO_ISSNS:
        val = config.wiley_portfolio.source_id_for_key(key)
        if val:
            return val, PORTFOLIO_DISPLAY_NAMES.get(key, val)

    raise ValueError(
        "No enrich source: set output.enrich_source_id or populate wiley_portfolio "
        "(run init-portfolio)"
    )


def load_config(path: Path | str) -> Config:
    p = Path(path)
    with p.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return Config.model_validate(data)


def region_summary_label(region: RegionConfig) -> str:
    """Human-readable region label for logs and API responses."""
    filter_type, ids = active_filter(region)
    if filter_type == "ror":
        return f"ROR ({len(ids)} institutions)"
    if filter_type == "institution":
        city = region.city.name or "city"
        cc = region.city.country_code or "?"
        return f"City ({city}, {cc}) — {len(ids)} institutions"
    return f"Country ({','.join(ids)})"

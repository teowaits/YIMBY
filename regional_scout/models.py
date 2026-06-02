"""Data models for regional-scout."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScopeVector:
    topic_ids: frozenset[str]
    source_ids: frozenset[str]


@dataclass
class AuthorRecord:
    openalex_id: str
    display_name: str
    institution_name: str | None
    country_code: str | None
    cited_by_count: int
    works_count: int
    first_publication_year: int | None = None


@dataclass
class WorkRecord:
    openalex_id: str
    title: str
    publication_year: int
    primary_topic_id: str | None
    primary_source_id: str | None
    fwci: float | None
    coauthor_ids: list[str] = field(default_factory=list)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "openalex_id": self.openalex_id,
            "title": self.title,
            "publication_year": self.publication_year,
            "primary_topic_id": self.primary_topic_id,
            "primary_source_id": self.primary_source_id,
            "fwci": round(self.fwci, 4) if self.fwci is not None else None,
        }


@dataclass
class RawScoreComponents:
    openalex_id: str
    relevance: float
    productivity: float
    impact: float
    centrality: float
    wiley_flag: float
    career_boost_multiplier: float = 1.0


@dataclass
class ScoreBreakdown:
    relevance: float
    productivity: float
    impact: float
    centrality: float
    wiley: float
    composite: float
    raw_relevance: float
    raw_productivity: float
    raw_impact: float
    raw_centrality: float


@dataclass
class ScoredAuthor:
    author: AuthorRecord
    breakdown: ScoreBreakdown
    wiley_friendly: bool
    wiley_journal: str | None
    in_scope_work_count: int
    mean_fwci: float | None


@dataclass
class ShortlistEntry:
    rank: int
    openalex_id: str
    display_name: str
    institution_name: str | None
    country_code: str | None
    composite_score: float
    breakdown: ScoreBreakdown
    wiley_friendly: bool
    wiley_journal: str | None
    in_scope_work_count: int
    mean_fwci: float | None
    cited_by_count: int
    in_scope_works: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        b = self.breakdown
        out: dict[str, Any] = {
            "rank": self.rank,
            "openalex_id": self.openalex_id,
            "display_name": self.display_name,
            "institution_name": self.institution_name,
            "country_code": self.country_code,
            "composite_score": round(self.composite_score, 6),
            "score_breakdown": {
                "relevance": round(b.relevance, 6),
                "productivity": round(b.productivity, 6),
                "impact": round(b.impact, 6),
                "centrality": round(b.centrality, 6),
                "wiley": round(b.wiley, 6),
            },
            "raw_components": {
                "relevance": round(b.raw_relevance, 6),
                "productivity": round(b.raw_productivity, 6),
                "impact": round(b.raw_impact, 6),
                "centrality": round(b.raw_centrality, 6),
            },
            "wiley_friendly": self.wiley_friendly,
            "wiley_journal": self.wiley_journal,
            "in_scope_work_count": self.in_scope_work_count,
            "mean_fwci": round(self.mean_fwci, 4) if self.mean_fwci is not None else None,
            "cited_by_count": self.cited_by_count,
        }
        if self.in_scope_works:
            out["in_scope_works"] = self.in_scope_works
        return out


@dataclass
class RunMetadata:
    region_label: str
    topic_count: int
    candidate_count: int
    eligible_count: int
    excluded_in_scope_count: int
    credits_estimated: int
    credits_used: int
    cache_hits: int
    api_calls: int
    publication_year_from: int
    publication_year_to: int
    output_dir: str
    scope_summary: dict[str, Any]
    region_filter: dict[str, Any] = field(default_factory=dict)

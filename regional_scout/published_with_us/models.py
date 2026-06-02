"""Models for published-with-us enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkSample:
    openalex_id: str
    title: str
    publication_year: int | None
    doi: str | None
    source_display_name: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "openalex_id": self.openalex_id,
            "title": self.title,
            "publication_year": self.publication_year,
            "doi": self.doi,
            "source_display_name": self.source_display_name,
        }


@dataclass
class AuthorPublishResult:
    openalex_id: str
    published: bool
    publication_count: int
    sample_work: WorkSample | None = None
    latest_work: WorkSample | None = None
    display_name: str | None = None
    source_row: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "openalex_id": self.openalex_id,
            "published": self.published,
            "publication_count": self.publication_count,
            "sample_work": self.sample_work.to_dict() if self.sample_work else None,
            "latest_work": self.latest_work.to_dict() if self.latest_work else None,
        }

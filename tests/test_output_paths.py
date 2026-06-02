"""Tests for output path resolution."""

from regional_scout.config import (
    Config,
    OpenAlexConfig,
    OutputConfig,
    RegionConfig,
    ScoringConfig,
    ScopeConfig,
    WileyPortfolioConfig,
)
from regional_scout.output.paths import resolve_run_output_dir


def _config(**output_kw) -> Config:
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(country_codes=["it"]),
        scoring=ScoringConfig(),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(),
        output=OutputConfig(**output_kw),
    )


def test_flat_output_dir():
    p = resolve_run_output_dir(_config(output_dir="./output"))
    assert p.name == "output"


def test_timestamp_subdir():
    p = resolve_run_output_dir(_config(output_dir="./output", timestamp_runs=True))
    assert p.parent.name == "output"
    assert len(p.name) == 17  # YYYY-MM-DD_HHMMSS

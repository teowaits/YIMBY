"""Credit estimation tests."""

from regional_scout.config import (
    Config,
    OpenAlexConfig,
    OutputConfig,
    RegionConfig,
    ScoringConfig,
    ScopeConfig,
    WileyPortfolioConfig,
)
from regional_scout.credits import estimate_run_credits, should_check_wiley


def _config(**kwargs) -> Config:
    scoring_kw = kwargs.pop("scoring", {})
    wp_kw = kwargs.pop("wiley_portfolio", {})
    output_kw = kwargs.pop("output", {})
    return Config(
        openalex=OpenAlexConfig(api_key="test-key-12345678"),
        region=RegionConfig(country_codes=["it"]),
        scoring=ScoringConfig(**scoring_kw),
        scope=ScopeConfig(),
        wiley_portfolio=WileyPortfolioConfig(**wp_kw),
        output=OutputConfig(**output_kw),
    )


def test_wiley_credits_only_when_enabled():
    configured = _config()
    assert should_check_wiley(configured) is True
    assert estimate_run_credits(configured).wiley > 0

    empty = _config(
        wiley_portfolio={
            "advanced_intelligent_systems": None,
            "advanced_intelligent_discovery": None,
        }
    )
    assert should_check_wiley(empty) is False
    assert estimate_run_credits(empty).wiley == 0

    from regional_scout.config import ScoringWeights

    weight = _config(
        scoring={"weights": ScoringWeights(wiley=0.1)},
        wiley_portfolio={
            "advanced_intelligent_systems": None,
            "advanced_intelligent_discovery": None,
        },
    )
    assert should_check_wiley(weight) is True
    assert estimate_run_credits(weight).wiley > 0

    always = _config(
        wiley_portfolio={
            "always_check": True,
            "advanced_intelligent_systems": None,
            "advanced_intelligent_discovery": None,
        }
    )
    assert should_check_wiley(always) is True
    assert estimate_run_credits(always).wiley > 0


def test_auto_enrich_in_estimate():
    cfg = _config(output={"auto_enrich": True, "shortlist_size": 10})
    est = estimate_run_credits(cfg)
    assert est.auto_enrich > 0

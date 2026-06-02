"""API server tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from regional_scout.config import load_config
from regional_scout.server.app import app, set_config_path
from regional_scout.server.runner import merge_run_overrides


@pytest.fixture
def client(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
openalex:
  api_key: "test-key-12345678"
  max_credits_per_run: 50000
  work_window_years: 5
  max_candidates: 50
region:
  country_codes: ["it"]
scoring: {}
scope: {}
wiley_portfolio:
  advanced_intelligent_systems: "S4210212817"
output:
  output_dir: "./output"
""",
        encoding="utf-8",
    )
    set_config_path(cfg)
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_no_api_key(client: TestClient):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["has_api_key"] is True
    assert "openalex" not in data or "api_key" not in data.get("openalex", {})


def test_estimate(client: TestClient):
    r = client.post("/api/estimate", json={"overrides": {"max_candidates": 20}})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert "within_budget" in body


def test_merge_overrides(tmp_path: Path):
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        """
openalex:
  api_key: "test-key-12345678"
region:
  country_codes: ["it"]
scoring: {}
scope: {}
wiley_portfolio: {}
output: {}
""",
        encoding="utf-8",
    )
    base = load_config(cfg_path)
    merged = merge_run_overrides(base, {"country_codes": ["de"], "max_candidates": 10})
    assert merged.region.country_codes == ["de"]
    assert merged.openalex.max_candidates == 10

"""OpenAlex API client — all HTTP goes through cache."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from regional_scout.cache import Cache
from regional_scout.config import Config
from regional_scout.logging_config import redact_secrets

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"
LIST_CREDITS = 10
SINGLETON_CREDITS = 1
MAX_FILTER_IDS = 50
MAX_RETRIES = 5
BACKOFF_BASE = 1.0
BACKOFF_CAP = 60.0


class CreditCounter:
    def __init__(self) -> None:
        self.used = 0
        self.cache_hits = 0
        self.api_calls = 0

    def add_list(self, n: int = 1) -> None:
        self.used += LIST_CREDITS * n
        self.api_calls += n

    def add_singleton(self, n: int = 1) -> None:
        self.used += SINGLETON_CREDITS * n
        self.api_calls += n

    def record_cache_hit(self) -> None:
        self.cache_hits += 1


class OpenAlexClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.credits = CreditCounter()
        self.cache = Cache(config.openalex.cache_path)
        self._client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        self._client.close()
        self.cache.close()

    def build_url(self, endpoint: str, params: dict[str, str] | None = None) -> str:
        ep = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        q: dict[str, str] = dict(params or {})
        q["api_key"] = self.config.openalex.api_key
        return f"{BASE_URL}{ep}?{urlencode(q)}"

    def _get_json(self, url: str, *, is_list: bool) -> dict[str, Any]:
        cached = self.cache.get(url)
        if cached is not None:
            self.credits.record_cache_hit()
            return cached

        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.get(url)
                if resp.status_code == 429:
                    wait = min(BACKOFF_BASE * (2**attempt), BACKOFF_CAP)
                    logger.warning("OpenAlex 429; backing off %.1fs", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                self.cache.set(url, data)
                if is_list:
                    self.credits.add_list()
                else:
                    self.credits.add_singleton()
                return data
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code == 429:
                    continue
                raise
            except httpx.HTTPError as e:
                last_err = e
                wait = min(BACKOFF_BASE * (2**attempt), BACKOFF_CAP)
                time.sleep(wait)

        safe = redact_secrets(url, self.config.openalex.api_key)
        raise RuntimeError(f"OpenAlex request failed after retries: {safe}") from last_err

    def fetch_page(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        url = self.build_url(endpoint, params)
        return self._get_json(url, is_list=True)

    def fetch_singleton(self, endpoint: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = self.build_url(endpoint, params)
        return self._get_json(url, is_list=False)

    def fetch_list(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate via meta.next_cursor until exhausted."""
        q = dict(params)
        q.setdefault("per-page", "200")
        q["cursor"] = "*"
        results: list[dict[str, Any]] = []
        pages = 0

        while True:
            data = self.fetch_page(endpoint, q)
            batch = data.get("results") or []
            results.extend(batch)
            pages += 1
            if max_pages is not None and pages >= max_pages:
                break
            next_cursor = (data.get("meta") or {}).get("next_cursor")
            if not next_cursor:
                break
            q = dict(params)
            q["per-page"] = q.get("per-page", "200")
            q["cursor"] = next_cursor

        return results

    def fetch_list_batched_filters(
        self,
        endpoint: str,
        base_params: dict[str, str],
        filter_key: str,
        ids: list[str],
        *,
        max_pages_per_batch: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run list fetches with OR-batched filter values."""
        if not ids:
            return []
        all_results: list[dict[str, Any]] = []
        for i in range(0, len(ids), MAX_FILTER_IDS):
            chunk = ids[i : i + MAX_FILTER_IDS]
            filt = base_params.get("filter", "")
            chunk_filter = f"{filter_key}:{'|'.join(chunk)}"
            if filt:
                chunk_filter = f"{filt},{chunk_filter}"
            params = {**base_params, "filter": chunk_filter}
            all_results.extend(
                self.fetch_list(endpoint, params, max_pages=max_pages_per_batch)
            )
        return all_results


def openalex_id(raw: str) -> str:
    """Normalize OpenAlex ID to short form A123."""
    if raw.startswith("https://openalex.org/"):
        return raw.rsplit("/", 1)[-1]
    return raw

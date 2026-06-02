"""Tests for credit counter cache tracking."""

from regional_scout.openalex import CreditCounter, LIST_CREDITS


def test_credit_counter_tracks_cache_and_api():
    c = CreditCounter()
    c.record_cache_hit()
    c.record_cache_hit()
    c.add_list(2)
    assert c.cache_hits == 2
    assert c.api_calls == 2
    assert c.used == 2 * LIST_CREDITS

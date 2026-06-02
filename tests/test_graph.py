"""Unit tests for graph.py."""

from __future__ import annotations

import networkx as nx

from regional_scout.graph import (
    MIN_GRAPH_SIZE,
    SMALL_POOL_CENTRALITY,
    build_coauthor_graph,
    compute_centrality,
)
from regional_scout.models import AuthorRecord, WorkRecord


def _authors(n: int) -> list[AuthorRecord]:
    return [
        AuthorRecord(f"A{i}", f"Name {i}", None, "it", 10, 5)
        for i in range(1, n + 1)
    ]


def test_small_pool_gets_flat_centrality():
    candidates = _authors(3)
    works_map = {
        "A1": [
            WorkRecord("W1", "t", 2024, "T1", None, 1.0, ["A1", "A2"]),
        ],
        "A2": [],
        "A3": [],
    }
    g = build_coauthor_graph(candidates, works_map)
    cent = compute_centrality(g)
    assert len(cent) == 3
    assert all(v == SMALL_POOL_CENTRALITY for v in cent.values())


def test_weighted_edge_from_shared_works():
    candidates = _authors(5)
    works_map = {
        "A1": [
            WorkRecord("W1", "t", 2024, "T1", None, 1.0, ["A1", "A2"]),
            WorkRecord("W2", "t2", 2024, "T1", None, 1.0, ["A1", "A2"]),
        ],
        "A2": [],
        "A3": [],
        "A4": [],
        "A5": [],
    }
    g = build_coauthor_graph(candidates, works_map)
    assert g["A1"]["A2"]["weight"] == 2


def test_disconnected_fallback_to_degree():
    candidates = _authors(MIN_GRAPH_SIZE)
    works_map = {f"A{i}": [] for i in range(1, MIN_GRAPH_SIZE + 1)}
    works_map["A1"] = [
        WorkRecord("W1", "t", 2024, "T1", None, 1.0, ["A1", "A2"]),
    ]
    works_map["A4"] = [
        WorkRecord("W2", "t", 2024, "T1", None, 1.0, ["A4", "A5"]),
    ]
    g = build_coauthor_graph(candidates, works_map)
    cent = compute_centrality(g)
    assert len(cent) == MIN_GRAPH_SIZE
    assert all(0 <= v <= 1 for v in cent.values())

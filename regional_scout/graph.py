"""Co-author graph and centrality — pure functions, no I/O."""

from __future__ import annotations

import logging
from itertools import combinations

import networkx as nx

from regional_scout.models import AuthorRecord, WorkRecord

logger = logging.getLogger(__name__)

MIN_GRAPH_SIZE = 5
SMALL_POOL_CENTRALITY = 0.5


def build_coauthor_graph(
    candidates: list[AuthorRecord],
    works_map: dict[str, list[WorkRecord]],
    *,
    candidate_ids: frozenset[str] | None = None,
) -> nx.Graph:
    """
    Weighted edges: count of shared in-scope works between regional candidates.
    """
    pool = candidate_ids or frozenset(a.openalex_id for a in candidates)
    g: nx.Graph = nx.Graph()
    for aid in pool:
        g.add_node(aid)

    for works in works_map.values():
        for work in works:
            present = [c for c in work.coauthor_ids if c in pool]
            for a, b in combinations(sorted(set(present)), 2):
                if g.has_edge(a, b):
                    g[a][b]["weight"] += 1
                else:
                    g.add_edge(a, b, weight=1)

    return g


def compute_centrality(g: nx.Graph) -> dict[str, float]:
    nodes = list(g.nodes())
    if not nodes:
        return {}
    if len(nodes) < MIN_GRAPH_SIZE:
        logger.warning(
            "Co-author graph has <%d nodes; assigning centrality %.2f to all",
            MIN_GRAPH_SIZE,
            SMALL_POOL_CENTRALITY,
        )
        return {n: SMALL_POOL_CENTRALITY for n in nodes}

    try:
        try:
            cent = nx.eigenvector_centrality_numpy(g, weight="weight")
        except ModuleNotFoundError:
            cent = nx.eigenvector_centrality(g, weight="weight", max_iter=500, tol=1e-6)
        return {str(k): float(v) for k, v in cent.items()}
    except (nx.AmbiguousSolution, nx.PowerIterationFailedConvergence) as e:
        logger.warning("Eigenvector centrality failed (%s); using degree centrality", e)
    except nx.NetworkXError as e:
        logger.warning("Eigenvector centrality failed (%s); using degree centrality", e)

    try:
        deg = nx.degree_centrality(g)
        return {str(k): float(v) for k, v in deg.items()}
    except nx.NetworkXError:
        logger.warning("Degree centrality failed; assigning %.2f to all", SMALL_POOL_CENTRALITY)
        return {n: SMALL_POOL_CENTRALITY for n in nodes}

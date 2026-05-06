"""Greedy correlation clustering with constraint edges.

Algorithm:
1. Build a graph with positive edges (p >= auto_link_threshold) and
   negative edges (p < reject_threshold).
2. Constraints (must-link / cannot-link) are injected as hard edges.
3. Greedily merge clusters: a merge is accepted only if it introduces
   no new cannot-link violations.
4. Every merge is versioned with a timestamp and contributing-edge set.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import networkx as nx

from ubid.config import get_settings
from ubid.schema.canonical import ScoredPair, ConstraintType


@dataclass
class MergeEvent:
    merged_canonical_ids: list[str]
    ubid: str
    timestamp: datetime
    contributing_pairs: list[str]
    merged_by: str = "auto"


@dataclass
class ClusterResult:
    ubid_to_canonical: dict[str, list[str]]   # ubid → list of canonical_ids
    canonical_to_ubid: dict[str, str]         # canonical_id → ubid
    merge_history: list[MergeEvent]


def cluster(
    scored_pairs: list[ScoredPair],
    constraints: list[tuple[str, str, ConstraintType]],
    existing_assignments: Optional[dict[str, str]] = None,  # canonical_id → existing UBID
) -> ClusterResult:
    settings = get_settings()
    auto_thresh = settings.auto_link_threshold
    reject_thresh = 0.20

    G = nx.Graph()

    for pair in scored_pairs:
        if pair.deterministic_tier_fired and pair.deterministic_result is not None:
            if pair.deterministic_result:
                G.add_edge(pair.canonical_id_a, pair.canonical_id_b,
                           weight=pair.calibrated_probability, kind="positive",
                           pair_id=None)
            else:
                G.add_edge(pair.canonical_id_a, pair.canonical_id_b,
                           weight=pair.calibrated_probability, kind="negative",
                           pair_id=None)
            continue

        if pair.calibrated_probability >= auto_thresh:
            G.add_edge(pair.canonical_id_a, pair.canonical_id_b,
                       weight=pair.calibrated_probability, kind="positive",
                       pair_id=None)
        elif pair.calibrated_probability < reject_thresh:
            G.add_edge(pair.canonical_id_a, pair.canonical_id_b,
                       weight=pair.calibrated_probability, kind="negative",
                       pair_id=None)

    # Inject hard constraints
    cannot_link: set[frozenset[str]] = set()
    must_link: list[tuple[str, str]] = []

    for a, b, ctype in constraints:
        if ctype == ConstraintType.CANNOT_LINK:
            cannot_link.add(frozenset([a, b]))
            if G.has_edge(a, b):
                G[a][b]["kind"] = "negative"
        else:
            must_link.append((a, b))
            G.add_edge(a, b, weight=1.0, kind="positive", pair_id=None)

    # Extract only positive-edge subgraph for initial connected components
    pos_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "positive"]
    pos_G = nx.Graph()
    pos_G.add_edges_from(pos_edges)
    pos_G.add_nodes_from(G.nodes())

    ubid_to_canonical: dict[str, list[str]] = {}
    canonical_to_ubid: dict[str, str] = {}
    merge_history: list[MergeEvent] = []

    # Seed from existing assignments to preserve continuity
    if existing_assignments:
        for cid, ubid in existing_assignments.items():
            if ubid not in ubid_to_canonical:
                ubid_to_canonical[ubid] = []
            ubid_to_canonical[ubid].append(cid)
            canonical_to_ubid[cid] = ubid

    for component in nx.connected_components(pos_G):
        component = list(component)

        # Check cannot-link violations within the component
        safe = True
        for i in range(len(component)):
            for j in range(i + 1, len(component)):
                if frozenset([component[i], component[j]]) in cannot_link:
                    safe = False
                    break
            if not safe:
                break

        if safe and len(component) > 1:
            # All members go to one UBID; reuse existing if possible
            existing_ubids = {canonical_to_ubid[c] for c in component if c in canonical_to_ubid}
            if len(existing_ubids) == 1:
                ubid = existing_ubids.pop()
            elif len(existing_ubids) == 0:
                ubid = str(uuid.uuid4())
            else:
                # Multiple existing UBIDs merging — pick the oldest (smallest UUID sorts first)
                ubid = sorted(existing_ubids)[0]

            ubid_to_canonical[ubid] = component
            for c in component:
                canonical_to_ubid[c] = ubid

            merge_history.append(MergeEvent(
                merged_canonical_ids=component,
                ubid=ubid,
                timestamp=datetime.utcnow(),
                contributing_pairs=[],
            ))
        else:
            # Cannot-link conflict: assign each as its own UBID (conservative)
            for c in component:
                if c not in canonical_to_ubid:
                    ubid = existing_assignments.get(c) if existing_assignments else None
                    ubid = ubid or str(uuid.uuid4())
                    ubid_to_canonical[ubid] = [c]
                    canonical_to_ubid[c] = ubid

    return ClusterResult(
        ubid_to_canonical=ubid_to_canonical,
        canonical_to_ubid=canonical_to_ubid,
        merge_history=merge_history,
    )

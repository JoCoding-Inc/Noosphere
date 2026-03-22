# backend/simulation/graph_utils.py
from __future__ import annotations
from collections import defaultdict, deque


def sanitize_neighbor_titles(neighbor_titles: list[str] | None) -> list[str]:
    """Sanitize and cap neighbor title list for LLM prompt injection."""
    sanitized: list[str] = []
    for raw_title in neighbor_titles or []:
        title = str(raw_title).replace("\n", " ").replace("\r", " ").strip()
        if title:
            sanitized.append(title[:120])
    return sanitized[:5]


def build_adjacency(edges: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """Build bidirectional adjacency map sorted by weight desc."""
    adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
    deduped_edges: dict[tuple[str, str], float] = {}
    for e in edges:
        src, tgt, w = e.get("source", ""), e.get("target", ""), float(e.get("weight", 0.0))
        if not src or not tgt or src == tgt:
            continue
        edge_key = tuple(sorted((src, tgt)))
        deduped_edges[edge_key] = max(w, deduped_edges.get(edge_key, float("-inf")))
    for (src, tgt), weight in deduped_edges.items():
        adj[src].append((tgt, weight))
        adj[tgt].append((src, weight))
    return {k: sorted(v, key=lambda x: -x[1]) for k, v in adj.items()}


def get_neighbor_titles(
    node_id: str,
    adjacency: dict[str, list[tuple[str, float]]],
    id_to_node: dict[str, dict],
    top_k: int = 5,
) -> list[str]:
    """Return titles of top-k weighted neighbors for a node."""
    neighbors = adjacency.get(node_id, [])[:top_k]
    return [id_to_node[nid]["title"] for nid, _ in neighbors if nid in id_to_node]


def degree_centrality(
    adjacency: dict[str, list[tuple[str, float]]],
    all_node_ids: list[str] | None = None,
) -> dict[str, int]:
    """Return degree (number of edges) per node."""
    centrality = {node_id: len(neighbors) for node_id, neighbors in adjacency.items()}
    if all_node_ids:
        for node_id in all_node_ids:
            centrality.setdefault(node_id, 0)
    return centrality


def connected_components(
    adjacency: dict[str, list[tuple[str, float]]],
    all_node_ids: list[str],
) -> list[list[str]]:
    """BFS over all nodes; returns list of components."""
    visited: set[str] = set()
    components: list[list[str]] = []
    ordered_node_ids = list(dict.fromkeys(all_node_ids))
    for node_id, neighbors in adjacency.items():
        if node_id not in ordered_node_ids:
            ordered_node_ids.append(node_id)
        for neighbor, _ in neighbors:
            if neighbor not in ordered_node_ids:
                ordered_node_ids.append(neighbor)
    for start in ordered_node_ids:
        if start in visited:
            continue
        component: list[str] = []
        queue: deque[str] = deque([start])
        visited.add(start)
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbor, _ in adjacency.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def build_clusters(
    adjacency: dict[str, list[tuple[str, float]]],
    all_node_ids: list[str],
    id_to_node: dict[str, dict],
) -> list[dict]:
    """Build clusters from connected components of the keyword graph.

    Returns list of cluster dicts sorted by size desc.
    Each cluster: {"id": str, "nodes": list[dict], "representative": dict}
    The representative is the node with the highest degree in the cluster.
    """
    components = connected_components(adjacency, all_node_ids)
    deg = degree_centrality(adjacency, all_node_ids)

    clusters: list[dict] = []
    for i, comp in enumerate(sorted(components, key=lambda c: -len(c))):
        nodes = [id_to_node[nid] for nid in comp if nid in id_to_node]
        if not nodes:
            continue
        representative = max(nodes, key=lambda n: deg.get(n.get("id", ""), 0))
        clusters.append({
            "id": f"cluster_{i}",
            "nodes": nodes,
            "representative": representative,
        })
    return clusters


def summarize_graph(
    edges: list[dict],
    id_to_node: dict[str, dict],
    top_n_hubs: int = 5,
    top_n_clusters: int = 4,
) -> str:
    """Return a compact plain-text graph summary for LLM prompt injection."""
    if not edges:
        return ""
    adj = build_adjacency(edges)
    all_ids = list(id_to_node.keys())
    deg = degree_centrality(adj, all_ids)
    components = connected_components(adj, all_ids)

    hubs = sorted(
        ((node_id, degree) for node_id, degree in deg.items() if degree > 0),
        key=lambda x: -x[1],
    )[:top_n_hubs]
    hub_lines = ", ".join(
        f"{id_to_node.get(nid, {}).get('title', nid)} ({d} connections)"
        for nid, d in hubs
    )

    sorted_comps = sorted(components, key=lambda c: -len(c))[:top_n_clusters]
    cluster_lines: list[str] = []
    for i, comp in enumerate(sorted_comps, 1):
        titles = [id_to_node.get(nid, {}).get("title", nid) for nid in comp[:4]]
        suffix = f"... (+{len(comp) - 4} more)" if len(comp) > 4 else ""
        cluster_lines.append(f"  Cluster {i} ({len(comp)} nodes): {', '.join(titles)}{suffix}")

    isolated = [nid for nid in all_ids if nid not in adj]
    isolated_titles = [id_to_node.get(nid, {}).get("title", nid) for nid in isolated[:5]]

    parts = [f"Top hub nodes: {hub_lines}"]
    if cluster_lines:
        parts.append("Technology clusters:\n" + "\n".join(cluster_lines))
    if isolated_titles:
        parts.append(f"Isolated nodes (potential blue ocean): {', '.join(isolated_titles)}")
    return "\n".join(parts)

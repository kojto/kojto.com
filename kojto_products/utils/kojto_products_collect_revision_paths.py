from odoo.exceptions import ValidationError

def collect_revision_paths(start_revision_id, edges, revision_map, env):
    """
    Collect all paths from the start revision with cumulative quantities for bottom-up analysis.

    Args:
        start_revision_id: ID of the starting revision.
        edges: List of tuples (src_id, dst_id) from resolve_graph.
        revision_map: Dict mapping revision IDs to kojto.product.component.revision records.
        env: Odoo environment for querying links.

    Returns:
        Tuple of (paths, quantities, link_quantities) where:
            - paths: Dict mapping revision IDs to lists of paths (each path is a list of (name, quantity)).
            - quantities: Dict mapping revision IDs to total quantities (sum of last path quantities).
            - link_quantities: Dict mapping (src_id, dst_id) to link quantities.
    """
    graph = {}
    link_quantities = {}
    link_cache = {}
    for src_id, dst_id in edges:
        graph.setdefault(src_id, []).append(dst_id)
        src_rev = revision_map.get(src_id)
        dst_rev = revision_map.get(dst_id)
        if src_rev and dst_rev:
            cache_key = (src_id, dst_rev.component_id.id)
            if cache_key not in link_cache:
                links = env['kojto.product.component.revision.link'].search([
                    ('source_revision_id', '=', src_id),
                    ('target_component_id', '=', dst_rev.component_id.id)
                ])
                link_cache[cache_key] = links
            else:
                links = link_cache[cache_key]
            quantity = sum(link.quantity or 1.0 for link in links)
            link_quantities[(src_id, dst_id)] = quantity
        else:
            link_quantities[(src_id, dst_id)] = 1.0

    paths = {rev_id: [] for rev_id in revision_map}
    def collect_paths(current_id, cumulative_quantity=1.0, path=None, visited=None):
        if path is None:
            path = []
        if visited is None:
            visited = set()
        if current_id in visited:
            cycle_path = path + [(current_id, cumulative_quantity)]
            cycle_path_str = " -> ".join([revision_map.get(pid, {'name': pid}).name for pid, _ in cycle_path])
            raise ValidationError(f"Cycle detected in path collection: {cycle_path_str}")
        visited.add(current_id)
        rev = revision_map.get(current_id)
        if not rev:
            return
        path.append((current_id, cumulative_quantity))
        paths[current_id].append([(revision_map[pid].name if pid in revision_map else pid, qty) for pid, qty in path])
        for child_id in graph.get(current_id, []):
            child_rev = revision_map.get(child_id)
            if not child_rev:
                continue
            link_quantity = link_quantities.get((current_id, child_id), 1.0)
            collect_paths(child_id, cumulative_quantity * link_quantity, path, visited)
        path.pop()
        visited.remove(current_id)

    if start_revision_id:
        collect_paths(start_revision_id)

    quantities = {rev_id: sum(path[-1][1] for path in paths[rev_id] if paths[rev_id]) for rev_id in paths}
    return paths, quantities, link_quantities

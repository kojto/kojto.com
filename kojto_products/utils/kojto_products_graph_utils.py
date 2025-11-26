# kojto_products/utils/kojto_products_graph_utils.py
from odoo.exceptions import ValidationError
from odoo import fields

def fetch_components(env, initial_component_ids, max_components=100000, max_depth=50):
    """
    Fetch linked components with limits to prevent OOM.

    Args:
        env: Odoo environment
        initial_component_ids: Starting component IDs
        max_components: Maximum components to fetch (prevents memory explosion)
        max_depth: Maximum recursion depth (prevents infinite loops)

    Returns:
        set: Component IDs (limited to prevent OOM)
    """
    component_ids = set(initial_component_ids)
    depth = 0

    def _fetch_components(component_ids_to_process):
        nonlocal depth
        if not component_ids_to_process or depth >= max_depth or len(component_ids) >= max_components:
            return

        # ✓ Limit query result
        links = env['kojto.product.component.revision.link'].search([
            ('source_revision_id.component_id', 'in', list(component_ids_to_process))
        ], limit=min(10000, max_components * 10))

        new_component_ids = {link.target_component_id.id for link in links if link.target_component_id} - component_ids

        if new_component_ids:
            # ✓ Respect component limit
            can_add = max_components - len(component_ids)
            if can_add > 0:
                to_add = list(new_component_ids)[:can_add]
                component_ids.update(to_add)
                depth += 1
                _fetch_components(set(to_add))

    _fetch_components(initial_component_ids)
    return component_ids

def get_latest_revision(component, path_locking_dates, latest_revisions, revision_cache):
    """
    Get the latest valid revision for a component based on the locking dates in the current path.

    Args:
        component: The component to get revision for
        path_locking_dates: List of (revision_id, datetime_locked) tuples from the current path
        latest_revisions: Dict mapping component IDs to their sorted revisions
        revision_cache: Dict for caching results

    Returns:
        The latest valid revision or None if no valid revision exists
    """
    cache_key = (component.id, tuple(sorted(path_locking_dates or [])))
    if cache_key in revision_cache:
        return revision_cache[cache_key]

    revs = latest_revisions.get(component.id, [])
    if not revs:
        return None

    # If no locking dates in path, return the latest revision
    if not path_locking_dates:
        latest = revs[-1]
        revision_cache[cache_key] = latest
        return latest

    # Find the latest revision that's not after any locking date in the path
    for rev in reversed(revs):
        is_valid = True
        for _, lock_date in path_locking_dates:
            if lock_date and rev.datetime_issue and rev.datetime_issue > lock_date:
                is_valid = False
                break
        if is_valid:
            revision_cache[cache_key] = rev
            return rev
    return None

def get_links(env, source_revision, path_locking_dates, latest_revisions, revision_cache):
    """
    Get all valid links from a source revision based on the current path's locking dates.

    Args:
        env: Odoo environment for database access
        source_revision: The source revision to get links from
        path_locking_dates: List of (revision_id, datetime_locked) tuples from the current path
        latest_revisions: Dict mapping component IDs to their sorted revisions
        revision_cache: Dict for caching results

    Returns:
        List of tuples (target_revision, link_id, quantity)
    """
    next_revisions = []
    if not source_revision or not source_revision.exists():
        return next_revisions
    links = env['kojto.product.component.revision.link'].search([
        ('source_revision_id', 'in', source_revision.id)
    ])
    target_component_ids = [link.target_component_id.id for link in links if link.target_component_id]
    if target_component_ids:
        revision_map_local = {}
        for component_id in set(target_component_ids):
            component = env['kojto.product.component'].browse(component_id)
            target_revision = get_latest_revision(component, path_locking_dates, latest_revisions, revision_cache)
            if target_revision:
                revision_map_local[component_id] = target_revision
        for link in links:
            if link.target_component_id and link.target_component_id.id in revision_map_local:
                target_revision = revision_map_local[link.target_component_id.id]
                next_revisions.append((target_revision, link.id, link.quantity or 1.0))
    return next_revisions

def dfs_traverse(revision, path_locking_dates, visited, recursion_stack, path, edges, aggregated_attributes,
                 mode, env, latest_revisions, revision_cache):
    """
    Perform a depth-first search traversal of the revision graph.

    Args:
        revision: Current revision to process
        path_locking_dates: List of (revision_id, datetime_locked) tuples from the current path
        visited: Set of visited revision IDs
        recursion_stack: Set of revision IDs in the current recursion stack
        path: List of (revision, link_id) tuples in the current path
        edges: List of (src_id, dst_id) tuples for the tree
        aggregated_attributes: Dict mapping revision IDs to their aggregated attributes
        mode: 'cycle' for cycle detection, 'tree' for tree construction
        env: Odoo environment for database access
        latest_revisions: Dict mapping component IDs to their sorted revisions
        revision_cache: Dict for caching results

    Returns:
        Tuple (has_cycle: bool, cycle_path: str)
    """
    if not revision or not revision.exists():
        return False, None
    if revision.id in recursion_stack:
        cycle_start = next(i for i, (rev, _) in enumerate(path) if rev.id == revision.id)
        cycle = path[cycle_start:] + [(revision, None)]
        cycle_path_str = " -> ".join([rev.name for rev, _ in cycle])
        return True, cycle_path_str
    if revision.id in visited:
        return False, None

    # Update path locking dates if this revision is locked
    current_path_locking_dates = list(path_locking_dates or [])
    if revision.is_locked and revision.datetime_locked:
        current_path_locking_dates.append((revision.id, revision.datetime_locked))

    recursion_stack.add(revision.id)
    path.append((revision, None))
    visited.add(revision.id)

    agg_attrs = {
        'weight': revision.weight_attribute or 0.0,
        'length': revision.length_attribute or 0.0,
        'area': revision.area_attribute or 0.0,
        'volume': revision.volume_attribute or 0.0,
        'price': revision.price_attribute or 0.0,
        'time': revision.time_attribute or 0.0,
        'other': revision.other_attribute or 0.0
    }

    # ✓ Include ALL children - no skipping to ensure correct aggregates
    for next_rev, link_id, quantity in get_links(env, revision, current_path_locking_dates, latest_revisions, revision_cache):
        if not next_rev or not next_rev.exists():
            continue
        path[-1] = (revision, link_id)
        has_cycle, cycle_path_str = dfs_traverse(
            next_rev, current_path_locking_dates, visited, recursion_stack, path,
            edges, aggregated_attributes, mode, env, latest_revisions, revision_cache
        )
        if has_cycle:
            return True, cycle_path_str
        if mode == 'tree':
            edges.append((revision.id, next_rev.id))
            child_attrs = aggregated_attributes.get(next_rev.id, {
                'weight': 0.0, 'length': 0.0, 'area': 0.0, 'volume': 0.0,
                'price': 0.0, 'time': 0.0, 'other': 0.0
            })
            for attr in ['weight', 'length', 'area', 'volume', 'price', 'time', 'other']:
                agg_attrs[attr] += quantity * child_attrs[attr]

    recursion_stack.remove(revision.id)
    path.pop()
    aggregated_attributes[revision.id] = agg_attrs
    return False, None

def resolve_graph(start_revision, env, mode='cycle', max_depth=None):
    """
    Resolve the revision graph starting from the given revision.
    Uses locking dates to determine which revisions are locked,
    but uses is_locked and is_last_revision fields to determine lock status display.

    Args:
        start_revision: The starting revision record.
        env: Odoo environment for database access.
        mode (str): 'cycle' for cycle detection, 'tree' for tree construction.
        max_depth (int): Maximum depth for traversal (None for unlimited, 50-100 recommended)

    Returns:
        For 'cycle' mode: Tuple (has_cycle: bool, cycle_path: str)
        For 'tree' mode: Tuple (visited: set, edges: list, aggregated_attributes: dict, lock_status: dict)

    Raises:
        ValidationError: If start_revision is invalid or mode is unsupported.
    """
    if not start_revision or not start_revision.exists():
        raise ValidationError(f"Invalid start_revision: {start_revision.name if start_revision else 'None'}")

    # ✓ FIXED: Only fetch components that are linked to start_revision
    component_ids = fetch_components(env, [start_revision.component_id.id], max_depth=max_depth or 50)

    # Only fetch components we'll use
    all_components = env['kojto.product.component'].browse(list(component_ids))
    all_revisions = env['kojto.product.component.revision'].search([
        ('component_id', 'in', all_components.ids)
    ])
    all_links = env['kojto.product.component.revision.link'].search([
        ('source_revision_id', 'in', all_revisions.ids)
    ])

    visited = set()
    recursion_stack = set()
    path = []
    edges = []
    revision_cache = {}
    aggregated_attributes = {}
    lock_status = {}  # Track lock status for each revision

    # Pre-compute latest revisions for each component (using SQL for efficiency)
    latest_revisions = {}
    for component in all_components:
        revs = [r for r in all_revisions if r.component_id.id == component.id]
        if revs:
            # Sort revisions by datetime_issue
            sorted_revs = sorted(revs, key=lambda r: r.datetime_issue or fields.Datetime.now())
            latest_revisions[component.id] = sorted_revs

    # Initialize lock status for all revisions
    for rev in all_revisions:
        if rev.is_locked:
            lock_status[rev.id] = 'L' if rev.is_last_revision else 'LS'
        else:
            lock_status[rev.id] = None

    # Track depth for bounded traversal
    depth_counter = [0]

    def dfs_traverse_with_depth_limit(revision, path_locking_dates, visited, recursion_stack, path, edges, aggregated_attributes,
                                      mode, env, latest_revisions, revision_cache):
        """DFS with depth limiting only - includes all children for correct aggregates."""
        # ✓ CONSTRAINT: Check depth limit (prevents stack overflow, not data loss)
        if max_depth and depth_counter[0] >= max_depth:
            return False, None

        depth_counter[0] += 1
        result = dfs_traverse(revision, path_locking_dates, visited, recursion_stack, path, edges,
                            aggregated_attributes, mode, env, latest_revisions, revision_cache)
        depth_counter[0] -= 1
        return result

    has_cycle, cycle_path_str = dfs_traverse_with_depth_limit(
        start_revision, None, visited, recursion_stack, path, edges,
        aggregated_attributes, mode, env, latest_revisions, revision_cache
    )

    if mode == 'cycle':
        return has_cycle, cycle_path_str or "No cycle detected"
    elif mode == 'tree':
        return visited, edges, aggregated_attributes, lock_status
    else:
        raise ValidationError(f"Invalid mode: {mode}")

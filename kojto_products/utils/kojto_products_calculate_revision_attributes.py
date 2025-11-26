def calculate_revision_attributes(rev_id, paths, quantities, link_quantities, revision_map, memo=None):
    """Calculate attributes for a revision using a bottom-up approach.
    Sum the revision's own attributes plus contributions from all child revisions,
    weighted by the quantities in link_quantities. Use memoization to avoid redundant calculations.
    """
    if memo is None:
        memo = {}

    if rev_id in memo:
        return memo[rev_id]

    rev = revision_map.get(rev_id)
    if not rev:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    # Start with the revision's own attributes
    total_weight = rev.weight_attribute or 0.0
    total_length = rev.length_attribute or 0.0
    total_area = rev.area_attribute or 0.0
    total_volume = rev.volume_attribute or 0.0
    total_price = rev.price_attribute or 0.0
    total_time = rev.time_attribute or 0.0
    total_other = rev.other_attribute or 0.0

    # Build graph of parent-child relationships from link_quantities
    children = [dst_id for (src_id, dst_id) in link_quantities if src_id == rev_id]

    # Aggregate contributions from child revisions
    for child_id in children:
        child = revision_map.get(child_id)
        if not child:
            continue

        # Recursively calculate child's attributes
        child_weight, child_length, child_area, child_volume, child_price, child_time, child_other = calculate_revision_attributes(
            child_id, paths, quantities, link_quantities, revision_map, memo
        )

        # Get quantity from this revision to the child
        qty = link_quantities.get((rev_id, child_id), 1.0)

        # Add weighted contributions
        contribution_weight = qty * child_weight
        contribution_length = qty * child_length
        contribution_area = qty * child_area
        contribution_volume = qty * child_volume
        contribution_price = qty * child_price
        contribution_time = qty * child_time
        contribution_other = qty * child_other

        total_weight += contribution_weight
        total_length += contribution_length
        total_area += contribution_area
        total_volume += contribution_volume
        total_price += contribution_price
        total_time += contribution_time
        total_other += contribution_other

    memo[rev_id] = (total_weight, total_length, total_area, total_volume, total_price, total_time, total_other)
    return memo[rev_id]

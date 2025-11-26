from markupsafe import Markup
from ..utils.kojto_products_calculate_revision_attributes import calculate_revision_attributes
from ..utils.kojto_products_unit_converter import UnitConverter

def calculate_top_down_attributes(rev_id, parent_id, link_quantities, revision_map, parent_multiplier=1.0, memo=None):
    """Calculate attributes for a revision using a top-down approach.
    Multiply the revision's own attributes by the quantity from parent link,
    and recursively calculate for children with their respective multipliers.
    """
    if memo is None:
        memo = {}

    if (rev_id, parent_multiplier) in memo:
        return memo[(rev_id, parent_multiplier)]

    rev = revision_map.get(rev_id)
    if not rev:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    qty = link_quantities.get((parent_id, rev_id), 1.0) if parent_id else 1.0
    current_multiplier = parent_multiplier * qty

    weight = (rev.weight_attribute or 0.0) * current_multiplier
    length = (rev.length_attribute or 0.0) * current_multiplier
    area = (rev.area_attribute or 0.0) * current_multiplier
    volume = (rev.volume_attribute or 0.0) * current_multiplier
    price = (rev.price_attribute or 0.0) * current_multiplier
    time = (rev.time_attribute or 0.0) * current_multiplier
    other = (rev.other_attribute or 0.0) * current_multiplier

    memo[(rev_id, parent_multiplier)] = (weight, length, area, volume, price, time, other)
    return memo[(rev_id, parent_multiplier)]

def format_top_down(edges, visited, aggregated_attributes, revision_map, env, start_revision_id, lock_status=None):
    """
    Generate a collapsible HTML tree for top-down analysis with correct quantities, alphabetical sorting,
    initially expanded using <details open>, and node text in one line using a universal mechanism for link
    quantities and tree construction. Aggregate values (weight, length, area, volume, price, time, other)
    are displayed with font-size: 0.9em and font-style: italic.
    """
    css = (
        ".revision-tree{font-family:Arial,sans-serif;max-width:800px;margin:20px auto;background:#fff;padding:20px;"
        "border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}"
        ".revision-tree ul,.revision-tree li{list-style:none !important;padding-left:20px;margin:0;}"
        ".revision-tree li::marker{content:none !important;}"
        ".revision-tree li{margin:5px 0;display:block;}"
        ".revision-tree summary{cursor:pointer;font-weight:bold;color:#333;padding:2px 0;}"
        ".revision-tree summary:hover{color:#0066cc;}"
        ".revision-tree .start-revision{background-color:#e6f3ff;border-left:4px solid #0066cc;padding:5px 10px;margin:5px 0;}"
        ".revision-tree .lock-indicator{font-style:italic !important;margin-left:4px;}"
        ".revision-tree .lock-indicator.locked{color:#FFA500 !important;font-weight:normal !important;}"
        ".revision-tree .lock-indicator.locked-superseded{color:#FF0000 !important;font-weight:bold !important;}"
        ".revision-tree .name-secondary{color:#008000 !important;font-weight:bold;font-style:italic;margin-left:4px;}"
        ".revision-tree .analytics{color:#666 !important;font-size:0.9em;font-style:italic;margin-left:4px;}"
    )

    if not visited or start_revision_id not in revision_map:
        start_rev = revision_map.get(start_revision_id)
        if not start_rev:
            html = f"""
            <div class='revision-tree'>
                <style>{css}</style>
                <ul style='list-style:none !important;'><li style='list-style:none !important;display:block;'>No top-down resolution available</li></ul>
            </div>
            """
            return Markup(html)

        weight_val, weight_unit = UnitConverter.convert_weight(start_rev.weight_attribute or 0.0)
        length_val, length_unit = UnitConverter.convert_length(start_rev.length_attribute or 0.0)
        area_val, area_unit = UnitConverter.convert_area(start_rev.area_attribute or 0.0)
        volume_val, volume_unit = UnitConverter.convert_volume(start_rev.volume_attribute or 0.0)
        price_val = start_rev.price_attribute or 0.0
        time_val, time_unit = UnitConverter.convert_time(start_rev.time_attribute or 0.0)

        details = f"<span style='font-size:0.9em;font-style:italic;'>{weight_val}{weight_unit}, {length_val}{length_unit}, {area_val}{area_unit}, {volume_val}{volume_unit}, {price_val}€, {time_val}{time_unit}, {start_rev.other_attribute or 0.0}</span>"
        unit_name = start_rev.component_id.unit_id.name if start_rev.component_id and start_rev.component_id.unit_id else 'units'
        lock_indicator = ""
        if start_rev.id in lock_status:
            status = lock_status[start_rev.id]
            if status == 'L':
                lock_indicator = f"<span class='lock-indicator locked' style='color:#FFA500 !important;font-style:italic !important;font-weight:normal !important;'>(L)</span>"
            elif status == 'LS':
                lock_indicator = f"<span class='lock-indicator locked-superseded' style='color:#FF0000 !important;font-style:italic !important;font-weight:bold !important;'>(LS)</span>"

        html = f"""
        <div class='revision-tree'>
            <style>{css}</style>
            <ul style='list-style:none !important;'><li style='list-style:none !important;display:block;' class='start-revision'><b>1.0</b> {unit_name} <b>{start_rev.name}</b>{lock_indicator}, {details}</li></ul>
        </div>
        """
        return Markup(html)

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

    def build_tree(rev_id, parent_id=None):
        rev = revision_map.get(rev_id)
        if not rev:
            return ""

        weight_val, weight_unit = UnitConverter.convert_weight(rev.weight_attribute or 0.0)
        length_val, length_unit = UnitConverter.convert_length(rev.length_attribute or 0.0)
        area_val, area_unit = UnitConverter.convert_area(rev.area_attribute or 0.0)
        volume_val, volume_unit = UnitConverter.convert_volume(rev.volume_attribute or 0.0)
        price_val = rev.price_attribute or 0.0
        time_val, time_unit = UnitConverter.convert_time(rev.time_attribute or 0.0)

        details = f"<span style='font-size:0.9em;font-style:italic;'>{weight_val}{weight_unit}, {length_val}{length_unit}, {area_val}{area_unit}, {volume_val}{volume_unit}, {price_val}€, {time_val}{time_unit}, {rev.other_attribute or 0.0}</span>"
        quantity = link_quantities.get((parent_id, rev_id), 1.0) if parent_id else 1.0
        unit_name = rev.component_id.unit_id.name if rev.component_id and rev.component_id.unit_id else 'units'
        children = sorted(graph.get(rev_id, []), key=lambda cid: revision_map[cid].name if cid in revision_map else '')

        revision_text = rev.name

        lock_indicator = ""
        if rev.id in lock_status:
            status = lock_status[rev.id]
            if status == 'L':
                lock_indicator = f"<span class='lock-indicator locked' style='color:#FFA500 !important;font-style:italic !important;font-weight:normal !important;'>(L)</span>"
            elif status == 'LS':
                lock_indicator = f"<span class='lock-indicator locked-superseded' style='color:#FF0000 !important;font-style:italic !important;font-weight:bold !important;'>(LS)</span>"

        node_html = [f"<li style='list-style:none !important;display:block;' class='{'start-revision' if rev_id == start_revision_id else ''}'>"]
        if children:
            if rev_id == start_revision_id:
                node_html.append(f"<details open><summary><b>{revision_text}</b>{lock_indicator}, {details}</summary><ul style='list-style:none !important;'>")
            else:
                node_html.append(f"<details open><summary><b>{quantity}</b> {unit_name} <b>{revision_text}</b>{lock_indicator}, {details}</summary><ul style='list-style:none !important;'>")
            for child_id in children:
                child_html = build_tree(child_id, rev_id)
                if child_html:
                    node_html.append(child_html)
            node_html.append("</ul></details>")
        else:
            if rev_id == start_revision_id:
                node_html.append(f"<b>{revision_text}</b>{lock_indicator}, {details}")
            else:
                node_html.append(f"<b>{quantity}</b> {unit_name} <b>{revision_text}</b>{lock_indicator}, {details}")
        node_html.append("</li>")
        return "".join(node_html)

    html = f"""
    <div class='revision-tree'>
        <style>{css}</style>
        <ul style='list-style:none !important;'>{build_tree(start_revision_id)}</ul>
    </div>
    """
    return Markup(html)

def format_bottom_up(start_revision, paths, quantities, link_quantities, revision_map, lock_status):
    """
    Format the bottom-up analysis as a collapsible HTML tree.
    Each revision's attributes are calculated from the bottom up, summing its own attributes
    and contributions from child revisions, weighted by the quantities in the paths.
    """
    css = (
        ".revision-tree{font-family:Arial,sans-serif;max-width:800px;margin:20px auto;background:#fff;padding:20px;"
        "border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}"
        ".revision-tree ul,.revision-tree li{list-style:none !important;padding-left:20px;margin:0;}"
        ".revision-tree li::marker{content:none !important;}"
        ".revision-tree li{margin:5px 0;display:block;}"
        ".revision-tree details{margin:5px 0;}"
        ".revision-tree summary{cursor:pointer;font-weight:bold;color:#333;padding:2px 0;}"
        ".revision-tree summary:hover{color:#0066cc;}"
        ".revision-tree .start-revision{background-color:#e6f3ff;border-left:4px solid #0066cc;padding:5px 10px;margin:5px 0;}"
        ".revision-tree .path-list{margin:5px 0 5px 20px;font-size:0.9em;}"
        ".revision-tree .path-item{margin:3px 0;padding:3px;border-left:2px solid #E0E0E0;color:#808080 !important;font-style:italic;}"
        ".revision-tree .analytics{color:#666 !important;font-size:0.9em;font-style:italic;margin-left:4px;}"
        ".revision-tree .lock-indicator{font-style:italic !important;margin-left:4px;}"
        ".revision-tree .lock-indicator.locked{color:#FFA500 !important;font-weight:normal !important;}"
        ".revision-tree .lock-indicator.locked-superseded{color:#FF0000 !important;font-weight:bold !important;}"
        ".revision-tree .name-secondary{color:#008000 !important;font-weight:bold !important;font-style:italic !important;margin-left:4px;}"
    )

    html = ['<div class="revision-tree">']
    html.append(f'<style>{css}</style>')

    def format_attributes(rev_id, paths, quantities, link_quantities, revision_map):
        weight, length, area, volume, price, time, other = calculate_revision_attributes(
            rev_id, paths, quantities, link_quantities, revision_map
        )
        weight_val, weight_unit = UnitConverter.convert_weight(weight)
        length_val, length_unit = UnitConverter.convert_length(length)
        area_val, area_unit = UnitConverter.convert_area(area)
        volume_val, volume_unit = UnitConverter.convert_volume(volume)
        time_val, time_unit = UnitConverter.convert_time(time)
        return f"<span class='analytics'>{weight_val}{weight_unit}, {length_val}{length_unit}, {area_val}{area_unit}, {volume_val}{volume_unit}, {price}€, {time_val}{time_unit}, {other}</span>"

    def build_tree():
        tree = ['<ul style="list-style:none !important;">']
        start_rev = revision_map.get(start_revision.id)
        if start_rev:
            attrs = format_attributes(start_revision.id, paths, quantities, link_quantities, revision_map)
            lock_indicator = ""
            if start_rev.id in lock_status:
                status = lock_status[start_rev.id]
                if status == 'L':
                    lock_indicator = f"<span class='lock-indicator locked' style='color:#FFA500 !important;font-style:italic !important;font-weight:normal !important;'>(L)</span>"
                elif status == 'LS':
                    lock_indicator = f"<span class='lock-indicator locked-superseded' style='color:#FF0000 !important;font-style:italic !important;font-weight:bold !important;'>(LS)</span>"
            revision_text = start_rev.name
            tree.append(f"""
                <li style='list-style:none !important;display:block;' class='start-revision'>
                    <b>{revision_text}</b>{lock_indicator}, {attrs}
                </li>
            """)

        # Sort revisions by component name and revision name
        sorted_revisions = sorted(
            [(rev_id, rev) for rev_id, rev in revision_map.items() if rev_id != start_revision.id],
            key=lambda x: (
                x[1].component_id.name or '',  # First sort by component name
                x[1].name or ''  # Then by revision name
            )
        )

        for rev_id, rev in sorted_revisions:
            rev_paths = paths.get(rev_id, [])
            if not rev_paths:
                continue
            total_qty = quantities.get(rev_id, 0.0)
            if total_qty == 0:
                continue
            attrs = format_attributes(rev_id, paths, quantities, link_quantities, revision_map)
            unit_name = rev.component_id.unit_id.name if rev.component_id and rev.component_id.unit_id else 'units'
            lock_indicator = ""
            if rev_id in lock_status:
                status = lock_status[rev_id]
                if status == 'L':
                    lock_indicator = f"<span class='lock-indicator locked' style='color:#FFA500 !important;font-style:italic !important;font-weight:normal !important;'>(L)</span>"
                elif status == 'LS':
                    lock_indicator = f"<span class='lock-indicator locked-superseded' style='color:#FF0000 !important;font-style:italic !important;font-weight:bold !important;'>(LS)</span>"
            revision_text = rev.name
            path_list = []
            for path in rev_paths:
                path_str = " → ".join(f"{qty:.1f} × {name}" for name, qty in path)
                path_list.append(f"<div class='path-item' style='color:#808080 !important;'>{path_str}</div>")
            tree.append(f"""
                <li style='list-style:none !important;display:block;'>
                    <details open>
                        <summary>
                            <b>{total_qty:.1f}</b> {unit_name} <b>{revision_text}</b>{lock_indicator}, {attrs}
                        </summary>
                        <div class='path-list'>
                            {"".join(path_list)}
                        </div>
                    </details>
                </li>
            """)
        tree.append('</ul>')
        return "".join(tree)

    html.append(build_tree())
    html.append('</div>')
    return Markup("".join(html))

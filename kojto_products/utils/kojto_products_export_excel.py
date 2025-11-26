# kojto_products/utils/kojto_products_export_excel.py
import io
import base64
import xlsxwriter
from collections import defaultdict
from datetime import datetime
from ..utils.kojto_products_collect_revision_paths import collect_revision_paths
from ..utils.kojto_products_calculate_revision_attributes import calculate_revision_attributes

def export_revision_tree_to_excel(edges, visited, aggregated_attributes, revision_map, env, start_revision_id, revision_number, lock_status):
    """
    Export revision tree data to an Excel file with two sheets: Top-Down Analysis and Bottom-Up Analysis.
    Includes attributes: weight, length, area, volume, price, time, and other.

    :param edges: List of tuples (src_id, dst_id) from resolve_graph.
    :param visited: Set of revision IDs from resolve_graph.
    :param aggregated_attributes: Dict mapping revision IDs to attributes (weight, length, area, volume, price, time, other).
    :param revision_map: Dict mapping revision IDs to kojto.product.component.revision records.
    :param env: Odoo environment for querying links.
    :param start_revision_id: ID of the starting revision for the tree.
    :param revision_number: Revision number (e.g., '01') to include in the filename.
    :param lock_status: Dict mapping revision IDs to lock status ('L' or 'LS').
    :return: Tuple of (base64-encoded file content, filename).
    """
    # Get component name from revision_map
    component_name = revision_map.get(start_revision_id).component_id.name or 'unnamed' if start_revision_id in revision_map else 'unnamed'

    # Create Excel workbook
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)

    # Define formats
    bold_format = workbook.add_format({'bold': True})
    text_wrap_format = workbook.add_format({'text_wrap': True})
    locked_latest_format = workbook.add_format({'color': '#FFA500', 'bold': True, 'italic': True})  # Orange
    locked_superseded_format = workbook.add_format({'color': '#FF0000', 'bold': True, 'italic': True})  # Red

    # Build adjacency list for top-down analysis
    graph = defaultdict(list)
    for src_id, dst_id in edges:
        graph[src_id].append(dst_id)

    # Get paths, quantities, and link quantities for bottom-up analysis
    paths, quantities, link_quantities = collect_revision_paths(start_revision_id, edges, revision_map, env)

    # Sheet 1: Top-Down Analysis
    sheet1 = workbook.add_worksheet("Top-Down Analysis")
    headers1 = ['Level', 'Revision Name', 'Quantity', 'Unit', 'Weight (kg)', 'Length (m)', 'Area (m²)', 'Volume (m³)', 'Price (€)', 'Time (min)', 'Other']
    cell_values1 = [headers1]
    for col, header in enumerate(headers1):
        sheet1.write(0, col, header, bold_format)

    row = 1
    def build_top_down_tree(rev_id, parent_id=None, level=0):
        nonlocal row
        rev = revision_map.get(rev_id)
        if not rev:
            return
        quantity = link_quantities.get((parent_id, rev_id), 1.0) if parent_id else 1.0
        unit_name = rev.component_id.unit_id.name if rev.component_id and rev.component_id.unit_id else 'units'

        # Format revision name with lock status
        revision_name = rev.name or ''
        if rev_id in lock_status:
            status = lock_status[rev_id]
            if status == 'L':
                revision_name += ' (L)'
            elif status == 'LS':
                revision_name += ' (LS)'

        row_data = [
            level,
            revision_name,
            quantity,
            unit_name,
            rev.weight_attribute or 0.0,
            rev.length_attribute or 0.0,
            rev.area_attribute or 0.0,
            rev.volume_attribute or 0.0,
            rev.price_attribute or 0.0,
            rev.time_attribute or 0.0,
            rev.other_attribute or 0.0
        ]
        cell_values1.append([str(val) for val in row_data])

        # Write data with appropriate format for lock status
        for col, value in enumerate(row_data):
            if col == 1:  # Revision Name column
                if rev_id in lock_status:
                    status = lock_status[rev_id]
                    if status == 'L':
                        sheet1.write(row, col, value, locked_latest_format)
                    elif status == 'LS':
                        sheet1.write(row, col, value, locked_superseded_format)
                    else:
                        sheet1.write(row, col, value)
                else:
                    sheet1.write(row, col, value)
            else:
                sheet1.write(row, col, value)
        row += 1
        children = sorted(graph.get(rev_id, []), key=lambda cid: revision_map[cid].name if cid in revision_map else '')
        for child_id in children:
            build_top_down_tree(child_id, rev_id, level + 1)

    if visited and start_revision_id in revision_map:
        build_top_down_tree(start_revision_id)
    else:
        unit_name = revision_map.get(start_revision_id).component_id.unit_id.name if start_revision_id in revision_map and revision_map.get(start_revision_id).component_id and revision_map.get(start_revision_id).component_id.unit_id else 'units'
        start_rev = revision_map.get(start_revision_id)

        # Format revision name with lock status
        revision_name = start_rev.name or 'Unknown' if start_rev else 'Unknown'
        if start_rev and start_rev.id in lock_status:
            status = lock_status[start_rev.id]
            if status == 'L':
                revision_name += ' (L)'
            elif status == 'LS':
                revision_name += ' (LS)'

        row_data = [
            0,
            revision_name,
            1.0,
            unit_name,
            start_rev.weight_attribute or 0.0 if start_rev else 0.0,
            start_rev.length_attribute or 0.0 if start_rev else 0.0,
            start_rev.area_attribute or 0.0 if start_rev else 0.0,
            start_rev.volume_attribute or 0.0 if start_rev else 0.0,
            start_rev.price_attribute or 0.0 if start_rev else 0.0,
            start_rev.time_attribute or 0.0 if start_rev else 0.0,
            start_rev.other_attribute or 0.0 if start_rev else 0.0
        ]
        cell_values1.append([str(val) for val in row_data])

        # Write data with appropriate format for lock status
        for col, value in enumerate(row_data):
            if col == 1:  # Revision Name column
                if start_rev and start_rev.id in lock_status:
                    status = lock_status[start_rev.id]
                    if status == 'L':
                        sheet1.write(row, col, value, locked_latest_format)
                    elif status == 'LS':
                        sheet1.write(row, col, value, locked_superseded_format)
                    else:
                        sheet1.write(row, col, value)
                else:
                    sheet1.write(row, col, value)
            else:
                sheet1.write(row, col, value)
        row += 1
    max_row1 = row

    # Sheet 2: Bottom-Up Analysis
    sheet2 = workbook.add_worksheet("Bottom-Up Analysis")
    headers2 = ['Revision Name', 'Total Quantity', 'Unit', 'Weight (kg)', 'Length (m)', 'Area (m²)', 'Volume (m³)', 'Price (€)', 'Time (min)', 'Other', 'Paths']
    cell_values2 = [headers2]
    for col, header in enumerate(headers2):
        sheet2.write(0, col, header, bold_format)

    # Write bottom-up analysis to sheet using the same calculation as format_bottom_up
    row = 1
    sorted_rev_ids = [start_revision_id] + sorted([rid for rid in visited if rid != start_revision_id], key=lambda rid: revision_map[rid].name if rid in revision_map else '')
    for rev_id in sorted_rev_ids:
        rev = revision_map.get(rev_id)
        if not rev:
            continue

        # Calculate attributes using the same function as format_bottom_up
        weight, length, area, volume, price, time, other = calculate_revision_attributes(
            rev_id, paths, quantities, link_quantities, revision_map
        )

        # Format revision name with lock status
        revision_name = rev.name or ''
        if rev_id in lock_status:
            status = lock_status[rev_id]
            if status == 'L':
                revision_name += ' (L)'
            elif status == 'LS':
                revision_name += ' (LS)'

        quantity = quantities.get(rev_id, 1.0)
        unit_name = rev.component_id.unit_id.name if rev.component_id and rev.component_id.unit_id else 'units'
        path_strs = [" -> ".join(f"{name}" if i < len(path) - 1 else f"{qty} x {name}" for i, (name, qty) in enumerate(path)) for path in paths[rev_id]]
        row_data = [
            revision_name,
            quantity,
            unit_name,
            weight,
            length,
            area,
            volume,
            price,
            time,
            other,
            "\n".join(path_strs) if path_strs else 'No paths'
        ]
        cell_values2.append([str(val) for val in row_data])

        # Write data with appropriate format for lock status
        for col, value in enumerate(row_data):
            if col == 0:  # Revision Name column
                if rev_id in lock_status:
                    status = lock_status[rev_id]
                    if status == 'L':
                        sheet2.write(row, col, value, locked_latest_format)
                    elif status == 'LS':
                        sheet2.write(row, col, value, locked_superseded_format)
                    else:
                        sheet2.write(row, col, value)
                else:
                    sheet2.write(row, col, value)
            elif col == 11:  # Paths column
                sheet2.write(row, col, value, text_wrap_format)
            else:
                sheet2.write(row, col, value)
        row += 1
    max_row2 = row

    # Auto-fit columns based on content length (approximate width in characters)
    def autofit_sheet(sheet, cell_values):
        # Compute max length per column considering header and all rows
        col_widths = {}
        for r_idx, row_values in enumerate(cell_values):
            for c_idx, value in enumerate(row_values):
                text = str(value) if value is not None else ''
                # Prefer multiline-aware max length for Paths
                if '\n' in text:
                    max_segment = max((len(seg) for seg in text.split('\n')), default=0)
                    length = max_segment
                else:
                    length = len(text)
                # Add a small padding
                length += 2
                col_widths[c_idx] = max(col_widths.get(c_idx, 0), length)

        # Excel columns A..L
        for c_idx, width in col_widths.items():
            # Cap extreme widths to keep sheets readable
            max_width = 80 if c_idx == 11 else 40
            final_width = min(width, max_width)
            # Map index to Excel column letter (0->A)
            col_letter = chr(ord('A') + c_idx)
            sheet.set_column(f'{col_letter}:{col_letter}', final_width)

    autofit_sheet(sheet1, cell_values1)
    autofit_sheet(sheet2, cell_values2)

    workbook.close()
    output.seek(0)
    file_content = base64.b64encode(output.read())
    file_name = f"{component_name}_rev{revision_number}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return file_content, file_name

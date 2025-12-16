# kojto_optimizer/utils/generate_2d_cutting_plan.py

import json
import logging
from datetime import datetime
from shapely.geometry import Polygon
from shapely.affinity import translate as shapely_translate

try:
    from pynest2d import Item, Box, Point, nest
    PYNEST2D_AVAILABLE = True
except ImportError:
    PYNEST2D_AVAILABLE = False
    Item = Box = Point = nest = None

_logger = logging.getLogger(__name__)


def generate_2d_cutting_plan(
    stock_rectangles_ids,
    shapes_to_cut_ids,
    method="maxrects_bssf",
    width_of_cut=0.0,
    use_stock_priority=False,
    package=None,
    margin_left=0.0,
    margin_right=0.0,
    margin_top=0.0,
    margin_bottom=0.0,
    allow_rotation=True  # New parameter to control rotation
):
    """
    Updated version:
    - Optional rotation: if allow_rotation=False, duplicate items for 0° and 90° only
    - Reduces small/irritating rotations (e.g., 1.57° ≈90°, 3.14°≈180°, 4.71°≈270°)
    - Keeps continuous rotation if True (default for better packing)
    - Normalized polygons + bbox sorting for bottom-left packing
    - SCALE=10.0, kerf as int
    """

    def error_result(message, error_details=None):
        err = {
            "success": False,
            "message": message,
            "cutting_plans": [],
            "stock_used": [],
            "summary": {}
        }
        if error_details is not None:
            err["error_details"] = error_details
        return json.dumps(err, indent=2)

    if not PYNEST2D_AVAILABLE:
        return error_result(
            "pynest2d library is not available. Please install it: pip install pynest2d",
            {"library": "pynest2d"}
        )

    if package:
        try:
            package_id = str(package.id)
            package_name = package.name or "Unnamed Package"
            package_subcode_id = str(package.subcode_id.id) if package.subcode_id else None
            package_description = package.description or "No description provided"
            package_date_issue = (package.date_issue.strftime('%Y-%m-%d')
                                  if package.date_issue else datetime.now().strftime('%Y-%m-%d'))
        except AttributeError as e:
            return error_result("Invalid package data", {"exception": str(e)})

    if not stock_rectangles_ids or not shapes_to_cut_ids:
        return error_result("Missing stock or shapes to cut")

    # Prepare stock (unchanged)
    stock_data = []
    for s in stock_rectangles_ids:
        original_width = float(s.stock_width)
        original_length = float(s.stock_length)
        effective_width = original_width - margin_left - margin_right
        effective_length = original_length - margin_top - margin_bottom
        if effective_width <= 0 or effective_length <= 0:
            continue
        stock_data.append({
            'position': s.stock_position,
            'description': s.stock_description or "-",
            'original_width': original_width,
            'original_length': original_length,
            'effective_width': effective_width,
            'effective_length': effective_length,
            'pieces': int(s.available_stock_rectangle_pieces),
        })

    if not stock_data:
        return error_result("No valid stock after applying margins")

    effective_width = stock_data[0]['effective_width']
    effective_length = stock_data[0]['effective_length']
    total_available_pieces = sum(s['pieces'] for s in stock_data)

    if use_stock_priority:
        stock_data.sort(key=lambda x: x['position'])

    # Prepare shapes - normalize to (0,0)
    shapes_data = []
    for shape in shapes_to_cut_ids:
        if not shape.outer_polygon_json:
            continue
        try:
            outer_poly_coords = json.loads(shape.outer_polygon_json)
            if len(outer_poly_coords) < 3:
                continue

            polygon = Polygon(outer_poly_coords)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or polygon.area <= 0:
                continue

            minx, miny, _, _ = polygon.bounds
            polygon = shapely_translate(polygon, xoff=-minx, yoff=-miny)

            outer_coords = list(polygon.exterior.coords[:-1])
            outer_points_float = [(float(x), float(y)) for x, y in outer_coords]

            bbox_width = polygon.bounds[2] - polygon.bounds[0]
            bbox_height = polygon.bounds[3] - polygon.bounds[1]

            shapes_data.append({
                'position': shape.cut_position,
                'description': shape.cut_description or "-",
                'polygon': polygon,
                'outer_points_float': outer_points_float,
                'outer_points_float_90': [( -y, x ) for x, y in reversed(outer_points_float)],  # For 90° rotated version
                'bbox_width': bbox_width,
                'bbox_height': bbox_height,
                'bbox_area': bbox_width * bbox_height,
                'area': polygon.area,
                'pieces': int(shape.required_cut_shape_pieces or 1),
            })
        except Exception as e:
            _logger.warning(f"Error processing shape {shape.cut_position}: {e}")
            continue

    if not shapes_data:
        return error_result("No valid shapes to cut")

    # Sort by bbox area descending
    shapes_data.sort(key=lambda x: x['bbox_area'], reverse=True)

    # Expand items - handle rotation limit
    all_items_data = []
    for shape in shapes_data:
        num_pieces = shape['pieces']
        if allow_rotation:
            # Full rotation allowed - use original
            all_items_data.extend([shape] * num_pieces)
        else:
            # Only 0° and 90° - duplicate for each orientation
            for _ in range(num_pieces):
                all_items_data.append(shape)  # 0°
                all_items_data.append({**shape, 'is_90': True})  # 90°

    if not all_items_data:
        return error_result("No items after expanding pieces")

    # Scale
    SCALE = 10.0

    # Create Items
    pynest_items = []
    item_mapping = []
    for data in all_items_data:
        try:
            if not allow_rotation and data.get('is_90'):
                points_float = data['outer_points_float_90']
            else:
                points_float = data['outer_points_float']
            points_int = [Point(int(round(x * SCALE)), int(round(y * SCALE)))
                          for x, y in points_float]
            if len(points_int) < 3:
                continue
            item = Item(points_int)
            pynest_items.append(item)
            item_mapping.append(data)
        except Exception as e:
            _logger.warning(f"Failed to create Item for {data['position']}: {e}")
            continue

    if not pynest_items:
        return error_result("No valid pynest2d Items created")

    # Bin and kerf
    bin_width_int = int(round(effective_width * SCALE))
    bin_height_int = int(round(effective_length * SCALE))
    bin_box = Box(bin_width_int, bin_height_int)
    spacing_scaled = int(round(width_of_cut * SCALE))

    _logger.info(f"Nesting parameters: bin={bin_width_int}x{bin_height_int} (scaled), "
                 f"spacing={spacing_scaled} (scaled, {width_of_cut}mm), "
                 f"items={len(pynest_items)}")

    # Nest
    try:
        num_bins_used = nest(pynest_items, bin_box, spacing_scaled)
        _logger.info(f"pynest2d nesting completed: {num_bins_used} sheets required")

        # Log placement statistics
        placed_count = sum(1 for item in pynest_items if item.binId() >= 0)
        _logger.info(f"Placed {placed_count} out of {len(pynest_items)} items")
    except Exception as e:
        _logger.error(f"Nesting failed: {e}", exc_info=True)
        return error_result("Nesting failed", {"exception": str(e)})

    if num_bins_used > total_available_pieces:
        return error_result(
            f"Insufficient stock: {num_bins_used} sheets needed, only {total_available_pieces} available"
        )

    # Extract positions from nested items
    # pynest2d places items in a coordinate system where the bin is centered at (0,0)
    # So items are placed around (-bin_width/2, -bin_height/2) to (bin_width/2, bin_height/2)
    # We need to shift to bottom-left origin (0,0) by adding half the bin dimensions
    plans_by_bin = {}
    unplaced_count = 0
    for item_obj, data in zip(pynest_items, item_mapping):
        bin_id = item_obj.binId()
        if bin_id < 0:
            unplaced_count += 1
            continue

        transformed = item_obj.transformedShape()
        if transformed.vertexCount() == 0:
            continue

        # Get all vertex coordinates from the transformed shape
        vertices = [(float(transformed.vertex(i).x()), float(transformed.vertex(i).y()))
                    for i in range(transformed.vertexCount())]

        if not vertices:
            continue

        # Find bounding box of the transformed shape
        min_x = min(v[0] for v in vertices)
        min_y = min(v[1] for v in vertices)
        max_x = max(v[0] for v in vertices)
        max_y = max(v[1] for v in vertices)

        # pynest2d uses a coordinate system where the bin is centered at (0,0)
        # The bin extends from approximately (-bin_width/2, -bin_height/2) to (bin_width/2, bin_height/2)
        # We need to shift coordinates to bottom-left origin (0,0)
        # The shift is: add half the bin dimensions to move from center-origin to bottom-left origin
        pos_x = (min_x + bin_width_int / 2.0) / SCALE
        pos_y = (min_y + bin_height_int / 2.0) / SCALE

        # Debug: log first few placements to verify coordinate system
        if len(plans_by_bin.get(bin_id, [])) < 3:
            _logger.debug(f"Item {data.get('position', 'unknown')}: "
                         f"transformed bbox=({min_x:.1f},{min_y:.1f}) to ({max_x:.1f},{max_y:.1f}), "
                         f"final pos=({pos_x:.2f},{pos_y:.2f})")

        # Ensure positions are non-negative (should be after the shift)
        if pos_x < -0.01 or pos_y < -0.01:  # Allow small negative due to rounding
            _logger.warning(f"Negative position detected for {data.get('position', 'unknown')}: "
                          f"x={pos_x:.3f}, y={pos_y:.3f}, min_x={min_x:.1f}, min_y={min_y:.1f}, "
                          f"bin_width={bin_width_int}, bin_height={bin_height_int}")
            pos_x = max(0, pos_x)
            pos_y = max(0, pos_y)

        rotation_deg = float(item_obj.rotation())
        # If no rotation, force 0 or 90
        if not allow_rotation:
            rotation_deg = 90.0 if data.get('is_90') else 0.0

        if bin_id not in plans_by_bin:
            plans_by_bin[bin_id] = []
        plans_by_bin[bin_id].append({
            'data': data,
            'x': pos_x,
            'y': pos_y,
            'rotation': rotation_deg,
        })

    if not plans_by_bin:
        return error_result("No items placed successfully")

    # Build output (unchanged)
    cutting_plans = []
    stock_usage = {}
    plan_number = 1
    stock_idx = 0

    for bin_id in sorted(plans_by_bin):
        placed = plans_by_bin[bin_id]
        stock = stock_data[stock_idx % len(stock_data)]
        stock_idx += 1

        used_area = sum(p['data']['area'] for p in placed)
        stock_area = effective_width * effective_length
        waste_pct = round(100 * (1 - used_area / stock_area), 2) if stock_area > 0 else 0

        cutting_plan = {
            'cutting_plan_number': f"CP_{plan_number:03d}",
            'stock_position': stock['position'],
            'stock_description': stock['description'],
            'stock_width': stock['original_width'],
            'stock_length': stock['original_length'],
            'pieces': 1,
            'waste_percentage': waste_pct,
            'cut_pattern': [
                {
                    'cut_position': p['data']['position'],
                    'cut_description': p['data']['description'],
                    'x': round(p['x'] + margin_left, 2),
                    'y': round(p['y'] + margin_bottom, 2),
                    'width': round(p['data']['bbox_width'], 2),
                    'length': round(p['data']['bbox_height'], 2),
                    'rotation': round(p['rotation'], 2),
                    'pieces': 1,
                    'area': round(p['data']['area'], 2),
                }
                for p in placed
            ]
        }
        cutting_plans.append(cutting_plan)

        key = stock['position']
        if key not in stock_usage:
            stock_usage[key] = {
                'stock_position': key,
                'stock_description': stock['description'],
                'stock_width': stock['original_width'],
                'stock_length': stock['original_length'],
                'pcs': 0,
            }
        stock_usage[key]['pcs'] += 1

        plan_number += 1

    total_cut_area = sum(sum(item['area'] for item in plan['cut_pattern']) for plan in cutting_plans)
    total_used_stock_area = len(cutting_plans) * stock_data[0]['original_width'] * stock_data[0]['original_length']
    total_waste_pct = round(100 * (1 - total_cut_area / total_used_stock_area), 2) if total_used_stock_area > 0 else 0

    result = {
        "success": True,
        "message": f"Generated {len(cutting_plans)} cutting plan(s) using {num_bins_used} sheet(s)."
                   + (f" {unplaced_count} item(s) unplaced." if unplaced_count else " All items placed."),
        "cutting_plans": cutting_plans,
        "stock_used": list(stock_usage.values()),
        "summary": {
            "total_stock_area": sum(s['original_width'] * s['original_length'] * s['pieces'] for s in stock_data),
            "total_used_stock_area": total_used_stock_area,
            "total_cut_area": round(total_cut_area, 2),
            "total_waste_percentage": total_waste_pct,
            "method": method,
            "width_of_cut": width_of_cut,
            "margin_left": margin_left,
            "margin_right": margin_right,
            "margin_top": margin_top,
            "margin_bottom": margin_bottom,
        }
    }

    if package:
        result.update({
            "id": package_id,
            "name": package_name,
            "subcode_id": package_subcode_id,
            "description": package_description,
            "date_issue": package_date_issue,
        })

    return json.dumps(result, indent=2)

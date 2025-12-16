# kojto_optimizer/utils/compute_cutting_plan_2d_svg.py

import json
import logging
from xml.etree import ElementTree as ET
from typing import Union, List, Dict, Optional
from html import escape
from shapely.geometry import Polygon
from shapely.affinity import translate, rotate

_logger = logging.getLogger(__name__)


def compute_cutting_plan_2d_svg(
    cutting_plan_json: Union[str, Dict, List[Dict]],
    shapes_to_cut_records: Optional[List] = None,
    package_name: Optional[str] = None,
    margin_left: float = 0.0,
    margin_bottom: float = 0.0
) -> List[str]:
    """
    Generate SVG strings for 2D cutting plans with actual polygon shapes.

    Args:
        cutting_plan_json: The cutting plan JSON data (string, dict, or list of dicts).
            Expected structure: {"cutting_plans": [{"stock_width", "stock_length", "cut_pattern", ...}, ...]}
        shapes_to_cut_records: List of shape records to get polygon data from
        package_name: Optional name of the package for naming cutting plans.
        margin_left: Left margin to translate cut shape coordinates (x direction).
        margin_bottom: Bottom margin to translate cut shape coordinates (y direction).

    Returns:
        List of SVG strings, each representing a cutting plan.
    """
    # Parse JSON if it's a string
    if isinstance(cutting_plan_json, str):
        try:
            cutting_plan_json = json.loads(cutting_plan_json)
        except json.JSONDecodeError as e:
            _logger.error(f"Error parsing cutting_plan_json: {e}")
            return []

    # Extract cutting plans
    if isinstance(cutting_plan_json, list):
        cutting_plans = [plan.get("cutting_plans", []) for plan in cutting_plan_json if "cutting_plans" in plan]
        cutting_plans = [plan for sublist in cutting_plans for plan in sublist]
    else:
        cutting_plans = cutting_plan_json.get("cutting_plans", [])

    if not cutting_plans:
        return []

    # Create a mapping of position -> shape record for quick lookup
    shape_map = {}
    if shapes_to_cut_records:
        for shape in shapes_to_cut_records:
            if shape.cut_position:
                shape_map[shape.cut_position] = shape

    svg_list = []
    for stock_idx, stock_plan in enumerate(cutting_plans):
        # Validate required keys
        if not all(key in stock_plan for key in ["stock_width", "stock_length", "cut_pattern"]):
            continue

        ET.register_namespace('', "http://www.w3.org/2000/svg")
        stock_width = stock_plan.get("stock_width", 1000)
        stock_length = stock_plan.get("stock_length", 1000)
        stock_description = escape(stock_plan.get("stock_description", f"Stock_{stock_idx}"))
        cutting_plan_number = f"{package_name or 'Unnamed'}_CP{stock_idx + 1:03d}"
        pieces = stock_plan.get("pieces", 1)

        # Define target dimensions with a cap on height
        target_width = 500
        max_text_lines = 50
        target_height = min(700, max(300, stock_length * 0.3))

        # Calculate scaling factor
        rect_width = target_width * 0.6
        scale_x = rect_width / max(stock_width, 1)
        scale_y = target_height / max(stock_length, 1)
        scale = min(scale_x, scale_y)

        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "version": "1.1",
            "width": "500px",
            "height": f"{target_height}px",
            "viewBox": f"0 0 {target_width} {target_height}"
        })

        # Stock rectangle (background)
        ET.SubElement(svg, "rect", {
            "x": "0",
            "y": "0",
            "width": str(stock_width * scale),
            "height": str(stock_length * scale),
            "fill": "lightgray",
            "fill-opacity": "0.1",
            "stroke": "black",
            "stroke-width": "2"
        })

        # Draw cut shapes (polygons)
        for cut_item in stock_plan.get("cut_pattern", []):
            if not all(key in cut_item for key in ["x", "y", "rotation", "cut_position"]):
                continue

            cut_position = cut_item.get("cut_position")
            x = cut_item.get("x", 0)
            y = cut_item.get("y", 0)
            rotation = cut_item.get("rotation", 0)

            # Apply margin translation
            x_translated = x + margin_left
            y_translated = y + margin_bottom

            # Get polygon data from shape record
            shape_record = shape_map.get(cut_position)
            if not shape_record or not shape_record.outer_polygon_json:
                # Fallback: draw bounding box if polygon data not available
                width = cut_item.get("width", 0)
                length = cut_item.get("length", 0)
                cut_rect_elem = ET.SubElement(svg, "rect", {
                    "x": str(x_translated * scale),
                    "y": str(y_translated * scale),
                    "width": str(width * scale),
                    "height": str(length * scale),
                    "fill": "none",
                    "stroke": "red",
                    "stroke-width": "1"
                })
                if rotation != 0:
                    center_x = (x_translated + width / 2) * scale
                    center_y = (y_translated + length / 2) * scale
                    cut_rect_elem.set("transform", f"rotate({rotation} {center_x} {center_y})")
                continue

            try:
                # Load polygon data
                outer_poly_points = json.loads(shape_record.outer_polygon_json)
                if not outer_poly_points or len(outer_poly_points) < 3:
                    continue

                # Create Shapely polygon
                inner_polys = []
                if shape_record.inner_polygons_json:
                    try:
                        inner_polys = json.loads(shape_record.inner_polygons_json)
                    except json.JSONDecodeError:
                        pass

                if inner_polys:
                    polygon = Polygon(outer_poly_points, inner_polys)
                else:
                    polygon = Polygon(outer_poly_points)

                if not polygon.is_valid:
                    polygon = polygon.buffer(0)

                # Apply transformation: rotate around origin (0,0), then translate
                # The polygon is already normalized at origin, so we rotate it first
                if rotation != 0:
                    polygon = rotate(polygon, rotation, origin=(0, 0))
                # Then translate to the final position
                polygon = translate(polygon, xoff=x_translated, yoff=y_translated)

                # Convert polygon to SVG path
                # Outer ring
                if polygon.exterior:
                    coords = list(polygon.exterior.coords)
                    if len(coords) > 0:
                        path_data = f"M {coords[0][0] * scale},{coords[0][1] * scale}"
                        for coord in coords[1:]:
                            path_data += f" L {coord[0] * scale},{coord[1] * scale}"
                        path_data += " Z"

                        # Create path element
                        path_elem = ET.SubElement(svg, "path", {
                            "d": path_data,
                            "fill": "none",
                            "stroke": "red",
                            "stroke-width": "1"
                        })

                # Inner rings (holes)
                if hasattr(polygon, 'interiors'):
                    for interior in polygon.interiors:
                        coords = list(interior.coords)
                        if len(coords) > 0:
                            path_data = f"M {coords[0][0] * scale},{coords[0][1] * scale}"
                            for coord in coords[1:]:
                                path_data += f" L {coord[0] * scale},{coord[1] * scale}"
                            path_data += " Z"

                            path_elem = ET.SubElement(svg, "path", {
                                "d": path_data,
                                "fill": "white",
                                "stroke": "red",
                                "stroke-width": "1"
                            })

            except Exception as e:
                _logger.warning(f"Error rendering polygon for {cut_position}: {e}")
                # Fallback to bounding box
                width = cut_item.get("width", 0)
                length = cut_item.get("length", 0)
                cut_rect_elem = ET.SubElement(svg, "rect", {
                    "x": str(x_translated * scale),
                    "y": str(y_translated * scale),
                    "width": str(width * scale),
                    "height": str(length * scale),
                    "fill": "none",
                    "stroke": "red",
                    "stroke-width": "1"
                })
                if rotation != 0:
                    center_x = (x_translated + width / 2) * scale
                    center_y = (y_translated + length / 2) * scale
                    cut_rect_elem.set("transform", f"rotate({rotation} {center_x} {center_y})")

        # Calculate waste
        stock_area = stock_width * stock_length
        cut_area = sum(cut_item.get("area", 0) for cut_item in stock_plan.get("cut_pattern", []))
        waste_area = stock_area - cut_area
        waste_percentage = (waste_area / stock_area * 100) if stock_area > 0 else 0

        # Text content with truncation
        text_lines = [
            f"CUTTING PLAN:",
            f"{cutting_plan_number}",
            f"##_{stock_idx + 1}, {stock_description}",
            f"{stock_width:.1f} x {stock_length:.1f} mm, {pieces} pcs",
            f"Waste {waste_percentage:.2f}%",
            " "
        ]

        # Group cut pieces
        cut_groups = {}
        for cut_item in stock_plan.get("cut_pattern", []):
            pos = escape(cut_item.get("cut_position", "N/A"))
            desc = escape(cut_item.get("cut_description", "N/A"))
            area = cut_item.get("area", 0)
            key = (pos, desc, area)
            if key not in cut_groups:
                cut_groups[key] = []
            cut_groups[key].append({
                "x": cut_item.get("x", 0) + margin_left,
                "y": cut_item.get("y", 0) + margin_bottom,
                "rotation": cut_item.get("rotation", 0)
            })

        # Add cut pieces info, truncate if too long
        line_count = len(text_lines)
        for (pos, desc, area), placements in cut_groups.items():
            if line_count + 2 + len(placements) > max_text_lines:
                text_lines.append("... (additional pieces truncated)")
                break
            text_lines.append(f"##_{pos}, {desc}")
            text_lines.append(f"Area: {area:.1f} mm² - {len(placements)} pcs")
            line_count += 2
            for i, placement in enumerate(placements, 1):
                if line_count >= max_text_lines:
                    text_lines.append("... (details truncated)")
                    break
                text_lines.append(
                    f"\t\t{i}. x: {placement['x']:.1f}, "
                    f"y: {placement['y']:.1f}, rotation: {placement['rotation']:.1f}°"
                )
                line_count += 1

        # Add text to SVG
        text_x = stock_width * scale + 10
        text_y_start = 14
        font_size = 10
        line_height = 12
        text = ET.SubElement(svg, "text", {
            "x": str(text_x),
            "y": str(text_y_start),
            "font-family": "Arial, sans-serif",
            "font-size": str(font_size),
            "fill": "black"
        })
        for i, line in enumerate(text_lines):
            ET.SubElement(text, "tspan", {
                "x": str(text_x),
                "dy": str(line_height) if i > 0 else "0"
            }).text = line

        # Ensure SVG height accommodates text
        required_height = max(target_height, text_y_start + len(text_lines) * line_height)
        svg.set("height", f"{required_height}px")
        svg.set("viewBox", f"0 0 {target_width} {required_height}")

        svg_string = ET.tostring(svg, encoding='utf-8', method='xml').decode('utf-8')
        svg_list.append(svg_string)

    return svg_list


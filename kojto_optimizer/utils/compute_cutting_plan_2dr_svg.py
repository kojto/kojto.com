import json
from xml.etree import ElementTree as ET
from typing import Union, List, Dict, Optional
from html import escape

def compute_cutting_plan_2dr_svg(
    cutting_plan_json: Union[str, Dict, List[Dict]],
    package_name: Optional[str] = None,
    margin_left: float = 0.0,
    margin_bottom: float = 0.0
) -> List[str]:
    """
    Generate SVG strings for 2D cutting plans based on the provided cutting_plan_json.

    Args:
        cutting_plan_json: The cutting plan JSON data (string, dict, or list of dicts).
            Expected structure: {"cutting_plans": [{"stock_width", "stock_length", "cut_pattern", ...}, ...]}
            or a list of such dictionaries.
        package_name: Optional name of the package for naming cutting plans.
        margin_left: Left margin to translate cut rectangle coordinates (x direction).
        margin_bottom: Bottom margin to translate cut rectangle coordinates (y direction).

    Returns:
        List of SVG strings, each representing a cutting plan.

    Raises:
        json.JSONDecodeError: If cutting_plan_json is a string but not valid JSON.
        ValueError: If cutting_plan_json is empty or lacks valid cutting plans.
    """
    # Parse JSON if it's a string
    if isinstance(cutting_plan_json, str):
        try:
            cutting_plan_json = json.loads(cutting_plan_json)
        except json.JSONDecodeError as e:
            return []

    # Handle case where cutting_plan_json is a list of plans
    if isinstance(cutting_plan_json, list):
        cutting_plans = [plan.get("cutting_plans", []) for plan in cutting_plan_json if "cutting_plans" in plan]
        cutting_plans = [plan for sublist in cutting_plans for plan in sublist]
    else:
        cutting_plans = cutting_plan_json.get("cutting_plans", [])

    if not cutting_plans:
        return []

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
        max_text_lines = 50  # Limit text lines to fit typical page
        target_height = min(700, max(300, stock_length * 0.3))  # Cap height

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

        # Stock rectangle
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

        # Cut rectangles
        for cut_rect in stock_plan.get("cut_pattern", []):
            if not all(key in cut_rect for key in ["width", "length", "x", "y", "rotation"]):
                continue
            cut_width = cut_rect.get("width", 0)
            cut_length = cut_rect.get("length", 0)
            x = cut_rect.get("x", 0)
            y = cut_rect.get("y", 0)
            rotation = cut_rect.get("rotation", 0)

            # Apply margin translation
            x_translated = x + margin_left
            y_translated = y + margin_bottom

            transform = ""
            if rotation == 90:
                transform = f"rotate(90 {x_translated * scale + cut_length * scale} {y_translated * scale})"
                x_adjusted = x_translated + cut_length
                y_adjusted = y_translated
            elif rotation == 180:
                transform = f"rotate(180 {x_translated * scale + cut_width * scale / 2} {y_translated * scale + cut_length * scale / 2})"
                x_adjusted = x_translated
                y_adjusted = y_translated
            elif rotation == 270:
                transform = f"rotate(270 {x_translated * scale} {y_translated * scale + cut_width * scale})"
                x_adjusted = x_translated
                y_adjusted = y_translated + cut_width
            else:
                x_adjusted = x_translated
                y_adjusted = y_translated

            cut_rect_elem = ET.SubElement(svg, "rect", {
                "x": str(x_adjusted * scale),
                "y": str(y_adjusted * scale),
                "width": str(cut_width * scale),
                "height": str(cut_length * scale),
                "fill": "none",
                "stroke": "red",
                "stroke-width": "1"
            })
            if transform:
                cut_rect_elem.set("transform", transform)

        # Calculate waste
        stock_area = stock_width * stock_length
        cut_area = sum(cut_rect.get("width", 0) * cut_rect.get("length", 0)
                       for cut_rect in stock_plan.get("cut_pattern", []))
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
        for cut_rect in stock_plan.get("cut_pattern", []):
            pos = escape(cut_rect.get("cut_position", "N/A"))
            desc = escape(cut_rect.get("cut_description", "N/A"))
            key = (pos, desc, cut_rect["width"], cut_rect["length"])
            if key not in cut_groups:
                cut_groups[key] = []
            cut_groups[key].append({
                "x": cut_rect.get("x", 0) + margin_left,
                "y": cut_rect.get("y", 0) + margin_bottom,
                "rotation": cut_rect.get("rotation", 0)
            })

        # Add cut pieces info, truncate if too long
        line_count = len(text_lines)
        for (pos, desc, width, length), placements in cut_groups.items():
            if line_count + 2 + len(placements) > max_text_lines:
                text_lines.append("... (additional pieces truncated)")
                break
            text_lines.append(f"##_{pos}, {desc}")
            text_lines.append(f"{width:.1f} x {length:.1f} mm - {len(placements)} pcs")
            line_count += 2
            for i, placement in enumerate(placements, 1):
                if line_count >= max_text_lines:
                    text_lines.append("... (details truncated)")
                    break
                text_lines.append(
                    f"\t\t{i}. x: {placement['x']:.1f}, "
                    f"y: {placement['y']:.1f}, rotation: {placement['rotation']}°"
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

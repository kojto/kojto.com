#$ kojto_optimizer/utils/export_2dr_cutting_plan_to_pdf_with_weasyprint.py

import json
import logging
import base64
import tempfile
import os
from xml.etree import ElementTree as ET
from weasyprint import HTML
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def export_2dr_cutting_plan_to_pdf_with_weasyprint(package, template_path=None):
    """
    Export each cutting plan of a 2DR package to a PDF using WeasyPrint, embedding SVGs in an HTML template.
    The text for each cutting plan is placed to the right of the stock rectangle.

    Args:
        package: The package record containing the cutting_plan_json.
        template_path: Path to your custom WeasyPrint HTML template (optional).

    Returns:
        dict: An action to download the generated PDF file.
    """
    if not package.cutting_plan_json:
        raise UserError("No cutting plan JSON available. Please ensure the cutting plan JSON is valid.")

    # Parse JSON with error handling
    try:
        cutting_plan_json = json.loads(package.cutting_plan_json)
    except json.JSONDecodeError as e:
        _logger.error(f"Invalid JSON in cutting_plan_json for package {package.id}: {str(e)}")
        raise UserError("Invalid cutting plan JSON. Please ensure the JSON is valid.")

    # Handle case where cutting_plan_json is a list of plans
    if isinstance(cutting_plan_json, list):
        cutting_plans = [plan.get("cutting_plans", []) for plan in cutting_plan_json if "cutting_plans" in plan]
        cutting_plans = [plan for sublist in cutting_plans for plan in sublist]  # Flatten the list
    else:
        cutting_plans = cutting_plan_json.get("cutting_plans", [])

    if not cutting_plans:
        raise UserError("No valid cutting plans found in the JSON.")

    # Default HTML template if none provided
    default_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page { size: A4; margin: 1cm; }
            body { font-family: Arial, sans-serif; }
            .cutting-plan { page-break-after: always; margin-bottom: 20px; }
            .svg-container { width: 100%; max-width: 1200px; margin: 0 auto; }
            h1 { text-align: center; }
        </style>
    </head>
    <body>
        <h1>Cutting Plans for {package_name}</h1>
        {svg_content}
    </body>
    </html>
    """

    svg_html_content = ""

    for stock_idx, stock_plan in enumerate(cutting_plans):
        # Stock dimensions and info
        stock_width = stock_plan.get("stock_width", 1000)
        stock_length = stock_plan.get("stock_length", 1000)
        stock_description = stock_plan.get("stock_description", f"Stock_{stock_idx}")
        cutting_plan_number = stock_plan.get("cutting_plan_number", f"CP_{stock_idx:03d}")
        pieces = stock_plan.get("pieces", 1)

        # Scale factor to fit SVG viewBox (stock rectangle on the left)
        scale_x = 500 / max(stock_width, 1)  # Allocate 500 units width for the stock
        scale_y = 500 / max(stock_length, 1)  # Allocate 500 units height for the stock
        scale = min(scale_x, scale_y)

        # Calculate SVG dimensions: stock on the left, text on the right
        stock_scaled_width = stock_width * scale
        stock_scaled_height = stock_length * scale
        text_width = 700  # Allocate space for text on the right
        svg_width = stock_scaled_width + text_width + 100  # Padding on both sides
        svg_height = max(stock_scaled_height, 500) + 100  # Ensure enough height for text

        # Create SVG
        ET.register_namespace('', "http://www.w3.org/2000/svg")
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "version": "1.1",
            "width": str(svg_width),
            "height": str(svg_height),
            "viewBox": f"0 0 {svg_width} {svg_height}"
        })

        # Draw stock rectangle (gray)
        ET.SubElement(svg, "rect", {
            "x": "50", "y": "50",
            "width": str(stock_scaled_width),
            "height": str(stock_scaled_height),
            "fill": "lightgray",
            "stroke": "black",
            "stroke-width": "2"
        })

        # Calculate waste percentage and gather cut positions
        stock_area = stock_width * stock_length
        cut_area = 0
        cut_pattern_text = []
        margin_left = getattr(package, 'margin_left', 0.0) or 0.0
        margin_bottom = getattr(package, 'margin_bottom', 0.0) or 0.0
        for cut_rect in stock_plan.get("cut_pattern", []):
            cut_area += cut_rect.get("width", 0) * cut_rect.get("length", 0)
            # Collect cut position details for text (with margin translation)
            x_translated = cut_rect.get('x', 0) + margin_left
            y_translated = cut_rect.get('y', 0) + margin_bottom
            cut_pattern_text.append(
                f"Cut: {cut_rect.get('cut_position', 'N/A')} "
                f"X:{x_translated:.1f} Y:{y_translated:.1f} "
                f"W:{cut_rect.get('width', 0)} L:{cut_rect.get('length', 0)} "
                f"Rot:{cut_rect.get('rotation', 0)}"
            )
        waste_area = stock_area - cut_area
        waste_percentage = (waste_area / stock_area * 100) if stock_area > 0 else 0

        # Add text information to the right of the stock rectangle
        text_content = (
            f"Cutting_plan_number: {cutting_plan_number}\n"
            f"Stock_position: {stock_plan.get('stock_position', str(stock_idx))}\n"
            f"Stock_description: {stock_description}\n"
            f"Stock_width: {stock_width}\n"
            f"Stock_length: {stock_length}\n"
            f"Pieces: {pieces}\n"
            f"Waste_percentage: {waste_percentage:.1f}%\n"
            "\n"  # Empty line for separation
            "Cut Positions:\n"
            f"{'\\n'.join(cut_pattern_text)}"
        )
        text = ET.SubElement(svg, "text", {
            "x": str(50 + stock_scaled_width + 20),  # Position to the right of the stock
            "y": "50",
            "font-family": "Arial",
            "font-size": "16",
            "fill": "black"
        })
        for i, line in enumerate(text_content.split('\n')):
            ET.SubElement(text, "tspan", {
                "x": str(50 + stock_scaled_width + 20),
                "dy": "20" if i > 0 else "0"
            }).text = line

        # Draw cut rectangles (red)
        for cut_rect in stock_plan.get("cut_pattern", []):
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
                transform = f"rotate(90 {x_translated * scale + 50 + cut_length * scale} {y_translated * scale + 50})"
                x_adjusted = x_translated + cut_length
                y_adjusted = y_translated
            else:
                x_adjusted = x_translated
                y_adjusted = y_translated

            cut_rect_elem = ET.SubElement(svg, "rect", {
                "x": str(x_adjusted * scale + 50),
                "y": str(y_adjusted * scale + 50),
                "width": str(cut_width * scale),
                "height": str(cut_length * scale),
                "fill": "none",
                "stroke": "red",
                "stroke-width": "1"
            })
            if transform:
                cut_rect_elem.set("transform", transform)

        # Convert SVG to string and encode for HTML embedding
        svg_string = ET.tostring(svg, encoding='utf-8', method='xml').decode('utf-8')
        svg_html_content += f"""
        <div class="cutting-plan">
            <div class="svg-container">
                {svg_string}
            </div>
        </div>
        """

    # Use provided template or default
    if template_path and os.path.exists(template_path):
        with open(template_path, 'r') as f:
            html_template = f.read()
    else:
        html_template = default_template

    # Fill template with SVG content
    html_content = html_template.format(
        package_name=package.name,
        svg_content=svg_html_content
    )

    # Generate PDF with WeasyPrint
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        HTML(string=html_content).write_pdf(tmp_file.name)
        with open(tmp_file.name, 'rb') as f:
            pdf_content = f.read()
        os.unlink(tmp_file.name)

    # Store PDF content in a field
    package.write({
        'cutting_plan_pdf': base64.b64encode(pdf_content)
    })

    # Return action to download the PDF
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{package._name}/{package.id}/cutting_plan_pdf/{package.name}_cutting_plans.pdf?download=true',
        'target': 'self',
    }

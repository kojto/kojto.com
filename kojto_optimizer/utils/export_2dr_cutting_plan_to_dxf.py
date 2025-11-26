#$ kojto_optimizer/utils/export_2dr_cutting_plan_to_dxf.py

import json
import logging
import base64
import ezdxf
import tempfile
import os
from ezdxf.math import Vec2
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def export_2dr_cutting_plan_to_dxf(package):
    """
    Export the cutting plan of a 2DR package to a DXF file with one stock insert per unique cutting plan,
    and insert MTEXT with stock information and cut positions specific to each cutting plan.

    Args:
        package: The package record containing the cutting_plan_json.

    Returns:
        dict: An action to download the generated DXF file.
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

    # Create a new DXF document
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # Define layers
    doc.layers.new('StockRectangles', dxfattribs={'color': 8})  # Gray
    doc.layers.new('CutRectangles', dxfattribs={'color': 1})    # Red
    doc.layers.new('Text', dxfattribs={'color': 7})            # Black for text

    # Collect unique stock blocks (one per unique stock geometry)
    stock_blocks = {}
    for stock_idx, stock_plan in enumerate(cutting_plans):
        stock_key = (
            stock_plan.get("stock_position", str(stock_idx)),
            stock_plan.get("stock_width", 1000),
            stock_plan.get("stock_length", 1000),
            stock_plan.get("stock_description", f"Stock_{stock_idx}")
        )
        if stock_key not in stock_blocks:
            block_name = f"Stock_{stock_key[0]}_{stock_key[1]}x{stock_key[2]}"
            stock_blocks[stock_key] = {
                "name": block_name,
                "width": stock_key[1],
                "length": stock_key[2],
                "description": stock_key[3],
                "pieces": stock_plan.get("pieces", 1),
                "cutting_plan_number": stock_plan.get("cutting_plan_number", f"CP_{stock_idx:03d}")
            }

    # Collect unique cut positions across all cutting plans
    cut_positions = {}
    for stock_idx, stock_plan in enumerate(cutting_plans):
        for cut_rect in stock_plan.get("cut_pattern", []):
            cut_key = (
                cut_rect.get("cut_position", f"Cut_{stock_idx}"),
                cut_rect.get("width", 0),
                cut_rect.get("length", 0),
                cut_rect.get("cut_description", f"Cut_{stock_idx}")
            )
            if cut_key not in cut_positions:
                cut_positions[cut_key] = {
                    "width": cut_key[1],
                    "length": cut_key[2],
                    "description": cut_key[3]
                }

    # Create stock blocks (without MTEXT here)
    stock_block_map = {}
    for stock_key, stock_data in stock_blocks.items():
        block_name = stock_data["name"]
        block = doc.blocks.new(block_name)

        # Add stock rectangle
        stock_points = [
            (0, 0),
            (stock_data["width"], 0),
            (stock_data["width"], stock_data["length"]),
            (0, stock_data["length"]),
            (0, 0),
        ]
        block.add_lwpolyline(stock_points, dxfattribs={"layer": "StockRectangles"})
        stock_block_map[stock_key] = block_name

    # Create cut blocks
    cut_block_map = {}
    for cut_key, cut_data in cut_positions.items():
        block_name = f"Cut_{cut_key[0]}_{cut_key[1]}x{cut_key[2]}"
        block = doc.blocks.new(block_name)
        cut_points = [
            (0, 0),
            (cut_data["width"], 0),
            (cut_data["width"], cut_data["length"]),
            (0, cut_data["length"]),
            (0, 0),
        ]
        block.add_lwpolyline(cut_points, dxfattribs={"layer": "CutRectangles"})
        cut_block_map[cut_key] = block_name

    # Insert stock blocks with their cut patterns and unique MTEXT
    current_offset_x = 0
    for stock_idx, stock_plan in enumerate(cutting_plans):
        stock_key = (
            stock_plan.get("stock_position", str(stock_idx)),
            stock_plan.get("stock_width", 1000),
            stock_plan.get("stock_length", 1000),
            stock_plan.get("stock_description", f"Stock_{stock_idx}")
        )
        stock_data = stock_blocks[stock_key]
        stock_width = stock_data["width"]
        block_name = stock_block_map[stock_key]

        # Insert stock block once per cutting plan entry
        insert_x = current_offset_x
        stock_insert_point = (insert_x, 0)
        msp.add_blockref(block_name, stock_insert_point, dxfattribs={"layer": "StockRectangles"})

        # Calculate waste percentage and gather cut pattern for this specific stock plan
        stock_area = stock_data["width"] * stock_data["length"]
        cut_area = 0
        cut_pattern_text = []
        margin_left = getattr(package, 'margin_left', 0.0) or 0.0
        margin_bottom = getattr(package, 'margin_bottom', 0.0) or 0.0
        for cut_rect in stock_plan.get("cut_pattern", []):
            cut_area += cut_rect.get("width", 0) * cut_rect.get("length", 0)
            # Collect cut position details for MTEXT (with margin translation)
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

        # Create MTEXT with stock information, cutting_plan_number, and cut positions for this specific plan
        text_content = (
            f"Cutting_plan_number: {stock_plan.get('cutting_plan_number', f'CP_{stock_idx:03d}')}\\P"
            f"Stock_position: {stock_key[0]}\\P"
            f"Stock_description: {stock_data['description']}\\P"
            f"Stock_width: {stock_data['width']}\\P"
            f"Stock_length: {stock_data['length']}\\P"
            f"Pieces: {stock_plan.get('pieces', 1)}\\P"
            f"Waste_percentage: {waste_percentage:.1f}%\\P"
            "\P"  # Empty line for separation
            "Cut Positions:\\P"
            f"{'\\P'.join(cut_pattern_text)}"
        )
        msp.add_mtext(
            text_content,
            dxfattribs={
                "layer": "Text",
                "style": "Standard",
                "char_height": 30,
                "width": 1500,
                "insert": (insert_x + 50, -200),  # Position relative to stock insertion point
                "attachment_point": 1  # Top-left alignment
            }
        )

        # Insert cut blocks within this stock
        for cut_rect in stock_plan.get("cut_pattern", []):
            cut_key = (
                cut_rect.get("cut_position", f"Cut_{stock_idx}"),
                cut_rect.get("width", 0),
                cut_rect.get("length", 0),
                cut_rect.get("cut_description", f"Cut_{stock_idx}")
            )
            cut_block_name = cut_block_map[cut_key]

            # Get base position
            base_x = cut_rect.get("x", 0)
            base_y = cut_rect.get("y", 0)
            rotation = cut_rect.get("rotation", 0)

            # Apply margin translation
            margin_left = getattr(package, 'margin_left', 0.0) or 0.0
            margin_bottom = getattr(package, 'margin_bottom', 0.0) or 0.0
            base_x_translated = base_x + margin_left
            base_y_translated = base_y + margin_bottom

            # Adjust insertion point based on +90 degree rotation
            if rotation == 90:
                insert_x_adjusted = base_x_translated + cut_rect.get("length", 0)
                insert_y_adjusted = base_y_translated
            else:
                insert_x_adjusted = base_x_translated
                insert_y_adjusted = base_y_translated

            # Apply stock offset and create insertion point
            insert_point = Vec2(insert_x_adjusted, insert_y_adjusted) + Vec2(insert_x, 0)

            msp.add_blockref(
                cut_block_name,
                insert_point,
                dxfattribs={
                    "layer": "CutRectangles",
                    "rotation": rotation
                }
            )

        # Update offset for the next stock
        current_offset_x += stock_width + 100

    # Save the DXF file to a temporary file and read it into a binary string
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp_file:
        doc.saveas(tmp_file.name)
        with open(tmp_file.name, 'rb') as f:
            dxf_content = f.read()
        os.unlink(tmp_file.name)

    # Store the DXF content in the autocad_dxf field for download
    package.autocad_dxf = base64.b64encode(dxf_content)

    # Return a URL for downloading the DXF file
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{package._name}/{package.id}/autocad_dxf/{package.name}_cutting_plan.dxf?download=true',
        'target': 'self',
    }

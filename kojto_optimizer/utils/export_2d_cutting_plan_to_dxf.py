# kojto_optimizer/utils/export_2d_cutting_plan_to_dxf.py

import json
import logging
import base64
import ezdxf
import tempfile
import os
from ezdxf.math import Vec2, Matrix44
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def export_2d_cutting_plan_to_dxf(package):
    """
    Export the cutting plan of a 2D package to a DXF file with one stock insert per unique cutting plan,
    and insert MTEXT with stock information and cut positions specific to each cutting plan.
    Uses actual polygon shapes from normalized DXF entities instead of rectangles.

    Args:
        package: The package record containing the cutting_plan_json.

    Returns:
        dict: An action to download the generated DXF file.
    """
    if not package.cutting_plan_json:
        raise UserError(
            "No cutting plan JSON available.\n"
            "Please compute the cutting plan first by clicking 'Compute Cutting Plan' or saving the package."
        )

    # Parse JSON with error handling
    try:
        cutting_plan_json = json.loads(package.cutting_plan_json)
    except json.JSONDecodeError as e:
        _logger.error(f"Invalid JSON in cutting_plan_json for package {package.id}: {str(e)}")
        raise UserError("Invalid cutting plan JSON. Please ensure the JSON is valid.")

    # Check if the cutting plan generation was successful
    if isinstance(cutting_plan_json, dict) and not cutting_plan_json.get("success", True):
        error_message = cutting_plan_json.get("message", "Unknown error")
        error_details = cutting_plan_json.get("error_details", {})
        _logger.error(f"Cutting plan generation failed for package {package.id}: {error_message}")
        raise UserError(
            f"Cannot export DXF: Cutting plan generation failed.\n"
            f"Error: {error_message}\n"
            f"Please recompute the cutting plan first."
        )

    # Handle case where cutting_plan_json is a list of plans
    if isinstance(cutting_plan_json, list):
        cutting_plans = [plan.get("cutting_plans", []) for plan in cutting_plan_json if "cutting_plans" in plan]
        cutting_plans = [plan for sublist in cutting_plans for plan in sublist]  # Flatten the list
    else:
        cutting_plans = cutting_plan_json.get("cutting_plans", [])

    if not cutting_plans:
        # Log detailed information for debugging
        _logger.error(f"No cutting plans found for package {package.id}")
        _logger.error(f"JSON keys: {list(cutting_plan_json.keys()) if isinstance(cutting_plan_json, dict) else 'Not a dict'}")
        _logger.error(f"Success status: {cutting_plan_json.get('success') if isinstance(cutting_plan_json, dict) else 'N/A'}")
        _logger.error(f"Message: {cutting_plan_json.get('message') if isinstance(cutting_plan_json, dict) else 'N/A'}")

        error_msg = "No valid cutting plans found in the JSON."
        if isinstance(cutting_plan_json, dict):
            if not cutting_plan_json.get("success", True):
                error_msg = f"Cannot export DXF: {cutting_plan_json.get('message', 'Cutting plan generation failed')}"
            elif cutting_plan_json.get("cutting_plans") == []:
                error_msg = "Cannot export DXF: No cutting plans were generated. Please ensure you have stock rectangles and shapes to cut, then recompute the cutting plan."

        raise UserError(error_msg)

    # Create a mapping of cut_position to shape record
    shapes_map = {}
    for shape in package.shapes_to_cut_ids:
        shapes_map[shape.cut_position] = shape

    # Create a new DXF document
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # Define layers FIRST (before creating blocks)
    doc.layers.new('StockRectangles', dxfattribs={'color': 8})  # Gray
    doc.layers.new('CutShapes', dxfattribs={'color': 1})       # Red
    doc.layers.new('Text', dxfattribs={'color': 7})            # Black for text

    # Create blocks for each unique shape (based on cut_position)
    # Blocks will contain the normalized DXF entities at origin (0,0)
    shape_blocks = {}
    for cut_position, shape in shapes_map.items():
        if not shape.normalized_dxf_entities_json:
            _logger.warning(f"No normalized_dxf_entities_json for shape {cut_position}")
            continue

        try:
            normalized_entities = json.loads(shape.normalized_dxf_entities_json)
            if not normalized_entities:
                _logger.warning(f"Empty normalized_entities for shape {cut_position}")
                continue
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error for shape {cut_position}: {e}")
            continue

        # Create a unique block name for this shape
        # DXF block names have restrictions: no spaces, special chars, max 255 chars
        # Replace problematic characters with underscores
        sanitized_name = str(cut_position).replace(' ', '_').replace('/', '_').replace('\\', '_')
        sanitized_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in sanitized_name)
        block_name = f"Shape_{sanitized_name}"[:255]  # Limit to 255 chars

        # Check if block already exists (by trying to access it)
        try:
            existing_block = doc.blocks[block_name]
            # Block already exists, reuse it
            shape_blocks[cut_position] = block_name
            _logger.info(f"Reusing existing block {block_name} for shape {cut_position}")
            continue
        except KeyError:
            # Block doesn't exist yet, will create it
            pass

        # Check if we've already created this block in this session
        if block_name in shape_blocks.values():
            # Find the existing cut_position that uses this block name
            for existing_pos, existing_block in shape_blocks.items():
                if existing_block == block_name:
                    shape_blocks[cut_position] = existing_block
                    _logger.info(f"Sharing block {block_name} between {existing_pos} and {cut_position}")
                    break
            continue  # Block already created

        # Create the block
        try:
            block = doc.blocks.new(block_name)
            _logger.info(f"Created block {block_name} for shape {cut_position} with {len(normalized_entities)} entities")
        except Exception as e:
            _logger.error(f"Failed to create block {block_name}: {e}")
            continue

        # Add normalized entities to the block (at origin, no transformation)
        entities_added = _add_entities_to_block(block, normalized_entities, "CutShapes")
        if entities_added == 0:
            _logger.warning(f"No entities were added to block {block_name} for shape {cut_position}. Normalized entities: {len(normalized_entities)}")
            # Don't add empty blocks to shape_blocks
            continue
        else:
            _logger.info(f"Added {entities_added} entities to block {block_name} for shape {cut_position}")

        shape_blocks[cut_position] = block_name

        # Verify block was created and has entities
        try:
            verify_block = doc.blocks[block_name]
            entity_count = len(list(verify_block))
            _logger.debug(f"Verified block {block_name} exists with {entity_count} entities")
        except Exception as e:
            _logger.error(f"Failed to verify block {block_name}: {e}")

    _logger.info(f"Created {len(shape_blocks)} shape blocks: {list(shape_blocks.keys())}")
    _logger.info(f"Total blocks in document: {len(doc.blocks)}")

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

    # Create stock blocks
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

    # Insert stock blocks with their cut patterns and unique MTEXT
    current_offset_x = 0
    margin_left = getattr(package, 'margin_left', 0.0) or 0.0
    margin_bottom = getattr(package, 'margin_bottom', 0.0) or 0.0

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

        for cut_rect in stock_plan.get("cut_pattern", []):
            # Use actual shape area if available, otherwise use bounding box area
            cut_position = cut_rect.get('cut_position', '')
            shape = shapes_map.get(cut_position)
            if shape and shape.shape_area:
                cut_area += shape.shape_area
            else:
                # Fallback to bounding box area
                cut_area += cut_rect.get("width", 0) * cut_rect.get("length", 0)

            # Collect cut position details for MTEXT (with margin translation)
            x_translated = cut_rect.get('x', 0) + margin_left
            y_translated = cut_rect.get('y', 0) + margin_bottom
            rotation = cut_rect.get('rotation', 0)
            cut_pattern_text.append(
                f"Cut: {cut_rect.get('cut_position', 'N/A')} "
                f"X:{x_translated:.1f} Y:{y_translated:.1f} "
                f"W:{cut_rect.get('width', 0):.1f} L:{cut_rect.get('length', 0):.1f} "
                f"Rot:{rotation:.1f}"
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

        # Insert cut shapes within this stock using blocks
        blocks_inserted_count = 0
        for cut_rect in stock_plan.get("cut_pattern", []):
            cut_position = cut_rect.get("cut_position", "")

            # Get the block name for this shape
            block_name = shape_blocks.get(cut_position)
            if not block_name:
                _logger.warning(f"Block not found for cut_position: {cut_position}. Available blocks: {list(shape_blocks.keys())}")
                continue

            # Verify block exists in document
            try:
                test_block = doc.blocks[block_name]
            except KeyError:
                available_blocks = [b.name for b in doc.blocks if hasattr(b, 'name')][:10]
                _logger.error(f"Block {block_name} not found in document blocks. Available blocks: {available_blocks}")
                continue

            # Get transformation for positioning on the sheet
            # The cutting plan gives us x, y position and rotation on the stock
            # Normalized entities are at origin (0,0) and horizontal in the block
            # We need to: 1) translate to position, 2) apply rotation, 3) apply stock offset

            # Base position from cutting plan
            base_x = cut_rect.get("x", 0)
            base_y = cut_rect.get("y", 0)
            rotation = cut_rect.get("rotation", 0)  # in degrees

            # Apply margin translation
            base_x_translated = base_x + margin_left
            base_y_translated = base_y + margin_bottom

            # Apply stock offset
            final_x = base_x_translated + insert_x
            final_y = base_y_translated

            # Insert the block with rotation and translation
            # ezdxf block insertion: insert point, rotation in degrees, xscale, yscale
            insert_point = (final_x, final_y)
            rotation_rad = rotation * 3.141592653589793 / 180.0  # Convert to radians

            # Add block reference with rotation
            try:
                blockref = msp.add_blockref(block_name, insert_point, dxfattribs={"layer": "CutShapes"})
                if rotation != 0:
                    blockref.rotation = rotation_rad
                blocks_inserted_count += 1
                _logger.debug(f"Inserted block {block_name} at ({final_x:.2f}, {final_y:.2f}) with rotation {rotation:.2f}°")
            except Exception as e:
                _logger.error(f"Failed to insert block {block_name}: {e}")

        _logger.info(f"Inserted {blocks_inserted_count} block references for cutting plan {stock_plan.get('cutting_plan_number', 'N/A')}")

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


def _add_entities_to_block(block, normalized_entities, layer):
    """
    Add normalized DXF entities to a block (at origin, no transformation).

    Args:
        block: Block to add entities to
        normalized_entities: List of normalized DXF entity dictionaries
        layer: Layer name for the entities

    Returns:
        int: Number of entities successfully added
    """
    entities_added = 0
    for entity_data in normalized_entities:
        entity_type = entity_data.get('type')
        if not entity_type:
            continue

        try:
            if entity_type == 'LINE':
                start = Vec2(entity_data.get('start', [0, 0]))
                end = Vec2(entity_data.get('end', [0, 0]))
                block.add_line(start, end, dxfattribs={"layer": layer})
                entities_added += 1

            elif entity_type == 'ARC':
                center = Vec2(entity_data.get('center', [0, 0]))
                radius = entity_data.get('radius', 0)
                start_angle = entity_data.get('start_angle', 0)
                end_angle = entity_data.get('end_angle', 360)
                block.add_arc(
                    center,
                    radius,
                    start_angle,
                    end_angle,
                    dxfattribs={"layer": layer}
                )
                entities_added += 1

            elif entity_type == 'CIRCLE':
                center = Vec2(entity_data.get('center', [0, 0]))
                radius = entity_data.get('radius', 0)
                block.add_circle(center, radius, dxfattribs={"layer": layer})
                entities_added += 1

            elif entity_type == 'LWPOLYLINE':
                points = entity_data.get('points', [])
                if points:
                    # Points are already normalized, use directly
                    point_list = [(float(pt[0]), float(pt[1])) for pt in points if len(pt) >= 2]
                    if point_list:
                        block.add_lwpolyline(point_list, dxfattribs={"layer": layer})
                        entities_added += 1

            elif entity_type == 'POLYLINE':
                points = entity_data.get('points', [])
                if points:
                    # Points are already normalized, use directly
                    point_list = [(float(pt[0]), float(pt[1])) for pt in points if len(pt) >= 2]
                    if point_list:
                        polyline = block.add_polyline2d(point_list, dxfattribs={"layer": layer})
                        if entity_data.get('closed', False):
                            polyline.close()
                        entities_added += 1
        except Exception as e:
            _logger.error(f"Error adding {entity_type} entity to block: {e}")
            continue

    return entities_added


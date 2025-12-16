# kojto_optimizer/utils/generate_2dr_cutting_plan.py

import json
from datetime import datetime
from rectpack import newPacker, PackingMode
from rectpack import GuillotineBafLas, MaxRectsBssf, SkylineBl

def generate_2dr_cutting_plan(stock_rectangles_ids, cutted_rectangles_ids, method="maxrects_bssf", width_of_cut=0.0, use_stock_priority=False, allow_cut_rotation=True, package=None, margin_left=0.0, margin_right=0.0, margin_top=0.0, margin_bottom=0.0):
    result = {}

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

    if package:
        try:
            package_id = str(package.id)
            package_name = package.name if package.name else "Unnamed Package"
            package_subcode_id = str(package.subcode_id.id) if package.subcode_id else None
            package_description = package.description if package.description else "No description provided"
            package_date_issue = (package.date_issue.strftime('%Y-%m-%d')
                                   if package.date_issue
                                   else datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            result["id"] = package_id
            result["name"] = package_name
            result["subcode_id"] = package_subcode_id
            result["description"] = package_description
            result["date_issue"] = package_date_issue
        except AttributeError as e:
            return error_result(
                "Cannot create cutting plan - invalid package data",
                {
                    "exception": str(e),
                    "package_repr": repr(package),
                    "package_type": str(type(package))
                }
            )

    def initialize_result():
        result["cutting_plans"] = []
        result["stock_used"] = []
        result["summary"] = {}

    if not stock_rectangles_ids or not cutted_rectangles_ids:
        return error_result(
            "Cannot create cutting plan - missing stock or cut rectangles",
            {
                "stock_rectangles_ids": repr(stock_rectangles_ids),
                "cutted_rectangles_ids": repr(cutted_rectangles_ids)
            }
        )

    valid_methods = [
        "guillotine_baf",
        "maxrects_bssf",
        "skyline_bl"
    ]
    if method not in valid_methods:
        return error_result(
            f"Cannot create cutting plan - invalid optimization method '{method}'",
            {"method": method, "valid_methods": valid_methods}
        )

    if width_of_cut < 0:
        return error_result(
            f"Cannot create cutting plan - width of cut ({width_of_cut}) cannot be negative",
            {"width_of_cut": width_of_cut}
        )

    # Validate margins - ensure they are always positive
    if margin_left < 0:
        return error_result(
            f"Cannot create cutting plan - margin left ({margin_left}) cannot be negative",
            {"margin_left": margin_left}
        )
    if margin_right < 0:
        return error_result(
            f"Cannot create cutting plan - margin right ({margin_right}) cannot be negative",
            {"margin_right": margin_right}
        )
    if margin_top < 0:
        return error_result(
            f"Cannot create cutting plan - margin top ({margin_top}) cannot be negative",
            {"margin_top": margin_top}
        )
    if margin_bottom < 0:
        return error_result(
            f"Cannot create cutting plan - margin bottom ({margin_bottom}) cannot be negative",
            {"margin_bottom": margin_bottom}
        )

    try:
        # Apply margins to stock rectangles - reduce width and length by margins
        stock_data = []
        original_stock_dimensions = {}  # Store original dimensions for display

        for s in stock_rectangles_ids:
            original_width = float(s.stock_width)
            original_length = float(s.stock_length)

            # Calculate effective dimensions after applying margins
            effective_width = original_width - margin_left - margin_right
            effective_length = original_length - margin_top - margin_bottom

            # Store original dimensions for later use
            original_stock_dimensions[s.stock_position] = {
                'original_width': original_width,
                'original_length': original_length,
                'effective_width': effective_width,
                'effective_length': effective_length
            }

            stock_data.append((
                s.stock_position,
                effective_width,
                effective_length,
                int(s.available_stock_rectangle_pieces),
                s.stock_description
            ))

        cut_data = [(c.cut_position, float(c.cut_width), float(c.cut_length),
                    int(c.required_cut_rectangle_pieces), c.cut_description)
                   for c in cutted_rectangles_ids]
    except Exception as e:
        return error_result(
            "Cannot create cutting plan - invalid input data for stock or cut rectangles",
            {
                "exception": str(e),
                "stock_rectangles_ids_type": str(type(stock_rectangles_ids)),
                "cutted_rectangles_ids_type": str(type(cutted_rectangles_ids)),
                "stock_rectangles_ids_repr": repr(stock_rectangles_ids),
                "cutted_rectangles_ids_repr": repr(cutted_rectangles_ids)
            }
        )

    for idx, (pos, width, length, pieces, _) in enumerate(stock_data):
        if width <= 0 or length <= 0 or pieces <= 0:
            return error_result(
                f"Cannot create cutting plan - stock {pos} has invalid dimensions after applying margins (width {width}, length {length}, or pieces {pieces})",
                {
                    "stock_index": idx,
                    "stock_position": pos,
                    "width": width,
                    "length": length,
                    "pieces": pieces,
                    "margin_left": margin_left,
                    "margin_right": margin_right,
                    "margin_top": margin_top,
                    "margin_bottom": margin_bottom
                }
            )
    for idx, (pos, width, length, pieces, _) in enumerate(cut_data):
        if width <= 0 or length <= 0 or pieces <= 0:
            return error_result(
                f"Cannot create cutting plan - cut {pos} has invalid dimensions (width {width}, length {length}, or pieces {pieces})",
                {
                    "cut_index": idx,
                    "cut_position": pos,
                    "width": width,
                    "length": length,
                    "pieces": pieces
                }
            )

    items = []
    for cut_pos, cut_width, cut_length, pieces, cut_desc in cut_data:
        adjusted_width = cut_width + width_of_cut
        adjusted_length = cut_length + width_of_cut
        items.extend([{
            "cut_position": cut_pos,
            "width": cut_width,
            "length": cut_length,
            "adjusted_width": adjusted_width,
            "adjusted_length": adjusted_length,
            "cut_description": cut_desc
        } for _ in range(pieces)])
    items.sort(key=lambda x: x["adjusted_width"] * x["adjusted_length"], reverse=True)

    # Group stock by position for priority-based optimization
    if use_stock_priority:
        # Sort stock data by position
        stock_data = sorted(stock_data, key=lambda x: x[0])  # Sort by stock_position (index 0)

        # Group stock by position
        stock_by_position = {}
        for stock_pos, stock_width, stock_length, stock_pieces, stock_desc in stock_data:
            if stock_pos not in stock_by_position:
                stock_by_position[stock_pos] = []
            stock_by_position[stock_pos].extend([
                (stock_pos, stock_width, stock_length, stock_desc)
                for _ in range(stock_pieces)
            ])

        # Process each position sequentially
        remaining_items = items.copy()
        all_patterns_by_stock = {}
        all_stock_usage = {}

        for stock_pos in sorted(stock_by_position.keys()):
            if not remaining_items:
                break

            # Create stock map for current position only
            stock_map = {}
            bin_index = 0
            for stock_pos_current, stock_width, stock_length, stock_desc in stock_by_position[stock_pos]:
                stock_map[bin_index] = (stock_pos_current, stock_width, stock_length, stock_desc)
                bin_index += 1

            if not stock_map:
                continue

            # Create packer for current position
            if method == "maxrects_bssf":
                packer = newPacker(mode=PackingMode.Offline, pack_algo=MaxRectsBssf, rotation=allow_cut_rotation)
            elif method == "guillotine_baf":
                packer = newPacker(mode=PackingMode.Offline, pack_algo=GuillotineBafLas, rotation=allow_cut_rotation)
            elif method == "skyline_bl":
                packer = newPacker(mode=PackingMode.Offline, pack_algo=SkylineBl, rotation=allow_cut_rotation)

            # Add bins for current position
            for bin_idx, (stock_pos_current, stock_width, stock_length, stock_desc) in stock_map.items():
                packer.add_bin(stock_width, stock_length, bid=(bin_idx, stock_pos_current, stock_desc))

            # Add remaining items
            for i, item in enumerate(remaining_items):
                packer.add_rect(item["adjusted_width"], item["adjusted_length"], rid=i)

            try:
                packer.pack()
            except Exception as e:
                continue  # Skip this position if packing fails

            # Process results for current position
            placed_rects = sum(len(bin.rect_list()) for bin in packer)
            if placed_rects == 0:
                continue  # No items placed in this position

            # Track which items were placed
            placed_item_indices = set()
            patterns_by_stock_current = {}
            stock_usage_current = {}

            for bin in packer:
                bin_idx, stock_pos_current, stock_desc = bin.bid
                if len(bin.rect_list()) > 0:
                    stock_usage_current[stock_pos_current] = stock_usage_current.get(stock_pos_current, 0) + 1
                    cut_pattern = [
                        {
                            "cut_position": remaining_items[rect.rid]["cut_position"],
                            "width": remaining_items[rect.rid]["width"],
                            "length": remaining_items[rect.rid]["length"],
                            "x": rect.x,
                            "y": rect.y,
                            "cut_description": remaining_items[rect.rid]["cut_description"],
                            "rotation": 0 if rect.width == remaining_items[rect.rid]["adjusted_width"] else 90
                        }
                        for rect in bin
                    ]
                    if cut_pattern:
                        pattern_key = "|".join(f"{p['cut_position']}_{p['width']}_{p['length']}_{p['x']}_{p['y']}_{p['rotation']}_{p['cut_description']}"
                                             for p in sorted(cut_pattern, key=lambda x: (x['x'], x['y'])))
                        if stock_pos_current not in patterns_by_stock_current:
                            patterns_by_stock_current[stock_pos_current] = {}
                        patterns_by_stock_current[stock_pos_current][pattern_key] = patterns_by_stock_current[stock_pos_current].get(pattern_key, 0) + 1

                        # Track placed items
                        for rect in bin:
                            placed_item_indices.add(rect.rid)

            # Update global tracking
            for stock_pos_current, patterns in patterns_by_stock_current.items():
                if stock_pos_current not in all_patterns_by_stock:
                    all_patterns_by_stock[stock_pos_current] = {}
                all_patterns_by_stock[stock_pos_current].update(patterns)

            for stock_pos_current, usage in stock_usage_current.items():
                all_stock_usage[stock_pos_current] = all_stock_usage.get(stock_pos_current, 0) + usage

            # Remove placed items from remaining items
            remaining_items = [item for i, item in enumerate(remaining_items) if i not in placed_item_indices]

        # Check if all items were placed
        if remaining_items:
            unplaced_count = len(remaining_items)
            return error_result(
                f"Cannot create cutting plan because of insufficient stock - unable to place {unplaced_count} cut rectangles",
                {
                    "placed_rects": len(items) - unplaced_count,
                    "total_items": len(items),
                    "remaining_items": [item["cut_position"] for item in remaining_items]
                }
            )

        patterns_by_stock = all_patterns_by_stock
        stock_usage = all_stock_usage

    else:
        # Original non-priority logic
        stock_map = {}
        bin_index = 0

        for stock_pos, stock_width, stock_length, stock_pieces, stock_desc in stock_data:
            for _ in range(stock_pieces):
                stock_map[bin_index] = (stock_pos, stock_width, stock_length, stock_desc)
                bin_index += 1

        if not stock_map:
            return error_result(
                "Cannot create cutting plan - no stock rectangles available",
                {"stock_data": stock_data}
            )

        if method == "maxrects_bssf":
            packer = newPacker(mode=PackingMode.Offline, pack_algo=MaxRectsBssf, rotation=allow_cut_rotation)
        elif method == "guillotine_baf":
            packer = newPacker(mode=PackingMode.Offline, pack_algo=GuillotineBafLas, rotation=allow_cut_rotation)
        elif method == "skyline_bl":
            packer = newPacker(mode=PackingMode.Offline, pack_algo=SkylineBl, rotation=allow_cut_rotation)

        for bin_idx, (stock_pos, stock_width, stock_length, stock_desc) in stock_map.items():
            packer.add_bin(stock_width, stock_length, bid=(bin_idx, stock_pos, stock_desc))
        for i, item in enumerate(items):
            packer.add_rect(item["adjusted_width"], item["adjusted_length"], rid=i)

        try:
            packer.pack()
        except Exception as e:
            return error_result(
                "Cannot create cutting plan - packing algorithm failed",
                {
                    "exception": str(e),
                    "stock_map": stock_map,
                    "items": items
                }
            )

        placed_rects = sum(len(bin.rect_list()) for bin in packer)
        if placed_rects < len(items):
            unplaced_count = len(items) - placed_rects
            return error_result(
                f"Cannot create cutting plan because of insufficient stock - unable to place {unplaced_count} cut rectangles",
                {
                    "placed_rects": placed_rects,
                    "total_items": len(items),
                    "stock_map": stock_map,
                    "items": items
                }
            )

        stock_usage = {}
        patterns_by_stock = {}
        for bin in packer:
            bin_idx, stock_pos, stock_desc = bin.bid
            if len(bin.rect_list()) > 0:
                stock_usage[stock_pos] = stock_usage.get(stock_pos, 0) + 1
                cut_pattern = [
                    {
                        "cut_position": items[rect.rid]["cut_position"],
                        "width": items[rect.rid]["width"],
                        "length": items[rect.rid]["length"],
                        "x": rect.x,
                        "y": rect.y,
                        "cut_description": items[rect.rid]["cut_description"],
                        "rotation": 0 if rect.width == items[rect.rid]["adjusted_width"] else 90
                    }
                    for rect in bin
                ]
                if cut_pattern:
                    pattern_key = "|".join(f"{p['cut_position']}_{p['width']}_{p['length']}_{p['x']}_{p['y']}_{p['rotation']}_{p['cut_description']}"
                                         for p in sorted(cut_pattern, key=lambda x: (x['x'], x['y'])))
                    if stock_pos not in patterns_by_stock:
                        patterns_by_stock[stock_pos] = {}
                    patterns_by_stock[stock_pos][pattern_key] = patterns_by_stock[stock_pos].get(pattern_key, 0) + 1

    for stock_pos, used_count in stock_usage.items():
        available = next(s[3] for s in stock_data if s[0] == stock_pos)
        if used_count > available:
            return error_result(
                f"Cannot create cutting plan because of insufficient stock - used {used_count} of {stock_pos}, but only {available} available",
                {
                    "stock_position": stock_pos,
                    "used_count": used_count,
                    "available": available
                }
            )

    initialize_result()

    total_stock_area = sum(w * l * p for _, w, l, p, _ in stock_data)
    total_cut_area = sum(w * l * p for _, w, l, p, _ in cut_data)

    plan_counter = 1
    cutting_plans = result["cutting_plans"]
    package_name_base = result.get("name", "Unnamed Package")
    for stock_pos, patterns in patterns_by_stock.items():
        stock_info = next(s for s in stock_data if s[0] == stock_pos)
        effective_width, effective_length, _, stock_desc = stock_info[1], stock_info[2], stock_info[3], stock_info[4]

        # Get original dimensions for display
        original_dims = original_stock_dimensions.get(stock_pos, {})
        original_width = original_dims.get('original_width', effective_width)
        original_length = original_dims.get('original_length', effective_length)

        for pattern_key, count in patterns.items():
            cut_pattern = []
            for p in pattern_key.split("|"):
                parts = p.split("_")
                cut_pattern.append({
                    "cut_position": parts[0],
                    "width": float(parts[1]),
                    "length": float(parts[2]),
                    "x": float(parts[3]),
                    "y": float(parts[4]),
                    "rotation": int(parts[5]),
                    "cut_description": parts[6]
                })

            used_area = sum(p["width"] * p["length"] for p in cut_pattern)
            # Use effective dimensions for waste calculation
            effective_stock_area = effective_width * effective_length
            waste_percentage = ((effective_stock_area - used_area) / effective_stock_area * 100) if effective_stock_area > 0 else 0

            cutting_plan_number = f"{package_name_base}_CP{plan_counter:03d}"
            cutting_plans.append({
                "cutting_plan_number": cutting_plan_number,
                "stock_position": stock_pos,
                "stock_description": stock_desc,
                "stock_width": original_width,  # Display original width
                "stock_length": original_length,  # Display original length
                "effective_stock_width": effective_width,  # Store effective width
                "effective_stock_length": effective_length,  # Store effective length
                "pieces": count,
                "cut_pattern": cut_pattern,
                "waste_percentage": round(waste_percentage, 2)
            })
            plan_counter += 1

    result["cutting_plans"] = cutting_plans

    stock_used_dict = {}
    for plan in cutting_plans:
        key = (plan["stock_position"], plan["stock_description"], plan["stock_width"], plan["stock_length"])
        if key in stock_used_dict:
            stock_used_dict[key]["pcs"] += plan["pieces"]
        else:
            stock_used_dict[key] = {
                "stock_position": plan["stock_position"],
                "stock_description": plan["stock_description"],
                "stock_width": plan["stock_width"],  # Original width for display
                "stock_length": plan["stock_length"],  # Original length for display
                "effective_stock_width": plan.get("effective_stock_width", plan["stock_width"]),
                "effective_stock_length": plan.get("effective_stock_length", plan["stock_length"]),
                "pcs": plan["pieces"]
            }

    result["stock_used"] = list(stock_used_dict.values())

    total_used_stock_area = sum(
        plan.get("effective_stock_width", plan["stock_width"]) * plan.get("effective_stock_length", plan["stock_length"]) * plan["pieces"]
        for plan in cutting_plans
    )
    total_waste_percentage = (
        (total_used_stock_area - total_cut_area) / total_used_stock_area * 100
        if total_used_stock_area > 0 else 0
    )

    result["summary"] = {
        "total_stock_area": total_stock_area,
        "total_used_stock_area": total_used_stock_area,
        "total_cut_area": total_cut_area,
        "total_waste_percentage": round(total_waste_percentage, 2),
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom
    }

    result["success"] = True
    result["message"] = "success"

    return json.dumps(result, indent=2)

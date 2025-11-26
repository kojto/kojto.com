import json
from binpacking import to_constant_bin_number
from datetime import datetime

def generate_1d_cutting_plan(stock_ids, bar_ids, method="best-fit", width_of_cut=0.0, initial_cut=0.0, final_cut=0.0, use_stock_priority=False, package=None):
    result = {
        "cutting_plans": [],
        "stock_used": [],
        "summary": {},
        "success": False,
        "message": "",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    def error_result(message, error_details=None):
        result.update({
            "success": False,
            "message": message,
            "error_details": error_details or "No additional details available",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return json.dumps(result, indent=2)

    # Validate package data
    if package:
        try:
            package_id = str(package.id)
            package_name = package.name if package.name else "Unnamed Package"
            package_subcode_id = str(package.subcode_id.id) if package.subcode_id else None
            package_description = package.description if package.description else "No description provided"
            package_date_issue = (
                package.date_issue.strftime('%Y-%m-%d')
                if package.date_issue
                else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            result["package"] = {
                "id": package_id,
                "name": package_name,
                "subcode_id": package_subcode_id,
                "description": package_description,
                "date_issue": package_date_issue
            }
        except AttributeError as e:
            return error_result(
                "Cannot create cutting plan - invalid package data provided",
                f"Missing or invalid package field: {str(e)}. Ensure package has valid id, name, subcode_id, description, and date_issue."
            )

    # Validate input data existence
    if not stock_ids:
        return error_result(
            "Cannot create cutting plan - no stock pieces provided",
            "Stock list is empty. Provide at least one valid stock piece with position, length, and pieces."
        )
    if not bar_ids:
        return error_result(
            "Cannot create cutting plan - no bars provided",
            "Bar list is empty. Provide at least one valid bar with position, length, and pieces."
        )

    # Validate optimization method
    valid_methods = ["greedy", "first-fit", "best-fit"]
    if method not in valid_methods:
        return error_result(
            "Cannot create cutting plan - invalid optimization method",
            f"Method '{method}' is not supported. Choose from: {', '.join(valid_methods)}."
        )

    # Validate cut parameters
    if width_of_cut < 0:
        return error_result(
            "Cannot create cutting plan - invalid width of cut",
            f"Width of cut ({width_of_cut}) cannot be negative. Provide a non-negative value."
        )
    if initial_cut < 0:
        return error_result(
            "Cannot create cutting plan - invalid initial cut",
            f"Initial cut ({initial_cut}) cannot be negative. Provide a non-negative value."
        )
    if final_cut < 0:
        return error_result(
            "Cannot create cutting plan - invalid final cut",
            f"Final cut ({final_cut}) cannot be negative. Provide a non-negative value."
        )

    # Process stock and bar data
    try:
        stock_data = [
            (s.stock_position, float(s.stock_length), int(s.available_stock_pieces), s.id, s.stock_description or "No description")
            for s in stock_ids
        ]
        bar_data = [
            (b.bar_position, float(b.bar_length), int(b.required_bar_pieces), b.id, b.bar_description or "No description")
            for b in bar_ids
        ]
    except (AttributeError, ValueError) as e:
        return error_result(
            "Cannot create cutting plan - invalid stock or bar data",
            f"Failed to process input data: {str(e)}. Ensure all stock and bars have valid position, length, pieces, and id."
        )

    # Validate stock and bar dimensions
    for pos, length, pieces, _, desc in stock_data:
        if length <= 0:
            return error_result(
                "Cannot create cutting plan - invalid stock length",
                f"Stock position {pos} ({desc}) has invalid length {length}. Length must be positive."
            )
        if pieces <= 0:
            return error_result(
                "Cannot create cutting plan - invalid stock pieces",
                f"Stock position {pos} ({desc}) has invalid pieces {pieces}. Pieces must be positive."
            )
        if length < initial_cut + final_cut:
            return error_result(
                "Cannot create cutting plan - insufficient stock length for cuts",
                f"Stock position {pos} ({desc}) length ({length}) is less than initial_cut ({initial_cut}) + final_cut ({final_cut})."
            )
    for pos, length, pieces, _, desc in bar_data:
        if length <= 0:
            return error_result(
                "Cannot create cutting plan - invalid bar length",
                f"Bar position {pos} ({desc}) has invalid length {length}. Length must be positive."
            )
        if pieces <= 0:
            return error_result(
                "Cannot create cutting plan - invalid bar pieces",
                f"Bar position {pos} ({desc}) has invalid pieces {pieces}. Pieces must be positive."
            )

    # Prepare items for packing
    items = []
    for bar_pos, bar_len, pieces, bar_id, bar_desc in bar_data:
        adjusted_length = bar_len + width_of_cut
        items.extend([{
            "bar_position": bar_pos,
            "length": bar_len,
            "adjusted_length": adjusted_length,
            "bar_id": str(bar_id),
            "bar_description": bar_desc
        } for _ in range(pieces)])
    items.sort(key=lambda x: x["adjusted_length"], reverse=True)

    # Group stock by position for priority-based optimization
    if use_stock_priority:
        # Sort stock data by position
        stock_data = sorted(stock_data, key=lambda x: x[0])  # Sort by stock_position (index 0)

        # Group stock by position
        stock_by_position = {}
        for stock_pos, stock_len, stock_pieces, stock_id, stock_desc in stock_data:
            if stock_pos not in stock_by_position:
                stock_by_position[stock_pos] = []
            usable_length = stock_len - initial_cut - final_cut
            if usable_length <= 0:
                continue
            stock_by_position[stock_pos].extend([
                (stock_pos, stock_len, usable_length, stock_id, stock_desc)
                for _ in range(stock_pieces)
            ])

        # Process each position sequentially
        remaining_items = items.copy()
        all_bins = []
        all_stock_map = {}
        bin_index = 0

        for stock_pos in sorted(stock_by_position.keys()):
            if not remaining_items:
                break

            # Create bins for current position only
            bins = []
            stock_map = {}
            for stock_pos_current, stock_len, usable_length, stock_id, stock_desc in stock_by_position[stock_pos]:
                bins.append({
                    "capacity": usable_length,
                    "original_length": stock_len,
                    "remaining": usable_length,
                    "items": [],
                    "stock_id": str(stock_id),
                    "stock_description": stock_desc
                })
                stock_map[bin_index] = stock_pos_current
                bin_index += 1

            if not bins:
                continue

            # Packing logic for current position
            if method == "greedy":
                for item in remaining_items[:]:  # Copy list to avoid modification during iteration
                    placed = False
                    for bin in bins:
                        if bin["remaining"] >= item["adjusted_length"]:
                            bin["items"].append({
                                "bar_position": item["bar_position"],
                                "length": item["length"],
                                "bar_id": item["bar_id"],
                                "bar_description": item["bar_description"]
                            })
                            bin["remaining"] -= item["adjusted_length"]
                            placed = True
                            remaining_items.remove(item)  # Remove placed item
                            break
            elif method == "first-fit":
                item_dict = {f"{item['bar_position']}_{i}": item["adjusted_length"] for i, item in enumerate(remaining_items)}
                try:
                    packed_bins = to_constant_bin_number(item_dict, len(bins))
                    placed_items = set()
                    for bin_idx, bin_contents in enumerate(packed_bins):
                        for item_key, adj_len in bin_contents.items():
                            bar_pos = item_key.split("_")[0]
                            bar_len = adj_len - width_of_cut
                            matching_item = next(i for i in remaining_items if i["bar_position"] == bar_pos and i["length"] == bar_len and i not in placed_items)
                            bins[bin_idx]["items"].append({
                                "bar_position": bar_pos,
                                "length": bar_len,
                                "bar_id": matching_item["bar_id"],
                                "bar_description": matching_item["bar_description"]
                            })
                            bins[bin_idx]["remaining"] -= adj_len
                            placed_items.add(matching_item)
                    # Remove placed items from remaining_items
                    remaining_items = [item for item in remaining_items if item not in placed_items]
                except (ValueError, StopIteration):
                    # Skip this position if packing fails
                    continue
            elif method == "best-fit":
                for item in remaining_items[:]:  # Copy list to avoid modification during iteration
                    best_bin_idx = None
                    min_remaining = float("inf")
                    for i, bin in enumerate(bins):
                        if bin["remaining"] >= item["adjusted_length"] and bin["remaining"] - item["adjusted_length"] < min_remaining:
                            best_bin_idx = i
                            min_remaining = bin["remaining"] - item["adjusted_length"]
                    if best_bin_idx is not None:
                        bins[best_bin_idx]["items"].append({
                            "bar_position": item["bar_position"],
                            "length": item["length"],
                            "bar_id": item["bar_id"],
                            "bar_description": item["bar_description"]
                        })
                        bins[best_bin_idx]["remaining"] -= item["adjusted_length"]
                        remaining_items.remove(item)  # Remove placed item
                    else:
                        # Skip this position if no fit found
                        break

            # Add bins from current position to global list
            all_bins.extend(bins)
            all_stock_map.update(stock_map)

        # Check if all items were placed
        if remaining_items:
            unplaced_count = len(remaining_items)
            return error_result(
                "Cannot create cutting plan - insufficient stock to place all bars",
                f"Unable to place {unplaced_count} bars. Increase stock quantity or adjust bar requirements."
            )

        bins = all_bins
        stock_map = all_stock_map

    else:
        # Original non-priority logic
        bins = []
        stock_map = {}
        bin_index = 0
        for stock_pos, stock_len, stock_pieces, stock_id, stock_desc in stock_data:
            usable_length = stock_len - initial_cut - final_cut
            if usable_length <= 0:
                continue
            for _ in range(stock_pieces):
                bins.append({
                    "capacity": usable_length,
                    "original_length": stock_len,
                    "remaining": usable_length,
                    "items": [],
                    "stock_id": str(stock_id),
                    "stock_description": stock_desc
                })
                stock_map[bin_index] = stock_pos
                bin_index += 1

        if not bins:
            return error_result(
                "Cannot create cutting plan - no usable stock pieces available",
                "No stock pieces remain after applying initial and final cuts. Ensure stock length exceeds initial_cut + final_cut."
            )

        # Packing logic
        if method == "greedy":
            for item in items:
                placed = False
                for bin in bins:
                    if bin["remaining"] >= item["adjusted_length"]:
                        bin["items"].append({
                            "bar_position": item["bar_position"],
                            "length": item["length"],
                            "bar_id": item["bar_id"],
                            "bar_description": item["bar_description"]
                        })
                        bin["remaining"] -= item["adjusted_length"]
                        placed = True
                        break
                if not placed:
                    return error_result(
                        "Cannot create cutting plan - insufficient stock to place all bars",
                        f"Unable to place bar {item['bar_position']} ({item['bar_description']}) with adjusted length {item['adjusted_length']}. Increase stock quantity."
                    )
        elif method == "first-fit":
            item_dict = {f"{item['bar_position']}_{i}": item["adjusted_length"] for i, item in enumerate(items)}
            try:
                packed_bins = to_constant_bin_number(item_dict, len(bins))
                for bin_idx, bin_contents in enumerate(packed_bins):
                    for item_key, adj_len in bin_contents.items():
                        bar_pos = item_key.split("_")[0]
                        bar_len = adj_len - width_of_cut
                        matching_item = next(i for i in items if i["bar_position"] == bar_pos and i["length"] == bar_len)
                        bins[bin_idx]["items"].append({
                            "bar_position": bar_pos,
                            "length": bar_len,
                            "bar_id": matching_item["bar_id"],
                            "bar_description": matching_item["bar_description"]
                        })
                        bins[bin_idx]["remaining"] -= adj_len
            except ValueError as e:
                return error_result(
                    "Cannot create cutting plan - insufficient stock to place all bars",
                    f"First-fit packing failed: {str(e)}. Increase stock quantity or adjust bar requirements."
                )
        elif method == "best-fit":
            for item in items:
                best_bin_idx = None
                min_remaining = float("inf")
                for i, bin in enumerate(bins):
                    if bin["remaining"] >= item["adjusted_length"] and bin["remaining"] - item["adjusted_length"] < min_remaining:
                        best_bin_idx = i
                        min_remaining = bin["remaining"] - item["adjusted_length"]
                if best_bin_idx is not None:
                    bins[best_bin_idx]["items"].append({
                        "bar_position": item["bar_position"],
                        "length": item["length"],
                        "bar_id": item["bar_id"],
                        "bar_description": item["bar_description"]
                    })
                    bins[best_bin_idx]["remaining"] -= item["adjusted_length"]
                else:
                    return error_result(
                        "Cannot create cutting plan - insufficient stock to place all bars",
                        f"Unable to place bar {item['bar_position']} ({item['bar_description']}) with adjusted length {item['adjusted_length']}. Increase stock quantity."
                    )

    # Verify all items were placed
    packed_items = sum(len(bin["items"]) for bin in bins)
    total_items = len(items)
    if packed_items < total_items:
        return error_result(
            "Cannot create cutting plan - insufficient stock to meet bar requirements",
            f"Unmet pieces: {total_items - packed_items}. Increase stock quantity or reduce bar pieces."
        )

    # Calculate cutting plans
    total_stock_length = sum(s[1] * s[2] for s in stock_data)
    total_bar_length = sum(b[1] * b[2] for b in bar_data)
    patterns_by_stock = {}
    for bin_idx, bin in enumerate(bins):
        if not bin["items"]:
            continue
        stock_pos = stock_map[bin_idx]
        stock_len = bin["original_length"]
        pattern_key = "|".join(
            f"{item['bar_position']}_{item['length']}_{item['bar_id']}_{item['bar_description']}"
            for item in bin["items"]
        )
        if stock_pos not in patterns_by_stock:
            patterns_by_stock[stock_pos] = {}
        patterns_by_stock[stock_pos][pattern_key] = patterns_by_stock[stock_pos].get(pattern_key, 0) + 1

    # Generate cutting plans
    package_name_base = result.get("package", {}).get("name", "Unnamed Package")
    plan_counter = 1
    for stock_pos, patterns in patterns_by_stock.items():
        stock_info = next(s for s in stock_data if s[0] == stock_pos)
        stock_len, stock_id, stock_desc = stock_info[1], stock_info[3], stock_info[4]
        for pattern_key, count in patterns.items():
            cut_pattern = []
            for p in pattern_key.split("|"):
                parts = p.split("_")
                cut_pattern.append({
                    "bar_position": parts[0],
                    "length": float(parts[1]),
                    "bar_id": parts[2],
                    "bar_description": parts[3]
                })
            used_length = sum(p["length"] + width_of_cut for p in cut_pattern) + initial_cut + final_cut
            total_waste = stock_len - used_length
            waste_percentage = (total_waste / stock_len * 100) if stock_len > 0 else 0
            cutting_plan_number = f"{package_name_base}_CP{plan_counter:03d}"
            result["cutting_plans"].append({
                "cutting_plan_number": cutting_plan_number,
                "stock_id": str(stock_id),
                "stock_description": stock_desc,
                "stock_position": stock_pos,
                "stock_length": stock_len,
                "pieces": count,
                "cut_pattern": cut_pattern,
                "waste_percentage": round(waste_percentage, 2),
                "initial_cut": initial_cut,
                "final_cut": final_cut,
                "width_of_cut": width_of_cut
            })
            plan_counter += 1

    # Generate stock used summary
    stock_used_dict = {}
    for plan in result["cutting_plans"]:
        key = (plan["stock_position"], plan["stock_description"], plan["stock_length"])
        if key in stock_used_dict:
            stock_used_dict[key]["pcs"] += plan["pieces"]
        else:
            stock_used_dict[key] = {
                "stock_position": plan["stock_position"],
                "stock_description": plan["stock_description"],
                "stock_length": plan["stock_length"],
                "pcs": plan["pieces"]
            }

    result["stock_used"] = list(stock_used_dict.values())

    # Calculate final summary
    total_used_stock_length = sum(
        next(s[1] for s in stock_data if s[0] == plan["stock_position"]) * plan["pieces"]
        for plan in result["cutting_plans"]
    )
    total_waste = total_used_stock_length - total_bar_length + (initial_cut + final_cut) * len([b for b in bins if b["items"]])
    total_waste_percentage = (total_waste / total_stock_length * 100) if total_stock_length > 0 else 0

    result["summary"] = {
        "total_stock_length": round(total_stock_length, 2),
        "total_used_stock_length": round(total_used_stock_length, 2),
        "total_bar_length": round(total_bar_length, 2),
        "total_waste_percentage": round(total_waste_percentage, 2),
        "method": method,
        "width_of_cut": width_of_cut,
        "initial_cut": initial_cut,
        "final_cut": final_cut
    }

    result["success"] = True
    result["message"] = "Cutting plan generated successfully"
    result["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return json.dumps(result, indent=2)

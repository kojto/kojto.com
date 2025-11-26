import json
from odoo import api
from ..utils.generate_1d_cutting_plan import generate_1d_cutting_plan

def compute_1d_cutting_plan(self):
    for record in self:
        try:
            result_json = generate_1d_cutting_plan(
                stock_ids=record.stock_ids,
                bar_ids=record.bar_ids,
                method=record.optimization_method,
                width_of_cut=record.width_of_cut,
                initial_cut=record.initial_cut,
                final_cut=record.final_cut,
                use_stock_priority=record.use_stock_priority,
                package=record
            )
            try:
                result = json.loads(result_json)
            except json.JSONDecodeError as e:
                error_msg = {
                    "cutting_plans": [],
                    "stock_used": [],
                    "summary": {},
                    "success": False,
                    "message": "Invalid JSON response from cutting plan generation",
                    "error_details": f"JSON parsing error: {str(e)}"
                }
                record.cutting_plan_json = json.dumps(error_msg)
                cutting_plan_text = (
                    "1. Summary:\n\tNo data available due to JSON parsing error\n\n"
                    "2. Used Stock:\n\tNo data available due to JSON parsing error\n\n"
                    "3. Cutting Plans:\n\tNo data available due to JSON parsing error\n\n"
                    f"4. Message:\n\tError: Invalid JSON response - {str(e)}\n"
                )
                record.cutting_plan = cutting_plan_text
                continue

            # Check for required keys and success status
            required_keys = ["cutting_plans", "stock_used", "summary"]
            missing_keys = [key for key in required_keys if key not in result]
            if missing_keys or not result.get("success", False):
                error_details = result.get("error_details", "No error details provided")
                message = result.get("message", "Unknown error in cutting plan generation")
                if missing_keys:
                    message = f"Missing required JSON keys: {', '.join(missing_keys)}"
                    error_details = f"Expected keys {required_keys}, but {missing_keys} were missing"
                error_msg = {
                    "cutting_plans": [],
                    "stock_used": [],
                    "summary": {},
                    "success": False,
                    "message": message,
                    "error_details": error_details
                }
                record.cutting_plan_json = json.dumps(error_msg)
                cutting_plan_text = (
                    "1. Summary:\n\tNo data available due to error\n\n"
                    "2. Used Stock:\n\tNo data available due to error\n\n"
                    "3. Cutting Plans:\n\tNo data available due to error\n\n"
                    f"4. Message:\n\tError: {message} - {error_details}\n"
                )
                record.cutting_plan = cutting_plan_text
                continue

            record.cutting_plan_json = result_json
            summary = result.get("summary", {})
            cutting_plan_text = "1. Summary:\n"
            cutting_plan_text += (
                f"\tAvailable Stock Length: {summary.get('total_stock_length', 0.0) / 1000:.2f} m\n"
                f"\tUsed Stock Length: {summary.get('total_used_stock_length', 0.0) / 1000:.2f} m\n"
                f"\tTotal Bar Length: {summary.get('total_bar_length', 0.0) / 1000:.2f} m\n"
                f"\tTotal Waste: {summary.get('total_waste_percentage', 0.0):.2f}%\n"
                f"\tMethod: {summary.get('method', 'N/A')}\n"
                f"\tWidth of Cut: {summary.get('width_of_cut', 0.0)} mm\n"
                f"\tInitial Cut: {summary.get('initial_cut', record.initial_cut)} mm\n"
                f"\tFinal Cut: {summary.get('final_cut', record.final_cut)} mm\n\n"
            )
            cutting_plan_text += "2. Used Stock:\n"
            for stock in result.get("stock_used", []):
                cutting_plan_text += (
                    f"\tPos. {stock['stock_position']}, "
                    f"{stock['stock_description'] or 'No description'}, "
                    f"{stock['stock_length']} mm, "
                    f"{stock['pcs']} pcs. required\n"
                )
            cutting_plan_text += "\n"
            bar_map = {}
            for bar in record.bar_ids:
                if bar.bar_length not in bar_map:
                    bar_map[bar.bar_length] = (bar.bar_position, bar.bar_description or "No description")
            cutting_plan_text += "3. Cutting Plans:\n"
            for plan in result.get("cutting_plans", []):
                cutting_plan_text += (
                    f"\tPlan {plan['cutting_plan_number']}, "
                    f"Pos. {plan['stock_position']}, "
                    f"{plan['stock_description'] or 'No description'}, "
                    f"{plan['stock_length']} mm, "
                    f"{plan['pieces']} pcs, "
                    f"Waste {plan['waste_percentage']}%\n"
                )
                cut_counts = {}
                for cut in plan["cut_pattern"]:
                    cut_length = cut["length"]
                    cut_counts[cut_length] = cut_counts.get(cut_length, 0) + 1
                for cut_length, count in cut_counts.items():
                    if cut_length in bar_map:
                        bar_position, bar_description = bar_map[cut_length]
                    else:
                        bar_position = "N/A"
                        bar_description = f"Unknown bar ({cut_length} mm)"
                    cutting_plan_text += (
                        f"\t\tBar pos. {bar_position}, "
                        f"{bar_description}, "
                        f"{cut_length} mm - {count} pcs\n"
                    )
            cutting_plan_text += "\n"
            cutting_plan_text += "4. Message:\n"
            cutting_plan_text += f"\t{result.get('message', 'No message provided')}\n"
            record.cutting_plan = cutting_plan_text

        except Exception as e:
            error_msg = {
                "cutting_plans": [],
                "stock_used": [],
                "summary": {},
                "success": False,
                "message": "Error generating cutting plan",
                "error_details": f"Unexpected error: {str(e)}"
            }
            record.cutting_plan_json = json.dumps(error_msg)
            cutting_plan_text = (
                "1. Summary:\n\tNo data available due to error\n\n"
                "2. Used Stock:\n\tNo data available due to error\n\n"
                "3. Cutting Plans:\n\tNo data available due to error\n\n"
                f"4. Message:\n\tError: {str(e)}\n"
            )
            record.cutting_plan = cutting_plan_text

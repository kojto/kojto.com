import json
from odoo import api
from ..utils.generate_2dr_cutting_plan import generate_2dr_cutting_plan

def compute_2dr_cutting_plan(self):
    for record in self:
        try:
            result_json = generate_2dr_cutting_plan(
                stock_rectangles_ids=record.stock_rectangles_ids,
                cutted_rectangles_ids=record.cutted_rectangles_ids,
                method=record.optimization_method,
                width_of_cut=record.width_of_cut,
                use_stock_priority=record.use_stock_priority,
                package=record,
                margin_left=record.margin_left or 0.0,
                margin_right=record.margin_right or 0.0,
                margin_top=record.margin_top or 0.0,
                margin_bottom=record.margin_bottom or 0.0
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
                    "2. Used Stock Rectangles:\n\tNo data available due to JSON parsing error\n\n"
                    "3. Cutting Plans:\n\tNo data available due to JSON parsing error\n\n"
                    f"4. Message:\n\tError: Invalid JSON response - {str(e)}\n"
                )
                record.cutting_plan = cutting_plan_text
                continue

            # Check for required keys
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
                    "2. Used Stock Rectangles:\n\tNo data available due to error\n\n"
                    "3. Cutting Plans:\n\tNo data available due to error\n\n"
                    f"4. Message:\n\tError: {message} - {error_details}\n"
                )
                record.cutting_plan = cutting_plan_text
                continue

            record.cutting_plan_json = result_json
            summary = result.get("summary", {})
            cutting_plan_text = "1. Summary:\n"
            cutting_plan_text += (
                f"\tTotal Stock Area: {summary.get('total_stock_area', 0.0) / 1000000:.2f} m²\n"
                f"\tUsed Stock Area: {summary.get('total_used_stock_area', 0.0) / 1000000:.2f} m²\n"
                f"\tTotal Cut Area: {summary.get('total_cut_area', 0.0) / 1000000:.2f} m²\n"
                f"\tTotal Waste: {summary.get('total_waste_percentage', 0.0):.2f}%\n"
                f"\tMethod: {summary.get('method', 'N/A')}\n"
                f"\tWidth of Cut: {summary.get('width_of_cut', 0.0)} mm\n"
                f"\tMargins: Left={summary.get('margin_left', 0.0):.1f}, Right={summary.get('margin_right', 0.0):.1f}, Top={summary.get('margin_top', 0.0):.1f}, Bottom={summary.get('margin_bottom', 0.0):.1f} mm\n\n"
            )
            cutting_plan_text += "2. Used Stock Rectangles:\n"
            for stock in result.get("stock_used", []):
                cutting_plan_text += (
                    f"\tPos. {stock['stock_position']}, "
                    f"{stock['stock_description']}, "
                    f"{stock['stock_width']} mm x {stock['stock_length']} mm, "
                    f"{stock['pcs']} pcs. required\n"
                )
            cutting_plan_text += "\n"
            cutting_plan_text += "3. Cutting Plans:\n"
            for plan in result.get("cutting_plans", []):
                cutting_plan_text += (
                    f"\tPlan {plan['cutting_plan_number']}, "
                    f"Pos. {plan['stock_position']}, "
                    f"{plan['stock_description']}, "
                    f"{plan['stock_width']} mm x {plan['stock_length']} mm, "
                    f"{plan['pieces']} pcs, "
                    f"Waste {plan['waste_percentage']}%\n"
                )
                for cut in plan["cut_pattern"]:
                    cutting_plan_text += (
                        f"\t\tCut pos. {cut['cut_position']}, "
                        f"{cut['cut_description']}, "
                        f"{cut['width']} mm x {cut['length']} mm, "
                        f"at ({cut['x']}, {cut['y']}), "
                        f"Rotation: {cut['rotation']}°\n"
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
                "2. Used Stock Rectangles:\n\tNo data available due to error\n\n"
                "3. Cutting Plans:\n\tNo data available due to error\n\n"
                f"4. Message:\n\tError: {str(e)}\n"
            )
            record.cutting_plan = cutting_plan_text

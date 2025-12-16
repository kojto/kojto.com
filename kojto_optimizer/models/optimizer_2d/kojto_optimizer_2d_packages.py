"""
Kojto Optimizer 2D Packages Model

Purpose:
--------
Defines the main package model for 2D shape optimization.
Handles package creation, cutting plan computation, and exports.
"""

import json
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KojtoOptimizer2dPackages(models.Model):
    _name = "kojto.optimizer.2d.packages"
    _description = "Kojto Profile Optimizer 2D Packages"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_optimizer.print_kojto_optimizer_2d_packages"

    name = fields.Char(compute="generate_2d_package_name", store=True, string="Name")
    subcode_id = fields.Many2one("kojto.commission.subcodes", required=True, string="Subcode")
    description = fields.Text(string="Description")
    date_issue = fields.Date(string='Issue Date', default=fields.Date.today)
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By')
    active = fields.Boolean(default=True, string="Active")

    # Stock rectangles
    stock_rectangles_ids = fields.One2many("kojto.optimizer.2d.stock.rectangles", "package_id", string="Stock Rectangles")

    # Shapes to cut (DXF-based)
    shapes_to_cut_ids = fields.One2many("kojto.optimizer.2d.shapes.to.cut", "package_id", string="Shapes to Cut")

    width_of_cut = fields.Float(required=True, default=4.0, string="Width of Cut (mm)")
    margin_left = fields.Float(default=0.0, string="Margin Left (mm)")
    margin_right = fields.Float(default=0.0, string="Margin Right (mm)")
    margin_top = fields.Float(default=0.0, string="Margin Top (mm)")
    margin_bottom = fields.Float(default=0.0, string="Margin Bottom (mm)")

    cutting_plan = fields.Text(compute="_compute_cutting_plan", store=True, string="Cutting Plan")
    cutting_plan_json = fields.Text(compute="_compute_cutting_plan", store=True, string="Cutting Plan JSON")
    cutting_plan_svgs = fields.Text("Cutting Plan SVGs", compute='_compute_cutting_plan_svgs')

    optimization_method = fields.Selection([
        ("guillotine_baf", "Guillotine - Best Area Fit"),
        ("maxrects_bssf", "MaxRects - Best Short Side Fit"),
        ("skyline_bl", "Skyline - Bottom Left"),
    ], required=True, default="maxrects_bssf", string="Optimization Method")

    use_stock_priority = fields.Boolean(
        string="Use Stock Priority",
        default=False,
        help="When enabled, stock rectangles will be used in order of their position field"
    )

    language_id = fields.Many2one(
        "res.lang",
        default=lambda self: self.env.ref("base.lang_en", raise_if_not_found=False).id or False,
        string="Language"
    )

    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment")
    autocad_dxf = fields.Binary(string="AutoCAD DXF", readonly=True)

    thickness = fields.Float(string="Thickness (mm)", digits=(9, 2))
    material_id = fields.Many2one("kojto.base.material.grades", string="Material")

    @api.constrains("width_of_cut", "margin_left", "margin_right", "margin_top", "margin_bottom")
    def _check_non_negative_values(self):
        for record in self:
            if any(val < 0 for val in [
                record.width_of_cut,
                record.margin_left,
                record.margin_right,
                record.margin_top,
                record.margin_bottom
            ]):
                raise ValidationError("Cut width and margins cannot be negative.")

    @api.constrains("stock_rectangles_ids", "shapes_to_cut_ids")
    def _check_record_limits(self):
        for record in self:
            if len(record.stock_rectangles_ids) > 99:
                raise ValidationError("The number of stock rectangles cannot exceed 99.")
            if len(record.shapes_to_cut_ids) > 999:
                raise ValidationError("The number of shapes to cut cannot exceed 999.")

    @api.depends("subcode_id")
    def generate_2d_package_name(self):
        for record in self:
            if not all([
                record.subcode_id,
                record.subcode_id.code_id,
                record.subcode_id.maincode_id
            ]):
                record.name = ""
                continue

            base_name_prefix = ".".join([
                record.subcode_id.maincode_id.maincode,
                record.subcode_id.code_id.code,
                record.subcode_id.subcode,
                "2D"
            ])

            self.env.cr.execute("""
                SELECT MAX(CAST(RIGHT(name, 3) AS INTEGER)) as num
                FROM kojto_optimizer_2d_packages
                WHERE name LIKE %s AND id != %s
            """, (
                f"{base_name_prefix}.%",
                record.id or 0
            ))
            last_number = self.env.cr.fetchone()[0] or 0
            next_number = last_number + 1

            if next_number > 999:
                raise ValidationError(
                    f"Maximum 2D package number reached for {base_name_prefix}"
                )

            record.name = f"{base_name_prefix}.{str(next_number).zfill(3)}"

    @api.depends("stock_rectangles_ids", "shapes_to_cut_ids", "optimization_method",
                 "width_of_cut", "margin_left", "margin_right", "margin_top", "margin_bottom",
                 "use_stock_priority", "thickness", "material_id",
                 "shapes_to_cut_ids.bbox_width", "shapes_to_cut_ids.bbox_height",
                 "shapes_to_cut_ids.required_cut_shape_pieces",
                 "shapes_to_cut_ids.outer_polygon_json")
    def _compute_cutting_plan(self):
        """Compute cutting plan for 2D shapes using actual polygon shapes."""
        for record in self:
            try:
                if not record.stock_rectangles_ids or not record.shapes_to_cut_ids:
                    record.cutting_plan = ""
                    record.cutting_plan_json = ""
                    continue

                # Import the 2D cutting plan generator (polygon-based)
                from ...utils.generate_2d_cutting_plan import generate_2d_cutting_plan

                # Generate cutting plan using actual polygon shapes
                result_json = generate_2d_cutting_plan(
                    stock_rectangles_ids=record.stock_rectangles_ids,
                    shapes_to_cut_ids=record.shapes_to_cut_ids,
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

                # Success case: parse and format the cutting plan
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
                    for cut in plan.get("cut_pattern", []):
                        cutting_plan_text += (
                            f"\t\tPos. {cut.get('cut_position', 'N/A')}, "
                            f"{cut.get('cut_description', 'N/A')}, "
                            f"X={cut.get('x', 0):.2f} mm, Y={cut.get('y', 0):.2f} mm, "
                            f"Width={cut.get('width', 0):.2f} mm, Length={cut.get('length', 0):.2f} mm, "
                            f"Rotation={cut.get('rotation', 0):.2f}°, "
                            f"Pieces={cut.get('pieces', 1)}\n"
                        )
                cutting_plan_text += "\n"
                cutting_plan_text += f"4. Message:\n\t{result.get('message', 'Cutting plan generated successfully')}\n"
                record.cutting_plan = cutting_plan_text
            except Exception as e:
                _logger.error(f"Error computing cutting plan for package {record.id or 'new'}: {str(e)}", exc_info=True)
                record.cutting_plan = f"Error computing cutting plan: {str(e)}"
                record.cutting_plan_json = json.dumps({
                    "cutting_plans": [],
                    "stock_used": [],
                    "summary": {},
                    "success": False,
                    "message": f"Error: {str(e)}",
                    "error_details": str(e)
                })

    @api.depends("cutting_plan_json", "shapes_to_cut_ids", "margin_left", "margin_bottom")
    def _compute_cutting_plan_svgs(self):
        """Compute SVG representations of cutting plans."""
        for package in self:
            if not package.cutting_plan_json:
                package.cutting_plan_svgs = False
                continue
            try:
                from ...utils.compute_cutting_plan_2d_svg import compute_cutting_plan_2d_svg
                svg_list = compute_cutting_plan_2d_svg(
                    package.cutting_plan_json,
                    shapes_to_cut_records=package.shapes_to_cut_ids,
                    package_name=package.name,
                    margin_left=package.margin_left or 0.0,
                    margin_bottom=package.margin_bottom or 0.0
                )
                package.cutting_plan_svgs = '\n'.join(svg_list) if svg_list else False
            except Exception as e:
                _logger.error(f"Error computing SVGs for package {package.id}: {str(e)}")
                package.cutting_plan_svgs = False

    def action_import_shapes_to_cut(self):
        """Open wizard to import DXF files."""
        self.ensure_one()
        return {
            "name": "Import DXF Shapes",
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.2d.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "dialog_size": "medium",
            },
        }

    def action_import_stock_rectangles(self):
        """Import stock rectangles (reuse from 2DR)."""
        self.ensure_one()
        stock_data = "\n".join(
            f"{stock.stock_position}\t{stock.stock_description}\t{stock.stock_width}\t{stock.stock_length}\t{stock.available_stock_rectangle_pieces}"
            for stock in self.stock_rectangles_ids
        ) if self.stock_rectangles_ids else "Position\tDescription\tWidth\tLength\tQuantity\n"

        return {
            "name": "Import Stock Rectangles",
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.2dr.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "default_import_type": "stock_rectangles",
                "default_data": stock_data,
                "dialog_size": "small",
            },
        }

    def write(self, vals):
        """Override write to trigger recomputation of child records when package fields change."""
        result = super().write(vals)

        # If thickness or material_id changed, recompute shape_weight for all child shapes
        if 'thickness' in vals or 'material_id' in vals:
            for package in self:
                if package.shapes_to_cut_ids:
                    package.shapes_to_cut_ids._compute_shape_weight()
                    # Force write to ensure computed weight is persisted
                    for shape in package.shapes_to_cut_ids:
                        shape.sudo().write({'shape_weight': shape.shape_weight})

        return result

    def action_export_to_dxf(self):
        """Export cutting plan to DXF file."""
        self.ensure_one()
        from ...utils.export_2d_cutting_plan_to_dxf import export_2d_cutting_plan_to_dxf
        return export_2d_cutting_plan_to_dxf(self)


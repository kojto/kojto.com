"""
Kojto Optimizer 2DR Packages Model

Purpose:
--------
Defines the main package model for 2D rectangle optimization.
Handles package creation, cutting plan computation, and exports.
"""

import json
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

from ...utils.compute_2dr_cutting_plan import compute_2dr_cutting_plan
from ...utils.export_2dr_cutting_plan_to_excel import export_2dr_cutting_plan_to_excel
from ...utils.export_2dr_cutting_plan_to_dxf import export_2dr_cutting_plan_to_dxf
from ...utils.compute_cutting_plan_2dr_svg import compute_cutting_plan_2dr_svg


class KojtoOptimizer2drPackages(models.Model):
    _name = "kojto.optimizer.2dr.packages"
    _description = "Kojto Profile Optimizer 2DR Packages"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_optimizer.print_kojto_optimizer_2dr_packages"


    name = fields.Char(compute="generate_2dr_package_name", store=True, string="Name")
    subcode_id = fields.Many2one("kojto.commission.subcodes", required=True, string="Subcode")
    description = fields.Text(string="Description")
    date_issue = fields.Date(string='Issue Date', default=fields.Date.today)
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By')
    active = fields.Boolean(default=True, string="Active")
    stock_rectangles_ids = fields.One2many("kojto.optimizer.2dr.stock.rectangles", "package_id", string="Stock Rectangles")
    cutted_rectangles_ids = fields.One2many("kojto.optimizer.2dr.cut.rectangles", "package_id", string="Cut Rectangles")
    width_of_cut = fields.Float(required=True, default=4.0, string="Width of Cut (mm)")
    cutting_plan = fields.Text(compute="_compute_cutting_plan", store=True, string="Cutting Plan")
    cutting_plan_json = fields.Text(compute="_compute_cutting_plan", store=True, string="Cutting Plan JSON")
    optimization_method = fields.Selection([
        ("guillotine_baf", "Guillotine - Best Area Fit"),
        ("maxrects_bssf", "MaxRects - Best Short Side Fit"),
        ("skyline_bl", "Skyline - Bottom Left"),], required=True, default="maxrects_bssf", string="Optimization Method")
    use_stock_priority = fields.Boolean(string="Use Stock Priority", default=False, help="When enabled, stock rectangles will be used in order of their position field")
    allow_cut_rotation = fields.Boolean(string="Allow Cut Rotation", default=True, help="When enabled, cut rectangles can be rotated. When disabled, the length of cut rectangles must be parallel to the length of stock rectangles.")
    language_id = fields.Many2one("res.lang", default=lambda self: self.env.ref("base.lang_en", raise_if_not_found=False).id or False, string="Language")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment")
    autocad_dxf = fields.Binary(string="AutoCAD DXF", readonly=True)
    thickness = fields.Float(string="Thickness (mm)", digits=(9, 2))
    material_id = fields.Many2one("kojto.base.material.grades", string="Material")
    cutting_plan_svgs = fields.Text("Cutting Plan SVGs", compute='_compute_cutting_plan_svgs')

    margin_left = fields.Float(string="Margin Left (mm)", default=0.0, help="Margin left from the left edge of the stock rectangle (reduces the width of the stock rectangle)")
    margin_right = fields.Float(string="Margin Right (mm)", default=0.0, help="Margin right from the right edge of the stock rectangle (reduces the width of the stock rectangle)")
    margin_top = fields.Float(string="Margin Top (mm)", default=0.0, help="Margin top from the top edge of the stock rectangle (reduces the height of the stock rectangle)")
    margin_bottom = fields.Float(string="Margin Bottom (mm)", default=0.0, help="Margin bottom from the bottom edge of the stock rectangle (reduces the height of the stock rectangle)")


    @api.constrains("stock_rectangles_ids", "cutted_rectangles_ids")
    def _constrain_record_limits(self):
        for package in self:
            if len(package.stock_rectangles_ids) > 99:
                raise ValidationError("Stock rectangles limit exceeded (max 99).")
            if len(package.cutted_rectangles_ids) > 999:
                raise ValidationError("Cut rectangles limit exceeded (max 999).")

    @api.constrains("margin_left", "margin_right", "margin_top", "margin_bottom")
    def _constrain_margins(self):
        for package in self:
            if package.margin_left < 0:
                raise ValidationError("Margin left cannot be negative.")
            if package.margin_right < 0:
                raise ValidationError("Margin right cannot be negative.")
            if package.margin_top < 0:
                raise ValidationError("Margin top cannot be negative.")
            if package.margin_bottom < 0:
                raise ValidationError("Margin bottom cannot be negative.")

    @api.constrains("margin_left", "margin_right", "margin_top", "margin_bottom", "stock_rectangles_ids")
    def _constrain_margin_stock_compatibility(self):
        for package in self:
            for stock in package.stock_rectangles_ids:
                effective_width = stock.stock_width - package.margin_left - package.margin_right
                effective_length = stock.stock_length - package.margin_top - package.margin_bottom

                if effective_width <= 0:
                    raise ValidationError(
                        f"Stock {stock.stock_position} width ({stock.stock_width} mm) is too small for margins "
                        f"(left: {package.margin_left} mm, right: {package.margin_right} mm). "
                        f"Effective width would be {effective_width} mm."
                    )
                if effective_length <= 0:
                    raise ValidationError(
                        f"Stock {stock.stock_position} length ({stock.stock_length} mm) is too small for margins "
                        f"(top: {package.margin_top} mm, bottom: {package.margin_bottom} mm). "
                        f"Effective length would be {effective_length} mm."
                    )

    @api.depends("subcode_id", "subcode_id.code_id", "subcode_id.maincode_id")
    def generate_2dr_package_name(self):
        for package in self:
            if not all([
                package.subcode_id,
                package.subcode_id.code_id,
                package.subcode_id.maincode_id
            ]):
                package.name = ""
                continue
            base_name_prefix = ".".join([
                package.subcode_id.maincode_id.maincode,
                package.subcode_id.code_id.code,
                package.subcode_id.subcode,
                "2DR"
            ])
            self.env.cr.execute("""
                SELECT MAX(CAST(RIGHT(name, 3) AS INTEGER)) as num
                FROM %s
                WHERE name LIKE %s AND id != %s
            """ % (self._table, '%s', '%s'), (
                f"{base_name_prefix}.%",
                package.id or 0
            ))
            last_number = self.env.cr.fetchone()[0] or 0
            next_number = last_number + 1
            if next_number > 999:
                raise ValidationError(
                    f"Maximum 2DR package number reached for {base_name_prefix}"
                )
            package.name = f"{base_name_prefix}.{str(next_number).zfill(3)}"

    @api.depends(
        "stock_rectangles_ids.stock_width",
        "stock_rectangles_ids.stock_length",
        "stock_rectangles_ids.available_stock_rectangle_pieces",
        "stock_rectangles_ids.stock_description",
        "stock_rectangles_ids.stock_position",
        "cutted_rectangles_ids.cut_width",
        "cutted_rectangles_ids.cut_length",
        "cutted_rectangles_ids.required_cut_rectangle_pieces",
        "cutted_rectangles_ids.cut_description",
        "optimization_method",
        "width_of_cut",
        "use_stock_priority",
        "allow_cut_rotation",
        "margin_left",
        "margin_right",
        "margin_top",
        "margin_bottom"
    )
    def _compute_cutting_plan(self):
        for package in self:
            try:
                compute_2dr_cutting_plan(package)
            except Exception as e:
                _logger.error(f"Error computing cutting plan for package {package.id or 'new'}: {str(e)}")
                package.cutting_plan = False
                package.cutting_plan_json = False
                continue
            if not package.cutting_plan_json:
                package.cutting_plan = False
                package.cutting_plan_json = False
                _logger.warning(f"No cutting plan generated for package {package.id or 'new'}")

    @api.depends("cutting_plan_json")
    def _compute_cutting_plan_svgs(self):
        for package in self:
            if not package.cutting_plan_json:
                package.cutting_plan_svgs = False
                continue
            try:
                svg_list = compute_cutting_plan_2dr_svg(
                    package.cutting_plan_json,
                    package.name,
                    margin_left=package.margin_left or 0.0,
                    margin_bottom=package.margin_bottom or 0.0
                )
                package.cutting_plan_svgs = '\n'.join(svg_list) if svg_list else False
            except Exception as e:
                _logger.error(f"Error computing SVGs for package {package.id}: {str(e)}")
                package.cutting_plan_svgs = False

    @api.onchange("stock_rectangles_ids", "cutted_rectangles_ids", "optimization_method", "width_of_cut", "use_stock_priority", "allow_cut_rotation", "margin_left", "margin_right", "margin_top", "margin_bottom")
    def _onchange_recompute_cutting_plan(self):
        if self._origin:
            self._compute_cutting_plan()

    def action_export_to_excel(self):
        self.ensure_one()
        return export_2dr_cutting_plan_to_excel(self)

    def action_import_stock_rectangles(self):
        self.ensure_one()
        data = self._format_import_data(self.stock_rectangles_ids, "stock")
        return self._open_import_wizard("stock_rectangles", data)

    def action_import_cut_rectangles(self):
        self.ensure_one()
        data = self._format_import_data(self.cutted_rectangles_ids, "cut")
        return self._open_import_wizard("cut_rectangles", data)

    def _format_import_data(self, records, record_type):
        if not records:
            return "Position\tDescription\tWidth\tHeight\tQuantity\n"
        if record_type == "stock":
            return "\n".join(
                f"{rec.stock_position}\t{rec.stock_description.replace('\t', ',')}\t"
                f"{rec.stock_width}\t{rec.stock_length}\t{rec.available_stock_rectangle_pieces}"
                for rec in records
            )
        return "\n".join(
            f"{rec.cut_position}\t{rec.cut_description.replace('\t', ',')}\t"
            f"{rec.cut_width}\t{rec.cut_length}\t{rec.required_cut_rectangle_pieces}"
            for rec in records
        )

    def _open_import_wizard(self, import_type, data):
        return {
            "name": f"Import {import_type.replace('_', ' ').title()}",
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.2dr.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "default_import_type": import_type,
                "default_data": data,
                "dialog_size": "small",
            },
        }

    def action_export_to_dxf(self):
        self.ensure_one()
        return export_2dr_cutting_plan_to_dxf(self)

    def action_generate_pdf(self):
        self.ensure_one()
        return self.print_document_as_pdf()

    def copy_and_open(self):
        self.ensure_one()
        # Copy the package with basic fields
        new_package = self.copy({
            'issued_by': self.issued_by.id if self.issued_by else False,
            'date_issue': fields.Date.today(),
        })

        # Copy all stock rectangles to the new package
        for stock in self.stock_rectangles_ids:
            stock_vals = {
                'package_id': new_package.id,
                'stock_position': stock.stock_position,
                'stock_description': stock.stock_description,
                'stock_width': stock.stock_width,
                'stock_length': stock.stock_length,
                'available_stock_rectangle_pieces': stock.available_stock_rectangle_pieces,
            }
            self.env['kojto.optimizer.2dr.stock.rectangles'].create(stock_vals)

        # Copy all cut rectangles to the new package
        for cut in self.cutted_rectangles_ids:
            cut_vals = {
                'package_id': new_package.id,
                'cut_position': cut.cut_position,
                'cut_description': cut.cut_description,
                'cut_width': cut.cut_width,
                'cut_length': cut.cut_length,
                'required_cut_rectangle_pieces': cut.required_cut_rectangle_pieces,
            }
            self.env['kojto.optimizer.2dr.cut.rectangles'].create(cut_vals)

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.2dr.packages",
            "view_mode": "form",
            "res_id": new_package.id,
            "target": "current"
        }

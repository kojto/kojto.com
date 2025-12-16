import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer1DStock(models.Model):
    _name = "kojto.optimizer.1d.stock"
    _description = "Stock for Kojto Optimizer 1D"

    package_id = fields.Many2one("kojto.optimizer.1d.packages", string="Package", required=True, ondelete="cascade")
    stock_position = fields.Char(string="Stock Position", required=True)
    stock_description = fields.Char(string="Stock Description", default="Stock_")
    stock_length = fields.Float(string="Length (mm)", required=True)
    available_stock_pieces = fields.Integer(string="Available Pieces", required=True, default=0)
    used_stock_pieces = fields.Integer(string="Used Pieces", compute="_compute_used_stock_pieces")

    @api.depends("package_id.cutting_plan_json")
    def _compute_used_stock_pieces(self):
        for record in self:
            used_pieces = 0
            if record.package_id.cutting_plan_json:
                try:
                    cutting_plan = json.loads(record.package_id.cutting_plan_json)
                    for plan in cutting_plan.get("cutting_plans", []):
                        if plan.get("stock_id") == str(record.id):
                            used_pieces += plan.get("pieces", 0)
                except (json.JSONDecodeError, Exception):
                    used_pieces = 0
            record.used_stock_pieces = used_pieces

    @api.constrains("stock_length", "available_stock_pieces")
    def _check_positive_values(self):
        for record in self:
            if record.stock_length <= 0:
                raise ValidationError("Stock length must be positive.")
            if record.available_stock_pieces < 0:
                raise ValidationError("Stock pieces cannot be negative.")

    @api.constrains("stock_length", "package_id")
    def _check_length_vs_cuts(self):
        for record in self:
            initial_cut = record.package_id.initial_cut or 0.0
            final_cut = record.package_id.final_cut or 0.0
            if record.stock_length <= initial_cut + final_cut:
                raise ValidationError(
                    f"Stock length ({record.stock_length} mm) must be greater than "
                    f"initial cut ({initial_cut} mm) + final cut ({final_cut} mm)."
                )

    @api.constrains("stock_position", "package_id")
    def _check_unique_stock_position(self):
        for record in self:
            if record.stock_position and record.package_id:
                duplicates = self.search([
                    ('stock_position', '=', record.stock_position),
                    ('package_id', '=', record.package_id.id),
                    ('id', '!=', record.id)
                ])
                if duplicates:
                    raise ValidationError(
                        f"Stock Position '{record.stock_position}' already exists "
                        f"within package '{record.package_id.name}'."
                    )

    _sql_constraints = [
        (
            'unique_stock_position_per_package',
            'UNIQUE(package_id, stock_position)',
            'Stock Position must be unique within the same package.'
        )
    ]

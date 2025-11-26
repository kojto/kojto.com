"""
Kojto Optimizer 2DR Stock Rectangles Model

Purpose:
--------
Defines the model for stock rectangles used in 2D rectangle optimization.
Each stock rectangle represents a piece of material that can be cut.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer2drStockRectangles(models.Model):
    _name = "kojto.optimizer.2dr.stock.rectangles"
    _description = "Kojto Profile Optimizer 2DR Stock Rectangles"
    _order = "stock_position, id"

    package_id = fields.Many2one("kojto.optimizer.2dr.packages", string="Package", required=True, ondelete="cascade")
    stock_position = fields.Char(string="Position", required=True)
    stock_description = fields.Char(string="Description", default="-")
    stock_width = fields.Float(string="Width (mm)", required=True)
    stock_length = fields.Float(string="Length (mm)", required=True)
    available_stock_rectangle_pieces = fields.Integer(string="Pieces", required=True, default=1)

    @api.constrains("stock_width", "stock_length", "available_stock_rectangle_pieces")
    def _constrain_positive_values(self):
        for rec in self:
            if any(v <= 0 for v in [rec.stock_width, rec.stock_length, rec.available_stock_rectangle_pieces]):
                raise ValidationError(
                    f"Stock rectangle '{rec.stock_position}' must have positive width, length, and pieces."
                )

    _sql_constraints = [(
            'unique_stock_position_per_package',
            'UNIQUE(package_id, stock_position)',
            'Stock Position must be unique within the same package.')]

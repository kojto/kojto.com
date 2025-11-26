"""
Kojto Optimizer 2DR Cut Rectangles Model

Purpose:
--------
Defines the model for cut rectangles used in 2D rectangle optimization.
Each cut rectangle represents a piece that needs to be cut from stock material.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer2drCutRectangles(models.Model):
    _name = "kojto.optimizer.2dr.cut.rectangles"
    _description = "Kojto Profile Optimizer 2DR Cut Rectangles"

    package_id = fields.Many2one(
        "kojto.optimizer.2dr.packages",
        string="Package",
        required=True,
        ondelete="cascade"
    )
    cut_position = fields.Char(string="Position", required=True)
    cut_description = fields.Char(string="Description", default="-")
    cut_width = fields.Float(string="Width (mm)", required=True)
    cut_length = fields.Float(string="Length (mm)", required=True)
    required_cut_rectangle_pieces = fields.Integer(string="Pieces", required=True, default=1)

    @api.constrains("cut_width", "cut_length", "required_cut_rectangle_pieces")
    def _constrain_positive_values(self):
        for rec in self:
            if any(v <= 0 for v in [rec.cut_width, rec.cut_length, rec.required_cut_rectangle_pieces]):
                raise ValidationError(
                    f"Cut rectangle '{rec.cut_position}' must have positive width, length, and pieces."
                )

    @api.constrains("cut_position", "package_id")
    def _check_unique_cut_position(self):
        for rec in self:
            if rec.cut_position and rec.package_id:
                duplicates = self.search([
                    ('cut_position', '=', rec.cut_position),
                    ('package_id', '=', rec.package_id.id),
                    ('id', '!=', rec.id),
                ])
                if duplicates:
                    raise ValidationError(
                        f"Cannot save: Cut Position '{rec.cut_position}' already exists "
                        f"within package '{rec.package_id.name}'."
                    )

    _sql_constraints = [
        (
            'unique_cut_position_per_package',
            'UNIQUE(package_id, cut_position)',
            'Cut Position must be unique within the same package.'
        )
    ]

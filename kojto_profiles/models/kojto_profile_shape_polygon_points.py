# kojto_profiles/models/kojto_profile_shape_polygon_points.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoProfileShapePolygonPoints(models.Model):
    _name = "kojto.profile.shape.polygon.points"
    _description = "Points in Kojto Profile Shape Polygons"

    polygon_id = fields.Many2one(
        "kojto.profile.shape.polygons",
        string="Polygon",
        required=True,
        ondelete="cascade"
    )
    x = fields.Float(string="X Coordinate", required=True)
    y = fields.Float(string="Y Coordinate", required=True)

    @api.constrains("x", "y")
    def _check_duplicate_points(self):
        """Prevent duplicate (x, y) coordinate pairs within the same polygon."""
        for rec in self:
            duplicates = rec.polygon_id.point_ids.filtered(
                lambda p: p.id != rec.id and p.x == rec.x and p.y == rec.y
            )
            if duplicates:
                raise ValidationError(
                    f"Duplicate point ({rec.x}, {rec.y}) in polygon '{rec.polygon_id.name}' "
                    f"of shape '{rec.polygon_id.shape_id.name}'"
                )

    def write(self, vals):
        """Trigger shape and profile drawing updates on coordinate changes."""
        res = super().write(vals)
        if 'x' in vals or 'y' in vals:
            self.polygon_id.shape_id._compute_shape_drawing()
            self.polygon_id.shape_id._compute_area()
            profiles = self.polygon_id.shape_id.insert_ids.mapped('profile_id')
            for profile in profiles:
                profile._compute_drawing()
        return res

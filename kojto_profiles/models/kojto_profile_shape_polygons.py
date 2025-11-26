#$ kojto_profiles/models/kojto_profile_shape_polygons.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from shapely.geometry import Polygon
from ..utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points

class KojtoProfileShapePolygons(models.Model):
    _name = "kojto.profile.shape.polygons"
    _description = "Polygons in Kojto Profile Shapes"

    name = fields.Char(string="Polygon Name", compute="_compute_polygon_name", store=True)
    shape_id = fields.Many2one("kojto.profile.shapes", string="Shape", ondelete="cascade", required=True)
    is_external = fields.Boolean(string="External Polygon", compute="_compute_is_external", store=True)
    point_ids = fields.One2many("kojto.profile.shape.polygon.points", "polygon_id", string="Points")
    drawing = fields.Binary("Image", compute="_compute_polygon_drawing")

    @api.depends("shape_id", "shape_id.polygon_ids")
    def _compute_polygon_name(self):
        """Auto-name polygon using shape name + index (e.g., SHP_001.01)"""
        for rec in self:
            if rec.shape_id and rec.shape_id.name:
                # Separate saved and unsaved polygons
                polygons = rec.shape_id.polygon_ids
                saved_polygons = polygons.filtered(lambda p: p.id and isinstance(p.id, int))
                unsaved_polygons = polygons - saved_polygons

                # Sort saved polygons by ID
                sorted_polygons = saved_polygons.sorted(key=lambda p: p.id)

                # Combine saved and unsaved polygons (unsaved at the end)
                all_polygons = sorted_polygons + unsaved_polygons

                # Find index of current record
                index = list(all_polygons).index(rec) + 1 if rec in all_polygons else 1
                rec.name = f"{rec.shape_id.name}.{index:02d}"
            else:
                rec.name = "Unnamed"

    @api.depends("shape_id.polygon_ids", "shape_id.polygon_ids.point_ids")
    def _compute_is_external(self):
        """Set the first valid polygon (with ≥3 points) as external, recalculate on any change."""
        for rec in self:
            if rec.shape_id:
                polygons = rec.shape_id.polygon_ids.sorted(key=lambda p: p.id or float('inf'))
                valid_polys = [p for p in polygons if len(p.point_ids) >= 3]
                rec.is_external = bool(valid_polys and rec == valid_polys[0])
            else:
                rec.is_external = False

    @api.depends("point_ids", "point_ids.x", "point_ids.y")
    def _compute_polygon_drawing(self):
        for rec in self:
            if len(rec.point_ids) >= 3:
                points = [(pt.x, pt.y) for pt in rec.point_ids]
                try:
                    rec.drawing = compute_svg_from_polygons_and_points([{
                        'points': points,
                        'is_subtract': not rec.is_external
                    }])
                except Exception:
                    rec.drawing = False
            else:
                rec.drawing = False

    @api.constrains("point_ids")
    def _check_point_count(self):
        """Only allow 0 or ≥3 points. Disallow 1 or 2."""
        for rec in self:
            count = len(rec.point_ids)
            if count in (1, 2):
                raise ValidationError(
                    f"Polygon '{rec.name or 'Unnamed'}' must have either 0 or at least 3 points. Found: {count}."
                )

    @api.constrains("point_ids")
    def _check_polygon_validity(self):
        """If a polygon has points, ensure it's valid."""
        for rec in self:
            if len(rec.point_ids) >= 3:
                try:
                    poly = Polygon([(p.x, p.y) for p in rec.point_ids])
                    if not poly.is_valid or not poly.is_simple:
                        raise ValidationError(
                            f"Polygon '{rec.name}' is invalid (self-intersecting or not simple)."
                        )
                except Exception as e:
                    raise ValidationError(f"Error validating polygon '{rec.name}': {str(e)}")

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.shape_id:
                rec.shape_id._compute_shape_drawing()
                rec.shape_id._compute_area()
                rec.shape_id.write({})  # Force recompute if needed
                if rec.shape_id.insert_ids:
                    for profile in rec.shape_id.insert_ids.mapped('profile_id'):
                        profile._compute_drawing()
        return res

    def action_open_polygon_form(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Polygon',
            'res_model': 'kojto.profile.shape.polygons',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def open_import_points_wizard(self):
        """Open the wizard to import points for this polygon, bypassing any save or validation."""
        self.ensure_one()
        try:
            view_id = self.env.ref('kojto_profiles.view_kojto_profile_shape_polygon_points_import_wizard_form').id
        except ValueError:
            view_id = False  # Fallback if view is not found
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import Polygon Points',
            'res_model': 'kojto.profile.shape.polygon.points.import.wizard',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {
                'default_polygon_id': self.id,
                'skip_validation': True,
                'bypass_save': True
            }
        }

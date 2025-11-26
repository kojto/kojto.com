"""
Kojto Profile Shape Polygon Points Import Wizard

Purpose:
--------
Provides a wizard interface for importing points data into profile shape polygons.
Supports various input formats (comma, semicolon, or tab-separated) and validates
the input data before creating the points.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoProfileShapePolygonPointsImportWizard(models.TransientModel):
    _name = "kojto.profile.shape.polygon.points.import.wizard"
    _description = "Import Points for Polygon in Kojto Profile Shapes"

    polygon_id = fields.Many2one("kojto.profile.shape.polygons", string="Polygon", required=True)
    data = fields.Text(
        string="Points Data",
        required=True,
        help="Format: x,y or x;y or x   y",
        default=lambda self: self._get_default_points_data()
    )

    @api.model
    def _get_default_points_data(self):
        """Populate the data field with current points of the selected polygon."""
        polygon_id = self._context.get('active_id')
        if polygon_id:
            polygon = self.env['kojto.profile.shape.polygons'].browse(polygon_id)
            points = polygon.point_ids.sorted(lambda p: p.id)  # Sort by ID for consistent order
            if points:
                return "\n".join(f"{p.x};{p.y}" for p in points)
        return ""

    def action_import_polygon_points(self):
        """Parse input and create polygon points. Create shape if polygon lacks one."""
        self.ensure_one()
        try:
            points = self._parse_points_data(self.data)
            polygon = self.polygon_id

            if not polygon.shape_id:
                shape = self.env['kojto.profile.shapes'].create({
                    'name': f"Temporary Shape for {polygon.name or 'Unnamed Polygon'}"
                })
                self._cr.execute("""
                    UPDATE kojto_profile_shape_polygons
                    SET shape_id = %s
                    WHERE id = %s
                """, (shape.id, polygon.id))
                self._cr.commit()
                polygon.invalidate_cache(['shape_id'])  # Ensure field is updated

            self._create_points(points)

            # 🔁 Force polygon and shape drawing recalculation
            self.env.cr.flush()  # Make sure points are saved
            polygon._compute_polygon_drawing()
            polygon.shape_id._compute_area()
            polygon.shape_id._compute_shape_drawing()

            for profile in polygon.shape_id.insert_ids.mapped('profile_id'):
                profile._compute_drawing()

            return {'type': 'ir.actions.act_window_close'}

        except Exception as e:
            raise ValidationError(f"Error importing points: {e}")

    def _parse_points_data(self, data):
        """Extract (x, y) pairs from a semicolon/comma/tab-separated list."""
        lines = [line.strip() for line in data.strip().split("\n") if line.strip()]
        if not lines:
            raise ValidationError("No valid points data provided.")

        header = lines[0].replace("\t", ";").replace(",", ";").split(";")
        start_idx = 1 if [h.upper() for h in header] == ["X", "Y"] else 0

        if len(lines) <= start_idx:
            raise ValidationError("No valid point rows provided.")

        points = []
        for line in lines[start_idx:]:
            parts = line.replace("\t", ";").replace(",", ";").split(";")
            if len(parts) != 2:
                raise ValidationError(f"Invalid format (must be two numbers per line): {line}")
            try:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
            except ValueError:
                raise ValidationError(f"Invalid number format in row: {line}")
            points.append((x, y))

        if len(points) < 3:
            raise ValidationError("At least 3 points are required to form a polygon.")

        return points

    def _create_points(self, points):
        """Remove old points and create new ones for the polygon."""
        self.polygon_id.point_ids.unlink()
        for x, y in points:
            self.env['kojto.profile.shape.polygon.points'].create({
                'polygon_id': self.polygon_id.id,
                'x': x,
                'y': y,
            })

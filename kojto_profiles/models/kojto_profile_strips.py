#$ kojto_profiles/models/kojto_profile_strips.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import math

# Import the new external utility for SVG computation and compute_strip_points
from ..utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points
from ..utils.compute_strip_points import compute_strip_points

class KojtoProfileStrips(models.Model):
    _name = "kojto.profile.strips"
    _description = "Kojto Profile Strips"
    _rec_name = "name"

    name = fields.Char(string="Description", required=True)
    point_1_x = fields.Float(string="X1", default=0.0)
    point_1_y = fields.Float(string="Y1", default=10.0)
    point_2_x = fields.Float(string="X2", default=0.0)
    point_2_y = fields.Float(string="Y2", default=100.0)
    thickness = fields.Float(string="Thickness", default=10.0)
    angle_1 = fields.Float(string="AngleR", default=90)
    angle_2 = fields.Float(string="AngleL", default=90)
    point_1o_x = fields.Float(string="X3", compute="compute_strip_points")
    point_1o_y = fields.Float(string="Y3", compute="compute_strip_points")
    point_2o_x = fields.Float(string="X4", compute="compute_strip_points")
    point_2o_y = fields.Float(string="Y4", compute="compute_strip_points")
    profile_id = fields.Many2one("kojto.profiles", string="Profile", ondelete="cascade")

    description_point_ids = fields.One2many("kojto.profile.description.points", "profile_strip_id", string="Description Points")

    drawing = fields.Binary("Image", compute="_compute_strip_drawing")

    strip_cross_sectional_area = fields.Float(string="Strip Area", compute="_compute_strip_cross_sectional_area", store=False)

    @api.depends('point_1_x', 'point_1_y', 'point_2_x', 'point_2_y', 'point_1o_x', 'point_1o_y', 'point_2o_x', 'point_2o_y', 'thickness')
    def _compute_strip_cross_sectional_area(self):
        for rec in self:
            dx1 = rec.point_2_x - rec.point_1_x
            dy1 = rec.point_2_y - rec.point_1_y
            base_1 = math.sqrt(dx1**2 + dy1**2)
            dx2 = rec.point_2o_x - rec.point_1o_x
            dy2 = rec.point_2o_y - rec.point_1o_y
            base_2 = math.sqrt(dx2**2 + dy2**2)
            strip_cross_sectional_area = 0.5 * (base_1 + base_2) * rec.thickness
            rec.strip_cross_sectional_area = strip_cross_sectional_area / 100

    projected_length = fields.Float(string="Projected Length", compute="_compute_projected_length", store=False)

    @api.depends('point_1_x', 'point_1_y', 'point_2_x', 'point_2_y', 'thickness', 'angle_1', 'angle_2')
    def _compute_projected_length(self):
        for rec in self:
            dx = rec.point_2_x - rec.point_1_x
            dy = rec.point_2_y - rec.point_1_y
            length = math.sqrt(dx**2 + dy**2)
            def cotangent(angle):
                return 1 / math.tan(math.radians(angle))
            if rec.angle_1 > 90:
                length -= rec.thickness * cotangent(rec.angle_1)
            if rec.angle_2 > 90:
                length -= rec.thickness * cotangent(rec.angle_2)
            rec.projected_length = length

    @api.depends("point_1_x", "point_1_y", "point_2_x", "point_2_y", "thickness", "angle_1", "angle_2")
    def compute_strip_points(self):
        for rec in self:
            # Call the utility function with the record's values
            (point_1o_x, point_1o_y), (point_2o_x, point_2o_y) = compute_strip_points(
                rec.point_1_x, rec.point_1_y,
                rec.point_2_x, rec.point_2_y,
                rec.thickness, rec.angle_1, rec.angle_2
            )
            # Assign the computed values to the fields
            rec.point_1o_x = point_1o_x
            rec.point_1o_y = point_1o_y
            rec.point_2o_x = point_2o_x
            rec.point_2o_y = point_2o_y

    @api.constrains("angle_1", "angle_2")
    def check_angle_limits(self):
        for rec in self:
            if not 30 <= rec.angle_1 <= 150:
                raise ValidationError("Right Angle Adjustment must be between 30° and 150°.")
            if not 30 <= rec.angle_2 <= 150:
                raise ValidationError("Left Angle Adjustment must be between 30° and 150°.")

    @api.constrains("thickness")
    def check_thickness_limits(self):
        for rec in self:
            if not 2 <= rec.thickness <= 50:
                raise ValidationError("Thickness must be between 2 mm and 50 mm.")

    @api.constrains("point_1_x", "point_1_y", "point_2_x", "point_2_y")
    def check_length_limits(self):
        for rec in self:
            dx = rec.point_2_x - rec.point_1_x
            dy = rec.point_2_y - rec.point_1_y
            length = math.sqrt(dx**2 + dy**2)
            if not 20 <= length <= 1200:
                raise ValidationError("The length between Point 1 and Point 2 must be between 20 mm and 1200 mm.")

    @api.depends("point_1_x", "point_1_y", "point_2_x", "point_2_y", "point_1o_x", "point_1o_y", "point_2o_x", "point_2o_y",
                 "description_point_ids", "description_point_ids.x", "description_point_ids.y",
                 "description_point_ids.description", "description_point_ids.color",
                 "description_point_ids.representation_shape", "description_point_ids.representation_shape_size",
                 "description_point_ids.description_offset_x", "description_point_ids.description_offset_y",
                 "description_point_ids.description_size")
    def _compute_strip_drawing(self):
        for rec in self:
            polygon = [
                (rec.point_1_x, rec.point_1_y),
                (rec.point_2_x, rec.point_2_y),
                (rec.point_2o_x, rec.point_2o_y),
                (rec.point_1o_x, rec.point_1o_y)
            ]

            # Get description points data
            description_points_data = []
            for point in rec.description_point_ids:
                description_points_data.append({
                    'points': [{
                        'x': point.x,
                        'y': point.y,
                        'description': point.description,
                        'color': point.get_color_hex(),
                        'size': point.representation_shape_size,
                        'description_offset_x': point.description_offset_x,
                        'description_offset_y': point.description_offset_y,
                        'description_size': point.description_size,
                        'shape_type': point.representation_shape,
                        'shape_size': point.representation_shape_size
                    }]
                })

            svg_data = compute_svg_from_polygons_and_points(
                [polygon],
                description_points_data,
                show_origin_points=True
            )
            rec.drawing = svg_data if svg_data else False

    @api.onchange("point_1_x", "point_1_y", "point_2_x", "point_2_y", "thickness", "angle_1", "angle_2")
    def _onchange_coordinates(self):
        self.compute_strip_points()
        self._compute_strip_drawing()


    def open_strip_window(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kojto Profile Strip',
            'res_model': 'kojto.profile.strips',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }


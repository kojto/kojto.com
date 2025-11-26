#$ kojto_profiles/models/kojto_profile_configurator.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ..utils.compute_section_properties_polygons import compute_section_properties
from ..utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points
from ..utils.compute_contact_lines_polygons import compute_contact_lines
from ..utils.compute_coating_perimeter_polygons import compute_coating_perimeter
from ..utils.compute_strip_points import compute_strip_points
from ..utils.compute_external_corners import compute_external_corners
from math import sqrt

class KojtoProfileConfigurator(models.TransientModel):
    _name = "kojto.profile.configurator"
    _description = "Kojto Profile Configurator"
    _rec_name = "name"

    name = fields.Char(string="Profile Name", default="Default name")
    a1 = fields.Float(string="A Thickness", default=10.0)
    a2 = fields.Float(string="A Length", default=100.0)
    b1 = fields.Float(string="B Thickness", default=10.0)
    b2 = fields.Float(string="B Length", default=90.0)
    b3 = fields.Float(string="B Distance", default=0.0)
    c1 = fields.Float(string="C Thickness", default=0.0)
    c2 = fields.Float(string="C Length", default=0.0)
    c3 = fields.Float(string="C Distance", default=0.0)
    d1 = fields.Float(string="D Thickness", default=0.0)
    d3 = fields.Float(string="D Distance", default=0.0)
    batch_id = fields.Integer(string="Batch") # this serves the creation of the profile into the batch
    material_id = fields.Many2one("kojto.base.material.grades", string="Material", default=18) #18 = S235
    profile_cross_sectional_area = fields.Float(string="Total Area", compute="_compute_section_properties")
    profile_weight = fields.Float(string="Weight", compute="_compute_section_properties")
    jx = fields.Float(string="Jx", compute="_compute_section_properties")
    jy = fields.Float(string="Jy", compute="_compute_section_properties")
    wx = fields.Float(string="Wx", compute="_compute_section_properties")
    wy = fields.Float(string="Wy", compute="_compute_section_properties")
    center_of_mass_x = fields.Float(string="Center of Mass X", compute="_compute_section_properties")
    center_of_mass_y = fields.Float(string="Center of Mass Y", compute="_compute_section_properties")
    max_height = fields.Float(string="h", compute="_compute_section_properties")
    max_width = fields.Float(string="w", compute="_compute_section_properties")
    coating_perimeter = fields.Float(string="U(mm)", compute="_compute_coating_perimeter")
    number_ext_corners = fields.Integer(string="Number of External corners", compute="_compute_number_external_corners")
    drawing = fields.Binary(string="Profile Drawing", compute="_compute_drawing")

    profile_library_id = fields.Many2one("kojto.profile.configurator.library", string="Select Profile from Library")

    def _get_polygons(self):
        """Generate polygons in memory based on configurator parameters."""
        polygons = []
        if self.a1 > 0 and self.a2 > 0:
            point_1_x, point_1_y = 0.0, 0.0
            point_2_x, point_2_y = self.a2, 0.0
            (point_1o_x, point_1o_y), (point_2o_x, point_2o_y) = compute_strip_points(
                point_1_x, point_1_y, point_2_x, point_2_y, self.a1, 90, 90
            )
            polygons.append([(point_1_x, point_1_y), (point_2_x, point_2_y), (point_2o_x, point_2o_y), (point_1o_x, point_1o_y)])
        if self.b1 > 0.0 and self.b2 > 0.0:
            point_1_x, point_1_y = self.b3 + self.b1, self.a1
            point_2_x, point_2_y = self.b3 + self.b1, self.a1 + self.b2
            (point_1o_x, point_1o_y), (point_2o_x, point_2o_y) = compute_strip_points(
                point_1_x, point_1_y, point_2_x, point_2_y, self.b1, 90, 90
            )
            polygons.append([(point_1_x, point_1_y), (point_2_x, point_2_y), (point_2o_x, point_2o_y), (point_1o_x, point_1o_y)])
        if self.c1 > 0.0 and self.c2 > 0.0:
            point_1_x, point_1_y = self.c3, self.a1 + self.b2
            point_2_x, point_2_y = self.c3 + self.c2, self.a1 + self.b2
            (point_1o_x, point_1o_y), (point_2o_x, point_2o_y) = compute_strip_points(
                point_1_x, point_1_y, point_2_x, point_2_y, self.c1, 90, 90
            )
            polygons.append([(point_1_x, point_1_y), (point_2_x, point_2_y), (point_2o_x, point_2o_y), (point_1o_x, point_1o_y)])
        if self.d1 > 0.0 and self.d3 >= 0.0:
            point_1_x, point_1_y = self.a2 - self.d3, self.a1
            point_2_x, point_2_y = self.a2 - self.d3, self.a1 + self.b2
            (point_1o_x, point_1o_y), (point_2o_x, point_2o_y) = compute_strip_points(
                point_1_x, point_1_y, point_2_x, point_2_y, self.d1, 90, 90
            )
            polygons.append([(point_1_x, point_1_y), (point_2_x, point_2_y), (point_2o_x, point_2o_y), (point_1o_x, point_1o_y)])
        return polygons

    @api.depends('a1', 'a2', 'b1', 'b2', 'b3', 'c1', 'c2', 'c3', 'd1', 'd3', 'material_id')
    def _compute_section_properties(self):
        for record in self:
            density = record.material_id.density if record.material_id and hasattr(record.material_id, 'density') else 1000
            polygons = record._get_polygons()
            properties = compute_section_properties(polygons, density)
            record.profile_cross_sectional_area = properties["profile_cross_sectional_area"]
            record.profile_weight = properties["profile_weight"]
            record.center_of_mass_x = properties["center_of_mass_x"]
            record.center_of_mass_y = properties["center_of_mass_y"]
            record.jx = properties["jx"]
            record.jy = properties["jy"]
            record.wx = properties["wx"]
            record.wy = properties["wy"]
            record.max_height = properties["max_height"]
            record.max_width = properties["max_width"]

    @api.depends('a1', 'a2', 'b1', 'b2', 'b3', 'c1', 'c2', 'c3', 'd1', 'd3')
    def _compute_coating_perimeter(self):
        for record in self:
            polygons = record._get_polygons()
            record.coating_perimeter = compute_coating_perimeter(polygons) or 0.0

    @api.depends('a1', 'a2', 'b1', 'b2', 'b3', 'c1', 'c2', 'c3', 'd1', 'd3')
    def _compute_number_external_corners(self):
        for record in self:
            polygons = record._get_polygons()
            count = compute_external_corners(polygons)  # Single integer return
            record.number_ext_corners = count or 0

    @api.depends('a1', 'a2', 'b1', 'b2', 'b3', 'c1', 'c2', 'c3', 'd1', 'd3')
    def _compute_drawing(self):
        for record in self:
            polygons = record._get_polygons()
            record.drawing = compute_svg_from_polygons_and_points(polygons, show_origin_points=True) or False

    @api.onchange('a1', 'a2', 'b1', 'b2', 'b3', 'c1', 'c2', 'c3', 'd1', 'd3')
    def _onchange_parameters(self):
        self._compute_section_properties()
        self._compute_coating_perimeter()
        self._compute_number_external_corners()
        self._compute_drawing()

    def create_profile_from_configurator(self):
        self.ensure_one()
        profile_vals = {
            'name': self.name,
            'material_id': self.material_id.id if self.material_id else False,
        }
        new_profile = self.env['kojto.profiles'].create(profile_vals)
        self.env.cr.commit()

        if new_profile.strip_ids:
            new_profile.strip_ids.unlink()
            self.env.cr.commit()

        polygons = self._get_polygons()
        strip_vals_list = []
        for idx, polygon in enumerate(polygons):
            point_1_x, point_1_y = polygon[0]
            point_2_x, point_2_y = polygon[1]
            point_2o_x, point_2o_y = polygon[2]
            point_1o_x, point_1o_y = polygon[3]
            if idx == 0:  # Strip A
                thickness, angle_1, angle_2 = self.a1, 90, 90
            elif idx == 1:  # Strip B
                thickness, angle_1, angle_2 = self.b1, 90, 90
            elif idx == 2:  # Strip C
                thickness, angle_1, angle_2 = self.c1, 90, 90
            elif idx == 3:  # Strip D
                thickness, angle_1, angle_2 = self.d1, 90, 90
            strip_vals = {
                'name': f"{self.name} - Strip {chr(65 + idx)}",
                'point_1_x': point_1_x,
                'point_1_y': point_1_y,
                'point_2_x': point_2_x,
                'point_2_y': point_2_y,
                'thickness': thickness,
                'angle_1': angle_1,
                'angle_2': angle_2,
                'profile_id': new_profile.id,
            }
            strip_vals_list.append(strip_vals)

        if strip_vals_list:
            try:
                self.env['kojto.profile.strips'].create(strip_vals_list)
                self.env.cr.commit()
            except Exception as e:
                raise

        batch_id = self.batch_id
        if batch_id:
            self.env['kojto.profile.batch.content'].create({
                'batch_id': batch_id,  # Use batch_id directly (not batch_id.id)
                'profile_id': new_profile.id,
                'length': 0.0,
                'quantity': 1,
            })
            self.env.cr.commit()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Profile Batch',
                'res_model': 'kojto.profile.batches',
                'view_mode': 'form',
                'res_id': batch_id,  # Use batch_id directly
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Profile',
            'res_model': 'kojto.profiles',
            'view_mode': 'form',
            'res_id': new_profile.id,
            'target': 'current',
        }

    @api.onchange('profile_library_id')
    def _onchange_profile_library(self):
        if self.profile_library_id:
            self.name = self.profile_library_id.name
            self.a1 = self.profile_library_id.a1
            self.a2 = self.profile_library_id.a2
            self.b1 = self.profile_library_id.b1
            self.b2 = self.profile_library_id.b2
            self.b3 = self.profile_library_id.b3
            self.c1 = self.profile_library_id.c1
            self.c2 = self.profile_library_id.c2
            self.c3 = self.profile_library_id.c3
            self.d1 = self.profile_library_id.d1
            self.d3 = self.profile_library_id.d3
            self.material_id = self.profile_library_id.material_id
            # Optional: Recompute the section properties
            self._onchange_parameters()

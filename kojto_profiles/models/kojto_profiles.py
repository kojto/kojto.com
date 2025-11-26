from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import ezdxf
import tempfile
import os
from ..utils.compute_section_properties_polygons import compute_section_properties
from ..utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points
from ..utils.compute_contact_lines_polygons import compute_contact_lines
from ..utils.compute_coating_perimeter_polygons import compute_coating_perimeter
from ..utils.compute_external_corners import compute_external_corners


class KojtoProfiles(models.Model):
    _name = "kojto.profiles"
    _description = "Kojto Profiles"
    _rec_name = "name"
    _sql_constraints = [("name_unique", "UNIQUE(name)", "The profile name must be unique.")]

    name = fields.Char(string="Profile Name", required=True)
    active = fields.Boolean(string="Is Active", default=True)
    material_id = fields.Many2one("kojto.base.material.grades", string="Material", required=True)
    strip_ids = fields.One2many("kojto.profile.strips", "profile_id", string="Profile Strips")
    shape_insert_ids = fields.One2many("kojto.profile.shape.inserts", "profile_id", string="Shape Inserts")
    drawing = fields.Binary("Combined Drawing", compute="_compute_drawing")
    autocad_dxf = fields.Binary("AutoCAD DXF", readonly=True)
    process_ids = fields.One2many("kojto.profile.processes", "profile_id", string="Processes")
    contact_lines_list = fields.Text(string="Contact Lines Text", compute="_compute_contact_lines_text")
    total_process_time_per_m = fields.Float(string="Total Process Time per Meter (min/m)", compute="_compute_total_process_time_per_m", help="Total time required per meter for all processes combined, in minutes.")
    profile_cross_sectional_area = fields.Float(string="Total Area", compute="_compute_section_properties")
    profile_weight = fields.Float(string="Weight per m", compute="_compute_section_properties")
    jx = fields.Float(string="Jx", compute="_compute_section_properties")
    jy = fields.Float(string="Jy", compute="_compute_section_properties")
    wx = fields.Float(string="Wx", compute="_compute_section_properties")
    wy = fields.Float(string="Wy", compute="_compute_section_properties")
    center_of_mass_x = fields.Float(string="Center of Mass X", compute="_compute_section_properties")
    center_of_mass_y = fields.Float(string="Center of Mass Y", compute="_compute_section_properties")
    max_height = fields.Float(string="h", compute="_compute_section_properties")
    max_width = fields.Float(string="w", compute="_compute_section_properties")
    coating_perimeter = fields.Float(string="U(mm)", compute="_compute_coating_perimeter")
    number_ext_corners = fields.Integer(string="Number of External Corners", compute="_compute_number_external_corners")

    #points with description in the SVG
    profile_description_point_ids = fields.One2many("kojto.profile.description.points", "profile_id", string="Profile Points")


    profile_description = fields.Text(string="Profile Description")
    profile_perimeter_coordinates = fields.Json(string="Profile Perimeter Coordinates", compute="_compute_section_properties")


    # Python Constraints
    @api.constrains("strip_ids")
    def _check_strip_ids(self):
        for record in self:
            if not record.strip_ids:
                raise ValidationError("A profile must have at least one strip defined.")

    @api.depends("process_ids.time_per_meter")
    def _compute_total_process_time_per_m(self):
        for record in self:
            record.total_process_time_per_m = sum(process.time_per_meter for process in record.process_ids) or 0.0

    def _get_polygons_data(self):
        """Get polygons data from strips and shape inserts with translation and rotation."""
        polygons_data = []

        # Add polygons from strips
        for strip in self.strip_ids:
            polygon = [
                (strip.point_1_x, strip.point_1_y),
                (strip.point_2_x, strip.point_2_y),
                (strip.point_2o_x, strip.point_2o_y),
                (strip.point_1o_x, strip.point_1o_y)
            ]
            if len(polygon) > 0:
                polygons_data.append(polygon)

        # Add polygons from shape inserts with translation and rotation
        for insert in self.shape_insert_ids:
            if insert.shape_id and insert.shape_id.polygon_ids:
                offset_x = insert.x
                offset_y = insert.y
                rotation = insert.rotation if hasattr(insert, 'rotation') else 0.0
                for polygon in insert.shape_id.polygon_ids:
                    if not polygon.point_ids:
                        continue
                    rotated_points = []
                    for point in polygon.point_ids:
                        import math
                        x_rotated = point.x * math.cos(math.radians(rotation)) - point.y * math.sin(math.radians(rotation))
                        y_rotated = point.x * math.sin(math.radians(rotation)) + point.y * math.cos(math.radians(rotation))
                        x_translated = x_rotated + offset_x
                        y_translated = y_rotated + offset_y
                        rotated_points.append((x_translated, y_translated))
                    if len(rotated_points) >= 3:
                        polygons_data.append({
                            'points': rotated_points,
                            'is_subtract': not polygon.is_external,
                            'id_different_color': polygon.is_external
                        })

        return polygons_data

    def _get_description_points_data(self):
        points_data = []
        for point in self.profile_description_point_ids:
            points_data.append({
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
        return points_data

    def _get_polygons_for_dxf(self):
        """Get all polygons for DXF export, converting dict format to list of points."""
        polygons_data = self._get_polygons_data()
        polygons = []
        for item in polygons_data:
            if isinstance(item, dict):
                polygons.append(item['points'])
            else:
                polygons.append(item)
        return polygons

    @api.depends("strip_ids", "strip_ids.point_1_x", "strip_ids.point_1_y", "strip_ids.point_2_x", "strip_ids.point_2_y",
                 "strip_ids.point_2o_x", "strip_ids.point_2o_y", "strip_ids.point_1o_x", "strip_ids.point_1o_y",
                 "shape_insert_ids", "shape_insert_ids.x", "shape_insert_ids.y", "shape_insert_ids.rotation",
                 "shape_insert_ids.shape_id", "shape_insert_ids.shape_id.polygon_ids",
                 "shape_insert_ids.shape_id.polygon_ids.point_ids", "shape_insert_ids.shape_id.polygon_ids.point_ids.x",
                 "shape_insert_ids.shape_id.polygon_ids.point_ids.y", "material_id", "material_id.density")
    def _compute_section_properties(self):
        for record in self:
            record.profile_cross_sectional_area = 0.0
            record.profile_weight = 0.0
            record.jx = 0.0
            record.jy = 0.0
            record.wx = 0.0
            record.wy = 0.0
            record.center_of_mass_x = 0.0
            record.center_of_mass_y = 0.0
            record.max_height = 0.0
            record.max_width = 0.0
            record.profile_perimeter_coordinates = []
            density = record.material_id.density if record.material_id and hasattr(record.material_id, "density") else 1000
            polygons_data = record._get_polygons_data()
            polygons_data = [p for p in polygons_data if (isinstance(p, dict) and p['points']) or (isinstance(p, list) and p)]
            if polygons_data:
                properties = compute_section_properties(polygons_data, density)
                record.profile_cross_sectional_area = properties.get("profile_cross_sectional_area", 0.0)
                record.profile_weight = properties.get("profile_weight", 0.0)
                record.center_of_mass_x = properties.get("center_of_mass_x", 0.0)
                record.center_of_mass_y = properties.get("center_of_mass_y", 0.0)
                record.jx = properties.get("jx", 0.0)
                record.jy = properties.get("jy", 0.0)
                record.wx = properties.get("wx", 0.0)
                record.wy = properties.get("wy", 0.0)
                record.max_height = properties.get("max_height", 0.0)
                record.max_width = properties.get("max_width", 0.0)
                # Round perimeter coordinates to 2 decimal places
                perimeter_coords = properties.get("perimeter_coordinates", [])
                record.profile_perimeter_coordinates = [[round(x, 2), round(y, 2)] for x, y in perimeter_coords]

    @api.depends("strip_ids", "strip_ids.point_1_x", "strip_ids.point_1_y", "strip_ids.point_2_x", "strip_ids.point_2_y",
                 "strip_ids.point_2o_x", "strip_ids.point_2o_y", "strip_ids.point_1o_x", "strip_ids.point_1o_y",
                 "shape_insert_ids", "shape_insert_ids.x", "shape_insert_ids.y", "shape_insert_ids.rotation",
                 "shape_insert_ids.shape_id", "shape_insert_ids.shape_id.polygon_ids",
                 "shape_insert_ids.shape_id.polygon_ids.point_ids", "shape_insert_ids.shape_id.polygon_ids.point_ids.x",
                 "shape_insert_ids.shape_id.polygon_ids.point_ids.y",
                 "profile_description_point_ids", "profile_description_point_ids.x", "profile_description_point_ids.y",
                 "profile_description_point_ids.description_offset_x", "profile_description_point_ids.description_offset_y",
                 "profile_description_point_ids.description_size")
    def _compute_drawing(self):
        for record in self:
            polygons_data = record._get_polygons_data()
            description_points_data = record._get_description_points_data()
            polygons_data = [p for p in polygons_data if (isinstance(p, dict) and p['points']) or (isinstance(p, list) and p)]
            description_points_data = [p for p in description_points_data if p['points']]

            record.drawing = compute_svg_from_polygons_and_points(
                polygons_data,
                description_points_data,
                show_origin_points=False
            ) or False

    @api.depends("strip_ids", "shape_insert_ids")
    def _compute_coating_perimeter(self):
        for record in self:
            polygons_data = record._get_polygons_data()
            polygons_data = [p for p in polygons_data if (isinstance(p, dict) and p['points']) or (isinstance(p, list) and p)]
            external_polygons = []
            for item in polygons_data:
                if isinstance(item, dict):
                    if not item.get('is_subtract', False) and item['points']:
                        external_polygons.append(item['points'])
                elif isinstance(item, list) and item:
                    external_polygons.append(item)
            record.coating_perimeter = compute_coating_perimeter(external_polygons) or 0.0

    @api.depends("strip_ids", "shape_insert_ids")
    def _compute_contact_lines_text(self):
        for record in self:
            polygons_data = record._get_polygons_data()
            polygons_data = [p for p in polygons_data if (isinstance(p, dict) and p['points']) or (isinstance(p, list) and p)]
            external_polygons = []
            for item in polygons_data:
                if isinstance(item, dict):
                    if not item.get('is_subtract', False) and item['points']:
                        external_polygons.append(item['points'])
                elif isinstance(item, list) and item:
                    external_polygons.append(item)
            contact_lines_result, _, _ = compute_contact_lines(external_polygons) if external_polygons else ([], [], [])
            contact_lines_str = "\n".join(
                f"({p1[0]:.2f}, {p1[1]:.2f}) - ({p2[0]:.2f}, {p2[1]:.2f})"
                for p1, p2 in contact_lines_result
            ) if contact_lines_result else ""
            record.contact_lines_list = contact_lines_str

    @api.depends("strip_ids", "shape_insert_ids")
    def _compute_number_external_corners(self):
        for record in self:
            polygons_data = record._get_polygons_data()
            polygons_data = [p for p in polygons_data if (isinstance(p, dict) and p['points']) or (isinstance(p, list) and p)]
            external_polygons = []
            for item in polygons_data:
                if isinstance(item, dict):
                    if not item.get('is_subtract', False) and item['points']:
                        external_polygons.append(item['points'])
                elif isinstance(item, list) and item:
                    external_polygons.append(item)
            record.number_ext_corners = compute_external_corners(external_polygons) or 0

    def generate_autocad_dxf(self):
        polygons = self._get_polygons_for_dxf()
        contact_lines_result, _, _ = compute_contact_lines(polygons) if polygons else ([], [], [])

        doc = ezdxf.new(dxfversion='R2010')
        msp = doc.modelspace()

        for i, polygon in enumerate(polygons, 1):
            points = [(x, y) for x, y in polygon]
            points.append(points[0])
            msp.add_lwpolyline(points, dxfattribs={'layer': 'Polygons'})

        for i, (p1, p2) in enumerate(contact_lines_result, 1):
            msp.add_line((p1[0], p1[1]), (p2[0], p2[1]), dxfattribs={'layer': 'ContactLines'})

        doc.layers.new('Polygons', dxfattribs={'color': 7})
        doc.layers.new('ContactLines', dxfattribs={'color': 1})
        doc.layers.new('Text', dxfattribs={'color': 2})

        section_properties = [
            f"Profile Name: {self.name}",
            f"Material: {self.material_id.name if self.material_id else 'N/A'}",
            f"Total Area: {self.profile_cross_sectional_area:.2f} mm²",
            f"Weight: {self.profile_weight:.2f} kg/m",
            f"Jx: {self.jx:.2f} mm⁴",
            f"Jy: {self.jy:.2f} mm⁴",
            f"Wx: {self.wx:.2f} mm³",
            f"Wy: {self.wy:.2f} mm³",
            f"Center of Mass X: {self.center_of_mass_x:.2f} mm",
            f"Center of Mass Y: {self.center_of_mass_y:.2f} mm",
            f"Max Height (h): {self.max_height:.2f} mm",
            f"Max Width (w): {self.max_width:.2f} mm",
            f"Coating Perimeter (U): {self.coating_perimeter:.2f} mm",
            f"Number of External corners: {self.number_ext_corners}"
        ]

        text_content = "\n".join(section_properties)

        msp.add_text(
            text_content,
            dxfattribs={
                'layer': 'Text',
                'height': 2.5,
                'style': 'Standard',
                'insert': (0, -self.max_height - 10, 0)
            }
        )

        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
            doc.saveas(tmp.name)
            with open(tmp.name, 'rb') as f:
                dxf_content = f.read()
            os.unlink(tmp.name)

        self.write({'autocad_dxf': base64.b64encode(dxf_content)})
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/autocad_dxf/{self.name}_autocad.dxf?download=true',
            'target': 'self',
        }

    def action_export_autocad(self):
        """Action method to export profile to AutoCAD DXF format."""
        return self.generate_autocad_dxf()

    def copy_with_relations(self):
        """Duplicate the record along with its relational fields."""
        for record in self:
            new_record = record.copy(
                {
                    "name": f"{record.name} (Copy)",
                    "autocad_dxf": False,
                }
            )
            for strip in record.strip_ids:
                strip.copy({"profile_id": new_record.id})
            for process in record.process_ids:
                process.copy({"profile_id": new_record.id})
            for shape_insert in record.shape_insert_ids:
                shape_insert.copy({"profile_id": new_record.id})
            for point in record.profile_description_point_ids:
                point.copy({"profile_id": new_record.id})
            return {
                "type": "ir.actions.act_window",
                "res_model": "kojto.profiles",
                "view_mode": "form",
                "res_id": new_record.id,
                "target": "current",
            }

    def generate_description_points(self):
        """Generate description points from profile perimeter coordinates and link them to strips if they coincide."""
        # Delete existing description points
        self.profile_description_point_ids.unlink()

        # Get perimeter coordinates
        if not self.profile_perimeter_coordinates:
            return

        # Get all strip points for this profile
        strip_points = []
        for strip in self.strip_ids:
            strip_points.append({
                'strip': strip,
                'points': [
                    (strip.point_1_x, strip.point_1_y),
                    (strip.point_2_x, strip.point_2_y),
                    (strip.point_1o_x, strip.point_1o_y),
                    (strip.point_2o_x, strip.point_2o_y)
                ]
            })

        # Create new description points
        for index, (x, y) in enumerate(self.profile_perimeter_coordinates, 1):
            # Check if this point coincides with any strip points
            matching_strips = []
            for strip_data in strip_points:
                for strip_x, strip_y in strip_data['points']:
                    # Use a small tolerance for floating point comparison
                    if abs(x - strip_x) < 0.01 and abs(y - strip_y) < 0.01:
                        matching_strips.append(strip_data['strip'])
                        break  # Found a match for this strip, no need to check other points

            # Create the description point
            vals = {
                'profile_id': self.id,
                'x': x,
                'y': y,
                'description': f'P_{index}',
                'color': 'red',
                'representation_shape': 'circle',
                'representation_shape_size': 3,
                'description_offset_x': 0,
                'description_offset_y': 0,
                'description_size': 10
            }

            # Only link to a strip if exactly one strip has a matching point
            if len(matching_strips) == 1:
                vals['profile_strip_id'] = matching_strips[0].id

            self.env['kojto.profile.description.points'].create(vals)

        # Force recompute of drawing
        self._compute_drawing()

